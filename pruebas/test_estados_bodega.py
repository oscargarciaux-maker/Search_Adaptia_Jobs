"""Contrato v52: la búsqueda diaria termina COMPLETA, CORTA o en AVERÍA; solo la avería pone la corrida en rojo."""
import json
import sys
from pathlib import Path

import pytest

from buscador import arranque, validacion

RAIZ = Path(__file__).resolve().parents[1]


def _reporte(**cambios):
    r = {"vacantes_en_bodega": 120, "nuevas_hoy": 10,
         "entrega": {"meta_cumplida": True, "metas_por_rol": {"qa": 20},
                     "roles": {"qa": {"nombre": "QA", "entregadas": 20, "unicas": 20, "faltan": 0}},
                     "supabase": {"filas": 20, "enviadas": 20, "pendientes": 0, "errores": []}},
         "catalogo": {"filas": 50, "enviadas": 50, "pendientes": 0, "errores": []}}
    for clave, valor in cambios.items():
        r[clave] = valor
    return r


def _correr(tmp_path, monkeypatch, reporte, *extra):
    (tmp_path / "datos").mkdir(exist_ok=True)
    (tmp_path / "datos/salud.json").write_text(json.dumps(reporte), encoding="utf-8")
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    monkeypatch.setattr(sys, "argv", ["validacion", "--salida", str(tmp_path), *extra])
    try:
        validacion.main()
        codigo = 0
    except SystemExit as e:
        codigo = e.code
    return codigo, (resumen.read_text(encoding="utf-8") if resumen.exists() else "")


def test_completa_termina_bien(tmp_path, monkeypatch, capsys):
    codigo, resumen = _correr(tmp_path, monkeypatch, _reporte())
    salida = capsys.readouterr().out
    assert codigo == 0 and "::warning::" not in salida and "::error::" not in salida and "COMPLETA" in salida
    assert "Resultado del día: COMPLETA" in resumen and "| 1 | 20 | 20 | 0 |" in resumen


def test_meta_corta_termina_bien_con_aviso_y_resumen(tmp_path, monkeypatch, capsys):
    r = _reporte()
    r["entrega"].update(meta_cumplida=False)
    r["entrega"]["roles"]["qa"].update(entregadas=12, unicas=12, faltan=8, perfiles_bajo_minimo=2)
    r["verificacion_enlaces"] = {"seleccion_del_dia": {"vacantes": 12, "estados": {"verificada": 10, "pendiente": 2}}}
    codigo, resumen = _correr(tmp_path, monkeypatch, r)
    salida = capsys.readouterr().out
    assert codigo == 0 and "::error::" not in salida
    assert "::warning::La meta de selección diaria está incompleta." in salida
    assert "::warning::2 vacantes de la selección de hoy tienen el enlace sin comprobar" in salida
    assert "Resultado del día: CORTA" in resumen and "| 1 | 20 | 12 | 8 | 2 |" in resumen
    assert "QA" not in resumen and "QA" not in salida   # público: sin nombres de cargo (auditoría de exposición)
    assert "segunda pasada" in resumen and "no se comparten hasta comprobarlo" in resumen
    assert resumen.endswith("\n\n")  # el paso «Resumen» escribe después: no debe pegarse a la tabla
    assert "La meta de selección diaria está incompleta." in resumen and "2 sin comprobar" in resumen


def test_57014_en_la_reconciliacion_es_averia(tmp_path, monkeypatch, capsys):
    r = _reporte()
    r["catalogo"]["identidad"] = {"errores": ["ofertas_unicas: 57014; tiempo_consulta"]}
    codigo, resumen = _correr(tmp_path, monkeypatch, r)
    salida = capsys.readouterr().out
    assert codigo == 1 and "(57014)" in salida and "::error::" in salida
    assert "Resultado del día: AVERÍA" in resumen


def test_averia_manda_aunque_la_meta_tambien_quede_corta(tmp_path, monkeypatch):
    r = _reporte()
    r["entrega"]["meta_cumplida"] = False
    r["entrega"]["supabase"]["pendientes"] = 3
    assert validacion.estado(r) == validacion.AVERIA
    assert _correr(tmp_path, monkeypatch, r)[0] == 1


@pytest.mark.parametrize("romper", [
    lambda r: r["entrega"]["supabase"].update(pendientes=1),
    lambda r: r["catalogo"].update(pendientes=4),
    lambda r: r["entrega"].update(registro_seleccion={"errores": ["x"]}),
    lambda r: r.update(estado_operativo={"activo": True, "pendientes": {"reservas": 1}}),
    lambda r: r.update(vacantes_en_bodega=0),
    # 7.G: «vacantes que ya no encajan» dejó de ser avería (pruebas/test_no_encajan_corta.py).
])
def test_cada_averia_de_la_decision_falla(romper):
    r = _reporte()
    romper(r)
    assert validacion.estado(r) == validacion.AVERIA


def test_sin_variable_de_resumen_no_escribe_nada(tmp_path, monkeypatch):
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos/salud.json").write_text(json.dumps(_reporte()), encoding="utf-8")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(sys, "argv", ["validacion", "--salida", str(tmp_path)])
    validacion.main()
    assert not (tmp_path / "resumen.md").exists()


def test_catalogo_sigue_igual_y_no_mira_la_meta(tmp_path, monkeypatch, capsys):
    r = _reporte()
    r["entrega"]["meta_cumplida"] = False
    codigo, resumen = _correr(tmp_path, monkeypatch, r, "--catalogo")
    assert codigo == 0 and resumen == "" and "::warning::" not in capsys.readouterr().out
    r["catalogo"]["pendientes"] = 1
    assert _correr(tmp_path, monkeypatch, r, "--catalogo")[0] == 1


def test_un_dia_corto_sigue_pidiendo_la_segunda_pasada():
    """Lo que decide la segunda pasada (8:30) y su respaldo (9:30) es metricas_entrega.json, no el color de la corrida."""
    corto = {"pasadas": 1, "meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0}
    assert arranque.hace_falta_pasada(corto, "30 13 * * *") and arranque.hace_falta_pasada(corto, "30 14 * * *")
    assert not arranque.hace_falta_pasada(corto, "15 12 * * *")  # los respaldos de la primera ya no repiten


def test_el_aviso_solo_marca_fallo_cuando_la_corrida_falla():
    flujo = (RAIZ / ".github/workflows/bodega.yml").read_text(encoding="utf-8")
    avisar = flujo.split("- name: Avisar", 1)[1].split("\n  reloj:", 1)[0]
    assert 'job.status }}" = "success"' in avisar and '"$AVISO/fail"' in avisar
    assert "python -m buscador.validacion --salida privado/estado_trabajo\n" in flujo
