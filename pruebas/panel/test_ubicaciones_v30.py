"""Contrato v30: dónde trabajaría, en filas (países, ciudades y modalidades por fila)."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from panel.afinidad import evaluar, relajado
from panel.api import crear_app
from panel.modelos import Perfil, explicar
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy

BASE = {"id": "00000000-0000-0000-0000-000000000001", "cliente_id": "00000000-0000-0000-0000-000000000002",
        "cargo_id": "00000000-0000-0000-0000-000000000003", "idiomas": ["es", "en"]}


def _v(modalidad, paises=(), mundo=(), ubicacion="", **extra):
    return {"titulo": "Product Designer", "modalidad": modalidad, "paises": list(paises),
            "paises_mundo": list(mundo or paises), "confianza_pais": "alta", "ubicacion": ubicacion,
            "idioma": "en", "fecha_publicacion": hoy(), **extra}


def _ok(v, p):
    return evaluar(v, p, hoy())["compatible"]


def test_un_perfil_anterior_se_lee_en_filas_sin_cambiar_lo_que_recibe():
    p = Perfil.model_validate({**BASE, "vive_en": "MX", "modalidades": ["remoto", "presencial"],
                               "paises_presenciales_extra": ["CO"], "puede_trabajar_en": ["US"],
                               "ciudades": ["Monterrey"]})
    assert p.ubicaciones == []  # no se guardan: siguen mandando los campos de siempre
    filas = [(f.paises, f.ciudades, f.modalidades) for f in p.filas]
    # Contrato v49: cada ciudad queda en las filas de su país (Monterrey es de México, no de Colombia).
    assert filas == [(["MX"], ["Monterrey"], ["remoto", "presencial"]), (["CO"], [], ["presencial"]),
                     (["US"], [], ["remoto"])]
    assert _ok(_v("remoto", ["MX"]), p) and _ok(_v("remoto", mundo=["US"]), p)
    assert _ok(_v("presencial", ["MX"], ubicacion="Monterrey, México"), p)
    assert not _ok(_v("presencial", ["MX"], ubicacion="Guadalajara, Jalisco, México"), p)


def test_filas_de_danna_presencial_en_chicago_y_remoto_desde_colombia():
    p = Perfil.model_validate({**BASE, "ubicaciones": [
        {"paises": ["CO"], "modalidades": ["remoto"]},
        {"paises": ["US"], "ciudades": ["Chicago"], "modalidades": ["hibrido", "presencial"]}]})
    assert (p.vive_en, p.modalidades, p.ciudades) == ("CO", ["remoto", "hibrido", "presencial"], ["Chicago"])
    assert (p.paises_presenciales_extra, p.puede_trabajar_en) == (["US"], [])
    assert _ok(_v("hibrido", mundo=["US"], ubicacion="Chicago, IL"), p)
    assert _ok(_v("remoto", ["CO"]), p)
    nueva_york = evaluar(_v("presencial", mundo=["US"], ubicacion="New York, NY"), p, hoy())
    assert not nueva_york["compatible"]
    assert nueva_york["motivos"] == ["modalidad diferente", "oficina en otro país"]  # los de donde vive
    # Una remota solo para EE. UU. no le sirve: en EE. UU. solo acepta híbrido o presencial…
    assert not _ok(_v("remoto", mundo=["US"]), p)
    # …salvo que una fila lo diga (antes «puede trabajar legalmente en»).
    p2 = Perfil.model_validate({**BASE, "ubicaciones": [*p.model_dump()["ubicaciones"],
                                                       {"paises": ["US"], "modalidades": ["remoto"]}]})
    assert _ok(_v("remoto", mundo=["US"]), p2) and p2.puede_trabajar_en == ["US"]


def test_regiones_se_convierten_en_paises_y_cada_fila_necesita_lugar():
    p = Perfil.model_validate({**BASE, "ubicaciones": [{"paises": ["CO"]}, {"paises": ["LATAM"], "modalidades": ["remoto"]}]})
    assert {"MX", "AR", "CL"} <= set(p.ubicaciones[1].paises)
    with pytest.raises(ValidationError) as e:
        Perfil.model_validate({**BASE, "ubicaciones": [{"paises": [], "ciudades": []}]})
    assert "al menos un país o una ciudad" in explicar(e.value)
    with pytest.raises(ValidationError) as e:
        Perfil.model_validate({**BASE, "ubicaciones": [{"paises": ["XX"]}]})
    assert "Elige países de la lista" in explicar(e.value)
    # Solo con ciudad: la ciudad implica el país (contrato v24).
    solo = Perfil.model_validate({**BASE, "vive_en": "ES", "ubicaciones": [{"ciudades": ["Madrid"],
                                                                            "modalidades": ["presencial"]}]})
    assert solo.vive_en == "ES" and _ok(_v("presencial", ["ES"], ubicacion="Madrid, España"), solo)


def test_ampliacion_remota_cercana_abre_la_remota_desde_donde_vive():
    p = Perfil.model_validate({**BASE, "ubicaciones": [{"paises": ["CO"], "modalidades": ["presencial"]},
                                                       {"paises": ["ES"], "modalidades": ["presencial"]}]})
    assert not _ok(_v("remoto", ["CO"]), p)
    r = relajado(p, "remota_cercana")
    assert r.filas[0].modalidades == ["presencial", "remoto"] and r.filas[1].modalidades == ["presencial"]
    assert _ok(_v("remoto", ["CO"]), r) and not _ok(_v("remoto", ["ES"]), r)


def test_el_panel_recibe_las_filas_de_los_perfiles_anteriores():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    perfiles = api.get("/api/config").json()["borrador"]["perfiles"]
    demo = {p["id"]: p for p in configuracion_demo()["perfiles"]}
    for p in perfiles:
        assert p["ubicaciones"][0]["paises"] == [demo[p["id"]]["vive_en"]]
