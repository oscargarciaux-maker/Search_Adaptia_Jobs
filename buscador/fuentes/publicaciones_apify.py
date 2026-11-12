"""Publicaciones «contratando» de LinkedIn con un actor de Apify sin sesión (solo si existe el secreto APIFY_TOKEN).

Reclutadores y empresas que publican "estamos contratando un Product Designer" en el feed, sin una oferta formal.
El actor (datos/config.yaml → apify.actor_publicaciones) busca publicaciones de las últimas 24 horas con las consultas
de cada rol (datos/entrega.yaml → consultas_publicaciones). Nunca se le da una cookie ni una sesión: un actor que la
pida no se usa. Cada publicación se paga (≈ USD 2 por 1.000 en harvestapi/linkedin-post-search), así que la corrida
tiene un tope de publicaciones por día.

Una publicación se propone para revisión solo si: anuncia una contratación (no es "open to work" ni un curso), nombra un cargo
del mapa, nombra un país de los activos o trabajo remoto, y se sabe la empresa (autor empresa, o el cargo del autor
dice "at/en <Empresa>"). El título es el cargo nombrado; nada se inventa. No se convierte automáticamente en oferta ni se envía a Supabase.
"""
import os
import re
import time

from buscador import enlaces, familias, normalizar, paises
from buscador.apify import Presupuesto, ejecutar
from buscador.fuentes import linkedin_publico

NOMBRE = "LinkedIn (publicación)"
API = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
CONTRATA = re.compile(r"\b(hiring|we.?re hiring|we are hiring|now hiring|join our team|join us|looking for an?|"
                      r"is looking for|open (?:role|position)|job opening|apply now|vacante|vacantes|estamos contratando|"
                      r"contratando|buscamos|estamos buscando|estamos en busqueda|se busca|oportunidad laboral|"
                      r"oferta laboral|unete|sumate|postulate|postula|envia tu cv|envianos tu cv|send your cv|"
                      r"send me your cv|dm me)\b")
RUIDO = re.compile(r"\b(open ?to ?work|opentowork|busco empleo|busco trabajo|estoy buscando (?:empleo|trabajo|"
                   r"nuevas oportunidades|una nueva oportunidad|mi (?:proximo|siguiente) (?:reto|desafio|empleo|trabajo))|"
                   r"me encuentro (?:buscando|en busqueda)|en busqueda (?:activa )?de (?:empleo|trabajo|nuevas oportunidades)|"
                   r"disponible para (?:nuevos? )?(?:proyectos|oportunidades|trabajar|empleo)|"
                   r"i.?m looking for (?:a new|my next|new opportunities|a job|work)|looking for my next|"
                   r"i.?m (?:currently )?(?:open|available) (?:to|for) (?:new )?(?:opportunities|roles|work)|"
                   r"seeking (?:a new|my next|new) (?:role|opportunit)|"
                   r"webinar|bootcamp|curso|course|masterclass|taller|workshop|mentoria|"
                   r"mentorship|certificacion gratuita|free certification|meetup|conferencia|charla|evento)\b")
# Contrato v11: avisos de «base de datos» o a futuro no son vacantes abiertas.
A_FUTURO = re.compile(r"\b(banco de (?:talento|talentos|candidatos|hojas de vida|cv)|base de datos|talent (?:pool|community|network)|"
                      r"futuras? (?:oportunidades|vacantes|procesos|posiciones)|futuros procesos|proximos procesos|"
                      r"future (?:opportunities|openings|roles|positions)|te (?:contactaremos|llamaremos)|"
                      r"(?:algun|un) dia|cuando (?:se abra|haya|surja)|registra(?:r)? tu (?:cv|hoja de vida)|"
                      r"deja(?:r)? tu (?:cv|hoja de vida) para|keep (?:your|you) (?:cv|resume|profile) on file|"
                      r"we.?ll (?:reach out|contact you) (?:in the future|when))\b")
# Una contratación real pide hacer algo: postular, enviar el CV, escribir o comentar.
ACCION = re.compile(r"\b(apply|aplica|aplicar|postula|postulate|postularse|postular|envia|enviame|envianos|send|dm|"
                    r"mensaje|message|escribe|escribeme|escribenos|contacta|contactame|contact me|reach out|inbox|"
                    r"comenta|comment|interesad[oa]s?|interested|link|enlace|correo|email|e-mail|whatsapp)\b")
CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CORREO_FALSO = re.compile(r"(?i)(no-?reply|@linkedin\.com$)")
_EMPRESA_CARGO = re.compile(r"(?:\bat\b|@|\ben\b|\bin\b|\|)\s*([A-Z0-9][\w&.,'’\- ]{1,40}?)(?=\s*(?:\||·|,|-|–|$))")


def entrada(actor, consultas, por_consulta, hoy):
    """Cuerpo de la corrida según el actor (cada uno nombra distinto sus campos)."""
    if "lofomachines" in actor:
        from datetime import date, timedelta
        ayer = (date.fromisoformat(hoy) - timedelta(days=1)).isoformat()
        return {"keywords": consultas, "maxPostsPerKeyword": max(10, por_consulta), "publishedAfter": ayer}
    return {"searchQueries": consultas, "maxPosts": por_consulta, "postedLimit": "24h", "sortBy": "date",
            "profileScraperMode": "short"}


def _campo(item, *claves):
    for c in claves:
        v = item
        for parte in c.split("."):
            v = v.get(parte) if isinstance(v, dict) else None
        if v:
            return v
    return ""


def empresa_de(item):
    """Empresa de la publicación: el autor si es una empresa; si es una persona, la del cargo que muestra
    ("Talent Acquisition at Rappi" → Rappi). '' si no se sabe."""
    tipo = str(_campo(item, "author.type", "authorType")).lower()
    nombre = str(_campo(item, "author.name", "authorName")).strip()
    if tipo in ("company", "organization", "empresa") and nombre:
        return nombre
    cargo = str(_campo(item, "author.info", "author.headline", "authorHeadline", "author.position")).strip()
    m = _EMPRESA_CARGO.search(cargo)
    if m:
        empresa = m.group(1).strip(" .,-–")
        if 1 < len(empresa) <= 40 and not re.match(r"(?i)(linkedin|remote|remoto|home|busca|search|the|la|el)\b", empresa):
            return empresa
    return ""


def cargo_de(texto, familias_validas):
    """El cargo del mapa que nombra la publicación (exacto o similar), escrito como en el mapa; '' si no nombra ninguno."""
    t = normalizar.texto(texto)
    for fam in familias.mapa():
        if fam["id"] not in familias_validas:
            continue
        for grado in ("exacto", "similar"):
            frases = sorted((f for f in fam["_titulos"][grado] if " " in f or "/" in f), key=len, reverse=True)
            for frase in frases:
                if normalizar.contiene_frase(t, frase):
                    crudo = next((c for c in fam.get("exactos" if grado == "exacto" else "similares", [])
                                  if normalizar.titulo_base(c) == frase), frase)
                    nivel = re.search(r"\b(senior|sr|junior|jr|semi ?senior|ssr|lead|trainee|intern)\b\s+" + re.escape(frase), t)
                    titulo = " ".join(w if w.isupper() or "/" in w else w[:1].upper() + w[1:] for w in crudo.split())
                    return (nivel.group(1).title() + " " + titulo) if nivel else titulo
    return ""


def contacto_de(item, texto):
    """Cómo escribirle a quien publicó: su perfil de LinkedIn (persona o empresa) y un correo si el post lo da."""
    perfil = str(_campo(item, "author.linkedinUrl", "author.url", "authorProfileUrl", "author.profileUrl")).split("?")[0]
    h = enlaces.host(perfil)
    if not ((h == "linkedin.com" or h.endswith(".linkedin.com")) and re.search(r"/(in|company)/[^/]+", perfil)):
        perfil = ""
    correo = next((c.rstrip(".") for c in CORREO.findall(texto or "") if not CORREO_FALSO.search(c.rstrip("."))), "")
    return {k: v for k, v in (("perfil", perfil), ("correo", correo)) if v}


