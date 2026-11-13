"""Contrato v16: bandeja «Por confirmar» — cola diaria, decisiones de un clic, reglas sin ubicaciones genéricas."""
from fastapi.testclient import TestClient

from buscador import alertas, catalogo, tiempos, vacante
from panel import revision, servicio
from panel.api import crear_app
from panel.ejecutor import validar_version
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy

TEXTO = ("We are looking for a Product Designer to join our team. We require 2 years of experience. English B2 "
         "required. Preferably based in Colombia or Mexico. We build digital products. ") * 3


def _fila(n, ubicacion, titulo="Product Designer", texto=TEXTO):
    v = vacante.crear(titulo, f"Empresa {n}", f"https://jobs.lever.co/e/{n}", "Lever", ubicacion=ubicacion,
                      descripcion=texto, fecha=hoy(), hoy=hoy(), remoto=True)
    v.update(paises=["AR", "CO", "MX"], confianza_pais="baja", nota_pais="remoto: confirmar región",
             verificacion={"estado": "verificada", "enlaces": [{"url": v["enlace"], "estado": "verificada",
                                                                "comprobada_en": tiempos.ahora()}]})
    f = catalogo.fila(v, hoy() + "T00:00:00Z")
    return {"id": f["id"], "datos": f["datos"], "description_full": f["description_full"]}


class Repo(RepositorioDemo):
    """La demostración con candidatas del catálogo y una bandeja vacía al empezar."""
    def __init__(self, candidatas):
        super().__init__()
        self.estado["revisiones"] = []
        self._candidatas = candidatas

    def candidatas_por_confirmar(self, desde):
        return self._candidatas

    def revisiones(self, estado=None, vacante_id=None):  # añade el catálogo como lo hace Supabase
        filas = super().revisiones(estado, vacante_id)
        por_id = {c["id"]: c for c in self._candidatas}
        return [dict(r, catalogo_vacantes={**por_id.get(r["vacante_id"], {}), "status": "archived",
                                           "reason": "elegibilidad regional por confirmar"}) for r in filas]


def _cfg():
    c = configuracion_demo()
    return validar_version({"revision": 1, "configuracion": c}), c


def test_cola_prioriza_faltantes_respeta_tope_y_filtros():
    cfg, c = _cfg()
    candidatas = [_fila(n, f"Remote Remoto {n}") for n in range(14)]
    ajena = _fila(99, "Remote Remoto x")
    ajena["datos"] = dict(ajena["datos"], titulo="Chef de cocina")  # no es del cargo de nadie
    candidatas.append(ajena)
    r = Repo(candidatas)
    estrictas = {p.id: 5 for p in cfg.perfiles}
    estrictas[cfg.perfiles[0].id] = 1  # el perfil 0 tiene faltantes
    resumen = revision.preparar_cola(r, cfg, hoy(), estrictas)
    pendientes = r.revisiones(estado="pendiente")
    assert resumen["por_confirmar"] == len(pendientes) == 14  # se guardan todas (para el CSV)
    vista = revision.listar(r, hoy())
    assert vista["total"] == revision.TOPE and vista["en_espera"] == 14  # el panel muestra solo las 10 más útiles
    assert resumen["por_confirmar_faltantes"] == 14
    assert all(p["perfiles"] and any(x["faltan"] for x in p["perfiles"]) for p in pendientes)
    assert candidatas[-1]["id"] not in {p["vacante_id"] for p in pendientes}
    assert "Colombia" in pendientes[0]["pista"] and set(pendientes[0]["sugerencia"]) == {"CO", "MX"}


def test_ubicacion_generica_nunca_crea_regla():
    assert revision.es_generica("Remote Remoto") and revision.es_generica("N/A") and revision.es_generica("Remote")
    assert not revision.es_generica("Sant Cugat del Vallès") and not revision.es_generica("Remote - MX")
    cfg, _ = _cfg()
    r = Repo([_fila(1, "Remote Remoto"), _fila(2, "Remote Remoto")])
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    vid = r.revisiones(estado="pendiente")[0]["vacante_id"]
    res = revision.decidir(r, vid, "sirve", ["CO"], aplicar_a_iguales=True)
    assert not res["regla"] and res["iguales"] == 0 and not r.reglas()


