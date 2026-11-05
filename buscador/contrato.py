"""Una vacante de la bodega en el formato del «Contrato de datos de ofertas — Adaptia Jobs (v1)»
(docs/CONTRATO_DATOS_v1.md). Sin IA: cada campo sale del texto del aviso con reglas; lo que no se puede saber queda
vacío (el contrato prohíbe inventar valores). `industries`, `keywords_role`, `keywords_soft` y `summary` quedan vacíos:
la plataforma los completa con IA.
"""
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from buscador import calidad, enlaces, normalizar, paises

VERSION = "v1"
COLUMNAS = [
    "external_id", "job_title", "company_name", "offer_url", "source_portal", "status",
    "published_date", "scraped_at",
    "location", "work_mode", "office_city", "office_country", "hire_scope", "hire_countries", "hire_regions",
    "posting_language", "language_requirements",
    "employment_type", "seniority", "years_experience_min", "years_experience_max",
    "industries", "keywords_role", "keywords_technical", "keywords_soft",
    "salary_text", "salary_min", "salary_max", "salary_currency", "salary_period",
    "description_full", "company_about", "summary", "apply_email", "company_website",
]
# Columnas adicionales (el contrato las guarda aparte como extras)
EXTRAS = ["search_tag", "delivery_date", "source_type", "match_grade"]
LISTAS = {"hire_countries", "hire_regions", "language_requirements", "industries", "keywords_role",
          "keywords_technical", "keywords_soft"}
NUMEROS = {"years_experience_min", "years_experience_max", "salary_min", "salary_max"}
EMPRESA_DESCONOCIDA = "Empresa confidencial"   # lo pone vacante.crear cuando la fuente no trae empresa

_RASTREO = re.compile(r"^(utm_\w+|gclid|fbclid|trk|trkinfo|trackingid|refid|ref|lever-source|gh_src|source|src)$", re.I)
_PORTALES = [("linkedin.com", "LinkedIn"), ("indeed.", "Indeed"), ("getonbrd.com", "Get on Board"),
             ("greenhouse.io", "Greenhouse"), ("lever.co", "Lever"), ("ashbyhq.com", "Ashby"),
             ("workable.com", "Workable"), ("smartrecruiters.com", "SmartRecruiters"), ("recruitee.com", "Recruitee"),
             ("computrabajo.", "Computrabajo"), ("bumeran.", "Bumeran"), ("elempleo.com", "elempleo"),
             ("workingnomads.com", "Working Nomads"), ("remotive.com", "Remotive")]


def _es_dominio(host, dominio):
    return dominio[:-1] in host.split(".") if dominio.endswith(".") else host == dominio or host.endswith("." + dominio)


# ── Identidad ──────────────────────────────────────────────────────────────────────────────────────────────────────
def url_limpia(url):
    """Sin parámetros de seguimiento; en LinkedIn, la forma canónica con solo el número del aviso."""
    url = str(url or "").strip()
    m = re.search(r"linkedin\.com/jobs/view/(?:[^/?#]*?-)?(\d{6,})", url)
    if m and enlaces.es_linkedin(url):
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    p = urlparse(url)
    if not p.scheme:
        return url
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _RASTREO.match(k)])
    return urlunparse((p.scheme, p.netloc, p.path, p.params, query, ""))


def external_id(url):
    """Único y estable por enlace: lnkd-<número> en LinkedIn, lnkdpost-<número> en publicaciones, y si no
    <portal>-<huella del enlace limpio>."""
    url = url_limpia(url)
    m = re.search(r"linkedin\.com/jobs/view/(\d+)", url)
    if m and enlaces.es_linkedin(url):
        return "lnkd-" + m.group(1)
    m = re.search(r"linkedin\.com/.*?(?:activity[:-]|urn:li:activity:|ugcPost[:-]|share[:-])(\d{15,})", url)
    if m and _es_dominio(enlaces.host(url), "linkedin.com"):
        return "lnkdpost-" + m.group(1)
    h = enlaces.host(url)
    etiqueta = next((n for d, n in _PORTALES if _es_dominio(h, d)), h.split(".")[0] if h else "web")
    return re.sub(r"[^a-z0-9]+", "", etiqueta.lower())[:20] + "-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def portal(url):
    h = enlaces.host(url)
    return next((n for d, n in _PORTALES if _es_dominio(h, d)), h)


# ── Ubicación ──────────────────────────────────────────────────────────────────────────────────────────────────────
_MODO = {"remoto": "remote", "hibrido": "hybrid", "presencial": "onsite"}


