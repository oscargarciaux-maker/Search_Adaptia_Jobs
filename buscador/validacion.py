"""Comprobar el resultado real después de conservar el estado y la cola de reintentos.

Contrato v52 (27 nov, decisión de Oscar): la búsqueda diaria termina en uno de tres estados.
- COMPLETA: todo bien → éxito.
- CORTA: la meta del día quedó incompleta, hay vacantes de la selección con el enlace sin comprobar (no se comparten
  hasta comprobarlo) o vacantes de la selección que ya no encajan (no se comparten: el panel las vuelve a evaluar con
  el perfil y el cargo vigentes; 7.G, 27 nov). Es un resultado de negocio, no una avería → éxito con ::warning:: y
  resumen de qué faltó. La segunda pasada de las 8:30 y su respaldo siguen completando la meta: deciden con
  `trabajo/metricas_entrega.json` (`buscador/arranque.py`, `falta_completar`), no con el color de la corrida.
- AVERÍA: Supabase, catálogo, reconciliación (incluido 57014), registro de la selección, operaciones centrales o sin
  catálogo → fallo (exit 1) y aviso /fail.
`--catalogo` (captura horaria y búsqueda profunda) no cambia: solo mira `errores_catalogo`."""
import argparse
import json
import os
from pathlib import Path

COMPLETA, CORTA, AVERIA = "completa", "corta", "averia"
NOMBRE_ESTADO = {COMPLETA: "COMPLETA", CORTA: "CORTA", AVERIA: "AVERÍA"}
CONFIRMADO = "Meta de selección y sincronización confirmadas. Esto no certifica autenticidad de cada empresa."


def _por_cargo(roles, mensaje, detalle):
    """`roles`: [(nombre, n)]. Con `detalle` (el panel, privado) un mensaje por cargo; sin él (registros de Actions,
    públicos: auditoría de exposición, 27 nov) uno solo con el total y cuántos cargos, sin nombres."""
    roles = [(nombre, n) for nombre, n in roles if n]
    if detalle:
        return [f"{nombre}: {n} {mensaje}" for nombre, n in roles]
    if not roles:
        return []
    return [f"{sum(n for _, n in roles)} {mensaje} ({len(roles)} {'cargo' if len(roles) == 1 else 'cargos'})"]


def errores(reporte, detalle=True):
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
    return fallos


# 7.G: por qué una vacante de la selección ya no encaja (lo anota `bodega.afinidad_vigente`). Solo en el detalle privado.
MOTIVOS_NO_ENCAJA = {"vacante": "cambió la vacante", "configuracion": "se editó el cargo o el perfil"}


def _ya_no_encajan(reporte, detalle):
    """7.G (decisión de Oscar, 27 nov): vacantes de la selección de hoy que ya no encajan = CORTA, no AVERÍA. Es un
    cambio de datos (la vacante, el cargo o el perfil), no algo roto. No se comparten: el panel las evalúa con el perfil
    y el cargo vigentes. En lo público (sin `detalle`) solo el total y cuántos cargos."""
    roles = (reporte.get("seleccion_actual") or {}).get("roles", {}).values()
    mensaje = "vacantes de la selección de hoy ya no encajan en ningún perfil del cargo; no se comparten."
    if not detalle:
        return _por_cargo([(rol.get("nombre", ""), len(_no_encajan(rol))) for rol in roles], mensaje, False)
    salida = []
    for rol in roles:
        lista = _no_encajan(rol)
        if not lista:
            continue
        motivos = {}
        for v in lista:
            motivo = MOTIVOS_NO_ENCAJA.get(v.get("motivo_no_encaja"))
            if motivo:
                motivos[motivo] = motivos.get(motivo, 0) + 1
        extra = f" ({', '.join(f'{n} {m}' for m, n in motivos.items())})" if motivos else ""
        salida.append(f"{rol.get('nombre', '')}: {len(lista)} {mensaje}{extra}")
    return salida


def _no_encajan(rol):
    return [v for v in rol.get("vacantes", []) if not v.get("afinidad_vigente") and not _cerro_despues(v)]


def cortos(reporte, detalle=True):
    """Contrato v52: la corrida funcionó pero el día quedó corto. No falla: avisa, y la segunda pasada completa.
    Sin `detalle` (registros públicos de Actions), sin nombres de cargo."""
    e = reporte.get("entrega") or {}
    salida = []
    if not e or not e.get("meta_cumplida"):
        salida.append("La meta de selección diaria está incompleta.")
    revision = (reporte.get("verificacion_enlaces") or {}).get("seleccion_del_dia")
    # 17 nov: solo cuenta lo que quedó sin comprobar; un enlace rechazado es una vacante que cerró y ya no se comparte.
    if revision and revision.get("vacantes") and revision.get("estados", {}).get("pendiente", 0):
        salida.append(f"{revision['estados']['pendiente']} vacantes de la selección de hoy tienen el enlace sin comprobar; "
                      "no se comparten hasta comprobarlo.")
    salida.extend(_ya_no_encajan(reporte, detalle))
    return salida


