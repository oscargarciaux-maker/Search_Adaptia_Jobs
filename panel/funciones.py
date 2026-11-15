"""Contrato v25: propuesta de la huella de funciones de un cargo, sin IA.

Compara las descripciones del catálogo cuyo título sí es del cargo con las de otros títulos y devuelve los términos
(una o dos palabras) que más distinguen al cargo. El operador revisa la lista antes de guardarla."""
from collections import Counter
import re
from hashlib import sha256

from buscador import normalizar

PALABRAS_VACIAS = set("""
a al algo algunos ante antes area areas as at be been being but by can con como cada de del desde do does donde dos
el ella en entre era es esta estas este esto estos etc for from fue gran ha han has have he her his how i if in
into is it its la las le les lo los mas may me mi more most mucho muy must new no nos not nuestra nuestro nuestros
nuestras o of on one or other otra otro otros our out para pero por puede que se ser si sin so sobre some son su sus
such than that the their them then there these they this those through to todo todos tu tus un una uno unos up
us very was we were what when where which while who will with within would y ya you your
experience experiencia years anos ano work trabajo trabajar team equipo equipos company empresa role rol job puesto
position oferta vacante we re you ll opportunity oportunidad looking buscamos join unete benefits beneficios salary
salario remote remoto hybrid hibrido full time tiempo completo apply aplicar candidate candidato candidatos skills
habilidades requirements requisitos responsibilities responsabilidades knowledge conocimiento conocimientos strong
excellent excelente good buen buena ability capacidad including incluyendo using usar uso like such also tambien
well bien best mejor based basado across help ayudar make hacer get our nuestro day dia days dias year
""".split())


def terminos(texto):
    """Términos de una y dos palabras de un texto (normalizado), sin palabras vacías ni números. Los pares no saltan
    signos de puntuación («usabilidad, journey» no forma un par)."""
    salida = set()
    for trozo in re.split(r"[,.;:!?()\[\]/|\n•·–-]+", str(texto)[:12000]):
        # Las palabras cortas, vacías o numéricas cortan el par («maps y diseño» no forma «maps diseño»).
        utiles = [p if len(p) >= 3 and not p.isdigit() and p not in PALABRAS_VACIAS else None
                  for p in normalizar.texto(trozo).split()]
        salida |= {p for p in utiles if p}
        salida |= {f"{a} {b}" for a, b in zip(utiles, utiles[1:]) if a and b}
    return salida


def proponer(del_cargo, otros, maximo=25, excluir=()):
    """Los términos más distintivos de `del_cargo` frente a `otros` (listas de descripciones)."""
    if len(del_cargo) < 5:
        return []
    excluir = {normalizar.texto(x) for x in excluir}
    en_cargo = Counter(t for d in del_cargo for t in terminos(d))
    en_otros = Counter(t for d in otros for t in terminos(d))
    n_cargo, n_otros = len(del_cargo), max(1, len(otros))
    soporte = max(3, -(-n_cargo // 10))
    puntajes = []
    for t, dc in en_cargo.items():
        if dc < soporte or t in excluir:
            continue
        proporcion = (dc / n_cargo) / ((en_otros.get(t, 0) + 1) / (n_otros + 1))
        if proporcion >= 2:
            puntajes.append((proporcion * (1.2 if " " in t else 1.0), dc, t))
    elegidos = []
    for _, _, t in sorted(puntajes, reverse=True):
        # Si ya está «historias usuario», no hace falta «historias» sola, y viceversa.
        if any(t in e.split() or e in t.split() for e in elegidos):
            continue
        elegidos.append(t)
        if len(elegidos) >= maximo:
            break
    return elegidos


def muestra_estable(ids, cuantos, semilla="adaptia"):
    """Hasta `cuantos` ids en un orden estable (el mismo resultado cada vez que se pide)."""
    return sorted(ids, key=lambda i: sha256(f"{semilla}|{i}".encode()).hexdigest())[:cuantos]
