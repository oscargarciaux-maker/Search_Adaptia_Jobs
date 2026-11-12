"""Borradores de WhatsApp (contrato v10): humanos, con al menos 5 vacantes listas, sin repetir y sin enviar nada."""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from panel import borradores
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy


def _v(n, cargo="Product Designer", modalidad="remoto"):
    return {"id": f"v{n:02}", "titulo": f"Product Designer {n}", "empresa": f"Empresa {n}", "modalidad": modalidad,
            "enlace": f"https://www.linkedin.com/jobs/view/41000000{n:02}", "estado": "lista", "cargo_nombre": cargo}


def test_texto_humano_con_cargo_y_sin_filtros():
    t = borradores.texto("Ana", [("Product Designer", [_v(1), _v(2, modalidad="hibrido")])], "2026-11-12", "c1")
    assert "Ana" in t and "Product Designer" in t and "1. Product Designer 1 · Empresa 1 (Remoto)" in t
    assert "2. Product Designer 2 · Empresa 2 (Híbrido)" in t and "linkedin.com/jobs/view/4100000002" in t
    for tecnico in ("B2", "años", "inglés", "filtro", "Colombia", "ampliad"):
        assert tecnico not in t
    otro_dia = borradores.texto("Ana", [("Product Designer", [_v(1)])], "2026-11-13", "c1")
    assert otro_dia.split("\n")[0] != t.split("\n")[0] or otro_dia.split("\n\n")[-1] != t.split("\n\n")[-1]


def test_dos_cargos_se_agrupan_en_el_mismo_mensaje():
    t = borradores.texto("Luis", [("QA", [_v(1)]), ("Frontend", [_v(2)])], "2026-11-12")
    assert "QA y Frontend" in t and "*QA*" in t and "*Frontend*" in t


@pytest.mark.parametrize("entrada,esperado", [("+57 300 123 4567", "+573001234567"), ("+52 (55) 1234-5678", "+525512345678")])
def test_telefonos(entrada, esperado):
    assert borradores.normalizar_telefono(entrada) == esperado


@pytest.mark.parametrize("malo", ["3001234567", "+0 300", "", "+57"])
def test_telefonos_invalidos(malo):
    with pytest.raises(ValueError):
        borradores.normalizar_telefono(malo)


def test_enlace_whatsapp_abre_el_chat_con_el_texto_completo():
    texto = "Hola Ana 👋\n\n1. UX · Acme\nhttps://x.example.org/a?b=1&c=2"
    url = borradores.enlace_whatsapp("+573001234567", texto)
    assert url.startswith("https://wa.me/573001234567?text=")
    assert parse_qs(urlparse(url).query)["text"][0] == texto


class Repo(RepositorioDemo):
    """Demostración con resultados por día controlados."""
    def __init__(self, por_dia):
        super().__init__()
        self.por_dia = por_dia

    def resultados(self, cliente_id, fecha=None):
        cfg = configuracion_demo()
        filas = []
        for v in self.por_dia.get(fecha, []):
            filas.append({"vacante_id": v["id"], "cargo_id": cfg["cargos"][0]["id"], "match_grade": "exact",
                          "explicacion": [], "filtros": cfg["perfiles"][0], "cargo_configuracion": cfg["cargos"][0],
                          "catalogo_vacantes": {}, "_ficha": v})
        return {"ejecucion": {"fecha": fecha}, "clientes": cfg["clientes"], "filas": filas}


@pytest.fixture
def repo(monkeypatch):
    from panel import servicio

    def resultados(repo, cliente_id=None, fecha=None):
        r = repo.resultados(cliente_id, fecha)
        return {"ejecucion": r["ejecucion"], "clientes": r["clientes"], "vacantes": [f["_ficha"] for f in r["filas"]]}
    monkeypatch.setattr(servicio, "resultados", resultados)
    return Repo


def test_genera_con_al_menos_cinco_completando_con_dias_anteriores_sin_repetir(repo):
    from datetime import date, timedelta
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    r = repo({hoy(): [_v(1), _v(2), _v(3)], ayer: [_v(3), _v(4), _v(5), _v(6)]})  # v03 repetida entre días
    res = borradores.generar(r)
    assert res["generados"] == 3  # los tres clientes de la demostración con consentimiento
    b = r.borradores(fecha=hoy())[0]
    assert b["vacantes"] == ["v01", "v02", "v03", "v04", "v05", "v06"] and b["estado"] == "pendiente"
    # Mañana no se repiten las ya incluidas.
    manana = (date.fromisoformat(hoy()) + timedelta(days=1)).isoformat()
    r.por_dia[manana] = [_v(1), _v(7)]
    borradores.generar(r, manana)
    assert set(r.borradores(fecha=manana)[0]["vacantes"]) == {"v07"}


def test_no_genera_sin_consentimiento_ni_pisa_lo_abierto_o_editado(repo):
    r = repo({hoy(): [_v(n) for n in range(1, 7)]})
    cfg = configuracion_demo()
    sin_permiso = cfg["clientes"][3]["id"]  # en la demostración solo los tres primeros aceptaron
    borradores.generar(r)
    assert not r.borradores(cliente_id=sin_permiso)
    b = r.borradores(fecha=hoy())[0]
    r.actualizar_borrador(b["id"], {"texto": "Texto mío", "editado": True})
    r.por_dia[hoy()] = [_v(n) for n in range(10, 17)]
    res = borradores.generar(r)
    assert r.borradores(fecha=hoy(), cliente_id=b["cliente_id"])[0]["texto"] == "Texto mío" and res["conservados"] >= 1


def test_api_de_contactos_y_mensajes_en_demostracion():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    h = {"origin": "http://testserver"}
    cliente = configuracion_demo()["clientes"][4]["id"]
    assert api.put(f"/api/contactos/{cliente}", json={"telefono": "300 123", "consentimiento": True}, headers=h).status_code == 422
    ok = api.put(f"/api/contactos/{cliente}", json={"telefono": "+57 300 123 4567", "nombre_saludo": "Ana",
                                                    "consentimiento": True}, headers=h)
    assert ok.json()["telefono"] == "+573001234567"
    assert api.get("/api/contactos").json()[cliente]["nombre_saludo"] == "Ana"
    assert api.post("/api/borradores/generar", headers=h).json()["generados"] >= 1
    lista = api.get("/api/borradores").json()["borradores"]
    b = next(x for x in lista if x["cliente_id"] == cliente)
    assert b["enlace"].startswith("https://wa.me/573001234567?text=") and "Ana" in b["texto"]
    cambiado = api.patch(f"/api/borradores/{b['id']}", json={"texto": "Hola Ana, editado"}, headers=h).json()
    assert cambiado["editado"] and api.patch(f"/api/borradores/{b['id']}", json={"estado": "enviado"}, headers=h).json()["estado"] == "enviado"
