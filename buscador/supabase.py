"""Sube las filas de la entrega diaria a la tabla `ofertas` de Supabase (supabase/esquema.sql) por su API REST.

Necesita dos secretos de GitHub: SUPABASE_URL (https://<proyecto>.supabase.co) y SUPABASE_SECRET_KEY (la clave secreta
del proyecto: Project Settings > API Keys; también sirve la antigua service_role). La entrega normal exige estos secretos
antes de recoger. `subir` conserva un resultado explícito de omisión para pruebas y llamadas aisladas sin configurar.
Como pide el contrato, una oferta que ya existe no se sobrescribe: las filas con un external_id repetido se ignoran.
"""
import os

import requests

from buscador import contrato

LOTE = 500   # el contrato acepta hasta 500 filas por llamada


def base(url):
    """Solo https://<proyecto>.supabase.co: la pantalla Data API de Supabase muestra la dirección con /rest/v1/ al final,
    y si se pega así la API responde «Invalid path» (PGRST125)."""
    from urllib.parse import urlparse
    p = urlparse(str(url or "").strip())
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else str(url or "").strip().rstrip("/")


def credenciales():
    url = base(os.environ.get("SUPABASE_URL", ""))
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
    """Fila normalizada del contrato → objeto para la tabla (listas como arreglos, vacíos como NULL)."""
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
    url = base(url)
    if not url or not clave:
        return {"omitida": "sin SUPABASE_URL o SUPABASE_SECRET_KEY"}
    sesion = sesion or requests.Session()
    cabeceras = {"apikey": clave, "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates,return=minimal"}
    if clave.startswith("eyJ"):   # las claves antiguas (JWT) también van como Authorization
        cabeceras["Authorization"] = f"Bearer {clave}"
    enviadas, errores, confirmadas = 0, [], []
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
            confirmadas.extend(f["external_id"] for f in lote)
        else:
            errores.append(f"{r.status_code}: {r.text[:300]}")
    # Aceptadas incluye ofertas que ya existían: el servidor puede ignorarlas sin devolver sus filas.
    return {"filas": len(objetos), "enviadas": enviadas, "errores": errores, "confirmadas": confirmadas}


def probar(url=None, clave=None, sesion=None):
    """Comprueba la conexión y que la tabla exista, sin escribir nada. Devuelve (ok, mensaje en español)."""
    if url is None:
        url, clave = credenciales()
    url = base(url)
    if not url:
        return False, "Faltan los secretos SUPABASE_URL o SUPABASE_SECRET_KEY en GitHub."
    cabeceras = {"apikey": clave}
    if clave.startswith("eyJ"):
        cabeceras["Authorization"] = f"Bearer {clave}"
    try:
        columnas = ",".join(["id"] + contrato.COLUMNAS + contrato.EXTRAS)
        r = (sesion or requests).get(f"{url}/rest/v1/ofertas?select={columnas}&limit=1", headers=cabeceras, timeout=30)
    except requests.RequestException as e:
        return False, f"No se pudo conectar con {url}: {type(e).__name__}. Revisa SUPABASE_URL."
    if r.status_code == 200:
        return True, f"Lectura y columnas de «ofertas» correctas ({url}); la escritura se comprueba al sincronizar."
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


def exigir_conexion():
    """Producción requiere Supabase antes de recoger o marcar entregas; una prueba no escribe ni exige claves."""
    url, clave = credenciales()
    if not url or not clave:
        raise RuntimeError("Supabase es obligatorio: faltan SUPABASE_URL o SUPABASE_SECRET_KEY. No se inició la entrega.")
    if clave.startswith("sb_publishable_"):
        raise RuntimeError("Supabase requiere la clave secreta, no la pública. No se inició la entrega.")
    if not clave.startswith("sb_secret_"):
        import base64
        import json
        try:
            parte = clave.split(".")[1]
            rol = json.loads(base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4)))["role"]
        except (IndexError, KeyError, ValueError, TypeError):
            rol = None
        if rol != "service_role":
            raise RuntimeError("La entrega requiere sb_secret_ o la clave service_role; no se inició la entrega.")
    ok, mensaje = probar(url, clave)
    if not ok:
        raise RuntimeError("No se inició la entrega: " + mensaje)
    return mensaje


def exigir_catalogo(sesion=None):
    url, clave = credenciales()
    if not url or not clave:
        raise RuntimeError("Faltan credenciales de Supabase para el catálogo.")
    cabeceras = {"apikey": clave}
    if clave.startswith("eyJ"):
        cabeceras["Authorization"] = f"Bearer {clave}"
    columnas = "id,contract_version,datos,description_full,published_at,first_seen_at,last_seen_at,observed_at,status,closed_at,reason"
    r = (sesion or requests).get(f"{url}/rest/v1/catalogo_vacantes?select={columnas}&limit=1",
                                 headers=cabeceras, timeout=30)
    if r.status_code != 200:
        raise RuntimeError("Falta el catálogo v2 o no hay permisos. Aplicar supabase/migraciones/002_catalogo.sql.")
    r = (sesion or requests).get(f"{url}/rest/v1/entregas_diarias?select=vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot&limit=1",
                                 headers=cabeceras, timeout=30)
    if r.status_code != 200:
        raise RuntimeError("Falta el registro de entregas v2. Aplicar supabase/migraciones/002_catalogo.sql.")


