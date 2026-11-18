"""Arranque de la búsqueda diaria (18 nov). Ese día GitHub no lanzó ningún horario programado durante horas y la
búsqueda de las 6:30 de Bogotá no corrió. Aquí se responde, con una sola regla, «¿cuántas búsquedas diarias terminaron
hoy?», leyendo el registro de entregas (trabajo/metricas_entrega.json: solo fechas y conteos, sin datos de clientes):

- bodega.yml: cada horario dice qué pasada es (HORARIOS) y `--horario` imprime ejecutar=true/false;
- la «Captura horaria» (trabajo «vigia»): `--vigia` imprime lanzar=true/false para lanzar bodega.yml una vez.

Las capturas horarias que completan el lote (v43) escriben el registro con `pasadas` sin sumar: no cuentan."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOGOTA = timezone(timedelta(hours=-5))
DESDE_HORA_UTC = 12  # el vigía no actúa antes: la principal (11:30 UTC) y su respaldo de las 12:15 pueden arrancar

# Horario de bodega.yml → pasada. Un horario que no esté aquí es un error (no trabaja a ciegas).
HORARIOS = {
    "30 11 * * *": "primera",            # 6:30 de Bogotá
    "15 12 * * *": "primera",            # respaldo
    "50 12 * * *": "primera",            # respaldo
    "30 13 * * *": "segunda",            # 8:30 de Bogotá
    "30 14 * * *": "segunda-respaldo",   # 9:30 de Bogotá
}


def hoy_bogota(ahora=None):
    return (ahora or datetime.now(timezone.utc)).astimezone(BOGOTA).date().isoformat()


def leer_dia(trabajo, hoy):
    """El registro de hoy, o None si no existe o no se puede leer."""
    try:
        dia = json.loads((Path(trabajo) / "metricas_entrega.json").read_text(encoding="utf-8")).get(hoy)
    except (OSError, ValueError, AttributeError):
        return None
    return dia if isinstance(dia, dict) else None


def busquedas_diarias(dia):
    """Búsquedas diarias que terminaron la entrega del día. Un registro anterior al 18 nov (sin el campo) cuenta 1."""
    if not isinstance(dia, dict):
        return 0
    try:
        return int(dia.get("pasadas", 1) or 0)
    except (TypeError, ValueError):
        return 1


def falta_completar(dia):
    """Segunda pasada de la mañana: si la de hoy no cumplió la meta, no confirmó Supabase o no corrió."""
    return not (isinstance(dia, dict) and dia.get("meta_cumplida") and dia.get("registro_confirmado")
                and not dia.get("pendientes_supabase"))


def hace_falta_pasada(dia, horario):
    """`horario`: el cron que lanzó bodega.yml; vacío = a mano (o por el vigía), que siempre trabaja.
    - primera (6:30 y sus respaldos): solo si hoy no terminó ninguna búsqueda diaria; así una de las 6:30 que GitHub
      lanza tarde no repite la que ya hizo un respaldo;
    - segunda (8:30): como antes, si falta completar;
    - respaldo de la segunda: igual, pero solo si hoy terminaron menos de dos (no se hace una tercera)."""
    if not horario:
        return True
    if horario not in HORARIOS:
        raise ValueError(f"Horario sin pasada en buscador/arranque.py: {horario!r}")
    pasada, hechas = HORARIOS[horario], busquedas_diarias(dia)
    if pasada == "primera":
        return hechas == 0
    if not falta_completar(dia):
        return False
    return pasada == "segunda" or hechas < 2


def _fecha_bogota(texto):
    try:
        return hoy_bogota(datetime.fromisoformat(str(texto).replace("Z", "+00:00")))
    except ValueError:
        return None


def hace_falta_lanzar(dia, corridas, rama, ahora=None):
    """Vigía. `corridas`: `gh run list --json createdAt,conclusion,event,headBranch` de bodega.yml. Lanza si hoy no
    terminó ninguna búsqueda diaria y no hay en la rama principal una de hoy lanzada a mano (cualquier resultado) ni
    una programada que no haya sido cancelada (en cola, corriendo o terminada). Así lanza como mucho una vez al día.
    Devuelve (lanzar, motivo)."""
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.astimezone(timezone.utc).hour < DESDE_HORA_UTC:
        return False, "Aún es temprano: los horarios de la mañana pueden arrancar todavía."
    if not isinstance(corridas, list) or not rama:
        return False, "No se pudo leer la lista de corridas o la rama principal: no se lanza nada a ciegas."
    if busquedas_diarias(dia) > 0:
        return False, "La búsqueda diaria de hoy ya terminó."
    hoy = hoy_bogota(ahora)
    for c in corridas:
        if not isinstance(c, dict) or c.get("headBranch") != rama or _fecha_bogota(c.get("createdAt", "")) != hoy:
            continue
        if c.get("event") == "workflow_dispatch":
            return False, "Hoy ya se lanzó una búsqueda a mano o por el vigía."
        if c.get("conclusion") != "cancelled":
            return False, "Hoy ya hay una búsqueda diaria lanzada por su horario."
    return True, "GitHub no lanzó la búsqueda diaria de hoy: se lanza ahora."


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trabajo", required=True, help="Carpeta trabajo/ de la rama publicado")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--horario", help="Cron que lanzó bodega.yml (vacío = a mano); imprime ejecutar=true/false")
    modo.add_argument("--vigia", metavar="CORRIDAS", help="JSON de gh run list; imprime lanzar=true/false")
    ap.add_argument("--rama", default="", help="Rama principal (con --vigia; vacía = no lanza)")
    args = ap.parse_args(argv)
    dia = leer_dia(args.trabajo, hoy_bogota())
    if args.vigia is not None:
        try:
            corridas = json.loads(Path(args.vigia).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            corridas = None
        lanzar, motivo = hace_falta_lanzar(dia, corridas, args.rama)
        print(f"::notice::{motivo}", file=sys.stderr)
        print(f"lanzar={'true' if lanzar else 'false'}")
        return
    print(f"ejecutar={'true' if hace_falta_pasada(dia, args.horario) else 'false'}")


if __name__ == "__main__":
    main()