def test_aplicar_a_iguales_crea_regla_y_resuelve_las_demas_y_la_regla_actua_sola():
    cfg, c = _cfg()
    r = Repo([_fila(1, "Pueblo Nuevo Ejemplo"), _fila(2, "Pueblo Nuevo Ejemplo"), _fila(3, "Otro Lugar Ejemplo")])
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    pendientes = {p["vacante_id"]: p for p in r.revisiones(estado="pendiente")}
    assert len(pendientes) == 3
    lista = revision.listar(r, hoy())["pendientes"]
    assert next(x for x in lista if x["ubicacion"] == "Pueblo Nuevo Ejemplo")["iguales"] == 1
    primera = next(v for v, p in pendientes.items() if p["ubicacion"] == "pueblo nuevo ejemplo")
    res = revision.decidir(r, primera, "sirve", ["CO"], aplicar_a_iguales=True)
    assert res["regla"] and res["iguales"] == 1 and res["asignadas"] >= 2
    assert r.reglas()[0]["texto"] == "pueblo nuevo ejemplo" and r.reglas()[0]["resultado"] == {"paises": ["CO"]}
    assert len(r.revisiones(estado="pendiente")) == 1
    # Noche siguiente: una vacante nueva con la misma ubicación se decide sola con la regla.
    r._candidatas.append(_fila(4, "Pueblo Nuevo Ejemplo"))
    resumen = revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    nueva = r.revisiones(vacante_id=r._candidatas[-1]["id"])[0]
    assert resumen["resueltas_por_regla"] == 1 and nueva["estado"] == "confirmada" and nueva["paises"] == ["CO"]


def test_confirmada_aparece_lista_para_el_cliente_y_no_se_repite():
    cfg, c = _cfg()
    r = Repo([_fila(1, "Lugar Ejemplo")])
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    vid = r.revisiones(estado="pendiente")[0]["vacante_id"]
    assert revision.decidir(r, vid, "sirve", ["CO"])["asignadas"] >= 1
    cliente = c["perfiles"][0]["cliente_id"]
    ficha = next(v for v in servicio.resultados(r, cliente)["vacantes"] if v["id"] == vid)
    assert ficha["estado"] == "lista"
    for decision, paises in (("sirve", ["CO"]), ("no_sirve", [])):
        try:
            revision.decidir(r, vid, decision, paises)
            raise AssertionError("se decidió dos veces")
        except Exception as e:  # noqa: BLE001
            assert "ya se decidió" in str(e)


def test_validaciones_de_la_decision():
    r = RepositorioDemo()
    for paises in ([], ["US"]):
        try:
            revision.decidir(r, "rev-demo-0", "sirve", paises)
            raise AssertionError("aceptó un país no cubierto")
        except Exception as e:  # noqa: BLE001
            assert "LATAM o España" in str(e)
    assert revision.decidir(r, "rev-demo-1", "saltar")["decision"] == "saltar"
    assert r.revisiones(vacante_id="rev-demo-1")[0]["estado"] == "saltada"


def test_api_de_la_bandeja_en_demostracion():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    h = {"origin": "http://testserver"}
    datos = api.get("/api/revisiones").json()
    assert datos["total"] == 3 and datos["ayudan_faltantes"] == 2
    primera = datos["pendientes"][0]
    assert primera["pista"] and primera["clientes"]
    assert api.post(f"/api/revisiones/{primera['vacante_id']}", json={"decision": "otra"}, headers=h).status_code == 422
    ok = api.post(f"/api/revisiones/{primera['vacante_id']}", json={"decision": "sirve", "paises": ["CO"]}, headers=h)
    assert ok.status_code == 200 and ok.json()["asignadas"] >= 1
    assert api.get("/api/revisiones").json()["total"] == 2
    sin_origen = api.post("/api/revisiones/rev-demo-1", json={"decision": "saltar"})
    assert sin_origen.status_code in (401, 403)


def test_correo_menciona_las_por_confirmar():
    _, _, texto = alertas.contenido("exito", "diario", {"fecha": hoy(), "entrega": {"vacantes": 120, "roles": {}}},
                                    {"resumen": {"por_confirmar": 4, "por_confirmar_faltantes": 2}})
    assert "4 vacante(s) por confirmar" in texto and "2 ayudan" in texto


class RepoCatalogo(Repo):
    """Registra lo que la bandeja cambia en el catálogo al decidir."""
    def __init__(self, candidatas):
        super().__init__(candidatas)
        self.catalogo_cambios, self.archivadas = {}, {}

    def actualizar_catalogo_datos(self, vacante_id, datos):
        self.catalogo_cambios[vacante_id] = datos

    def archivar_catalogo(self, vacante_id, razon):
        self.archivadas[vacante_id] = razon


