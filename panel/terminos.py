"""Expansión abierta sin IA: variantes, mapa opcional y vocabulario público ESCO."""
from functools import lru_cache
from pathlib import Path
import re

import requests
from rapidfuzz import fuzz
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


# PR 1b (16 nov), movido aquí en v44: palabras con que empiezan los títulos en español y palabras propias. Sin IA:
# listas editables. v44: un título con palabras propias del portugués no cuenta como español (antes «designer de
# produto» y «gerente de produto» pasaban por la palabra «de» y gastaban turnos de búsqueda).
INICIO_ES = ("diseñador", "diseñadora", "desarrollador", "desarrolladora", "analista", "ingeniero", "ingeniera",
             "gerente", "jefe", "jefa", "lider", "líder", "coordinador", "coordinadora", "especialista", "gestor",
             "gestora", "consultor", "consultora", "programador", "programadora", "probador", "redactor", "redactora",
             "responsable", "director", "directora", "encargado", "encargada", "asistente", "auxiliar", "tester de",
             "dueño", "administrador", "administradora", "arquitecto", "arquitecta", "experto", "experta")
PALABRAS_ES = ("ia", "inteligencia artificial", "de", "del", "y", "con", "para", "datos", "pruebas", "calidad",
               "producto", "proyectos", "ventas", "mercadeo")
PALABRAS_PT = ("produto", "desenvolvedor", "desenvolvedora", "dados", "engenheiro", "engenheira", "projetos",
               "vendas", "gestao", "designer de", "testes", "qualidade", "pleno")


@lru_cache(maxsize=8192)
def en_portugues(titulo):
    """18 nov: título con palabras propias del portugués («designer de produto»): no se sugiere (solo es/en)."""
    t = normalizar.texto(titulo)
    return any(normalizar.contiene_frase(t, normalizar.texto(x)) for x in PALABRAS_PT)


@lru_cache(maxsize=8192)
def en_espanol(titulo):
    """Título en español: empieza como uno («Diseñador…») o trae palabras propias («Product Manager IA»), y no trae
    palabras del portugués."""
    t = normalizar.texto(titulo)
    if en_portugues(titulo):
        return False
    return any(t == normalizar.texto(x) or t.startswith(normalizar.texto(x) + " ") for x in INICIO_ES) or \
        any(normalizar.contiene_frase(t, normalizar.texto(x)) for x in PALABRAS_ES)


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
    """Contrato v44 (decisión de Oscar: «usarlos solos»): títulos en español de la familia del mapa a la que pertenece
    el cargo. Ya se usan para buscar (consultas_es); con esto también se reconocen al elegir. Solo títulos curados del
    mapa, nunca compuestos: esos solo se sugieren."""
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


def sugerir(cargo, sesion=None, consultar_esco=True):
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
        evidencia.append("Nombres en español armados con el glosario (revisa antes de añadir)")
    en_es = []
    for x in [*[y for y in principales + limpios if en_espanol(y)], *combinados]:
        if normalizar.titulo_base(x) not in {normalizar.titulo_base(y) for y in en_es}:
            en_es.append(x)
    amplios = [x for x in base_titulos if normalizar.titulo_base(x) not in claves]
    return {"terminos_exactos": principales[:30], "terminos_similares": limpios[:30], "terminos_cercanos": vecinos[:30],
            "terminos_es": en_es[:20], "terminos_base": amplios[:8], "familia_base": familia_base,
            "fuentes": list(dict.fromkeys(evidencia)) or ["Variantes de escritura"],
            "requiere_revision": not limpios and not combinados,
            "nota": "Revisa los términos antes de guardar; un equivalente no garantiza pertinencia de cada anuncio."}


# Los términos de un cargo se comparan contra miles de títulos: normalizarlos una sola vez (funciones puras).
_base = lru_cache(maxsize=32768)(normalizar.titulo_base)
_texto = lru_cache(maxsize=32768)(normalizar.texto)


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
            canon = _base(t)
            if canon and normalizar.contiene_frase(base, canon):
                return valor, {"regla": "término de cargo", "termino": t, "grado": valor}
    if len(base) >= 6:
        opciones = [cargo["nombre"], *cargo.get("terminos_exactos", []), *cargo.get("terminos_similares", [])]
        for t in opciones:
            puntaje = fuzz.token_sort_ratio(base, _base(t))
            if puntaje >= 90:
                return "similar", {"regla":"similitud textual", "termino":t, "grado":"similar", "similitud_textual":round(puntaje)}
    # Contrato v44: los títulos en español de la familia del mapa del cargo (los mismos con que se busca en español).
    for t in espanol_del_mapa(cargo.get("nombre") or ""):
        canon = _base(t)
        if canon and normalizar.contiene_frase(base, canon):
            return "similar", {"regla": "título en español del mapa", "termino": t, "grado": "similar"}
    if cercanos:
        for t in cargo.get("terminos_cercanos", []):
            canon = _base(t)
            if canon and normalizar.contiene_frase(base, canon):
                return "cercano", {"regla": "cargo cercano", "termino": t, "grado": "cercano"}
    return None, None
