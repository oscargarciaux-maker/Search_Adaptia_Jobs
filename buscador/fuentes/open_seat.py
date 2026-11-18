"""Open Seat (https://open-seat.github.io, 17 nov, sugerida por Oscar): lista pública de empresas que contratan diseño,
producto, desarrollo y datos en Argentina y LATAM, con su sistema de postulación (Greenhouse, Lever, Ashby…).

No se toman sus avisos: su archivo solo trae un resumen corto y la entrega necesita la descripción completa. Se toma su
lista de empresas (`data/companies.json`) y sus portales se leen con `ats.py`, que trae la ficha completa, la fecha y
detecta los cierres. Una sola descarga por búsqueda; sin sesión ni claves.
"""
import re

from buscador.fuentes import ats

NOMBRE = "Open Seat"
URL_EMPRESAS = "https://open-seat.github.io/data/companies.json"
# El slug va dentro de una dirección web (`ats.url_api`): solo letras, números, punto, guion y guion bajo.
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def tableros(cliente, hoy):
    """(filas para `ats.buscar` con origen «Open Seat», estadísticas). Ignora sistemas que no sabemos leer y slugs
    raros. Si la lista no se puede leer, no devuelve nada: la búsqueda sigue con los portales de siempre."""
    datos = cliente.json(URL_EMPRESAS)
    lista = datos.get("companies") if isinstance(datos, dict) else datos
    if not isinstance(lista, list):
        return [], {"error": "lista de empresas no disponible"}
    filas, omitidas = {}, 0
    for c in lista:
        if not isinstance(c, dict):
            continue
        sistema = str(c.get("ats") or "").strip().lower()
        slug = str(c.get("slug") or "").strip()
        nombre = " ".join(str(c.get("name") or slug).split())[:120]
        if sistema not in ats.SISTEMAS or not _SLUG.match(slug):
            omitidas += 1
            continue
        filas.setdefault((sistema, slug.lower()), {"empresa": nombre, "sistema": sistema, "slug": slug,
                                                    "origen": NOMBRE, "agregada": hoy})
    return list(filas.values()), {"empresas": len(lista), "portales": len(filas), "omitidas": omitidas}
