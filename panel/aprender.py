"""Contrato v17: aprendizaje de ubicaciones solo con código (sin IA). Cada noche, antes de la búsqueda, revisa las
decisiones del operador en la bandeja «Por confirmar» y deduce reglas de lugar generales:

1. De cada ubicación decidida («Sant Cugat del Vallès, Barcelona» → España) toma sus frases de lugar candidatas
   (1 a 4 palabras seguidas), sin palabras genéricas (remote, área, metropolitana, y alrededores…) ni lugares que la
   tabla oficial ya conoce.
2. Si una frase aparece en **al menos 2 ubicaciones distintas**, todas con el **mismo** resultado (los mismos países, o
   todas «solo otro país»), sin ninguna en contra y sin ser un nombre ambiguo o una palabra corriente, nace una regla
   `aprendida`: «frase → resultado». Se queda solo la frase más larga que tenga la misma evidencia.
3. Una regla aprendida que una decisión posterior contradice **se desactiva sola** (y suma un conflicto).
4. Una regla desactivada (por conflicto o a mano en el panel) nunca se reactiva sola.

Las reglas aprendidas, como las del operador, solo resuelven lo que la tabla oficial deja «por confirmar»
(`paises.elegibles`): nunca cambian un país ya reconocido.
"""
import re

from buscador import normalizar, paises
from panel.revision import _GENERICAS

MINIMO_EVIDENCIAS = 2
_VACIAS = {"de", "del", "la", "las", "el", "los", "y", "e", "and", "of", "the", "area", "metropolitana",
           "metropolitan", "alrededores", "surrounding", "areas", "greater", "region", "province", "provincia",
           "state", "estado", "city", "ciudad", "distrito", "district", "county", "condado", "municipio", "zona",
           "centro", "norte", "sur", "este", "oeste", "north", "south", "east", "west", "da", "do", "dos", "das",
           "en", "in", "at", "near", "cerca", "sede", "campus", "edificio", "building", "piso", "floor", "calle",
           "street", "avenida", "av", "suite", "oficina", "offices"}
# Palabras geográficas comunes: valen dentro de una frase («sant cugat», «pueblo nuevo de x»), nunca solas.
_GEOGRAFICAS = {"nuevo", "nueva", "pueblo", "villa", "puerto", "valle", "rio", "lago", "monte", "san", "santa", "santo",
                "sant", "saint", "st", "port", "mount", "lake", "new", "old", "viejo", "vieja", "alto", "alta", "bajo",
                "baja", "grande", "real", "playa", "costa", "isla", "islas", "cabo", "punta", "sierra", "mar", "ville"}
MINIMO_PALABRA_SUELTA = 3
ETIQUETAS = {"sirve": "confirmada por operador", "otro_pais": "otro país (operador)", "no_sirve": "no sirve (operador)"}


def resultado_de(decision):
    """{"paises": [...]} o {"extranjero": True}, o None si la decisión no dice nada del lugar ("no sirve", "saltar")."""
    if decision.get("estado") == "confirmada" and decision.get("motivo") == ETIQUETAS["sirve"] and decision.get("paises"):
        return {"paises": sorted(decision["paises"])}
    if decision.get("estado") == "descartada" and decision.get("motivo") == ETIQUETAS["otro_pais"]:
        return {"extranjero": True}
    return None


def frases(ubicacion):
    """Frases de lugar candidatas de una ubicación (1 a 4 palabras seguidas, sin palabras vacías ni genéricas)."""
    d = paises.datos()
    conocidos = set(d["ciudades"]) | set(d["fuera_lugares"]) | {n for _, ns in d["nombres_pais"] for n in ns}
    vetadas = d["ambiguas"] | d["palabras_comunes"] | conocidos
    texto = re.sub(r"[^a-z0-9 ]+", " ", _GENERICAS.sub(" ", paises.clave(ubicacion)))
    tramos, actual = [], []
    for palabra in texto.split():  # las palabras vacías cortan una frase en tramos
        if palabra in _VACIAS or palabra.isdigit() or len(palabra) < 2:
            if actual:
                tramos.append(actual)
            actual = []
        else:
            actual.append(palabra)
    if actual:
        tramos.append(actual)
    salida = set()
    for tramo in tramos:
        for n in range(1, min(4, len(tramo)) + 1):
            for i in range(len(tramo) - n + 1):
                frase = " ".join(tramo[i:i + n])
                palabras = tramo[i:i + n]
                if n == 1 and palabras[0] in _GEOGRAFICAS or all(p in _GEOGRAFICAS for p in palabras):
                    continue
                if len(frase) >= 4 and frase not in vetadas and not any(p in vetadas for p in palabras if len(p) > 3):
                    salida.add(frase)
    return salida


