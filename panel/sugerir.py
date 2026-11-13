"""Contrato v17 (ampliación «Sugerencias de la revisión»): una respuesta sugerida y su motivo para cada vacante de la
bandeja «Por confirmar», calculada solo con código (sin IA). Es una ayuda: decide la persona.

La pregunta única es: **¿puede postularse alguien que vive en un país de LATAM o en España?**

Solo cuentan como evidencia las frases que hablan de dónde vive o trabaja la persona (ubicación del aviso, «based in»,
«hiring in», oficinas, zonas horarias, regiones). Las de beneficios, viajes y clientes no cuentan: un retiro en París o
«clientes de EE. UU.» no dicen nada de quién puede postularse.

Reglas, en orden:
1. Países cubiertos o LATAM, sin extranjeros → «sí» con esos países.
2. Solo lugares extranjeros (o regiones sin LATAM ni España) → «otro país».
3. Mezcla, Europa/EMEA (incluye España), «cualquier lugar» o zona horaria → sin sugerencia: hay que leerla.
4. Ninguna evidencia → «no sirve» (en caso de duda, no entra; decisión del 13 nov).
"""
import re

from buscador import normalizar, paises

# Frases que hablan de dónde vive o trabaja la persona.
_CONTEXTO = re.compile(
    r"\b(based|located|location|locations|reside|resides|residing|resident|residents|residence|live in|living in|"
    r"must be in|must live|hiring in|hire in|hiring from|open to|candidates in|candidates from|applicants in|"
    r"applicants from|work from|working from|anywhere|remote in|remote from|remote within|remote across|within|"
    r"office|offices|headquarter|headquarters|hq|commut|onsite|on site|hybrid|time ?zone|timezone|zona horaria|utc|"
    r"gmt|desde|ubicad|ubicacion|residir|residencia|residente|vivir en|radicad|modalidad|remoto|remota|remotamente|"
    r"remote|remotely|trabajar desde|eligible|eligibility|"
    r"authorized to work|work authorization|right to work|visa|sponsorship|sede|oficina|oficinas|presencial|hibrid)")
# Frases que nunca son evidencia de lugar de la persona.
_IGNORAR = re.compile(
    r"\b(retreat|retreats|offsite|trip|trips|travel|travels|viaje|viajes|clients|clientes|"
    r"customers|partners in|lunch|stipend|perks|benefit|benefits|beneficio|beneficios|conference|conferences|"
    r"event|events|evento|eventos|vacation|vacaciones|holiday|holidays|founded|fundada|offices around the world)\b")
_ESTADO_US = re.compile(r"\b[A-Z][a-zA-Z.\s]{1,30},\s*([A-Z]{2})\b")
_US_MAYUSCULA = re.compile(r"\bU\.?S\.?A?\b")
_ESTADOS_AMBIGUOS = {"AR", "CO", "PA"}  # también son países cubiertos (contrato v15)
_MAXIMO_FRASE = 260
_EXCLUYE = re.compile(r"\b(excluding|excludes|except|excepto|exceptuando|salvo|sin incluir|other than|not open to|"
                      r"not available in|no disponible en|no aplica para)\b")

ETIQUETA = {"sirve": "sí", "otro_pais": "otro país", "no_sirve": "no sirve", "": ""}
GRUPOS = {"otro_pais": 0, "no_sirve": 1, "sirve": 2, "": 3}


def _frases(texto):
    for frase in re.split(r"(?<=[.!?;])\s+|\n+|\s+[•·▪]\s+", texto or ""):
        frase = " ".join(frase.split())
        if 6 <= len(frase) <= 600:
            yield frase


def _extranjeros(original, t, d):
    """Nombres extranjeros que aparecen como palabras completas (para citarlos en el motivo)."""
    nombres = []
    for lista in ("fuera", "fuera_lugares"):
        for m in paises._patron(tuple(d[lista])).finditer(t):
            nombre = m.group(0)
            if nombre == "us" and not _US_MAYUSCULA.search(original):
                continue  # «join us»: no es EE. UU.
            if nombre not in nombres:
                nombres.append(nombre)
    for m in _ESTADO_US.finditer(original):  # «Salem, OR»
        codigo = m.group(1)
        if codigo in paises._ESTADOS_EEUU and codigo not in _ESTADOS_AMBIGUOS:
            lugar = " ".join(m.group(0).split())
            if lugar not in nombres:
                nombres.append(lugar)
    return nombres


