"""Consultas rotativas y reparto del presupuesto entre familias, sin favorecer un país fijo."""
import hashlib
from collections import Counter, defaultdict, deque
from datetime import date, timedelta

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


# Contrato v40: cuota de búsquedas por persona. Cada persona activa (un perfil) aporta su cargo, sus lugares de búsqueda
# y un peso (meta del día, más si va corta o si sus países tienen pocas fuentes). Lo fija el panel durante una búsqueda;
# vacío, el reparto sigue como antes. `_RENDIMIENTO`: lo que trajo cada combinación en búsquedas anteriores.
_PERSONAS = []
_RENDIMIENTO = {}
CEROS_PARA_BAJAR = 3
BUSQUEDAS = Counter()  # (fuente, familia, lugar) → páginas buscadas en esta búsqueda (contrato v40)  # búsquedas seguidas sin nada útil para que una combinación pase al final de su persona


def configurar_personas(personas=None):
    global _PERSONAS
    _PERSONAS = [dict(p, lugares=set(p["lugares"])) for p in (personas or []) if p.get("peso", 0) > 0]
    BUSQUEDAS.clear()


def anotar_busqueda(fuente, familia, lugar):
    BUSQUEDAS[(fuente, familia, str(lugar))] += 1


def busquedas_por_persona():
    """Contrato v40: {perfil: {fuente: páginas}} buscadas hoy para cada persona (una compartida cuenta para todas)."""
    salida = {}
    for p in _PERSONAS:
        cuenta = Counter()
        for (fuente, familia, lugar), n in BUSQUEDAS.items():
            if familia == p["familia"] and _claves_lugar(lugar) & p["lugares"]:
                cuenta[fuente] += n
        salida[p["perfil"]] = dict(cuenta)
    return salida


def configurar_rendimiento(rendimiento=None):
    global _RENDIMIENTO
    _RENDIMIENTO = dict(rendimiento or {})


def medir(estado, crudas, vacantes, hoy, dias=30):
    """Contrato v40: lo que trajo hoy cada combinación (cargo@lugar) buscada en LinkedIn o Indeed: vacantes nuevas de un
    cargo que entraron a la bodega. Cuenta las búsquedas seguidas sin nada útil (`ceros`) y olvida lo de más de 30
    días. Se guarda en `estado["rendimiento"]` y ordena la búsqueda siguiente."""
    origen = {c["enlace"]: c["_busqueda"] for c in crudas if c.get("_busqueda") and c.get("enlace")}
    utiles = Counter(origen[v["enlace"]] for v in vacantes
                     if v.get("familias") and v.get("enlace") in origen and v.get("visto_primera_vez") == hoy)
    buscadas = set(origen.values()) | {k for fuente in ("linkedin", "indeed") for k, f in (estado.get(fuente) or {}).items()
                                       if f == hoy and "@" in k and "#" not in k}
    rendimiento = estado.setdefault("rendimiento", {})
    for clave in buscadas:
        n = utiles.get(clave, 0)
        anterior = rendimiento.get(clave) or {}
        rendimiento[clave] = {"utiles": n, "ceros": 0 if n else anterior.get("ceros", 0) + 1, "fecha": hoy}
    limite = (date.fromisoformat(hoy) - timedelta(days=dias)).isoformat()
    for clave in [k for k, r in rendimiento.items() if (r.get("fecha") or "") < limite]:
        del rendimiento[clave]
    return rendimiento


def sirve_a_corta(v):
    """Contrato v40: True si una vacante guardada es de un cargo y un país de alguna persona que va corta (o es nueva).
    La relectura de descripciones empieza por estas: sin descripción no se sabe el idioma y no se entrega."""
    familias_v = {f.get("familia") for f in v.get("familias") or [] if isinstance(f, dict)}
    paises_v = set(v.get("paises") or []) | set(v.get("paises_mundo") or [])
    return any(p.get("corto") and p["familia"] in familias_v and (v.get("alcance_mundial") or paises_v & p["lugares"])
               for p in _PERSONAS)


