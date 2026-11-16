"""Contrato v31: mensajes de hasta 10 con máximo 2 por empresa, «Tengo más…», enlace de 24 h y «a mi WhatsApp»."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from panel import borradores
from panel.afinidad import enlace_utilizable
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, hoy
from pruebas.panel.test_borradores import _v, repo  # noqa: F401 (fixture)


def _empresa(n, empresa):
    return {**_v(n), "empresa": empresa}


def test_maximo_dos_por_empresa_y_tengo_mas(repo):  # noqa: F811
    vacantes = [_empresa(n, "Acme" if n <= 4 else f"Otra {n}") for n in range(1, 16)]
    r = repo({hoy(): vacantes})
    borradores.generar(r)
    b = r.borradores(fecha=hoy())[0]
    assert len(b["vacantes"]) == 10
    assert sum(v.startswith("v0") and int(v[1:]) <= 4 for v in b["vacantes"]) == 2  # solo 2 de Acme
    assert "Tengo 5 vacantes más para ti" in b["texto"]  # 15 listas − 10 elegidas


def test_sin_sobrantes_no_ofrece_mas(repo):  # noqa: F811
    r = repo({hoy(): [_v(n) for n in range(1, 7)]})
    borradores.generar(r)
    assert "Tengo" not in r.borradores(fecha=hoy())[0]["texto"]


def test_enlace_comprobado_hace_menos_de_24_horas_se_comparte():
    def fila(horas):
        url = "https://www.linkedin.com/jobs/view/4100000001"
        cuando = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
        return {"catalogo_vacantes": {"status": "active", "datos": {
            "enlace": url, "verificacion": {"enlaces": [{"url": url, "estado": "verificada", "comprobada_en": cuando}]}}}}
    assert enlace_utilizable(fila(20)) and not enlace_utilizable(fila(25))


def test_mandarme_todos_a_mi_whatsapp_en_partes():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    h = {"origin": "http://testserver"}
    sin_numero = api.get("/api/borradores/para-mi")
    assert sin_numero.status_code == 422 and "Mi número" in sin_numero.json()["detail"]
    assert api.put("/api/ajustes/operador", json={"telefono": "300 1"}, headers=h).status_code == 422
    assert api.put("/api/ajustes/operador", json={"telefono": "+57 311 222 3344"}, headers=h).json() == \
        {"telefono": "+573112223344"}
    assert api.get("/api/ajustes/operador").json()["telefono"] == "+573112223344"
    assert api.post("/api/borradores/generar", headers=h).status_code == 200
    r = api.get("/api/borradores/para-mi").json()
    assert r["clientes"] >= 1 and r["partes"]
    for parte in r["partes"]:
        assert parte["enlace"].startswith("https://wa.me/573112223344?text=")
        assert len(parte["enlace"]) <= borradores.LARGO_ENLACE or parte["clientes"] == 1
        texto = parse_qs(urlparse(parte["enlace"]).query)["text"][0]
        assert texto == parte["texto"] and "https://wa.me/" in texto
    assert sum(p["clientes"] for p in r["partes"]) == r["clientes"]


def test_sesion_se_renueva_sola_con_el_token_de_renovacion():
    from types import SimpleNamespace
    email = "operador" + "@" + "empresa.test"
    llamadas = []

    def post(url, **k):
        llamadas.append((url, k.get("json")))
        if url.endswith("/auth/v1/token") and k["json"]["refresh_token"] == "renovar-bueno":
            return SimpleNamespace(status_code=200, json=lambda: {
                "access_token": "nuevo", "refresh_token": "renovar-2", "expires_in": 3600,
                "user": {"email": email, "email_confirmed_at": "2026-01-01"}})
        return SimpleNamespace(status_code=200 if url.endswith("/logout") else 400, json=lambda: {})

    class Repo(RepositorioDemo):
        url = "https://supabase.example"
        cabeceras = {}
        sesion = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=401, json=lambda: {}), post=post)
    with TestClient(crear_app(repositorio=Repo(), origen="https://panel.example", operadores=[email])) as c:
        c.cookies.set("adaptia_renovar", "renovar-malo")
        assert c.get("/api/config").status_code == 401
        c.cookies.set("adaptia_renovar", "renovar-bueno")
        assert c.get("/api/session").json()["sesion"] is True
        r = c.get("/api/config")
        assert r.status_code == 200
        cookies = r.headers.get_list("set-cookie")
        assert any(x.startswith("adaptia_session=nuevo") and "HttpOnly" in x for x in cookies)
        assert any(x.startswith("adaptia_renovar=renovar-2") and "Path=/api/" in x for x in cookies)
        # Al cerrar sesión se borran las dos cookies y se anula la renovación en Supabase, aunque el acceso ya haya
        # vencido (aquí /auth/v1/user responde 401): primero se renueva y con ese acceso se anula.
        c.cookies.set("adaptia_session", "vencido")
        llamadas.clear()
        salida = c.post("/api/auth/logout", headers={"origin": "https://panel.example"})
        assert sum('adaptia_' in x and 'Max-Age=0' in x for x in salida.headers.get_list("set-cookie")) == 2
        assert [u.rsplit("/", 1)[-1] for u, _ in llamadas] == ["token", "logout"]
        assert salida.json()["anulada"] is True
