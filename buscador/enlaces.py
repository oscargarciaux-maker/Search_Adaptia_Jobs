"""Tipo de cada enlace (original, portal, agregador o desconocido) y búsqueda del original detrás de un agregador."""
import re
from functools import lru_cache
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

RUTA = Path(__file__).resolve().parent.parent / "datos" / "dominios.yaml"
TIPOS = ["original", "portal", "desconocido", "agregador"]   # del mejor al peor
_PAGINA_DE_EMPLEO = re.compile(r"^(careers?|jobs?|empleos?|trabaja|talent|vacantes|work|join|apply|recruiting)\.|"
                               r"/(careers?|jobs?|empleos?|vacantes|trabaja-con-nosotros|trabaja-con-nosotras|"
                               r"trabaje-con-nosotros|work-with-us|join-us|open-positions|carreras|oportunidades)(/|$|\?)", re.I)
_HREF = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
_APLICAR = re.compile(r"apply|aplicar|postular|postúlate|postulate|candidatar", re.I)


@lru_cache(maxsize=1)
def dominios():
    d = yaml.safe_load(RUTA.read_text(encoding="utf-8"))
    return {k: [x.lower() for x in d[k]] for k in ("originales", "portales", "agregadores")}


def host(url):
    h = (urlparse(str(url or "")).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _en(h, lista):
    """El dominio está en la lista. Una entrada sin punto ("computrabajo") vale para cualquier país:
    computrabajo.com.co, co.computrabajo.com, computrabajo.com.mx…"""
    etiquetas = h.split(".")
    return any((d in etiquetas) if "." not in d else (h == d or h.endswith("." + d)) for d in lista)


def tipo(url):
    """'original', 'portal', 'agregador' o 'desconocido'. Un enlace vacío o inválido es 'agregador' (no sirve)."""
    h = host(url)
    if not h:
        return "agregador"
    d = dominios()
    # Primero agregadores: algunos usan subdominios de portales conocidos
    if _en(h, d["agregadores"]):
        return "agregador"
    if _en(h, d["originales"]):
        return "original"
    if _en(h, d["portales"]):
        return "portal"
    if _PAGINA_DE_EMPLEO.search(h + urlparse(url).path):
        return "original"
    return "desconocido"


def sirve(url):
    """true si se puede entregar: no es un agregador."""
    return tipo(url) != "agregador"


def mejor(enlaces):
    """El mejor enlace de una lista: original antes que portal, portal antes que desconocido; nunca un agregador."""
    candidatos = [u for u in enlaces if u and sirve(u)]
    return min(candidatos, key=lambda u: TIPOS.index(tipo(u))) if candidatos else ""


def original_en_html(html, url_pagina):
    """Enlace original o de portal que aparece en la página de un agregador (el botón de postular), o ''.
    Prefiere los enlaces cuyo texto o dirección dice aplicar/postular y los sistemas de postulación."""
    origen = host(url_pagina)
    candidatos = []
    for m in _HREF.finditer(html or ""):
        href = unescape(m.group(1)).strip()
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        absoluto = urljoin(url_pagina, href)
        h = host(absoluto)
        if not h or h == origen or not absoluto.startswith("http"):
            continue
        t = tipo(absoluto)
        if t in ("original", "portal"):
            contexto = (html[max(0, m.start() - 200):m.end() + 200])
            puntaje = (0 if t == "original" else 1) - (2 if _APLICAR.search(contexto) else 0)
            if "linkedin.com" in h and "/jobs/" not in absoluto:
                continue  # el perfil de la empresa en LinkedIn no es la vacante
            candidatos.append((puntaje, len(candidatos), absoluto))
    return min(candidatos)[2] if candidatos else ""


def es_linkedin(url):
    return host(url).endswith("linkedin.com") and "/jobs/view/" in str(url)