def aprender(decisiones, reglas):
    """(reglas nuevas, reglas a desactivar, conteos). No escribe nada: lo hace quien llama."""
    evidencia = {}  # frase → {ubicacion: resultado}
    for d in decisiones:
        resultado = resultado_de(d)
        ubicacion = paises.clave(d.get("ubicacion"))
        if not resultado or not ubicacion:
            continue
        for f in frases(ubicacion):
            evidencia.setdefault(f, {})[ubicacion] = resultado
    existentes = {r["texto"]: r for r in reglas}
    candidatas = {}
    for f, por_ubicacion in evidencia.items():
        resultados = list(por_ubicacion.values())
        minimo = MINIMO_PALABRA_SUELTA if " " not in f else MINIMO_EVIDENCIAS
        if len(por_ubicacion) >= minimo and all(r == resultados[0] for r in resultados):
            candidatas[f] = (resultados[0], frozenset(por_ubicacion))
    # Quedarse con la frase más larga que tiene exactamente la misma evidencia («sant cugat» y no también «cugat»).
    nuevas = []
    for f, (resultado, ubicaciones) in candidatas.items():
        if any(otra != f and normalizar.contiene_frase(otra, f) and ub == ubicaciones for otra, (_, ub) in candidatas.items()):
            continue
        if f in existentes:  # ya existe (activa, o desactivada a mano o por conflicto: no se reactiva sola)
            continue
        nuevas.append({"texto": f, "resultado": resultado, "origen": "aprendida", "activa": True,
                       "ejemplos": sorted(ubicaciones)[:5]})
    desactivar = []
    for texto, regla in existentes.items():
        if regla.get("origen") != "aprendida" or not regla.get("activa", True):
            continue
        contrarias = [u for u, res in evidencia.get(texto, {}).items() if res != regla.get("resultado")]
        if contrarias:
            desactivar.append({"texto": texto, "activa": False,
                               "conflictos": int(regla.get("conflictos") or 0) + len(contrarias)})
    return nuevas, desactivar, {"aprendidas_nuevas": len(nuevas), "desactivadas_por_conflicto": len(desactivar)}


def preparar(repo):
    """Antes de la búsqueda: aprende de las decisiones, guarda y carga todas las reglas activas en `paises`."""
    nuevas, desactivar, conteos = aprender(repo.decisiones_ubicacion(), repo.reglas())
    for fila in nuevas:
        repo.guardar_regla(fila)
    for fila in desactivar:
        repo.actualizar_regla(fila["texto"], {"activa": False, "conflictos": fila["conflictos"]})
    reglas = repo.reglas()
    paises.cargar_reglas(reglas)
    activas = [r for r in reglas if r.get("activa", True)]
    return {**conteos, "reglas_activas": len(activas),
            "reglas_aprendidas": sum(1 for r in activas if r.get("origen") == "aprendida"),
            "reglas_en_conflicto": sum(1 for r in reglas if (r.get("conflictos") or 0) and not r.get("activa", True))}, reglas


def guardar_usos(repo, reglas):
    """Después de la búsqueda: suma a cada regla cuántas veces resolvió una ubicación."""
    previas = {paises.clave(r["texto"]): r for r in reglas}
    aplicadas = 0
    for texto, n in paises.USOS.items():
        r = previas.get(texto)
        if r and n:
            repo.actualizar_regla(r["texto"], {"usos": int(r.get("usos") or 0) + n})
            aplicadas += n
    return aplicadas
