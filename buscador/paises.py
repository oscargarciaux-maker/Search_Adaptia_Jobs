"""Desde qué países de LATAM y del mundo hispanohablante (España) se puede aplicar a una vacante (sin IA).

Mira primero la ubicación y el título del aviso; la descripción solo cuenta para la modalidad remota y para frases que
restringen dónde debe vivir la persona ("must be based in", "only candidates from"). Devuelve:
  {"paises": [códigos], "modalidad": "remoto|hibrido|presencial|sin dato", "confianza": "alta|media|baja",
   "nota": texto corto para la página}
Si nadie de esos países puede aplicar, "paises" queda vacío. Remoto para LATAM no incluye a España; remoto para el
mundo sí; remoto para Europa es solo España.
"""
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import yaml

from buscador import normalizar

RUTA = Path(__file__).resolve().parent.parent / "datos" / "paises.yaml"
RUTA_MUNDO = RUTA.parent / "paises_mundo.yaml"
RUTA_LUGARES = RUTA.parent / "lugares_mundo.json.gz"  # contrato v19: GeoNames (CC BY 4.0), generado
RUTA_AREAS = RUTA.parent / "areas_metropolitanas.yaml"  # contrato v32
RUTA_ALIAS = RUTA.parent / "alias_lugares.yaml"  # contrato v38
RUTA_CORREGIDAS = RUTA.parent / "ubicaciones_corregidas.yaml"  # 7.E: errores conocidos de un portal
_METRO = re.compile(r"^(?:area metropolitana de |region metropolitana de |greater )(.+?)(?: area| metropolitan area)?$|"
                    r"^(.+?) (?:y alrededores|and surrounding areas|metropolitan area|area metropolitana|area)$")


@lru_cache(maxsize=1)
def areas_metropolitanas():
    try:
        crudo = yaml.safe_load(RUTA_AREAS.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}
    return {normalizar.texto(k): str(v).upper() for k, v in crudo.items()}


def area_metropolitana(texto):
    """Contrato v32: el país de un área metropolitana con formato LinkedIn («Roma y alrededores» → IT), o "".
    Contrato v38: si la lista no la trae, el país de fuera de la ciudad en GeoNames cuando no es ambigua («Greater
    Toronto Area» → CA, «Seattle y alrededores» → US)."""
    m = _METRO.match(normalizar.texto(texto or ""))
    if not m:
        return ""
    nombre = (m.group(1) or m.group(2) or "").strip()
    if nombre in areas_metropolitanas():
        return areas_metropolitanas()[nombre]
    pais = _pais_de_nombre(nombre)
    return pais if pais not in datos()["codigos"] else ""  # los países cubiertos siguen con su tabla curada


@lru_cache(maxsize=1)
def _alias():
    try:
        crudo = yaml.safe_load(RUTA_ALIAS.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}
    salida = {}
    for k, v in crudo.items():
        pais, _, ciudad = str(v).partition(",")
        salida[normalizar.texto(k)] = (pais.strip().upper(), normalizar.texto(ciudad))
    return salida


@lru_cache(maxsize=1)
def alias_lugares():
    """Contrato v38: apodo → país ISO («nyc» → US)."""
    return {k: pais for k, (pais, _) in _alias().items()}


def alias_ciudad(nombre):
    """Contrato v38: la ciudad a la que equivale un apodo («nyc» → «new york city»), o el mismo nombre."""
    return _alias().get(nombre, ("", ""))[1] or nombre


@lru_cache(maxsize=1)
def ubicaciones_corregidas():
    """7.E (27 nov): ubicación entera que un portal escribe mal → la que dice el aviso (`datos/ubicaciones_corregidas.yaml`)."""
    try:  # el operador edita este archivo: si está mal escrito, se avisa y la búsqueda sigue sin correcciones
        crudo = yaml.safe_load(RUTA_CORREGIDAS.read_text(encoding="utf-8")) or {}
        if not isinstance(crudo, dict):
            raise ValueError("debe ser «ubicación del portal: ubicación correcta»")
    except (OSError, yaml.YAMLError, ValueError) as e:
        from buscador import registro
        registro.aviso("paises:ubicaciones-corregidas", e)
        return {}
    return {clave(k): str(v).strip() for k, v in crudo.items() if k and v and str(v).strip()}


def corregir_ubicacion(ubicacion):
    """La ubicación corregida si el texto entero está en `datos/ubicaciones_corregidas.yaml`; si no, la misma."""
    return ubicaciones_corregidas().get(clave(ubicacion), ubicacion or "")

_REMOTO = re.compile(r"\b(remote|remoto|remota|remotely|teletrabajo|home ?office|work from home|wfh|trabajo a distancia|"
                     r"100% remoto|distributed|fully distributed|anywhere|desde casa|trabajo desde casa|remote work)\b")
# Contrato v49: la descripción llega normalizada (sin «%» ni «:»), así que «Modalidad: 100% remoto» es «modalidad 100
# remoto». Con el «%» escrito, estos patrones nunca coincidían y el aviso quedaba presencial en la ciudad de la empresa.
_REMOTO_DESC = re.compile(r"\b(fully remote|100 remote|100 remoto|100 remota|remoto 100|trabajo remoto|remote[- ]first|"
                          r"remote position|remote role|remote job|this is a remote|posicion remota|modalidad remota|"
                          r"modalidad remoto|modalidad de trabajo remot[oa]|totalmente remot[oa]|home office)\b")
_NO_REMOTO = re.compile(r"\b(?:no|not|sin|nunca|isn t|is not|no es|tampoco)\b[a-z ]{0,18}$")


def _remoto_en_descripcion(d):
    """True si la descripción dice que el trabajo es remoto (y no lo niega justo antes: «no es 100% remoto»)."""
    return any(not _NO_REMOTO.search(d[max(0, m.start() - 25):m.start()]) for m in _REMOTO_DESC.finditer(d))
_HIBRIDO = re.compile(r"\b(hybrid|hibrido|hibrida|semipresencial|semi presencial)\b")
_PRESENCIAL = re.compile(r"\b(on ?site|onsite|presencial|in office|in-office)\b")
# Restricciones de residencia en la descripción. Se comparan contra el texto normalizado (sin tildes, minúsculas).
_RESTRINGE = re.compile(
    r"\b(must|should|need to|required to|have to)\s+(be\s+)?(?:(?:physically|currently|legally)\s+)?(reside|live|located|based|living|residing)\s+(in|within)\s+"
    r"(the\s+)?(?P<lugar>[a-z .]{2,40})"
    r"|\b(only|solo|solamente|unicamente|exclusively)\s+(open\s+to\s+)?(candidates|applicants|candidatos|personas|residents)?\s*"
    r"(from|in|de|en|residing in|located in|based in)\s+(the\s+)?(?P<lugar2>[a-z .]{2,40})"
    r"|\b(?P<lugar3>us|usa|u\.s|united states|uk|canada|eu|europe|india)[- ](?P<marca3>only|based|residents?)\b"
    r"|\b(?:must be|must have|need to be|required to be)\s+(?:legally )?(?:authorized to work|eligible to work|the right to work)\s+in\s+(?:the )?(?P<lugar4>[a-z .]{2,40})"
    r"|\b(?:debes?|debera[s]?|es necesario|se requiere)\s+(?:residir|vivir|estar ubicado|estar ubicada|tener residencia)\s+en\s+(?P<lugar5>[a-z .]{2,40})")
# Contrato v49: «US-based» solo restringe la residencia si habla de la persona («must be US-based», «US-based
# candidates»). «A leading US-based company» o «US based clients» describen a la empresa: 243 vacantes de la bodega del
# 25 nov quedaban fuera de LATAM solo por eso.
_BASADO_ANTES = re.compile(r"\b(?:must be|should be|need to be|needs to be|have to be|has to be|required to be|are|is|"
                           r"be|being|currently)\s*$")
_BASADO_DESPUES = re.compile(r"\s*(?:candidates?|applicants?|only|residents?|talent|individuals?|professionals?|"
                             r"citizens?|people|persons?|(?:fully\s+)?(?:remote\s+)?(?:roles?|positions?|jobs?))\b")
# Contrato v49: «Anywhere in France, Belgium, Spain» o «en cualquier parte de México» no es para cualquier país: manda
# el lugar que nombra después.
_MUNDO_ACOTADO = re.compile(r"\b(?:anywhere|worldwide|any country|cualquier (?:parte|lugar|pais))\s+"
                            r"(?:in|within|across|en|de|del|dentro de)\b"
                            r"(?!\s+(?:the\s+)?(?:world|globe|planet)\b|\s+(?:todo\s+)?(?:el\s+)?(?:mundo|planeta)\b)")