def a_vacante(item, familias_validas, hoy=None, max_dias=30):
    """Vacante cruda (formato de las fuentes) o (None, motivo). Filtro estricto sin IA (contrato v11): anuncia una
    contratación y pide postular o escribir; no es alguien buscando empleo, un curso ni un «banco de talento»; nombra un
    cargo del mapa, un país activo o remoto, la empresa y una fecha dentro del plazo. La forma de contacto se exige
    después, solo al post que no enlaza una ficha formal (`contrato.entregable_post`)."""
    texto = str(_campo(item, "content", "text", "postText"))
    enlace = str(_campo(item, "linkedinUrl", "postUrl", "url", "socialContent.shareUrl"))
    h = enlaces.host(enlace)
    if not texto or not enlaces.sirve(enlace) or not (h == "linkedin.com" or h.endswith(".linkedin.com")):
        return None, "sin texto o enlace"
    t = normalizar.texto(texto)
    titular = normalizar.texto(str(_campo(item, "author.info", "author.headline", "authorHeadline")))
    if RUIDO.search(t) or RUIDO.search(titular):
        return None, "busca empleo, curso o evento"
    if A_FUTURO.search(t):
        return None, "banco de talento o vacante a futuro"
    if not CONTRATA.search(t):
        return None, "no anuncia una contratación"
    if len(set(re.findall(r"https?://\S+", texto))) > 3:
        return None, "lista de vacantes de terceros"
    titulo = cargo_de(texto, familias_validas)
    if not titulo:
        return None, "sin cargo del mapa"
    empresa = empresa_de(item)
    if not empresa:
        return None, "sin empresa"
    nombrados = paises._paises_nombrados(t)
    remoto = bool(paises._REMOTO.search(t) or paises._REMOTO_DESC.search(t))
    if not nombrados and not remoto:
        return None, "sin país ni remoto"
    if not ACCION.search(t) and not re.search(r"https?://", texto):
        return None, "no pide postular ni escribir"
    fecha = str(_campo(item, "postedAt.date", "postedAt", "publishedAt", "date"))[:10]
    fecha = fecha if re.match(r"\d{4}-\d{2}-\d{2}$", fecha) else ""
    if hoy and fecha:
        from datetime import date
        edad = (date.fromisoformat(hoy) - date.fromisoformat(fecha)).days
        if not 0 <= edad <= max_dias:
            return None, "fuera del plazo"
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    return {
        "titulo": titulo, "empresa": empresa, "ubicacion": ", ".join(nombres[c] for c in nombrados[:3]),
        "descripcion": texto[:15000], "fecha": fecha,
        "enlace": enlace.split("?")[0], "enlace_directo": "", "remoto": True if remoto else None, "fuente": NOMBRE,
        "contacto": contacto_de(item, texto),  # sin contacto puede servir si enlaza una ficha; un post solo no
    }, ""


def resolver_oferta(cliente, item, familias_validas):
    """Un post puede descubrir una ficha; se entrega el contenido de la ficha, nunca se certifica el post."""
    texto = str(_campo(item, "content", "text", "postText"))
    urls = re.findall(r"https?://[^\s<>\"']+", texto)
    urls += [str(_campo(item, "externalUrl", "article.url", "link.url"))]
    for url in urls[:10]:
        url = url.rstrip(".,;:!?)")
        if not enlaces.es_linkedin(url):
            continue
        jid = re.search(r"(\d+)/?$", url.split("?")[0])
        if not jid:
            continue
        respuesta = cliente.get(linkedin_publico.AVISO + jid.group(1))
        if respuesta is None or respuesta.status_code != 200:
            continue
        desc, cerrada, _, _ = linkedin_publico.ficha(respuesta.text)
        def campo(patron):
            m = re.search(patron, respuesta.text)
            return linkedin_publico.texto_html(m.group(1)) if m else ""
        titulo = campo(r'<h1[^>]*>([\s\S]*?)</h1>')
        empresa = campo(r'topcard__org-name-link[^>]*>([\s\S]*?)</a>')
        lugar = campo(r'topcard__flavor--bullet[^>]*>([\s\S]*?)</span>')
        if cerrada or len(desc) < 200 or not titulo or not empresa:
            continue
        if not any(f["familia"] in familias_validas for f in familias.clasificar(titulo, desc)):
            continue
        return {"titulo": titulo, "empresa": empresa, "descripcion": desc, "ubicacion": lugar,
                "enlace": f"https://www.linkedin.com/jobs/view/{jid.group(1)}/", "fecha": "",
                "fuente": "LinkedIn (oferta desde feed)", "remoto": None}
    return None


