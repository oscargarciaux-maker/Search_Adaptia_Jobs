"""Contrato v32: áreas metropolitanas con formato de LinkedIn («Roma y alrededores») se clasifican solas; un nombre
ambiguo sin ese sufijo («Granada») sigue preguntándose."""
import pytest

from buscador import paises, vacante


def _v(ubicacion):
    return vacante.crear("Product Designer", "Acme", f"https://jobs.lever.co/a/{abs(hash(ubicacion))}", "Lever",
                         ubicacion=ubicacion, descripcion="We build products. " * 5, fecha="2026-11-16",
                         hoy="2026-11-16", remoto=None)


@pytest.mark.parametrize("ubicacion,mundo", [("Roma y alrededores", ["IT"]), ("Greater Rome Area", ["IT"]),
                                             ("Paris y alrededores", ["FR"])])
def test_area_extranjera_queda_clara_y_fuera(ubicacion, mundo):
    v = _v(ubicacion)
    assert v["confianza_pais"] == "alta" and v["paises"] == [] and v["paises_mundo"] == mundo


@pytest.mark.parametrize("ubicacion,pais", [("Granada y alrededores", "ES"), ("Guadalajara y alrededores", "MX"),
                                            ("Área metropolitana de Santiago", "CL")])
def test_area_cubierta_queda_en_su_pais(ubicacion, pais):
    v = _v(ubicacion)
    assert v["confianza_pais"] == "alta" and v["paises"] == [pais] and v["paises_mundo"] == [pais]


def test_nombre_ambiguo_sin_sufijo_sigue_por_confirmar():
    assert _v("Granada")["confianza_pais"] == "baja"
    assert paises.area_metropolitana("Granada") == "" and paises.area_metropolitana("Roma y alrededores") == "IT"
