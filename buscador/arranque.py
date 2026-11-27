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
# Hora de Bogotá (hora, minuto) entre las que se puede pedir la búsqueda diaria de hoy.
DIARIA_DESDE = (6, 30)   # el Reloj (v51)
VIGIA_DESDE = (7, 0)     # el vigía no actúa antes: la principal (6:30) y su respaldo de las 7:15 pueden arrancar
DIARIA_HASTA = (19, 0)   # más tarde ya no se empieza: terminaría de noche y cerca del cambio de día

# Reloj (v51)
ESPERA_MINIMA = 20       # minutos; un relevo que esperó menos corre en un entorno sin temporizador: no sigue
CADA_CAPTURA = 55        # minutos entre capturas horarias (el relevo llega cada 30)
MAX_PEDIDAS = 3          # veces que el Reloj pide la búsqueda diaria en un día si GitHub la cancela en la cola

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
    """Vigía (trabajo de la «Captura horaria»): la misma regla que el Reloj (`toca_diaria`), pero desde las 7:00 de
    Bogotá y sin insistir: si hoy ya se pidió una vez (a mano, por el vigía o por el Reloj), no pide otra."""
    return toca_diaria(dia, corridas, rama, ahora, desde=VIGIA_DESDE, max_pedidas=1)


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
    """En cola, esperando su temporizador o corriendo. Una lista sin `status` (la del vigía antes de v51) se lee por
    `conclusion`, que GitHub deja vacía hasta que la corrida termina."""
    return c["status"] != "completed" if "status" in c else not c.get("conclusion")


def relevo(yo, relojes, rama, ahora=None):
    """¿Qué hace este relevo del reloj? Devuelve (actuar, seguir, motivo, falta_temporizador).
    - actuar: puede pedir la captura o la búsqueda que toque;
    - seguir: pide el siguiente relevo. De los relevos vivos (esperando o corriendo) sigue solo el de número más
      alto: así nunca se retiran todos a la vez y, si llegan a quedar dos cadenas, en la ronda siguiente queda una.
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
    if any(_activa(c) and _numero(c.get("databaseId")) > _numero(yo) for c in lista):
        return True, False, "Hay un relevo del reloj más reciente en marcha: este no pide el siguiente.", False
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


def toca_diaria(dia, diarias, rama, ahora=None, desde=DIARIA_DESDE, max_pedidas=MAX_PEDIDAS):
    """¿Se pide ahora la búsqueda diaria? Una sola regla para el Reloj y el vigía. Entre `desde` y `DIARIA_HASTA` (hora
    de Bogotá), si hoy no terminó ninguna y en la rama principal no hay una de hoy en marcha ni terminada (bien o mal:
    una que falló se revisa, no se repite sola). Una que GitHub canceló en la cola no cuenta, pero no se pide más de
    `max_pedidas` veces al día. Devuelve (lanzar, motivo)."""
    ahora = ahora or datetime.now(timezone.utc)
    local = ahora.astimezone(BOGOTA)
    if (local.hour, local.minute) < desde:
        return False, "Aún es temprano: los horarios de la mañana pueden arrancar todavía."
    if (local.hour, local.minute) >= DIARIA_HASTA:
        return False, "Ya es tarde para empezar la búsqueda de hoy; si hace falta, se pide con «Buscar ahora»."
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
    if sum(c.get("event") == "workflow_dispatch" for c in de_hoy) >= max_pedidas:
        return False, "Hoy ya se pidió la búsqueda diaria (a mano, por el vigía o por el Reloj): no se insiste."
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


def _reloj(carpeta, yo, rama, dia, ahora):
    """`--reloj CARPETA` con relojes.json, diarias.json y capturas.json (salidas de `gh run list --json …`). Todo se
    decide con un mismo instante."""
    relojes, diarias, capturas = (_leer_json(Path(carpeta) / n) for n in ("relojes.json", "diarias.json", "capturas.json"))
    actuar, seguir, motivo, falta = relevo(yo, relojes, rama, ahora)
    print(f"::{'error' if falta else 'notice'}::{motivo}", file=sys.stderr)
    captura = diaria = False
    if actuar:
        diaria, motivo_diaria = toca_diaria(dia, diarias, rama, ahora)
        # Si toca la diaria no se pide la captura: en la cola del grupo solo cabe una en espera.
        captura, motivo_captura = (False, "Se pide la búsqueda diaria.") if diaria else \
            toca_captura(capturas, diarias, rama, ahora)
        print(f"::notice::Búsqueda diaria: {motivo_diaria}", file=sys.stderr)
        print(f"::notice::Captura horaria: {motivo_captura}", file=sys.stderr)
    for nombre, valor in (("actuar", actuar), ("seguir", seguir), ("captura", captura), ("diaria", diaria),
                          ("falta_temporizador", falta)):
        print(f"{nombre}={_si(valor)}")


def main(argv=None, ahora=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trabajo", default="", help="Carpeta trabajo/ de la rama publicado (no hace falta con --reloj-vivo)")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--horario", help="Cron que lanzó bodega.yml (vacío = a mano); imprime ejecutar=true/false")
    modo.add_argument("--vigia", metavar="CORRIDAS", help="JSON de gh run list; imprime lanzar=true/false")
    modo.add_argument("--reloj", metavar="CARPETA", help="Carpeta con relojes.json, diarias.json y capturas.json; "
                      "imprime actuar, seguir, captura, diaria y falta_temporizador (true/false)")
    modo.add_argument("--reloj-vivo", metavar="RELOJES", help="JSON de gh run list de reloj.yml; imprime revivir=…")
    ap.add_argument("--rama", default="", help="Rama principal (con --vigia y el reloj; vacía = no lanza)")
    ap.add_argument("--yo", default="", help="Con --reloj: el número de esta corrida (GITHUB_RUN_ID)")
    args = ap.parse_args(argv)
    ahora = ahora or datetime.now(timezone.utc)
    if args.reloj_vivo is not None:
        revivir, motivo = hace_falta_revivir(_leer_json(args.reloj_vivo), args.rama)
        print(f"::notice::{motivo}", file=sys.stderr)
        print(f"revivir={_si(revivir)}")
        return
    dia = leer_dia(args.trabajo, hoy_bogota(ahora))
    if args.reloj is not None:
        return _reloj(args.reloj, args.yo, args.rama, dia, ahora)
    if args.vigia is not None:
        lanzar, motivo = hace_falta_lanzar(dia, _leer_json(args.vigia), args.rama, ahora)
        print(f"::notice::{motivo}", file=sys.stderr)
        print(f"lanzar={_si(lanzar)}")
        return
    print(f"ejecutar={_si(hace_falta_pasada(dia, args.horario))}")


if __name__ == "__main__":
    main()