def buscar(cliente, actor, consultas, familias_validas, hoy, maximo=60, token=None, reloj=time.monotonic,
           control_gasto=None):
    """Corre el actor una vez con todas las consultas. Devuelve (vacantes crudas, estadísticas)."""
    inicio = reloj()
    token = token or os.environ.get("APIFY_TOKEN", "")
    if not token or not actor:
        return [], {"omitida": "sin APIFY_TOKEN o sin actor_publicaciones en datos/config.yaml"}
    if not consultas:
        return [], {"omitida": "sin consultas_publicaciones en datos/entrega.yaml"}
    if maximo <= 0:
        return [], {"omitida": "presupuesto reservado a ofertas formales"}
    control_gasto = control_gasto or Presupuesto({}, hoy)
    cargo = control_gasto.reservar(0.025)
    if not cargo:
        return [], {"omitida": "presupuesto de Apify agotado"}
    por_consulta = max(1, maximo // len(consultas))
    items, ejecucion = ejecutar(cliente, actor, entrada(actor, consultas, por_consulta, hoy), token,
                                cargo, max_items=maximo, limite_segundos=180)
    if ejecucion.get("error"):
        return [], ejecucion
    crudas, motivos, revision = [], {}, []
    for item in items if isinstance(items, list) else []:
        if reloj() - inicio >= 180:
            break
        if not isinstance(item, dict) or item.get("type") in ("comment", "reaction"):
            continue
        v, motivo = a_vacante(item, familias_validas)
        if v:
            formal = resolver_oferta(cliente, item, familias_validas)
            if formal:
                crudas.append(formal)
                continue
            # Una publicación de contratación es un indicio, no una oferta formal comprobada.
            # No llenar cuotas ni enviar a Supabase hasta verificar su oferta original.
            revision.append({"titulo": v["titulo"], "empresa": v["empresa"], "enlace": v["enlace"],
                             "motivo": "publicación pendiente de verificar contra una oferta formal"})
        else:
            motivos[motivo] = motivos.get(motivo, 0) + 1
    return crudas, {"consultas": len(consultas), "publicaciones": len(items) if isinstance(items, list) else 0,
                    "vacantes": len(crudas), "pendientes_revision": len(revision), "muestras_revision": revision[:10],
                    "ejecucion": ejecucion,
                    "descartadas": motivos}


def consultas_post(terminos, maximo=2):
    """Consultas del buscador de posts para un cargo: contratación + el término exacto (máx. 5 operadores)."""
    return [f'(hiring OR contratando OR vacante OR buscamos) "{t}"' for t in list(dict.fromkeys(terminos))[:maximo]]


def buscar_posts(cliente, actor, consultas, familias_validas, hoy, maximo=30, token=None, control_gasto=None,
                 max_dias=30, reloj=time.monotonic):
    """Contrato v11: posts para perfiles con déficit. Devuelve (fichas formales, posts, estadísticas). Un post que enlaza
    a una ficha formal se entrega como esa ficha; sin ficha, queda como post etiquetado (nunca en el cupo ni en
    `ofertas`). Las estadísticas solo traen conteos."""
    from buscador import vacante
    inicio = reloj()
    token = token or os.environ.get("APIFY_TOKEN", "")
    if not token or not actor:
        return [], [], {"omitida": "sin APIFY_TOKEN o sin actor_publicaciones"}
    if not consultas or maximo <= 0:
        return [], [], {"omitida": "sin consultas o sin posts en el presupuesto"}
    control_gasto = control_gasto or Presupuesto({}, hoy)
    cargo = control_gasto.reservar(round(maximo * 0.002 + 0.01, 3))  # ≈ USD 2 por 1.000 posts
    if not cargo:
        return [], [], {"omitida": "presupuesto de Apify agotado"}
    items, ejecucion = ejecutar(cliente, actor, entrada(actor, consultas, max(1, maximo // len(consultas)), hoy), token,
                                cargo, max_items=maximo, limite_segundos=180)
    if ejecucion.get("error"):
        return [], [], {k: ejecucion[k] for k in ("error", "clave_invalida") if k in ejecucion}
    formales, posts, motivos, vistos = [], [], {}, set()
    for item in items if isinstance(items, list) else []:
        if reloj() - inicio >= 240:
            break
        if not isinstance(item, dict) or item.get("type") in ("comment", "reaction"):
            continue
        cruda, motivo = a_vacante(item, familias_validas, hoy, max_dias)
        if not cruda:
            motivos[motivo] = motivos.get(motivo, 0) + 1
            continue
        formal = resolver_oferta(cliente, item, familias_validas)
        if formal:
            formales.append(formal)
            continue
        post = vacante.crear_post(cruda["titulo"], cruda["empresa"], cruda["enlace"], cruda["ubicacion"],
                                  cruda["descripcion"], cruda["fecha"], cruda["remoto"], cruda["contacto"], hoy)
        from buscador import contrato
        motivo = "sin cargo del mapa" if not post else contrato.entregable_post(post)
        if motivo or post["id"] in vistos:
            motivos[motivo or "repetido"] = motivos.get(motivo or "repetido", 0) + 1
            continue
        vistos.add(post["id"])
        posts.append(post)
    return formales, posts, {"consultas": len(consultas), "publicaciones": len(items) if isinstance(items, list) else 0,
                             "fichas_formales": len(formales), "posts": len(posts), "descartadas": motivos,
                             "gasto_reservado_usd": cargo}
