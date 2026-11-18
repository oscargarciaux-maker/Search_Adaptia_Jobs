"""18 nov: GitHub no lanzó ningún horario programado durante horas y la búsqueda de las 6:30 no corrió. bodega.yml tiene
horarios de respaldo que solo trabajan si el anterior no lo hizo, y la «Captura horaria» la lanza una vez si hoy no
corrió (buscador/vigia.py)."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from buscador import entrega, validacion, vigia

RAIZ = Path(__file__).resolve().parent.parent
HOY = "2026-11-18"


def _metricas(tmp_path, dia):
    (tmp_path / "metricas_entrega.json").write_text(json.dumps({HOY: dia} if dia is not None else {}))
    return tmp_path


COMPLETA = {"meta_cumplida": True, "registro_confirmado": True, "pendientes_supabase": 0, "pasadas": 1}
INCOMPLETA_1 = {"meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0, "pasadas": 1}
INCOMPLETA_2 = dict(INCOMPLETA_1, pasadas=2)
ANTIGUA = {"meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0}  # sin «pasadas»


@pytest.mark.parametrize("tipo,dia,esperado", [
    ("principal", COMPLETA, True),
    ("principal", None, True),
    ("respaldo", None, True),               # no corrió la de las 6:30: el respaldo la hace
    ("respaldo", INCOMPLETA_1, False),      # ya corrió: la completa la segunda pasada, no el respaldo
    ("respaldo", COMPLETA, False),
    ("segunda", None, True),
    ("segunda", INCOMPLETA_2, True),        # la segunda de siempre no cambia
    ("segunda", COMPLETA, False),
    ("segunda-respaldo", None, True),
    ("segunda-respaldo", INCOMPLETA_1, True),   # la de las 8:30 no corrió
    ("segunda-respaldo", INCOMPLETA_2, False),  # ya hubo dos búsquedas: no se hace una tercera
    ("segunda-respaldo", ANTIGUA, True),
    ("segunda-respaldo", COMPLETA, False),
])
def test_cada_pasada_solo_trabaja_si_hace_falta(tmp_path, tipo, dia, esperado):
    assert validacion.hace_falta_pasada(_metricas(tmp_path, dia), HOY, tipo) is esperado


def test_sin_registro_legible_trabaja(tmp_path):
    (tmp_path / "metricas_entrega.json").write_text("{roto")
    assert validacion.hace_falta_pasada(tmp_path, HOY, "respaldo") is True
    with pytest.raises(ValueError):
        validacion.hace_falta_pasada(tmp_path, HOY, "otra")


def _resumen():
    return {"meta_cumplida": False, "supabase": {"pendientes": 0}, "registro_seleccion": {"filas": 1},
            "enlaces_comprobados": True,
            "roles": {"ux": {"candidatas": 3, "entregadas": 2, "faltan": 1, "reserva_sin_entregar": 0}}}


def test_las_pasadas_del_dia_se_cuentan_sin_las_capturas_horarias():
    historial = {}
    entrega.registrar_medicion(historial, _resumen(), HOY)
    assert historial[HOY]["pasadas"] == 1
    entrega.registrar_medicion(historial, _resumen(), HOY, pasada=False)  # captura horaria que completó el lote
    assert historial[HOY]["pasadas"] == 1
    entrega.registrar_medicion(historial, _resumen(), HOY)
    assert historial[HOY]["pasadas"] == 2
    viejo = {HOY: dict(ANTIGUA)}
    entrega.registrar_medicion(viejo, _resumen(), HOY)
    assert viejo[HOY]["pasadas"] == 2  # un registro anterior sin el campo cuenta como una


AHORA = datetime(2026, 11, 18, 13, 23, tzinfo=timezone.utc)


def _corrida(hora, evento="schedule", conclusion="success", fecha=HOY):
    return {"createdAt": f"{fecha}T{hora}:00Z", "event": evento, "conclusion": conclusion, "status": "completed"}


@pytest.mark.parametrize("metricas,corridas,ahora,esperado", [
    ({}, [], AHORA, True),                                             # como el 18 nov: nada corrió
    ({}, [_corrida("11:30", fecha="2026-11-17")], AHORA, True),        # solo la de ayer
    ({}, [_corrida("04:00")], AHORA, True),                            # 23:00 del 17 en Bogotá: es de ayer
    ({}, [_corrida("11:30", conclusion="cancelled")], AHORA, True),    # GitHub la canceló en la cola
    ({}, [_corrida("11:30", conclusion="")], AHORA, False),            # corriendo o en cola
    ({}, [_corrida("11:30", conclusion="failure")], AHORA, False),     # corrió: la segunda pasada la repite
    ({}, [_corrida("12:23", "workflow_dispatch", "cancelled")], AHORA, False),  # ya se lanzó una vez hoy
    ({HOY: COMPLETA}, [], AHORA, False),                               # ya terminó
    ({}, [], datetime(2026, 11, 18, 11, 23, tzinfo=timezone.utc), False),       # muy temprano
    ({}, None, AHORA, False),                                          # sin lista de corridas no lanza a ciegas
])
def test_el_vigia_lanza_una_sola_vez_y_solo_si_no_corrio(metricas, corridas, ahora, esperado):
    lanzar, motivo = vigia.hace_falta_lanzar(metricas, corridas, ahora)
    assert lanzar is esperado and motivo


def _flujo(nombre):
    return yaml.safe_load((RAIZ / ".github/workflows" / nombre).read_text(encoding="utf-8"))


def test_cada_horario_de_bodega_tiene_su_pasada():
    flujo = _flujo("bodega.yml")
    horarios = [h["cron"] for h in flujo[True]["schedule"]]  # PyYAML lee «on» como True
    assert "30 11 * * *" in horarios and "30 13 * * *" in horarios and len(horarios) == 5
    pasos = flujo["jobs"]["bodega"]["steps"]
    decidir = next(p for p in pasos if p.get("id") == "decidir")["run"]
    asignados = set(re.findall(r'"(\d+ \d+ \* \* \*)"', decidir))
    assert asignados == set(horarios) - {"30 11 * * *"}  # la principal cae en «*) principal»
    assert "--pasada" in decidir and "*) pasada=principal" in decidir


def test_el_vigia_solo_corre_programado_y_con_el_permiso_minimo():
    flujo = _flujo("incremental.yml")
    trabajo = flujo["jobs"]["vigia"]
    assert trabajo["if"] == "github.event_name == 'schedule'"
    assert trabajo["permissions"] == {"actions": "write", "contents": "read"}
    texto = json.dumps(trabajo)
    assert "gh workflow run bodega.yml" in texto and "prueba=false" in texto
    assert "secrets." not in texto  # no usa claves de Supabase ni de nadie
    # La captura sigue igual: sin permiso de acciones.
    assert "permissions" not in flujo["jobs"]["captura"]
