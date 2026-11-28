"""Filtros verificables por perfil. No infiere compatibilidad con un CV ni llama a una IA."""
from functools import lru_cache
import re
from datetime import date

from buscador import contrato, enlaces, normalizar, paises, tasas, tiempos
from panel.modelos import Perfil, horas_de_zona, pais_de_ciudad

NIVELES = ["A1", "A2", "B1", "B2", "C1", "C2", "native"]
CAMPOS_FILTRO = ("id", "titulo", "paises", "confianza_pais", "modalidad", "idioma", "publicada_en",
                 "fecha_publicacion", "fecha_estimada", "ids_agrupados", "salario", "paises_mundo", "alcance_mundial",
                 "zona_utc", "ubicacion", "nota_pais")


def ligera(datos, descripcion=None):
    """Solo lo que usan los filtros, con experiencia e inglés ya interpretados por las mismas funciones del motor.
    Permite estimar sobre miles de vacantes sin conservar descripciones ni enlaces. Los años mínimos no dependen del
    texto; el inglés exigido viene calculado en el catálogo (contrato v7). Si falta y no hay descripción, se usa el
    nivel guardado tratándolo como obligatorio: la estimación puede quedar corta, nunca inflada."""
    v = {k: datos.get(k) for k in CAMPOS_FILTRO}
    # Contrato v37: el estado del enlace, para contar «listas» en la cobertura (no interviene en `evaluar`).
    estado = datos.get("verificacion")
    v["_verificacion"] = estado.get("estado", "") if isinstance(estado, dict) else (estado or "")
    v["_anos_minimos"] = contrato.anos("", datos.get("anos_min"))[0]
    if descripcion is None and datos.get("requisito_ingles") is not None:
        v["_requisito_ingles"] = datos["requisito_ingles"]
    else:
        v["_requisito_ingles"] = contrato.requisitos_idioma(descripcion or "", datos.get("ingles", ""))
    return v


# Contrato v27: regla del sistema (no del perfil): nunca se entrega una vacante publicada hace más de 30 días.
def _dias_maximos():
    try:
        import yaml
        from pathlib import Path
        ruta = Path(__file__).resolve().parent.parent / "datos" / "config.yaml"
        return int(yaml.safe_load(ruta.read_text(encoding="utf-8")).get("dias_maximos", 30))
    except Exception:  # noqa: BLE001 — sin config se usa el valor del contrato
        return 30


ANTIGUEDAD_SISTEMA = _dias_maximos()  # el mismo límite que usa la captura (`datos/config.yaml`)
AVISO_RESTRICCION = {"salario menor al aceptado": "Salario menor al que pide",
                     "menciona algo que el perfil no acepta": "Menciona algo que no acepta",
                     "tipo de contrato no aceptado": "Tipo de contrato que no acepta"}


# Contrato v28: a un post con la ubicación deducida o sin confirmar solo se le perdona lo que depende de saber dónde y
# cómo es (país y modalidad); idioma, fecha y lo demás se exigen igual. Los «sin confirmar», hasta 2 por perfil al día;
# desde v49 el tope cuenta todo post al que se le perdonó la ubicación (también los «deducidos»).
POST_UBICACION_TOLERADA = {"país sin elegibilidad confirmada", "modalidad diferente"}
TOPE_POSTS_SIN_CONFIRMAR = 2
ETIQUETA_POST_UBICACION = {"deducida": "Post · ubicación deducida", "sin_confirmar": "Post · ubicación sin confirmar"}


def post_ubicacion(v):
    """'sin_confirmar', 'deducida' o '' según lo que se sabe de la ubicación de un post (contrato v28)."""
    if v.get("tipo") != "post":
        return ""
    if v.get("ubicacion_sin_confirmar") and v.get("confianza_pais") not in {"alta", "media"}:
        return "sin_confirmar"
    return "deducida" if v.get("ubicacion_deducida") else ""


def evaluar_post(v, perfil, hoy=None):
    """Como `evaluar`, pero un post deducido o sin confirmar que solo falla por país o modalidad se admite."""
    r = evaluar(v, perfil, hoy)
    if not r["compatible"] and post_ubicacion(v) and set(r["motivos"]) <= POST_UBICACION_TOLERADA:
        r = dict(r, compatible=True, motivos=[], pruebas=[*r["pruebas"], ETIQUETA_POST_UBICACION[post_ubicacion(v)]])
        tolerada = True
    else:
        tolerada = False
    return dict(r, tolerada=tolerada)  # contrato v49: se le perdonó el país o la modalidad; cuenta para el tope diario


