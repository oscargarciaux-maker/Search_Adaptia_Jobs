"""Contrato v51: el «Reloj». Desde el 17 nov GitHub solo dispara los horarios de este repositorio cada 8 a 12 horas,
pero lo que se pide arranca al momento. El reloj es una cadena de relevos que esperan con el temporizador de un entorno
de GitHub y piden la captura de cada hora y la búsqueda de las 6:30 de Bogotá. Reglas en buscador/arranque.py."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from buscador import arranque

RAIZ = Path(__file__).resolve().parent.parent
AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)  # 7:00 de Bogotá
HECHA = {"meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0, "pasadas": 1}


def _corrida(minutos_atras, estado="completed", conclusion="success", evento="workflow_dispatch", numero=1,
             rama="main", ahora=AHORA):
    creada = (ahora - timedelta(minutes=minutos_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"databaseId": numero, "status": estado, "conclusion": conclusion if estado == "completed" else "",
            "createdAt": creada, "event": evento, "headBranch": rama}


def _yo(minutos=30, numero=50, **campos):
    return _corrida(minutos, "in_progress", numero=numero, **campos)


# ── El relevo ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_un_relevo_que_espero_su_media_hora_actua_y_pide_el_siguiente():
    actuar, seguir, motivo, falta = arranque.relevo(50, [_yo(), _corrida(60, numero=49)], "main", AHORA)
    assert (actuar, seguir, falta) == (True, True, False) and motivo


def test_sin_temporizador_el_relevo_no_hace_nada_y_no_sigue():
    # Un entorno recién creado no espera: la corrida empieza al momento. Sin este seguro la cadena giraría sin pausa.
    for minutos in (0, 1, 19):
        actuar, seguir, motivo, falta = arranque.relevo(50, [_yo(minutos)], "main", AHORA)
        assert (actuar, seguir, falta) == (False, False, True) and "ACTIVAR_RELOJ" in motivo
    assert arranque.relevo(50, [_yo(20)], "main", AHORA)[:2] == (True, True)


@pytest.mark.parametrize("otro,sigue", [
    (_corrida(10, "waiting", numero=51), False),      # el horario de respaldo dejó un relevo más nuevo: se queda ese
    (_corrida(1, "queued", numero=51), False),
    (_corrida(30, "in_progress", numero=51), False),
    (_corrida(30, "in_progress", numero=49), True),   # de dos que corren a la vez sigue el de número más alto: este
    (_corrida(45, "waiting", numero=49), True),
    (_corrida(10, "waiting", numero=51, rama="otra"), True),  # una prueba en otra rama no es otra cadena
    (_corrida(5, "completed", numero=51), True),
])
def test_nunca_dos_cadenas_pero_el_relevo_que_se_retira_si_cumple_con_lo_que_toca(otro, sigue):
    actuar, seguir, _, falta = arranque.relevo(50, [_yo(), otro], "main", AHORA)
    assert actuar is True and seguir is sigue and falta is False


@pytest.mark.parametrize("estado_a", ["in_progress", "waiting", "queued"])
@pytest.mark.parametrize("estado_b", ["in_progress", "waiting", "queued"])
def test_de_dos_relevos_vivos_sigue_exactamente_uno_los_vea_como_los_vea_cada_cual(estado_a, estado_b):
    # Cada relevo decide por su cuenta y puede ver al otro esperando o corriendo. Con una regla por estado, los dos
    # podían retirarse a la vez y la cadena se cortaba.
    a, b = _corrida(31, estado_a, numero=50), _corrida(30, estado_b, numero=51)
    sigue_a = arranque.relevo(50, [a, b], "main", AHORA)[1]
    sigue_b = arranque.relevo(51, [a, b], "main", AHORA)[1]
    assert (sigue_a, sigue_b) == (False, True)


@pytest.mark.parametrize("relojes,rama", [
    (None, "main"), ("roto", "main"), ([], "main"),          # sin lista o sin su propio registro
    ([_yo()], ""),                                             # sin rama principal
    ([_yo(rama="otra")], "main"),                              # lanzado fuera de la rama principal
    ([dict(_yo(), createdAt="ayer")], "main"),                 # fecha ilegible
])
def test_sin_datos_claros_el_relevo_no_hace_nada_a_ciegas(relojes, rama):
    assert arranque.relevo(50, relojes, rama, AHORA)[:2] == (False, False)


# ── La captura de cada hora ──────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("capturas,diarias,esperado", [
    ([], [], True),                                                           # nunca corrió
    ([_corrida(55)], [], True),
    ([_corrida(54)], [], False),                                              # el relevo de la media hora no repite
    ([_corrida(30, conclusion="cancelled"), _corrida(70)], [], True),         # una cancelada en la cola no cuenta
    ([_corrida(90), _corrida(5, "in_progress")], [], False),                  # ya hay una corriendo
    ([_corrida(90)], [_corrida(40, "in_progress")], False),                   # la búsqueda diaria ya captura
    ([_corrida(90)], [_corrida(2, "queued")], False),                         # pedirla cancelaría a la que espera
    ([_corrida(90)], [_corrida(200)], True),
    ([_corrida(10, rama="otra"), _corrida(90)], [], True),                    # una prueba en otra rama no cuenta
    (None, [], False), ([], None, False),                                     # sin listas no se pide a ciegas
])
def test_la_captura_se_pide_cada_hora_y_nunca_encima_de_otra(capturas, diarias, esperado):
    lanzar, motivo = arranque.toca_captura(capturas, diarias, "main", AHORA)
    assert lanzar is esperado and motivo


# ── La búsqueda diaria ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("dia,diarias,ahora,esperado", [
    (None, [], AHORA, True),                                                  # 7:00 de Bogotá y hoy no corrió
    (None, [], datetime(2026, 11, 27, 11, 30, tzinfo=timezone.utc), True),    # 6:30 en punto
    (None, [], datetime(2026, 11, 27, 11, 29, tzinfo=timezone.utc), False),   # aún no
    (None, [], datetime(2026, 11, 27, 23, 59, tzinfo=timezone.utc), True),    # 18:59 de Bogotá: aún se puede
    (None, [], datetime(2026, 11, 28, 0, 0, tzinfo=timezone.utc), False),     # 19:00: ya es tarde para empezarla
    (None, [], datetime(2026, 11, 27, 4, 0, tzinfo=timezone.utc), False),     # 23:00 del día anterior en Bogotá
    (HECHA, [], AHORA, False),                                                # ya terminó
    (None, [_corrida(20, "in_progress")], AHORA, False),                      # está corriendo
    (None, [_corrida(1, "queued")], AHORA, False),
    (None, [_corrida(25, conclusion="failure")], AHORA, False),               # falló: se revisa, no se repite sola
    (None, [_corrida(25, conclusion="cancelled")], AHORA, True),              # GitHub la canceló en la cola
    (None, [dict(_corrida(25, conclusion="cancelled"), empezo=False)], AHORA, True),
    # Cortada en marcha (tope de tiempo, o alguien la canceló): también termina «cancelled», pero sí empezó. No se
    # repite sola: con el tope de 150 minutos habría buscado tres veces seguidas.
    (None, [dict(_corrida(160, conclusion="cancelled"), empezo=True)], AHORA, False),
    (None, [_corrida(25, conclusion="cancelled", evento="schedule")], AHORA, True),
    (None, [_corrida(m, conclusion="cancelled") for m in (25, 20, 15)], AHORA, False),  # tres pedidas: no insiste
    (None, [_corrida(600, conclusion="failure")], AHORA, True),               # la de ayer (21:00 de Bogotá)
    (None, [_corrida(20, "in_progress", rama="otra")], AHORA, True),          # una prueba en otra rama
    (None, None, AHORA, False),                                               # sin lista no se lanza a ciegas
])
def test_la_busqueda_diaria_se_pide_a_las_6_30_una_vez_y_solo_si_no_corrio(dia, diarias, ahora, esperado):
    lanzar, motivo = arranque.toca_diaria(dia, diarias, "main", ahora)
    assert lanzar is esperado and motivo


def test_reanudar_la_cadena_solo_cuando_no_queda_ningun_relevo_vivo():
    assert arranque.hace_falta_revivir([], "main")[0] is True
    assert arranque.hace_falta_revivir([_corrida(90)], "main")[0] is True
    assert arranque.hace_falta_revivir([_corrida(10, "waiting")], "main")[0] is False
    assert arranque.hace_falta_revivir([_corrida(10, "waiting", rama="otra")], "main")[0] is True
    assert arranque.hace_falta_revivir(None, "main")[0] is False and arranque.hace_falta_revivir([], "")[0] is False


# ── Línea de comandos y flujos ───────────────────────────────────────────────────────────────────────────────────────
def _salidas(texto):
    return dict(linea.split("=") for linea in texto.splitlines())


def _archivos(carpeta, relojes, diarias=(), capturas=()):
    for nombre, lista in (("relojes", relojes), ("diarias", diarias), ("capturas", capturas)):
        (carpeta / f"{nombre}.json").write_text(json.dumps(list(lista)), encoding="utf-8")
    return ["--trabajo", str(carpeta), "--reloj", str(carpeta), "--yo", "50", "--rama", "main"]


def test_linea_de_comandos_del_reloj(tmp_path, capsys):
    # 7:00 de Bogotá, hoy no ha corrido la búsqueda: se pide, y con ella no se pide también la captura (en la cola del
    # grupo «publicar» solo cabe una corrida en espera: la segunda cancelaría a la primera).
    arranque.main(_archivos(tmp_path, [_yo()]), ahora=AHORA)
    salida = capsys.readouterr()
    assert _salidas(salida.out) == {"actuar": "true", "seguir": "true", "captura": "false", "diaria": "true",
                                    "captura_sin_diaria": "true", "falta_temporizador": "false"}
    assert "::notice::" in salida.err and "=" not in salida.err.replace("::", "")  # los motivos no van a GITHUB_OUTPUT

    # Con la búsqueda diaria en marcha no se pide ni otra ni la captura; la cadena sigue.
    arranque.main(_archivos(tmp_path, [_yo()], diarias=[_corrida(5, "in_progress")]), ahora=AHORA)
    assert _salidas(capsys.readouterr().out) == {"actuar": "true", "seguir": "true", "captura": "false", "diaria": "false",
                                                 "captura_sin_diaria": "false", "falta_temporizador": "false"}

    # Con la búsqueda de hoy ya terminada (el registro del día lo dice), toca la captura de la hora.
    (tmp_path / "metricas_entrega.json").write_text(json.dumps({arranque.hoy_bogota(AHORA): HECHA}), encoding="utf-8")
    arranque.main(_archivos(tmp_path, [_yo()], diarias=[_corrida(100)], capturas=[_corrida(70)]), ahora=AHORA)
    assert _salidas(capsys.readouterr().out) == {"actuar": "true", "seguir": "true", "captura": "true", "diaria": "false",
                                                 "captura_sin_diaria": "true", "falta_temporizador": "false"}

    # Sin temporizador: nada, y se dice como error.
    arranque.main(_archivos(tmp_path, [_yo(0)]), ahora=AHORA)
    salida = capsys.readouterr()
    assert _salidas(salida.out) == {"actuar": "false", "seguir": "false", "captura": "false", "diaria": "false",
                                    "captura_sin_diaria": "false", "falta_temporizador": "true"}
    assert "::error::" in salida.err


def test_linea_de_comandos_para_reanudar_no_necesita_la_carpeta_de_trabajo(tmp_path, capsys):
    (tmp_path / "relojes.json").write_text("[]", encoding="utf-8")
    arranque.main(["--reloj-vivo", str(tmp_path / "relojes.json"), "--rama", "main"])
    assert capsys.readouterr().out == "revivir=true\n"
    (tmp_path / "relojes.json").write_text(json.dumps([_corrida(10, "waiting")]), encoding="utf-8")
    arranque.main(["--reloj-vivo", str(tmp_path / "relojes.json"), "--rama", "main"])
    assert capsys.readouterr().out == "revivir=false\n"
    arranque.main(["--reloj-vivo", str(tmp_path / "no-existe.json"), "--rama", "main"])
    assert capsys.readouterr().out == "revivir=false\n"


def _flujo(nombre):
    return yaml.safe_load((RAIZ / ".github/workflows" / nombre).read_text(encoding="utf-8"))


def test_el_flujo_del_reloj_espera_en_su_entorno_y_solo_puede_pedir_flujos():
    flujo = _flujo("reloj.yml")
    assert flujo["permissions"] == {"actions": "write", "contents": "read"}
    assert "concurrency" not in flujo  # no comparte la cola «publicar»: no cancela búsquedas ni capturas en espera
    trabajo = flujo["jobs"]["relevo"]
    assert trabajo["environment"] == "reloj" and trabajo["timeout-minutes"] <= 5
    pasos = {p.get("name"): p for p in trabajo["steps"]}
    decidir = pasos["Decidir qué toca"]["run"]
    assert '--yo "$GITHUB_RUN_ID"' in decidir and "--reloj" in decidir
    for lista in ("reloj.yml", "bodega.yml", "incremental.yml"):
        assert f"gh run list --workflow {lista}" in decidir
    # Las búsquedas canceladas se miran una a una: solo la que no llegó a empezar se vuelve a pedir.
    assert 'select(.conclusion == "cancelled")' in decidir and "empezo" in decidir and "|| pasos=1" in decidir
    siguiente = pasos["Pedir el siguiente relevo"]
    assert siguiente["if"] == "steps.decidir.outputs.seguir == 'true'"
    assert "for intento in 1 2 3" in siguiente["run"] and "origen=relevo" in siguiente["run"]
    orden = [p.get("name") for p in trabajo["steps"]]
    assert orden.index("Pedir el siguiente relevo") < orden.index("Pedir la búsqueda diaria")  # primero la cadena
    diaria = pasos["Pedir la búsqueda diaria"]["run"]
    assert "bodega.yml" in diaria and "prueba=false" in diaria
    assert "enfoque" not in diaria  # la completa de siempre
    captura = pasos["Pedir la captura horaria"]
    # A mano su valor por defecto es de prueba; `reloj=true` hace que cuente como la programada.
    assert "incremental.yml" in captura["run"] and "prueba=false" in captura["run"] and "reloj=true" in captura["run"]
    # Un flujo desactivado a propósito (para no buscar un día) no pone el relevo en rojo ni deja el día sin capturas.
    assert "::warning::" in diaria and "fallo=true" in diaria and "::warning::" in captura["run"]
    assert "steps.diaria.outputs.fallo == 'true' && steps.decidir.outputs.captura_sin_diaria == 'true'" in captura["if"]
    texto = json.dumps(flujo)
    assert "secrets." not in texto and "SUPABASE" not in texto  # no usa ninguna clave ni datos de clientes
    # Ningún valor calculado se pega dentro de un guion: va por variables de entorno.
    for paso in trabajo["steps"]:
        assert "${{" not in paso.get("run", "")


def test_una_busqueda_real_reanuda_el_reloj_con_el_permiso_minimo():
    bodega = _flujo("bodega.yml")
    trabajo = bodega["jobs"]["reloj"]
    assert trabajo["permissions"] == {"actions": "write", "contents": "read"}
    assert trabajo["if"] == "${{ !inputs.prueba }}"  # una corrida de prueba no arranca nada
    pasos = {p.get("name"): p for p in trabajo["steps"]}
    assert "--reloj-vivo" in pasos["Mirar si el reloj está parado"]["run"]
    reanudar = pasos["Reanudar el reloj"]
    assert reanudar["if"] == "steps.reloj.outputs.revivir == 'true'"
    assert "gh workflow run reloj.yml" in reanudar["run"] and "origen=reanudar" in reanudar["run"]
    assert "::warning::" in reanudar["run"] and "${{" not in reanudar["run"]  # un Reloj desactivado no la pone en rojo
    assert "secrets." not in json.dumps(trabajo)
    assert "permissions" not in bodega["jobs"]["bodega"]  # la búsqueda sigue sin permiso de lanzar flujos
    # El vigía no reanuda: cuando GitHub dispara un horario, el del propio Reloj hace ese trabajo. Su lista de corridas
    # trae el estado, que la regla compartida usa para saber si hay una búsqueda en marcha.
    vigia = json.dumps(_flujo("incremental.yml")["jobs"]["vigia"])
    assert "reloj.yml" not in vigia and "headBranch,status" in vigia
    assert _flujo("reloj.yml")[True]["schedule"]  # PyYAML lee «on» como True
    # Una captura pedida por el Reloj respeta la marca de «captura horaria activa», como la programada.
    captura = json.dumps(_flujo("incremental.yml")["jobs"]["captura"])
    assert "github.event_name == 'workflow_dispatch' && !inputs.reloj" in captura
