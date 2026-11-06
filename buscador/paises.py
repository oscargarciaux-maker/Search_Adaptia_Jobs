"""Desde qué países de LATAM y del mundo hispanohablante (España) se puede aplicar a una vacante (sin IA).

Mira primero la ubicación y el título del aviso; la descripción solo cuenta para la modalidad remota y para frases que
restringen dónde debe vivir la persona ("must be based in", "only candidates from"). Devuelve:
  {"paises": [códigos], "modalidad": "remoto|hibrido|presencial|sin dato", "confianza": "alta|media|baja",
   "nota": texto corto para la página}
Si nadie de esos países puede aplicar, "paises" queda vacío. Remoto para LATAM no incluye a España; remoto para el
mundo sí; remoto para Europa es solo España.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from buscador import normalizar

RUTA = Path(__file__).resolve().parent.parent / "datos" / "paises.yaml"

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
    claves.sort(key=lambda x: -len(x[0]))  # las frases largas primero ("santiago de chile" antes que "santiago")
    return {
        "paises": paises,
        "codigos": [p["codigo"] for p in paises],
        "latam": [p["codigo"] for p in paises if p.get("region", "latam") == "latam"],
        "europa": [p["codigo"] for p in paises if p.get("region") == "europa"],
        "utc": {p["codigo"]: p["utc"] for p in paises},
        "claves": claves,
        "nombres_pais": [(p["codigo"],[normalizar.texto(x) for x in p["nombres"]+p["gentilicios"]]) for p in paises],
        "ciudades": ciudades,
        "toda_latam": sorted({normalizar.texto(x) for x in crudo["toda_latam"]}, key=len, reverse=True),
        "mundo": sorted({normalizar.texto(x) for x in crudo["todo_el_mundo"]}, key=len, reverse=True),
        "toda_europa": sorted({normalizar.texto(x) for x in crudo["toda_europa"]}, key=len, reverse=True),
        "fuera": sorted({normalizar.texto(x) for x in crudo["fuera_de_latam"]}, key=len, reverse=True),
        "subregiones": crudo.get("subregiones", []),
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


def _pais_por_nombre(t, codigos):
    """Alguno de esos países aparece por su nombre o gentilicio (no solo por una ciudad: "Santa Ana, California")."""
    return any(_nombra(t, [normalizar.texto(x) for x in p["nombres"] + p["gentilicios"]])
               for p in datos()["paises"] if p["codigo"] in codigos)


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


def elegibles(titulo, ubicacion, descripcion="", remoto=None):
    """Países desde los que se puede aplicar, con modalidad, confianza y una nota corta."""
    d = datos()
    todos, latam, europa = d["codigos"], d["latam"], d["europa"]
    lugar = normalizar.texto(f"{ubicacion} {titulo}")
    ambito = normalizar.texto(ubicacion) or lugar
    desc = normalizar.texto(descripcion)[:30000]
    mod = modalidad(titulo, ubicacion, descripcion, remoto)
    # El título no puede convertir una oficina de otro país en una ubicación permitida.
    geografia = normalizar.texto(ubicacion)
    nombres_pais = [codigo for codigo,nombres in d["nombres_pais"] if _nombra(geografia,nombres)]
    ciudad_sola = normalizar.texto(_REMOTO.sub(" ",_HIBRIDO.sub(" ",_PRESENCIAL.sub(" ",geografia))))
    ciudad_sola = re.sub(r"^(?:area metropolitana de |region metropolitana de |greater )", "", ciudad_sola)
    ciudad_sola = re.sub(r" (?:y alrededores|and surrounding areas|metropolitan area|area)$", "", ciudad_sola)
    ciudades = d["ciudades"].get(ciudad_sola,[])
    nombrados = nombres_pais or ciudades
    es_latam = _nombra(ambito, d["toda_latam"])
    es_mundo = _nombra(ambito, d["mundo"])
    es_europa = _nombra(ambito, d["toda_europa"])
    fuera = _nombra(ambito, d["fuera"])
    def subregion(texto):
        return next((r["paises"] for r in d["subregiones"] if _nombra(texto, r["nombres"])), None)

    def r(paises, confianza, nota):
        return {"paises": paises, "modalidad": mod, "confianza": confianza, "nota": nota}

    # Residencia explícita: también restringe ofertas presenciales o híbridas.
    titulo_normalizado = normalizar.texto(titulo)
    remoto_en = re.search(r"\bremote\s+(?:only\s+)?(?:in|from|within)\s+([a-z /.+]{2,80})", titulo_normalizado)
    restricciones = _restricciones(desc) + _restricciones(titulo_normalizado)
    if remoto_en:
        restricciones.append(remoto_en.group(1))
    def interpretar(restringe):
        r_paises = _paises_nombrados(restringe)
        if r_paises:
            return r_paises
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
        return r(todos, "baja", "restricción de residencia sin confirmar")
    if mod != "remoto":
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
        return r(region, "alta", "restricción regional")
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
