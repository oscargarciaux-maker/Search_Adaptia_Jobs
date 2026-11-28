"""Expansión abierta sin IA: variantes, mapa opcional y vocabulario público ESCO."""
from functools import lru_cache
from pathlib import Path
import re

import requests
from rapidfuzz import fuzz, process
import yaml

from buscador import familias, normalizar

ESCO = "https://ec.europa.eu/esco/api"


def variantes(cargo):
    base = " ".join(cargo.split())
    compacto = re.sub(r"\bfront[\s-]*end\b", "frontend", base, flags=re.I)
    compacto = re.sub(r"\bback[\s-]*end\b", "backend", compacto, flags=re.I)
    salida = [base, compacto]
    for termino in ("frontend", "backend", "fullstack"):
        if termino in compacto.lower():
            salida += [f"{termino} developer", f"{termino} engineer", f"desarrollador {termino}"]
    return list(dict.fromkeys(salida))


# PR 1b (16 nov), movido aquí en v44 y a `datos/titulos_idioma.yaml` en v49: palabras con que empiezan los títulos en
# español y palabras propias. Sin IA: listas editables. v44: un título con palabras propias del portugués no cuenta como
# español (antes «designer de produto» y «gerente de produto» pasaban por la palabra «de» y gastaban turnos de búsqueda).
@lru_cache(maxsize=1)
def titulos_idioma():
    ruta = Path(__file__).resolve().parent.parent / "datos" / "titulos_idioma.yaml"
    crudo = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {k: tuple(dict.fromkeys(normalizar.texto(x) for x in crudo.get(k) or [] if normalizar.texto(x)))
            for k in ("inicio", "palabras", "portugues", "inicio_tambien_ingles", "ingles")}


@lru_cache(maxsize=8192)
def en_portugues(titulo):
    """18 nov: título con palabras propias del portugués («designer de produto»): no se sugiere (solo es/en)."""
    t = normalizar.texto(titulo)
    return any(normalizar.contiene_frase(t, x) for x in titulos_idioma()["portugues"])


@lru_cache(maxsize=8192)
def en_espanol(titulo):
    """Título en español: empieza como uno («Diseñador…») o trae palabras propias («Product Manager IA»), y no trae
    palabras del portugués. Contrato v49: «Director of Engineering» empieza igual que en español pero trae palabras
    del inglés: no cuenta."""
    t = normalizar.texto(titulo)
    if en_portugues(titulo):
        return False
    listas = titulos_idioma()
    con_ingles = any(normalizar.contiene_frase(t, x) for x in listas["ingles"])
    for x in listas["inicio"]:
        if t == x or t.startswith(x + " "):
            if not (x in listas["inicio_tambien_ingles"] and con_ingles):
                return True
    return any(normalizar.contiene_frase(t, x) for x in listas["palabras"])


def _familias_de(base):
    """Familias del mapa donde `base` (título normalizado) es el id, un título exacto o uno similar, con su nivel."""
    coincidencias = []
    for orden, f in enumerate(familias.mapa_base()):
        nivel = 0 if base == normalizar.texto(f["id"]) else next(
            (i for i, g in enumerate(("exacto", "similar")) if base in f["_titulos"][g]), None)
        if nivel is not None:
            coincidencias.append((nivel, orden, f))
    return coincidencias


@lru_cache(maxsize=1)
def glosario():
    ruta = Path(__file__).resolve().parent.parent / "datos" / "glosario_cargos.yaml"
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def _bonito(titulo):
    """«gerente de producto» → «Gerente de Producto»; respeta siglas ya en mayúscula (UX, IA)."""
    menores = set(glosario().get("minusculas") or [])
    palabras = titulo.split()
    return " ".join(p if (p.isupper() and len(p) > 1) or (i and p.lower() in menores) else p[:1].upper() + p[1:]
                    for i, p in enumerate(palabras))


