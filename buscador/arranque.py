"""Arranque de la búsqueda diaria (18 nov). Ese día GitHub no lanzó ningún horario programado durante horas y la
búsqueda de las 6:30 de Bogotá no corrió. Aquí se responde, con una sola regla, «¿cuántas búsquedas diarias terminaron
hoy?», leyendo el registro de entregas (trabajo/metricas_entrega.json: solo fechas y conteos, sin datos de clientes):

- bodega.yml: cada horario dice qué pasada es (HORARIOS) y `--horario` imprime ejecutar=true/false;
- la «Captura horaria» (trabajo «vigia»): `--vigia` imprime lanzar=true/false para lanzar bodega.yml una vez;
- el «Reloj» (contrato v51, reloj.yml): desde el 17 nov GitHub solo dispara los horarios de este repositorio cada 8 a
  12 horas, pero lo que se pide (workflow_dispatch) arranca al momento. El reloj es una cadena de relevos: cada uno
  espera con el temporizador del entorno `reloj`, pide el siguiente y lanza lo que toque. `--reloj` imprime
  actuar/seguir/captura/diaria; `--reloj-vivo` imprime revivir=true/false para quien deba reanudar la cadena.

Las capturas horarias que completan el lote (v43) escriben el registro con `pasadas` sin sumar: no cuentan."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOGOTA = timezone(timedelta(hours=-5))
DESDE_HORA_UTC = 12  # el vigía no actúa antes: la principal (11:30 UTC) y su respaldo de las 12:15 pueden arrancar

# Reloj (v51)
DIARIA_DESDE_UTC = (11, 30)  # 6:30 de Bogotá: desde aquí el reloj pide la búsqueda diaria si hoy no corrió
ESPERA_MINIMA = 20           # minutos; un relevo que esperó menos corre en un entorno sin temporizador: no sigue
CADA_CAPTURA = 55            # minutos entre capturas horarias (el relevo llega cada 30)
MAX_PEDIDAS = 3              # búsquedas diarias que se piden como mucho en un día (a mano, vigía o reloj)

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


def _instante(texto):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None


def _fecha_bogota(texto):
    instante = _instante(texto)
    return hoy_bogota(instante) if instante else None


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


def _numero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _de_la_rama(corridas, rama):
    """Las corridas de la rama principal, o None si la lista no se pudo leer (no se decide a ciegas)."""
    if not isinstance(corridas, list) or not rama:
        return None
    return [c for c in corridas if isinstance(c, dict) and c.get("headBranch") == rama]


def _activa(c):
    """En cola, esperando su temporizador o corriendo. Sin el dato, se cuenta como activa (lo prudente)."""
    return c.get("status") != "completed"


def relevo(yo, relojes, rama, ahora=None):
    """¿Qué hace este relevo del reloj? Devuelve (actuar, seguir, motivo, falta_temporizador).
    - actuar: puede pedir la captura o la búsqueda que toque;
    - seguir: pide el siguiente relevo. Solo sigue una cadena: si hay otro relevo vivo, este se retira (de dos que
      corren a la vez, sigue el más antiguo).
    Sin su propio registro, fuera de la rama principal o sin haber esperado (entorno sin temporizador: la cadena
    giraría sin pausa) no hace nada."""
    ahora = ahora or datetime.now(timezone.utc)
    lista = _de_la_rama(relojes, rama)
    mio = next((c for c in lista or [] if str(c.get("databaseId")) == str(yo)), None)
    creada = _instante(mio.get("createdAt")) if mio else None
    if creada is None:
        return False, False, "No se pudo leer este relevo en la rama principal: no se hace nada a ciegas.", False
    if (ahora - creada).total_seconds() < ESPERA_MINIMA * 60:
        return (False, False, "El entorno «reloj» no tiene su temporizador de espera (30 minutos): el reloj no "
                "sigue. Ver docs/ACTIVAR_RELOJ.md.", True)
    otros = [c for c in lista if str(c.get("databaseId")) != str(yo) and _activa(c)]
    en_espera = [c for c in otros if c.get("status") != "in_progress"]
    mayores = [c for c in otros if c.get("status") == "in_progress" and _numero(c.get("databaseId")) < _numero(yo)]
    if en_espera or mayores:
        return True, False, "Ya hay otro relevo del reloj en marcha: este no pide el siguiente.", False
    return True, True, "Relevo en hora: pide el siguiente.", False


def toca_captura(capturas, diarias, rama, ahora=None):
    """Captura horaria: si no hay una búsqueda diaria ni otra captura en marcha (una en cola cancelaría a la otra) y
    la última captura que no se canceló empezó hace `CADA_CAPTURA` minutos o más. Devuelve (lanzar, motivo)."""
    ahora = ahora or datetime.now(timezone.utc)
    capturas, diarias = _de_la_rama(capturas, rama), _de_la_rama(diarias, rama)
    if capturas is None or diarias is None:
        return False, "No se pudo leer la lista de corridas: no se pide la captura a ciegas."
    if any(_activa(c) for c in diarias):
        return False, "Hay una búsqueda diaria en marcha: ella ya captura."
    if any(_activa(c) for c in capturas):
        return False, "Ya hay una captura en marcha."
    hechas = [i for i in (_instante(c.get("createdAt")) for c in capturas if c.get("conclusion") != "cancelled") if i]
    if hechas and (ahora - max(hechas)).total_seconds() < CADA_CAPTURA * 60:
        return False, "La última captura es de hace menos de una hora."
    return True, "Toca la captura de esta hora."


def toca_diaria(dia, diarias, rama, ahora=None):
    """Búsqueda diaria desde el reloj: a partir de las 6:30 de Bogotá, si hoy no terminó ninguna y en la rama principal
    no hay una de hoy en marcha ni terminada (bien o mal: una que falló se revisa, no se repite sola). Una que GitHub
    canceló en la cola no cuenta, pero no se pide más de `MAX_PEDIDAS` veces al día. Devuelve (lanzar, motivo)."""
    ahora = ahora or datetime.now(timezone.utc)
    if (ahora.astimezone(timezone.utc).hour, ahora.astimezone(timezone.utc).minute) < DIARIA_DESDE_UTC:
        return False, "Aún no son las 6:30 de Bogotá."
    lista = _de_la_rama(diarias, rama)
    if lista is None:
        return False, "No se pudo leer la lista de corridas o la rama principal: no se lanza nada a ciegas."
    if busquedas_diarias(dia) > 0:
        return False, "La búsqueda diaria de hoy ya terminó."
    hoy = hoy_bogota(ahora)
    de_hoy = [c for c in lista if _fecha_bogota(c.get("createdAt", "")) == hoy]
    if any(_activa(c) for c in de_hoy):
        return False, "La búsqueda diaria de hoy ya está en marcha."
    if any(c.get("conclusion") != "cancelled" for c in de_hoy):
        return False, "La búsqueda diaria de hoy ya corrió; si falló, se revisa antes de repetirla."
    if sum(c.get("event") == "workflow_dispatch" for c in de_hoy) >= MAX_PEDIDAS:
        return False, "Hoy ya se pidió la búsqueda diaria varias veces y GitHub las canceló: no se insiste."
    return True, "Es la hora de la búsqueda diaria y hoy no ha corrido: se pide ahora."


def hace_falta_revivir(relojes, rama):
    """¿Hay que reanudar la cadena del reloj? Sí cuando no queda ningún relevo vivo en la rama principal."""
    lista = _de_la_rama(relojes, rama)
    if lista is None:
        return False, "No se pudo leer la lista de relevos: no se lanza nada a ciegas."
    if any(_activa(c) for c in lista):
        return False, "El reloj sigue en marcha."
    return True, "El reloj está parado: se reanuda."


def _leer_json(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _si(valor):
    return "true" if valor else "false"


def _reloj(args, dia):
    """`--reloj CARPETA` con relojes.json, diarias.json y capturas.json (salidas de `gh run list --json …`)."""
    carpeta = Path(args.reloj)
    relojes, diarias, capturas = (_leer_json(carpeta / n) for n in ("relojes.json", "diarias.json", "capturas.json"))
    actuar, seguir, motivo, falta = relevo(args.yo, relojes, args.rama)
    print(f"::{'error' if falta else 'notice'}::{motivo}", file=sys.stderr)
    captura = diaria = False
    if actuar:
        diaria, motivo_diaria = toca_diaria(dia, diarias, args.rama)
        # Si toca la diaria no se pide la captura: en la cola del grupo solo cabe una en espera.
        captura, motivo_captura = (False, "Se pide la búsqueda diaria.") if diaria else \
            toca_captura(capturas, diarias, args.rama)
        print(f"::notice::Búsqueda diaria: {motivo_diaria}", file=sys.stderr)
        print(f"::notice::Captura horaria: {motivo_captura}", file=sys.stderr)
    for nombre, valor in (("actuar", actuar), ("seguir", seguir), ("captura", captura), ("diaria", diaria),
                          ("falta_temporizador", falta)):
        print(f"{nombre}={_si(valor)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trabajo", required=True, help="Carpeta trabajo/ de la rama publicado")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--horario", help="Cron que lanzó bodega.yml (vacío = a mano); imprime ejecutar=true/false")
    modo.add_argument("--vigia", metavar="CORRIDAS", help="JSON de gh run list; imprime lanzar=true/false")
    modo.add_argument("--reloj", metavar="CARPETA", help="Carpeta con relojes.json, diarias.json y capturas.json; "
                      "imprime actuar, seguir, captura y diaria (true/false)")
    modo.add_argument("--reloj-vivo", metavar="RELOJES", help="JSON de gh run list de reloj.yml; imprime revivir=…")
    ap.add_argument("--rama", default="", help="Rama principal (con --vigia y el reloj; vacía = no lanza)")
    ap.add_argument("--yo", default="", help="Con --reloj: el número de esta corrida (GITHUB_RUN_ID)")
    args = ap.parse_args(argv)
    dia = leer_dia(args.trabajo, hoy_bogota())
    if args.reloj is not None:
        return _reloj(args, dia)
    if args.reloj_vivo is not None:
        revivir, motivo = hace_falta_revivir(_leer_json(args.reloj_vivo), args.rama)
        print(f"::notice::{motivo}", file=sys.stderr)
        print(f"revivir={_si(revivir)}")
        return
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
