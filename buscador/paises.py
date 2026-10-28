"""Desde qué países de LATAM se puede aplicar a una vacante (sin IA).

Mira primero la ubicación y el título del aviso; la descripción solo cuenta para la modalidad remota y para frases que
restringen dónde debe vivir la persona ("must be based in", "only candidates from"). Devuelve:
  {"paises": [códigos], "modalidad": "remoto|hibrido|presencial|sin dato", "confianza": "alta|media|baja",
   "nota": texto corto para la página}
Si nadie de LATAM puede aplicar, "paises" queda vacío.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from buscador import normalizar

RUTA = Path(__file__).resolve().parent.parent / "datos" / "paises.yaml"

_REMOTO = re.compile(r"\b(remote|remoto|remota|remotely|teletrabajo|home ?office|work from home|wfh|trabajo a distancia|"
                     r"100% remoto|distributed|fully distributed|anywhere)\b")
_REMOTO_DESC = re.compile(r"\b(fully remote|100% remote|100% remoto|trabajo remoto|remote[- ]first|remote position|"
                          r"remote role|remote job|this is a remote|posicion remota|modalidad remota|totalmente remoto|"
                          r"trabajo 100% remoto|home office)\b")
_HIBRIDO = re.compile(r"\b(hybrid|hibrido|hibrida|semipresencial|semi presencial)\b")
_PRESENCIAL = re.compile(r"\b(on ?site|onsite|presencial|in office|in-office)\b")
# Restricciones de residencia en la descripción. Se comparan contra el texto normalizado (sin tildes, minúsculas).
_RESTRINGE = re.compile(
    r"\b(must|should|need to|required to|have to)\s+(be\s+)?(reside|live|located|based|living|residing)\s+(in|within)\s+"
    r"(the\s+)?(?P<lugar>[a-z .]{2,40})"
    r"|\b(only|solo|solamente|unicamente|exclusively)\s+(open\s+to\s+)?(candidates|applicants|candidatos|personas|residents)?\s*"
    r"(from|in|de|en|residing in|located in|based in)\s+(the\s+)?(?P<lugar2>[a-z .]{2,40})"
    r"|\b(?P<lugar3>us|usa|u\.s|united states|uk|canada|eu|europe|india)[- ](only|based|residents?)\b")
_ZONA = re.compile(r"\b(?:utc|gmt)\s*([-+−–])\s*(\d{1,2})(?:[:.]\d{2})?(?:\s*(?:to|a|al|-|–|y|and)\s*(?:utc|gmt)?\s*([-+−–])\s*(\d{1,2}))?")
_ZONAS_US = {"est": -5, "edt": -5, "eastern time": -5, "cst": -6, "central time": -6, "mst": -7, "pst": -8, "pacific time": -8}


@lru_cache(maxsize=1)
def datos():
    crudo = yaml.safe_load(RUTA.read_text(encoding="utf-8"))
    paises = crudo["paises"]
    claves = []  # (frase normalizada, código)
    for p in paises:
        for frase in p["nombres"] + p["gentilicios"] + p["ciudades"]:
            claves.append((normalizar.texto(frase), p["codigo"]))
    claves.sort(key=lambda x: -len(x[0]))  # las frases largas primero ("santiago de chile" antes que "santiago")
    return {
        "paises": paises,
        "codigos": [p["codigo"] for p in paises],
        "utc": {p["codigo"]: p["utc"] for p in paises},
        "claves": claves,
        "toda_latam": sorted({normalizar.texto(x) for x in crudo["toda_latam"]}, key=len, reverse=True),
        "fuera": sorted({normalizar.texto(x) for x in crudo["fuera_de_latam"]}, key=len, reverse=True),
    }


def _paises_nombrados(t):
    """Códigos de los países de LATAM nombrados en el texto normalizado (por país, gentilicio o ciudad)."""
    hallados, usado = [], t
    for frase, codigo in datos()["claves"]:
        if normalizar.contiene_frase(usado, frase):
            if codigo not in hallados:
                hallados.append(codigo)
            usado = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", " ", usado)
    return hallados


def _nombra(t, frases):
    return any(normalizar.contiene_frase(t, f) for f in frases)


def _por_zona_horaria(t):
    """Países de LATAM dentro de la franja horaria que pide el aviso, o None si no pide ninguna.
    Recibe el texto en minúsculas y sin tildes pero con sus signos ("utc-3"): la normalización general quita el guion."""
    rangos = []
    for m in _ZONA.finditer(t):
        a = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        b = int(m.group(4)) * (1 if m.group(3) == "+" else -1) if m.group(4) else None
        rangos.append((min(a, b), max(a, b)) if b is not None else (a - 2, a + 2))
    for nombre, valor in _ZONAS_US.items():
        if re.search(r"(?<![a-z])" + nombre + r"(?![a-z])", t):
            rangos.append((valor - 2, valor + 2))
    if not rangos:
        return None
    utc = datos()["utc"]
    return [c for c in datos()["codigos"] if any(lo <= utc[c] <= hi for lo, hi in rangos)]


def _restriccion(desc):
    """Lugar al que la descripción restringe la residencia, o '' si no restringe."""
    m = _RESTRINGE.search(desc)
    if not m:
        return ""
    return (m.group("lugar") or m.group("lugar2") or m.group("lugar3") or "").strip()


def modalidad(titulo, ubicacion, descripcion="", remoto=None):
    t = normalizar.texto(f"{titulo} {ubicacion}")
    d = normalizar.texto(descripcion)[:4000]
    if _HIBRIDO.search(t):
        return "hibrido"
    if remoto is True or _REMOTO.search(t):
        return "remoto"
    if _PRESENCIAL.search(t):
        return "presencial"
    if _HIBRIDO.search(d):
        return "hibrido"
    if _REMOTO_DESC.search(d):
        return "remoto"
    return "presencial" if t.strip() else "sin dato"


def elegibles(titulo, ubicacion, descripcion="", remoto=None):
    """Países de LATAM desde los que se puede aplicar, con modalidad, confianza y una nota corta."""
    todos = datos()["codigos"]
    lugar = normalizar.texto(f"{ubicacion} {titulo}")
    desc = normalizar.texto(descripcion)[:6000]
    mod = modalidad(titulo, ubicacion, descripcion, remoto)
    nombrados = _paises_nombrados(lugar)
    latam = _nombra(lugar, datos()["toda_latam"])
    fuera = _nombra(lugar, datos()["fuera"])

    def r(paises, confianza, nota):
        return {"paises": paises, "modalidad": mod, "confianza": confianza, "nota": nota}

    if mod != "remoto":
        if nombrados:
            return r(nombrados, "alta", "")
        if latam and not fuera:
            return r(todos, "media", "región LATAM sin país")
        if fuera:
            return r([], "alta", "fuera de LATAM")
        return r(todos, "baja", "confirmar ubicación")

    # Remoto: primero las restricciones explícitas de la descripción
    restringe = _restriccion(desc)
    if restringe:
        r_paises = _paises_nombrados(restringe)
        if r_paises:
            return r(r_paises, "alta", "solo " + ", ".join(r_paises))
        if _nombra(restringe, datos()["toda_latam"]):
            return r(todos, "alta", "")
        if _nombra(restringe, datos()["fuera"]) or re.match(r"(us|usa|u\.s|uk|eu)\b", restringe):
            return r([], "alta", "remoto fuera de LATAM")
    if latam:
        return r(todos, "alta", "")
    if nombrados:
        return r(nombrados, "media" if len(nombrados) == 1 else "alta", "")
    if fuera:
        return r([], "alta", "remoto fuera de LATAM")
    zona = _por_zona_horaria(normalizar.sin_tildes(f"{ubicacion} {titulo} {descripcion[:6000]}").lower())
    if zona is not None:
        return r(zona, "media", "por zona horaria")
    if _nombra(desc, datos()["toda_latam"]):
        return r(todos, "media", "")
    return r(todos, "baja", "remoto: confirmar región")