@lru_cache(maxsize=512)
def modificador(cargo):
    """Contrato v44/v49: para un cargo que no está en el mapa pero sí su oficio base con un modificador del glosario
    («AI Product Manager» = AI + Product Manager), devuelve (modificador del glosario, familia base). Si el cargo ya
    está en el mapa o no trae modificador, (None, None)."""
    base = normalizar.titulo_base(cargo)
    if not base or _familias_de(base):
        return None, None
    for mod in glosario().get("modificadores") or []:
        for forma in sorted(mod.get("en") or [], key=len, reverse=True):
            clave = normalizar.texto(forma)
            if not normalizar.contiene_frase(base, clave):
                continue
            resto = " ".join(re.sub(rf"(?<![a-z0-9]){re.escape(clave)}(?![a-z0-9])", " ", base).split())
            coincidencias = _familias_de(resto)
            if coincidencias:
                return mod, min(coincidencias, key=lambda x: x[:2])[2]
    return None, None


def compuestos(cargo):
    """Contrato v44: para un cargo compuesto (`modificador`), devuelve (sugerencias en español, títulos del oficio base,
    id de la familia base). Sin IA: combina los nombres en español del mapa con las formas en español del modificador.
    Si el cargo ya está en el mapa o no trae modificador, devuelve listas vacías."""
    mod, f = modificador(cargo)
    if not mod:
        return [], [], None
    formas = [normalizar.texto(x) for x in [*(mod.get("en") or []), *(mod.get("es") or [])]]
    espanol = [x for x in f.get("exactos", []) if en_espanol(x)
               and not any(normalizar.contiene_frase(normalizar.texto(x), y) for y in formas if y)]
    ingles = [x for x in f.get("exactos", []) if not en_espanol(x)]
    # El nombre más común en español, el original en inglés y dos más en español, cada uno con cada forma.
    titulos = [x for x in (espanol[:1] + ingles[:1] + espanol[1:3]) if x]
    salida = [_bonito(f"{titulo} {sufijo}") for titulo in titulos for sufijo in mod.get("es") or []]
    vistos, unicos = set(), []
    for x in salida:
        if normalizar.texto(x) not in vistos:
            vistos.add(normalizar.texto(x))
            unicos.append(x)
    return unicos[:int(glosario().get("maximo") or 12)], [_bonito(x) for x in f.get("exactos", [])][:8], f["id"]


@lru_cache(maxsize=512)
def espanol_del_mapa(nombre):
    """Contrato v44 (decisión de Oscar: «usarlos solos»): títulos exactos en español de la familia del mapa a la que
    pertenece el cargo. Se usan para buscar (consultas_es) y para reconocer al elegir. Desde v50 son una parte de
    `hermanos_es`, que suma los compuestos del glosario."""
    base = normalizar.titulo_base(nombre)
    coincidencias = _familias_de(base) if base else []
    if not coincidencias:
        return ()
    salida = []
    # Solo si el cargo es un título exacto de la familia (un cargo que es «similar» de una familia amplia, como QA Lead
    # en QA, no hereda sus títulos), solo los exactos (los similares se sugieren) y nunca de una sola palabra
    # («Programador», «Redactor»: aceptarían «Programador CNC» en cualquier cargo).
    for nivel, _, f in sorted(coincidencias, key=lambda x: x[:2]):
        if nivel == 0:
            salida += [x for x in f.get("exactos", []) if en_espanol(x) and len(normalizar.titulo_base(x).split()) > 1]
    return tuple(dict.fromkeys(salida))


@lru_cache(maxsize=512)
def hermanos_es(nombre):
    """Contrato v50 (decisión de Oscar del 26 nov: «aplicar solos, con control»): los nombres en español que un cargo
    usa sin que el operador los añada, para buscar y para reconocer avisos. Son el mismo oficio con otro nombre: los
    títulos exactos en español de su familia del mapa (`espanol_del_mapa`, v44) y, para un cargo compuesto («AI Product
    Manager»), los que arma el glosario (`compuestos`). Los «similares» del mapa son oficios vecinos («Analista de
    operaciones» para Data Analyst): siguen siendo sugerencias. El control es el de v49: sin las funciones del cargo en
    la descripción la vacante va al final, y con señal de otro oficio va a «Por confirmar».
    Devuelve ((nombre, origen), …) con origen «mapa» o «glosario»."""
    salida = [(x, "mapa") for x in espanol_del_mapa(nombre)] + [(x, "glosario") for x in compuestos(nombre)[0]]
    vistos, unicos = set(), []
    for x, origen in salida:
        clave = normalizar.titulo_base(x)
        if clave and clave not in vistos:
            vistos.add(clave)
            unicos.append((x, origen))
    return tuple(unicos)


