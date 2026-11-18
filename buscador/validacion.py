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


def hace_falta_completar(trabajo, hoy):
    """Segunda pasada de la mañana: solo si la nocturna de hoy no cumplió la meta, no confirmó Supabase o no corrió."""
    try:
        dia = json.loads((Path(trabajo) / "metricas_entrega.json").read_text(encoding="utf-8")).get(hoy)
    except (OSError, ValueError, AttributeError):
        return True
    return not (isinstance(dia, dict) and dia.get("meta_cumplida") and dia.get("registro_confirmado")
                and not dia.get("pendientes_supabase"))


PASADAS = ("principal", "respaldo", "segunda", "segunda-respaldo")


def _dia(trabajo, hoy):
    try:
        dia = json.loads((Path(trabajo) / "metricas_entrega.json").read_text(encoding="utf-8")).get(hoy)
    except (OSError, ValueError, AttributeError):
        return None
    return dia if isinstance(dia, dict) else None


def hace_falta_pasada(trabajo, hoy, tipo):
    """18 nov: GitHub a veces no lanza un horario programado (ese día no corrió ninguno). bodega.yml tiene horarios de
    respaldo que solo trabajan si el anterior no lo hizo:
    - principal (6:30 de Bogotá o a mano): siempre;
    - respaldo de la mañana: solo si hoy aún no terminó ninguna búsqueda diaria;
    - segunda (8:30): como antes, si falta meta, confirmar Supabase o no corrió;
    - respaldo de la segunda: lo mismo, pero solo si hoy terminaron menos de dos búsquedas diarias.
    Si no se puede leer el registro del día, trabaja (como cuando falta el archivo)."""
    if tipo not in PASADAS:
        raise ValueError(f"Pasada desconocida: {tipo}")
    if tipo == "principal":
        return True
    dia = _dia(trabajo, hoy)
    if tipo == "respaldo":
        return dia is None
    if not hace_falta_completar(trabajo, hoy):
        return False
    return tipo == "segunda" or dia is None or int(dia.get("pasadas", 1) or 0) < 2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--catalogo", action="store_true")
    ap.add_argument("--hace-falta-completar", action="store_true",
                    help="Imprime ejecutar=true/false para GITHUB_OUTPUT según el día de hoy en Bogotá")
    ap.add_argument("--pasada", choices=PASADAS,
                    help="Igual que --hace-falta-completar, según el horario que lanzó la búsqueda (bodega.yml)")
    args = ap.parse_args()
    if args.hace_falta_completar or args.pasada:
        from datetime import datetime, timedelta, timezone
        hoy = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
        falta = hace_falta_pasada(Path(args.salida) / "trabajo", hoy, args.pasada or "segunda")
        print(f"ejecutar={'true' if falta else 'false'}")
        return
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
