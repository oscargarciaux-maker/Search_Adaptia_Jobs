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
        if self.estado_get != 200:
            return Respuesta(self.estado_get)
        if metodo == "POST":
            return Respuesta(self.estado_post)
        if url.endswith("/runs"):
            return Respuesta(datos={"workflow_runs": self.corridas})
        return Respuesta(datos={"default_branch": "main"})


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
    gh, sesion = _gh(corridas=[{"status": "in_progress", "head_branch": "main", "created_at": _ahora()}])
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
    gh, _ = _gh(corridas=[{"status": "queued", "head_branch": "prueba", "created_at": _ahora()}])
    assert gh.estado()["en_curso"] is None


def test_estado_dice_en_cola_corriendo_y_la_de_hoy():
    r = acciones.resumir([{"status": "queued", "head_branch": "main", "created_at": _ahora(),
                           "event": "workflow_dispatch", "html_url": "https://github.com/x"}], "main")
    assert r["en_curso"]["estado"] == "en_cola" and r["en_curso"]["manual"] is True
    assert r["ultima_hoy"]["creada"]
    r = acciones.resumir([{"status": "completed", "conclusion": "success", "head_branch": "main",
                           "created_at": "2020-01-01T12:00:00Z"}], "main")
    assert r["en_curso"] is None and r["ultima_hoy"] is None  # la de otro día no es de hoy


@pytest.mark.parametrize("codigo", [401, 403, 404, 500])
def test_un_error_de_github_se_explica_sin_mostrar_la_llave(codigo):
    gh, _ = _gh(estado_get=codigo)
    with pytest.raises(ErrorRepositorio) as e:
        gh.estado()
    assert TOKEN not in e.value.mensaje and e.value.estado == 502


def test_sin_llave_el_boton_no_aparece(monkeypatch):
    monkeypatch.delenv("GITHUB_ACCIONES_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORIO", raising=False)
    assert acciones.desde_entorno() is None
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo(), acciones=False))
    assert api.get("/api/busqueda").json() == {"disponible": False}
    assert api.post("/api/busqueda", headers=H).status_code == 409


def test_con_llave_mal_escrita_no_se_cae_el_panel(monkeypatch):
    monkeypatch.setenv("GITHUB_ACCIONES_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_REPOSITORIO", "sin-barra")
    with pytest.raises(ValueError):
        acciones.desde_entorno()


def test_api_lanza_y_bloquea_en_la_demo():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    assert api.get("/api/busqueda").json() == {"disponible": True, "en_curso": None, "ultima_hoy": None}
    assert api.post("/api/busqueda", json={}).status_code == 403  # sin origen: como cualquier escritura
    assert api.post("/api/busqueda", json={}, headers=H).json() == {"lanzada": True}
    estado = api.get("/api/busqueda").json()
    assert estado["en_curso"]["estado"] == "corriendo"
    assert api.post("/api/busqueda", json={}, headers=H).status_code == 409
    assert TOKEN not in str(estado)


def test_la_llave_no_llega_al_navegador(monkeypatch):
    gh, _ = _gh(corridas=[{"status": "queued", "head_branch": "main", "created_at": _ahora()}])
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo(), acciones=gh))
    texto = api.get("/api/busqueda").text + api.get("/api/session").text
    assert TOKEN not in texto
