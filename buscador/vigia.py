"""Vigía de la búsqueda diaria (18 nov). Ese día GitHub no lanzó ningún horario programado durante horas y la búsqueda
de las 6:30 de Bogotá no corrió. La «Captura horaria» corre cada hora: si después de las 12:00 UTC (7:00 de Bogotá)
hoy no terminó ninguna búsqueda diaria y tampoco hay una lanzada, en cola o corriendo, imprime lanzar=true para que
el flujo la lance una vez con workflow_dispatch.

Solo lee la fecha del registro de entregas (sin datos de clientes) y la lista de corridas de bodega.yml que da GitHub.
Una búsqueda cancelada por GitHub mientras esperaba no cuenta; una lanzada a mano (o por este vigía) siempre cuenta,
así nunca lanza dos veces el mismo día."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOGOTA = timezone(timedelta(hours=-5))
DESDE_HORA_UTC = 12


def _fecha_bogota(texto):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone(BOGOTA).date().isoformat()
    except ValueError:
        return None


def hace_falta_lanzar(metricas, corridas, ahora=None):
    """`metricas`: contenido de trabajo/metricas_entrega.json; `corridas`: `gh run list --json
    createdAt,status,conclusion,event` de bodega.yml. Devuelve (lanzar, motivo)."""
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.astimezone(timezone.utc).hour < DESDE_HORA_UTC:
        return False, "Aún es temprano: los horarios de la mañana pueden arrancar todavía."
    if not isinstance(corridas, list):
        return False, "No se pudo leer la lista de corridas: no se lanza nada a ciegas."
    hoy = ahora.astimezone(BOGOTA).date().isoformat()
    if isinstance(metricas, dict) and isinstance(metricas.get(hoy), dict):
        return False, "La búsqueda diaria de hoy ya terminó."
    for c in corridas:
        if not isinstance(c, dict) or _fecha_bogota(c.get("createdAt", "")) != hoy:
            continue
        if c.get("event") == "workflow_dispatch":
            return False, "Hoy ya se lanzó una búsqueda a mano o por el vigía."
        if c.get("conclusion") != "cancelled":
            return False, "Hoy ya hay una búsqueda diaria lanzada por su horario."
    return True, "GitHub no lanzó la búsqueda diaria de hoy: se lanza ahora."


def _leer(ruta, defecto):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metricas", required=True)
    ap.add_argument("--corridas", required=True)
    args = ap.parse_args()
    lanzar, motivo = hace_falta_lanzar(_leer(args.metricas, {}), _leer(args.corridas, None))
    print(f"::notice::{motivo}", file=sys.stderr)
    print(f"lanzar={'true' if lanzar else 'false'}")


if __name__ == "__main__":
    main()
