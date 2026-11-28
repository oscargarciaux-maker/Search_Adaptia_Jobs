"""7.G (decisión de Oscar, 27 nov): una vacante de la selección de hoy que ya no encaja no es una avería, pero NO se
comparte. Cada asignación guarda la copia del perfil y del cargo con que se hizo; antes el panel solo miraba esa copia,
así que si el operador editaba el perfil o el cargo después, la vacante seguía «lista» y entraba al WhatsApp."""
from copy import deepcopy
from datetime import date, timedelta

import pytest

from buscador import familias
from panel import ejecutor, servicio
from panel.repositorio import hoy
from pruebas.panel.test_ampliacion_marcada import _Registro
from pruebas.panel.test_control import cfg, cfg_un_perfil, trabajo  # noqa: F401 (fixtures)


class _ConVigente(_Registro):
    """Como el repositorio real: devuelve también el perfil y el cargo de la versión vigente del día."""
    vigente = None

    def resultados(self, cliente_id, fecha):
        r = super().resultados(cliente_id, fecha)
        return {**r, "perfiles": self.vigente["perfiles"], "cargos": self.vigente["cargos"]}


@pytest.fixture
def asignada(cfg_un_perfil):  # noqa: F811 (la fixture importada de test_control)
    v = trabajo()  # Product Designer, remota mundial, en inglés: le sirve al perfil de Colombia
    v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
    repo = _ConVigente("cargo:" + cfg_un_perfil["cargos"][0]["id"], v)
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg_un_perfil}, hoy())
    assert len(repo.asignaciones) == 1
    repo.vigente = deepcopy(cfg_un_perfil)
    return repo


def _ficha(repo):
    r = servicio.resultados(repo)
    return r, r["vacantes"][0]


def test_sin_cambios_sigue_lista(asignada):
    r, v = _ficha(asignada)
    assert v["estado"] == "lista" and v["enlace"] and r["listas"] == r["para_copiar"] == 1


def test_perfil_editado_despues_no_se_comparte_y_queda_marcada(asignada):
    asignada.vigente["perfiles"][0]["idiomas"] = ["es"]  # el operador quita el inglés después de la asignación
    r, v = _ficha(asignada)
    assert v["estado"] == "no_encaja" and v["enlace"] == ""
    assert servicio.NO_ENCAJA_PERFIL in v["motivos"]
    assert r["listas"] == r["para_copiar"] == 0  # ni lista, ni WhatsApp, ni «Copiar»
    assert len(asignada.asignaciones) == 1  # no se borra nada: la asignación sigue guardada


def _cambiar_cargo(repo):
    repo.vigente["cargos"][0].update(nombre="QA Engineer", terminos_exactos=["QA Engineer"], terminos_similares=[],
                                     terminos_cercanos=[])


def test_cargo_editado_despues_no_se_comparte_y_queda_marcada(asignada):
    _cambiar_cargo(asignada)
    r, v = _ficha(asignada)
    assert v["estado"] == "no_encaja" and v["enlace"] == "" and servicio.NO_ENCAJA_CARGO in v["motivos"]
    assert r["para_copiar"] == 0


def test_aprobada_a_mano_no_se_retira_por_el_cargo(asignada):
    asignada.asignaciones[0]["explicacion"].append({"aprobada_por": "operador"})
    _cambiar_cargo(asignada)
    assert _ficha(asignada)[1]["estado"] == "lista"


def test_una_ampliada_sigue_si_el_perfil_editado_ya_la_acepta_sin_ampliar(asignada):
    """Thermos: un perfil presencial que recibió una remota «remota_cercana» y después pasa a aceptar remoto."""
    fila = asignada.asignaciones[0]
    fila["explicacion"].append({"ampliacion": "remota_cercana"})
    fila["filtros"] = dict(fila["filtros"], modalidades=["presencial"],
                           ubicaciones=[dict(u, modalidades=["presencial"]) for u in fila["filtros"]["ubicaciones"]])
    assert _ficha(asignada)[1]["estado"] == "lista"  # el perfil vigente acepta remoto: encaja sin ampliar


def test_sin_editar_el_cargo_no_se_vuelve_a_mirar(asignada, monkeypatch):
    """Thermos: un título aprendido que salió por el tope de 200 no retira lo asignado si nadie editó el cargo."""
    editado = servicio._cargo_editado
    assert not editado({"nombre": "QA", "terminos_exactos": ["a", "b"]}, {"nombre": "QA", "terminos_exactos": ["b", "a"]})
    assert editado({"nombre": "QA", "terminos_exactos": ["a"]}, {"nombre": "QA", "terminos_exactos": ["a", "b"]})
    monkeypatch.setattr(servicio, "_cargo_editado", lambda vigente, guardado: False)
    _cambiar_cargo(asignada)
    assert _ficha(asignada)[1]["estado"] == "lista"


def test_perfil_o_cargo_que_salio_de_la_configuracion_no_se_toca(asignada):
    asignada.vigente.update(perfiles=[], cargos=[])  # lo entregado de un cargo que salió se conserva (v49)
    assert _ficha(asignada)[1]["estado"] == "lista"


def test_un_dia_anterior_no_cambia(asignada):
    asignada.vigente["perfiles"][0]["idiomas"] = ["es"]
    asignada.ejecucion = dict(asignada.ejecucion, fecha=(date.fromisoformat(hoy()) - timedelta(days=1)).isoformat())
    assert _ficha(asignada)[1]["estado"] != "no_encaja"