def _ciudad(ubicacion, codigo):
    """Primera parte de la ubicación si no es el nombre del país ni una región genérica."""
    primera = str(ubicacion or "").split(",")[0].split("·")[0].strip(" -")
    t = normalizar.texto(primera)
    if not t or re.search(r"\b(remote|remoto|hybrid|hibrido|latam|latin america|worldwide|anywhere|desde casa|"
                          r"n a|na|sin dato)\b", t):
        return ""
    datos = next((p for p in paises.datos()["paises"] if p["codigo"] == codigo), None)
    if datos and t in {normalizar.texto(n) for n in datos["nombres"] + [datos["nombre"]]}:
        return ""
    return re.sub(r"\s*\(.*?\)", "", primera).strip()


_PRESENCIAL = re.compile(r"\b(on ?site|presencial|in office|in-office|en oficina|presencialidad|100% presencial)\b")


def ubicacion(v):
    """(work_mode, office_city, office_country, hire_scope, hire_countries, hire_regions). La bodega da por presencial
    un aviso que no dice su modalidad; el contrato no: `work_mode` presencial solo si el aviso lo dice."""
    mod = _MODO.get(v.get("modalidad", ""), "")
    explicito = mod != "onsite" or _PRESENCIAL.search(normalizar.texto(
        f"{v.get('titulo', '')} {v.get('ubicacion', '')} {str(v.get('_descripcion', ''))[:4000]}"))
    lista = list(v.get("paises") or [])
    conf = v.get("confianza_pais", "")
    nota = v.get("nota_pais", "")
    d = paises.datos()
    if mod in ("onsite", "hybrid"):
        modo = mod if explicito else ""
        if len(lista) == 1 and conf == "alta":
            ciudad = _ciudad(v.get("ubicacion"), lista[0])
            return modo, ciudad, lista[0], "city" if ciudad else "country", lista, []
        return modo, "", "", "", [], []
    if mod != "remote" or conf == "baja" or nota == "por zona horaria":
        return mod, "", "", "", [], []
    if set(lista) == set(d["codigos"]):
        return mod, "", "", "worldwide", [], []
    if nota == "remoto para Europa":
        return mod, "", "", "region", [], ["EU"]
    if set(d["latam"]) <= set(lista):
        return mod, "", "", "region", [], ["LATAM"]
    if lista:
        return mod, "", "", "country", lista, []
    return mod, "", "", "", [], []


# ── Idioma y perfil ────────────────────────────────────────────────────────────────────────────────────────────────
_INGLES = r"(?:ingl[eé]s|english|ingles)"
_CEFR = re.compile(rf"{_INGLES}[^.\n]{{0,40}}?\b([abc][12])\b|\b([abc][12])\b[^.\n]{{0,25}}?{_INGLES}", re.I)
_A_CEFR = {"basico": "A2", "intermedio": "B1", "avanzado": "C1", "fluido": "C1", "nativo": "native"}
_DESEABLE = re.compile(r"deseable|valorable|nice to have|a plus|is a plus|preferred|preferible|plus|bonus|ideal", re.I)


def requisitos_idioma(descripcion, nivel_ingles):
    """'en:B2:1' (idioma:nivel:obligatorio) si el aviso pide inglés; '' si no lo pide."""
    texto = str(descripcion or "")
    m = _CEFR.search(texto)
    nivel = (m.group(1) or m.group(2)).upper() if m else _A_CEFR.get(nivel_ingles, "")
    if not nivel and not nivel_ingles:
        return ""
    if m:
        cerca = texto[max(0, m.start() - 60):m.end() + 60]
    else:
        i = re.search(_INGLES, texto, re.I)
        cerca = texto[max(0, i.start() - 60):i.end() + 60] if i else ""
    return f"en:{nivel}:{0 if _DESEABLE.search(cerca) else 1}"


_CONTRATO = [
    ("internship", r"\b(internship|intern|pasant[ií]a|pasante|practicante|pr[aá]cticas profesionales|est[aá]gio|trainee)\b"),
    ("freelance", r"\b(freelance|freelancer|por proyecto|per project)\b"),
    ("part_time", r"\b(part[- ]time|medio tiempo|tiempo parcial|media jornada|meio per[ií]odo)\b"),
    ("contract", r"\b(contractor|contract position|contract role|contrato por prestaci[oó]n|prestaci[oó]n de servicios|"
                 r"contrato temporal|temporary position|fixed[- ]term|b2b contract)\b"),
    ("full_time", r"\b(full[- ]time|tiempo completo|jornada completa|tempo integral)\b"),
]


