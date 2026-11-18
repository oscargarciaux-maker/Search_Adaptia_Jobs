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
    # 17 nov: solo falla lo que quedó sin comprobar; un enlace rechazado es una vacante que cerró y ya no se comparte.
    if revision and revision.get("vacantes") and revision.get("estados", {}).get("pendiente", 0):
        fallos.append(f"{revision['estados']['pendiente']} vacantes de la selección de hoy tienen el enlace sin comprobar; "
                      "no se comparten hasta comprobarlo.")
    for rol in (reporte.get("seleccion_actual") or {}).get("roles", {}).values():
        fuera = [v for v in rol.get("vacantes", []) if not v.get("afinidad_vigente") and not _cerro_despues(v)]
        if fuera:
            fallos.append(f"{rol['nombre']}: {len(fuera)} vacantes de la selección de hoy ya no encajan en ningún perfil "
                          "del cargo.")
    return fallos


def _cerro_despues(v):
    """17 nov: una vacante elegida hoy que después se detectó cerrada (o salió del inventario) ya no se comparte —su
    enlace queda rechazado—; es un aviso, no una falla. Antes se reportaba como «fuera del perfil»."""
    return v.get("catalog_status") != "active" or (v.get("verificacion") or {}).get("estado") == "rechazada"


def avisos(reporte):
    """Lo que conviene saber sin que la búsqueda falle."""
    salida = []
    for rol in (reporte.get("seleccion_actual") or {}).get("roles", {}).values():
        cerradas = [v for v in rol.get("vacantes", []) if not v.get("afinidad_vigente") and _cerro_despues(v)]
        if cerradas:
            salida.append(f"{rol['nombre']}: {len(cerradas)} vacantes elegidas hoy cerraron o salieron del inventario "
                          "después; no se comparten.")
    return salida


def errores_catalogo(reporte):
    c = reporte.get("catalogo") or {}
    fallos = []
    if not c or c.get("omitida") or c.get("errores") or c.get("pendientes") or c.get("enviadas") != c.get("filas"):
        fallos.append("El catálogo no está sincronizado; se conserva la cola para reintentar.")
    if (c.get("identidad") or {}).get("errores"):
        detalles = (c.get("identidad") or {}).get("errores") or []
        tiempo = any("57014; tiempo_consulta" in str(e) for e in detalles)
        fallos.append("La reconciliación de ofertas únicas no está confirmada; conservar histórico y reintentar."
                      + (" Supabase canceló la consulta por tiempo (57014)." if tiempo else ""))
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
    for mensaje in ([] if args.catalogo else avisos(reporte)):
        print("::warning::" + mensaje)
    for mensaje in fallos:
        print("::error::" + mensaje)
    if fallos:
        raise SystemExit(1)
    print("Meta de selección y sincronización confirmadas. Esto no certifica autenticidad de cada empresa.")


if __name__ == "__main__":
    main()
