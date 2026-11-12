"""Etiquetas de una vacante a partir de su texto (sin IA): idioma, inglés pedido, años mínimos y salario.
No filtran nada: la página las muestra como columnas."""
import re

from buscador import normalizar

# Solo palabras PROPIAS de cada idioma (contrato v12). Las compartidas por español y portugués («de», «que», «para»,
# «experiencia», «empresa», «requisitos»…) no cuentan: con ellas un aviso largo en portugués salía como español.
_ES = {"el", "la", "los", "las", "del", "y", "en", "es", "un", "una", "lo", "le", "al", "sus", "muy", "pero", "hasta",
       "donde", "tambien", "usted", "nuestro", "nuestra", "nuestros", "nuestras", "buscamos", "puesto", "ofrecemos",
       "conocimientos", "funciones", "desarrollo", "equipo", "trabajo", "personas", "proceso", "manejo", "cual",
       "vacante", "postulate", "contar", "deseable", "ubicacion"}
_EN = {"the", "and", "of", "to", "for", "with", "we", "you", "your", "our", "experience", "looking", "skills", "team",
       "role", "requirements", "about", "will", "are", "is"}
_PT = {"em", "uma", "um", "da", "das", "ao", "aos", "pelo", "pela", "seu", "sua", "seus", "suas", "com", "ou", "voce",
       "nao", "sao", "tambem", "equipe", "vaga", "vagas", "atuar", "atuacao", "nosso", "nossa", "nossos", "nossas",
       "desejavel", "conhecimento", "conhecimentos", "trabalho", "trabalhar", "pessoas", "solucoes", "desenvolvimento",
       "atividades", "mais", "muito", "onde", "ate", "isso", "essa", "esse", "processo"}
assert not _ES & _PT  # una palabra que se escribe igual en los dos idiomas no decide
# Contrato v13: otros idiomas frecuentes en el inventario (Francia, Alemania, Italia). Solo palabras propias.
_FR = {"les", "des", "du", "et", "vous", "nous", "est", "pour", "avec", "dans", "sur", "une", "votre", "notre", "poste",
       "equipe", "au", "aux", "chez", "nos", "vos", "sont", "etes", "sera", "ainsi"}
_DE = {"und", "der", "die", "das", "wir", "sie", "mit", "fur", "ihre", "unsere", "bei", "auf", "ist", "sind", "einen",
       "eine", "ein", "oder", "werden", "zur", "zum", "uber", "kenntnisse", "erfahrung", "aufgaben"}
_IT = {"il", "di", "che", "per", "con", "della", "delle", "degli", "nel", "nella", "sono", "siamo", "lavoro", "esperienza",
       "conoscenza", "azienda", "gli", "dei", "alla", "anche", "nostro", "nostra", "ricerca"}
_OTROS = {"fr": _FR - _ES - _EN - _PT, "de": _DE - _ES - _EN - _PT, "it": _IT - _ES - _EN - _PT}


def idioma(texto):
    """'es', 'en', 'pt', 'fr', 'de' o 'it' según las palabras propias más frecuentes; '' si no hay texto."""
    palabras = re.findall(r"[a-z]+", normalizar.sin_tildes(texto).lower()[:6000])
    if not palabras:
        return ""
    es = sum(p in _ES for p in palabras)
    en = sum(p in _EN for p in palabras)
    pt = sum(p in _PT for p in palabras)
    otros = [(sum(p in conjunto for p in palabras), codigo) for codigo, conjunto in _OTROS.items()]
    mejor = max([(en, "en"), (es, "es"), (pt, "pt")] + [(n * 0.9, c) for n, c in otros])
    return mejor[1] if mejor[0] > 0 else ""


_INGLES = r"(?:ingl[eé]s|english|ingles)"
# (nivel, patrón que ya habla de inglés, patrón suelto que solo cuenta si cerca se habla de inglés)
_NIVELES_INGLES = [
    ("nativo", rf"native\s+(?:level\s+)?(?:in\s+)?english|english\s*[:\-–(]?\s*native|{_INGLES}\s+(?:a\s+)?nivel\s+nativo|"
               rf"{_INGLES}\s+nativo|native\s+english\s+speaker", r"\bc2\b|\bnativo\b|\bnative\b"),
    ("fluido", rf"fluent\s+(?:in\s+)?english|english\s+fluency|fluency\s+in\s+english|{_INGLES}\s*[:\-–(]?\s*(?:nivel\s+)?"
               rf"(?:flu[ií]do|fluent)|biling[uü]e|bilingual", r"\bc1\b|\bfluent\b|\bflu[ií]d[oa]\b"),
    ("avanzado", rf"{_INGLES}\s*[:\-–(]?\s*(?:nivel\s+)?(?:avanzado|advanced|alto|excelente|excellent|proficient)|"
                 rf"(?:advanced|excellent|strong|proficient)\s+(?:command\s+of\s+|level\s+of\s+)?english|"
                 rf"english\s+proficiency|nivel\s+(?:avanzado|alto)\s+de\s+{_INGLES}", None),
    ("intermedio", rf"{_INGLES}\s*[:\-–(]?\s*(?:nivel\s+)?(?:intermedio|intermediate|medio|conversacional|conversational)|"
                   rf"intermediate\s+english", r"\bb[12]\b"),
    ("basico", rf"{_INGLES}\s*[:\-–(]?\s*(?:nivel\s+)?(?:b[aá]sico|basic)|basic\s+english", r"\ba[12]\b"),
]


