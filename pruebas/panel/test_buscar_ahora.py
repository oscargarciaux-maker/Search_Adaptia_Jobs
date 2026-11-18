"""18 nov: «Buscar ahora» en el Resumen lanza bodega.yml desde el servidor del panel, con su propia llave de GitHub
(panel/acciones.py). La llave nunca sale del servidor; sin ella el botón no aparece."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from panel import acciones
from panel.api import crear_app
from panel.repositorio import ErrorRepositorio, RepositorioDemo

H = {"origin": "http://testserver"}
TOKEN = "github_pat_de_prueba_no_real"


class Respuesta:
    def __init__(self, estado=200, datos=None):
        self.status_code, self._datos = estado, datos or {}

    def json(self):
        return self._datos


class SesionFalsa:
    """Imita a la API de GitHub y guarda lo que se le pidió."""
    def __init__(self, corridas=(), estado_post=204, estado_get=200):
        self.corridas, self.estado_post, self.estado_get = list(corridas), estado_post, estado_get
        self.pedidos = []

    def request(self, metodo, url, headers=None, timeout=None, **kw):
        self.pedidos.append((metodo, url, headers, kw))
        if metodo == "POST":
            return Respuesta(self.estado_post)
        if self.estado_get != 200:
            return Respuesta(self.estado_get)
        if url.endswith("/actions/runs"):
            return Respuesta(datos={"workflow_runs": self.corridas})
        return Respuesta(datos={"default_branch": "main"})


def _c(flujo="bodega.yml", status="completed", rama="main", **kw):
    return {"path": ".github/workflows/" + flujo, "status": status, "head_branch": rama, "created_at": _ahora(), **kw}


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh(**kw):
    sesion = SesionFalsa(**kw)
    return acciones.AccionesGitHub(TOKEN, "dueno/repo", sesion=sesion), sesion


def test_lanza_la_busqueda_diaria_de_la_rama_principal():
    gh, sesion = _gh()
    assert gh.lanzar() == {"lanzada": True}
    metodo, url, cabeceras, kw = sesion.pedidos[-1]
    assert metodo == "POST" and url.endswith("/repos/dueno/repo/actions/workflows/bodega.yml/dispatches")
    assert kw["json"] == {"ref": "main", "inputs": {"modo": "diario", "prueba": "false"}}
    assert cabeceras["Authorization"] == "Bearer " + TOKEN


def test_no_lanza_si_ya_hay_una_en_cola_o_corriendo():
    gh, sesion = _gh(corridas=[_c(status="in_progress")])
    with pytest.raises(ErrorRepositorio) as e:
        gh.lanzar()
    assert e.value.estado == 409 and not any(p[0] == "POST" for p in sesion.pedidos)


def test_no_lanza_dos_veces_seguidas():
    gh, sesion = _gh()
    gh.lanzar()
    with pytest.raises(ErrorRepositorio):
        gh.lanzar()
    assert sum(p[0] == "POST" for p in sesion.pedidos) == 1


def test_una_corrida_de_otra_rama_no_cuenta():
    gh, _ = _gh(corridas=[_c(status="completed", rama="prueba")])
    assert gh.estado()["en_curso"] is None


def test_estado_dice_en_cola_corriendo_y_la_pedida_hoy():
    r = acciones.resumir([_c(status="queued", event="workflow_dispatch")], "main")
    assert r["en_curso"]["estado"] == "en_cola" and r["ultima_pedida"]["estado"] == "en_cola"
    r = acciones.resumir([_c(conclusion="cancelled", event="workflow_dispatch")], "main")
    assert r["en_curso"] is None and r["ultima_pedida"]["estado"] == "cancelled"  # el panel avisa que se canceló
    r = acciones.resumir([_c(event="workflow_dispatch", conclusion="success", created_at="2020-01-01T12:00:00Z")],
                         "main")
    assert r["ultima_pedida"] is None  # la de otro día no es de hoy


@pytest.mark.parametrize("corrida,bloquea", [
    (_c("profunda.yml", "in_progress"), True),     # larga: lanzar ahora haría esperar y la captura la cancelaría
    (_c("preparar.yml", "queued"), True),          # esperando turno: lanzar la cancelaría
    (_c("incremental.yml", "queued"), True),
    (_c("incremental.yml", "in_progress"), False), # dura minutos: se espera detrás sin riesgo
    (_c("bodega.yml", "in_progress", rama="otra"), True),  # ocupa el mismo grupo aunque sea de otra rama
    (_c("pruebas.yml", "in_progress"), False),     # fuera del grupo
])
def test_no_lanza_si_otra_tarea_del_grupo_ocupa_el_turno(corrida, bloquea):
    gh, sesion = _gh(corridas=[corrida])
    if bloquea:
        with pytest.raises(ErrorRepositorio) as e:
            gh.lanzar()
        assert e.value.estado == 409 and "Espera" in e.value.mensaje
    else:
        assert gh.lanzar() == {"lanzada": True}


def test_el_grupo_coincide_con_los_flujos():
    import yaml
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2] / ".github/workflows"
    grupo = {f.name for f in raiz.glob("*.yml")
             if ((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("concurrency") or {}).get("group") == "publicar"}
    assert grupo == acciones.GRUPO_PUBLICAR and set(acciones.NOMBRES) == grupo


@pytest.mark.parametrize("codigo", [401, 403, 404, 500])
def test_un_error_de_github_se_explica_sin_mostrar_la_llave(codigo):
    gh, _ = _gh(estado_get=codigo)
    with pytest.raises(ErrorRepositorio) as e:
        gh.estado()
    assert TOKEN not in e.value.mensaje and e.value.estado == 502


def _real(monkeypatch, token, repositorio):
    monkeypatch.setenv("GITHUB_ACCIONES_TOKEN", token)
    monkeypatch.setenv("GITHUB_REPOSITORIO", repositorio)
    return crear_app(demo=False, repositorio=RepositorioDemo(), origen="https://panel.example",
                     operadores=["operador@example.org"])


def test_sin_llave_el_boton_no_aparece(monkeypatch):
    assert _real(monkeypatch, "", "").state.acciones is None


def test_con_llave_mal_escrita_el_panel_arranca_sin_boton(monkeypatch):
    assert _real(monkeypatch, TOKEN, "sin-barra").state.acciones is None
    assert _real(monkeypatch, "con espacio", "dueno/repo").state.acciones is None


def test_espacios_al_pegar_se_quitan(monkeypatch):
    app = _real(monkeypatch, " " + TOKEN + "\n", " dueno/repo ")
    assert app.state.acciones.repositorio == "dueno/repo"


def test_api_lanza_y_bloquea_en_la_demo():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    assert api.get("/api/busqueda").json() == {"disponible": True, "en_curso": None, "ocupado": None,
                                               "ultima_pedida": None}
    assert api.post("/api/busqueda", json={}).status_code == 403  # sin origen: como cualquier escritura
    assert api.post("/api/busqueda", json={}, headers=H).json() == {"lanzada": True}
    assert api.get("/api/busqueda").json()["en_curso"]["estado"] == "corriendo"
    assert api.post("/api/busqueda", json={}, headers=H).status_code == 409


def test_un_error_de_github_deja_el_boton_con_el_motivo_y_sin_la_llave():
    gh, _ = _gh(estado_get=401)
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo(), acciones=gh))
    r = api.get("/api/busqueda")
    assert r.status_code == 200 and r.json()["disponible"] is True and "rechazó la llave" in r.json()["ocupado"]
    assert TOKEN not in r.text
    r = api.post("/api/busqueda", json={}, headers=H)
    assert r.status_code == 502 and TOKEN not in r.text