def abiertos(v):
    """Contrato v49: (países desde los que se puede postular, si es para cualquier país, si solo pide una franja
    horaria) de una vacante ya etiquetada. Una sola regla para quien decide (`panel.afinidad.lugar`), quien prioriza
    (`cobertura.sirve_a_corta`), la admisión (`bodega._sirve_a_perfiles`) y la medición.
    - Un país cubierto solo cuenta si está en `paises`; uno de fuera, si el aviso lo nombra (`paises_mundo`).
    - «Anywhere in France…» no es alcance mundial: manda lo nombrado. El alcance mundial vale si el aviso no nombra
      países o si `paises` trae todos los cubiertos.
    - «Solo franja»: la nota «por zona horaria» y ningún país nombrado."""
    elegibles, nombrados = set(v.get("paises") or []), set(v.get("paises_mundo") or [])
    cubiertos = set(datos()["codigos"])
    acotado = mundo_acotado(v.get("ubicacion"))
    # «Anywhere in LATAM» acota a una región que no deja países sueltos en `paises_mundo`: ahí manda `paises`.
    paises_abiertos = ((elegibles & nombrados) if acotado and nombrados else elegibles) | (nombrados - cubiertos)
    mundial = bool(v.get("alcance_mundial")) and not acotado and (not nombrados or cubiertos <= elegibles)
    return paises_abiertos, mundial, v.get("nota_pais") == NOTA_ZONA and not nombrados


NOTA_ZONA = "por zona horaria"
NOTA_APERTURA = "abierta a esos países según el aviso"  # contrato v50: lo dice la letra pequeña en español


_TRAS_ACOTAR = re.compile(r"^\s*(?:in|within|across|en|de|del|dentro de)\s+(?:the\s+|el\s+|la\s+|los\s+|las\s+)?")


def mundo_acotado(ubicacion):
    """True si la ubicación dice «en cualquier parte de <un lugar>» (no es alcance mundial)."""
    return _MUNDO_ACOTADO.search(normalizar.texto(ubicacion or "")) is not None


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
    ciudades = {}
    for p in paises:
        for ciudad in p["ciudades"]:
            ciudades.setdefault(normalizar.texto(ciudad),[]).append(p["codigo"])
    # Contrato v15: la tabla ISO completa (datos/paises_mundo.yaml). Cada lugar apunta a su país propio (los 21 de
    # paises.yaml) o a «XX» (extranjero). Un nombre que apunta a más de un país es ambiguo y nunca decide solo.
    propios = {p["codigo"] for p in paises}
    mundo = yaml.safe_load(RUTA_MUNDO.read_text(encoding="utf-8"))["paises"] if RUTA_MUNDO.exists() else []
    nombres_propios = {normalizar.texto(x): p["codigo"] for p in paises for x in p["nombres"]}
    for m in mundo:
        if m["iso2"] in propios:
            nombres_propios.update({n: m["iso2"] for n in m["nombres"]})
    lugares = {}
    def anotar(frase, codigo):
        frase = normalizar.texto(frase)
        if len(frase) > 2 and nombres_propios.get(frase, codigo) == codigo:  # el nombre de un país propio siempre gana
            lugares.setdefault(frase, set()).add(codigo)
    for p in paises:
        for ciudad in p["ciudades"]:
            anotar(ciudad, p["codigo"])
    curadas = {f: set(c) for f, c in lugares.items()}  # ciudades elegidas a mano: ganan a una provincia homónima
    comunes = {normalizar.texto(x) for x in crudo.get("palabras_comunes", [])}
    provincias_fuera = set()
    for m in mundo:
        codigo = m["iso2"] if m["iso2"] in propios else "XX"
        for sub in m.get("subdivisiones", []):
            if normalizar.texto(sub) in comunes:
                continue  # «Como», «Mayo», «Laguna»: palabras corrientes, no lugares
            anotar(sub, codigo)
            if codigo == "XX":
                provincias_fuera.add(normalizar.texto(sub))
        if codigo == "XX":
            for n in m["nombres"]:
                anotar(n, "XX")
    for frase in crudo["fuera_de_latam"]:
        anotar(frase, "XX")
    for f, c in curadas.items():
        lugares[f] = c
    ambiguas = {f for f, c in lugares.items() if len(c) > 1} | {normalizar.texto(f) for f in crudo.get("ambiguas", [])}
    ciudades = {f: sorted(c) for f, c in lugares.items() if "XX" not in c and f not in ambiguas}
    fuera_lugares = {f for f, c in lugares.items() if c == {"XX"} and f not in ambiguas}
    fuera_lugares |= {normalizar.texto(x) for x in crudo["fuera_de_latam"] if len(normalizar.texto(x)) <= 2}  # "us", "uk"
    # Las provincias extranjeras solo se buscan en el campo de ubicación; en frases de la descripción, solo países y la
    # lista hecha a mano (una provincia puede llamarse como una palabra corriente).
    fuera = fuera_lugares - provincias_fuera
    nombres_pais = []  # con los otros nombres de la tabla mundial («equador», «united mexican states»)
    for p in paises:
        extra = next((m["nombres"] for m in mundo if m["iso2"] == p["codigo"]), [])
        nombres_pais.append((p["codigo"], [normalizar.texto(x) for x in p["nombres"] + extra + p["gentilicios"]]))
    todos_nombres = [n for _, ns in nombres_pais for n in ns]
    # Lugares extranjeros que contienen el nombre de un país propio («New Mexico», «Nuevo México»): se quitan antes de
    # buscar nombres de país, así no se leen como México.
    fuera_con_propio = sorted((f for f in fuera_lugares if any(normalizar.contiene_frase(f, n) and f != n for n in todos_nombres)),
                              key=len, reverse=True)
    # Lugares propios que contienen un lugar extranjero («Baja California», «Nuevo León»?): se quitan antes de buscar
    # lugares extranjeros, así «California» no convierte a Baja California en EE. UU.
    propios_con_fuera = sorted((f for f in ciudades if _patron(tuple(fuera_lugares)).search(f)), key=len, reverse=True)
    claves.sort(key=lambda x: -len(x[0]))  # las frases largas primero ("santiago de chile" antes que "santiago")
    # Contrato v12: «paises» son todos los que se reconocen en un aviso; «codigos», «latam» y «europa», solo los cubiertos.
    cubiertos = [p for p in paises if p.get("cobertura", True)]
    return {
        "paises": paises,
        "cubiertos": cubiertos,
        "codigos": [p["codigo"] for p in cubiertos],
        "reconocidos": [p["codigo"] for p in paises],
        "latam": [p["codigo"] for p in cubiertos if p.get("region", "latam") == "latam"],
        "europa": [p["codigo"] for p in cubiertos if p.get("region") == "europa"],
        "utc": {p["codigo"]: p["utc"] for p in paises},
        "claves": claves,
        "nombres_pais": nombres_pais,
        "ciudades": ciudades,
        "ambiguas": ambiguas,
        "fuera_con_propio": fuera_con_propio,
        "propios_con_fuera": propios_con_fuera,
        "palabras_comunes": comunes,
        "iso2_extranjeros": {m["iso2"].lower() for m in mundo if m["iso2"] not in propios},
        "iso3": {m["iso3"]: m["iso2"] for m in mundo if m["iso2"] in propios},
        "iso3_extranjeros": {m["iso3"] for m in mundo if m["iso2"] not in propios},
        "toda_latam": sorted({normalizar.texto(x) for x in crudo["toda_latam"]}, key=len, reverse=True),
        "mundo": sorted({normalizar.texto(x) for x in crudo["todo_el_mundo"]}, key=len, reverse=True),
        "toda_europa": sorted({normalizar.texto(x) for x in crudo["toda_europa"]}, key=len, reverse=True),
        "fuera": sorted(fuera, key=len, reverse=True),
        "fuera_lugares": sorted(fuera_lugares, key=len, reverse=True),
        "subregiones": crudo.get("subregiones", []),
    }


def _paises_nombrados(t):
    """Códigos de los países de LATAM nombrados en el texto normalizado (por país, gentilicio o ciudad)."""
    claves = datos()["claves"]
    if not _nombra(t, [frase for frase, _ in claves]):  # una sola expresión compilada: casi ningún texto nombra un país
        return []
    hallados, usado = [], t
    for frase, codigo in claves:
        if normalizar.contiene_frase(usado, frase):
            if codigo not in hallados:
                hallados.append(codigo)
            usado = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", " ", usado)
    return hallados