def hermanos_del_cargo(cargo):
    """Los `hermanos_es` de un cargo que el operador no excluyó (un nombre que contiene un término excluido no se usa)
    y que no tiene ya entre sus términos."""
    excluidos = [_texto(x) for x in cargo.get("terminos_excluidos") or [] if _texto(x)]
    propios = {_base(x) for x in [cargo.get("nombre") or "", *(cargo.get("terminos_exactos") or []),
                                  *(cargo.get("terminos_similares") or [])]}
    return [(x, origen) for x, origen in hermanos_es(cargo.get("nombre") or "")
            if _base(x) not in propios and not any(normalizar.contiene_frase(_texto(x), e) for e in excluidos)]


def sugerir(cargo, sesion=None, consultar_esco=True, definicion=None):
    """Nombres sugeridos para un cargo. `definicion` (contrato v50): sus términos y excluidos tal como están en el
    borrador, para decir qué nombres en español usa solos (`hermanos_es`) con la misma regla del motor."""
    base = normalizar.titulo_base(cargo)
    exactos, similares, evidencia = variantes(cargo), [], []
    # El mapa existente es una ayuda, nunca un requisito para aceptar un cargo nuevo. Solo aportan las familias donde
    # el cargo es título exacto o similar; «cercano» señala un oficio vecino (motion designer para editor de video),
    # no un equivalente. Se usa el grado más fuerte encontrado para no mezclar oficios distintos.
    coincidencias = _familias_de(base)
    mejor = min((n for n, _, _ in coincidencias), default=None)
    cercanos = []
    for nivel, _, f in sorted(coincidencias, key=lambda x: x[:2]):
        if nivel == mejor:
            (exactos if nivel == 0 else similares).extend(f.get("exactos", []))
            similares.extend(f.get("similares", []))
            cercanos.extend(f.get("cercanos", []))  # oficios vecinos: solo para ampliar (contrato v9)
    if coincidencias:
        evidencia.append("Equivalentes del mapa existente")
    if consultar_esco:
        try:
            cli = sesion or requests.Session()
            r = cli.get(ESCO + "/search", params={"text": cargo, "type": "occupation", "language": "es", "limit": 5}, timeout=8)
            r.raise_for_status()
            resultados = r.json().get("_embedded", {}).get("results", [])
            for resultado in resultados:
                titulo = resultado.get("title") or resultado.get("label") or ""
                if not isinstance(titulo, str) or fuzz.token_sort_ratio(base, normalizar.titulo_base(titulo)) < 86:
                    continue
                uri = resultado.get("uri", "")
                if not uri.startswith(("http://data.europa.eu/esco/occupation/", "https://data.europa.eu/esco/occupation/")):
                    continue
                for idioma in ("es", "en"):
                    detalle = cli.get(ESCO + "/resource/occupation", params={"uri": uri, "language": idioma}, timeout=8)
                    detalle.raise_for_status()
                    d = detalle.json()
                    for campo in ("preferredLabel", "alternativeLabel"):
                        labels = d.get(campo, {})
                        labels = labels.get(idioma, []) if isinstance(labels, dict) else labels
                        similares += [labels] if isinstance(labels, str) else labels if isinstance(labels, list) else []
                evidencia.append("ESCO, vocabulario ocupacional público")
                break
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            evidencia.append("ESCO no disponible; puedes completar términos desde la interfaz")
    claves, principales, limpios = set(), [], []
    for destino, terminos in ((principales, exactos), (limpios, similares)):
        for x in terminos:
            if isinstance(x, str) and 2 <= len(x) <= 120 and normalizar.titulo_base(x) not in claves \
                    and not en_portugues(x):
                claves.add(normalizar.titulo_base(x))
                destino.append(x)
    vecinos = []
    for x in cercanos:
        if isinstance(x, str) and 2 <= len(x) <= 120 and normalizar.titulo_base(x) not in claves:
            claves.add(normalizar.titulo_base(x))
            vecinos.append(x)
    # Contrato v44: nombres en español aparte, para mostrarlos primero. Los del mapa (curados) y, si el cargo es un
    # oficio con modificador («AI Product Manager»), las combinaciones del glosario. Y el oficio base, más amplio.
    combinados, base_titulos, familia_base = compuestos(cargo)
    if familia_base:
        evidencia.append("Nombres en español armados con el glosario (se usan solos)")
    # Contrato v50: lo que el cargo ya usa solo no se sugiere para añadir (ni aquí ni en «Qué hacer»).
    usados = hermanos_del_cargo({**{k: (definicion or {}).get(k) or [] for k in (
        "terminos_exactos", "terminos_similares", "terminos_excluidos")}, "nombre": cargo})
    solos = {normalizar.titulo_base(x) for x, _ in usados}
    en_es = []
    for x in [*[y for y in principales + limpios if en_espanol(y)], *combinados]:
        if normalizar.titulo_base(x) not in solos | {normalizar.titulo_base(y) for y in en_es}:
            en_es.append(x)
    amplios = [x for x in base_titulos if normalizar.titulo_base(x) not in claves]
    return {"terminos_exactos": principales[:30], "terminos_similares": limpios[:30], "terminos_cercanos": vecinos[:30],
            "terminos_es": en_es[:20], "terminos_base": amplios[:8], "familia_base": familia_base,
            # Contrato v50: los nombres en español que el cargo usa solos (no hace falta añadirlos).
            "hermanos_es": [_bonito(x) for x, _ in usados],
            "fuentes": list(dict.fromkeys(evidencia)) or ["Variantes de escritura"],
            "requiere_revision": not limpios and not combinados,
            "nota": "Revisa los términos antes de guardar; un equivalente no garantiza pertinencia de cada anuncio."}