def test_depuracion_completa_carga_todas_incluso_las_que_no_sirven_a_nadie():
    cfg, _ = _cfg()
    ajena = _fila(99, "Remote Remoto x")
    ajena["datos"] = dict(ajena["datos"], titulo="Chef de cocina")
    r = RepoCatalogo([_fila(n, f"Lugar Ejemplo {n}") for n in range(3)] + [ajena])
    resumen = revision.preparar_cola(r, cfg, hoy(), {p.id: 5 for p in cfg.perfiles}, completa=True)
    pendientes = {p["vacante_id"]: p for p in r.revisiones(estado="pendiente")}
    assert resumen["por_confirmar"] == 4 and ajena["id"] in pendientes
    assert pendientes[ajena["id"]]["motivo"] == revision.DEPURACION and not pendientes[ajena["id"]]["perfiles"]
    # La búsqueda de la noche siguiente no vence las cargadas para depurar.
    r._candidatas = []
    revision.preparar_cola(r, cfg, hoy(), {p.id: 5 for p in cfg.perfiles})
    estados = {p["vacante_id"]: p["estado"] for p in super(Repo, r).revisiones()}
    assert set(estados.values()) == {"pendiente"}  # también las que sirven a un cliente: las cargó la persona
    assert resumen["leidas_del_catalogo"] == 4 and resumen["fuera_por_idioma"] == 0


def test_decidir_actualiza_el_catalogo_al_momento_y_sin_perfiles_no_exige_busqueda():
    cfg, _ = _cfg()
    ajena = _fila(98, "Lugar Raro")
    ajena["datos"] = dict(ajena["datos"], titulo="Chef de cocina")
    otra = _fila(97, "Otro Raro")
    otra["datos"] = dict(otra["datos"], titulo="Chef de cocina")
    r = RepoCatalogo([ajena, otra])
    r.ejecucion = lambda fecha: None  # sin búsqueda del día
    revision.preparar_cola(r, cfg, hoy(), {}, completa=True)
    res = revision.decidir(r, ajena["id"], "sirve", ["EC"])
    assert res["asignadas"] == 0
    assert r.catalogo_cambios[ajena["id"]]["paises"] == ["EC"]
    revision.decidir(r, otra["id"], "no_sirve")
    assert r.archivadas[otra["id"]] == "descartada por el operador"


def test_decisiones_para_busqueda():
    filas = [{"vacante_id": "a", "estado": "confirmada", "motivo": "confirmada por operador", "paises": ["EC"]},
             {"vacante_id": "b", "estado": "descartada", "motivo": "otro país (operador)", "paises": []},
             {"vacante_id": "c", "estado": "descartada", "motivo": "no sirve (operador)", "paises": []},
             {"vacante_id": "d", "estado": "saltada", "motivo": "", "paises": []},
             {"vacante_id": "e", "estado": "vencida", "motivo": "", "paises": []}]
    assert revision.decisiones_para_busqueda(filas) == {
        "a": {"paises": ["EC"]}, "b": {"extranjero": True}, "c": {"descartada": True}}


def test_api_cargar_todas_en_demostracion():
    import time
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    r = api.post("/api/revisiones/cargar", headers={"origin": "http://testserver"})
    assert r.status_code == 200 and r.json()["estado"] in ("en_curso", "listo")  # responde al instante
    for _ in range(100):
        estado = api.get("/api/revisiones/cargar").json()
        if estado["estado"] != "en_curso":
            break
        time.sleep(0.05)
    assert estado["estado"] == "listo" and estado["resultado"]["por_confirmar"] == 3  # la demostración conserva su bandeja
    assert api.post("/api/revisiones/cargar").status_code in (401, 403)


def test_pendiente_que_el_sistema_ya_resolvio_sale_sola_de_la_bandeja():
    cfg, _ = _cfg()
    filas = [_fila(1, "Remote Remoto"), _fila(2, "Remote Remoto")]
    r = Repo(filas)
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles}, completa=True)
    resuelta = filas[0]["id"]
    original = r.revisiones
    r.revisiones = lambda estado=None, vacante_id=None: [
        dict(x, catalogo_vacantes={**x["catalogo_vacantes"], "status": "active", "reason": None})
        if x["vacante_id"] == resuelta else x for x in original(estado, vacante_id)]
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    estados = {x["vacante_id"]: (x["estado"], x["motivo"]) for x in super(Repo, r).revisiones()}
    assert estados[resuelta] == ("vencida", revision.RESUELTA_SOLA)
    assert estados[filas[1]["id"]][0] == "pendiente"


