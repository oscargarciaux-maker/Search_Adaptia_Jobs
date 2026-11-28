"""P-12.10 («Vacantes» rápida, mismo resultado): memoria acotada de las etiquetas y las funciones, POST de solo lectura
que no vacían las copias, decisiones que renuevan solo a sus clientes y mensajes rehechos una vez tras una tanda."""
from copy import deepcopy
import json
import threading
import time

from fastapi.testclient import TestClient
import pytest

from buscador import normalizar, vacante
from panel import borradores, contenido, servicio
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, configuracion_demo

H = {"origin": "http://testserver"}


class Contado(RepositorioDemo):
    """La demostración, contando lecturas de resultados y de la bandeja."""

    def __init__(self, extra=0):
        super().__init__()
        self.lecturas = {}
        if extra:  # más pendientes, copias de las de siempre con otro id
            base = [r for r in self._revisiones() if r["vacante_id"] in ("rev-demo-0", "rev-demo-1")]
            for n in range(extra):
                r = deepcopy(base[n % len(base)])
                r["vacante_id"] = f"{r['vacante_id']}-{n}"
                if r.get("catalogo_vacantes"):
                    r["catalogo_vacantes"]["id"] = r["vacante_id"]
                self.estado["revisiones"].append(r)

    def _contar(self, nombre):
        self.lecturas[nombre] = self.lecturas.get(nombre, 0) + 1

    def resultados(self, cliente_id, fecha=None):
        self._contar("resultados:" + (cliente_id or ""))
        return super().resultados(cliente_id, fecha)

    def revisiones(self, estado=None, vacante_id=None, ligera=False, sin_descripcion=False):
        if not vacante_id:
            self._contar("revisiones")
        return super().revisiones(estado, vacante_id, ligera, sin_descripcion)


def _huella(r):
    return json.dumps(r["vacantes"], sort_keys=True, ensure_ascii=False, default=str)


def _sin_memoria(monkeypatch):
    monkeypatch.setattr(servicio, "_reetiquetar_publicada", lambda b: vacante.reetiquetar(b, publicada=True))
    monkeypatch.setattr(servicio, "_avisos_de_funciones",
                        lambda c, t, d, cargo, clave: c.avisos(c.evidencia(t, d, cargo)))


def test_la_memoria_da_exactamente_lo_mismo_que_calcular(monkeypatch):
    repo = RepositorioDemo()
    clientes = [c["id"] for c in configuracion_demo()["clientes"]]
    servicio._REETIQUETADAS.vaciar()
    servicio._EVIDENCIAS.vaciar()
    con = [_huella(servicio.resultados(repo, c)) for c in clientes]
    otra_vez = [_huella(servicio.resultados(repo, c)) for c in clientes]  # ahora desde la memoria
    assert len(servicio._REETIQUETADAS) > 0 and len(servicio._EVIDENCIAS) > 0
    with monkeypatch.context() as m:
        _sin_memoria(m)
        sin = [_huella(servicio._calcular_resultados(repo, c, None)) for c in clientes]
    assert con == sin == otra_vez


def test_reetiquetar_desde_la_memoria_es_igual_y_no_comparte_nada():
    servicio._REETIQUETADAS.vaciar()
    desc = "We need 3+ years of experience. Advanced English required. Salary USD 2,000 - 3,000. " * 5
    base = {"titulo": "Product Designer", "_descripcion": desc, "empresa": "X", "idioma": "pt", "familias": []}
    esperado = vacante.reetiquetar(deepcopy(base), publicada=True)
    primera = servicio._reetiquetar_publicada(deepcopy(base))
    primera["familias"].append({"familia": "cambiada"})  # quien la usa puede cambiarla sin tocar la memoria
    segunda = servicio._reetiquetar_publicada(deepcopy(base))
    assert segunda == esperado and list(segunda) == list(esperado)
    sin_texto = {"titulo": "Product Designer", "_descripcion": "", "ingles": "B2", "anos_min": 4}
    assert servicio._reetiquetar_publicada(dict(sin_texto)) == vacante.reetiquetar(dict(sin_texto), publicada=True)
    with pytest.raises(KeyError):  # sin título, el mismo error de siempre
        servicio._reetiquetar_publicada({"_descripcion": desc})