def tipo_contrato(titulo, descripcion):
    for texto in (titulo, str(descripcion or "")[:8000]):
        for valor, patron in _CONTRATO:
            if re.search(patron, str(texto or ""), re.I):
                return valor
    return ""


_NIVEL_CONTRATO = {"trainee": "intern", "junior": "junior", "semi senior": "mid", "senior": "senior", "lead": "lead"}


def seniority(titulo):
    """Del título, con las equivalencias del contrato: staff y principal cuentan como senior."""
    t = normalizar.texto(titulo)
    nivel = normalizar.nivel(titulo)
    if nivel == "lead" and re.search(r"\b(staff|principal)\b", t) and not re.search(r"\b(lead|lider|head|director|"
                                                                                       r"directora|gerente|chief|vp)\b", t):
        return "senior"
    return _NIVEL_CONTRATO.get(nivel, "")


_RANGO_ANOS = re.compile(r"(\d{1,2})\s*(?:-|–|a|to|y|and|ou|or)\s*(\d{1,2})\s*(?:anos|años|years|yrs)", re.I)


def anos(descripcion, minimo):
    """(mínimo, máximo) de años de experiencia; el máximo solo si el aviso da un rango."""
    if minimo is None:
        return "", ""
    texto = normalizar.sin_tildes(str(descripcion or ""))[:12000]
    for m in _RANGO_ANOS.finditer(texto):
        a, b = int(m.group(1)), int(m.group(2))
        cerca = texto[max(0, m.start() - 80):m.end() + 80].lower()
        if a == minimo and a < b <= 40 and "experien" in cerca:
            return a, b
    return (minimo, "") if 0 <= minimo <= 40 else ("", "")


# ── Compensación ───────────────────────────────────────────────────────────────────────────────────────────────────
_MONEDAS = [(r"US\$|U\$S|USD", "USD"), (r"R\$|BRL", "BRL"), (r"(?<![\w/])S/|PEN", "PEN"), (r"€|EUR", "EUR"),
            (r"MXN", "MXN"), (r"COP", "COP"), (r"ARS", "ARS"), (r"CLP", "CLP"), (r"UYU", "UYU"), (r"Bs\.?|VES", "VES"),
            (r"DOP", "DOP"), (r"GTQ", "GTQ"), (r"CRC|₡", "CRC")]
_NUMERO = re.compile(r"(\d[\d.,\s]*\d|\d)\s*(k|mil|millones|M)?(?![A-Za-z])", re.I)
_PERIODO = [(r"\b(mes|month|mensual(es)?|monthly|mensais|/\s*m)\b", "month"),
            (r"\b(a[nñ]o|year|anual(es)?|annual|annually|yr|per annum|/\s*y)\b", "year"),
            (r"\b(hora|hour|hourly|hr|/\s*h)\b", "hour")]


def _numero(texto, sufijo):
    t = texto.replace(" ", "")
    if "." in t and "," in t:
        decimal = "." if t.rfind(".") > t.rfind(",") else ","
        t = t.replace("," if decimal == "." else ".", "").replace(decimal, ".")
    elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", t):
        t = re.sub(r"[.,]", "", t)
    elif re.fullmatch(r"\d+[.,]\d{1,2}", t):
        t = t.replace(",", ".")
    else:
        t = re.sub(r"[.,]", "", t)
    try:
        n = float(t)
    except ValueError:
        return None
    n *= {"k": 1e3, "mil": 1e3, "m": 1e6, "millones": 1e6}.get((sufijo or "").lower(), 1)
    return int(n) if n == int(n) else round(n, 2)


def salario(texto_salario, descripcion=""):
    """(salary_text, min, max, moneda, periodo). La moneda solo si el aviso la dice: un '$' solo no basta."""
    s = str(texto_salario or "").strip()
    if not s or not re.search(r"\d", s):
        return "", "", "", "", ""
    numeros = [_numero(m.group(1), m.group(2)) for m in _NUMERO.finditer(s)]
    numeros = [n for n in numeros if n]
    if not numeros:
        return "", "", "", "", ""
    i = str(descripcion or "").find(s)
    despues = str(descripcion)[i + len(s):i + len(s) + 40] if i >= 0 else ""
    moneda = next((c for p, c in _MONEDAS if re.search(p, s + " " + despues[:6])), "")
    periodo = next((c for p, c in _PERIODO if re.search(p, s, re.I)), "") or \
        next((c for p, c in _PERIODO if re.search(p, despues, re.I)), "")
    minimo = numeros[0]
    maximo = numeros[1] if len(numeros) > 1 and numeros[1] != numeros[0] else ""
    if maximo != "" and maximo < minimo:
        minimo, maximo = maximo, minimo
    return s, minimo, maximo, moneda, periodo


