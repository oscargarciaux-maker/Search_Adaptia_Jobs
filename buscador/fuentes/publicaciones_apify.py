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

NOMBRE = "LinkedIn (publicación)"
API = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
CONTRATA = re.compile(r"\b(hiring|we.?re hiring|we are hiring|now hiring|join our team|join us|looking for an?|"
                      r"is looking for|open (?:role|position)|job opening|apply now|vacante|vacantes|estamos contratando|"
                      r"contratando|buscamos|estamos buscando|estamos en busqueda|se busca|oportunidad laboral|"
                      r"oferta laboral|unete|sumate|postulate|postula|envia tu cv|envianos tu cv|send your cv|"
                      r"send me your cv|dm me)\b")
RUIDO = re.compile(r"\b(open ?to ?work|opentowork|busco empleo|busco trabajo|estoy buscando (?:empleo|trabajo|"
                   r"nuevas oportunidades|una nueva oportunidad)|i.?m looking for (?:a new|my next|new opportunities)|"
                   r"looking for my next|webinar|bootcamp|curso|course|masterclass|taller|workshop|mentoria|"
                   r"mentorship|certificacion gratuita|free certification)\b")
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


def a_vacante(item, familias_validas):
    """Vacante cruda (formato de las fuentes) o (None, motivo)."""
    texto = str(_campo(item, "content", "text", "postText"))
    enlace = str(_campo(item, "linkedinUrl", "postUrl", "url", "socialContent.shareUrl"))
    h = enlaces.host(enlace)
    if not texto or not enlaces.sirve(enlace) or not (h == "linkedin.com" or h.endswith(".linkedin.com")):
        return None, "sin texto o enlace"
    t = normalizar.texto(texto)
    if RUIDO.search(t) or not CONTRATA.search(t):
        return None, "no anuncia una contratación"
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
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    fecha = str(_campo(item, "postedAt.date", "postedAt", "publishedAt", "date"))[:10]
    return {
        "titulo": titulo, "empresa": empresa, "ubicacion": ", ".join(nombres[c] for c in nombrados[:3]),
        "descripcion": texto[:15000], "fecha": fecha if re.match(r"\d{4}-\d{2}-\d{2}", fecha) else "",
        "enlace": enlace.split("?")[0], "enlace_directo": "", "remoto": True if remoto else None, "fuente": NOMBRE,
    }, ""


def buscar(cliente, actor, consultas, familias_validas, hoy, maximo=60, token=None, reloj=time.monotonic):
    """Corre el actor una vez con todas las consultas. Devuelve (vacantes crudas, estadísticas)."""
    token = token or os.environ.get("APIFY_TOKEN", "")
    if not token or not actor:
        return [], {"omitida": "sin APIFY_TOKEN o sin actor_publicaciones en datos/config.yaml"}
    if not consultas:
        return [], {"omitida": "sin consultas_publicaciones en datos/entrega.yaml"}
    por_consulta = max(1, maximo // len(consultas))
    items = cliente.post_json(API.format(actor=actor.replace("/", "~")) + f"?token={token}",
                              entrada(actor, consultas, por_consulta, hoy), timeout=900)
    if items is None:
        return [], {"error": "el actor no respondió o rechazó la entrada", "consultas": len(consultas)}
    if not isinstance(items, list):
        return [], {"error": "el actor devolvió una estructura inesperada; no se aceptaron registros"}
    crudas, motivos, revision = [], {}, []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("type") in ("comment", "reaction"):
            continue
        v, motivo = a_vacante(item, familias_validas)
        if v:
            # Una publicación de contratación es un indicio, no una oferta formal comprobada.
            # No llenar cuotas ni enviar a Supabase hasta verificar su oferta original.
            revision.append({"titulo": v["titulo"], "empresa": v["empresa"], "enlace": v["enlace"],
                             "motivo": "publicación pendiente de verificar contra una oferta formal"})
        else:
            motivos[motivo] = motivos.get(motivo, 0) + 1
    return crudas, {"consultas": len(consultas), "publicaciones": len(items) if isinstance(items, list) else 0,
                    "vacantes": 0, "pendientes_revision": len(revision), "muestras_revision": revision[:10],
                    "descartadas": motivos}
