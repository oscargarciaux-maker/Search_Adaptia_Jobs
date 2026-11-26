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
def mapa_base():
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


_mapa_operativo = None


def mapa():
    return _mapa_operativo if _mapa_operativo is not None else mapa_base()


def preparar(mapa_crudo):
    resultado = []
    for fam in mapa_crudo:
        f = dict(fam)
        f["_titulos"] = {grado: _frases(fam.get(campo), grado != "cercano") for campo, grado in _CAMPOS_TITULOS.items()}
        # Contrato v44: títulos en español del mapa que solo clasifican (no se buscan: no entran en `consultas`).
        f["_titulos"]["similar"] += [x for x in _frases(fam.get("similares_es"), False) if x not in f["_titulos"]["similar"]]
        f["_re"] = {g: _regex([x for x in f["_titulos"][g] if not _es_una_palabra(x)]) for g in GRADOS}
        f["_una"] = {g: {x for x in f["_titulos"][g] if _es_una_palabra(x)} for g in GRADOS}
        f["_herramientas"] = [normalizar.texto(h) for h in fam.get("herramientas", [])]
        f["_genericos"] = set()
        f["_excluir"] = _regex([normalizar.texto(e) for e in fam.get("excluir", [])])
        # Contrato v25: funciones del cargo (huella) y sus términos exactos para leer la descripción.
        f["_funciones"] = sorted({normalizar.texto(x) for x in fam.get("funciones") or [] if normalizar.texto(x)})
        f["_exactos_desc"] = sorted({normalizar.texto(x) for x in fam.get("exactos") or [] if normalizar.texto(x)})
        resultado.append(f)
    return resultado


def configurar(mapa_crudo=None):
    global _mapa_operativo
    _mapa_operativo = preparar(mapa_crudo) if mapa_crudo is not None else None
    _todas_las_frases.cache_clear()


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


# Contrato v25: títulos que no dicen el oficio; con ellos manda lo que diga la descripción.
GENERICOS = {"profesional", "especialista", "consultor", "consultora", "analista", "coordinador", "coordinadora",
             "asociado", "asociada", "specialist", "consultant", "professional", "associate", "lead", "senior",
             "junior", "experto", "experta", "expert"}
GRADO_FUNCIONES = "funciones"  # nunca se entrega solo: va a «Por confirmar» (contrato v25)
# Contrato v49: lo contrario de «funciones». El título SÍ es del cargo, pero la descripción no trae ninguna de sus
# funciones y hay una señal de otro oficio. Tampoco se entrega solo: va a «Por confirmar» con su propio motivo.
GRADO_OTRO_OFICIO = "otro_oficio"
# Del más fuerte al más débil. Lo usan `clasificar` y `vacante.unir` (al juntar copias gana el más fuerte): un grado
# nuevo se añade aquí o juntar dos copias falla.
ORDEN_GRADOS = GRADOS + [GRADO_FUNCIONES, GRADO_OTRO_OFICIO]


def _por_descripcion_panel(palabras, descripcion, excluidas):
    """Contrato v25, solo cargos del panel: {familia: grado} leyendo la descripción cuando el título no encajó."""
    desc = normalizar.texto(descripcion)[:12000]
    if not desc:
        return {}
    salida = {}
    generico = bool(palabras) and set(palabras) <= GENERICOS | {"de", "en", "y", "and", "of", "the", "i", "ii", "iii"}
    for fam in mapa():
        if not fam.get("_control_cargo") or fam["id"] in excluidas:
            continue
        if generico and fam["_exactos_desc"]:
            veces = sum(len(re.findall(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", desc))
                        for t in fam["_exactos_desc"])
            if veces >= 2:
                salida[fam["id"]] = "similar"
                continue
        funciones = fam["_funciones"]
        if funciones:
            halladas = sum(1 for t in funciones if normalizar.contiene_frase(desc, t))
            if halladas >= max(4, -(-3 * len(funciones) // 10)):
                salida[fam["id"]] = GRADO_FUNCIONES
    return salida


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
        if fam.get("_control_cargo"):
            if fam["_excluir"] and fam["_excluir"].search(completo):
                excluidas.add(fam["id"])
                continue
            from panel.terminos import grado as grado_control
            g, _ = grado_control(titulo, fam["_control_cargo"], cercanos=True)
            if g and descripcion:
                # Contrato v49: el título es del cargo, pero la descripción no trae ninguna de sus funciones y hay
                # una señal de otro oficio. No se entrega sola: queda con el grado «otro_oficio» y se pregunta.
                from panel.contenido import evidencia
                if evidencia(titulo, descripcion, fam["_control_cargo"])["otro_oficio"]:
                    g = GRADO_OTRO_OFICIO
            if g:
                salida[fam["id"]] = g
            continue
        # Un vecino explícito (p. ej. UX Engineer) no debe quedar anulado por la exclusión genérica «engineer».
        nombrado = any(base in fam["_titulos"][g] for g in GRADOS)
        if fam["_excluir"] and fam["_excluir"].search(completo) and not nombrado:
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
        salida.update(_por_descripcion_panel(palabras, descripcion, excluidas))
    if not salida and descripcion:
        desc = normalizar.texto(descripcion)[:8000]
        palabras_set = set(palabras)
        for fam in mapa():
            if fam["id"] in excluidas or not (fam["_genericos"] & palabras_set):
                continue
            if sum(1 for h in fam["_herramientas"] if normalizar.contiene_frase(desc, h)) >= 2:
                salida[fam["id"]] = "cercano"
    return sorted(({"familia": k, "coincidencia": v} for k, v in salida.items()),
                  key=lambda x: ORDEN_GRADOS.index(x["coincidencia"]))


def consultas(familia_id):
    return next(f["consultas"] for f in mapa() if f["id"] == familia_id)


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


