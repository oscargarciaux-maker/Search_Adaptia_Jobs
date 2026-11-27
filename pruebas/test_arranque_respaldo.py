"""18 nov: GitHub no lanzó ningún horario programado durante horas y la búsqueda de las 6:30 no corrió. bodega.yml tiene
horarios de respaldo que solo trabajan si el anterior no lo hizo, y la «Captura horaria» la lanza una vez si hoy no
corrió. Una sola regla para todo: buscador/arranque.py."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from buscador import arranque, entrega

RAIZ = Path(__file__).resolve().parent.parent
HOY = "2026-11-18"
PRINCIPAL, RESPALDO, SEGUNDA, SEGUNDA_RESPALDO = "30 11 * * *", "15 12 * * *", "30 13 * * *", "30 14 * * *"

COMPLETA = {"meta_cumplida": True, "registro_confirmado": True, "pendientes_supabase": 0, "pasadas": 1}
INCOMPLETA_1 = {"meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0, "pasadas": 1}
INCOMPLETA_2 = dict(INCOMPLETA_1, pasadas=2)
SOLO_CAPTURA = dict(INCOMPLETA_1, pasadas=0)  # una captura horaria completó un lote (v43), sin búsqueda diaria
ANTIGUA = {"meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0}  # sin «pasadas»


@pytest.mark.parametrize("horario,dia,esperado", [
    ("", COMPLETA, True),                    # a mano o por el vigía: siempre
    (PRINCIPAL, None, True),
    (PRINCIPAL, INCOMPLETA_1, False),        # GitHub la lanzó tarde y un respaldo ya la hizo: no repite
    (RESPALDO, None, True),                  # no corrió la de las 6:30: el respaldo la hace
    (RESPALDO, SOLO_CAPTURA, True),
    (RESPALDO, INCOMPLETA_1, False),         # ya corrió: la completa la segunda pasada, no el respaldo
    (RESPALDO, ANTIGUA, False),
    ("50 12 * * *", None, True),
    (SEGUNDA, None, True),
    (SEGUNDA, INCOMPLETA_2, True),           # la segunda de siempre no cambia
    (SEGUNDA, COMPLETA, False),
    (SEGUNDA_RESPALDO, None, True),
    (SEGUNDA_RESPALDO, INCOMPLETA_1, True),  # la de las 8:30 no corrió
    (SEGUNDA_RESPALDO, INCOMPLETA_2, False), # ya hubo dos búsquedas: no se hace una tercera
    (SEGUNDA_RESPALDO, ANTIGUA, True),
    (SEGUNDA_RESPALDO, COMPLETA, False),
])
def test_cada_horario_solo_trabaja_si_hace_falta(horario, dia, esperado):
    assert arranque.hace_falta_pasada(dia, horario) is esperado


def test_un_horario_sin_pasada_es_un_error():
    with pytest.raises(ValueError):
        arranque.hace_falta_pasada(None, "0 9 * * *")


def test_registro_roto_cuenta_como_sin_registro(tmp_path):
    (tmp_path / "metricas_entrega.json").write_text("{roto", encoding="utf-8")
    assert arranque.leer_dia(tmp_path, HOY) is None
    assert arranque.leer_dia(tmp_path / "no-existe", HOY) is None


def test_linea_de_comandos_imprime_lo_que_lee_el_flujo(tmp_path, capsys):
    (tmp_path / "metricas_entrega.json").write_text(json.dumps({arranque.hoy_bogota(): INCOMPLETA_1}), encoding="utf-8")
    arranque.main(["--trabajo", str(tmp_path), "--horario", RESPALDO])
    arranque.main(["--trabajo", str(tmp_path), "--horario", SEGUNDA])
    arranque.main(["--trabajo", str(tmp_path), "--horario", ""])
    assert capsys.readouterr().out.splitlines() == ["ejecutar=false", "ejecutar=true", "ejecutar=true"]
    (tmp_path / "corridas.json").write_text("[]", encoding="utf-8")
    arranque.main(["--trabajo", str(tmp_path), "--vigia", str(tmp_path / "corridas.json"), "--rama", "main"])
    salida = capsys.readouterr()
    assert salida.out == "lanzar=false\n" and "::notice::" in salida.err  # el motivo no va a GITHUB_OUTPUT


def _resumen():
    return {"meta_cumplida": False, "supabase": {"pendientes": 0}, "registro_seleccion": {"filas": 1},
            "enlaces_comprobados": True,
            "roles": {"ux": {"candidatas": 3, "entregadas": 2, "faltan": 1, "reserva_sin_entregar": 0}}}


def test_las_pasadas_del_dia_se_cuentan_sin_las_capturas_horarias():
    historial = {}
    entrega.registrar_medicion(historial, _resumen(), HOY, busqueda_diaria=False)  # captura que completó un lote
    assert historial[HOY]["pasadas"] == 0 and arranque.busquedas_diarias(historial[HOY]) == 0
    entrega.registrar_medicion(historial, _resumen(), HOY, busqueda_diaria=True)
    assert historial[HOY]["pasadas"] == 1
    entrega.registrar_medicion(historial, _resumen(), HOY, busqueda_diaria=True)
    assert historial[HOY]["pasadas"] == 2
    viejo = {HOY: dict(ANTIGUA)}
    entrega.registrar_medicion(viejo, _resumen(), HOY, busqueda_diaria=True)
    assert viejo[HOY]["pasadas"] == 2  # un registro anterior sin el campo cuenta como una


AHORA = datetime(2026, 11, 18, 13, 23, tzinfo=timezone.utc)


def _corrida(hora, evento="schedule", conclusion="success", fecha=HOY, rama="main"):
    return {"createdAt": f"{fecha}T{hora}:00Z", "event": evento, "conclusion": conclusion, "headBranch": rama}


@pytest.mark.parametrize("dia,corridas,ahora,esperado", [
    (None, [], AHORA, True),                                             # como el 18 nov: nada corrió
    (SOLO_CAPTURA, [], AHORA, True),                                     # una captura no es la búsqueda diaria
    (None, [_corrida("11:30", fecha="2026-11-17")], AHORA, True),        # solo la de ayer
    (None, [_corrida("04:00")], AHORA, True),                            # 23:00 del 17 en Bogotá: es de ayer
    (None, [_corrida("11:30", conclusion="cancelled")], AHORA, True),    # GitHub la canceló en la cola
    (None, [_corrida("12:00", "workflow_dispatch", rama="prueba")], AHORA, True),  # prueba en otra rama
    (None, [_corrida("11:30", conclusion="")], AHORA, False),            # corriendo o en cola
    (None, [_corrida("11:30", conclusion="failure")], AHORA, False),     # corrió: la segunda pasada la repite
    (None, [_corrida("12:23", "workflow_dispatch", "cancelled")], AHORA, False),  # ya se lanzó una vez hoy
    (COMPLETA, [], AHORA, False),                                        # ya terminó
    (None, [], datetime(2026, 11, 18, 11, 23, tzinfo=timezone.utc), False),       # muy temprano
    (None, None, AHORA, False),                                          # sin lista de corridas no lanza a ciegas
])
def test_el_vigia_lanza_una_sola_vez_y_solo_si_no_corrio(dia, corridas, ahora, esperado):
    lanzar, motivo = arranque.hace_falta_lanzar(dia, corridas, "main", ahora)
    assert lanzar is esperado and motivo


def test_el_vigia_sin_rama_no_lanza():
    assert arranque.hace_falta_lanzar(None, [], "", AHORA)[0] is False


def _flujo(nombre):
    return yaml.safe_load((RAIZ / ".github/workflows" / nombre).read_text(encoding="utf-8"))


def test_cada_horario_de_bodega_tiene_su_pasada():
    flujo = _flujo("bodega.yml")
    horarios = {h["cron"] for h in flujo[True]["schedule"]}  # PyYAML lee «on» como True
    assert horarios == set(arranque.HORARIOS)
    assert arranque.HORARIOS == {PRINCIPAL: "primera", RESPALDO: "primera", "50 12 * * *": "primera",
                                 SEGUNDA: "segunda", SEGUNDA_RESPALDO: "segunda-respaldo"}
    pasos = flujo["jobs"]["bodega"]["steps"]
    decidir = next(p for p in pasos if p.get("id") == "decidir")["run"]
    assert '--horario "${{ github.event.schedule }}"' in decidir
    avisar = next(p for p in pasos if p.get("name") == "Avisar")
    assert "steps.decidir.outputs.ejecutar != 'false'" in avisar["if"]  # un respaldo que no trabaja no avisa


def test_el_vigia_solo_corre_programado_y_con_el_permiso_minimo():
    flujo = _flujo("incremental.yml")
    trabajo = flujo["jobs"]["vigia"]
    assert trabajo["if"] == "github.event_name == 'schedule'"
    assert trabajo["permissions"] == {"actions": "write", "contents": "read"}
    texto = json.dumps(trabajo)
    assert "gh workflow run bodega.yml" in texto and "prueba=false" in texto and "headBranch" in texto
    assert "secrets." not in texto  # no usa claves de Supabase ni de nadie
    assert "permissions" not in flujo["jobs"]["captura"]  # la captura sigue sin permiso de acciones