def _pais_por_nombre(t, codigos):
    """Alguno de esos países aparece por su nombre o gentilicio (no solo por una ciudad: "Santa Ana, California")."""
    return any(_nombra(t, [normalizar.texto(x) for x in p["nombres"] + p["gentilicios"]])
               for p in datos()["paises"] if p["codigo"] in codigos)


def _nombra(t, frases):
    """¿Aparece alguna de las frases como palabras completas? Una sola expresión compilada por lista (la de lugares
    extranjeros tiene más de 1.700 frases y se consulta varias veces por vacante en cada captura)."""
    if not t or not frases:
        return False
    return _patron(tuple(frases)).search(t) is not None


@lru_cache(maxsize=256)
def _patron(frases):
    alternativas = "|".join(re.escape(f) for f in sorted(set(frases), key=len, reverse=True) if f)
    return re.compile(r"(?<![a-z0-9])(?:" + alternativas + r")(?![a-z0-9])")


def _rangos_zona(t):
    """Franjas UTC (min, max) que pide el aviso. Texto en minúsculas, sin tildes, con sus signos («utc-3»)."""
    rangos = []
    for m in _ZONA.finditer(t):
        a = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        b = int(m.group(4)) * (1 if m.group(3) == "+" else -1) if m.group(4) else None
        rangos.append((min(a, b), max(a, b)) if b is not None else (a - 2, a + 2))
    for nombre, valor in _ZONAS_US.items():
        if re.search(r"(?<![a-z])" + nombre + r"(?![a-z])", t):
            rangos.append((valor - 2, valor + 2))
    return rangos


def _por_zona_horaria(t):
    """Países de LATAM dentro de la franja horaria que pide el aviso, o None si no pide ninguna."""
    rangos = _rangos_zona(t)
    if not rangos:
        return None
    utc = datos()["utc"]
    return [c for c in datos()["codigos"] if any(lo <= utc[c] <= hi for lo, hi in rangos)]


def _restricciones(desc, titulo=False):
    """Todas las restricciones reconocidas; una frase comercial no acredita residencia. `titulo`: el texto es el
    título del aviso; ahí «(USA-based)» habla del puesto y siempre restringe."""
    d = datos()
    restricciones = []
    for m in re.finditer(r"(?=(?P<coincidencia>"+_RESTRINGE.pattern+r"))",desc):
        lugar = (m.group("lugar") or m.group("lugar2") or m.group("lugar3") or m.group("lugar4") or m.group("lugar5") or "").strip()
        coincidencia = m.group("coincidencia")
        contexto = coincidencia[:coincidencia.find(lugar)]
        if not titulo and m.group("lugar3") and m.group("marca3") == "based" and not (
                _BASADO_ANTES.search(desc[max(0, m.start() - 30):m.start()])
                or _BASADO_DESPUES.match(desc[m.start() + len(coincidencia):][:30])):
            continue  # contrato v49: describe a la empresa o a sus clientes, no dónde debe vivir la persona
        residencia = re.search(r"\b(reside|live|located|based|living|residing|candidates|applicants|candidatos|personas|residents)\b", contexto)
        conocido = _paises_nombrados(lugar) or any(_nombra(lugar,d[k]) for k in ("fuera","toda_latam","toda_europa","mundo")) or any(_nombra(lugar,r["nombres"]) for r in d["subregiones"])
        if residencia or conocido or m.group("lugar4") or m.group("lugar5"):
            restricciones.append(lugar)
    return restricciones


def _contratacion_remota(desc):
    d = datos()
    alcances = sorted(set(d["mundo"]+d["toda_latam"]+d["toda_europa"]),key=len,reverse=True)
    opciones = "|".join(re.escape(x) for x in alcances)
    patron = (r"\b(?:hiring|contratamos|open to candidates|accepting candidates)\s+(?:remotely\s+)?"
              r"(?:(?:across|in|from|en|de)\s+)?(?:all of\s+)?(?P<contratacion>"+opciones+r")\b"
              r"|\b(?:work|working|trabajar|trabaja)\s+(?:remotely\s+)?(?:from|desde)\s+(?P<trabajo>"+opciones+r")\b"
              # Contrato v49: el español de los avisos de LATAM. «Modalidad: 100% remoto | Latinoamérica», «remoto desde
              # cualquier país de Latinoamérica», «100% remoto para LATAM». «Empresa líder en Latinoamérica» no cuenta:
              # el alcance tiene que venir pegado a la palabra «remoto».
              r"|\bremot[oa]\s+(?:100\s+)?(?:(?:desde|para|en)\s+)?(?:cualquier\s+(?:pais|lugar|parte)\s+de\s+|"
              r"tod[oa]\s+)?(?P<remoto_es>"+opciones+r")\b")
    for m in re.finditer(patron,desc):
        if re.search(r"\b(?:not|no|cannot|can t|unable|except|excluding|sin|tampoco)\b",desc[max(0,m.start()-35):m.start()]):
            continue
        hallado = m.group("contratacion") or m.group("trabajo") or m.group("remoto_es")
        # Contrato v49: «work from anywhere in the US» nombra dónde; no abre el aviso a cualquier país. El alcance es
        # el lugar que sigue («anywhere in LATAM or Europe» → LATAM; «anywhere in the US» → fuera).
        if _MUNDO_ACOTADO.match(hallado + desc[m.end():][:40]):
            lugar = _TRAS_ACOTAR.sub("", desc[m.end():][:60])
            return re.split(r"\b(?:anywhere|worldwide|cualquier)\b", lugar)[0].strip()  # sin la frase siguiente
        return hallado
    return ""


# Contrato v50: la letra pequeña en español que dice desde dónde puede postular LA PERSONA («abierto a candidatos de
# Colombia y Perú», «puedes postular desde Uruguay», «vacante disponible para Colombia, Ecuador o Perú»). Solo frases
# que hablan de quién postula. Las de la empresa («presencia en 6 países», «en 2024 contratamos en México a 200
# personas», «clientes en LATAM»), las de beneficios («puedes trabajar desde España cuatro semanas al año») y las
# vagas («desde donde quieras») no empiezan así y no abren nada. Texto normalizado (sin tildes ni signos, minúsculas).
_APERTURA_ES = re.compile(
    r"\b(?:"
    r"abiert[oa]s?\s+(?:a|para)\s+(?:tod[oa]s?\s+(?:l[oa]s\s+)?)?(?:candidat[oa]s|personas|profesionales|postulantes|"
    r"aplicantes|talentos?|residentes)(?:\s+que\s+(?:residan|vivan|esten|se\s+encuentren))?\s+(?:de|en|desde)"
    r"|(?:puedes|podras|pueden|podran)\s+(?:aplicar|postular|postularte|postularse)\s+desde"
    r"|(?:aceptamos|recibimos)\s+(?:candidat[oa]s|postulantes|postulaciones|aplicaciones)\s+(?:de|desde|en)"
    r"|contratamos\s+(?:talentos?|personas|profesionales|candidat[oa]s)\s+(?:en|de|desde)"
    r"|(?:vacante|posicion|oferta|oportunidad|rol|puesto|convocatoria)\s+(?:remot[oa]\s+)?"
    r"(?:disponible|abiert[oa]|valid[oa]|habilitad[oa])\s+(?:para|en)"
    r"|paises\s+(?:donde\s+contratamos|en\s+los\s+que\s+contratamos|elegibles|habilitados)"
    r")\s+")
_ENTRE_LUGARES = re.compile(r"(?:(?:y|o|e|u|ni|tambien|como|toda|todo|todos|todas|el|la|los|las|de|del|cualquier|pais|"
                            r"paises|parte|lugar|resto|otros)\s+){0,5}")
_NEGADA = re.compile(r"\b(?:no|sin|tampoco|nunca|excepto|salvo)\b")


@lru_cache(maxsize=1)
def _lugares_de_apertura():
    """Patrón con los nombres de países de todo el mundo, las subregiones y los alcances (LATAM, Europa, todo el mundo):
    una lista que mezcla países cubiertos y de fuera («Colombia, Estados Unidos y México») se lee entera."""
    d = datos()
    nombres = {n for _, lista in d["nombres_pais"] for n in lista} | set(d["mundo"] + d["toda_latam"] + d["toda_europa"])
    nombres |= {n for r in d["subregiones"] for n in r["nombres"]} | set(mundo()["por_nombre"])
    return re.compile(r"(?:" + "|".join(re.escape(x) for x in sorted(nombres, key=len, reverse=True) if x) + r")\b")


