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


# ── 2. Cargo ─────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def qa():
    return cargo_operativo(cargo_crudo("QA"))


@pytest.mark.parametrize("titulo", ["Penetration Tester", "Senior Web Application Penetration Tester",
                                    "Penetration Testers", "AI Red Team Tester", "Analista de Pentesting",
                                    "Senior IT-Security Consultant / Penetration Tester (m/w/d)"])
def test_seguridad_ofensiva_no_es_qa(qa, titulo):
    assert grado(titulo, qa)[0] is None


@pytest.mark.parametrize("titulo,esperado", [
    ("QA Tester", "exacto"), ("Software Tester", "exacto"), ("Test Engineer", "exacto"), ("Tester", "exacto"),
    ("Manual Tester", "exacto"), ("Game Tester", "exacto"), ("Testers", "exacto"), ("QA Software Engineer", "exacto"),
    ("Lider Tecnico QA", "exacto"),
])
def test_los_tester_de_verdad_siguen_siendo_qa(qa, titulo, esperado):
    assert grado(titulo, qa)[0] == esperado


def test_penetration_tester_sigue_siendo_ciberseguridad():
    pentester = cargo_operativo(cargo_crudo("Pentester"))
    assert grado("Penetration Tester", pentester)[0] == "exacto"
    assert grado("Analista de Pentesting", pentester)[0] == "similar"


# ── 3. Eficiencia del rescate ────────────────────────────────────────────────────────────────────────────────────────
def _sin_comprobar(n, ubicacion, remoto):
    v = _comprobada(n, ubicacion, remoto)
    v["verificacion"]["enlaces"] = []
    return v


def test_el_rescate_no_comprueba_ampliadas_para_quien_ya_tiene_5(meta_diez, monkeypatch):  # noqa: F811
    from buscador import verificar_enlaces
    pedidas = []
    monkeypatch.setattr(verificar_enlaces, "auditar", lambda vacantes, cache, **_: pedidas.extend(vacantes) or 0)
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    previas = [{"delivery_date": ayer, "role_id": "otro", "vacante_id": v["id"], "match_grade": "exact", "snapshot": v}
               for v in [_comprobada(n, "Bogotá, Colombia", None) for n in range(MINIMO_POR_PERFIL)]]
    remotas = [_sin_comprobar(10 + n, "Remote - Colombia", True) for n in range(8)]
    en_su_ciudad = [_sin_comprobar(30 + n, "Bogotá, Colombia", None) for n in range(2)]
    repo = _Supabase(previas)  # reutilizar le da 5 de su ciudad: las remotas ya no pueden entrar
    ejecutor.registrar(repo, {"revision": 1, "configuracion": meta_diez}, hoy(), vacantes=remotas + en_su_ciudad,
                       cache_enlaces={})
    assert len(_recibidas(repo, meta_diez)) == MINIMO_POR_PERFIL
    # Antes se pedían las 10 (3 por plaza que falta hasta la meta); ahora solo las 2 que pueden entrar.
    assert {v["id"] for v in pedidas} == {v["id"] for v in en_su_ciudad}


def test_el_rescate_si_comprueba_ampliadas_mientras_caben(meta_diez, monkeypatch):  # noqa: F811
    from buscador import verificar_enlaces
    pedidas = []
    monkeypatch.setattr(verificar_enlaces, "auditar", lambda vacantes, cache, **_: pedidas.extend(vacantes) or 0)
    remotas = [_sin_comprobar(10 + n, "Remote - Colombia", True) for n in range(20)]
    ejecutor.registrar(_Supabase(), {"revision": 1, "configuracion": meta_diez}, hoy(), vacantes=remotas,
                       cache_enlaces={})
    assert len(pedidas) == MINIMO_POR_PERFIL * 3  # 3 por plaza de ampliada (antes 20: 3 por plaza hasta la meta)