def dias_busqueda(clave, ultima, hoy, max_dias):
    """Días hacia atrás que pide una búsqueda. Repetida, solo lo publicado desde la vez anterior; pero si esa vez no dejó
    nada útil (`ceros`), los `max_dias` completos: lo que trajo pudo perderse (17 nov, caso Danna: la limpieza
    archivaba lo de fuera de LATAM y, al repetir, Chicago solo pedía el último día)."""
    if not ultima or (_RENDIMIENTO.get(clave) or {}).get("ceros"):
        return max_dias
    from datetime import datetime
    return min(max_dias, max(1, (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days + 1))


def _claves_lugar(lugar):
    """«CO:REMOTO», «REMOTO_CO:ES», «CIUDAD_BOGOTA» → el lugar, sin sufijo y su país, para casarlo con una persona."""
    base = str(lugar).split(":")[0]
    claves = {str(lugar), base}
    if base.startswith("REMOTO_") and len(base) == 9:
        claves.add(base[7:])
    return claves


def de_personas(combinaciones):
    """Contrato v40: {índice de persona: [combinaciones]} de las que le sirven a cada persona."""
    salida = {}
    for i, persona in enumerate(_PERSONAS):
        salida[i] = [c for c in combinaciones if c[0] == persona["familia"] and _claves_lugar(c[2]) & persona["lugares"]]
    return salida


def _por_personas(combinaciones, estado, hoy, prioritarias):
    """Turnos ponderados entre personas: en cada turno avanza la persona con menos búsquedas para su peso, y toma su
    combinación menos reciente que aún no se haya tomado. Una búsqueda compartida sirve a todas sus personas y cuenta
    como turno para cada una: así nadie acapara y quien no comparte lugares (p. ej. Emiratos) recibe su parte.
    Lo que no es de ninguna persona sigue después con el reparto anterior."""
    def azar(clave):
        return hashlib.sha256(f"{hoy}|{clave}".encode()).hexdigest()

    def orden(c):
        clave = f"{c[0]}@{c[2]}"
        baja = (_RENDIMIENTO.get(clave) or {}).get("ceros", 0) >= CEROS_PARA_BAJAR
        return (baja, not va_primero(c[0], c[2]), estado.get(clave, ""), 0 if "REMOTO" in str(c[2]) else 1, azar(c[2]))

    suyas = de_personas(combinaciones)
    sirve = defaultdict(list)  # combinación → personas a las que sirve
    for i, lista in suyas.items():
        for c in lista:
            sirve[id(c)].append(i)
    def cola(i, lista):
        # Primero sus lugares principales (donde vive y sus regiones), después el resto por antigüedad.
        principales = set(_PERSONAS[i].get("principales") or ())
        return deque(sorted(lista, key=lambda c: (not (_claves_lugar(c[2]) & principales), orden(c))))

    colas = {i: cola(i, lista) for i, lista in suyas.items() if lista}
    pase = {i: 0.0 for i in colas}
    tomadas, salida = set(), []
    while colas:
        i = min(colas, key=lambda k: (pase[k], -_PERSONAS[k]["peso"], k))
        while colas[i] and id(colas[i][0]) in tomadas:
            colas[i].popleft()
        if not colas[i]:
            del colas[i]
            continue
        c = colas[i].popleft()
        tomadas.add(id(c))
        salida.append(c)
        for j in sirve[id(c)]:  # una búsqueda compartida es un turno para cada persona a la que sirve
            if j in pase:
                pase[j] += 1 / _PERSONAS[j]["peso"]
    resto = [c for c in combinaciones if id(c) not in tomadas]
    return salida + (_repartir_familias(resto, estado, hoy, prioritarias) if resto else [])


def repartir(combinaciones, estado, hoy, prioritarias=()):
    """Contrato v40: con personas configuradas (modo panel), turnos ponderados por persona (`_por_personas`).
    Sin ellas, una consulta por familia en cada vuelta (`_repartir_familias`)."""
    if _PERSONAS:
        return _por_personas(list(combinaciones), estado, hoy, prioritarias)
    return _repartir_familias(combinaciones, estado, hoy, prioritarias)


def _repartir_familias(combinaciones, estado, hoy, prioritarias=()):
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
