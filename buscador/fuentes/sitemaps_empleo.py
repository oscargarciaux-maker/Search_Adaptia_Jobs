"""Portales en español que publican la lista de sus vacantes (sitemap) y cada ficha con su `JobPosting` (schema.org).
Contrato v44 (18 nov, aprobado por Oscar): Hireline (México y Colombia, tecnología) y Magneto (Colombia).

Se postula en el mismo sitio, sin sesión ni cookies. Solo se leen rutas que su robots.txt permite: el sitemap de
ofertas y la ficha `/empleos/...` (nunca la búsqueda con parámetros ni su API). Del sitemap se toman solo las vacantes
cuyo título (en la dirección) nombra un cargo buscado y que se actualizaron en los últimos 30 días; de cada ficha, lo
que dice el `JobPosting`: título, empresa, ciudad y país, fecha real (`datePosted`), cierre (`validThrough`), si es
remota (`TELECOMMUTE`), desde qué país se postula y salario. Nada se inventa: lo que la ficha no dice queda vacío.
"""
import re
import time
from datetime import date, datetime, timedelta, timezone

from buscador import cobertura, normalizar
from buscador.fuentes import jobposting

# Cada sitio: sus sitemaps de ofertas por país y la parte de la dirección que tienen las fichas.
SITIOS = {
    "Hireline": {"sitemaps": {"MX": "https://hireline.io/mx/sitemap_ofertas.xml",
                              "CO": "https://hireline.io/co/sitemap_ofertas.xml"},
                 "ficha": "/empleos/", "presupuesto": "hireline_fichas"},
    "Magneto": {"sitemaps": {"CO": "https://sitemaps.magneto365.com/sitemap-jobs.xml"},
                "ficha": "/co/empleos/", "presupuesto": "magneto_fichas"},
}
_URL = re.compile(r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+)\s*</lastmod>)?", re.S)


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


def _clave(x):
    """Título comparable con la dirección (sin tildes, sin nivel y sin «/», que la dirección no lleva)."""
    return " ".join(normalizar.titulo_base(x).replace("/", " ").split())


def _patron(f):
    """Una expresión por cargo con todos sus títulos (de 3 letras o más): comparar 29 mil direcciones contra cientos de
    títulos uno por uno tardaba minutos (Thermos, v44)."""
    terminos = sorted({c for c in map(_clave, [*cobertura.consultas(f), *(f.get("consultas_es") or [])])
                       if len(c) >= 3}, key=len, reverse=True)
    if not terminos:
        return None
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(x) for x in terminos) + r")(?![a-z0-9])")


def candidatos(enlaces, mapa, hoy, patron, dias=30, reloj=time.monotonic, limite_segundos=None):
    """[(enlace, familia)] de las vacantes del sitemap cuyo título nombra algún cargo buscado y se actualizaron en los
    últimos `dias`, de la más reciente a la más antigua."""
    desde = (date.fromisoformat(hoy) - timedelta(days=dias)).isoformat()
    patrones = [(f["id"], x) for f in mapa if (x := _patron(f))]
    inicio = reloj()
    salida, vistos = [], set()
    for enlace, mod in sorted(enlaces, key=lambda e: e[1], reverse=True):
        if limite_segundos is not None and reloj() - inicio >= limite_segundos:
            break
        if patron not in enlace or enlace in vistos or (mod and mod < desde):
            continue
        texto = _clave(titulo_de_enlace(enlace))
        familia = next((fid for fid, x in patrones if x.search(texto)), None)
        if familia:
            vistos.add(enlace)
            salida.append((enlace, familia))
    return salida


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
                       candidatos(entradas(r.text), mapa, hoy, sitio["ficha"], reloj=reloj,
                                  limite_segundos=None if limite_segundos is None else limite_segundos / 3)]
    candidatas.sort(key=lambda c: c[1] not in set(prioritarias))  # estable: dentro, de la más reciente a la más antigua
    crudas, leidas = jobposting.leer_fichas(cliente, [(e, titulo_de_enlace(e), c) for e, _, c in candidatas], hoy, nombre,
                                            max_fichas, reloj, inicio, limite_segundos)
    return crudas, {"sitemaps_fallidos": fallidas, "candidatas": len(candidatas), **leidas, "avisos": len(crudas),
                    "segundos": round(reloj() - inicio)}
