"""Contrato v49: afinidad por funciones, sin IA. El título dice que la vacante es del cargo; aquí se comprueba si la
descripción lo respalda, con la huella de funciones del cargo (propia, heredada del mapa de cargos o calculada de noche).

- `cargo_operativo`: el mismo cargo «rellenado» para clasificar, asignar, rescatar, revisar y mostrar.
- `evidencia`: fuerte, débil, ninguna o sin huella; y si además hay una señal de que es otro oficio.
Nada de esto descarta: sin evidencia, la vacante va al final con su etiqueta; con señal de otro oficio, se pregunta en
«Por confirmar» (decisiones de Oscar, 26 nov)."""
from functools import lru_cache
from pathlib import Path
import re

import yaml

from buscador import familias, normalizar
from panel import terminos

MIN_HUELLA = 4    # con menos términos la huella no opina
FUERTE = 3        # términos de la huella para una evidencia fuerte
MIN_TEXTO = 200   # el mismo mínimo de descripción que pide `contrato.entregable`
OTRA_FAMILIA = 4  # herramientas de otra familia del mapa, de otra área (y ninguna de la suya), para señalar otro oficio
ETIQUETA_SIN_FUNCIONES = "Funciones por confirmar"
MOTIVO_OTRO_OFICIO = "Título coincide; funciones de otro oficio"  # motivo en la bandeja «Por confirmar»


@lru_cache(maxsize=1)
def oficios_ajenos():
    """Palabras del título que delatan otro sector (`datos/oficios_ajenos.yaml`), ya normalizadas."""
    ruta = Path(__file__).resolve().parent.parent / "datos" / "oficios_ajenos.yaml"
    try:
        crudo = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except OSError as e:  # sin la lista solo se pierde esa señal; se avisa para que no pase inadvertido
        from buscador import registro
        registro.aviso("contenido:oficios_ajenos", e)
        return ()
    return tuple(dict.fromkeys(normalizar.texto(x) for x in crudo.get("palabras") or [] if normalizar.texto(x)))


def _unicos(valores):
    vistos, salida = set(), []
    for v in valores:
        clave = normalizar.texto(v) if isinstance(v, str) else ""
        if clave and clave not in vistos:
            vistos.add(clave)
            salida.append(v)
    return salida


@lru_cache(maxsize=512)
def familia_del_mapa(nombre):
    """(familia del mapa, nivel) del cargo: 0 si su nombre es el id o un título exacto de la familia, 1 si es similar,
    2 si es un cargo compuesto con ese oficio base («AI Product Manager» → Product Manager). (None, None) si no está."""
    base = normalizar.titulo_base(nombre or "")
    coincidencias = terminos._familias_de(base) if base else []
    if coincidencias:
        nivel, _, f = min(coincidencias, key=lambda x: x[:2])
        return f, nivel
    _, f = terminos.modificador(nombre or "")
    return (f, 2) if f else (None, None)


def distintivo(nombre):
    """Formas (en español e inglés) del modificador de un cargo compuesto: lo que lo distingue de su oficio base."""
    mod, _ = terminos.modificador(nombre or "")
    if not mod:
        return []
    formas = [*(mod.get("es") or []), *(mod.get("en") or [])]
    return _unicos(re.sub(r"^de(?:l)? ", "", f.strip(), flags=re.I) for f in formas)


