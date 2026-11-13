"""Contrato v19: municipios y ciudades del mundo (GeoNames) como último recurso, regiones como ubicación y la región
del título cuando la ubicación no dice nada. Casos tomados de la revisión de Oscar (13 nov)."""
import pytest

from buscador import paises


def _e(ubicacion, titulo="Product Analyst", remoto=None, descripcion=""):
    return paises.elegibles(titulo, ubicacion, descripcion, remoto)


@pytest.mark.parametrize("ubicacion", ["Inca", "Abrera", "Cassà de la Selva", "Esplugues de Llobregat",
                                       "Riba-roja de Túria", "Manresa y alrededores", "Palma"])
def test_municipios_de_espana(ubicacion):
    r = _e(ubicacion)
    assert r["paises"] == ["ES"] and r["confianza"] in ("alta", "media")


@pytest.mark.parametrize("ubicacion", ["Harrisburg, PA", "Cambridge y alrededores", "Calcuta y alrededores",
                                       "Johannesburgo y alrededores", "Nicosia", "Tel Aviv", "Köln", "Sterling"])
def test_ciudades_extranjeras(ubicacion):
    r = _e(ubicacion)
    assert r["paises"] == [] and r["confianza"] == "alta"


def test_ambiguas_y_listas_curadas_no_cambian():
    assert _e("Camas")["confianza"] == "baja"  # Camas (Sevilla) y Camas (Washington): no decide
    assert _e("Bogotá")["paises"] == ["CO"] and _e("Madrid")["paises"] == ["ES"]
    assert _e("Córdoba")["confianza"] == "baja"  # España y Argentina
    assert paises.lugar_conocido("Inca") == "ES" and paises.lugar_conocido("Harrisburg, PA") == "fuera"
    assert paises.lugar_conocido("Inca; Harrisburg, PA") is None  # tramos contradictorios


def test_region_como_ubicacion_y_region_del_titulo():
    for ubicacion in ("LATAM", "Latin America", "América Latina"):
        r = _e(ubicacion)
        assert len(r["paises"]) == 19 and "ES" not in r["paises"] and r["confianza"] == "alta"
    assert _e("Remote job", "Latam | Code & Game Tutor", True)["confianza"] == "alta"
    r = _e("Remote", "Sr. Customer Success Manager - EMEA", True)
    assert r["paises"] == ["ES"] and r["confianza"] == "alta"
    # Con una ubicación concreta, la región del título no la reemplaza.
    assert _e("Tel Aviv", "Sales Manager - LATAM")["paises"] == []
