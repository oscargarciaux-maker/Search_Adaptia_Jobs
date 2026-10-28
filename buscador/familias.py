"""Mapa de cargos: a qué familias pertenece una vacante y con qué coincidencia (exacto, similar, cercano). Sin IA.

Reglas (docs/PLAN.md, sección del mapa de cargos):
1. El título se normaliza (sin nivel, sin ciudad, sin modalidad; femenino = masculino).
2. Contiene un título de `exactos` → exacto; de `similares` → similar; de `cercanos` → cercano.
   Un título de una sola palabra ("desarrollador", "qa") solo cuenta si es la primera o la última palabra del cargo, y
   baja un grado (exacto → similar), porque dice menos.
3. Si no, comparación aproximada (errores de tipeo, orden de palabras): 90 de 100 o más → similar.
4. Si no, una palabra de `genericos` en el título y 2 o más `herramientas` en la descripción → cercano.
5. Una palabra de `excluir` en el título deja fuera esa familia.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml
from rapidfuzz import fuzz, process

from buscador import normalizar

RUTA = Path(__file__).resolve().parent.parent / "datos" / "mapa_cargos.yaml"
GRADOS = ["exacto", "similar", "cercano"]
_CAMPOS_TITULOS = {"exactos": "exacto", "similares": "similar", "cercanos": "cercano"}


def _es_una_palabra(frase):
    return " " not in frase and "/" not in frase.strip("/")


def _frases(lista, permitir_una_palabra):
    """Títulos normalizados. Se descarta el que, al quitar el nivel, queda en una palabra genérica ("Staff Engineer" ->
    "engineer"), y en `cercanos` no se aceptan títulos de una palabra: dirían demasiado poco."""
    salida = []
    for crudo in lista or []:
        f = normalizar.titulo_base(crudo)
        if not f or f in salida:
            continue
        if _es_una_palabra(f) and (not permitir_una_palabra or len(normalizar.texto(crudo).split()) > 1):
            continue
        salida.append(f)
    return salida


def _regex(frases):
    if not frases:
        return None
    alternativas = "|".join(re.escape(f) for f in sorted(frases, key=len, reverse=True))
    return re.compile(r"(?<![a-z0-9])(?:" + alternativas + r")(?![a-z0-9])")


@lru_cache(maxsize=1)
def mapa():
    crudo = yaml.safe_load(RUTA.read_text(encoding="utf-8"))["familias"]
    familias = []
    for fam in crudo:
        f = dict(fam)
        f["_titulos"] = {grado: _frases(fam.get(campo), grado != "cercano") for campo, grado in _CAMPOS_TITULOS.items()}
        # Para comparar rápido: una expresión por grado con las frases de varias palabras y un conjunto con las de una
        f["_re"] = {g: _regex([x for x in f["_titulos"][g] if not _es_una_palabra(x)]) for g in GRADOS}
        f["_una"] = {g: {x for x in f["_titulos"][g] if _es_una_palabra(x)} for g in GRADOS}
        f["_herramientas"] = [normalizar.texto(h) for h in fam.get("herramientas") or []]
        f["_genericos"] = {normalizar.titulo_base(g) for g in fam.get("genericos") or []}
        f["_excluir"] = _regex([normalizar.texto(e) for e in fam.get("excluir") or []])
        familias.append(f)
    return familias


@lru_cache(maxsize=1)
def _todas_las_frases():
    """(frase, familia, grado) de exactos y similares de varias palabras, para la comparación aproximada."""
    return [(fr, f["id"]) for f in mapa() for g in ("exacto", "similar") for fr in f["_titulos"][g]
            if not _es_una_palabra(fr)]


def _baja(grado):
    return GRADOS[min(GRADOS.index(grado) + 1, len(GRADOS) - 1)]


def _grado(fam, base, extremos):
    """Mejor grado de una familia para el título base, o None."""
    for g in GRADOS:
        if fam["_re"][g] and fam["_re"][g].search(base):
            return g
        # Una sola palabra: solo si es la primera o la última del cargo ("Desarrollador Java", "Java Developer"),
        # y baja un grado porque dice menos
        if fam["_una"][g] & extremos:
            return _baja(g)
    return None


def clasificar(titulo, descripcion=""):
    """Lista de {"familia": id, "coincidencia": grado}, de la mejor coincidencia a la peor."""
    base = normalizar.titulo_base(titulo)
    if not base:
        return []
    completo = normalizar.texto(titulo)
    palabras = [p for p in base.replace("/", " ").split() if p]
    extremos = {palabras[0], palabras[-1]} if palabras else set()
    salida = {}
    excluidas = set()
    for fam in mapa():
        if fam["_excluir"] and fam["_excluir"].search(completo):
            excluidas.add(fam["id"])
            continue
        grado = _grado(fam, base, extremos)
        if grado:
            salida[fam["id"]] = grado
    if not salida and len(base) >= 6:
        # Errores de tipeo u otro orden de palabras ("Desinger UX", "Designer Product")
        mejor = process.extractOne(base, [f for f, _ in _todas_las_frases()], scorer=fuzz.token_sort_ratio,
                                   score_cutoff=90)
        if mejor:
            fam_id = _todas_las_frases()[mejor[2]][1]
            if fam_id not in excluidas:
                salida[fam_id] = "similar"
    if not salida and descripcion:
        desc = normalizar.texto(descripcion)[:8000]
        palabras_set = set(palabras)
        for fam in mapa():
            if fam["id"] in excluidas or not (fam["_genericos"] & palabras_set):
                continue
            if sum(1 for h in fam["_herramientas"] if normalizar.contiene_frase(desc, h)) >= 2:
                salida[fam["id"]] = "cercano"
    return sorted(({"familia": k, "coincidencia": v} for k, v in salida.items()),
                  key=lambda x: GRADOS.index(x["coincidencia"]))


def consultas(familia_id):
    return next(f["consultas"] for f in mapa() if f["id"] == familia_id)


def para_la_pagina():
    """Mapa reducido para la página: nombres y títulos como se escriben, y las frases normalizadas para buscar."""
    return [{
        "id": f["id"], "nombre": f["nombre"], "area": f["area"],
        "exactos": f.get("exactos") or [], "similares": f.get("similares") or [], "cercanos": f.get("cercanos") or [],
        "claves": sorted({k for g in GRADOS for k in f["_titulos"][g]} | {normalizar.titulo_base(f["nombre"])}),
    } for f in mapa()]


def herramientas_en(descripcion, familia_ids=None):
    """Herramientas del oficio que menciona la descripción (de las familias dadas, o de todas)."""
    desc = normalizar.texto(descripcion)[:8000]
    vistas = []
    for fam in mapa():
        if familia_ids and fam["id"] not in familia_ids:
            continue
        for crudo, h in zip(fam.get("herramientas") or [], fam["_herramientas"]):
            if h and normalizar.contiene_frase(desc, h) and crudo not in vistas:
                vistas.append(crudo)
    return vistas[:12]


