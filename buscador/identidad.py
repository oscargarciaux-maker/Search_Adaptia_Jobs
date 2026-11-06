"""Evidencia de copias entre portales. No identifica ofertas solo por título y empresa."""
from functools import lru_cache
import re

from bs4 import BeautifulSoup

from buscador import normalizar


@lru_cache(maxsize=4000)
def contenido(texto):
    return normalizar.texto(BeautifulSoup(str(texto or ""), "html.parser").get_text(" ", strip=True))


def titulo(v):
    # Conservar el nivel: Senior y Junior son oportunidades diferentes.
    return re.sub(r"\s+", " ", normalizar.texto(v.get("titulo", "")).replace("/", " ")).strip()


def grupo(v):
    empresa = normalizar.empresa(v.get("empresa", ""))
    if empresa in ("", "empresa confidencial", "confidential", "confidential company", "confidencial"):
        return None
    return empresa, titulo(v)


def lugar_compatible(a, b):
    if normalizar.texto(a.get("ubicacion")) == normalizar.texto(b.get("ubicacion")):
        return True
    if a.get("modalidad") != b.get("modalidad"):
        return False
    if a.get("modalidad") == "remoto":
        from buscador.paises import elegibles
        alcances = [elegibles(v.get("titulo", ""), v.get("ubicacion", ""), v.get("_descripcion", ""), True) for v in (a, b)]
        return (a.get("confianza_pais") == b.get("confianza_pais") == "alta" and bool(a.get("paises"))
                and set(a["paises"]) == set(b.get("paises", [])) and set(alcances[0]["paises"]) == set(alcances[1]["paises"]))
    from buscador.contrato import ubicacion
    _, ciudad_a, pais_a, *_ = ubicacion(a)
    _, ciudad_b, pais_b, *_ = ubicacion(b)
    return bool(ciudad_a and ciudad_b and pais_a and pais_a == pais_b and
                normalizar.texto(ciudad_a) == normalizar.texto(ciudad_b))


def requisiciones(texto):
    halladas = re.findall(r"\b(?:requisition(?: id)?|req(?:uisition)?[.#]?|job id|reference|referencia)\s*[:#=-]?\s*"
                         r"([a-z0-9][a-z0-9_-]{3,39})\b", texto, flags=re.I)
    return {x.lower() for x in halladas if any(c.isdigit() for c in x)}


@lru_cache(maxsize=4000)
def fragmentos(texto):
    palabras = texto.split()
    return frozenset(tuple(palabras[i:i + 5]) for i in range(len(palabras) - 4))


def misma(a, b):
    if not grupo(a) or grupo(a) != grupo(b) or not lugar_compatible(a, b):
        return False
    x, y = contenido(a.get("_descripcion", "")), contenido(b.get("_descripcion", ""))
    if min(len(x), len(y)) < 200:
        return False
    ra, rb = requisiciones(x), requisiciones(y)
    if ra and rb and ra.isdisjoint(rb):
        return False
    if x == y:
        return True
    # Un texto recortado o una plantilla corta/repetida no demuestra una misma requisición.
    if min(len(x), len(y)) / max(len(x), len(y)) < 0.85 or min(len(set(x.split())), len(set(y.split()))) < 50:
        return False
    sx, sy = fragmentos(x), fragmentos(y)
    return bool(sx and sy) and len(sx & sy) / len(sx | sy) >= 0.97