def _apertura_nombrada(desc):
    """Los lugares que siguen a una frase de apertura en español (texto normalizado), o "". Solo la lista pegada a la
    frase: «abierto a candidatos de colombia y peru» → «colombia y peru», sin lo que venga en la oración siguiente."""
    lugar = _lugares_de_apertura()
    for m in _APERTURA_ES.finditer(desc):
        if _NEGADA.search(desc[max(0, m.start() - 35):m.start()]):
            continue
        fin = m.end()
        while True:
            # Primero el lugar tal cual («cualquier parte del mundo» es un alcance entero); si no, tras los conectores.
            hallado = lugar.match(desc, fin) or lugar.match(desc, _ENTRE_LUGARES.match(desc, fin).end())
            if not hallado:
                break
            fin = hallado.end()
            fin += len(desc[fin:]) - len(desc[fin:].lstrip())
        if fin > m.end():
            return desc[m.end():fin].strip()
    return ""


def modalidad(titulo, ubicacion, descripcion="", remoto=None):
    t = normalizar.texto(f"{titulo} {ubicacion}")
    d = normalizar.texto(descripcion)[:30000]
    if _HIBRIDO.search(t):
        return "hibrido"
    if _PRESENCIAL.search(t):
        return "presencial"
    if _HIBRIDO.search(d):
        return "hibrido"
    if re.search(r"\b(?:this (?:role|position|job) is|must work|will work|required to work|trabajo obligatorio|modalidad)\s+(?:fully |completely |100 )?(?:on ?site|onsite|in office|presencial)\b", d):
        return "presencial"
    if remoto is True or _REMOTO.search(t):
        return "remoto"
    if _remoto_en_descripcion(d):
        return "remoto"
    return "presencial" if t.strip() else "sin dato"


CONFIANZAS = ("alta", "media", "baja")
MODALIDADES = ("hibrido", "remoto", "presencial", "sin dato")  # explícitas antes que la presencial por defecto
NOTA_INCIERTA = "confirmar países: fuentes con ubicación incierta"


def lugar_del_portal(localizacion, pais, nombre_pais, remoto=False):
    """Contrato v50: la ubicación de un aviso de un portal de un solo país: «Localidad, Provincia» más el país del
    portal. En una remota, si la localidad abre otro país aun con el del portal al final («Concepción del Uruguay»), se
    quita: el aviso es del país de su portal y no debe abrir otro (desde 7.E, «Palermo» o «Florida» seguidas del país ya
    no abren Italia ni EE. UU. y se conservan). En una presencial o híbrida la
    localidad se conserva siempre: sin ciudad no le llega a nadie (v49), y ahí el país lo decide la ciudad del perfil
    («Granada, España» se quedaba en «España» por la isla de Granada)."""
    tramos = [t.strip() for t in localizacion.split(",") if t.strip()] if isinstance(localizacion, str) else []
    if not remoto:
        return ", ".join([*tramos, nombre_pais])
    for desde in range(len(tramos) + 1):
        lugar = ", ".join([*tramos[desde:], nombre_pais])
        if set(alcance("", lugar).get("paises_mundo") or []) <= {pais}:
            return lugar
    return nombre_pais


def ordenar(codigos):
    """Códigos sin repetir en el orden de `datos/paises.yaml`: el mismo conjunto siempre se guarda igual."""
    orden = {c: i for i, c in enumerate(datos()["codigos"])}
    return sorted(set(codigos), key=lambda c: (orden.get(c, len(orden)), c))


def combinar(resultados):
    """Elegibilidad de una vacante vista en varias observaciones (fuentes o enlaces), sin degradar la evidencia.

    Una observación con ubicación confirmada (confianza alta o media) no se mezcla con una incierta (baja): la incierta
    no suma países ni rebaja la confianza. Las confirmadas suman sus países; la confianza es la de la observación más
    fuerte que respalda todo el conjunto, o la más débil de las que aportan si ninguna lo respalda sola. Si todas son
    inciertas se suman y la nota solo cambia cuando difieren. El resultado no depende del orden de las observaciones."""
    resultados = [r for r in resultados if r]
    if not resultados:
        return None
    confirmados = [r for r in resultados if r["confianza"] in ("alta", "media")]
    base = confirmados or resultados
    aportan = [r for r in base if r["paises"]] or base
    union = ordenar(p for r in aportan for p in r["paises"])
    rango = lambda r: (CONFIANZAS.index(r["confianza"]), r["nota"])  # noqa: E731
    respaldo = sorted((r for r in aportan if set(r["paises"]) >= set(union)), key=rango)
    notas = sorted({r["nota"] for r in aportan})
    if not confirmados:
        confianza, nota = "baja", notas[0] if len(notas) == 1 else NOTA_INCIERTA
    elif respaldo:
        confianza, nota = respaldo[0]["confianza"], respaldo[0]["nota"]
    else:
        confianza = max((r["confianza"] for r in aportan), key=CONFIANZAS.index)
        nota = notas[0] if len(notas) == 1 else ""
    modos = {r["modalidad"] for r in resultados}
    modo = next((m for m in MODALIDADES if m in modos), sorted(modos)[0])
    zonas = [r["zona_utc"] for r in resultados if r.get("zona_utc")]
    return {"paises": union, "modalidad": modo, "confianza": confianza, "nota": nota,
            # Contrato v23: todos los países nombrados (cubiertos o no), alcance mundial y franja horaria pedida.
            "paises_mundo": sorted({c for r in resultados for c in r.get("paises_mundo") or []}),
            "alcance_mundial": any(r.get("alcance_mundial") for r in resultados),
            "zona_utc": [min(z[0] for z in zonas), max(z[1] for z in zonas)] if zonas else None}


# Contrato v13: códigos al final de la ubicación. LinkedIn y los portales escriben «Bucharest, ro» o «Barcelona, es»
# (país ISO en minúsculas) y «San Jose, CA» (estado de EE. UU. en mayúsculas). Antes quedaban «por confirmar».
_ESTADOS_EEUU = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC
    ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
_CODIGO_FINAL = re.compile(r"(?:,|\s[-–]|^)\s*([A-Za-z]{2}|[A-Z]{3})\s*$")
_SOLO_CODIGOS = re.compile(r"^\s*([A-Za-z]{2}|[A-Z]{3})(?:\s+\1)*\s*$")


@lru_cache(maxsize=1)
def _crudo_lugares():
    import gzip
    import json
    try:
        with gzip.open(RUTA_LUGARES, "rt", encoding="utf-8") as f:
            crudo = json.load(f)
    except (OSError, ValueError):
        return {}
    extranjeros = crudo.get("extranjeros") or {}
    if isinstance(extranjeros, list):  # formato v19: sin país
        extranjeros = dict.fromkeys(extranjeros, "")
    return {"cubiertos": crudo.get("cubiertos") or {}, "extranjeros": extranjeros,
            "coordenadas": crudo.get("coordenadas") or {}}


def _lugares_mundo():
    crudo = _crudo_lugares()
    return crudo.get("cubiertos", {}), crudo.get("extranjeros", {})


def _pais_de_nombre(nombre):
    """Contrato v38: país ISO de un nombre de lugar exacto (ya normalizado): alias, lista curada de paises.yaml si
    apunta a un solo país, o GeoNames (cubierto o el país dominante de una ciudad de fuera). "" si no se sabe."""
    if not nombre:
        return ""
    if nombre in alias_lugares():
        return alias_lugares()[nombre]
    curados = datos()["ciudades"].get(nombre) or []
    if curados:
        return curados[0] if len(curados) == 1 else ""
    cubiertos, extranjeros = _lugares_mundo()
    return cubiertos.get(nombre) or extranjeros.get(nombre) or ""


_POSTAL = re.compile(r"(?:\s|^)(?:\d{4,6}(?:-\d{3,4})?|[a-z]\d[a-z] ?\d[a-z]\d|[a-z]{1,2}\d[a-z\d]? ?\d[a-z]{2})$")


def _candidatos_tramo(tramo):
    """Formas de un tramo de ubicación para buscarlo como lugar: tal cual, sin código postal («new york ny 10001»),
    sin la sigla final del estado o provincia («harrisburg pa», «melbourne vic»)."""
    t = normalizar.texto(_REMOTO.sub(" ", _HIBRIDO.sub(" ", _PRESENCIAL.sub(" ", normalizar.texto(tramo)))))
    t = re.sub(r"^(?:area metropolitana de |region metropolitana de |greater |remote in |based in |in )", "", t)
    t = re.sub(r" (?:y alrededores|and surrounding areas|metropolitan area|area metropolitana|area)$", "", t)
    sin_postal = _POSTAL.sub("", t).strip()
    vistos = []
    for c in (t, sin_postal, re.sub(r" [a-z]{2,3}$", "", sin_postal)):
        if c and c not in vistos:
            vistos.append(c)
    return vistos


