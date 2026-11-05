"""Sube las filas de la entrega diaria a la tabla `ofertas` de Supabase (supabase/esquema.sql) por su API REST.

Necesita dos secretos de GitHub: SUPABASE_URL (https://<proyecto>.supabase.co) y SUPABASE_SECRET_KEY (la clave secreta
del proyecto: Project Settings > API Keys; también sirve la antigua service_role). Sin ellos no hace nada.
Como pide el contrato, una oferta que ya existe no se sobrescribe: las filas con un external_id repetido se ignoran.
"""
import os

import requests

from buscador import contrato

LOTE = 500   # el contrato acepta hasta 500 filas por llamada


def credenciales():
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    clave = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return (url, clave) if url and clave else (None, None)


def _lista(texto):
    partes = [p.strip() for p in str(texto or "").split("|") if p.strip()]
    return partes or None


def _idiomas(texto):
    salida = []
    for parte in _lista(texto) or []:
        idioma, nivel, obligatorio = (parte.split(":") + ["", "1"])[:3]
        salida.append({"language": idioma, "level": nivel or None, "required": obligatorio != "0"})
    return salida or None


def fila_db(fila):
    """Fila del CSV del contrato → objeto para la tabla (listas como arreglos, vacíos como NULL)."""
    salida = {}
    for c in contrato.COLUMNAS + contrato.EXTRAS:
        v = fila.get(c, "")
        if c == "language_requirements":
            salida[c] = _idiomas(v)
        elif c in contrato.LISTAS:
            salida[c] = _lista(v)
        else:
            salida[c] = None if v in ("", None) else v
    return salida


def subir(filas, url=None, clave=None, sesion=None):
    """Inserta las filas en lotes de 500. Devuelve un resumen para salud.json (nunca lanza error)."""
    if url is None:
        url, clave = credenciales()
    if not url:
        return {"omitida": "sin SUPABASE_URL o SUPABASE_SECRET_KEY"}
    sesion = sesion or requests.Session()
    cabeceras = {"apikey": clave, "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates,return=minimal"}
    if clave.startswith("eyJ"):   # las claves antiguas (JWT) también van como Authorization
        cabeceras["Authorization"] = f"Bearer {clave}"
    enviadas, errores = 0, []
    objetos = [fila_db(f) for f in filas]
    for i in range(0, len(objetos), LOTE):
        lote = objetos[i:i + LOTE]
        try:
            r = sesion.post(f"{url}/rest/v1/ofertas?on_conflict=external_id", json=lote, headers=cabeceras, timeout=60)
        except requests.RequestException as e:
            errores.append(type(e).__name__)
            continue
        if r.status_code < 300:
            enviadas += len(lote)
        else:
            errores.append(f"{r.status_code}: {r.text[:300]}")
    return {"filas": len(objetos), "enviadas": enviadas, "errores": errores}


def probar(url=None, clave=None, sesion=None):
    """Comprueba la conexión y que la tabla exista, sin escribir nada. Devuelve (ok, mensaje en español)."""
    if url is None:
        url, clave = credenciales()
    if not url:
        return False, "Faltan los secretos SUPABASE_URL o SUPABASE_SECRET_KEY en GitHub."
    cabeceras = {"apikey": clave}
    if clave.startswith("eyJ"):
        cabeceras["Authorization"] = f"Bearer {clave}"
    try:
        r = (sesion or requests).get(f"{url}/rest/v1/ofertas?select=id&limit=1", headers=cabeceras, timeout=30)
    except requests.RequestException as e:
        return False, f"No se pudo conectar con {url}: {type(e).__name__}. Revisa SUPABASE_URL."
    if r.status_code == 200:
        return True, f"Conexión correcta: la tabla «ofertas» existe y la clave funciona ({url})."
    detalle = f"Supabase respondió {r.status_code}: {r.text[:300]}"
    if r.status_code == 401 or "Invalid API key" in r.text or "No API key" in r.text:
        return False, f"Supabase rechazó la clave: usa la clave SECRETA (sb_secret_… o service_role), no la pública. {detalle}"
    if "42501" in r.text or "permission denied" in r.text:
        return False, ("La clave no tiene permiso sobre la tabla: vuelve a correr supabase/esquema.sql completo (al final "
                       f"da los permisos). {detalle}")
    if r.status_code == 404 or "PGRST205" in r.text or "does not exist" in r.text or "Could not find" in r.text:
        return False, ("La API de Supabase no ve la tabla «ofertas». Revisa: 1) que SUPABASE_URL sea la del mismo proyecto "
                       "donde creaste la tabla; 2) vuelve a correr supabase/esquema.sql completo (al final da permisos y "
                       "recarga la API); 3) en Project Settings → Data API, que la API esté activa y «public» esté en "
                       f"Exposed schemas. {detalle}")
    return False, f"Respuesta inesperada. {detalle}"


if __name__ == "__main__":
    import sys
    ok, mensaje = probar()
    print(mensaje)
    sys.exit(0 if ok else 1)