MOTIVO_TITULO_AJENO = "el título actual no corresponde al cargo configurado"


def evaluar_asignada(v, perfil, hoy, ampliacion=""):
    """La evaluación con que se asignó: ampliada con su nivel, post (contrato v28) o la normal."""
    if ampliacion:
        return evaluar_ampliada(v, perfil, hoy, ampliacion)
    if v.get("tipo") == "post":
        return evaluar_post(v, perfil, hoy)
    return evaluar(v, perfil, hoy)


def encaja_asignada(v, perfil, cargo, hoy, ampliacion="", aprobada=False):
    """7.H (decisión de Oscar, 28 nov): la regla única de «¿esta vacante le sigue sirviendo a quien se le asignó?», la
    misma en el panel (`servicio.resultados`) y en la comprobación final de la Bodega (`bodega.afinidad_vigente`). Encaja
    si cumple el perfil y su título corresponde al cargo operativo (`grado` con cercanos), aunque otro cargo la
    reconozca mejor. Una aprobada a mano en «Por confirmar» no se vuelve a mirar por el título. Devuelve la evaluación
    del perfil (con `compatible` y `motivos` ya ajustados por el cargo)."""
    from panel.terminos import grado  # aquí: terminos carga el mapa de cargos y no hace falta al importar afinidad
    r = evaluar_asignada(v, perfil, hoy, ampliacion)
    if not aprobada and not grado(v.get("titulo") or "", cargo, cercanos=True)[0]:
        r = dict(r, compatible=False, motivos=[*r["motivos"], MOTIVO_TITULO_AJENO])
    return r


def faltas(resultado):
    """Contrato v27: cuántas cosas del perfil no cumple una vacante compatible (0 = encaja en todo). Sirve para ordenar."""
    return len(resultado.get("incumple") or ())


# Contrato v9: niveles de ampliación para que cada perfil reciba un mínimo diario. País, idioma, plazo, enlace y los
# requisitos que el aviso sí declara nunca se amplían.
MINIMO_POR_PERFIL = 5
# Contrato v27: los datos sin informar ya no descartan y los cargos cercanos entran directamente, así que solo quedan como
# último recurso la remota abierta a su país (un perfil sin «remoto») y más vacantes de la misma empresa (v11).
# Los nombres antiguos se conservan en ETIQUETAS_AMPLIACION y `relajado` para leer asignaciones ya guardadas.
AMPLIACIONES = ("remota_cercana", "empresa_4")
ETIQUETAS_AMPLIACION = {"sin_dato": "aviso sin años o inglés informados", "cargo_cercano": "cargo cercano",
                        "remota_cercana": "remota abierta a su país",
                        "experiencia_cercana": "experiencia cercana (±2 años)",
                        "empresa_4": "más vacantes de la misma empresa"}
TOPE_EMPRESA_AMPLIADO = 4
HORAS_COMPARTIR = 24  # contrato v31


def relajado(perfil, nivel):
    """Copia del perfil con lo que admite el nivel de ampliación, o None si el nivel no aplica a ese perfil."""
    p = perfil if isinstance(perfil, Perfil) else Perfil.model_validate(perfil)
    cambio = {"aceptar_experiencia_sin_dato": True, "aceptar_ingles_sin_dato": True}
    if nivel == "remota_cercana":
        if "remoto" in p.modalidades:
            return None
        cambio["modalidades"] = [*p.modalidades, "remoto"]
        # Contrato v30: la remota se acepta desde donde vive (primera fila).
        primera, *resto = p.filas
        cambio["ubicaciones"] = [primera.model_copy(update={"modalidades": [*primera.modalidades, "remoto"]}), *resto]
    if nivel in ("experiencia_cercana", "empresa_4"):
        # El aviso sí dice años: se admiten hasta 2 de diferencia con el rango del perfil (nunca país, idioma ni plazo).
        if p.experiencia_min is not None:
            cambio["experiencia_min"] = max(0, p.experiencia_min - 2)
        if p.experiencia_max is not None:
            cambio["experiencia_max"] = min(40, p.experiencia_max + 2)
    return p.model_copy(update=cambio)