def _tramos(ubicacion):
    return re.split(r"[,;|/()]| - | – |·", ubicacion or "")


RADIO_CIUDAD_KM = 50  # contrato v38: un lugar a esta distancia o menos cuenta como la misma ciudad (alrededores)


def coordenadas(nombre, codigos=(), estado=""):
    """Contrato v38: (lat, lon) de la ciudad de 15.000 habitantes o más con ese nombre, la más poblada de los países
    dados (y del estado de EE. UU., si se da). None si no está o si, sin países, el nombre es de varios."""
    lugares = _crudo_lugares().get("coordenadas", {})
    for candidato in _candidatos_tramo(nombre):
        candidato = alias_ciudad(candidato)
        filas = lugares.get(candidato)
        if not filas:
            continue
        if codigos:
            filas = [f for f in filas if f[0] in codigos]
        elif len({f[0] for f in filas}) > 1:
            pais = _pais_de_nombre(candidato)
            filas = [f for f in filas if f[0] == pais] if pais else []
        if estado:
            filas = [f for f in filas if f[1] == estado] or filas
        if filas:
            return filas[0][2], filas[0][3]
    return None


def cerca(lugar, otro, codigos=(), estado=""):
    """Contrato v38: True si dos ciudades quedan a RADIO_CIUDAD_KM o menos («Brooklyn» y «New York», «Chía» y
    «Bogotá»). Sin coordenadas de alguna de las dos, False: nunca se adivina."""
    from math import asin, cos, radians, sin, sqrt
    a, b = coordenadas(lugar, codigos, estado), coordenadas(otro, codigos)
    if not a or not b:
        return False
    la1, lo1, la2, lo2 = map(radians, (*a, *b))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h)) <= RADIO_CIUDAD_KM


def estado_eeuu(ubicacion):
    """La sigla de estado de EE. UU. tras la ciudad («Brooklyn, NY» → NY), o ""."""
    m = _SIGLA.search(ubicacion or "")
    return m.group(1) if m and m.group(1) in _ESTADOS_EEUU else ""


def pais_de_lugar(ubicacion):
    """Contrato v38: el país (cualquiera, ISO2) de la ciudad o región que nombra la ubicación, o None. Por tramos: un
    tramo de fuera sin país conocido no cuenta; dos tramos con países distintos no deciden."""
    hallados = set()
    for tramo in _tramos(ubicacion):
        for candidato in _candidatos_tramo(tramo):
            pais = _pais_de_nombre(candidato)
            if pais:
                hallados.add(pais)
                break
    return next(iter(hallados)) if len(hallados) == 1 else None


_GENERICAS_LUGAR = {"", "na", "n a", "job", "location", "locations", "multiple locations", "various locations",
                    "varias ubicaciones", "anywhere", "global", "worldwide", "open to", "open"}


def lugar_conocido(ubicacion):
    """Contrato v19, último recurso: el país de un municipio o ciudad de GeoNames que la ubicación nombra por sí sola
    («Inca» → ES, «Harrisburg, PA» → extranjero). Devuelve un código cubierto, "fuera" o None. Solo la ubicación (nunca
    la descripción), por tramos separados por comas; un tramo ambiguo no cuenta y tramos contradictorios no deciden."""
    cubiertos, extranjeros = _lugares_mundo()
    if not cubiertos and not extranjeros:
        return None
    resultados = set()
    for tramo in _tramos(ubicacion):
        for candidato in _candidatos_tramo(tramo):  # «harrisburg pa» → «harrisburg»; v38: sin código postal
            alias = alias_lugares().get(candidato)
            if alias:  # contrato v38: «NYC», «GTA», «CDMX»
                resultados.add(alias if alias in datos()["codigos"] else "fuera")
                break
            if candidato in cubiertos:
                resultados.add(cubiertos[candidato])
                break
            if candidato in extranjeros:
                resultados.add("fuera")
                break
    return next(iter(resultados)) if len(resultados) == 1 else None


def _sin_repeticion(texto):
    """«Buenos Aires Buenos Aires» → «Buenos Aires»: algunas fuentes repiten la ubicación pegada."""
    anterior = None
    while anterior != texto:
        anterior, texto = texto, re.sub(r"\b(\w[\w ]*?\w)(?:\s+\1\b)+", r"\1", texto)
    return texto


def _expandir_codigos(ubicacion):
    """Cambia un código de país por su nombre (cubierto) o por «pais extranjero».

    Vale para la ubicación entera («MX», «MX MX», «Bo») y para el final de cada tramo, tras una coma o un guion
    («Bucharest, ro», «Remote - MX», «Mumbai, IND»). En mayúsculas tras una ciudad, un código que también es estado de
    EE. UU. (CO, AR, PA) solo se lee como país si la ciudad es de ese país; si no, se deja «por confirmar»."""
    d = datos()
    nombres = {p["codigo"]: p["nombre"] for p in d["paises"]}

    def por_codigo(codigo, ciudad):
        if len(codigo) == 3:
            if codigo in d["iso3"]:
                return nombres[d["iso3"][codigo]]
            return "pais extranjero" if codigo in d["iso3_extranjeros"] else None
        mayus = codigo.upper()
        if ciudad and codigo.isupper() and mayus in _ESTADOS_EEUU:
            if mayus in _COMUNIDADES_ES and "ES" in nombres and _pais_de_nombre(ciudad) == "ES":
                return nombres["ES"]  # contrato v38: «Sabadell, CT» es Cataluña, «Vigo, GA» es Galicia
            if mayus in nombres:
                es_de = mayus in d["ciudades"].get(ciudad, []) or _pais_por_nombre(ciudad, [mayus])
                return nombres[mayus] if es_de else None
            return "pais extranjero"
        if mayus in nombres:
            return nombres[mayus]
        return "pais extranjero" if codigo.lower() in d["iso2_extranjeros"] | {"uk"} else None

    partes = []
    for parte in re.split(r"([;|])", str(ubicacion or "")):
        solo = _SOLO_CODIGOS.match(parte)
        m = None if solo else _CODIGO_FINAL.search(parte)
        if solo:
            nombre = por_codigo(solo.group(1), "")
            parte = nombre or parte
        elif m:
            ciudad = normalizar.texto(parte[:m.start()])
            nombre = por_codigo(m.group(1), ciudad)
            if nombre:
                parte = parte[:m.start()] + ", " + nombre
        partes.append(parte)
    return "".join(partes)


def _ciudad_dentro(texto, ciudades):
    """Contrato v14: una ciudad conocida dentro de un texto más largo («Área metropolitana de Bogotá D.C.»,
    «Las Rozas de Madrid»). Solo si todas las ciudades halladas son de un único país cubierto."""
    ambiguas = datos()["ambiguas"] | _CIUDADES_AMBIGUAS
    posibles = tuple(f for f in ciudades if f not in ambiguas and (" " in f or len(f) >= 6))
    if not _nombra(texto, posibles):  # una sola expresión compilada: casi ningún texto nombra una ciudad (v19)
        return []
    frases = [f for f in posibles if normalizar.contiene_frase(texto, f)]
    frases = [f for f in frases if not any(f != otra and normalizar.contiene_frase(otra, f) for otra in frases)]
    hallados = {c for f in frases for c in ciudades[f]}
    return sorted(hallados) if len(hallados) == 1 else []


# Nombres de ciudad que existen en varios países (o son también nombre de persona): nunca deciden solos dentro de un
# texto largo. Siguen valiendo cuando la ubicación es exactamente esa ciudad o trae el país.
_CIUDADES_AMBIGUAS = {"santiago", "cordoba", "valencia", "granada", "merida", "leon", "victoria", "trujillo", "colon",
                      "concepcion", "guadalajara", "cartagena", "san jose", "santa cruz", "san juan", "la paz",
                      "san pedro", "santa ana", "salamanca", "toledo", "rosario", "sucre", "santa fe", "providencia",
                      "san miguel", "san isidro", "san francisco", "santa marta", "barcelona", "palma"}


# Contrato v17: reglas de ubicación del operador (exactas) y aprendidas por código (frases). Las carga la búsqueda en
# modo panel desde Supabase (nunca desde archivos públicos). Solo resuelven lo que la tabla oficial deja «por
# confirmar»: nunca cambian un país ya reconocido.
_REGLAS = {"exactas": {}, "frases": []}
USOS = Counter()


