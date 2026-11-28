"""7.H (decisión de Oscar, 28 nov): la Bodega decide «ya no encaja» con la misma regla que el panel. Antes contaba como
«ya no encaja» una vacante que OTRO cargo reconocía mejor (`entrega.roles_de`), aunque el panel la siguiera
compartiendo porque encaja con el perfil: avisos CORTA falsos. Lo que importa es lo que recibe el cliente."""
from copy import deepcopy
import uuid

import pytest

from buscador import bodega, familias, vacante, validacion
from panel import afinidad, ejecutor, servicio
from panel.repositorio import hoy
from pruebas.panel.test_control import cfg, cfg_un_perfil, trabajo  # noqa: F401 (fixtures)
from pruebas.panel.test_no_encaja import _ConVigente
from pruebas.test_estados_bodega import _reporte


@pytest.fixture
def con_ux(cfg_un_perfil):  # noqa: F811 (la fixture importada de test_control)
    """Product Designer (con «UX Designer» como similar) y un cargo nuevo «UX Designer», que reconoce mejor (exacto) a
    una vacante «UX Designer». Cada cargo con un perfil igual (Colombia, remoto, inglés)."""
    c = deepcopy(cfg_un_perfil)
    pd = c["cargos"][0]
    ux = dict(deepcopy(pd), id=str(uuid.uuid5(uuid.NAMESPACE_URL, "7h-ux")), nombre="UX Designer",
              terminos_exactos=["UX Designer"], terminos_similares=[], terminos_cercanos=[])
    c["cargos"].append(ux)
    perfil_pd = next(p for p in c["perfiles"] if p["cargo_id"] == pd["id"] and p.get("activo", True))
    c["perfiles"].append(dict(deepcopy(perfil_pd), id=str(uuid.uuid5(uuid.NAMESPACE_URL, "7h-perfil")), cargo_id=ux["id"]))
    return c


def _roles(c):
    _, configuracion, _ = ejecutor.preparar({"configuracion": c}, hoy())
    return {r["nombre"]: r for r in configuracion["roles"]}, configuracion["roles"]


def _presencial():
    """El perfil solo acepta remoto: una presencial en Bogotá no le sirve (el panel recalcula idioma y lugar del texto,
    así que el caso se arma con la ubicación, no cambiando un campo a mano)."""
    v = vacante.crear("Product Designer", "Empresa", "https://jobs.lever.co/empresa/dos", "Lever",
                      ubicacion="Bogotá, Colombia", descripcion=trabajo()["_descripcion"], fecha=hoy(), hoy=hoy())
    v["verificacion"] = trabajo()["verificacion"]
    return v


def _clasificada(c, v):
    with ejecutor.activar({"configuracion": c}, hoy()):
        v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
    return v


def test_otro_cargo_la_reconoce_mejor_pero_encaja_con_el_perfil_no_cuenta(con_ux):
    por_nombre, roles = _roles(con_ux)
    v = _clasificada(con_ux, trabajo(titulo="UX Designer"))
    pd, ux = por_nombre["Product Designer"], por_nombre["UX Designer"]
    assert not bodega._empata(v, pd, roles)  # la regla vieja: «UX Designer» la reconoce mejor → falso «ya no encaja»
    assert bodega.afinidad_vigente(v, v, pd, roles, {v["id"]: v})  # 7.H: encaja con el perfil de Product Designer
    assert bodega.afinidad_vigente(v, v, ux, roles, {v["id"]: v})
    entrada = {"id": v["id"], "afinidad_vigente": bodega.afinidad_vigente(v, v, pd, roles, {v["id"]: v}),
               "catalog_status": "active", "verificacion": {"estado": "verificada"}}
    reporte = _reporte(seleccion_actual={"roles": {pd["id"]: {"nombre": pd["nombre"], "vacantes": [entrada]}}})
    assert validacion.estado(reporte) == validacion.COMPLETA and not validacion.cortos(reporte)  # sin aviso


def test_la_que_de_verdad_ya_no_encaja_con_el_perfil_sigue_dando_corta(con_ux):
    por_nombre, roles = _roles(con_ux)
    pd = por_nombre["Product Designer"]
    v = _clasificada(con_ux, _presencial())  # el perfil solo acepta remoto
    assert not bodega.afinidad_vigente(v, v, pd, roles, {v["id"]: v})
    v2 = _clasificada(con_ux, trabajo(titulo="Frontend Engineer"))  # ni el perfil ni el título son del cargo
    assert not bodega.afinidad_vigente(v2, v2, pd, roles, {v2["id"]: v2})
    entrada = {"id": v["id"], "afinidad_vigente": False, "catalog_status": "active",
               "verificacion": {"estado": "verificada"}, "motivo_no_encaja": bodega.motivo_no_encaja(v, pd, roles)}
    reporte = _reporte(seleccion_actual={"roles": {pd["id"]: {"nombre": pd["nombre"], "vacantes": [entrada]}}})
    assert validacion.estado(reporte) == validacion.CORTA
    assert entrada["motivo_no_encaja"] == validacion.MOTIVO_CONFIGURACION  # la copia tampoco encaja


def test_se_conservan_inventario_y_ampliacion(con_ux):
    por_nombre, roles = _roles(con_ux)
    pd = por_nombre["Product Designer"]
    v = _clasificada(con_ux, _presencial())
    assert bodega.afinidad_vigente(dict(v, _ampliacion="remota_cercana"), v, pd, roles, {v["id"]: v})  # va marcada
    assert not bodega.afinidad_vigente(dict(v, _ampliacion="remota_cercana"), v, pd, roles, {})  # salió del inventario


def test_el_motivo_vacante_usa_la_misma_regla(con_ux):
    """La copia de la mañana encaja con el perfil de ahora aunque otro cargo la reconozca mejor: cambió la vacante."""
    por_nombre, roles = _roles(con_ux)
    original = _clasificada(con_ux, trabajo(titulo="UX Designer"))
    assert bodega.motivo_no_encaja(original, por_nombre["Product Designer"], roles) == validacion.MOTIVO_VACANTE


@pytest.mark.parametrize("cambios, encaja", [
    ({"titulo": "UX Designer"}, True),       # otro cargo la reconoce mejor: encaja igual
    ({"titulo": "Product Designer"}, True),
    (None, False),                            # el perfil no la acepta (presencial)
    ({"titulo": "Frontend Engineer"}, False),  # el título no es del cargo
])
def test_bodega_y_panel_dan_el_mismo_resultado(con_ux, cambios, encaja):
    por_nombre, roles = _roles(con_ux)
    pd = por_nombre["Product Designer"]
    v = _clasificada(con_ux, trabajo(**cambios) if cambios else _presencial())
    assert bodega.afinidad_vigente(v, v, pd, roles, {v["id"]: v}) is encaja
    # El panel, con la asignación de esa vacante al perfil de Product Designer.
    repo = _ConVigente(pd["id"], v)
    perfil = pd["_perfiles"][0]
    repo.asignaciones.append({"ejecucion_id": "e", "cliente_id": perfil["cliente_id"], "perfil_id": perfil["id"],
                              "cargo_id": pd["id"].split(":", 1)[1], "vacante_id": v["id"], "match_grade": "strong",
                              "explicacion": [], "filtros": perfil, "cargo_configuracion": pd["_cargo"]})
    repo.vigente = deepcopy(con_ux)
    ficha = servicio.resultados(repo)["vacantes"][0]
    assert (ficha["estado"] == "lista") is encaja
    assert afinidad.encaja_asignada(v, perfil, pd["_cargo"], hoy())["compatible"] is encaja
