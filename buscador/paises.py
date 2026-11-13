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

_REMOTO = re.compile(r"\b(remote|remoto|remota|remotely|teletrabajo|home ?office|work from home|wfh|trabajo a distancia|"
                     r"100% remoto|distributed|fully distributed|anywhere|desde casa|trabajo desde casa|remote work)\b")
_REMOTO_DESC = re.compile(r"\b(fully remote|100% remote|100% remoto|trabajo remoto|remote[- ]first|remote position|"
                          r"remote role|remote job|this is a remote|posicion remota|modalidad remota|totalmente remoto|"
                          r"trabajo 100% remoto|home office)\b")
_HIBRIDO = re.compile(r"\b(hybrid|hibrido|hibrida|semipresencial|semi presencial)\b")
_PRESENCIAL = re.compile(r"\b(on ?site|onsite|presencial|in office|in-office)\b")
# Restricciones de residencia en la descripción. Se comparan contra el texto normalizado (sin tildes, minúsculas).
_RESTRINGE = re.compile(
    r"\b(must|should|need to|required to|have to)\s+(be\s+)?(?:(?:physically|currently|legally)\s+)?(reside|live|located|based|living|residing)\s+(in|within)\s+"
    r"(the\s+)?(?P<lugar>[a-z .]{2,40})"
    r"|\b(only|solo|solamente|unicamente|exclusively)\s+(open\s+to\s+)?(candidates|applicants|candidatos|personas|residents)?\s*"
    r"(from|in|de|en|residing in|located in|based in)\s+(the\s+)?(?P<lugar2>[a-z .]{2,40})"
    r"|\b(?P<lugar3>us|usa|u\.s|united states|uk|canada|eu|europe|india)[- ](only|based|residents?)\b"
    r"|\b(?:must be|must have|need to be|required to be)\s+(?:legally )?(?:authorized to work|eligible to work|the right to work)\s+in\s+(?:the )?(?P<lugar4>[a-z .]{2,40})"
    r"|\b(?:debes?|debera[s]?|es necesario|se requiere)\s+(?:residir|vivir|estar ubicado|estar ubicada|tener residencia)\s+en\s+(?P<lugar5>[a-z .]{2,40})")
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


def _restricciones(desc):
    """Todas las restricciones reconocidas; una frase comercial no acredita residencia."""
    d = datos()
    restricciones = []
    for m in re.finditer(r"(?=(?P<coincidencia>"+_RESTRINGE.pattern+r"))",desc):
        lugar = (m.group("lugar") or m.group("lugar2") or m.group("lugar3") or m.group("lugar4") or m.group("lugar5") or "").strip()
        coincidencia = m.group("coincidencia")
        contexto = coincidencia[:coincidencia.find(lugar)]
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
              r"|\b(?:work|working|trabajar|trabaja)\s+(?:remotely\s+)?(?:from|desde)\s+(?P<trabajo>"+opciones+r")\b")
    for m in re.finditer(patron,desc):
        if re.search(r"\b(?:not|no|cannot|can t|unable|except|excluding)\b",desc[max(0,m.start()-35):m.start()]):
            continue
        return m.group("contratacion") or m.group("trabajo")
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
    if _REMOTO_DESC.search(d):
        return "remoto"
    return "presencial" if t.strip() else "sin dato"


CONFIANZAS = ("alta", "media", "baja")
MODALIDADES = ("hibrido", "remoto", "presencial", "sin dato")  # explícitas antes que la presencial por defecto
NOTA_INCIERTA = "confirmar países: fuentes con ubicación incierta"


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
    return {"paises": union, "modalidad": modo, "confianza": confianza, "nota": nota}


# Contrato v13: códigos al final de la ubicación. LinkedIn y los portales escriben «Bucharest, ro» o «Barcelona, es»
# (país ISO en minúsculas) y «San Jose, CA» (estado de EE. UU. en mayúsculas). Antes quedaban «por confirmar».
_ESTADOS_EEUU = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC
    ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
_CODIGO_FINAL = re.compile(r"(?:,|\s[-–]|^)\s*([A-Za-z]{2}|[A-Z]{3})\s*$")
_SOLO_CODIGOS = re.compile(r"^\s*([A-Za-z]{2}|[A-Z]{3})(?:\s+\1)*\s*$")


@lru_cache(maxsize=1)
def _lugares_mundo():
    import gzip
    import json
    try:
        with gzip.open(RUTA_LUGARES, "rt", encoding="utf-8") as f:
            crudo = json.load(f)
    except (OSError, ValueError):
        return {}, frozenset()
    return crudo.get("cubiertos", {}), frozenset(crudo.get("extranjeros", []))


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
    for tramo in re.split(r"[,;|/()]| - | – ", ubicacion or ""):
        t = normalizar.texto(_REMOTO.sub(" ", _HIBRIDO.sub(" ", _PRESENCIAL.sub(" ", normalizar.texto(tramo)))))
        t = re.sub(r"^(?:area metropolitana de |region metropolitana de |greater )", "", t)
        t = re.sub(r" (?:y alrededores|and surrounding areas|metropolitan area|area)$", "", t)
        for candidato in (t, re.sub(r" [a-z]{2}$", "", t)):  # «harrisburg pa» → «harrisburg»
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
    """Países desde los que se puede aplicar, con modalidad, confianza y una nota corta."""
    r = _elegibles(titulo, ubicacion, descripcion, remoto)
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


def _elegibles(titulo, ubicacion, descripcion="", remoto=None):
    """Lo que dicen la ubicación, el título y la descripción con la tabla oficial (sin reglas)."""
    d = datos()
    todos, latam, europa = d["codigos"], d["latam"], d["europa"]
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
    nombres_pais = [codigo for codigo,nombres in d["nombres_pais"] if _nombra(sin_homonimos,nombres)]
    ciudad_sola = normalizar.texto(_REMOTO.sub(" ",_HIBRIDO.sub(" ",_PRESENCIAL.sub(" ",geografia))))
    ciudad_sola = re.sub(r"^(?:area metropolitana de |region metropolitana de |greater )", "", ciudad_sola)
    ciudad_sola = re.sub(r" (?:y alrededores|and surrounding areas|metropolitan area|area)$", "", ciudad_sola)
    ciudades = d["ciudades"].get(ciudad_sola,[])
    if not nombres_pais and not ciudades and not _nombra(ciudad_sola, d["fuera_lugares"]):
        ciudades = _ciudad_dentro(ciudad_sola, d["ciudades"])
    nombrados = nombres_pais or ciudades
    es_latam = _nombra(ambito, d["toda_latam"])
    es_mundo = _nombra(ambito, d["mundo"])
    es_europa = _nombra(ambito, d["toda_europa"])
    ambito_sin_propios = ambito
    for frase in d["propios_con_fuera"]:
        ambito_sin_propios = re.sub(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", " ", ambito_sin_propios)
    fuera = _nombra(ambito_sin_propios, d["fuera_lugares"])
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
    restricciones = _restricciones(desc) + _restricciones(titulo_normalizado)
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
    if contratacion:
        return r(interpretar(contratacion), "alta", "contratación remota explícita")
    if es_mundo or (_REMOTO.search(titulo_normalizado) and _nombra(titulo_normalizado,d["mundo"])):
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
