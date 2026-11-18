"""Elempleo (Colombia): portal donde se postula en el mismo sitio. Sin sesión ni cookies. PR 1b (16 nov).

Se leen solo rutas públicas que su robots.txt no bloquea: la búsqueda `/co/ofertas-empleo/trabajo-<cargo>` y la ficha
`/co/ofertas-trabajo/...`. La lista sale del `ItemList` (schema.org) de la búsqueda y cada ficha trae su `JobPosting`:
fecha real de publicación (`datePosted`), cierre (`validThrough`), empresa, ciudad, si es remota (`TELECOMMUTE`),
desde qué país se postula (`applicantLocationRequirements`) y salario. Nada se inventa: lo que la ficha no dice queda
vacío. Como Computrabajo, rota las familias y cada corrida toma las que hace más tiempo no se revisan.
"""
import html
import time
from datetime import datetime, timezone

from buscador import cobertura
from buscador.fuentes import jobposting
from buscador.fuentes.computrabajo import slug

NOMBRE = "Elempleo"
BASE = "https://www.elempleo.com"
PAISES = {"CO"}


# Contrato v44: el JobPosting se lee con el lector común (también para Hireline y Magneto).
_bloques = jobposting.bloques
_texto = jobposting.texto
_fecha = jobposting.fecha
_salario = jobposting.salario


def tarjetas(pagina):
    """[(enlace sin parámetros, título)] del `ItemList` de una página de resultados."""
    salida = []
    for b in _bloques(pagina):
        if b.get("@type") != "ItemList":
            continue
        for elemento in b.get("itemListElement") or []:
            item = (elemento or {}).get("item") or {}
            enlace = str(item.get("@id") or "").split("?")[0]
            if "/ofertas-trabajo/" in enlace and item.get("name"):
                salida.append((enlace, html.unescape(str(item["name"])).strip()))
    return salida


def ficha(pagina, hoy):
    """Datos del `JobPosting` de la ficha, o None si no lo trae. `cerrada` si `validThrough` ya pasó."""
    return jobposting.ficha(pagina, hoy, "CO")


def buscar(cliente, mapa, estado, presupuesto, hoy=None, max_fichas=80, reloj=time.monotonic, limite_segundos=None,
           prioritarias=()):
    """Familias del panel con algún perfil en Colombia (o todas en modo heredado). Devuelve (vacantes crudas,
    estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    # Portal en español: con títulos en español del cargo (perfiles solo en español) se rota solo entre ellos.
    todas = [(f["id"], f.get("consultas_es") or cobertura.consultas(f), "CO", {}) for f in mapa
             if not f.get("paises_objetivo") or PAISES & set(f["paises_objetivo"])]
    todas = cobertura.repartir(todas, estado, hoy, prioritarias)
    avisos, vistos = [], set()
    hechas = fallidas = seguidas = 0
    for familia, consultas, _, _ in todas:
        if hechas >= presupuesto or seguidas >= 4 or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        siguiente = cobertura.siguiente_busqueda(consultas, hoy, 1, f"{familia}@CO", estado)
        if siguiente is None or siguiente[1]:  # contrato v47: ya se buscaron hoy todos sus nombres (lee una página)
            continue
        consulta = siguiente[0][0]
        r = cliente.get(f"{BASE}/co/ofertas-empleo/trabajo-{slug(consulta)}")
        hechas += 1
        if r is None or r.status_code != 200:
            fallidas += 1
            seguidas += 1
            continue
        seguidas = 0
        for enlace, titulo in tarjetas(r.text):
            if enlace not in vistos:
                vistos.add(enlace)
                avisos.append({"enlace": enlace, "titulo": titulo, "familia": familia})
        estado[f"{familia}@CO"] = hoy
        estado[cobertura.clave_consulta(f"{familia}@CO", [consulta])] = hoy
    avisos.sort(key=lambda a: a["familia"] not in prioritarias)
    crudas, leidas = jobposting.leer_fichas(cliente, [(a["enlace"], a["titulo"], "CO") for a in avisos], hoy, NOMBRE,
                                            max_fichas, reloj, inicio, limite_segundos)
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), **leidas,
                    "combinaciones_total": len(todas)}
