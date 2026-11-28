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

from buscador import enlaces, familias, ficha, normalizar, paises
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


# Contrato v28 (16 nov, pedido de Oscar): un post que no nombra país ni modalidad no se descarta de entrada. Antes se
# buscan pistas de ubicación con reglas fijas (sin IA), de la más fuerte a la más débil. Prefijos de 1 dígito (+1, +7)
# y el dominio «.co» (lo usan startups de todo el mundo) no cuentan: son ambiguos.
PREFIJOS = {"593": "EC", "591": "BO", "595": "PY", "598": "UY", "506": "CR", "507": "PA", "502": "GT", "503": "SV",
            "504": "HN", "505": "NI", "57": "CO", "52": "MX", "54": "AR", "56": "CL", "51": "PE", "58": "VE", "34": "ES",
            "53": "CU"}
MONEDAS = {"COP": "CO", "MXN": "MX", "ARS": "AR", "CLP": "CL", "PEN": "PE", "UYU": "UY", "PYG": "PY", "BOB": "BO",
           "CRC": "CR", "GTQ": "GT", "DOP": "DO", "VES": "VE", "HNL": "HN", "NIO": "NI"}
MONEDAS_TEXTO = {"pesos colombianos": "CO", "pesos mexicanos": "MX", "pesos argentinos": "AR", "pesos chilenos": "CL",
                 "soles": "PE", "colones": "CR", "quetzales": "GT"}
DOMINIOS = {"com.co": "CO", "gov.co": "CO", "edu.co": "CO", "org.co": "CO", "mx": "MX", "com.ar": "AR", "ar": "AR",
            "cl": "CL", "pe": "PE", "ec": "EC", "es": "ES", "uy": "UY", "py": "PY", "bo": "BO", "cr": "CR", "pa": "PA",
            "gt": "GT", "do": "DO", "ve": "VE", "hn": "HN", "ni": "NI", "sv": "SV"}
_TELEFONO = re.compile(r"(?<![\w+])\+\s?(\d{1,3})(?=[\s\-().]*\d)")
_DOMINIO = re.compile(r"(?:@|https?://)[\w.-]+?\.((?:com|gov|edu|org)\.[a-z]{2}|[a-z]{2})(?![\w.])", re.I)


def pistas_ubicacion(texto, item=None, empresa="", empresas_pais=None):
    """([países ISO2], de dónde salió) para un post que no nombra país ni modalidad; ([], "") si no hay pista.
    Orden: ubicación del autor que trae el actor, prefijo telefónico, moneda, dominio de correos o enlaces y el país
    donde la misma empresa tiene sus otras vacantes confirmadas en el catálogo."""
    autor = str(_campo(item or {}, "author.location", "author.locationName", "authorLocation", "author.geo.name",
                       "author.company.location"))
    if autor:
        hallados = sorted(paises.paises_en_texto(normalizar.texto(autor)))
        if len(hallados) == 1:
            return hallados, "ubicación de quien publicó"
    for m in _TELEFONO.finditer(texto or ""):
        digitos = m.group(1)
        for largo in (3, 2):
            if digitos[:largo] in PREFIJOS:
                return [PREFIJOS[digitos[:largo]]], f"prefijo telefónico +{digitos[:largo]}"
    for codigo, pais in MONEDAS.items():
        if re.search(rf"\b{codigo}\b", texto or ""):
            return [pais], f"moneda {codigo}"
    normal = normalizar.texto(texto or "")
    for frase, pais in MONEDAS_TEXTO.items():
        if normalizar.contiene_frase(normal, frase):
            return [pais], f"moneda ({frase})"
    for m in _DOMINIO.finditer(texto or ""):
        sufijo = m.group(1).lower()
        pais = DOMINIOS.get(sufijo) or (DOMINIOS.get(sufijo.split(".")[-1]) if "." in sufijo else None)
        if pais:
            return [pais], f"dominio .{sufijo}"
    if empresa and empresas_pais:
        pais = empresas_pais.get(normalizar.empresa(empresa))
        if pais:
            return [pais], "país de las otras vacantes de la empresa"
    return [], ""