# Los términos de un cargo se comparan contra miles de títulos: normalizarlos una sola vez (funciones puras).
_base = lru_cache(maxsize=32768)(normalizar.titulo_base)
_texto = lru_cache(maxsize=32768)(normalizar.texto)
_singular = lru_cache(maxsize=32768)(normalizar.singular)


def _clave_cargo(cargo):
    return (cargo.get("nombre") or "",
            *(tuple(cargo.get(k) or ()) for k in ("terminos_exactos", "terminos_similares", "terminos_cercanos")))


@lru_cache(maxsize=512)
def _contexto_propio(clave):
    """7.E: (familias del mapa del cargo, sus términos normalizados). Las familias son donde su nombre o alguno de sus
    términos es título exacto o similar, más la de su oficio base: un cargo de nombre libre con «tester» es de QA."""
    nombre, *listas = clave
    propios = frozenset(_base(x) for lista in listas for x in lista) - {""}
    suyas = {f["id"] for _, _, f in _familias_de(_base(nombre))}
    suyas |= {f["id"] for f in familias.mapa_base()
              if propios & (set(f["_titulos"]["exacto"]) | set(f["_titulos"]["similar"]))}
    _, base = modificador(nombre)
    if base:
        suyas.add(base["id"])
    return frozenset(suyas), propios


def _oficio_ajeno(texto, cargo, palabra):
    """7.E (27 nov): el nombre más largo de OTRO oficio del mapa que trae el título y que contiene `palabra`
    («penetration tester» es Ciberseguridad y contiene «tester»), si no es también un término del cargo; si no, ''.
    Así un término del cargo no basta cuando es parte del nombre de otro oficio: el nombre más largo dice el oficio,
    como «New Mexico» no es México. Sin familia del mapa conocida para el cargo, no se aplica."""
    suyas, propios = _contexto_propio(_clave_cargo(cargo))
    if not suyas:
        return ""
    for f in familias.mapa_base():
        if f["id"] in suyas:
            continue
        for patron in (f["_re"]["exacto"], f["_re"]["similar"]):
            for m in patron.finditer(texto) if patron else ():
                nombre = m.group(0)
                # P-7.F: también en singular, para la vuelta de plurales («analista de prueba»)
                if nombre not in propios and any(len(x) > len(palabra) and normalizar.contiene_frase(x, palabra)
                                                 for x in (nombre, _base(_singular(nombre)))):
                    return nombre
    return ""


def _excluido_del_mapa(completo, cargo):
    """7.E: el título trae un `excluir` de una familia del mapa del cargo («pentesting» en QA)."""
    suyas, _ = _contexto_propio(_clave_cargo(cargo))
    return any(f["_excluir"] and f["_excluir"].search(completo) for f in familias.mapa_base() if f["id"] in suyas)