def evaluar_ampliada(v, perfil, hoy, nivel):
    """Evaluación con el perfil relajado del nivel; el título cercano lo decide quien llama (grado del cargo)."""
    p = relajado(perfil, nivel)
    return evaluar(v, p, hoy) if p else {"compatible": False, "motivos": ["ampliación no aplicable"], "incumple": [], "avisos": [],
                                         "pruebas": []}


def evaluar(v, perfil, hoy=None):
    p = perfil if isinstance(perfil, Perfil) else Perfil.model_validate(perfil)
    hoy = date.fromisoformat(hoy) if isinstance(hoy, str) else hoy or date.today()
    motivos, pruebas = [], []
    # Contrato v30: la ubicación cumple si alguna fila del perfil (países, ciudades y modalidades) acepta la vacante.
    fallos, prueba = lugar(v, p)
    motivos.extend(fallos)
    if not fallos:
        pruebas.append(prueba)
    if v.get("idioma") not in p.idiomas:
        motivos.append("idioma del aviso diferente")
    # Contrato v27: solo la ubicación, el idioma y las reglas del sistema (30 días, fecha confirmada) descartan. Lo demás
    # del perfil (años, nivel, inglés, restricciones y su antigüedad) ordena y deja un aviso de lo que no cumple.
    incumple, avisos = [], []
    def blando(codigo, texto):
        incumple.append(codigo)
        avisos.append(texto)
    publicada = tiempos.instante(v.get("publicada_en"))
    try:
        fecha = date.fromisoformat((publicada or v.get("fecha_publicacion") or "")[:10])
        edad = (hoy - fecha).days
        if v.get("fecha_estimada") or not 0 <= edad <= ANTIGUEDAD_SISTEMA:
            motivos.append("publicación fuera del plazo")
        elif edad > p.antiguedad_dias:
            blando("publicación fuera del plazo del perfil", f"Publicada hace {edad} días")
        else:
            pruebas.append(f"Publicada hace {edad} días")
    except (ValueError, TypeError):
        motivos.append("fecha de publicación sin confirmar")
    # La vista previa precalcula estos dos datos con las mismas funciones para no conservar descripciones.
    minimo = v["_anos_minimos"] if "_anos_minimos" in v else contrato.anos(v.get("_descripcion", ""), v.get("anos_min"))[0]
    # Contrato v22: con 2 años o menos, junior abierto (sin aviso de experiencia).
    junior_abierto = p.experiencia_anos is not None and p.experiencia_anos <= 2
    if (p.experiencia_min is not None or p.experiencia_max is not None) and not junior_abierto:
        if minimo in ("", None):
            pruebas.append("Experiencia no informada")
        elif (p.experiencia_min is not None and minimo < p.experiencia_min) or (p.experiencia_max is not None and minimo > p.experiencia_max):
            blando("experiencia fuera del rango", f"Pide {minimo} año{'s' if minimo != 1 else ''} de experiencia")
        else:
            pruebas.append(f"Exige {minimo} años de experiencia")
    if p.ingles_maximo != "sin_filtro":
        requisito = v["_requisito_ingles"] if "_requisito_ingles" in v else contrato.requisitos_idioma(
            v.get("_descripcion", ""), v.get("ingles", ""))
        partes = requisito.split(":")
        nivel = partes[1] if len(partes) > 1 else ""
        obligatorio = len(partes) > 2 and partes[2] == "1"
        if nivel not in NIVELES:
            pruebas.append("Inglés no informado")
        elif obligatorio and NIVELES.index(nivel) > NIVELES.index(p.ingles_maximo):
            # Contrato v33 (Oscar, 16 nov): el nivel de inglés sirve para dar mejores matches, no para descartar. Si el
            # aviso exige más que el perfil, llega igual, con su etiqueta y después de las que encajan en todo.
            blando("inglés requerido superior al indicado", f"Pide inglés {'nativo' if nivel == 'native' else nivel}")
        else:
            pruebas.append(f"Inglés {nivel}" + (" deseable" if not obligatorio else " requerido"))
    titulo, descripcion = v.get("titulo") or "", v.get("_descripcion") or ""
    if p.experiencia_anos is not None and p.experiencia_anos >= 5 and (
            contrato.seniority(titulo) in ("intern", "junior") or contrato.tipo_contrato(titulo, descripcion) == "internship"):
        blando("nivel inferior al del perfil", "Es de nivel junior o prácticas")
    for r in p.restricciones:
        motivo = restriccion(v, r, titulo, descripcion)
        if motivo:
            blando(motivo, f"Menciona «{r.texto}»" if r.tipo == "otra" else AVISO_RESTRICCION.get(motivo, motivo))
    return {"compatible": not motivos, "motivos": motivos, "incumple": incumple, "avisos": avisos,
            "pruebas": pruebas}


