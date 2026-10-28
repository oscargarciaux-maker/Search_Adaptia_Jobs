"""Normalización de textos, títulos y empresas (sin IA)."""
import re
import unicodedata

NIVELES = {
    "trainee": "trainee", "intern": "trainee", "internship": "trainee", "pasante": "trainee", "pasantia": "trainee",
    "practicante": "trainee", "aprendiz": "trainee", "estagio": "trainee", "estagiario": "trainee",
    "junior": "junior", "jr": "junior", "entry": "junior",
    "semi senior": "semi senior", "semisenior": "semi senior", "semi-senior": "semi senior", "ssr": "semi senior",
    "mid": "semi senior", "mid level": "semi senior", "pleno": "semi senior",
    "senior": "senior", "sr": "senior",
    "lead": "lead", "lider": "lead", "staff": "lead", "principal": "lead", "head": "lead",
    "director": "lead", "directora": "lead", "gerente": "lead", "chief": "lead", "vp": "lead",
}
# Del más alto al más bajo: si un título dice "Senior Lead", cuenta como lead
_ORDEN_NIVEL = ["lead", "senior", "semi senior", "junior", "trainee"]
_ROMANOS = re.compile(r"\b(i{1,3}|iv|1|2|3)\b$")
# Palabras de nivel que se quitan del título para compararlo con el mapa. "manager", "director", "head" y "líder" no:
# son parte del cargo (Product Manager, Community Manager, líder de proyectos); su nivel sí se detecta con NIVELES.
_QUITAR = ["trainee", "intern", "internship", "pasante", "pasantia", "practicante", "aprendiz", "estagio", "estagiario",
           "junior", "jr", "entry level", "semi senior", "semisenior", "semi-senior", "ssr", "mid level", "mid", "pleno",
           "senior", "sr", "lead", "staff", "principal"]
_QUITAR_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(_QUITAR, key=len, reverse=True)) + r")\b\.?")
# Si al quitar el nivel el cargo queda en una sola palabra ("Tech Lead" -> "tech"), "lead", "staff" y "principal" son
# parte del cargo y se dejan
_QUITAR_SIN_CARGO_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(set(_QUITAR) - {"lead", "staff", "principal"},
                                                                              key=len, reverse=True)) + r")\b\.?")
# Femenino y masculino cuentan igual: diseñadora -> diseñador, ingeniera -> ingeniero
_GENERO = [(re.compile(r"\b(\w+)dora\b"), r"\1dor"), (re.compile(r"\bingeniera\b"), "ingeniero"),
           (re.compile(r"\barquitecta\b"), "arquitecto"), (re.compile(r"\btecnica\b"), "tecnico"),
           (re.compile(r"\bexperta\b"), "experto"), (re.compile(r"\bcientifica\b"), "cientifico"),
           (re.compile(r"\bdesenvolvedora\b"), "desenvolvedor")]
_NIVEL_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in NIVELES), key=len, reverse=True)) + r")\b\.?")
_RUIDO = re.compile(r"\b(remote|remoto|remota|hybrid|hibrido|hibrida|presencial|on ?site|full ?time|part ?time|"
                    r"tiempo completo|medio tiempo|m/f|f/m|m/f/d|h/m|m/h|a/o|o/a|\(a\)|ref\s*#?\s*\w+)\b", re.I)


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")


def texto(texto_crudo):
    """Minúsculas, sin tildes, solo letras, números y espacios simples (conserva '/', '+', '#' y '.' útiles: c#, .net)."""
    t = sin_tildes(texto_crudo).lower()
    t = re.sub(r"[^a-z0-9+#./ ]+", " ", t)
    t = re.sub(r"(?<![a-z0-9])\.|\.(?![a-z0-9])", " ", t)  # puntos sueltos, no los de .net o node.js
    return re.sub(r"\s+", " ", t).strip()


def nivel(titulo):
    """Nivel del cargo según su título: trainee, junior, semi senior, senior, lead o '' si no lo dice."""
    t = texto(titulo).replace("/", " ")
    hallados = {NIVELES[m.group(1)] for m in _NIVEL_RE.finditer(t)}
    if not hallados and _ROMANOS.search(t):
        n = _ROMANOS.search(t).group(1)
        return {"i": "junior", "1": "junior", "ii": "semi senior", "2": "semi senior"}.get(n, "senior")
    return next((n for n in _ORDEN_NIVEL if n in hallados), "")


def titulo_base(titulo):
    """Título sin nivel, sin ciudad entre paréntesis, sin modalidad ni códigos: para comparar con el mapa de cargos."""
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", str(titulo or ""))
    t = re.split(r"\s+[-–—|]\s+(?=[^-–—|]*\b(remote|remoto|hibrido|hybrid|presencial|bogota|mexico|latam)\b)", t, flags=re.I)[0]
    t = texto(t)
    t = _RUIDO.sub(" ", t)
    t = re.sub(r"(?<=[a-z])/(a|o|as|os|e)(?![a-z])", "", t)  # desarrollador/a -> desarrollador
    sin_nivel = _QUITAR_RE.sub(" ", t.replace("/", " / "))
    if len(sin_nivel.replace("/", " ").split()) < 2 <= len(t.replace("/", " ").split()):
        sin_nivel = _QUITAR_SIN_CARGO_RE.sub(" ", t.replace("/", " / "))
    t = sin_nivel
    for patron, reemplazo in _GENERO:
        t = patron.sub(reemplazo, t)
    t = re.sub(r"\b(\d{3,}|i{1,3}|iv)\b", " ", t)
    t = re.sub(r"\s+", " ", t).replace(" / ", "/")
    return re.sub(r"/{2,}", "/", t).strip(" -/")


_SUFIJOS_EMPRESA = re.compile(r"\b(s\.?a\.?s\.?|s\.?a\.?|ltda\.?|inc\.?|llc|ltd\.?|corp\.?|corporation|gmbh|s\.?r\.?l\.?|"
                              r"s\.? de r\.?l\.?(?: de c\.?v\.?)?|s\.?a\.? de c\.?v\.?|co\.?|company|group|grupo)\b")


def empresa(nombre):
    """Empresa normalizada para deduplicar: sin tildes, sin S.A.S., Inc., Ltda. ni signos."""
    t = sin_tildes(nombre).lower()
    t = _SUFIJOS_EMPRESA.sub(" ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def contiene_frase(haystack, frase):
    """true si la frase aparece como palabras completas dentro del texto ya normalizado."""
    return re.search(r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])", haystack) is not None