def clave(texto):
    """Ubicación normalizada, igual en la bandeja, las reglas y la búsqueda."""
    return _sin_repeticion(normalizar.texto(texto or ""))[:300]


def cargar_reglas(reglas=()):
    """Activa las reglas (filas de `panel_reglas_ubicacion`); sin argumento, las retira."""
    exactas, frases = {}, []
    for r in reglas or []:
        if not r.get("activa", True) or not isinstance(r.get("resultado"), dict):
            continue
        texto = clave(r.get("texto"))
        if len(texto) < 2:
            continue
        if r.get("origen") == "aprendida":
            frases.append((texto, r["resultado"]))
        else:
            exactas[texto] = r["resultado"]
    _REGLAS["exactas"], _REGLAS["frases"] = exactas, sorted(frases, key=lambda x: -len(x[0]))
    USOS.clear()


def elegibles(titulo, ubicacion, descripcion="", remoto=None):
    """Países desde los que se puede aplicar, con modalidad, confianza y una nota corta (y, desde v23, `paises_mundo`,
    `alcance_mundial` y `zona_utc`)."""
    ubicacion = corregir_ubicacion(ubicacion)
    r = {**_elegibles(titulo, ubicacion, descripcion, remoto), **alcance(titulo, ubicacion, descripcion)}
    restriccion = r.pop("_restriccion")
    if restriccion and r["modalidad"] == "remoto":
        # Contrato v49: en una remota con residencia obligatoria solo cuentan los países de esa frase. Antes se
        # sumaba el de la ubicación («Colombia» + «must reside in Argentina» llegaba a quien vive en Colombia).
        r["paises_mundo"] = restriccion
    if r["confianza"] != "baja" or not (_REGLAS["exactas"] or _REGLAS["frases"]):
        return r
    texto = clave(ubicacion)
    resultado, origen = _REGLAS["exactas"].get(texto), "operador"
    if resultado is None:
        hallados = [(f, res) for f, res in _REGLAS["frases"] if normalizar.contiene_frase(texto, f)]
        if hallados and all(res == hallados[0][1] for _, res in hallados):  # si dos reglas se contradicen, no decide
            (texto, resultado), origen = hallados[0], "aprendida"
    if resultado is None:
        return r
    USOS[texto] += 1
    if resultado.get("paises"):
        cubiertos = [c for c in resultado["paises"] if c in datos()["codigos"]]
        if cubiertos:
            return {**r, "paises": cubiertos, "confianza": "alta",
                    "nota": "regla del operador" if origen == "operador" else "regla aprendida"}
        return r
    return {**r, "paises": [], "confianza": "alta", "nota": "regla: solo otro país"}


@lru_cache(maxsize=1)
def mundo():
    """Contrato v23: la tabla mundial (datos/paises_mundo.yaml) para el panel y para reconocer países de cualquier parte.
    `lista`: [{codigo, nombre}] por nombre; `nombres`: (nombre normalizado, ISO2) del más largo al más corto, con las
    subdivisiones de los extranjeros frecuentes (estados de EE. UU.…) salvo las que comparten nombre con un país."""
    filas = yaml.safe_load(RUTA_MUNDO.read_text(encoding="utf-8"))["paises"] if RUTA_MUNDO.exists() else []
    lista = sorted(({"codigo": m["iso2"], "nombre": m.get("nombre") or m["iso2"],
                     "nombre_en": m.get("nombre_en") or m.get("nombre") or m["iso2"]} for m in filas),
                   key=lambda x: normalizar.sin_tildes(x["nombre"]).lower())
    paises_n = {(n, m["iso2"]) for m in filas for n in m["nombres"]}
    de_pais = {n for n, _ in paises_n}
    propios = {p["codigo"] for p in datos()["paises"]}
    subs = {(n, m["iso2"]) for m in filas if m["iso2"] not in propios for n in m.get("subdivisiones", [])
            if n not in de_pais and len(n) > 3}
    nombres = sorted(paises_n | subs, key=lambda x: -len(x[0]))
    por_nombre = {}
    for n, c in nombres:
        por_nombre.setdefault(n, set()).add(c)
    # Una sola expresión con las frases más largas primero: en cada posición gana la más larga.
    patron = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in por_nombre) + r")(?![a-z0-9])") \
        if por_nombre else None
    solo_paises = sorted({n for n, _ in paises_n}, key=len, reverse=True)
    patron_paises = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in solo_paises) + r")(?![a-z0-9])") \
        if solo_paises else None
    # Contrato v38: nombres que son país y también región de otro país («Georgia»: país y estado de EE. UU.).
    homonimos = {}
    for m in filas:
        for n in m.get("subdivisiones", []):
            if n in de_pais and m["iso2"] not in {c for x, c in paises_n if x == n}:
                homonimos.setdefault(n, set()).add(m["iso2"])
    return {"lista": lista, "codigos": {m["iso2"] for m in filas}, "por_nombre": por_nombre, "patron": patron,
            "patron_paises": patron_paises, "pais_de": {n: c for n, c in paises_n}, "homonimos": homonimos}


def paises_por_nombre_entero(texto):
    """Contrato v38: solo los países nombrados por su nombre («Spain», «Canada»), sin ciudades ni regiones."""
    m = mundo()
    if not texto or m["patron_paises"] is None:
        return set()
    return {m["pais_de"][h.group(1)] for h in m["patron_paises"].finditer(texto)}


def paises_en_texto(texto):
    """ISO2 de los países (de cualquier parte) que nombra un texto normalizado. La frase más larga gana («New Mexico»
    es EE. UU., no México)."""
    m = mundo()
    if not texto or m["patron"] is None:
        return set()
    return {c for hallado in m["patron"].finditer(texto) for c in m["por_nombre"][hallado.group(1)]}


# Contrato v38: siglas de provincias de Canadá y estados de Australia tras la ciudad («Toronto, ON», «Sydney NSW»).
_PROVINCIAS_CA = set("AB BC MB NB NL NS NT NU ON PE QC SK YT".split())
_ESTADOS_AU = set("NSW VIC QLD TAS ACT SA WA NT".split())
_COMUNIDADES_ES = set("AN AR AS CB CE CL CM CN CT EX GA IB MC MD ML NC PV RI VC".split())  # ISO 3166-2:ES
_SIGLA = re.compile(r"(?:,|\s)\s*([A-Z]{2,3})(?=\s*(?:\d{4,5}(?:-\d{4})?|[A-Z]\d[A-Z] ?\d[A-Z]\d)?\s*(?:,|\(|$))")


def _paises_por_sigla(ubicacion, nombrados=()):
    """Contrato v32/v38: el país que dice una sigla de estado o provincia tras la ciudad, admitiendo código postal
    («New York, NY 10001», «Toronto, ON M5V 3L9»). Si la sigla también es código de país («Berlin, DE», «Toronto, CA»,
    «Amsterdam, NL»), decide la ciudad: si la ciudad es de ese país, es el país; si no, es el estado de EE. UU.
    («London, KY»: KY también es Islas Caimán). Una sigla de estado no suma EE. UU. si la ubicación nombra otro país
    («Barcelona, CT, Spain»: CT es Cataluña). Tras una ciudad de un país cubierto solo cuenta una sigla que no sea
    también código de país ni de comunidad de España («Panama City, FL»). AR, CO y PA siguen la regla de v15."""
    texto = ubicacion or ""
    codigos_iso = mundo()["codigos"]
    ciudad = pais_de_lugar(_tramos(texto)[0]) if _tramos(texto) else None
    hallados = set()
    for m in _SIGLA.finditer(texto):
        sigla = m.group(1)
        if m.start() == 0 or not texto[:m.start()].strip(" ,-"):
            continue  # la sigla sola no es una ciudad con su estado
        if sigla in codigos_iso and ciudad == sigla:
            hallados.add(sigla)
        elif sigla in _ESTADOS_AU and ciudad == "AU":
            hallados.add("AU")
        elif sigla in _PROVINCIAS_CA and (ciudad == "CA" or (sigla not in codigos_iso and sigla not in _ESTADOS_AU)):
            hallados.add("CA")
        elif sigla in {"NSW", "VIC", "QLD", "TAS", "ACT"}:
            hallados.add("AU")
        elif sigla in _ESTADOS_EEUU and sigla not in {"AR", "CO", "PA"} and not (set(nombrados) - {"US"}) and (
                ciudad not in datos()["codigos"] or (sigla not in codigos_iso and
                                                     not (ciudad == "ES" and sigla in _COMUNIDADES_ES))):
            # «nombrados»: países escritos con su nombre. «Toledo, OH» y «Panama City, FL» son de EE. UU.; «Vigo, GA»
            # es Galicia.
            hallados.add("US")
    return hallados


