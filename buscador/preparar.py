"""Entrada de Actions: respaldo → artefacto confirmado → migración/activación. Nunca imprime credenciales."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

import requests

from buscador import migraciones, respaldo, supabase


def marca(sesion=None):
    url, clave = supabase.credenciales()
    if not url or not clave: return None
    cab = {"apikey": clave}
    if clave.startswith("eyJ"): cab["Authorization"] = f"Bearer {clave}"
    try:
        r = (sesion or requests.Session()).get(url + "/rest/v1/estado_operativo", timeout=30, headers=cab,
            params={"cola": "eq.control", "identificador": "eq.instalacion_automatica", "select": "payload", "limit": 1})
        datos = r.json()
        if r.status_code == 404 and isinstance(datos, dict) and datos.get("code") in ("PGRST205", "42P01"):
            return None
        if r.status_code != 200 or not isinstance(datos, list): raise ValueError()
        if not datos: return None
        payload = datos[0]["payload"]
        if not isinstance(payload, dict) or set(payload) != {"migraciones"} or not isinstance(payload["migraciones"], dict) or not payload["migraciones"]:
            raise ValueError()
        if any(not re.fullmatch(r"\d{3}", v) or not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h)
               for v, h in payload["migraciones"].items()): raise ValueError()
        return payload
    except (requests.RequestException, ValueError, KeyError, IndexError):
        raise RuntimeError("No se pudo comprobar la instalación automática por REST; revisar conexión/permisos, sin volver al modo local.") from None


def comprobar_rest(huellas):
    for intento in range(6):
        try:
            if marca() != {"migraciones": huellas}: raise RuntimeError("Marca de instalación no confirmada.")
            supabase.exigir_conexion()
            supabase.exigir_catalogo()
            return
        except (RuntimeError, requests.RequestException):
            if intento == 5: raise RuntimeError("El esquema se guardó, pero REST aún no confirma tablas/permisos; revisar antes de capturar.") from None
            time.sleep(2)  # Solo lecturas; no repetir SQL ni llamadas pagadas.


def salidas(ejecutar, central, catalogo, copia="", resumen=""):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"ejecutar={str(ejecutar).lower()}\nrespaldo={copia}\n")
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a") as f:
            f.write(f"ESTADO_SUPABASE_ACTIVO={str(central).lower()}\nCATALOGO_ACTIVO={str(catalogo).lower()}\n")
    if resumen:
        print(resumen)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f: f.write(resumen + "\n")


def correr(args):
    if args.prueba:
        salidas(True, False, False, resumen="Prueba temporal: sin migraciones, estado central ni Apify pagado.")
        return
    dsn = os.environ.get("SUPABASE_DB_URL", "").strip()
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("La preparación real solo se ejecuta desde main.")
    if not dsn:
        if args.modo == "instalar":
            raise RuntimeError("Configuración inicial pendiente: guardar SUPABASE_DB_URL y SUPABASE_BACKUP_KEY en Secrets una vez.")
        instalada = marca()
        if instalada and instalada != {"migraciones": {m.version: m.digest for m in migraciones.descubrir()}}:
            raise RuntimeError("Hay una actualización de base pendiente: configurar SUPABASE_DB_URL para aplicarla automáticamente.")
        central = bool(instalada) or os.environ.get("ESTADO_SUPABASE_ACTIVO", "").lower() == "true"
        captura = os.environ.get("CAPTURA_HORARIA_ACTIVA", "").lower() == "true"
        ejecutar = args.modo != "incremental" or bool(instalada) or captura or args.manual
        salidas(ejecutar, central, central or captura and args.modo != "profunda",
                resumen="Instalación automática vigente." if instalada else "Modo manual existente; automatización pendiente de configurar.")
        return
    llave = os.environ.get("SUPABASE_BACKUP_KEY", "")
    respaldo.clave(llave)
    url, clave = supabase.credenciales()
    if not url or not clave: raise RuntimeError("Configurar SUPABASE_URL y SUPABASE_SECRET_KEY del mismo proyecto antes de instalar.")
    privado = Path(args.privado)
    privado.mkdir(mode=0o700, parents=True, exist_ok=True)
    plan_archivo = privado / "plan.json"
    with migraciones.conexion(dsn, url) as conn:
        if args.fase == "respaldo":
            copia = privado / "respaldos" / ("corte-" + uuid4().hex + ".enc")
            plan = migraciones.planificar(conn, Path(args.salida) / "trabajo", copia, llave)
            plan_archivo.write_text(json.dumps(plan))
            salidas(False, False, False, copia=str(copia) if plan["necesaria"] else "",
                    resumen="Respaldo cifrado preparado; debe subirse antes de aplicar." if plan["necesaria"] else "Esquema automático ya vigente; no requiere otro respaldo de migración.")
            return
        if not plan_archivo.exists(): raise RuntimeError("Falta el plan y su respaldo previo; ejecutar primero la fase de respaldo.")
        resultado = migraciones.preparar(conn, Path(args.salida) / "trabajo", json.loads(plan_archivo.read_text()),
                                         instancia_nueva=args.instancia_nueva)
    comprobar_rest({m.version: m.digest for m in migraciones.descubrir()})
    from buscador.bodega import _guardar_json
    _guardar_json(Path(args.salida) / "trabajo/apify_presupuesto.json", resultado.pop("presupuesto"))
    salidas(True, True, True, resumen=f"Preparación confirmada: {resultado['vigentes']} migraciones vigentes; aplicadas ahora: {', '.join(resultado['aplicadas']) or 'ninguna'}. Catálogo y estado central activos para las capturas.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fase", choices=("respaldo", "aplicar"), default="respaldo")
    p.add_argument("--modo", choices=("diario", "incremental", "profunda", "instalar"), default="instalar")
    p.add_argument("--salida", default="salida")
    p.add_argument("--privado", default="privado")
    p.add_argument("--prueba", action="store_true")
    p.add_argument("--manual", action="store_true")
    p.add_argument("--instancia-nueva", action="store_true")
    args = p.parse_args()
    try:
        correr(args)
    except Exception as e:
        # Mensajes propios son controlados; no mostrar detalles SQL, DSN, filas o errores libpq.
        mensaje = str(e) if type(e) is RuntimeError else "Preparación no confirmada; revisar credenciales, conexión y migración. Se conserva el respaldo cifrado disponible."
        print("::error::" + mensaje)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
