"""17 nov, búsqueda #29: tras casi una hora de búsqueda, la primera consulta a Supabase se quedó colgada 45 s en una
conexión que la red había cortado sin avisar, y se perdió el registro de asignaciones del día."""
from types import SimpleNamespace

import pytest
import requests

from panel import repositorio
from panel.repositorio import ErrorRepositorio, RepositorioSupabase


class Sesion:
    def __init__(self, fallos=0):
        self.fallos, self.pedidos, self.cerrada = fallos, [], 0

    def request(self, metodo, url, **k):
        self.pedidos.append((metodo, k.get("timeout")))
        if self.fallos:
            self.fallos -= 1
            raise requests.ReadTimeout("conexión cortada")
        return SimpleNamespace(status_code=200, content=b"[]", json=lambda: [{"id": "x"}])

    def close(self):
        self.cerrada += 1


@pytest.fixture
def repo(monkeypatch):
    monkeypatch.setattr("buscador.supabase.credenciales", lambda: ("https://prueba.supabase.co", "clave-ficticia"))
    return lambda sesion: RepositorioSupabase(sesion)


def test_tras_mucho_rato_quieta_se_abre_una_conexion_nueva(repo, monkeypatch):
    sesion = Sesion()
    r = repo(sesion)
    r.pedir("GET", "panel_ejecuciones")
    assert sesion.cerrada == 0
    r._ultimo_uso -= repositorio.INACTIVIDAD_MAXIMA + 1  # como después de la búsqueda
    r.pedir("PATCH", "panel_ejecuciones", json={})
    assert sesion.cerrada == 1
    assert sesion.pedidos[0][1] == (10, 45)  # conectar no espera 45 s


def test_una_lectura_colgada_se_reintenta_una_vez(repo):
    sesion = Sesion(fallos=1)
    assert repo(sesion).pedir("GET", "panel_ejecuciones") == [{"id": "x"}]
    assert len(sesion.pedidos) == 2 and sesion.cerrada == 1


def test_una_escritura_colgada_no_se_repite_sola(repo):
    sesion = Sesion(fallos=1)
    with pytest.raises(ErrorRepositorio):
        repo(sesion).pedir("POST", "panel_asignaciones", json=[])
    assert len(sesion.pedidos) == 1


def test_dos_fallos_seguidos_avisan_como_antes(repo):
    with pytest.raises(ErrorRepositorio):
        repo(Sesion(fallos=2)).pedir("GET", "panel_ejecuciones")
