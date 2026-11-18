"""Portales en español que publican la lista de sus vacantes (sitemap) y cada ficha con su `JobPosting` (schema.org).
Contrato v44 (18 nov, aprobado por Oscar): Hireline (México y Colombia, tecnología) y Magneto (Colombia).

Se postula en el mismo sitio, sin sesión ni cookies. Solo se leen rutas que su robots.txt permite: el sitemap de
ofertas y la ficha `/empleos/...` (nunca la búsqueda con parámetros ni su API). Del sitemap se toman solo las vacantes
cuyo título (en la dirección) nombra un cargo buscado y que se actualizaron en los últimos 30 días; de cada ficha, lo
que dice el `JobPosting`: título, empresa, ciudad y país, fecha real (`datePosted`), cierre (`validThrough`), si es
remota (`TELECOMMUTE`), desde qué país se postula y salario. Nada se inventa: lo que la ficha no dice queda vacío.
"""
import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone

from buscador import cobertura, normalizar
from buscador.fuentes.elempleo import _fecha, _salario, _texto

# Cada sitio: sus sitemaps de ofertas por país y la parte de la dirección que tienen las fichas.
SITIOS = {
    "Hireline": {"sitemaps": {"MX": "https://hireline.io/mx/sitemap_ofertas.xml",
                              "CO": "https://hireline.io/co/sitemap_ofertas.xml"},
                 "ficha": "/empleos/"},
    "Magneto": {"sitemaps": {"CO": "https://sitemaps.magneto365.com/sitemap-jobs.xml"},
                "ficha": "/co/empleos/"},
}
PAISES_NOMBRE = {"MX": "México", "CO": "Colombia"}
_URL = re.compile(r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+)\s*</lastmod>)?", re.S)
_LDJSON = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def entradas(xml):
    """[(enlace, fecha de actualización o "")] de un sitemap."""
    return [(loc.strip(), (mod or "")[:10]) for loc, mod in _URL.findall(xml or "")]


def titulo_de_enlace(enlace):
    """«…/empleos/disenador-ux-ui-remoto/114112» o «…/empleos/disenador-ux-1121716» → «disenador ux ui remoto»."""
    partes = [p for p in enlace.split("?")[0].rstrip("/").split("/") if p]
    if partes and partes[-1].isdigit():
        partes = partes[:-1]
    ultimo = re.sub(r"-\d{4,}$", "", partes[-1] if partes else "")
    return ultimo.replace("-", " ")


def _terminos(f):
    salida = []
    for t in [*cobertura.consultas(f), *(f.get("consultas_es") or [])]:
        clave = " ".join(normalizar.titulo_base(t).replace("/", " ").split())  # la dirección no lleva «/»
        if clave and len(clave) >= 3 and clave not in salida:
            salida.append(clave)
    return salida


def candidatos(enlaces, mapa, hoy, patron, dias=30):
    """[(enlace, familia)] de las vacantes del sitemap cuyo título nombra algún cargo buscado, recientes."""
    desde = (date.fromisoformat(hoy) - timedelta(days=dias)).isoformat()
    terminos = [(f["id"], _terminos(f)) for f in mapa]
    salida, vistos = [], set()
    for enlace, mod in enlaces:
        if patron not in enlace or enlace in vistos or (mod and mod < desde):
            continue
        texto = " ".join(normalizar.titulo_base(titulo_de_enlace(enlace)).replace("/", " ").split())
        for familia, lista in terminos:
            if any(normalizar.contiene_frase(texto, t) for t in lista):
                vistos.add(enlace)
                salida.append((enlace, familia))
                break
    return salida


def _postings(pagina):
    for crudo in _LDJSON.findall(pagina or ""):
        try:
            datos = json.loads(crudo.strip())
        except ValueError:
            continue
        for b in datos if isinstance(datos, list) else (datos.get("@graph") or [datos]):
            if isinstance(b, dict) and b.get("@type") == "JobPosting":
                yield b


def _uno(valor):
    return (valor[0] if valor else "") if isinstance(valor, list) else (valor or "")