# ── Contenido ──────────────────────────────────────────────────────────────────────────────────────────────────────
_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
_CORREO_NO = re.compile(r"no-?reply|example|ejemplo|sentry|wixpress|\.png$|\.jpg$", re.I)


def correo(descripcion):
    return next((c for c in _CORREO.findall(str(descripcion or "")) if not _CORREO_NO.search(c)), "")


# ── Filas ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def entregable(v, idiomas=("es", "en")):
    """Motivo por el que la vacante no puede ir en la entrega, o '' si puede."""
    if not v.get("titulo") or not v.get("empresa") or v.get("empresa") == EMPRESA_DESCONOCIDA:
        return "sin empresa"
    motivo = calidad.motivo(v["titulo"], v.get("enlace", ""), v.get("fuente", ""))
    if motivo:
        return motivo
    if len(v.get("_descripcion", "")) < 200:
        return "sin descripción completa"   # sin texto no se sabe el idioma ni se detectan copias (contrato §2)
    if v.get("idioma") not in idiomas:
        return "idioma fuera del contrato"
    if not v.get("paises"):
        return "no se puede aplicar desde los países"
    if (v.get("verificacion") or {}).get("estado") == "rechazada":
        return "enlaces rechazados: " + v["verificacion"].get("motivo", "sin destino válido")
    return ""


def filas(v, rol="", grado="", fecha_entrega="", capturada="", solo_comprobados=True):
    """Filas del contrato para una vacante: una por enlace (LinkedIn y el directo de la empresa), con el mismo contenido
    (el contrato las une). `capturada`: fecha y hora ISO de la corrida."""
    mod, ciudad, pais_oficina, alcance, hire_paises, regiones = ubicacion(v)
    desc = v.get("_descripcion", "")
    anos_min, anos_max = anos(desc, v.get("anos_min"))
    s_texto, s_min, s_max, s_moneda, s_periodo = salario(v.get("salario"), desc)
    base = {
        "job_title": v["titulo"][:300], "company_name": v["empresa"][:300], "status": "active",
        "published_date": "" if v.get("fecha_estimada") else (v.get("fecha_publicacion") or "")[:10],
        "scraped_at": capturada,
        "location": v.get("ubicacion", ""), "work_mode": mod, "office_city": ciudad, "office_country": pais_oficina,
        "hire_scope": alcance, "hire_countries": "|".join(hire_paises), "hire_regions": "|".join(regiones),
        "posting_language": v.get("idioma") if v.get("idioma") in ("es", "en") else "",
        "language_requirements": requisitos_idioma(desc, v.get("ingles", "")),
        "employment_type": "internship" if seniority(v["titulo"]) == "intern" else tipo_contrato(v["titulo"], desc),
        "seniority": seniority(v["titulo"]),
        "years_experience_min": anos_min, "years_experience_max": anos_max,
        "industries": "", "keywords_role": "", "keywords_technical": "|".join((v.get("herramientas") or [])[:40]),
        "keywords_soft": "",
        "salary_text": s_texto, "salary_min": s_min, "salary_max": s_max, "salary_currency": s_moneda,
        "salary_period": s_periodo,
        "description_full": desc[:30000], "company_about": "", "summary": "", "apply_email": correo(desc),
        "company_website": "",
        "search_tag": rol, "delivery_date": fecha_entrega,
        "source_type": "publicacion" if any("publicación" in f for f in v.get("fuentes") or [v.get("fuente", "")]) else "oferta", "match_grade": grado,
    }
    salida, vistos = [], set()
    revision = v.get("verificacion")
    comprobados = {url_limpia(r["url"]) for r in (revision or {}).get("enlaces", []) if r["estado"] == "verificada"}
    for url in (v.get("enlace"), v.get("enlace_directo")):
        url = url_limpia(url)
        if not url or url in vistos or solo_comprobados and revision is not None and url not in comprobados:
            continue
        vistos.add(url)
        fila = dict(base, external_id=external_id(url), offer_url=url, source_portal=portal(url))
        salida.append({c: fila.get(c, "") for c in COLUMNAS + EXTRAS})
    return salida
