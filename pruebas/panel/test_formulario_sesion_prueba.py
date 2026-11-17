"""PR 3 de la sesión de prueba (17 nov): la sesión trae las ciudades principales de cada país (sin variantes repetidas)
y la hora de cada país, para pedir primero el país y decir «2 h menos que donde vive»."""
from fastapi.testclient import TestClient

from panel.api import crear_app
from panel.repositorio import RepositorioDemo


def test_sesion_trae_ciudades_por_pais_y_horas():
    s = TestClient(crear_app(demo=True, repositorio=RepositorioDemo())).get("/api/session").json()
    co = s["ciudades_por_pais"]["CO"]
    assert "Bogota" in co and "Medellin" in co
    assert not any(c.startswith("Bogota ") for c in co)  # «Bogota D C» sobra si ya está «Bogota»
    assert "Chicago" in s["ciudades_por_pais"]["US"]
    assert s["utc_paises"]["CO"] == -5 and s["utc_paises"]["ES"] == 1 and s["utc_paises"]["US"] == -5


def test_yo_en_demostracion():
    r = TestClient(crear_app(demo=True, repositorio=RepositorioDemo())).get("/api/yo").json()
    assert r == {"nombre": "Operador de prueba", "correo": ""}