def cargo_operativo(cargo, aprendidos=(), huella_auto=(), ampliados=()):
    """El cargo como lo usa el motor (un dict nuevo; no cambia lo guardado). A lo que escribió el operador le añade:
    los nombres sugeridos si no puso ninguno, los títulos aprendidos (v25), la huella de funciones (la suya; si no
    tiene, las `herramientas` de su familia del mapa más la huella calculada de noche), los `excluir` de su familia como
    señales de otro oficio (solo si el cargo es título exacto de esa familia), su distintivo si es compuesto y los
    términos ampliados por el LLM (P-14.2). Aplicarlo dos veces da lo mismo."""
    c = dict(cargo)
    nombre = c.get("nombre") or ""
    if not c.get("terminos_exactos"):
        c["terminos_exactos"] = terminos.sugerir(nombre, consultar_esco=False)["terminos_exactos"]
    c["terminos_similares"] = _unicos([*(c.get("terminos_similares") or []), *(aprendidos or ())])
    # P-14.2: los términos ampliados por el LLM (ya filtrados, `panel.ampliados`) van aparte: `grado` solo los reconoce
    # contenidos en el título, nunca por similitud textual.
    if ampliados or c.get("terminos_ampliados"):  # sin ellos, el cargo queda igual que antes (ni la clave)
        c["terminos_ampliados"] = _unicos([*(c.get("terminos_ampliados") or []), *(ampliados or ())])
    familia, nivel = familia_del_mapa(nombre)
    if not c.get("funciones"):
        c["funciones"] = _unicos([*((familia or {}).get("herramientas") or []), *(huella_auto or ())])[:40]
    propios = [normalizar.texto(x) for x in [nombre, *c["terminos_exactos"], *c["terminos_similares"],
                                             *(c.get("terminos_cercanos") or [])]]
    if familia and nivel == 0 and "excluir_mapa" not in c:
        # Un excluido del mapa que el propio cargo usa en sus términos («UX Engineer» como similar) no es señal.
        c["excluir_mapa"] = [x for x in familia.get("excluir") or []
                             if not any(normalizar.contiene_frase(p, normalizar.texto(x)) for p in propios)]
    c.setdefault("excluir_mapa", [])
    c.setdefault("distintivo", distintivo(nombre))
    return c


@lru_cache(maxsize=2048)
def _patron(frases):
    """Una sola expresión con las frases (ya normalizadas), la más larga primero."""
    alternativas = "|".join(re.escape(f) for f in sorted(set(frases), key=len, reverse=True) if f)
    return re.compile(r"(?<![a-z0-9])(?:" + alternativas + r")(?![a-z0-9])") if alternativas else None


def _halladas(texto_normalizado, frases):
    patron = _patron(tuple(frases))
    return {m.group(0) for m in patron.finditer(texto_normalizado)} if patron else set()


@lru_cache(maxsize=1)
def _herramientas_del_mapa():
    return tuple((f["id"], f.get("area") or "", f.get("nombre") or f["id"], tuple(h for h in f["_herramientas"] if h))
                 for f in familias.mapa_base() if len(f["_herramientas"]) >= OTRA_FAMILIA)


def _otra_familia(desc, propia):
    """Nombre de otra familia del mapa, de OTRA área, cuyas herramientas (`OTRA_FAMILIA` o más) sí están en la descripción, o ''.
    Las familias de la misma área comparten herramientas (backend y fullstack, growth y marketing digital): no señalan."""
    area = (propia or {}).get("area")
    for fid, su_area, nombre, herramientas in _herramientas_del_mapa():
        if fid != (propia or {}).get("id") and (not area or su_area != area) \
                and len(_halladas(desc, herramientas)) >= OTRA_FAMILIA:
            return nombre
    return ""


def evidencia(titulo, descripcion, cargo):
    """Lo que la descripción dice sobre el cargo (`cargo`: el de `cargo_operativo`).
    {nivel, halladas, falta_distintivo, otro_oficio, senal}:
    - nivel: «fuerte» (3+ funciones de la huella, o el nombre del cargo 2+ veces), «debil» (1 o 2), «ninguna», o
      «sin_huella» si no hay huella suficiente o el aviso no trae descripción (entonces no opina).
    - falta_distintivo: en un cargo compuesto, la forma que no aparece ni en el título ni en la descripción («IA»).
    - otro_oficio: sin ninguna evidencia y con una señal positiva de otro oficio (`senal` dice cuál)."""
    crudo = descripcion or ""
    desc, tit = normalizar.texto(crudo)[:12000], normalizar.texto(titulo or "")
    funciones = [f for f in cargo.get("funciones") or [] if normalizar.texto(f)]
    huella = [normalizar.texto(f) for f in funciones]
    con_texto = len(crudo) >= MIN_TEXTO
    falta = ""
    formas = cargo.get("distintivo") or []
    if formas and con_texto and not _halladas(f"{tit} {desc}", [normalizar.texto(f) for f in formas]):
        falta = formas[0]
    if not con_texto or len(huella) < MIN_HUELLA:
        return {"nivel": "sin_huella", "halladas": [], "falta_distintivo": falta, "otro_oficio": False, "senal": ""}
    encontradas = _halladas(desc, huella)
    halladas = [f for f, h in zip(funciones, huella) if h in encontradas]
    nombres = [normalizar.texto(x) for x in [cargo.get("nombre") or "", *(cargo.get("terminos_exactos") or [])]]
    patron = _patron(tuple(n for n in nombres if n))
    menciones = len(patron.findall(desc)) if patron else 0
    nivel = "fuerte" if len(halladas) >= FUERTE or menciones >= 2 else "debil" if halladas or menciones else "ninguna"
    # Un título que es exactamente uno de los nombres del cargo (o uno aprobado por el operador, v25) nunca se retiene:
    # con una descripción pobre solo va al final. La señal de otro oficio es para títulos con algo más.
    propios = {normalizar.titulo_base(x) for x in [cargo.get("nombre") or "", *(cargo.get("terminos_exactos") or []),
                                                    *(cargo.get("terminos_similares") or [])]}
    senal = _senal(tit, desc, cargo, nombres + huella) \
        if nivel == "ninguna" and normalizar.titulo_base(titulo or "") not in propios else ""
    return {"nivel": nivel, "halladas": halladas[:8], "falta_distintivo": falta, "otro_oficio": bool(senal),
            "senal": senal}