def _cuenta(texto, canon, cargo, base):
    """El término del cargo está en el título y no es parte de un nombre más largo de otro oficio (en el título tal cual
    ni en singular: «Analista de Datos» también es «analista de dato»). Un término de una sola palabra no basta nunca
    dentro de otro oficio (7.E). Uno de varias palabras solo deja de bastar si ese nombre más largo trae además un
    `excluir` de la familia del cargo en el mapa (P-7.F, 27 nov): «analista de pruebas» (QA) dentro de «analista de
    pruebas de seguridad» (Ciberseguridad, y QA excluye «pruebas de seguridad») no es QA, pero «marketing manager»
    dentro de «product marketing manager» sigue siendo Marketing Manager."""
    if not canon or not normalizar.contiene_frase(texto, canon):
        return False
    for t in dict.fromkeys((base, texto)):
        ajeno = _oficio_ajeno(t, cargo, canon)
        if ajeno and (" " not in canon or _excluido_del_mapa(ajeno, cargo)):
            return False
    return True


def grado(titulo, cargo, cercanos=False):
    """(grado, evidencia). `cercanos=True` reconoce además los oficios vecinos del cargo (contrato v9), que solo
    sirven para ampliar a un perfil que no llega al mínimo."""
    base = _base(titulo)
    if not base:
        return None, None
    completo = _texto(titulo)
    if any(normalizar.contiene_frase(completo, _texto(x)) for x in cargo.get("terminos_excluidos", [])):
        return None, None
    for campo, valor in (("terminos_exactos", "exacto"), ("terminos_similares", "similar")):
        terminos = [cargo["nombre"], *cargo.get(campo, [])] if campo == "terminos_exactos" else cargo.get(campo, [])
        for t in terminos:
            if _cuenta(base, _base(t), cargo, base):
                return valor, {"regla": "término de cargo", "termino": t, "grado": valor}
    # Contrato v49: los plurales cuentan («Desarrolladores Full Stack», «QA Engineers»), como segunda oportunidad.
    plural = _base(_singular(base))  # y de nuevo el género: «desarrolladoras» → «desarrolladora» → «desarrollador»
    if plural != base:
        for campo, valor in (("terminos_exactos", "exacto"), ("terminos_similares", "similar")):
            terminos = [cargo["nombre"], *cargo.get(campo, [])] if campo == "terminos_exactos" else cargo.get(campo, [])
            for t in terminos:
                if _cuenta(plural, _base(_singular(_base(t))), cargo, base):
                    return valor, {"regla": "término de cargo", "termino": t, "grado": valor}
    # 7.E: «Analista de Pentesting» se parece a «analista de testing», pero trae «pentesting», un excluido de la familia
    # del cargo en el mapa. La similitud textual es lo más débil: no basta.
    if len(base) >= 6 and not _excluido_del_mapa(completo, cargo):
        opciones = [cargo["nombre"], *cargo.get("terminos_exactos", []), *cargo.get("terminos_similares", [])]
        for t in opciones:
            puntaje = fuzz.token_sort_ratio(base, _base(t))
            if puntaje >= 90:
                return "similar", {"regla":"similitud textual", "termino":t, "grado":"similar", "similitud_textual":round(puntaje)}
    # Contrato v44: los títulos en español de la familia del mapa del cargo (los mismos con que se busca en español).
    # Contrato v50: y los nombres que arma el glosario para un cargo compuesto, que también se usan solos.
    for t, origen in hermanos_es(cargo.get("nombre") or ""):
        canon = _base(t)
        if _cuenta(base, canon, cargo, base):  # P-7.F: con la misma guarda del nombre más largo
            regla = "título en español del mapa" if origen == "mapa" else "nombre hermano en español"
            return "similar", {"regla": regla, "termino": t, "grado": "similar"}
    # P-14.2: los términos ampliados por el LLM, solo si el título los contiene (con la guarda del nombre más largo y
    # la vuelta de plurales), nunca por similitud textual.
    for t in cargo.get("terminos_ampliados") or ():
        if _cuenta(base, _base(t), cargo, base) or (plural != base and _cuenta(plural, _base(_singular(_base(t))),
                                                                                cargo, base)):
            return "similar", {"regla": "término ampliado", "termino": t, "grado": "similar"}
    if cercanos:
        for t in cargo.get("terminos_cercanos", []):
            canon = _base(t)
            if canon and normalizar.contiene_frase(base, canon):
                return "cercano", {"regla": "cargo cercano", "termino": t, "grado": "cercano"}
    return None, None