_POR_MES = {"month": 1, "year": 1 / 12}
MARGEN_SALARIO = 0.10  # contrato v26: redondeos y variación de las tasas no descartan

# Contrato v35: cada zona aceptada por el perfil cubre ±1 hora (horario de verano incluido). Antes (v23) eran tres franjas
# fijas; sus claves se leen como UTC-5, UTC-8 y UTC+1.
MARGEN_ZONA = 1


def lugar(v, p):
    """(motivos, prueba) de la ubicación, por fila (v30). Si ninguna fila sirve, los motivos son los de la primera.
    Contrato v49 (decisiones de Oscar, 26 nov): si el aviso nombra un país, manda ese país.
    - Un país cubierto (LATAM y España) solo cuenta si está en `paises`; uno de fuera, si el aviso lo nombra.
    - «Anywhere in France…» no es alcance mundial. El alcance mundial vale si el aviso no nombra países o los cubre todos.
    - El horario solo abre una remota que NO nombra país (`nota_pais` «por zona horaria») y solo para las zonas que el
      perfil marcó; la zona del país donde vive ya no cuenta sola (antes 95 remotas de otro país llegaban a Colombia).
    - Híbrido/presencial: la fila necesita ciudad y el aviso debe nombrarla (o quedar a 50 km)."""
    modo = v.get("modalidad")
    abiertos, mundial, solo_franja = paises.abiertos(v)
    horario = solo_franja and modo not in ("hibrido", "presencial") and horario_compatible(v, p)
    sin_pais = v.get("confianza_pais") not in {"alta", "media"} and not horario
    primeros = None
    for fila in p.filas:
        motivos, prueba = _en_fila(v, fila, modo, abiertos, mundial, horario, sin_pais)
        if not motivos:
            return [], prueba
        primeros = primeros or motivos
    return primeros or ["no admite postular desde su país"], ""


MOTIVO_SIN_CIUDAD = "falta la ciudad en el perfil"
MOTIVO_CIUDAD_SIN_CONFIRMAR = "oficina sin ciudad confirmada"


def _en_fila(v, fila, modo, abiertos, mundial, horario, sin_pais):
    modos = ("remoto", "hibrido", "presencial")
    motivos = []
    if (modo in modos and modo not in fila.modalidades) or (modo not in modos and not set(modos) <= set(fila.modalidades)):
        motivos.append("modalidad diferente")
    paises_fila = set(fila.paises)
    if sin_pais:
        return motivos + ["país sin elegibilidad confirmada"], ""
    if modo in ("hibrido", "presencial"):
        if motivos:  # la fila no acepta esa modalidad: su ciudad no viene al caso
            return motivos + ([] if abiertos & paises_fila else ["oficina en otro país"]), ""
        if not fila.ciudades:
            return [MOTIVO_SIN_CIUDAD], ""
        if en_sus_ciudades(v, fila.ciudades, paises_fila):
            return motivos, "Oficina en su ciudad"
        if paises_fila and not abiertos & paises_fila:
            return motivos + ["oficina en otro país"], ""
        return motivos + ["oficina en otra ciudad" if otra_ciudad(v, fila.ciudades, paises_fila)
                          else MOTIVO_CIUDAD_SIN_CONFIRMAR], ""
    if horario:  # el aviso no nombra país: lo que la admite es la franja que el perfil marcó
        return motivos, "Remota con horario compatible"
    if abiertos & paises_fila or mundial:
        return motivos, "Remota abierta a su país" if modo == "remoto" else "Ubicación compatible"
    return motivos + ["no admite postular desde su país"], ""