def test_vacante_vieja_sin_ver_o_ya_resuelta_no_se_pregunta():
    from datetime import date, timedelta
    hoy_ = hoy()
    base = {"titulo": "Product Designer", "ubicacion": "Remote Remoto", "modalidad": "remoto",
            "_descripcion": "Preferably based in Colombia or Mexico."}
    assert revision._sin_revisar(dict(base, visto_ultima_vez=hoy_), hoy_) == ""
    viejo = (date.fromisoformat(hoy_) - timedelta(days=10)).isoformat()
    assert revision._sin_revisar(dict(base, visto_ultima_vez=viejo), hoy_) == revision.POSIBLE_CIERRE
    assert revision._sin_revisar(dict(base, ubicacion="Inca"), hoy_) == revision.RESUELTA_SOLA
    assert revision._sin_revisar(dict(base, ubicacion="Harrisburg, PA"), hoy_) == revision.RESUELTA_SOLA


def test_regiones_que_elige_el_operador():
    assert len(revision.expandir(["LATAM"])) == 19 and revision.expandir(["LATAM_ES"])[-1] == "ES"
    sud_centro = revision.expandir(["SUD_CENTRO_MX"])
    assert {"AR", "CR", "MX"} <= set(sud_centro) and "BR" not in sud_centro and "ES" not in sud_centro
    assert set(revision.leer_paises("Sudamérica, Centroamérica o México")) == set(sud_centro)


def test_carga_en_segundo_plano_una_a_la_vez_y_con_avance():
    import threading
    import time
    cfg, _ = _cfg()
    r = RepoCatalogo([_fila(n, f"Lugar Ejemplo {n}") for n in range(45)])
    r.operativa = lambda fecha: {"revision": 1, "configuracion": configuracion_demo()}
    r.ejecucion = lambda fecha: None
    puerta = threading.Event()
    original = r.candidatas_por_confirmar

    def lenta(desde=None):
        puerta.wait(5)
        return original(desde)
    r.candidatas_por_confirmar = lenta
    primero = revision.iniciar_carga(r, hoy())
    segundo = revision.iniciar_carga(r, hoy())  # mientras corre no arranca otro
    assert primero["estado"] == segundo["estado"] == "en_curso"
    puerta.set()
    for _ in range(200):
        if revision.estado_carga()["estado"] != "en_curso":
            break
        time.sleep(0.05)
    final = revision.estado_carga()
    assert final["estado"] == "listo" and final["resultado"]["leidas_del_catalogo"] == 45
    assert final["avance"]["total"] == 45 and final["avance"]["leidas"] == 40  # avisa cada 20


def test_cada_vacante_se_evalua_una_vez_y_las_vencidas_van_en_lote(monkeypatch):
    cfg, _ = _cfg()
    filas = [_fila(n, f"Lugar Ejemplo {n}") for n in range(5)]
    r = Repo(filas)
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles}, completa=True)
    llamadas, lotes = [], []
    original = revision._sin_revisar
    monkeypatch.setattr(revision, "_sin_revisar", lambda d, f: llamadas.append(d.get("ubicacion")) or original(d, f))
    r.vencer_revisiones = lambda ids, motivo="": lotes.append((list(ids), motivo))
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles}, completa=True)
    assert len(llamadas) == len(set(llamadas)) == 5  # candidatas y pendientes guardadas: una sola vez cada una
    assert not lotes  # nada que vencer: ninguna petición


def test_consulta_de_dudosas_sin_espacios_y_conteos(monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import urlencode
    from panel.repositorio import RepositorioSupabase
    monkeypatch.setattr("buscador.supabase.credenciales", lambda: ("https://prueba.supabase.co", "clave-ficticia"))
    vistas = []

    def request(metodo, url, **op):
        vistas.append(op["params"])
        return SimpleNamespace(status_code=200, content=b"[]", json=lambda: [])

    def get(url, **op):
        filtro = op["params"]
        total = {"reason": "7", "datos->>confianza_pais": "9"}.get(next((k for k in filtro if k not in ("select", "limit")), ""), "8306")
        return SimpleNamespace(status_code=206, headers={"Content-Range": "0-0/" + total})
    repo = RepositorioSupabase(SimpleNamespace(request=request, get=get))
    assert list(repo.candidatas_por_confirmar()) == []
    consulta = urlencode(vistas[0])
    assert " " not in vistas[0]["reason"] and "+" not in consulta.split("reason=")[1].split("&")[0]
    assert repo.conteo_dudosas() == {"catalogo": 8306, "por_confirmar": 7, "confianza_baja": 9}
