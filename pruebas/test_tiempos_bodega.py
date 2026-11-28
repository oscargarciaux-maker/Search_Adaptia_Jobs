"""P-12.3: el registro público de la Bodega muestra inicio y segundos de cada subpaso, y solo texto fijo y cifras."""
import re

import pytest

from buscador import bodega, refuerzo, verificar_enlaces

LINEA = re.compile(r"^\[\d\d:\d\d:\d\d\] (Inicio: .+|Fin: .+ en \d+ s(, [a-z_]+ \d+)*)$")


def test_tramo_deja_inicio_y_fin_con_cifras_enteras(capsys):
    with bodega.tramo("Refuerzo, ronda 1: buscar en las fuentes") as cifras:
        cifras["avisos"] = 7
        cifras["lugar"] = "Bogotá"  # una cadena no es cifra: no se imprime
        cifras["activo"] = True      # ni un booleano
    lineas = capsys.readouterr().out.strip().splitlines()
    assert len(lineas) == 2 and all(LINEA.match(x) for x in lineas)
    assert lineas[0].endswith("Inicio: Refuerzo, ronda 1: buscar en las fuentes")
    assert lineas[1].endswith("Fin: Refuerzo, ronda 1: buscar en las fuentes en 0 s, avisos 7")
    assert "Bogot" not in "".join(lineas) and "activo" not in "".join(lineas)


def test_tramo_registra_el_fin_aunque_falle(capsys):
    with pytest.raises(ValueError):
        with bodega.tramo("Rescate con Apify"):
            raise ValueError("secreto de cliente")
    salida = capsys.readouterr().out
    assert "Fin: Rescate con Apify en" in salida and "secreto" not in salida


def test_completar_mide_cada_evaluacion(monkeypatch, capsys):
    from buscador import entrega
    llamadas = []
    monkeypatch.setattr(entrega, "elegir", lambda *a, **k: ({}, {"roles": {"r": {"faltan": 2}}}))
    cfg_entrega = {"roles": [{"id": "r", "familias": ["f"]}]}
    _, rondas = refuerzo.completar([], {}, "2026-11-28", cfg_entrega, {"rondas": 2}, [{"id": "f"}],
                                   lambda mapa, n: (llamadas.append(n) or [], {}), lambda v, n: v, medir=bodega.tramo)
    salida = capsys.readouterr().out
    assert llamadas == [1, 2] and len(rondas) == 2
    for n in (1, 2):
        assert f"Inicio: Refuerzo, ronda {n}: evaluar faltantes" in salida
        assert f"Fin: Refuerzo, ronda {n}: evaluar faltantes" in salida


def test_completar_sin_medir_no_imprime(monkeypatch, capsys):
    from buscador import entrega
    monkeypatch.setattr(entrega, "elegir", lambda *a, **k: ({}, {"roles": {}}))
    refuerzo.completar([], {}, "2026-11-28", {"roles": []}, {"rondas": 1}, [], lambda m, n: ([], {}), lambda v, n: v)
    assert capsys.readouterr().out == ""


def test_preparar_mide_sus_subpasos(monkeypatch, capsys):
    monkeypatch.setattr(verificar_enlaces, "auditar", lambda *a, **k: 3)
    monkeypatch.setattr(verificar_enlaces, "anotar", lambda v, c: None)
    monkeypatch.setattr(verificar_enlaces, "resumen", lambda vs: {})
    monkeypatch.setattr(verificar_enlaces, "cola_de_seleccion", lambda *a, **k: [])
    verificar_enlaces.preparar([{"id": "a", "titulo": "t", "url": "u"}], {}, "2026-11-28", {},
                               cfg={"vacantes_por_corrida": 10, "segundos_corrida": 5}, medir=bodega.tramo)
    salida = capsys.readouterr().out
    assert "Inicio: Comprobar enlaces: selección del día y resto" in salida
    assert all(LINEA.match(x) for x in salida.strip().splitlines())