def paises_por_empresa(vacantes):
    """{empresa normalizada: país} cuando todas sus vacantes con país confirmado están en un solo país."""
    vistos = {}
    for v in vacantes or ():
        if v.get("tipo") == "post" or v.get("confianza_pais") != "alta" or not v.get("paises"):
            continue
        vistos.setdefault(normalizar.empresa(v.get("empresa") or ""), set()).update(v["paises"])
    return {e: next(iter(c)) for e, c in vistos.items() if e and len(c) == 1}


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


def a_vacante(item, familias_validas, hoy=None, max_dias=30, empresas_pais=None):
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
    deducida, sin_confirmar = "", False
    if not nombrados and not remoto:
        # Contrato v28: un país de fuera nombrado («New York», «Madrid») es una ubicación, no una duda. Si no nombra
        # ninguno, se buscan pistas antes de rendirse.
        nombrados = sorted(paises.paises_en_texto(t))[:3]
        if not nombrados:
            nombrados, deducida = pistas_ubicacion(texto, item, empresa, empresas_pais)
        sin_confirmar = not nombrados
    if not ACCION.search(t) and not re.search(r"https?://", texto):
        return None, "no pide postular ni escribir"
    fecha = str(_campo(item, "postedAt.date", "postedAt", "publishedAt", "date"))[:10]
    fecha = fecha if re.match(r"\d{4}-\d{2}-\d{2}$", fecha) else ""
    if hoy and fecha:
        from datetime import date
        edad = (date.fromisoformat(hoy) - date.fromisoformat(fecha)).days
        if not 0 <= edad <= max_dias:
            return None, "fuera del plazo"
    nombres = {**{p["codigo"]: p["nombre_en"] for p in paises.mundo()["lista"]},
               **{p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}}
    return {
        "titulo": titulo, "empresa": empresa, "ubicacion": ", ".join(nombres.get(c, c) for c in nombrados[:3]),
        "ubicacion_deducida": deducida, "ubicacion_sin_confirmar": sin_confirmar,
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
        def campo(patron, texto=respuesta.text):
            m = re.search(patron, texto)
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


def _agotado(control_gasto):
    return {"credito_agotado": True} if getattr(control_gasto, "bloqueado", False) else {}


def _sin_credito(control_gasto, ejecucion):
    """8.2: Apify dijo que el plan no tiene crédito: aviso (no avería) y nada más se reserva este mes."""
    if hasattr(control_gasto, "marcar_agotado"):
        control_gasto.marcar_agotado()
    return {"credito_agotado": True, "aviso": ejecucion.get("aviso", ""),
            "usd_reservado": ejecucion.get("tope_reservado_usd") or 0, "usd_reportado": 0}


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
        return [], {"omitida": "presupuesto de Apify agotado", **_agotado(control_gasto)}
    por_consulta = max(1, maximo // len(consultas))
    items, ejecucion = ejecutar(cliente, actor, entrada(actor, consultas, por_consulta, hoy), token,
                                cargo, max_items=maximo, limite_segundos=180)
    if ejecucion.get("credito_agotado"):
        return [], _sin_credito(control_gasto, ejecucion)
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


def consultas_post(terminos, maximo=2, lugares=()):
    """Consultas del buscador de posts para un cargo: contratación + el término exacto (máx. 5 operadores). Contrato
    v28: con `lugares` (países de los perfiles con déficit o «remoto»), una consulta más por lugar con el primer
    término, para traer posts que sí nombran dónde es."""
    terminos = list(dict.fromkeys(terminos))
    salida = [f'(hiring OR contratando OR vacante OR buscamos) "{t}"' for t in terminos[:maximo]]
    if terminos:
        salida += [f'(hiring OR contratando OR buscamos) "{terminos[0]}" {lugar}' for lugar in lugares]
    return salida


# Lectura acotada compartida con la ficha del panel (contrato v29): mismos límites que en el contrato v28.
_dominio_conocido = ficha.dominio_conocido
_leer_acotado = ficha.leer_acotado


def ubicacion_en_enlaces(texto, titulo, maximo=2, obtener=None):
    """(ubicación, remoto) del JobPosting de la primera ficha enlazada en un sistema de postulación o portal conocido,
    o None. Solo GET acotado, sin formularios (reusa la lectura de `confirmar_ubicacion`)."""
    from buscador import confirmar_ubicacion as cu
    if obtener is None:
        import requests
        sesion = requests.Session()
        obtener = lambda url: _leer_acotado(url, sesion)  # noqa: E731
    urls = [u.rstrip(".,;:!?)") for u in re.findall(r"https?://[^\s<>\"']+", texto or "")]
    for url in [u for u in urls if not enlaces.es_linkedin(u) and _dominio_conocido(u)][:maximo]:
        try:
            html = obtener(url)
        except Exception as e:  # noqa: BLE001 — una ficha caída no impide el post
            from buscador import registro
            registro.aviso("publicaciones_apify:ficha", e)
            continue
        observada = cu.observacion(html, titulo) if html else None
        if observada:
            return observada
    return None


def buscar_posts(cliente, actor, consultas, familias_validas, hoy, maximo=30, token=None, control_gasto=None,
                 max_dias=30, reloj=time.monotonic, empresas_pais=None):
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
        return [], [], {"omitida": "presupuesto de Apify agotado", **_agotado(control_gasto)}
    items, ejecucion = ejecutar(cliente, actor, entrada(actor, consultas, max(1, maximo // len(consultas)), hoy), token,
                                cargo, max_items=maximo, limite_segundos=180)
    if ejecucion.get("credito_agotado"):
        return [], [], _sin_credito(control_gasto, ejecucion)
    if ejecucion.get("error"):
        return [], [], {k: ejecucion[k] for k in ("error", "clave_invalida") if k in ejecucion}
    formales, posts, motivos, vistos = [], [], {}, set()
    for item in items if isinstance(items, list) else []:
        if reloj() - inicio >= 240:
            break
        if not isinstance(item, dict) or item.get("type") in ("comment", "reaction"):
            continue
        cruda, motivo = a_vacante(item, familias_validas, hoy, max_dias, empresas_pais)
        if not cruda:
            motivos[motivo] = motivos.get(motivo, 0) + 1
            continue
        formal = resolver_oferta(cliente, item, familias_validas)
        if formal:
            formales.append(formal)
            continue
        if cruda["ubicacion_sin_confirmar"] and reloj() - inicio < 200:
            ficha = ubicacion_en_enlaces(cruda["descripcion"], cruda["titulo"])
            if ficha:  # contrato v28: la ficha enlazada (portal de la empresa o ATS) dice dónde es
                cruda.update(ubicacion=ficha[0], remoto=ficha[1], ubicacion_deducida="ficha enlazada en el post",
                             ubicacion_sin_confirmar=False)
        post = vacante.crear_post(cruda["titulo"], cruda["empresa"], cruda["enlace"], cruda["ubicacion"],
                                  cruda["descripcion"], cruda["fecha"], cruda["remoto"], cruda["contacto"], hoy)
        if post:
            post.update(ubicacion_deducida=cruda["ubicacion_deducida"],
                        ubicacion_sin_confirmar=cruda["ubicacion_sin_confirmar"])
            if cruda["ubicacion_sin_confirmar"] and cruda["remoto"] is None:
                post["modalidad"] = ""  # el post no dice la modalidad: no se supone presencial
        from buscador import contrato
        motivo = "sin cargo del mapa" if not post else contrato.entregable_post(post)
        if motivo or post["id"] in vistos:
            motivos[motivo or "repetido"] = motivos.get(motivo or "repetido", 0) + 1
            continue
        vistos.add(post["id"])
        posts.append(post)
    deducidas = {}
    for p in posts:
        if p.get("ubicacion_deducida"):
            deducidas[p["ubicacion_deducida"]] = deducidas.get(p["ubicacion_deducida"], 0) + 1
    return formales, posts, {"consultas": len(consultas), "publicaciones": len(items) if isinstance(items, list) else 0,
                             "fichas_formales": len(formales), "posts": len(posts), "descartadas": motivos,
                             "ubicacion_deducida": deducidas,
                             "ubicacion_sin_confirmar": sum(1 for p in posts if p.get("ubicacion_sin_confirmar")),
                             "gasto_reservado_usd": cargo, "usd_reservado": cargo,
                             "usd_reportado": ejecucion.get("costo_uso_reportado_usd") or 0}