def _senal(tit, desc, cargo, propios):
    """Señal positiva de otro oficio para un título sin ninguna evidencia: un excluido de su familia del mapa, una
    palabra de otro sector que el cargo no usa, o las herramientas de otra familia del mapa."""
    for x in cargo.get("excluir_mapa") or []:
        if normalizar.contiene_frase(tit, normalizar.texto(x)):
            return x
    for palabra in _halladas(tit, oficios_ajenos()):
        if not any(normalizar.contiene_frase(p, palabra) for p in propios):
            return palabra
    familia, _ = familia_del_mapa(cargo.get("nombre") or "")
    return _otra_familia(desc, familia)


MIN_PUROS = 15       # avisos con el título exacto del cargo para calcular su huella de un idioma
TERMINOS_POR_IDIOMA = 12


def huellas_automaticas(vacantes, cargos):
    """{cargo_id: [términos]} calculados de la bodega de la noche, sin IA (`funciones.proponer`, v25): lo que más
    distingue a los avisos cuyo título es exactamente un nombre del cargo frente a los de otros títulos. Por idioma
    (español e inglés por separado): una huella solo en inglés dejaría «sin evidencia» a los avisos en español.
    Solo sirve para ordenar y para no castigar cargos sin huella propia; nunca reemplaza la que escribió el operador."""
    from panel import funciones
    con_texto = [v for v in vacantes if len(v.get("_descripcion") or "") >= MIN_TEXTO and v.get("idioma") in ("es", "en")
                 and v.get("titulo") and v.get("tipo") != "post"]
    bases = [(normalizar.titulo_base(v["titulo"]), v) for v in con_texto]
    salida = {}
    for cargo in cargos:
        nombres = [cargo.get("nombre") or "", *(cargo.get("terminos_exactos") or [])]
        puros = {normalizar.titulo_base(x) for x in nombres} - {""}
        terminos_cargo = []
        for idioma in ("es", "en"):
            suyos = [v["_descripcion"] for b, v in bases if b in puros and v["idioma"] == idioma]
            if len(suyos) < MIN_PUROS:
                continue
            otros = [v["_descripcion"] for b, v in bases if v["idioma"] == idioma and b not in puros
                     and not terminos.grado(v["titulo"], cargo, cercanos=True)[0]]
            otros = otros[::max(1, len(otros) // 400)][:400]  # muestra estable: uno de cada tantos
            terminos_cargo += funciones.proponer(suyos, otros, maximo=TERMINOS_POR_IDIOMA,
                                                 excluir=[*nombres, *(cargo.get("terminos_similares") or [])])
        if terminos_cargo:
            salida[str(cargo["id"])] = _unicos(terminos_cargo)
    return salida


def penalizacion(e):
    """Lo que pesa al ordenar: como una cosa más que no cumple (contrato v27), nunca descarta."""
    return 1 if e["nivel"] == "ninguna" or e["falta_distintivo"] else 0


def avisos(e):
    """Etiquetas para el panel y para ordenar el mensaje de WhatsApp."""
    salida = [ETIQUETA_SIN_FUNCIONES] if e["nivel"] == "ninguna" else []
    if e["falta_distintivo"]:
        salida.append(f"No menciona {e['falta_distintivo']}")
    return salida


def explicacion(e):
    """Lo que se guarda en `panel_asignaciones.explicacion` (contrato v49)."""
    return {"funciones": e["nivel"], "halladas": e["halladas"],
            **({"falta": e["falta_distintivo"]} if e["falta_distintivo"] else {})}