# P-14.2 (IA acotada, decisión de Oscar del 28 nov): un LLM PROPONE nombres del mismo oficio para buscar
# (`panel/ampliados.py`). Aquí se filtran con las reglas deterministas de siempre; quien decide si un aviso sirve sigue
# siendo `grado`, que solo los reconoce contenidos en el título (`_contiene`).
MAX_AMPLIADOS = 8  # por idioma: cada término nuevo reparte los turnos de búsqueda del cargo
_CARACTERES = re.compile(r"^[^\W\d_][\w .,/&+#()'-]*$")


def _familia_propia(nombre):
    """Las familias del mapa del oficio del cargo: donde su nombre es el id o un título exacto (o similar si no es
    exacto en ninguna), o la de su oficio base si es compuesto. Más estrecho que `_contexto_propio`, que también suma
    las familias de sus términos (un Product Manager con «product lead» tocaría Product Owner)."""
    coincidencias = _familias_de(_base(nombre)) if nombre else []
    if coincidencias:
        mejor = min(n for n, _, _ in coincidencias)
        return frozenset(f["id"] for n, _, f in coincidencias if n == mejor)
    _, base = modificador(nombre or "")
    return frozenset({base["id"]}) if base else frozenset()


@lru_cache(maxsize=4096)
def _de_otro_oficio(clave, propia):
    """¿`clave` (título normalizado) es un título de OTRA familia del mapa, igual o casi igual (similitud ≥ 90, la
    misma que acepta `grado`)? «Product Owner» no amplía Product Manager, ni «Product Owners», casi igual. Un cargo
    que no está en el mapa no tiene familia propia: para él, cualquier título del mapa es de otro oficio (si fuera el
    suyo, el cargo estaría en el mapa)."""
    exactas = {f["id"] for _, _, f in _familias_de(clave)}
    if exactas:  # un título del mapa: vale si es también de su familia
        return not exactas & propia
    for f in familias.mapa_base():
        if f["id"] in propia:
            continue
        titulos = [*f["_titulos"]["exacto"], *f["_titulos"]["similar"]]
        if titulos and process.extractOne(clave, titulos, scorer=fuzz.token_sort_ratio, score_cutoff=90):
            return True
    return False


def filtrar_ampliados(propuesta, cargo, maximo=MAX_AMPLIADOS):
    """Los términos propuestos que se pueden usar, en su idioma: los de `es` deben reconocerse como título en español
    (`en_espanol`) y los de `en`, no (ni portugués). Fuera: de una sola palabra, con cifras o símbolos raros, los que
    el cargo ya usa (o sus hermanos en español), los que traen un excluido del operador o del mapa, y los que son el
    nombre de OTRO oficio del mapa (7.E: «Diseñador gráfico» no es «Diseñador UX»). Se aplica cada vez que se usan,
    con el cargo vigente: un excluido nuevo los saca sin volver a pedir nada."""
    if not isinstance(propuesta, dict):
        return []
    nombre = cargo.get("nombre") or ""
    vistos = {_base(x) for x in [nombre, *(cargo.get("terminos_exactos") or []),
                                 *(cargo.get("terminos_similares") or []),
                                 *(cargo.get("terminos_cercanos") or [])] if isinstance(x, str)}
    vistos |= {_base(x) for x, _ in hermanos_es(nombre)}
    excluidos = [_texto(x) for x in [*(cargo.get("terminos_excluidos") or []), *(cargo.get("excluir_mapa") or [])]
                 if isinstance(x, str) and _texto(x)]
    propia = _familia_propia(nombre)
    salida = []
    for idioma in ("es", "en"):
        tomados = 0
        for t in propuesta.get(idioma) or []:
            if tomados >= maximo:
                break
            if not isinstance(t, str):
                continue
            t = " ".join(t.split()).strip(" .,;")
            clave = _base(t)
            if not (4 <= len(t) <= 60) or not _CARACTERES.match(t) or len(clave.split()) < 2 or clave in vistos:
                continue
            if (idioma == "es") != en_espanol(t) or en_portugues(t):
                continue
            if any(normalizar.contiene_frase(_texto(t), e) for e in excluidos):
                continue
            if _de_otro_oficio(clave, propia):
                continue
            vistos.add(clave)
            salida.append(t)
            tomados += 1
    return salida