def ficha(pagina, hoy, pais_sitio):
    """Datos del `JobPosting`, o None si la ficha no lo trae. `cerrada` si `validThrough` ya pasó."""
    posting = next(_postings(pagina), None)
    if not posting:
        return None
    lugar = posting.get("jobLocation") or {}
    lugar = lugar[0] if isinstance(lugar, list) and lugar else lugar
    direccion = (lugar or {}).get("address") or {}
    ciudad = str(_uno(direccion.get("addressLocality"))).strip()
    crudo = str(_uno(direccion.get("addressCountry")) or "").strip()
    if len(crudo) == 2 and crudo.isalpha():  # código ISO («CO»)
        pais = PAISES_NOMBRE.get(crudo.upper(), crudo.upper())
    elif crudo:  # nombre («MÉXICO»): tal cual, con mayúscula inicial
        pais = crudo.title()
    else:
        pais = PAISES_NOMBRE.get(pais_sitio, pais_sitio)
    titulo = html.unescape(str(posting.get("title") or "")).strip()
    remota = str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE" or bool(
        re.search(r"\bremot[oa]\b|\bhome office\b|\bteletrabajo\b", normalizar.texto(titulo)))
    hibrida = bool(re.search(r"\bhibrid[oa]\b", normalizar.texto(titulo)))
    requisito = posting.get("applicantLocationRequirements") or []
    requisito = requisito if isinstance(requisito, list) else [requisito]
    paises_postula = [str((r or {}).get("name") or "").strip() for r in requisito if isinstance(r, dict)]
    if remota:
        ubicacion = f"{', '.join(x for x in paises_postula if x) or pais} (Remoto)"
    else:
        ubicacion = ", ".join(x for x in (ciudad, pais) if x) + (" (Híbrido)" if hibrida else "")
    fecha, hasta = _fecha(posting.get("datePosted")), _fecha(posting.get("validThrough"))
    descripcion = _texto(posting.get("description"))
    salario = _salario(posting.get("baseSalary"))
    return {"titulo": titulo,
            "empresa": str(((posting.get("hiringOrganization") or {}).get("name")) or "").strip(),
            "ubicacion": ubicacion, "remoto": True if remota else None,
            "descripcion": "\n".join(x for x in (descripcion, salario) if x)[:30000],
            "fecha": fecha if fecha and fecha <= hoy else "", "cerrada": bool(hasta) and hasta < hoy}


def buscar(cliente, nombre, mapa, hoy=None, max_fichas=60, reloj=time.monotonic, limite_segundos=None, prioritarias=(),
           paises=None):
    """Lee los sitemaps del sitio `nombre` (de los países pedidos, o todos) y las fichas de las vacantes que nombran un
    cargo buscado. Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    sitio = SITIOS[nombre]
    inicio = reloj()
    candidatas, fallidas = [], 0
    for codigo, url in sitio["sitemaps"].items():
        if paises is not None and codigo not in paises:
            continue
        r = cliente.get(url)
        if r is None or r.status_code != 200:
            fallidas += 1
            continue
        candidatas += [(enlace, familia, codigo) for enlace, familia in
                       candidatos(entradas(r.text), mapa, hoy, sitio["ficha"])]
    candidatas.sort(key=lambda c: c[1] not in set(prioritarias))
    crudas, con_ficha, cerradas, seguidas = [], 0, 0, 0
    for enlace, _, codigo in candidatas[:max_fichas]:
        if seguidas >= 4 or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        r = cliente.get(enlace)
        if r is None or r.status_code != 200:
            seguidas += 1 if r is not None and r.status_code in (403, 429) else 0
            continue
        seguidas = 0
        datos = ficha(r.text, hoy, codigo)
        if not datos:
            continue
        con_ficha += 1
        if datos.pop("cerrada"):
            cerradas += 1
            continue
        crudas.append(dict(datos, titulo=datos["titulo"] or titulo_de_enlace(enlace), enlace=enlace,
                           enlace_directo="", fuente=nombre))
    return crudas, {"sitemaps_fallidos": fallidas, "candidatas": len(candidatas), "con_descripcion": con_ficha,
                    "cerradas": cerradas, "avisos": len(crudas), "segundos": round(reloj() - inicio)}
