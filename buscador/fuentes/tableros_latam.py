"""RemotosLatam y WeRemoto (contrato v44, aprobado por Oscar): tableros de empleo remoto para LATAM. Son agregadores, así
que NO se toman sus avisos (regla del proyecto: nunca entregar un agregador). Como Open Seat, se usan solo para
descubrir empresas que contratan en remoto para LATAM: de sus páginas de categoría se sacan los portales de postulación
(Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee) y esos portales se leen con `ats.py`, que trae la
ficha completa, la fecha real y los cierres, y deja el enlace donde se postula de verdad.

Solo páginas que su robots.txt permite (las de categoría, sin parámetros); nunca su API ni páginas con «?». Sin sesión.
Si un tablero no responde, la búsqueda sigue con los portales de siempre.
"""
import re

from buscador.fuentes import ats

PAGINAS = {
    "RemotosLatam": [f"https://remotoslatam.com/empleos/{c}" for c in
                     ("diseno", "programacion", "desarrollador-web", "project-manager", "datos-e-ia", "marketing",
                      "en-espanol", "para-latinos")],
    "WeRemoto": [f"https://www.weremoto.com/categoria-de-trabajo/{c}" for c in
                 ("diseno", "programacion", "it", "project-manager", "analista-de-datos", "marketing")],
}
_PATRONES = {
    "greenhouse": re.compile(r"https?://(?:job-boards|boards)\.greenhouse\.io/([A-Za-z0-9_-]+)"),
    "lever": re.compile(r"https?://jobs\.lever\.co/([A-Za-z0-9._-]+)"),
    "ashby": re.compile(r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9._-]+)"),
    "workable": re.compile(r"https?://apply\.workable\.com/([A-Za-z0-9._-]+)"),
    "smartrecruiters": re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9._-]+)"),
    "recruitee": re.compile(r"https?://([a-z0-9-]+)\.recruitee\.com"),
}
# Partes de dirección que no son empresas (rutas del propio sistema).
_NO_EMPRESA = {"j", "a", "embed", "api", "v1", "jobs", "careers", "www", "app", "static"}
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,79}$")


def portales(pagina):
    """{(sistema, slug)} de los enlaces a portales de postulación de una página."""
    salida = set()
    for sistema, patron in _PATRONES.items():
        for slug in patron.findall(pagina or ""):
            if slug.lower() not in _NO_EMPRESA and _SLUG.match(slug):
                salida.add((sistema, slug))
    return salida


def tableros(cliente, hoy):
    """(filas para `ats.buscar` con su origen, estadísticas)."""
    filas, stats = {}, {}
    for nombre, paginas in PAGINAS.items():
        leidas = fallidas = 0
        for url in paginas:
            r = cliente.get(url)
            if r is None or r.status_code != 200:
                fallidas += 1
                continue
            leidas += 1
            for sistema, slug in portales(r.text):
                if sistema in ats.SISTEMAS:
                    filas.setdefault((sistema, slug.lower()), {"empresa": slug, "sistema": sistema, "slug": slug,
                                                                "origen": nombre, "agregada": hoy})
        stats[nombre] = {"paginas": leidas, "fallidas": fallidas,
                         "portales": sum(1 for f in filas.values() if f["origen"] == nombre)}
    return list(filas.values()), stats
