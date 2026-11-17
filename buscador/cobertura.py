"""Consultas rotativas y reparto del presupuesto entre familias, sin favorecer un país fijo."""
import hashlib
from collections import defaultdict, deque
from datetime import date

from buscador import normalizar


def consultas(familia):
    salida, vistas = [], set()
    for campo in ("consultas", "exactos", "similares", "cercanos"):
        for frase in familia.get(campo, []):
            clave = normalizar.titulo_base(frase)
            if clave and clave not in vistas:
                vistas.add(clave)
                salida.append(frase)
    return salida


def rotar(frases, hoy, cantidad, desfase=0):
    if not frases:
        return []
    inicio = (date.fromisoformat(hoy).toordinal() * cantidad + desfase) % len(frases)
    return [frases[(inicio + i) % len(frases)] for i in range(min(cantidad, len(frases)))]


def clave_consulta(clave, frases):
    return clave + "#" + hashlib.sha256("|".join(frases).encode()).hexdigest()[:12]


# Contrato v37: lugares que van primero en cada familia (los de perfiles que quedaron bajo el mínimo o son nuevos).
# Lo fija el panel durante una búsqueda (`panel.ejecutor.activar`); vacío, todo sigue como antes.
_PRIMERO = {}


def configurar_primero(lugares=None):
    global _PRIMERO
    _PRIMERO = {f: set(v) for f, v in (lugares or {}).items()}


def va_primero(familia, lugar):
    """True si el lugar (o su país, antes de «:») es de un perfil que va corto en esa familia."""
    lugares = _PRIMERO.get(familia) or ()
    return bool(lugares) and (lugar in lugares or str(lugar).split(":")[0] in lugares)


def repartir(combinaciones, estado, hoy, prioritarias=()):
    """Una consulta por familia en cada vuelta; las menos recientes primero dentro de cada familia.

    En empates, remotas primero y desempate diario estable: ningún país queda siempre al final.
    Cuatro turnos de entrega por uno del resto evitan que otros cargos queden sin presupuesto.
    No supone cobertura completa por noche.
    """
    grupos = defaultdict(list)
    prioritarias = set(prioritarias)
    for c in combinaciones:
        grupos[c[0]].append(c)

    def azar(clave):
        return hashlib.sha256(f"{hoy}|{clave}".encode()).hexdigest()

    for familia, lista in grupos.items():
        lista.sort(key=lambda c: (not va_primero(c[0], c[2]), estado.get(f"{c[0]}@{c[2]}", ""),
                                  0 if "REMOTO" in c[2] else 1, azar(c[2])))
        grupos[familia] = deque(lista)
    tandas = []
    for prioritario in (True, False):
        ids = sorted((f for f in grupos if (f in prioritarias) == prioritario), key=azar)
        tanda = deque()
        while any(grupos[f] for f in ids):
            for f in ids:
                if grupos[f]:
                    tanda.append(grupos[f].popleft())
        tandas.append(tanda)
    salida = []
    principales, otras = tandas
    while principales or otras:
        for _ in range(4):
            if principales:
                salida.append(principales.popleft())
        if otras:
            salida.append(otras.popleft())
    return salida
