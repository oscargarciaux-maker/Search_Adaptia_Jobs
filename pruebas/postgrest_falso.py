"""Ayuda para los Supabase simulados de las pruebas (P-12.1).

`repositorio.paginar` lee por páginas ordenadas por una clave (`order=<clave>` y, desde la segunda, `<clave>=gt.…`) y
solo termina al recibir una página VACÍA. Muchos simuladores devuelven siempre la misma lista, sin la clave en cada
fila y sin mirar `gt.`. `como_postgrest` los hace responder como PostgREST a esas lecturas: la primera página trae
todas sus filas (cada una con su clave) y la siguiente llega vacía. Las demás peticiones no cambian."""
from functools import wraps


def _clave(params):
    orden = str((params or {}).get("order") or "")
    return orden if orden and "." not in orden and "," not in orden else None


def una_pagina(params, filas):
    """La respuesta de un simulador a una lectura por páginas: todo en la primera y vacía la siguiente."""
    clave = _clave(params)
    if not clave or not isinstance(filas, list):
        return filas
    if str(params.get(clave, "")).startswith("gt."):
        return []
    return [f if not isinstance(f, dict) or clave in f else {**f, clave: f"fila-{n:06d}"} for n, f in enumerate(filas)]


def como_postgrest(pedir):
    """Decora el `pedir(self, metodo, ruta, **op)` de un simulador."""
    @wraps(pedir)
    def envuelto(*args, **op):
        if next(a for a in args if isinstance(a, str)) != "GET":
            return pedir(*args, **op)
        clave, params = _clave(op.get("params")), op.get("params") or {}
        if clave and str(params.get(clave, "")).startswith("gt."):
            return []  # la página siguiente, sin llamar al simulador (no cuenta como otra lectura)
        return una_pagina(params, pedir(*args, **op))
    return envuelto