def horario_compatible(v, p):
    """Una remota que solo pide franja horaria sirve si la franja cruza una zona que el perfil marcó en «horarios que
    acepta» (±1 h). Contrato v49: la zona del país donde vive ya no cuenta sola. Sin `zona_utc` no aplica."""
    zona = v.get("zona_utc")
    if not zona:
        return False
    franjas = [(h - MARGEN_ZONA, h + MARGEN_ZONA) for h in map(horas_de_zona, p.acepta_horario) if h is not None]
    return any(zona[0] <= hi and lo <= zona[1] for lo, hi in franjas)


def _paises_del_aviso(v):
    return set(v.get("paises") or []) | set(v.get("paises_mundo") or [])


def _ciudad_del_pais(ciudad, del_aviso, paises_fila):
    """Contrato v49: el nombre de una ciudad no anula el país. Vale si el aviso no dice país o si su país es uno de la
    fila («Santiago» de Chile no acepta «Santiago de Cali, Colombia»; «Paris» de una fila de EE. UU. es la de Texas).
    En una fila sin países, el país es el de la ciudad; si el nombre es de varios, no se puede comprobar y vale."""
    referencia = _paises_de_ciudad(ciudad, paises_fila)
    return not del_aviso or not referencia or bool(del_aviso & referencia)


def _paises_de_ciudad(ciudad, paises_fila):
    """Los países donde puede estar una ciudad del perfil: los de su fila; en una fila sin países, el de la ciudad."""
    return set(paises_fila) or ({pais_de_ciudad(ciudad)} - {None})


def en_sus_ciudades(v, ciudades, paises_fila=()):
    """Contrato v24: la ubicación del aviso nombra una de las ciudades donde trabajaría.
    Contrato v38: o queda a 50 km o menos de una de ellas («Brooklyn, NY» para quien trabajaría en New York).
    Contrato v49: siempre que el país del aviso sea el de esa ciudad (`_ciudad_del_pais`)."""
    ubicacion = normalizar.texto(v.get("ubicacion") or "")
    if not ubicacion:
        return False
    del_aviso = _paises_del_aviso(v)
    return any(normalizar.contiene_frase(ubicacion, normalizar.texto(c)) and _ciudad_del_pais(c, del_aviso, paises_fila)
               for c in ciudades) or _cerca(v, ciudades, paises_fila)


def _cerca(v, ciudades, paises_fila=()):
    """Contrato v38: la ciudad del aviso está en los alrededores de alguna ciudad del perfil (GeoNames, sin IA)."""
    limpia = re.sub(r"\s*\(.*?\)", "", v.get("ubicacion") or "")
    codigos = tuple(sorted(_paises_del_aviso(v)))
    ciudad = contrato._ciudad(limpia, codigos[0] if len(codigos) == 1 else "")
    if not ciudad:
        return False
    estado = paises.estado_eeuu(limpia)
    for c in ciudades:
        # La ciudad del perfil se ubica primero en su país («Madrid» es España, no el Madrid de Cundinamarca); si el
        # nombre es de varios países, en los de su fila (v49: «Valencia» de España no es la de California).
        # Para los alrededores la ciudad se ubica en su propio país cuando el nombre lo dice («Madrid» es la de
        # España aunque la fila sea de Colombia: Bogotá no es «alrededores de Madrid»); si el nombre es de varios
        # países, en los de la fila («Valencia» de España no es la de California).
        if paises_fila and codigos and not set(paises_fila) & set(codigos):
            continue  # la fila es de sus países: «Paris» de una fila de EE. UU. no acepta la de Francia
        suyo = pais_de_ciudad(c)
        referencia = (suyo,) if suyo else tuple(sorted(paises_fila))
        if referencia and codigos and not set(referencia) & set(codigos):
            continue
        if paises.cerca(ciudad, c, referencia or codigos, estado):
            return True
    return False


