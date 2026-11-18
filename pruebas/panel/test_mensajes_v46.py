"""Contrato v46: «Mandarme todos» en un solo mensaje con enlaces cortos firmados, de qué día es cada vacante del
mensaje, frase sin «hoy» si vienen de días anteriores, y copias de Mensajes que no vacían el resto."""
from datetime import date, timedelta
import re
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from panel import borradores
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, hoy
from pruebas.panel.test_borradores import _v, repo  # noqa: F401 (fixture)

H = {"origin": "http://testserver"}


def _api():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()), follow_redirects=False)
    api.put("/api/ajustes/operador", json={"telefono": "+57 311 222 3344"}, headers=H)
    api.post("/api/borradores/generar", headers=H)
    return api


def _cortos(api):
    texto = api.get("/api/borradores/para-mi").json()["texto"]
    return re.findall(r"http://testserver(/w/\S+)", texto)


def test_enlace_corto_abre_el_chat_del_cliente_con_su_mensaje_actual():
    api = _api()
    corto = _cortos(api)[0]
    b = next(x for x in api.get("/api/borradores").json()["borradores"]
             if corto.endswith(borradores.ficha_corta(x["id"], hoy())))
    api.patch(f"/api/borradores/{b['id']}", json={"texto": "Hola, texto editado"}, headers=H)
    r = api.get(corto)
    assert r.status_code == 302
    destino = r.headers["location"]
    assert destino.startswith("https://wa.me/") and parse_qs(urlparse(destino).query)["text"][0] == "Hola, texto editado"
    assert next(x for x in api.get("/api/borradores").json()["borradores"] if x["id"] == b["id"])["estado"] == "abierto"


def test_enlace_corto_mal_firmado_de_otro_dia_o_enviado_no_sirve():
    api = _api()
    corto = _cortos(api)[0]
    borrador_id = corto.split("/w/")[1].split(".")[0]
    assert api.get(f"/w/{borrador_id}.{'0' * 16}").status_code == 404
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    assert api.get("/w/" + borradores.ficha_corta(borrador_id, ayer)).status_code == 404
    api.patch(f"/api/borradores/{borrador_id}", json={"estado": "enviado"}, headers=H)
    r = api.get(corto)
    assert r.status_code == 404 and "ya no sirve" in r.text
    # La firma nunca lleva la llave.
    assert borradores._llave().hex() not in api.get("/api/borradores/para-mi").text


def test_un_solo_mensaje_aunque_sean_muchos_clientes():
    class Repo(RepositorioDemo):
        def ajuste(self, clave, defecto=None):
            return {"telefono": "+573112223344"} if clave == "operador" else defecto

    contactos = [{"cliente_id": f"c{i}", "telefono": "+57300000000" + str(i % 10), "nombre_saludo": f"C{i}",
                  "consentimiento": True}
                 for i in range(30)]
    filas = [{"id": f"b{i:02d}" + "0" * 30, "cliente_id": f"c{i}", "estado": "pendiente", "vacantes": ["v"] * 10,
              "texto": "x" * 3000} for i in range(30)]
    r = borradores.para_operador(Repo(), "https://panel.example", hoy(), contactos=contactos, borradores=filas,
                                 nombres={})
    assert r["clientes"] == 30 and len(r["texto"]) < 4000 and r["enlace"].count("wa.me") == 1


def test_mensaje_sin_hoy_si_las_vacantes_son_de_dias_anteriores(repo):  # noqa: F811
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    r = repo({ayer: [_v(n) for n in range(1, 7)]})
    borradores.generar(r)
    texto = r.borradores(fecha=hoy())[0]["texto"]
    assert "siguen abiertas" in texto or "todavía abiertas" in texto
    assert "Hoy encontré" not in texto and "que vi hoy" not in texto and "nuevas" not in texto


def test_borradores_dicen_cuantas_son_de_hoy():
    api = _api()
    for b in api.get("/api/borradores").json()["borradores"]:
        assert b["de_hoy"] + b["anteriores"] == len(b["vacantes"])


def test_escribir_un_mensaje_no_vacia_las_demas_copias():
    llamadas = []

    class Repo(RepositorioDemo):
        def ejecuciones(self):
            llamadas.append(1)
            return super().ejecuciones()
    api = TestClient(crear_app(demo=True, repositorio=Repo()))
    api.get("/api/ejecuciones")
    api.post("/api/borradores/generar", headers=H)
    b = api.get("/api/borradores").json()["borradores"][0]
    antes = len(llamadas)
    api.patch(f"/api/borradores/{b['id']}", json={"estado": "abierto"}, headers=H)
    api.get("/api/ejecuciones")
    assert len(llamadas) == antes  # la copia del historial sigue


def test_vista_previa_de_whatsapp_no_marca_abierto_ni_firma_rara_ensucia_el_registro(capsys):
    api = _api()
    corto = _cortos(api)[0]
    borrador_id = corto.split("/w/")[1].split(".")[0]
    r = api.get(corto, headers={"user-agent": "WhatsApp/2.24.1 A"})
    assert r.status_code == 302 and r.headers["cache-control"] == "no-store"
    assert next(x for x in api.get("/api/borradores").json()["borradores"] if x["id"] == borrador_id)["estado"] == "pendiente"
    assert api.get(f"/w/{borrador_id}." + "ñ" * 16).status_code == 404
    assert "api:enlace-corto" not in capsys.readouterr().err


def test_sin_consentimiento_no_va_en_mandarme_todos():
    class Repo(RepositorioDemo):
        def ajuste(self, clave, defecto=None):
            return {"telefono": "+573112223344"} if clave == "operador" else defecto
    b = {"id": "b1" + "0" * 34, "cliente_id": "c1", "estado": "pendiente", "texto": "hola", "vacantes": []}
    sin = [{"cliente_id": "c1", "telefono": "+573000000000", "consentimiento": False}]
    assert borradores.para_operador(Repo(), "https://p.example", hoy(), contactos=sin, borradores=[b],
                                    nombres={})["clientes"] == 0
