"""18 nov (velocidad): «Por confirmar», los mensajes y «Copiar WhatsApp» tardaban demasiado. Lo que se lee en cada
pantalla tiene una copia corta en memoria, confirmar no rehace los borradores antes de responder y los borradores no
leen las vacantes de un cliente que no usan."""
import time

from fastapi.testclient import TestClient

from panel import borradores, revision
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, configuracion_demo

H = {"origin": "http://testserver"}


class Contado(RepositorioDemo):
    """La demostración, contando cuántas veces se lee cada cosa."""
    def __init__(self):
        super().__init__()
        self.lecturas = {}

    def _contar(self, nombre):
        self.lecturas[nombre] = self.lecturas.get(nombre, 0) + 1

    def revisiones(self, estado=None, vacante_id=None, ligera=False, sin_descripcion=False):
        self._contar("revisiones" + ("-una" if vacante_id else ""))
        return super().revisiones(estado, vacante_id, ligera, sin_descripcion)

    def resultados(self, cliente_id, fecha=None):
        self._contar("resultados")
        return super().resultados(cliente_id, fecha)

    def ejecuciones(self):
        self._contar("ejecuciones")
        return super().ejecuciones()


def test_la_bandeja_se_lee_una_vez_entre_pantallas_y_decidir_no_obliga_a_releerla():
    repo = Contado()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    total = api.get("/api/revisiones?pagina=1&por_pagina=1").json()["en_espera"]
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    cliente = configuracion_demo()["clientes"][0]["id"]
    api.get(f"/api/revisiones?pagina=1&por_pagina=8&cliente_id={cliente}")
    assert repo.lecturas.get("revisiones") == 1  # Resumen, bandeja y detalle del cliente comparten la lectura
    primera = api.get("/api/revisiones?pagina=1&por_pagina=25").json()["pendientes"][0]["vacante_id"]
    r = api.post(f"/api/revisiones/{primera}", json={"decision": "saltar"}, headers=H)
    assert r.status_code == 200 and r.json()["decididas"] == [primera]
    despues = api.get("/api/revisiones?pagina=1&por_pagina=25").json()
    assert despues["en_espera"] == total - 1 and primera not in {p["vacante_id"] for p in despues["pendientes"]}
    assert repo.lecturas.get("revisiones") == 1  # la decisión quitó su fila de la copia sin leer todas otra vez


def test_otra_escritura_si_obliga_a_releer_la_bandeja():
    repo = Contado()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    api.post("/api/revisiones/cargar", headers=H)
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    assert repo.lecturas.get("revisiones") >= 2


def test_confirmar_responde_sin_rehacer_borradores_y_los_rehace_en_segundo_plano(monkeypatch):
    llamadas = []
    monkeypatch.setattr(borradores, "generar", lambda repo, fecha=None, dias_atras=3, resultados=None:
                        llamadas.append(resultados is not None) or {})
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    primera = api.get("/api/revisiones").json()["pendientes"][0]
    r = api.post(f"/api/revisiones/{primera['vacante_id']}", json={"decision": "sirve", "paises": ["CO"]}, headers=H)
    assert r.status_code == 200 and r.json()["asignadas"] >= 1
    for _ in range(50):
        if llamadas:
            break
        time.sleep(0.05)
    assert llamadas == [True]  # una sola vez, en segundo plano y con las copias del servidor


def test_decidir_fuera_del_panel_sigue_rehaciendo_los_borradores(monkeypatch):
    llamadas = []
    monkeypatch.setattr(borradores, "generar", lambda *a, **k: llamadas.append(1) or {})
    r = RepositorioDemo()
    primera = revision.listar(r, "2026-11-18")["pendientes"][0]["vacante_id"]
    con = revision.decidir(r, primera, "sirve", ["CO"])
    assert con["asignadas"] >= 1 and llamadas == [1]
    revision.decidir(r, revision.listar(r, "2026-11-18")["pendientes"][0]["vacante_id"], "sirve", ["CO"],
                     regenerar=False)
    assert llamadas == [1]


def test_whatsapp_usa_la_copia_de_resultados():
    repo = Contado()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    cliente = configuracion_demo()["clientes"][0]["id"]
    api.get(f"/api/resultados?cliente_id={cliente}")
    antes = repo.lecturas["resultados"]
    msg = api.get(f"/api/whatsapp/{cliente}").json()
    assert msg["vacantes"] > 0 and repo.lecturas["resultados"] == antes


def test_borradores_no_leen_vacantes_solo_para_saber_los_clientes():
    class Repo(Contado):
        def clientes_de(self, fecha=None):
            return configuracion_demo()["clientes"]
    repo = Repo()
    vistos = []
    borradores.generar(repo, resultados=lambda cliente_id, f: vistos.append(cliente_id) or {"vacantes": []})
    assert None not in vistos and "" not in vistos and repo.lecturas.get("resultados", 0) == 0


def test_comprobacion_reciente_no_se_repite_al_confirmar():
    from datetime import datetime, timedelta, timezone
    ahora = datetime.now(timezone.utc)
    reciente = {"verificacion": {"estado": "verificada", "enlaces": [
        {"estado": "verificada", "comprobada_en": (ahora - timedelta(hours=2)).isoformat()}]}}
    vieja = {"verificacion": {"estado": "verificada", "enlaces": [
        {"estado": "verificada", "comprobada_en": (ahora - timedelta(hours=30)).isoformat()}]}}
    assert revision._comprobada_hace_poco(reciente)
    assert not revision._comprobada_hace_poco(vieja)
    assert not revision._comprobada_hace_poco({"verificacion": {"estado": "pendiente"}})


def test_tiempo_del_servidor_en_cada_respuesta():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    assert api.get("/api/revisiones").headers["server-timing"].startswith("app;dur=")


def test_borradores_se_guardan_siempre_en_el_orden_de_los_contactos():
    """Se calculan en paralelo, pero el orden guardado no depende de qué cliente termina primero (CI del PR #124: el
    primer mensaje de la lista cambiaba entre corridas)."""
    import random
    cfg = configuracion_demo()
    ids = [c["id"] for c in cfg["clientes"]]

    class Repo(RepositorioDemo):
        def __init__(self):
            super().__init__()
            self.orden = []

        def clientes_de(self, fecha=None):
            return cfg["clientes"]

        def contactos(self):
            return [{"cliente_id": i, "telefono": "+57 300 000 00" + str(n).zfill(2), "consentimiento": True,
                     "nombre_saludo": ""} for n, i in enumerate(ids)]

        def guardar_borrador(self, fila):
            self.orden.append(fila["cliente_id"])
            return super().guardar_borrador(fila)

    def resultados(cliente_id, f):
        time.sleep(random.uniform(0, 0.03))  # cada cliente tarda distinto
        return {"vacantes": [{"id": cliente_id[:6] + str(n), "estado": "lista", "empresa": f"E{n}", "titulo": "UX",
                              "cargo_nombre": "UX", "enlace": "https://example.org/" + str(n)} for n in range(6)]}
    for _ in range(3):
        repo = Repo()
        borradores.generar(repo, resultados=resultados)
        assert repo.orden == ids
