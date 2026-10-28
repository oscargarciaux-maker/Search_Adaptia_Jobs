"""Etiquetas de una vacante a partir de su texto (sin IA): idioma, inglés pedido, años mínimos y salario.
No filtran nada: la página las muestra como columnas."""
import re

from buscador import normalizar

_ES = {"el", "la", "los", "las", "de", "del", "y", "en", "para", "con", "por", "una", "que", "experiencia", "buscamos",
       "empresa", "conocimientos", "requisitos", "funciones", "trabajo", "nuestro", "somos"}
_EN = {"the", "and", "of", "to", "for", "with", "we", "you", "your", "our", "experience", "looking", "skills", "team",
       "role", "requirements", "about", "will", "are", "is"}
_PT = {"voce", "nao", "para", "com", "uma", "dos", "das", "experiencia", "vaga", "requisitos", "empresa", "trabalho",
       "conhecimento", "atuar", "sobre", "nossa", "nosso", "beneficios", "desejavel"}
_PT_SOLO = {"voce", "nao", "vaga", "atuar", "nossa", "nosso", "desejavel", "conhecimento", "trabalho"}


def idioma(texto):
    """'es', 'en' o 'pt' según las palabras más comunes del aviso; '' si no hay texto."""
    palabras = re.findall(r"[a-z]+", normalizar.sin_tildes(texto).lower()[:6000])
    if not palabras:
        return ""
    es = sum(p in _ES for p in palabras)
    en = sum(p in _EN for p in palabras)
    pt = sum(p in _PT_SOLO for p in palabras) * 3 + sum(p in _PT and p not in _PT_SOLO for p in palabras) * 0.3
    mejor = max((en, "en"), (es, "es"), (pt, "pt"))
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


_MONEDA = r"(?:US\$|USD|U\$S|COP|MXN|ARS|CLP|PEN|BRL|R\$|S/\.?|Bs\.?|€|EUR|\$)"
_NUM = r"\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d+)?\s*(?:k|K|mil|millones|M)?"
_SALARIO = re.compile(rf"{_MONEDA}\s?{_NUM}(?:\s*(?:-|–|a|to|hasta)\s*{_MONEDA}?\s?{_NUM})?"
                      rf"(?:\s*(?:{_MONEDA}))?(?:\s*(?:/|por|per|al|a la|a el)\s*(?:mes|month|año|year|hora|hour|hr|h))?",
                      re.I)


# Cifras de la empresa que no son sueldo ("raised $300M", "ronda de US$ 50 millones").
_NO_SALARIO = re.compile(r"(?:rais|fund|financ|invest|inversi|valuat|valua|revenue|ingres|factur|ARR|serie[s]?\s+[a-e]\b|"
                         r"ronda|round|backed|respald|capital|transacci|transaction|volume|volumen|loans?|pr[eé]stamo|"
                         r"billion|mil millones)", re.I)


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
        if _NO_SALARIO.search(contexto):
            continue
        return valor[:60]
    return ""
