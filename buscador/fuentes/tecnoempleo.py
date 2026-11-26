"""Tecnoempleo (España, tecnología): portal donde se postula en el mismo sitio, con cuenta de candidato. Contrato v50
§3 (decisión de Oscar del 26 nov: pasa de la lista de agregadores a la de portales). Sin sesión ni cookies.

Se leen dos rutas públicas: la búsqueda `/ofertas-trabajo/?te=<cargo>` (enlaces y títulos de las fichas) y la ficha
`/<aviso>/<tecnologías>/rf-<id>`, que trae su `JobPosting` (schema.org): fecha de publicación, empresa, ciudad y
descripción. Como Elempleo, usa el lector común (`jobposting`). Nada se inventa: lo que la ficha no dice queda vacío.
Solo se lee la ficha de un aviso cuyo título es de un cargo buscado (v49). El enlace se comprueba como cualquier otro."""
import html
import re
import time
from datetime import datetime, timezone

from buscador import cobertura
from buscador.fuentes import jobposting

NOMBRE = "Tecnoempleo"
BUSQUEDA = "https://www.tecnoempleo.com/ofertas-trabajo/"
PAISES = {"ES"}
_FICHA = re.compile(r'<a[^>]+href="(https://www\.tecnoempleo\.com/[a-z0-9-]+/[a-z0-9-]+/rf-[a-z0-9]+)"[^>]*>(.*?)</a>',
                    re.S)


def tarjetas(pagina):
    """[(enlace de la ficha, título)] de una página de resultados, sin repetir (cada aviso enlaza varias veces)."""
    salida = {}
    for enlace, interior in _FICHA.findall(pagina or ""):
        titulo = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", interior)).split())
        if titulo and enlace not in salida:
            salida[enlace] = titulo
    return list(salida.items())


def combinaciones(mapa):
    """(familia, consultas, lugar, {}) de los cargos con alguien que trabajaría en España (o todos en modo heredado).
    Como en InfoJobs: los títulos en español tienen su turno («ES:ES») si alguien de España acepta español."""
    salida = []
    for f in mapa:
        if "paises_objetivo" in f and not PAISES & set(f["paises_objetivo"] or []):
            continue
        es = list(f.get("consultas_es") or [])
        resto = [c for c in cobertura.consultas(f) if c not in es]
        if es and ("paises_es" not in f or PAISES & set(f["paises_es"])):
            salida.append((f["id"], es, "ES:ES", {}))
        elif es and not resto:
            salida.append((f["id"], es, "ES", {}))
        if resto:
            salida.append((f["id"], resto, "ES", {}))
    return salida


def buscar(cliente, mapa, estado, presupuesto, hoy=None, max_fichas=80, reloj=time.monotonic, limite_segundos=None,
           prioritarias=()):
    """Busca los nombres de cada cargo (uno por búsqueda, cada uno con su clave; lo ya buscado hoy no se repite) y lee
    las fichas de los títulos de un cargo buscado. Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    todas = cobertura.repartir(combinaciones(mapa), estado, hoy, prioritarias)
    turnos = [(k, c) for c in todas for k in range(len(c[1]))]
    turnos.sort(key=lambda t: t[0])  # estable: el primer nombre de cada combinación, luego el segundo…
    avisos, vistos = [], set()
    hechas = fallidas = seguidas = 0
    for k, (familia, consultas, lugar, _) in turnos:
        if hechas >= presupuesto or seguidas >= 3 or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        b = cobertura.siguiente_busqueda(consultas, hoy, 1, f"{familia}@{lugar}", estado, desfase=k, paginada=False)
        if b is None or estado.get(b.clave_terminos) == hoy:  # ya se buscó hoy con ese nombre
            continue
        r = cliente.get(BUSQUEDA, params={"te": b.terminos[0]})
        hechas += 1
        if r is None or r.status_code != 200:
            fallidas += 1
            seguidas += 1
            continue
        seguidas = 0
        cobertura.anotar_busqueda("tecnoempleo", familia, lugar)
        hallados = tarjetas(r.text)
        if hallados:  # una página sin avisos (o un bloqueo con 200) no cuenta como buscada: se reintenta más tarde
            cobertura.anotar_hecha(estado, b, hoy)
        for enlace, titulo in hallados:
            if enlace not in vistos:
                vistos.add(enlace)
                avisos.append({"enlace": enlace, "titulo": titulo, "familia": familia})
    es_del_cargo = cobertura.titulos_del_cargo(mapa)
    del_cargo = [a for a in avisos if es_del_cargo(a["titulo"], a["familia"])]
    del_cargo.sort(key=lambda a: a["familia"] not in prioritarias)  # estable
    crudas, leidas = jobposting.leer_fichas(cliente, [(a["enlace"], a["titulo"], "ES") for a in del_cargo], hoy, NOMBRE,
                                            max_fichas, reloj, inicio, limite_segundos)
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), "del_cargo": len(del_cargo),
                    **leidas, "combinaciones_total": len(todas)}