def subir_catalogo(filas, sesion=None, tabla="catalogo_vacantes"):
    url, clave = credenciales()
    if not url or not clave:
        return {"omitida": "sin credenciales de Supabase", "confirmadas": []}
    clave_id = "id" if tabla == "catalogo_vacantes" else "vacante_id"
    modo = "merge-duplicates" if tabla == "catalogo_vacantes" else "ignore-duplicates"
    cabeceras = {"apikey": clave, "Prefer": f"resolution={modo},return=minimal"}
    if clave.startswith("eyJ"):
        cabeceras["Authorization"] = f"Bearer {clave}"
    sesion = sesion or requests.Session()
    confirmadas, errores = [], []
    for inicio in range(0, len(filas), 100):
        lote = filas[inicio:inicio + 100]
        try:
            r = sesion.post(f"{url}/rest/v1/{tabla}?on_conflict={clave_id}", json=lote,
                             headers=cabeceras, timeout=60)
        except requests.RequestException as e:
            errores.append(type(e).__name__)
            continue
        if 200 <= r.status_code < 300:
            confirmadas.extend(f[clave_id] for f in lote)
        else:
            errores.append(f"HTTP {r.status_code}: catálogo no sincronizado")
    return {"filas": len(filas), "enviadas": len(confirmadas), "confirmadas": confirmadas, "errores": errores}


def leer_entregas(hoy, sesion=None):
    """Recuperar identidades sin cargar todo el histórico de descripciones; solo snapshots de hoy."""
    url, clave = credenciales()
    cab = {"apikey": clave}
    if clave and clave.startswith("eyJ"):
        cab["Authorization"] = f"Bearer {clave}"
    sesion = sesion or requests.Session()
    memoria = {}
    offset = 0
    while True:
        r = sesion.get(f"{url}/rest/v1/entregas_diarias", headers=cab, timeout=30,
                       params={"select": "vacante_id,delivery_date,enlace:snapshot->>enlace,enlace_directo:snapshot->>enlace_directo,aliases:snapshot->_enlaces",
                               "order": "vacante_id", "limit": 1000, "offset": offset})
        if r.status_code != 200 or not isinstance(r.json(), list):
            raise RuntimeError("No se pudo recuperar la memoria de entregas desde Supabase.")
        filas = r.json()
        memoria.update({f["vacante_id"]: f["delivery_date"] for f in filas})
        for f in filas:
            for enlace in [f.get("enlace"), f.get("enlace_directo"), *(f.get("aliases") or [])]:
                if enlace:
                    memoria[contrato.url_limpia(enlace)] = f["delivery_date"]
        if len(filas) < 1000:
            break
        offset += len(filas)
    v1_hoy = set()
    offset = 0
    while True:
        r = sesion.get(f"{url}/rest/v1/ofertas", headers=cab, timeout=30,
                       params={"select": "offer_url,delivery_date", "order": "id", "limit": 1000, "offset": offset})
        if r.status_code != 200 or not isinstance(r.json(), list):
            raise RuntimeError("No se pudo recuperar la memoria histórica v1 desde Supabase.")
        filas = r.json()
        for f in filas:
            if f.get("offer_url"):
                memoria[contrato.url_limpia(f["offer_url"])] = f.get("delivery_date") or hoy
                if f.get("delivery_date") == hoy:
                    v1_hoy.add(contrato.url_limpia(f["offer_url"]))
        if len(filas) < 1000:
            break
        offset += len(filas)
    r = sesion.get(f"{url}/rest/v1/entregas_diarias", headers=cab, timeout=30,
                   params={"select": "role_id,match_grade,selected_at,snapshot", "delivery_date": "eq." + hoy, "limit": 500})
    if r.status_code != 200 or not isinstance(r.json(), list):
        raise RuntimeError("No se pudo recuperar el lote diario desde Supabase.")
    grados = {"exact": "exacto", "similar": "similar", "close": "cercano"}
    lote = {"fecha": hoy, "elegidas": {}}
    for f in r.json():
        v = dict(f["snapshot"], _capturada_entrega=f["selected_at"])
        lote["elegidas"].setdefault(f["role_id"], []).append((v, grados[f["match_grade"]]))
    registradas = {contrato.url_limpia(u) for lista in lote["elegidas"].values() for v, _ in lista
                   for u in (v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])) if u}
    lote["v1_sin_registro_hoy"] = sorted(v1_hoy - registradas)
    return memoria, lote


if __name__ == "__main__":
    import sys
    ok, mensaje = probar()
    print(mensaje)
    sys.exit(0 if ok else 1)
