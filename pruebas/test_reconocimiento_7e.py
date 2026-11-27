"""P-7.E (27 nov): tres defectos de reconocimiento hallados al medir con la bodega real (sección 7.A).

1. Lugar: LinkedIn escribe «California, Pará, Brasil» en avisos de EE. UU. (4 de Adobe con el rango salarial de EE. UU.).
2. Cargo: «Penetration Tester» entraba como QA por el término suelto «tester».
3. Eficiencia: el rescate comprobaba enlaces de remotas ampliadas que ya no podían entrar (tope de 5 de la 7.A).
"""
from datetime import date, timedelta

import pytest

from buscador import paises
from buscador.medicion import cargo_crudo
from panel import ejecutor
from panel.afinidad import MINIMO_POR_PERFIL
from panel.contenido import cargo_operativo
from panel.repositorio import hoy
from panel.terminos import grado
from pruebas.panel.test_ampliacion_marcada import _comprobada, _recibidas, _Supabase, meta_diez, presencial  # noqa: F401
from pruebas.panel.test_control import cfg, cfg_un_perfil  # noqa: F401 (fixtures)


# ── 1. Lugar ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _lugar(ubicacion):
    r = paises.elegibles("Senior Product Manager", ubicacion)
    return r["paises_mundo"]


def test_california_para_brasil_de_linkedin_es_eeuu():
    assert _lugar("California, Pará, Brasil") == ["US"]
    assert _lugar("california, para, brasil") == ["US"]  # sin tildes ni mayúsculas, igual


def test_el_caso_real_de_brasil_sigue_siendo_brasil():
    # Califórnia es un municipio de Paraná: antes salía Brasil y EE. UU. (por el nombre del estado).
    assert _lugar("Califórnia, Paraná, Brasil") == ["BR"]
    assert _lugar("Belém, Pará, Brasil") == ["BR"]


@pytest.mark.parametrize("ubicacion,esperado", [
    ("Birmingham, Alabama, United States", ["US"]),  # antes también Reino Unido (West Midlands)
    ("Palermo, Capital Federal, Argentina", ["AR"]),  # antes también Italia
    ("La Florida, RM, Chile", ["CL"]),  # antes también EE. UU.
    ("Münster, NW, Germany", ["DE"]),  # antes también Irlanda
    ("San Francisco, California, Estados Unidos", ["US"]),
    ("Tijuana, Baja California, México", ["MX"]),
])
def test_el_pais_escrito_al_final_manda_sobre_un_estado_de_otro_pais(ubicacion, esperado):
    assert _lugar(ubicacion) == esperado


@pytest.mark.parametrize("ubicacion,esperado", [
    ("New York, United States; London, United Kingdom", ["GB", "US"]),  # varias ubicaciones
    ("Remote - European Union, Germany, Hamburg, France", ["DE", "FR"]),  # una lista de países no se recorta
])
def test_varias_ubicaciones_no_se_recortan(ubicacion, esperado):
    assert set(esperado) <= set(_lugar(ubicacion))


def test_el_archivo_de_correcciones_tiene_el_formato_esperado():
    corregidas = paises.ubicaciones_corregidas()
    assert corregidas and all(k == paises.clave(k) and v.strip() for k, v in corregidas.items())