def ingles(texto):
    """Nivel de inglés que pide el aviso: nativo, fluido, avanzado, intermedio, basico, o '' si no lo dice.
    Las palabras sueltas (C1, B2, fluent) solo cuentan si cerca se habla de inglés."""
    t = normalizar.sin_tildes(texto).lower()[:12000]
    for nivel, directo, _ in _NIVELES_INGLES:
        if re.search(directo, t):
            return nivel
    for nivel, _, suelto in _NIVELES_INGLES:
        if suelto:
            for m in re.finditer(suelto, t):
                if re.search(_INGLES, t[max(0, m.start() - 80):m.end() + 80]):
                    return nivel
    return ""


_ANOS = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|–|a|to|y|and|ou|or)\s*\d{1,2}\s*)?(?:anos|years|yrs|anos de|años)", re.I)


def anos_min(texto):
    """Años mínimos de experiencia que pide el aviso (el menor que aparece cerca de "experiencia"), o None."""
    t = normalizar.sin_tildes(texto)[:12000]
    mejor = None
    for m in _ANOS.finditer(t):
        alrededor = t[max(0, m.start() - 80):m.end() + 80].lower()
        if not re.search(r"experien", alrededor):
            continue
        n = int(m.group(1))
        if n <= 20 and (mejor is None or n < mejor):
            mejor = n
    return mejor


# "S/" (soles) en mayúscula y sin una letra o "/" antes: si no, toma rutas de enlaces como "s/348".
_MONEDA = r"(?:US\$|USD|U\$S|COP|MXN|ARS|CLP|PEN|BRL|R\$|(?<![\w/])(?-i:S/)\.?|Bs\.?|€|EUR|\$)"
# La "M" de millones no puede ser el comienzo de "MXN" o "MENSUALES".
_NUM = r"\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d+)?\s*(?:k|K|mil|millones|M)?(?![A-Za-zÁÉÍÓÚáéíóú])"
_SALARIO = re.compile(rf"{_MONEDA}\s?{_NUM}(?:\s*(?:-|–|a|to|hasta)\s*{_MONEDA}?\s?{_NUM})?"
                      rf"(?:\s*(?:{_MONEDA}))?(?:\s*(?:/|por|per|al|a la|a el)\s*(?:mes|month|año|year|hora|hour|hr|h))?",
                      re.I)


# Cifras de la empresa que no son sueldo ("raised $300M", "ronda de US$ 50 millones").
_NO_SALARIO = re.compile(r"(?:rais|fund|financ|invest|inversi|valuat|valua|revenue|ingres|factur|ARR|serie[s]?\s+[a-e]\b|"
                         r"ronda|round|backed|respald|capital|transacci|transaction|volume|volumen|loans?|pr[eé]stamo|"
                         r"billion|mil millones|presupuest|budget)", re.I)
# Millones en dólares o euros son cifras de la empresa, no un sueldo (en pesos chilenos o colombianos sí puede serlo).
_MILLONES = re.compile(r"\d\s*(?:M|millones)\b", re.I)
_MONEDA_LOCAL = re.compile(r"COP|CLP|ARS|PYG|UYU", re.I)
_MILLONES_DESPUES = re.compile(r"\s*(?:mil+(?:l|h)|bill|bn\b|B\b|M\b|mm\b)", re.I)
# "Compensation: $100,000" o "Sueldo: $15.000" justo antes de la cifra: es sueldo aunque la frase hable de ventas.
_ROTULO_SUELDO = re.compile(r"(?:salar|sueldo|compensa|remunera|pago|pay|rango|range)\w*\W{0,4}$", re.I)


def salario(texto):
    """Primer rango de salario publicado (texto corto), o ''."""
    texto = str(texto or "")[:15000]
    for m in _SALARIO.finditer(texto):
        valor = m.group(0).strip()
        if not (re.search(r"\d", valor) and len(re.sub(r"\D", "", valor)) >= 3):
            continue
        # Solo la misma frase: lo que va antes desde el último punto y lo que sigue hasta el próximo.
        antes = re.split(r"[.!?\n]\s", texto[max(0, m.start() - 60):m.start()])[-1]
        despues = re.split(r"[.!?\n]", texto[m.end():m.end() + 25])[0]
        contexto = antes + " " + despues
        local = _MONEDA_LOCAL.search(valor + " " + despues)
        if (_MILLONES.search(valor) or _MILLONES_DESPUES.match(despues)) and not local:
            continue
        if _NO_SALARIO.search(contexto) and not _ROTULO_SUELDO.search(antes):
            continue
        return valor[:60]
    return ""