def _evidencias(datos):
    """[(texto original, texto normalizado)] con lo que dice el aviso del lugar de la persona."""
    salida = []
    for campo in (datos.get("ubicacion"), datos.get("titulo")):
        if campo:
            salida.append((campo, normalizar.texto(campo)))
    for frase in _frases(datos.get("_descripcion") or ""):
        t = normalizar.texto(frase)
        if _CONTEXTO.search(t) and not _IGNORAR.search(t):
            salida.append((frase, t))
    return salida


def _cita(frase):
    return frase if len(frase) <= _MAXIMO_FRASE else frase[:_MAXIMO_FRASE - 1].rstrip() + "…"


def sugerir(datos):
    """{decision, paises, motivo, frase, grupo}. `decision` vacía = hay que leerla."""
    d = paises.datos()
    cubiertos, excluidos, extranjeros, latam, europa, mundo, zona = [], [], [], [], [], [], []
    frase_si = frase_no = frase_duda = ""
    for original, t in _evidencias(datos):
        corte = _EXCLUYE.search(t)
        antes, despues = (t[:corte.start()], t[corte.start():]) if corte else (t, "")
        propios = [c for c in paises._paises_nombrados(antes) if c in d["codigos"]]
        excluidos += [c for c in paises._paises_nombrados(despues) if c in d["codigos"] and c not in excluidos]
        fuera = _extranjeros(original, t, d)
        es_latam = paises._nombra(t, d["toda_latam"])
        es_europa = paises._nombra(t, d["toda_europa"])
        es_mundo = paises._nombra(t, d["mundo"])
        es_zona = bool(paises._ZONA.search(t)) and not propios and not fuera
        cubiertos += [c for c in propios if c not in cubiertos]
        extranjeros += [f for f in fuera if f not in extranjeros]
        if es_latam:
            latam.append(original)
        if es_europa:
            europa.append(original)
        if es_mundo:
            mundo.append(original)
        if es_zona:
            zona.append(original)
        if (propios or es_latam) and not frase_si:
            frase_si = original
        if fuera and not frase_no:
            frase_no = original
        if (es_europa or es_mundo or es_zona) and not frase_duda:
            frase_duda = original
    nombres = {p["codigo"]: p["nombre"] for p in d["paises"]}
    cubiertos = [c for c in cubiertos if c not in excluidos]
    positivos = bool(cubiertos or latam)
    if positivos and not extranjeros and not europa and not mundo:
        if latam:  # «LATAM» vale para todos los de LATAM (menos los excluidos), más España si la nombra
            codigos = [c for c in d["latam"] if c not in excluidos] + (["ES"] if "ES" in cubiertos else [])
            lugar = "LATAM" + (" excepto " + ", ".join(nombres.get(c, c) for c in excluidos) if excluidos else "")
            lugar += " y España" if "ES" in cubiertos else ""
        else:
            codigos = cubiertos
            lugar = ", ".join(nombres.get(c, c) for c in codigos)
        return {"decision": "sirve", "paises": codigos, "motivo": f"Menciona {lugar}.",
                "frase": _cita(frase_si), "grupo": GRUPOS["sirve"]}
    if positivos or europa or mundo or zona:
        partes = []
        if cubiertos or latam:
            partes.append(", ".join(nombres.get(c, c) for c in cubiertos) or "LATAM")
        if extranjeros:
            partes.append("también " + ", ".join(extranjeros[:4]))
        if europa:
            partes.append("Europa/EMEA (incluye España)")
        if mundo:
            partes.append("«cualquier lugar»")
        if zona:
            partes.append("solo un horario, sin país")
        return {"decision": "", "paises": cubiertos, "motivo": "Léela: menciona " + "; ".join(partes) + ".",
                "frase": _cita(frase_duda or frase_si or frase_no), "grupo": GRUPOS[""]}
    if extranjeros:
        return {"decision": "otro_pais", "paises": [], "motivo": "Solo menciona " + ", ".join(extranjeros[:4]) + ".",
                "frase": _cita(frase_no), "grupo": GRUPOS["otro_pais"]}
    ubicacion = datos.get("ubicacion") or "nada"
    return {"decision": "no_sirve", "paises": [],
            "motivo": f"El aviso no dice desde qué país: solo «{ubicacion}».", "frase": "", "grupo": GRUPOS["no_sirve"]}
