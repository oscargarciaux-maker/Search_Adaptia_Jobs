"""Contrato v35: formulario del cliente. Zonas UTC (las antiguas se convierten), restricción «Otra…» que solo ordena y
cifra «últimos 30 días» con su promedio diario."""
import pytest
from pydantic import ValidationError

from panel import afinidad, importar, servicio
from panel.modelos import Configuracion, horas_de_zona
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy
from pruebas.panel.test_control import _perfil_mundo, _vacante_texto, trabajo


def test_zonas_utc_y_conversion_de_las_antiguas():
    p = _perfil_mundo(acepta_horario=["us_este", "europa", "us_pacifico", "UTC+5:30", "UTC-5"])
    assert p.acepta_horario == ["UTC-5", "UTC+1", "UTC-8", "UTC+5:30"]
    assert horas_de_zona("UTC+5:30") == 5.5 and horas_de_zona("UTC-3") == -3 and horas_de_zona("Lima") is None
    for mala in (["UTC+20"], ["Bogotá"], ["UTC-5:15"]):
        with pytest.raises(ValidationError):
            _perfil_mundo(acepta_horario=mala)


def test_la_zona_utc_hace_lo_mismo_que_el_horario_antiguo():
    est = _vacante_texto("Remote", "You must overlap with EST hours.")
    antiguo = afinidad.evaluar(est, _perfil_mundo(vive_en="ES", acepta_horario=["us_este"]), hoy())
    nuevo = afinidad.evaluar(est, _perfil_mundo(vive_en="ES", acepta_horario=["UTC-5"]), hoy())
    assert antiguo["compatible"] and nuevo["compatible"]
    assert not afinidad.evaluar(est, _perfil_mundo(vive_en="ES", acepta_horario=["UTC+9"]), hoy())["compatible"]


def test_otra_restriccion_solo_ordena_y_deja_etiqueta():
    p = _perfil_mundo(restricciones=[{"tipo": "otra", "texto": "  call   center "}])
    assert p.restricciones[0].texto == "call center"
    r = afinidad.evaluar(trabajo(titulo="Product Designer for call center", paises=["CO"]), p, hoy())
    assert r["compatible"] and "Menciona «call center»" in r["avisos"]
    assert not afinidad.evaluar(trabajo(paises=["CO"]), p, hoy())["avisos"]
    with pytest.raises(ValidationError):
        _perfil_mundo(restricciones=[{"tipo": "otra", "texto": "https://x.co"}])


def test_ultimos_30_dias_cuenta_tambien_las_ya_entregadas():
    repo = RepositorioDemo()
    modelo = Configuracion.model_validate(configuracion_demo())
    r = servicio.vista_previa(repo, modelo)["perfiles"][str(modelo.perfiles[0].id)]
    assert r["ultimos_30"] > r["compatibles"] > 0
    assert r["por_dia"] == round(r["ultimos_30"] / 30, 1)


def test_importador_acepta_zonas_utc():
    errores = []
    assert importar._zonas("UTC-3|gmt+1|EE. UU. Pacífico", errores) == ["UTC-3", "UTC+1", "us_pacifico"]
    importar._zonas("Lima", errores)
    assert errores and "UTC-5" in errores[0]