def _estados_de_otro_pais(ubicacion):
    """7.E (27 nov): en «Califórnia, Paraná, Brasil» el país escrito al final manda: los países que solo suman los
    nombres de estados o regiones de otro país en los tramos de antes («California» → EE. UU.) se quitan.
    «Birmingham, Alabama, United States» no es Reino Unido. Solo si la ubicación es un lugar: un único país escrito con
    su nombre y sin «;», «|» ni «/», que separan varios. La modalidad al final («(Remoto)») no cuenta como tramo."""
    if re.search(r"[;|/]", ubicacion or ""):
        return set()
    lugares = [c[0] for t in _tramos(ubicacion) if (c := _candidatos_tramo(t))]
    pais_final = mundo()["pais_de"].get(lugares[-1]) if len(lugares) > 1 else None
    if not pais_final or paises_por_nombre_entero(" , ".join(lugares)) != {pais_final}:
        return set()
    return {c for t in lugares[:-1] for c in paises_en_texto(t) - paises_por_nombre_entero(t)} - {pais_final}


def alcance(titulo, ubicacion, descripcion=""):
    """Contrato v23: países que el aviso nombra como lugar o como alcance permitido (cubiertos o no), si es remoto para
    cualquier lugar y la franja horaria que pide. Sin IA: tabla ISO y las mismas frases de residencia del motor."""
    d = datos()
    ubicacion_n = normalizar.texto(_expandir_codigos(ubicacion))
    titulo_n = normalizar.texto(titulo)
    # «Baja California» (México) no es California (EE. UU.): los lugares propios que contienen uno extranjero se quitan.
    sin_propios = ubicacion_n
    for frase in d["propios_con_fuera"]:
        sin_propios = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", " ", sin_propios)
    # Contrato v38: un tramo que es entero una ciudad de fuera conocida dice su país, aunque contenga el nombre de otro
    # («Jersey City» es EE. UU., no Jersey). Un tramo que es exactamente un país («Georgia») sigue siendo el país.
    de_ciudades = set()
    for tramo in _tramos(ubicacion):
        t = normalizar.texto(tramo)
        pais = "" if not t or t in mundo()["pais_de"] else pais_de_lugar(tramo)
        if pais and pais not in d["codigos"] and paises_en_texto(t) - {pais}:
            de_ciudades.add(pais)
            sin_propios = re.sub(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", " ", sin_propios)
            ubicacion_n = re.sub(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", " ", ubicacion_n)
    hallados = paises_en_texto(sin_propios) | (paises_en_texto(ubicacion_n) & set(d["reconocidos"])) | de_ciudades
    tramos = [normalizar.texto(t) for t in _tramos(ubicacion)]
    ciudad = pais_de_lugar(_tramos(ubicacion)[0]) if tramos and tramos[0] else None
    for t in tramos[1:]:  # «Atlanta, Georgia»: la ciudad es de EE. UU., así que Georgia es el estado
        if ciudad and ciudad in mundo()["homonimos"].get(t, ()):
            hallados = (hallados - {mundo()["pais_de"][t]}) | {ciudad}
    hallados -= _estados_de_otro_pais(ubicacion)
    # Contrato v32: LinkedIn muestra muchas de EE. UU. como «Chicago, IL», «Austin, TX» o «Remote, US». Sin esto no
    # tenían país y se descartaban al entrar, aunque un perfil viva en EE. UU. AR, CO y PA también son países cubiertos:
    # esos tres siguen por la regla de v15.
    resto = (ubicacion or "").split(",", 1)[1] if "," in (ubicacion or "") else ""
    siglas = _paises_por_sigla(ubicacion, paises_por_nombre_entero(normalizar.texto(resto)))
    if siglas:  # v38: la sigla del estado manda sobre la ciudad homónima («Paris, TX» es EE. UU., no Francia)
        hallados = siglas | paises_en_texto(normalizar.texto(_expandir_codigos(resto)))
    # Contrato v38: también «US-Remote», «Remote/USA», «US | Canada».
    if re.search(r"(?:^|[,\s(/|\-])(?:US|USA|U\.S\.A?\.?)(?:$|[,\s)/|\-])", ubicacion or ""):
        hallados.add("US")
    if re.search(r"\b(?:north america|norteamerica|america del norte)\b", ubicacion_n):
        hallados |= {"US", "CA"}  # v38: México solo si el aviso lo nombra
    if not hallados:  # contrato v38: la ciudad dice el país («Chicago» → US, «Toronto» → CA, «Tokio» → JP)
        por_lugar = pais_de_lugar(ubicacion)
        if por_lugar and por_lugar not in d["codigos"]:  # los países cubiertos siguen con su tabla curada
            hallados.add(por_lugar)
    metro = area_metropolitana(_REMOTO.sub(" ", _HIBRIDO.sub(" ", _PRESENCIAL.sub(" ", ubicacion_n))))
    if metro:  # contrato v32: «Granada y alrededores» es España, no Granada (el país del Caribe)
        hallados = {metro}
    remoto_en = re.search(r"\bremote\s+(?:only\s+)?(?:in|from|within)\s+([a-z /.+]{2,80})", titulo_n)
    frases = _restricciones(normalizar.texto(descripcion)[:30000]) + _restricciones(titulo_n, titulo=True) + \
        ([remoto_en.group(1)] if remoto_en else [])
    restriccion = set()  # contrato v49: los países de las frases de residencia, aparte de los de la ubicación
    for frase in frases:
        restriccion |= paises_en_texto(frase)
        if re.match(r"(us|usa|u s)\b", frase):
            restriccion.add("US")
        if re.match(r"uk\b", frase):
            restriccion.add("GB")
    hallados |= restriccion
    # Contrato v49: «Anywhere in France, Belgium, Spain» nombra dónde; no es para cualquier país.
    mundial = (_nombra(ubicacion_n, d["mundo"]) and not _MUNDO_ACOTADO.search(ubicacion_n)) or \
        bool(_REMOTO.search(titulo_n) and _nombra(titulo_n, d["mundo"]) and not _MUNDO_ACOTADO.search(titulo_n))
    rangos = _rangos_zona(normalizar.sin_tildes(f"{ubicacion} {titulo} {descripcion[:6000]}").lower())
    return {"paises_mundo": sorted(hallados), "alcance_mundial": bool(mundial), "_restriccion": sorted(restriccion),
            "zona_utc": [min(a for a, _ in rangos), max(b for _, b in rangos)] if rangos else None}


def _elegibles(titulo, ubicacion, descripcion="", remoto=None):
    """Lo que dicen la ubicación, el título y la descripción con la tabla oficial (sin reglas)."""
    d = datos()
    todos, latam, europa = d["codigos"], d["latam"], d["europa"]
    ubicacion_original = ubicacion or ""
    ubicacion = _expandir_codigos(ubicacion)
    lugar = normalizar.texto(f"{ubicacion} {titulo}")
    ambito = normalizar.texto(ubicacion) or lugar
    desc = normalizar.texto(descripcion)[:30000]
    mod = modalidad(titulo, ubicacion, descripcion, remoto)
    # El título no puede convertir una oficina de otro país en una ubicación permitida.
    geografia = _sin_repeticion(normalizar.texto(ubicacion))
    sin_homonimos = geografia
    for frase in d["fuera_con_propio"]:  # «New Mexico» no es México
        sin_homonimos = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", " ", sin_homonimos)
    siglas = _paises_por_sigla(ubicacion_original)
    if siglas and not siglas & set(todos) and "," in ubicacion_original:
        # Contrato v38: «Panama City, FL» es Florida. La sigla dice un país de fuera: el nombre de país que va dentro
        # del nombre de la ciudad no cuenta.
        primera = normalizar.texto(ubicacion_original.split(",", 1)[0])
        sin_homonimos = re.sub(r"(?<![a-z0-9])" + re.escape(primera) + r"(?![a-z0-9])", " ", sin_homonimos)
    nombres_pais = [codigo for codigo,nombres in d["nombres_pais"] if _nombra(sin_homonimos,nombres)]
    ciudad_sola = normalizar.texto(_REMOTO.sub(" ",_HIBRIDO.sub(" ",_PRESENCIAL.sub(" ",geografia))))
    ciudad_sola = re.sub(r"^(?:area metropolitana de |region metropolitana de |greater )", "", ciudad_sola)
    ciudad_sola = re.sub(r" (?:y alrededores|and surrounding areas|metropolitan area|area)$", "", ciudad_sola)
    ciudades = d["ciudades"].get(ciudad_sola,[])
    # Contrato v32: «Roma y alrededores», «Greater Madrid Area»: el área de la ciudad grande, aunque el nombre exista en
    # otros países. Sin el sufijo, un nombre ambiguo sigue sin decidir.
    metro = "" if nombres_pais else area_metropolitana(_REMOTO.sub(" ", _HIBRIDO.sub(" ", _PRESENCIAL.sub(" ", geografia))))
    if metro and metro in d["reconocidos"]:  # v38: Brasil también («Recife y alrededores»: país sin cobertura)
        ciudades = [metro]
    if not nombres_pais and not ciudades and not _nombra(ciudad_sola, d["fuera_lugares"]):
        ciudades = _ciudad_dentro(ciudad_sola, d["ciudades"])
    nombrados = nombres_pais or ciudades
    es_latam = _nombra(ambito, d["toda_latam"])
    es_mundo = _nombra(ambito, d["mundo"]) and not _MUNDO_ACOTADO.search(ambito)  # v49: «anywhere in <lugar>»
    es_europa = _nombra(ambito, d["toda_europa"])
    ambito_sin_propios = ambito
    for frase in d["propios_con_fuera"]:
        ambito_sin_propios = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", " ", ambito_sin_propios)
    fuera = _nombra(ambito_sin_propios, d["fuera_lugares"]) or bool(metro and metro not in d["reconocidos"])
    if not nombrados and not fuera and not es_latam and not es_mundo and not es_europa:
        por_lugar = lugar_conocido(ubicacion)  # contrato v19: municipios y ciudades del mundo, solo si nada más decidió
        if por_lugar == "fuera":
            fuera = True
        elif por_lugar:
            ciudades = nombrados = [por_lugar]
    if not nombrados and not fuera and not es_latam and not es_mundo and not es_europa and \
            ciudad_sola in _GENERICAS_LUGAR:
        # Ubicación sin lugar («Remote job», «N/A»): la región del título vale («Latam | Code Tutor», «CSM - EMEA»).
        titulo_n = normalizar.texto(titulo)
        es_latam = _nombra(titulo_n, d["toda_latam"])
        es_europa = _nombra(titulo_n, d["toda_europa"])
        if es_latam or es_europa:
            ambito = f"{ambito} {titulo_n}"
    def subregion(texto):
        # Contrato v18: todas las subregiones nombradas («Sudamérica, Centroamérica o México»), no solo la primera.
        hallados = [c for r in d["subregiones"] if _nombra(texto, r["nombres"]) for c in r["paises"]]
        return ordenar(hallados) if hallados else None

    def r(paises, confianza, nota):
        # Contrato v12: un país reconocido pero sin cobertura (Brasil) nunca queda como país desde el que se aplica.
        cubiertos = [c for c in paises if c in todos]
        if paises and not cubiertos and not nota:
            nota = "país fuera de la cobertura"
        return {"paises": cubiertos, "modalidad": mod, "confianza": confianza, "nota": nota}

    # Residencia explícita: también restringe ofertas presenciales o híbridas.
    titulo_normalizado = normalizar.texto(titulo)
    remoto_en = re.search(r"\bremote\s+(?:only\s+)?(?:in|from|within)\s+([a-z /.+]{2,80})", titulo_normalizado)
    restricciones = _restricciones(desc) + _restricciones(titulo_normalizado, titulo=True)
    if remoto_en:
        restricciones.append(remoto_en.group(1))
    def interpretar(restringe):
        r_paises = _paises_nombrados(restringe)
        if r_paises:
            region = subregion(restringe)  # «Centroamérica, Chile o México»: la región más los países
            return ordenar(r_paises + region) if region else r_paises
        # «Authorized to work in the country»: el país es el del propio aviso, si la ubicación lo nombra.
        if nombrados and re.match(r"(?:and |y )?(?:authorized to work in |autorizad[oa] para trabajar en )?"
                                  r"(?:(?:the|this|that|el|este|dicho) )?(?:country|pais)\b", restringe):
            return nombrados
        region = subregion(restringe)
        if region:
            return region
        if _nombra(restringe, d["toda_latam"]):
            return latam
        if _nombra(restringe, d["mundo"]):
            return todos
        if _nombra(restringe, d["toda_europa"]):
            return europa
        if _nombra(restringe, d["fuera"]) or re.match(r"(us|usa|u\.s|uk)\b", restringe):
            return []
        return None
    limites = [interpretar(texto) for texto in restricciones if texto]
    if any(valor is None for valor in limites):
        # Contrato v14: una frase de residencia solo puede restringir más. Si la ubicación ya es solo extranjera
        # (o solo de un país sin cobertura, como Brasil), no se vuelve «por confirmar» por no entender la frase.
        if not es_latam and not es_mundo:
            if nombrados and not any(c in todos for c in nombrados):
                return r(nombrados, "alta", "")
            if fuera and not nombres_pais and not ciudades:
                return r([], "alta", "fuera de LATAM y España")
        return r(todos, "baja", "restricción de residencia sin confirmar")
    if mod != "remoto":
        explicita = _PRESENCIAL.search(f"{lugar} {desc}") or _HIBRIDO.search(f"{lugar} {desc}")
        if not nombrados and not fuera and not explicita:
            # Contrato v19: «Latin America» o «Sudamérica» como ubicación, sin decir presencial ni híbrida, es una
            # región. Una presencial o híbrida sigue exigiendo un lugar concreto (contrato v8).
            region = subregion(ambito)
            if region or es_latam:
                return r(region or latam, "alta", "región como ubicación")
        if nombrados and not (fuera and not nombres_pais):
            permitidos = set(nombrados).intersection(*(set(valor) for valor in limites))
            return r([c for c in nombrados if c in permitidos], "alta", "" if permitidos else "fuera de LATAM y España")
        if fuera or es_europa:
            return r([], "alta", "fuera de LATAM y España")
        return r(todos, "baja", "confirmar ubicación")

    if limites:
        permitidos = set(todos).intersection(*(set(valor) for valor in limites))
        return r([c for c in todos if c in permitidos], "alta",
                 "restricción explícita de residencia" if permitidos else "remoto fuera de LATAM y España")
    contratacion = _contratacion_remota(desc)
    alcance_contratacion = interpretar(contratacion) if contratacion else None
    if contratacion and alcance_contratacion is None and paises_en_texto(contratacion) - set(todos):
        alcance_contratacion = []  # «work from anywhere in India»: solo nombra un país de fuera
    if alcance_contratacion is not None:  # None: nombra un lugar que no se reconoce; deciden las reglas de abajo
        return r(alcance_contratacion, "alta", "contratación remota explícita")
    # Contrato v50: la letra pequeña en español que nombra desde dónde se puede postular SUMA esos países a los del
    # aviso («Remoto, Chile» + «abierto a candidatos de Colombia y Perú» → Chile, Colombia y Perú). Solo cuando la
    # ubicación nombra un país concreto: si ya es una región, LATAM o no dice país, deciden las reglas de abajo (una
    # frase así nunca recorta lo que el aviso ya abría).
    if nombrados and not (es_latam or es_mundo or es_europa or fuera or subregion(ambito)):
        apertura = _apertura_nombrada(desc)
        sumados = set(_paises_nombrados(apertura)) | set(subregion(apertura) or []) if apertura else set()
        if apertura and _nombra(apertura, d["toda_latam"]):
            sumados |= set(latam)
        if apertura and _nombra(apertura, d["mundo"]):
            sumados |= set(todos)
        if sumados - set(nombrados):
            return r(ordenar(list(sumados) + [c for c in nombrados if c in todos]), "alta", NOTA_APERTURA)
    if es_mundo or (_REMOTO.search(titulo_normalizado) and _nombra(titulo_normalizado,d["mundo"])
                    and not _MUNDO_ACOTADO.search(titulo_normalizado)):
        return r(todos, "alta", "")
    region = subregion(ambito)
    if region:
        return r(ordenar(region + nombrados), "alta", "restricción regional")
    if es_latam:
        return r(sorted(set(latam) | (set(europa) & set(nombrados))), "alta", "")
    if nombrados:
        return r(nombrados, "media" if len(nombrados) == 1 else "alta", "")
    if fuera:
        return r([], "alta", "remoto fuera de LATAM y España")
    if es_europa:
        return r(europa, "alta", "remoto para Europa")
    zona = _por_zona_horaria(normalizar.sin_tildes(f"{ubicacion} {titulo} {descripcion[:6000]}").lower())
    if zona is not None:
        return r(zona, "baja", "por zona horaria")
    return r(todos, "baja", "remoto: confirmar región")
