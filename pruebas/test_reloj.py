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
    (_corrida(10, "waiting", numero=51), False),      # el horario de respaldo dejó otro relevo esperando: se queda ese
    (_corrida(1, "queued", numero=51), False),
    (_corrida(30, "in_progress", numero=49), False),  # dos a la vez: sigue el más antiguo…
    (_corrida(30, "in_progress", numero=51), True),   # …que es este
    (_corrida(10, "waiting", numero=51, rama="otra"), True),  # una prueba en otra rama no es otra cadena
    (_corrida(40, "completed", numero=49), True),
])
def test_nunca_dos_cadenas_pero_el_relevo_que_se_retira_si_cumple_con_lo_que_toca(otro, sigue):
    actuar, seguir, _, falta = arranque.relevo(50, [_yo(), otro], "main", AHORA)
    assert actuar is True and seguir is sigue and falta is False


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
    (None, [], datetime(2026, 11, 27, 4, 0, tzinfo=timezone.utc), False),     # 23:00 del día anterior en Bogotá
    (HECHA, [], AHORA, False),                                                # ya terminó
    (None, [_corrida(20, "in_progress")], AHORA, False),                      # está corriendo
    (None, [_corrida(1, "queued")], AHORA, False),
    (None, [_corrida(25, conclusion="failure")], AHORA, False),               # falló: se revisa, no se repite sola
    (None, [_corrida(25, conclusion="cancelled")], AHORA, True),              # GitHub la canceló en la cola
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


def test_linea_de_comandos_del_reloj(tmp_path, capsys):
    ahora = datetime.now(timezone.utc)
    (tmp_path / "relojes.json").write_text(json.dumps([_yo(ahora=ahora)]))
    (tmp_path / "diarias.json").write_text(json.dumps([_corrida(5, "in_progress", ahora=ahora)]))
    (tmp_path / "capturas.json").write_text("[]")
    arranque.main(["--trabajo", str(tmp_path), "--reloj", str(tmp_path), "--yo", "50", "--rama", "main"])
    salida = capsys.readouterr()
    # Con una búsqueda diaria en marcha no pide ni otra ni la captura; la cadena sigue.
    assert _salidas(salida.out) == {"actuar": "true", "seguir": "true", "captura": "false", "diaria": "false",
                                    "falta_temporizador": "false"}
    assert "::notice::" in salida.err and "=" not in salida.err.replace("::", "")  # los motivos no van a GITHUB_OUTPUT

    (tmp_path / "relojes.json").write_text(json.dumps([_yo(0, ahora=ahora)]))
    arranque.main(["--trabajo", str(tmp_path), "--reloj", str(tmp_path), "--yo", "50", "--rama", "main"])
    salida = capsys.readouterr()
    assert _salidas(salida.out) == {"actuar": "false", "seguir": "false", "captura": "false", "diaria": "false",
                                    "falta_temporizador": "true"}
    assert "::error::" in salida.err

    arranque.main(["--trabajo", str(tmp_path), "--reloj-vivo", str(tmp_path / "capturas.json"), "--rama", "main"])
    assert capsys.readouterr().out == "revivir=true\n"
    arranque.main(["--trabajo", str(tmp_path), "--reloj-vivo", str(tmp_path / "no-existe.json"), "--rama", "main"])
    assert capsys.readouterr().out == "revivir=false\n"


def test_si_toca_la_diaria_no_se_pide_tambien_la_captura(tmp_path, capsys, monkeypatch):
    # En la cola del grupo «publicar» solo cabe una corrida en espera: la segunda cancelaría a la primera.
    ahora = datetime.now(timezone.utc)
    monkeypatch.setattr(arranque, "DIARIA_DESDE_UTC", (0, 0))
    monkeypatch.setattr(arranque, "hoy_bogota", lambda _ahora=None: "2026-01-01")  # ninguna corrida es «de hoy»
    for nombre, lista in (("relojes", [_yo(ahora=ahora)]), ("diarias", []), ("capturas", [])):
        (tmp_path / f"{nombre}.json").write_text(json.dumps(lista))
    arranque.main(["--trabajo", str(tmp_path), "--reloj", str(tmp_path), "--yo", "50", "--rama", "main"])
    salida = _salidas(capsys.readouterr().out)
    assert salida["diaria"] == "true" and salida["captura"] == "false"


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
    siguiente = pasos["Pedir el siguiente relevo"]
    assert siguiente["if"] == "steps.decidir.outputs.seguir == 'true'"
    orden = [p.get("name") for p in trabajo["steps"]]
    assert orden.index("Pedir el siguiente relevo") < orden.index("Pedir la búsqueda diaria")  # primero la cadena
    assert "bodega.yml" in pasos["Pedir la búsqueda diaria"]["run"] and "prueba=false" in pasos["Pedir la búsqueda diaria"]["run"]
    assert "enfoque" not in pasos["Pedir la búsqueda diaria"]["run"]  # la completa de siempre
    captura = pasos["Pedir la captura horaria"]["run"]
    assert "incremental.yml" in captura and "prueba=false" in captura  # a mano su valor por defecto es de prueba
    texto = json.dumps(flujo)
    assert "secrets." not in texto and "SUPABASE" not in texto  # no usa ninguna clave ni datos de clientes


def test_la_busqueda_y_la_captura_programada_reanudan_el_reloj_con_el_permiso_minimo():
    bodega = _flujo("bodega.yml")
    trabajo = bodega["jobs"]["reloj"]
    assert trabajo["permissions"] == {"actions": "write", "contents": "read"}
    assert trabajo["if"] == "${{ !inputs.prueba }}"  # una corrida de prueba no arranca nada
    texto = json.dumps(trabajo)
    assert "--reloj-vivo" in texto and "gh workflow run reloj.yml" in texto and "secrets." not in texto
    assert "permissions" not in bodega["jobs"]["bodega"]  # la búsqueda sigue sin permiso de lanzar flujos
    vigia = json.dumps(_flujo("incremental.yml")["jobs"]["vigia"])
    assert "--reloj-vivo" in vigia and "gh workflow run reloj.yml" in vigia
