"""Comprobar el resultado real después de conservar el estado y la cola de reintentos.

Contrato v52 (27 nov, decisión de Oscar): la búsqueda diaria termina en uno de tres estados.
- COMPLETA: todo bien → éxito.
- CORTA: la meta del día quedó incompleta o hay vacantes de la selección con el enlace sin comprobar (no se comparten
  hasta comprobarlo). Es un resultado de negocio, no una avería → éxito con ::warning:: y resumen de qué faltó. La
  segunda pasada de las 8:30 y su respaldo siguen completando la meta: deciden con `trabajo/metricas_entrega.json`
  (`buscador/arranque.py`, `falta_completar`), no con el color de la corrida.
- AVERÍA: Supabase, catálogo, reconciliación (incluido 57014), registro de la selección, operaciones centrales, sin
  catálogo o vacantes que ya no encajan → fallo (exit 1) y aviso /fail.
`--catalogo` (captura horaria y búsqueda profunda) no cambia: solo mira `errores_catalogo`."""
import argparse
import json
import os
from pathlib import Path

COMPLETA, CORTA, AVERIA = "completa", "corta", "averia"
NOMBRE_ESTADO = {COMPLETA: "COMPLETA", CORTA: "CORTA", AVERIA: "AVERÍA"}
CONFIRMADO = "Meta de selección y sincronización confirmadas. Esto no certifica autenticidad de cada empresa."


def errores(reporte):
    """Averías: lo que de verdad está roto o sin confirmar. La corrida falla (contrato v52)."""
    e = reporte.get("entrega") or {}
    sb = e.get("supabase") or {}
    fallos = []
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
    for rol in (reporte.get("seleccion_actual") or {}).get("roles", {}).values():
        fuera = [v for v in rol.get("vacantes", []) if not v.get("afinidad_vigente") and not _cerro_despues(v)]
        if fuera:
            fallos.append(f"{rol['nombre']}: {len(fuera)} vacantes de la selección de hoy ya no encajan en ningún perfil "
                          "del cargo.")
    return fallos


def cortos(reporte):
    """Contrato v52: la corrida funcionó pero el día quedó corto. No falla: avisa, y la segunda pasada completa."""
    e = reporte.get("entrega") or {}
    salida = []
    if not e or not e.get("meta_cumplida"):
        salida.append("La meta de selección diaria está incompleta.")
    revision = (reporte.get("verificacion_enlaces") or {}).get("seleccion_del_dia")
    # 17 nov: solo cuenta lo que quedó sin comprobar; un enlace rechazado es una vacante que cerró y ya no se comparte.
    if revision and revision.get("vacantes") and revision.get("estados", {}).get("pendiente", 0):
        salida.append(f"{revision['estados']['pendiente']} vacantes de la selección de hoy tienen el enlace sin comprobar; "
                      "no se comparten hasta comprobarlo.")
    return salida


def problemas(reporte):
    """Averías y cortes juntos (lo que devolvía `errores` antes de v52): el panel marca «parcial» con cualquiera."""
    return errores(reporte) + cortos(reporte)


def estado(reporte):
    if errores(reporte):
        return AVERIA
    return CORTA if cortos(reporte) else COMPLETA


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
    estado_op = reporte.get("estado_operativo") or {}
    if estado_op.get("activo") and (any(estado_op.get("pendientes", {}).values()) or estado_op.get("lotes_pendientes") or
            any(r.get("errores") or r.get("omitida") for r in estado_op.get("reintentos", {}).values())):
        fallos.append("Hay operaciones centrales sin confirmar; conservar estado y revisar los reintentos.")
    return fallos


def resumen(reporte, fallos=None, faltas=None):
    """Markdown para $GITHUB_STEP_SUMMARY, solo con cifras que ya trae salud.json (sin datos de clientes)."""
    fallos = errores(reporte) if fallos is None else fallos
    faltas = cortos(reporte) if faltas is None else faltas
    actual = AVERIA if fallos else CORTA if faltas else COMPLETA
    e = reporte.get("entrega") or {}
    lineas = [f"## Resultado del día: {NOMBRE_ESTADO[actual]}", ""]
    if fallos or faltas:
        lineas += ["**Motivo:**", *[f"- {m}" for m in fallos + faltas], ""]
    else:
        lineas += [CONFIRMADO, ""]
    roles = e.get("roles") or {}
    if roles:
        metas = e.get("metas_por_rol") or {}
        perfiles = any("perfiles_bajo_minimo" in r for r in roles.values())
        lineas += ["| Cargo | Meta | Logradas | Faltan |" + (" Perfiles bajo el mínimo |" if perfiles else ""),
                   "|---|---|---|---|" + ("---|" if perfiles else "")]
        for rid, r in roles.items():
            meta = metas.get(rid)
            fila = (f"| {r.get('nombre', rid)} | {'—' if meta is None else meta} | "
                    f"{r.get('unicas', r.get('entregadas', 0))} | {r.get('faltan', 0)} |")
            lineas.append(fila + (f" {r.get('perfiles_bajo_minimo', 0)} |" if perfiles else ""))
        lineas.append("")
    revision = (reporte.get("verificacion_enlaces") or {}).get("seleccion_del_dia") or {}
    if revision.get("vacantes"):
        n = revision.get("estados") or {}
        lineas += [f"Enlaces de la selección: {n.get('verificada', 0)} comprobados, {n.get('pendiente', 0)} sin "
                   f"comprobar, {n.get('rechazada', 0)} cerrados.", ""]
    if actual == CORTA:
        lineas += ["La corrida no falla: la segunda pasada (8:30) o «Buscar ahora» completan lo que faltó.", ""]
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--catalogo", action="store_true")
    args = ap.parse_args()
    reporte = json.loads((Path(args.salida) / "datos/salud.json").read_text(encoding="utf-8"))
    if args.catalogo:
        fallos = errores_catalogo(reporte)
        for mensaje in fallos:
            print("::error::" + mensaje)
        if fallos:
            raise SystemExit(1)
        print(CONFIRMADO)
        return
    fallos, faltas = errores(reporte), cortos(reporte)
    for mensaje in avisos(reporte) + faltas:
        print("::warning::" + mensaje)
    for mensaje in fallos:
        print("::error::" + mensaje)
    if destino := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(destino, "a", encoding="utf-8") as f:
            f.write(resumen(reporte, fallos, faltas))
    if fallos:
        print("Resultado: AVERÍA.")
        raise SystemExit(1)
    if faltas:
        print("Resultado: CORTA. Sincronización confirmada; el día quedó corto (ver avisos). No es una avería.")
        return
    print("Resultado: COMPLETA. " + CONFIRMADO)


if __name__ == "__main__":
    main()