def problemas(reporte):
    """Averías y cortes juntos (lo que devolvía `errores` antes de v52): el panel marca «parcial» con cualquiera."""
    return errores(reporte) + cortos(reporte)


def estado(reporte, fallos=None, faltas=None):
    """La única regla de los tres estados: manda la avería. `fallos`/`faltas` evitan calcular dos veces."""
    fallos = errores(reporte) if fallos is None else fallos
    faltas = cortos(reporte) if faltas is None else faltas
    return AVERIA if fallos else CORTA if faltas else COMPLETA


def _cerro_despues(v):
    """17 nov: una vacante elegida hoy que después se detectó cerrada (o salió del inventario) ya no se comparte —su
    enlace queda rechazado—; es un aviso, no una falla. Antes se reportaba como «fuera del perfil»."""
    return v.get("catalog_status") != "active" or (v.get("verificacion") or {}).get("estado") == "rechazada"


def avisos(reporte, detalle=True):
    """Lo que conviene saber sin que la búsqueda falle."""
    return _por_cargo(
        [(rol.get("nombre", ""), sum(1 for v in rol.get("vacantes", [])
                                     if not v.get("afinidad_vigente") and _cerro_despues(v)))
         for rol in (reporte.get("seleccion_actual") or {}).get("roles", {}).values()],
        "vacantes elegidas hoy cerraron o salieron del inventario después; no se comparten.", detalle)


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


def resumen(reporte, fallos, faltas):
    """Markdown para $GITHUB_STEP_SUMMARY (público): solo totales, sin nombre ni meta de cada cargo (27 nov)."""
    actual = estado(reporte, fallos, faltas)
    e = reporte.get("entrega") or {}
    lineas = [f"## Resultado del día: {NOMBRE_ESTADO[actual]}", ""]
    if fallos or faltas:
        lineas += ["**Motivo:**", *[f"- {m}" for m in fallos + faltas], ""]
    else:
        lineas += [CONFIRMADO, ""]
    roles = e.get("roles") or {}
    if roles:
        metas = [m for m in (e.get("metas_por_rol") or {}).values() if m is not None]
        perfiles = any("perfiles_bajo_minimo" in r for r in roles.values())
        lineas += ["| Cargos | Meta total | Logradas | Faltan |" + (" Perfiles bajo el mínimo |" if perfiles else ""),
                   "|---|---|---|---|" + ("---|" if perfiles else "")]
        fila = (f"| {len(roles)} | {sum(metas) if metas else '—'} | "
                f"{sum(r.get('unicas', r.get('entregadas', 0)) for r in roles.values())} | "
                f"{sum(r.get('faltan', 0) for r in roles.values())} |")
        lineas.append(fila + (f" {sum(r.get('perfiles_bajo_minimo', 0) for r in roles.values())} |" if perfiles else ""))
        lineas += ["", "El detalle por cargo está en el panel (este resumen es público).", ""]
    revision = (reporte.get("verificacion_enlaces") or {}).get("seleccion_del_dia") or {}
    if revision.get("vacantes"):
        n = revision.get("estados") or {}
        lineas += [f"Enlaces de la selección: {n.get('verificada', 0)} comprobados, {n.get('pendiente', 0)} sin "
                   f"comprobar, {n.get('rechazada', 0)} cerrados.", ""]
    if actual == CORTA:
        lineas.append("La corrida no falla (no es una avería).")
        if not e.get("meta_cumplida"):
            lineas.append("La segunda pasada (8:30) o «Buscar ahora» completan la meta.")
        if revision.get("vacantes") and (revision.get("estados") or {}).get("pendiente"):
            lineas.append("Las vacantes con el enlace sin comprobar no se comparten hasta comprobarlo.")
        if _ya_no_encajan(reporte, False):
            lineas.append("Las vacantes que ya no encajan no se comparten; el detalle por cargo está en el panel.")
        lineas.append("")
    # Termina en línea en blanco: el paso «Resumen» escribe después en el mismo archivo y no debe pegarse a la tabla.
    return "\n".join(lineas) + "\n"


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
    # Lo que se imprime y el resumen son públicos: sin nombres de cargo (detalle=False). El estado no cambia.
    fallos, faltas = errores(reporte, detalle=False), cortos(reporte, detalle=False)
    for mensaje in avisos(reporte, detalle=False) + faltas:
        print("::warning::" + mensaje)
    for mensaje in fallos:
        print("::error::" + mensaje)
    if destino := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(destino, "a", encoding="utf-8") as f:
            f.write(resumen(reporte, fallos, faltas))
    actual = estado(reporte, fallos, faltas)
    print(f"Resultado: {NOMBRE_ESTADO[actual]}. " + {
        AVERIA: "Ver los errores de arriba.",
        CORTA: "Sincronización confirmada; el día quedó corto (ver avisos). No es una avería.",
        COMPLETA: CONFIRMADO}[actual])
    if actual == AVERIA:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