def test_las_memorias_tienen_tope(monkeypatch):
    memoria = servicio._Memoria(3)
    for n in range(10):
        assert memoria.obtener(n, lambda n=n: n * 2) == n * 2
    assert len(memoria) == 3
    assert memoria.obtener(9, lambda: "no se recalcula") == 18


def test_avisos_de_funciones_recordados_igual_que_calculados():
    servicio._EVIDENCIAS.vaciar()
    cargo_cfg = configuracion_demo()["cargos"][0]
    cargo = contenido.cargo_operativo(cargo_cfg)
    clave = json.dumps(cargo_cfg, sort_keys=True, ensure_ascii=False, default=str)
    for desc in ("Figma, wireframes y prototipos con el equipo de producto. " * 6, "corta", None):
        esperado = contenido.avisos(contenido.evidencia("Product Designer", desc, cargo))
        assert servicio._avisos_de_funciones(contenido, "Product Designer", desc, cargo, clave) == esperado
        assert servicio._avisos_de_funciones(contenido, "Product Designer", desc, cargo, clave) == esperado


def test_memoria_de_normalizar_con_bloques_en_varios_hilos():
    normalizar.vaciar_cache()
    dentro, salir = threading.Event(), threading.Event()

    def otro():
        with normalizar.con_memoria():
            dentro.set()
            salir.wait(5)
    hilo = threading.Thread(target=otro)
    hilo.start()
    dentro.wait(5)
    with normalizar.con_memoria():
        normalizar.texto("Diseñadora UX")
    assert normalizar._memoria_activa is True  # el otro hilo sigue dentro: no se apaga ni se vacía
    assert normalizar._texto.cache_info().currsize == 1
    salir.set()
    hilo.join(5)
    assert normalizar._memoria_activa is False and normalizar._texto.cache_info().currsize == 0


def _cuerpos():
    cfg = configuracion_demo()
    return {"/api/vista-previa": {"configuracion": cfg},
            "/api/estimacion-en-vivo": {"configuracion": cfg, "perfil_id": cfg["perfiles"][0]["id"]},
            "/api/cargos/expandir": {"cargo": "Product Designer", "rapido": True},
            "/api/cargos/funciones": {"nombre": "Product Designer"},
            "/api/clientes/importar/previa": {"contenido": "nombre\nCliente nuevo\n"}}


def test_los_post_de_solo_lectura_no_vacian_las_copias():
    repo = Contado()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    cliente = configuracion_demo()["clientes"][0]["id"]
    api.get(f"/api/resultados?cliente_id={cliente}")
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    antes = dict(repo.lecturas)
    for ruta, cuerpo in _cuerpos().items():
        assert api.post(ruta, json=cuerpo, headers=H).status_code < 500, ruta
        api.get(f"/api/resultados?cliente_id={cliente}")
        api.get("/api/revisiones?pagina=1&por_pagina=25")
        assert repo.lecturas == antes, ruta  # ni los resultados ni la bandeja se volvieron a leer
    api.put("/api/ajustes/operador", json={"telefono": "+573000000000"}, headers=H)  # solo renueva Mensajes
    api.get(f"/api/resultados?cliente_id={cliente}")
    assert repo.lecturas == antes
    api.post("/api/revisiones/cargar", headers=H)  # una escritura de verdad sí las renueva
    api.get(f"/api/resultados?cliente_id={cliente}")
    assert repo.lecturas[f"resultados:{cliente}"] == antes[f"resultados:{cliente}"] + 1


def test_la_copia_de_pendientes_dura_cinco_minutos(monkeypatch):
    from panel import api as modulo
    assert modulo.VIGENCIA_PENDIENTES == 300
    repo = Contado()
    ahora = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: ahora[0])
    api = TestClient(crear_app(demo=True, repositorio=repo))
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    ahora[0] += 240  # pasada la copia de 20 s de la página, pero dentro de los 5 min de las pendientes
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    assert repo.lecturas["revisiones"] == 1
    ahora[0] += 61
    api.get("/api/revisiones?pagina=1&por_pagina=25")
    assert repo.lecturas["revisiones"] == 2


def _sin_esperar(app):
    """Reloj falso para los mensajes: el hilo espera hasta que la prueba lo suelta."""
    ahora, soltar = [0.0], threading.Event()

    def dormir(_):
        soltar.wait(5)
        ahora[0] += 10_000
    app.state.reloj, app.state.dormir = (lambda: ahora[0]), dormir
    return soltar