def otra_ciudad(v, ciudades, paises_fila=()):
    """True si la ubicación del aviso nombra una ciudad y no es ninguna de las del perfil."""
    ubicacion = normalizar.texto(v.get("ubicacion") or "")
    if not ubicacion or en_sus_ciudades(v, ciudades, paises_fila):
        return False  # contrato v38: los alrededores de su ciudad («Jersey City» para New York) no son otra ciudad
    limpia = re.sub(r"\s*\(.*?\)", "", v.get("ubicacion") or "")
    codigo = next(iter(v.get("paises") or v.get("paises_mundo") or []), "")
    ciudad = normalizar.texto(contrato._ciudad(limpia, codigo) or "")
    # Si la «ciudad» es en realidad el nombre de un país («Colombia (On-site)»), el aviso no dice ciudad. Solo nombres
    # de país completos: «New York» también es un estado y sí es una ciudad (contrato v30).
    return bool(ciudad) and ciudad not in _nombres_de_pais()


@lru_cache(maxsize=1)
def _nombres_de_pais():
    return {normalizar.texto(x) for p in paises.mundo()["lista"] for x in (p["nombre"], p.get("nombre_en") or "") if x}

# Contrato v22 (14 nov, pedido de Oscar): lo que el aviso pide solo como deseable no descarta. Marcas editables; se
# buscan como palabras completas en la línea u oración, o en el encabezado de la sección.
MARCAS_DESEABLE = ("deseable", "deseables", "valorable", "se valora", "se valorara", "valoraremos", "plus", "a plus",
                   "nice to have", "nice-to-have", "bonus", "bonus points", "preferred", "preferible", "preferiblemente",
                   "preferentemente", "ideally", "idealmente", "opcional", "optional", "would be great", "extra",
                   "not required", "no excluyente", "no es requisito")
_CORTE_ORACION = re.compile(r"(?<=[.;!?])\s+|\s+[•·▪◦\-–*]\s+")


def _deseable(texto_normalizado):
    return any(normalizar.contiene_frase(texto_normalizado, normalizar.texto(m)) for m in MARCAS_DESEABLE)


_VINETA = re.compile(r"^\s*([-–•·▪◦*]|\d+[.)])\s+")
SECCIONES = ("requirements", "requisitos", "responsabilidades", "responsibilities", "qualifications", "cualificaciones",
             "what you will do", "what you'll do", "que haras", "about you", "sobre ti", "perfil", "beneficios",
             "benefits", "funciones", "tareas", "must have", "must-have", "conocimientos", "skills", "habilidades",
             "experiencia", "experience", "we offer", "ofrecemos")


def menciones_obligatorias(descripcion, palabras):
    """True si la descripción menciona alguna palabra fuera de lo marcado como deseable.
    - Encabezado: «Algo:» al inicio de una línea (hasta 5 palabras antes de los dos puntos) o una línea corta con el
      nombre de una sección conocida. Si es de deseables («Nice to have», «Deseable», «Bonus»…), su sección no cuenta
      hasta el siguiente encabezado.
    - Dentro de cada línea, una oración con marca de deseable («Java is a plus», «idealmente…») no cuenta."""
    if not palabras or not descripcion:
        return False
    en_deseables = False
    for linea in str(descripcion)[:12000].splitlines():
        crudo = linea.strip()
        if not crudo:
            continue
        vineta = bool(_VINETA.match(crudo))
        prefijo, dos_puntos, resto = crudo.partition(":")
        normal = normalizar.texto(crudo)
        if not vineta and dos_puntos and 0 < len(normalizar.texto(prefijo).split()) <= 5:
            en_deseables = _deseable(normalizar.texto(prefijo))
            contenido = resto
        elif not vineta and len(normal.split()) <= 4 and not re.search(r"[.!?)]$", crudo) and (
                _deseable(normal) or any(normalizar.contiene_frase(normal, normalizar.texto(x)) for x in SECCIONES)):
            en_deseables = _deseable(normal)
            contenido = ""
        else:
            contenido = crudo
        if en_deseables or not contenido.strip():
            continue
        for oracion in _CORTE_ORACION.split(contenido):
            o = normalizar.texto(oracion)
            if not _deseable(o) and any(normalizar.contiene_frase(o, w) for w in palabras):
                return True
    return False


