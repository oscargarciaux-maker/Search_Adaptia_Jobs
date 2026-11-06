"""Comprobar el resultado real después de conservar el estado y la cola de reintentos."""
import argparse
import json
from pathlib import Path


def errores(reporte):
    e = reporte.get("entrega") or {}
    sb = e.get("supabase") or {}
    fallos = []
    if not e or not e.get("meta_cumplida"):
        fallos.append("La meta de selección diaria está incompleta.")
    if not sb or sb.get("omitida") or sb.get("errores") or sb.get("pendientes") or \
            sb.get("enviadas") is None or sb.get("enviadas") != sb.get("filas"):
        fallos.append("La sincronización con Supabase no está confirmada o tiene filas pendientes.")
    if not reporte.get("vacantes_en_bodega"):
        fallos.append("No hay catálogo válido.")
    registro = e.get("registro_seleccion")
    if registro is not None and (registro.get("errores") or registro.get("pendientes") or registro.get("omitida")):
        fallos.append("La selección no quedó registrada en Supabase; conservar pendientes y reintentar.")
    if reporte.get("catalogo") is not None:
        fallos.extend(errores_catalogo(reporte))
    revision = (reporte.get("verificacion_enlaces") or {}).get("seleccion_del_dia")
    if revision and revision.get("vacantes") and revision.get("estados", {}).get("verificada", 0) != revision["vacantes"]:
        fallos.append("La selección histórica tiene enlaces sin comprobación vigente o rechazados; revisar antes de compartir.")
    seleccion = reporte.get("seleccion_actual") or {}
    for rol in seleccion.get("roles", {}).values():
        if any(not v.get("afinidad_vigente") for v in rol.get("vacantes", [])):
            fallos.append(f"{rol['nombre']}: la selección histórica contiene vacantes fuera del perfil o del catálogo activo.")
    return fallos


def errores_catalogo(reporte):
    c = reporte.get("catalogo") or {}
    fallos = []
    if not c or c.get("omitida") or c.get("errores") or c.get("pendientes") or c.get("enviadas") != c.get("filas"):
        fallos.append("El catálogo no está sincronizado; se conserva la cola para reintentar.")
    estado = reporte.get("estado_operativo") or {}
    if estado.get("activo") and (any(estado.get("pendientes", {}).values()) or estado.get("lotes_pendientes") or
            any(r.get("errores") or r.get("omitida") for r in estado.get("reintentos", {}).values())):
        fallos.append("Hay operaciones centrales sin confirmar; conservar estado y revisar los reintentos.")
    return fallos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--catalogo", action="store_true")
    args = ap.parse_args()
    reporte = json.loads((Path(args.salida) / "datos/salud.json").read_text(encoding="utf-8"))
    fallos = errores_catalogo(reporte) if args.catalogo else errores(reporte)
    for mensaje in fallos:
        print("::error::" + mensaje)
    if fallos:
        raise SystemExit(1)
    print("Meta de selección y sincronización confirmadas. Esto no certifica autenticidad de cada empresa.")


if __name__ == "__main__":
    main()