def test_sirve_renueva_solo_las_copias_de_sus_clientes(monkeypatch):
    monkeypatch.setattr(borradores, "generar", lambda *a, **k: {})
    repo = Contado()
    app = crear_app(demo=True, repositorio=repo)
    soltar = _sin_esperar(app)
    api = TestClient(app)
    destino = configuracion_demo()["perfiles"][4]["cliente_id"]  # el único cliente de rev-demo-0
    otro = next(c["id"] for c in configuracion_demo()["clientes"] if c["id"] != destino)
    for c in (destino, otro):
        api.get(f"/api/resultados?cliente_id={c}")
    r = api.post("/api/revisiones/rev-demo-0", json={"decision": "sirve", "paises": ["CO"]}, headers=H)
    soltar.set()
    assert r.status_code == 200 and r.json()["asignadas"] >= 1
    for c in (destino, otro):
        api.get(f"/api/resultados?cliente_id={c}")
    assert repo.lecturas[f"resultados:{destino}"] == 2  # recibió la asignación: se recalcula
    assert repo.lecturas[f"resultados:{otro}"] == 1     # no le tocó: sale de la copia


def test_cinco_sirve_seguidos_rehacen_los_mensajes_una_vez_y_solo_de_sus_clientes(monkeypatch):
    llamadas = []
    repo = Contado(extra=4)
    app = crear_app(demo=True, repositorio=repo)

    def generar(r, fecha=None, dias_atras=3, resultados=None, clientes=None, hilos=4):
        # Después del sello: los resultados que lee ya incluyen la decisión (no salen de una copia de antes).
        antes = repo.lecturas.get("resultados:" + next(iter(clientes)), 0)
        resultados(next(iter(clientes)), None)
        llamadas.append({"clientes": set(clientes), "hilos": hilos,
                         "recalculo": repo.lecturas["resultados:" + next(iter(clientes))] == antes + 1})
        return {}
    monkeypatch.setattr(borradores, "generar", generar)
    soltar = _sin_esperar(app)
    api = TestClient(app)
    ids = ["rev-demo-0", "rev-demo-1", "rev-demo-0-0", "rev-demo-1-1", "rev-demo-0-2"]
    perfiles = configuracion_demo()["perfiles"]
    for c in (perfiles[4]["cliente_id"], perfiles[1]["cliente_id"]):  # los de rev-demo-0 y rev-demo-1
        api.get(f"/api/resultados?cliente_id={c}")
    pais = {"rev-demo-0": ["CO"], "rev-demo-1": ["ES"]}
    nuevos = set()
    for vid in ids:
        r = api.post(f"/api/revisiones/{vid}", json={"decision": "sirve", "paises": pais[vid[:10]]}, headers=H)
        assert r.status_code == 200, r.text
        if r.json()["asignadas"]:
            nuevos |= {p["cliente_id"] for p in repo.estado["asignaciones_extra"] if p["vacante_id"] == vid}
    assert llamadas == []  # mientras siguen llegando decisiones, se espera
    soltar.set()
    for _ in range(100):
        if llamadas:
            break
        time.sleep(0.02)
    time.sleep(0.2)  # por si quedara otra vuelta pendiente
    assert len(llamadas) == 1
    assert llamadas[0]["clientes"] == nuevos and llamadas[0]["hilos"] == 1 and llamadas[0]["recalculo"]


def test_generar_solo_para_los_clientes_pedidos():
    cfg = configuracion_demo()
    ids = [c["id"] for c in cfg["clientes"]]

    class Repo(RepositorioDemo):
        def clientes_de(self, fecha=None):
            return cfg["clientes"]

        def contactos(self):
            return [{"cliente_id": i, "telefono": "+5730000000" + str(n).zfill(2), "consentimiento": True,
                     "nombre_saludo": ""} for n, i in enumerate(ids)]
    pedidos = []

    def resultados(cliente_id, f):
        pedidos.append(cliente_id)
        return {"vacantes": []}
    borradores.generar(Repo(), resultados=resultados, clientes=[ids[1], ids[3]], hilos=1)
    assert set(pedidos) == {ids[1], ids[3]}
