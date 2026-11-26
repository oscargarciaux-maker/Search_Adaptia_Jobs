"""Contrato v43 (18 nov): «Confirmar y aplicar» rige desde hoy, una búsqueda no se cae si la configuración cambia
mientras corre (búsqueda #33), Comunidad recibe hasta su meta y una vacante llega a los perfiles de otro cargo que la
acepta."""
from copy import deepcopy
from uuid import uuid4

import pytest

from panel import ejecutor
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy
from pruebas.panel.test_control import trabajo


class Repo:
    """Supabase mínimo: una ejecución del día, el lote en entregas_diarias y las asignaciones guardadas."""
    def __init__(self, lote, version_nueva=None, ejecucion=None):
        self.lote, self.version_nueva, self.ejecucion, self.asignaciones = lote, version_nueva, ejecucion, {}

    def operativa(self, fecha):
        return self.version_nueva

    def pedir(self, metodo, ruta, **op):
        if ruta == "panel_ejecuciones":
            if metodo == "GET":
                return [self.ejecucion] if self.ejecucion else []
            if metodo == "POST":
                self.ejecucion = {"id": str(uuid4()), **op["json"]}
            if metodo == "PATCH":
                self.ejecucion.update(op["json"])
        elif ruta == "entregas_diarias":
            return self.lote
        elif ruta == "panel_asignaciones":
            for f in op["json"]:
                self.asignaciones[(f["perfil_id"], f["vacante_id"])] = f
        return []


def _fila(cargo, n):
    v = trabajo(id=f"v{n:02d}", empresa=f"Empresa {n}", enlace=f"https://jobs.lever.co/e/{n}")
    return {"role_id": "cargo:" + cargo["id"], "vacante_id": v["id"], "match_grade": "exact", "snapshot": v}


@pytest.fixture
def cfg():
    return configuracion_demo()


def test_confirmar_a_mitad_de_la_busqueda_no_la_tumba_y_asigna_con_la_nueva(cfg):
    vieja = {"revision": 1, "configuracion": deepcopy(cfg)}
    nueva_cfg = deepcopy(cfg)
    nueva_cfg["perfiles"][0]["activo"] = False  # en la nueva, el primer perfil ya no recibe
    nueva = {"revision": 2, "configuracion": nueva_cfg}
    repo = Repo([_fila(cfg["cargos"][0], 1)], version_nueva=nueva,
                ejecucion={"id": "e1", "fecha": hoy(), "revision": 1, "resumen": {}})
    ejecutor.registrar(repo, vieja, hoy())  # antes: RuntimeError «conserva otra versión»
    assert repo.ejecucion["revision"] == 2 and repo.ejecucion["resumen"]["revisiones_anteriores"] == [1]
    perfiles = {p for p, _ in repo.asignaciones}
    assert cfg["perfiles"][0]["id"] not in perfiles and perfiles  # se asignó con los filtros nuevos


def test_vacante_de_dos_cargos_llega_a_los_dos_perfiles_una_vez(cfg):
    ux = dict(deepcopy(cfg["cargos"][0]), id=str(uuid4()), nombre="UX Designer", cupo=5)
    perfil = dict(deepcopy(cfg["perfiles"][3]), id=str(uuid4()), cargo_id=ux["id"], meta_diaria=5)
    cfg["cargos"].append(ux)
    cfg["perfiles"].append(perfil)
    cfg["techo_diario"] = 200
    version = {"revision": 1, "configuracion": cfg}
    repo = Repo([_fila(cfg["cargos"][0], 1)])
    ejecutor.registrar(repo, version, hoy())
    del_ux = [f for (p, _), f in repo.asignaciones.items() if p == perfil["id"]]
    assert len(del_ux) == 1 and del_ux[0]["cargo_id"] == ux["id"]
    # El lote no cambia: la vacante sigue contando para su cargo.
    assert repo.ejecucion["resumen"]["vacantes"] == 1


def test_un_cargo_solo_cercano_no_recibe_la_vacante(cfg):
    lejano = dict(deepcopy(cfg["cargos"][1]), id=str(uuid4()), nombre="Contador", cupo=5, terminos_exactos=[],
                  terminos_similares=[], terminos_cercanos=["Product Designer"])
    perfil = dict(deepcopy(cfg["perfiles"][3]), id=str(uuid4()), cargo_id=lejano["id"], meta_diaria=5)
    cfg["cargos"].append(lejano)
    cfg["perfiles"].append(perfil)
    cfg["techo_diario"] = 200
    repo = Repo([_fila(cfg["cargos"][0], 1)])
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    assert not [p for p, _ in repo.asignaciones if p == perfil["id"]]


def test_comunidad_hasta_su_meta_y_primero_lo_que_no_recibieron_los_reales(cfg):
    cfg["clientes"][2]["comunidad"] = True
    comunidad = cfg["perfiles"][2]  # de Product Designer, cliente 03
    comunidad["meta_diaria"] = 2
    cfg["perfiles"][0]["activo"] = cfg["perfiles"][1]["activo"] = False  # Product Designer sin clientes reales
    # v01 y v02 son del lote de Frontend (las recibe su cliente real); v03 a v05, de Product Designer (nadie real).
    lote = [_fila(cfg["cargos"][1], n) for n in (1, 2)] + [_fila(cfg["cargos"][0], n) for n in (3, 4, 5)]
    repo = Repo(lote)
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    de_comunidad = {v for p, v in repo.asignaciones if p == comunidad["id"]}
    assert len(de_comunidad) == 2 and de_comunidad <= {"v03", "v04", "v05"}  # su meta, y no lo de los reales
    assert {v for p, v in repo.asignaciones if p == cfg["perfiles"][3]["id"]} >= {"v01", "v02"}
    assert repo.ejecucion["resumen"]["asignaciones_comunidad"] == 2


def test_iniciar_alinea_con_la_version_mas_nueva_y_no_retrocede(cfg):
    repo = Repo([], ejecucion={"id": "e1", "fecha": hoy(), "revision": 3, "resumen": {}})
    assert ejecutor.iniciar(repo, {"revision": 5, "configuracion": cfg}, hoy())["revision"] == 5
    assert repo.ejecucion["resumen"]["revisiones_anteriores"] == [3]
    assert ejecutor.iniciar(repo, {"revision": 4, "configuracion": cfg}, hoy())["revision"] == 5


def test_pasada_horaria_arma_lote_solo_si_la_configuracion_cambio_despues_del_lote(cfg, monkeypatch, tmp_path):
    vistos = []
    monkeypatch.setattr(ejecutor.bodega, "correr", lambda salida, modo="diario", hoy=None, **k:
                        vistos.append(bool((ejecutor.bodega._config_operativa or {}).get("completar_lote"))) or {})
    monkeypatch.setattr(ejecutor, "registrar", lambda *a, **k: None)
    for lote_de, esperado in ((1, False), (None, False), (0, True)):
        version = {"revision": 1, "configuracion": cfg}
        repo = Repo([], version_nueva=version,
                    ejecucion={"id": "e1", "fecha": hoy(), "revision": 1, "resumen": {"revision_del_lote": lote_de}})
        repo.ejecuciones = lambda: []
        ejecutor.correr(str(tmp_path), modo="incremental", repo=repo)
        assert vistos[-1] is esperado


def test_demo_confirmar_rige_desde_hoy(tmp_path):
    r = RepositorioDemo(tmp_path / "demo.json")
    assert r.publicar(r.config()["revision"])["vigente_desde"] == hoy()