def restriccion(v, r, titulo, descripcion):
    """Contrato v22: motivo de descarte de una restricción del perfil, o None. Solo con evidencia clara en el aviso:
    sin salario, sin moneda convertible o sin periodo comparable, nunca descarta. Contrato v26: otra moneda se convierte
    con `datos/tasas_cambio.yaml` y solo descarta si queda más de un 10 % por debajo."""
    if r.tipo == "salario_minimo":
        _, minimo, maximo, moneda, periodo = contrato.salario(v.get("salario"), descripcion)
        valor = maximo if maximo != "" else minimo
        if valor == "" or not moneda or not periodo:
            return None
        valor = tasas.convertir(valor, moneda, r.moneda)
        if valor is None:
            return None
        if "hour" in (periodo, r.periodo):
            if periodo != r.periodo:
                return None
            return "salario menor al aceptado" if valor < r.monto * (1 - MARGEN_SALARIO) else None
        mensual, pedido = valor * _POR_MES[periodo], r.monto * _POR_MES[r.periodo]
        return "salario menor al aceptado" if mensual < pedido * (1 - MARGEN_SALARIO) else None
    if r.tipo == "palabras":
        palabras = [normalizar.texto(w) for w in r.palabras]
        if any(normalizar.contiene_frase(normalizar.texto(titulo), w) for w in palabras) or \
                menciones_obligatorias(descripcion, palabras):
            return "menciona algo que el perfil no acepta"
        return None
    if r.tipo == "otra":  # contrato v35: igual que «palabras», con una sola frase libre
        frase = normalizar.texto(r.texto)
        if frase and (normalizar.contiene_frase(normalizar.texto(titulo), frase) or
                      menciones_obligatorias(descripcion, [frase])):
            return "menciona algo que el perfil no acepta"
        return None
    if r.tipo == "contrato":
        tipo = contrato.tipo_contrato(titulo, descripcion)
        if tipo in r.tipos or ("internship" in r.tipos and contrato.seniority(titulo) == "intern"):
            return "tipo de contrato no aceptado"
    return None


def preferidos(perfiles):
    """Contrato v22: términos preferidos (sectores y palabras) de los perfiles, ya normalizados."""
    salida = set()
    for p in perfiles or ():
        datos = p if isinstance(p, dict) else p.model_dump()
        for t in (datos.get("sectores_preferidos") or []) + (datos.get("palabras_preferidas") or []):
            salida.add(normalizar.texto(t))
    return {t for t in salida if t}


def coincidencias_preferidas(v, terminos):
    """Cuántos términos preferidos distintos menciona la vacante en el título, la descripción o la empresa."""
    if not terminos:
        return 0
    texto = normalizar.texto(" ".join([v.get("titulo") or "", v.get("empresa") or "",
                                       (v.get("_descripcion") or "")[:12000]]))
    return sum(1 for t in terminos if normalizar.contiene_frase(texto, t))


def enlace_utilizable(row, ahora=None):
    """Lee evidencia vigente, no convierte un HTTP 200 ni un estado histórico en disponibilidad."""
    from datetime import datetime, timezone
    ahora = ahora or datetime.now(timezone.utc)
    v = row.get("catalogo_vacantes") or {}
    datos = v.get("datos") or {}
    if v.get("status") != "active" or datos.get("duplicada_de"):
        return ""
    comprobaciones = (datos.get("verificacion") or {}).get("enlaces", [])
    for e in sorted(comprobaciones, key=lambda x: (not enlaces.es_linkedin(x.get("url", "")),
                                                   x.get("url") != datos.get("enlace"))):
        fecha = tiempos.instante(e.get("comprobada_en") or e.get("verificada_en") or e.get("checked_at"))
        if not fecha or e.get("estado") != "verificada":
            continue
        edad = (ahora - datetime.fromisoformat(fecha.replace("Z", "+00:00"))).total_seconds()
        # Contrato v31: un enlace comprobado en las últimas 24 h se puede compartir (antes 6 h; los posts ya 24 h, v11).
        if 0 <= edad < HORAS_COMPARTIR * 3600:
            url = contrato.url_limpia(e.get("url", ""))
            originales = {contrato.url_limpia(x) for x in
                          [datos.get("enlace"), datos.get("enlace_directo"), *datos.get("enlaces_alternativos", [])] if x}
            if url in originales and enlaces.sirve(url):
                return url
    return ""
