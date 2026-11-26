"""Contrato v50 §3: InfoJobs (España), sin red y con datos ficticios. La búsqueda trae el aviso completo; su ficha pide
captcha y nunca se abre: lo que la búsqueda mostró hoy cuenta como comprobado 24 h (decisión de Oscar, como Indeed)."""
import json
from datetime import datetime, timezone

from buscador import bodega, cobertura, verificar_enlaces
from buscador.fuentes import indeed, infojobs

TEXTO = ("Buscamos un/a QA Tester para nuestro equipo en Madrid. Diseñarás casos de prueba, ejecutarás pruebas "
         "manuales y automatizadas con Selenium y Postman y reportarás defectos en Jira junto a desarrollo. ") * 2


def _aviso(n, titulo="QA Tester", publicada="2026-11-20T10:00:00Z", modalidad="Híbrido", ciudad="Madrid",
           descripcion=TEXTO):
    return {"code": f"abc{n:03d}", "title": titulo, "description": descripcion, "city": ciudad,
            "link": f"//www.infojobs.net/madrid/qa-tester/of-iabc{n:03d}?applicationOrigin=search-new",
            "teleworking": modalidad, "publishedAt": publicada, "companyName": "Empresa Ficticia, S.L."}


def _pagina(avisos):
    datos = {"offers": avisos, "navigation": {"self": 1, "totalPages": 1}}
    return "<html><script>window.__INITIAL_PROPS__ = JSON.parse(" + json.dumps(json.dumps(datos)) + ");</script></html>"


CAPTCHA = "<html><title>InfoJobs</title><div class='geetest_captcha'></div></html>"


class Respuesta:
    def __init__(self, texto, codigo=200):
        self.text, self.status_code = texto, codigo


class Cliente:
    def __init__(self, paginas=None):
        self.pedidas, self.paginas = [], paginas

    def get(self, url, params=None, **opciones):
        self.pedidas.append((url, dict(params or {}), opciones))
        if self.paginas is None:
            return Respuesta(_pagina([_aviso(1), _aviso(2, "Product Manager", modalidad="Solo teletrabajo")]))
        return self.paginas.pop(0) if self.paginas else Respuesta(CAPTCHA)


MAPA = [{"id": "cargo:qa", "consultas": ["qa", "qa engineer", "tester"], "consultas_es": ["analista qa", "analista de pruebas"],
         "paises_objetivo": ["ES", "CO"], "paises_es": ["ES"]},
        {"id": "cargo:pm", "consultas": ["product manager"], "paises_objetivo": ["MX"]}]


def _buscar(cliente, estado=None, **opciones):
    infojobs.VISTAS.clear()
    cobertura.BUSQUEDAS.clear()
    return infojobs.buscar(cliente, MAPA, {} if estado is None else estado, hoy="2026-11-26",
                           **{"presupuesto": 10, **opciones})


def test_lee_los_avisos_de_la_pagina_de_busqueda():
    cliente = Cliente()
    crudas, stats = _buscar(cliente, presupuesto=1)
    url, params, opciones = cliente.pedidas[0]
    assert url == infojobs.BUSQUEDA and params["sortBy"] == "PUBLICATION_DATE" and opciones == {"reintentar_429": False}
    qa = next(c for c in crudas if c["titulo"] == "QA Tester")
    assert qa == {"titulo": "QA Tester", "empresa": "Empresa Ficticia, S.L.", "ubicacion": "Madrid, España (Híbrido)",
                  "descripcion": TEXTO.strip(), "fecha": "2026-11-20", "remoto": None, "fuente": "InfoJobs",
                  "enlace": "https://www.infojobs.net/madrid/qa-tester/of-iabc001", "enlace_directo": ""}
    remota = next(c for c in crudas if c["titulo"] == "Product Manager")
    assert remota["remoto"] is True and remota["ubicacion"] == "Madrid, España (Remoto)"
    assert stats["busquedas"] == 1 and stats["avisos"] == 2 and not stats["bloqueada"]
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-26", 30, set(), set())
    v = next(x for x in vacantes if x["titulo"] == "QA Tester")
    assert v["paises"] == ["ES"] and v["modalidad"] == "hibrido" and v["idioma"] == "es" and v["fuente"] == "InfoJobs"


def test_solo_busca_para_cargos_con_alguien_en_espana_y_con_sus_nombres_en_espanol():
    cliente = Cliente()
    _, stats = _buscar(cliente)
    nombres = [p["keyword"] for _, p, _ in cliente.pedidas]
    assert "product manager" not in nombres  # ese cargo solo tiene gente en México
    assert set(nombres) == {"analista qa", "analista de pruebas", "qa", "qa engineer", "tester"}
    assert len(nombres) == stats["busquedas"] == 5
    # Cada nombre con su clave: la búsqueda para quien falta (v47) no repite lo que ya se buscó hoy.
    estado = {}
    primera = Cliente()
    _buscar(primera, estado)
    cobertura.configurar_personas([{"familia": "cargo:qa", "perfil": "p", "lugares": ["ES"], "peso": 5, "corto": True,
                                    "idiomas": ["es", "en"]}])
    cobertura.configurar_faltantes(True)
    try:
        segunda = Cliente()
        _buscar(segunda, estado)
    finally:
        cobertura.configurar_faltantes(False)
        cobertura.configurar_personas()
    assert segunda.pedidas == []  # ya se buscaron hoy todos sus nombres


def test_la_segunda_corrida_del_dia_sigue_con_otros_nombres_y_hay_un_tope_diario():
    estado = {}
    primera, segunda, tercera = Cliente(), Cliente(), Cliente()
    _buscar(primera, estado, presupuesto=2)
    _buscar(segunda, estado, presupuesto=2)   # p. ej. la pasada de las 8:30: no repite las dos primeras
    nombres = [p["keyword"] for _, p, _ in primera.pedidas + segunda.pedidas]
    assert len(nombres) == len(set(nombres)) == 4 and estado[infojobs.CONTADOR] == {"fecha": "2026-11-26", "paginas": 4}
    estado[infojobs.CONTADOR]["paginas"] = infojobs.TOPE_DIA   # ya se leyeron las del día entre todas las corridas
    assert _buscar(tercera, estado)[1]["busquedas"] == 0 and tercera.pedidas == []
    # Al día siguiente el contador empieza de nuevo.
    otro_dia = Cliente()
    infojobs.buscar(otro_dia, MAPA, estado, 1, hoy="2026-11-27")
    assert len(otro_dia.pedidas) == 1 and estado[infojobs.CONTADOR] == {"fecha": "2026-11-27", "paginas": 1}


def test_lo_visto_hoy_cuenta_como_comprobado_y_la_ficha_nunca_se_abre():
    crudas, stats = _buscar(Cliente(), presupuesto=1)
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-26", 30, set(), set())
    v = next(x for x in vacantes if x["titulo"] == "QA Tester")
    cache = {}
    assert stats["vistas"] == 2 and verificar_enlaces.incorporar(vacantes, cache, infojobs.VISTAS) == len(vacantes)
    assert cache[v["enlace"]]["estado"] == "verificada"
    assert cache[v["enlace"]]["motivo"] == "vista hoy en la búsqueda de InfoJobs"
    assert verificar_enlaces.anotar(v, cache)["estado"] == "verificada"
    # Su ficha pide captcha: la comprobación directa ni se intenta (como en Indeed).
    assert verificar_enlaces.sin_comprobacion_directa(v["enlace"])
    assert not verificar_enlaces.sin_comprobacion_directa("https://www.infojobs.net.falso.com/x/y/of-i1")

    def prohibido(*a, **k):
        raise AssertionError("no se abre la ficha de InfoJobs")
    otra = dict(v, id="otra", enlace="https://www.infojobs.net/madrid/otra/of-izzz999", _enlaces=[])
    assert verificar_enlaces.auditar([otra], {}, ahora=datetime(2026, 11, 26, tzinfo=timezone.utc),
                                     comprobar_url=prohibido) == 0

    class SinRed:
        def get(self, *a, **k):
            raise AssertionError("no se pide la ficha de InfoJobs")

        def close(self):
            pass
    # Tampoco desde los caminos que llaman a `comprobar` o leen la descripción directamente.
    directo = verificar_enlaces.comprobar(otra["enlace"], "QA Tester", sesion=SinRed())
    assert (directo["estado"], directo["motivo"]) == ("pendiente", "sin comprobación directa")
    from buscador import ficha
    assert ficha.traer_descripcion([otra["enlace"]], "QA Tester", obtener=prohibido) == ""
    # Indeed sigue marcando solo páginas de Indeed, aunque el enlace de la empresa sea de InfoJobs.
    indeed.VISTAS.clear()
    indeed._anotar_vista("https://es.indeed.com/viewjob?jk=1", "https://www.infojobs.net/madrid/x/of-i1")
    assert list(indeed.VISTAS) == ["https://es.indeed.com/viewjob?jk=1"]


def test_un_aviso_viejo_sin_descripcion_o_raro_no_se_marca_como_visto():
    avisos = [_aviso(1, publicada="2026-09-01T10:00:00Z"),                 # más de 30 días: no se guarda
              _aviso(2, descripcion="Texto corto."),                          # se guarda, pero no cuenta como visto
              _aviso(3, publicada="no es una fecha"),                         # sin fecha: tampoco
              _aviso(4, publicada="2026-11-27T02:00:00Z"),                    # fecha futura: queda sin fecha
              {"title": "Sin enlace"}, dict(_aviso(5), link="//www.otro.com/x/y/of-i1"), "x", None,
              _aviso(6)]
    crudas, stats = _buscar(Cliente([Respuesta(_pagina(avisos))]), presupuesto=1)
    assert [c["enlace"][-6:] for c in crudas] == ["abc002", "abc003", "abc004", "abc006"]
    assert [c["fecha"] for c in crudas] == ["2026-11-20", "", "", "2026-11-20"]
    assert list(infojobs.VISTAS) == ["https://www.infojobs.net/madrid/qa-tester/of-iabc006"]


def test_la_ciudad_se_conserva_en_presencial_e_hibrida_y_una_homonima_no_abre_otro_pais_en_remota():
    from buscador import paises
    # «Granada» también es un país del Caribe: en híbrida la ciudad se queda (sin ciudad no le llega a nadie, v49).
    hibrida = infojobs.vacante(_aviso(7, ciudad="Granada"))
    assert hibrida["ubicacion"] == "Granada, España (Híbrido)"
    v = bodega.limpiar([], [hibrida], "2026-11-26", 30, set(), set())[0][0]
    assert v["paises"] == ["ES"] and v["modalidad"] == "hibrido"
    # En una remota la ciudad no hace falta y no debe abrir otro país.
    remota = infojobs.vacante(_aviso(8, ciudad="Granada", modalidad="Solo teletrabajo"))
    assert remota["ubicacion"] == "España (Remoto)"
    for ciudad in ("Granada", "Córdoba", "Guadalajara", "Cartagena", "Valencia", "Mérida", "Madrid"):
        ubicacion = infojobs.vacante(_aviso(9, ciudad=ciudad, modalidad="Solo teletrabajo"))["ubicacion"]
        assert set(paises.alcance("", ubicacion).get("paises_mundo") or []) <= {"ES"}, ubicacion
    assert infojobs.vacante(_aviso(10, ciudad="Madrid", modalidad="Solo teletrabajo"))["ubicacion"] == "Madrid, España (Remoto)"


def test_una_descripcion_con_comillas_y_parentesis_no_se_confunde_con_un_captcha():
    raro = _aviso(11, descripcion=TEXTO + ' Ejemplo de código: console.log("hola"); y alert("fin");')
    crudas, stats = _buscar(Cliente([Respuesta(_pagina([raro]))]), presupuesto=1)
    assert not stats["bloqueada"] and len(crudas) == 1 and 'console.log("hola");' in crudas[0]["descripcion"]
    punto = dict(_aviso(12), link="//www.infojobs.net/madrid/programador-.net_c%23/of-iabc012?x=1")
    assert infojobs.vacante(punto)["enlace"] == "https://www.infojobs.net/madrid/programador-.net_c%23/of-iabc012"


def test_al_primer_captcha_la_fuente_se_detiene_y_no_insiste():
    cliente = Cliente([Respuesta(_pagina([_aviso(1)])), Respuesta(CAPTCHA), Respuesta(_pagina([_aviso(2)]))])
    estado = {}
    crudas, stats = _buscar(cliente, estado)
    assert len(cliente.pedidas) == 2 and stats == {"modo": "pagina", "busquedas": 2, "bloqueada": True, "avisos": 1,
                                                   "vistas": 1, "combinaciones_total": 2}
    assert len(crudas) == 1
    assert sum(n for (fuente, _, _), n in cobertura.BUSQUEDAS.items() if fuente == "infojobs") == 1  # la bloqueada no cuenta
    # Un error del sitio o una página sin sus datos también detienen la fuente; nada se inventa.
    for respuesta in (Respuesta("", 503), Respuesta("<html>otro diseño</html>"), None,
                      Respuesta("<script>window.__INITIAL_PROPS__ = JSON.parse(\"no es json\");</script>")):
        solo = Cliente([respuesta])
        assert _buscar(solo)[1]["bloqueada"] and len(solo.pedidas) == 1


def test_la_fuente_esta_registrada_donde_hace_falta():
    from buscador import contrato, enlaces
    from panel import ejecutor
    assert 0 < bodega.config()["presupuestos"]["infojobs_busquedas"] <= 5  # a la sexta página pide captcha
    assert "InfoJobs" in ejecutor.fuentes_en("ES") and "InfoJobs" not in ejecutor.fuentes_en("CO")
    enlace = "https://www.infojobs.net/madrid/qa-tester/of-iabc001"
    assert enlaces.sirve(enlace) and contrato.portal(enlace) == "InfoJobs"


# ── Modo API (con la clave de la aplicación registrada en InfoJobs) ─────────────────────────────────────────────────
CLAVE = ("id-de-prueba", "secreto-de-prueba")


def _resumen(n, titulo="QA Tester", modalidad="Híbrido"):
    return {"id": f"abc{n:03d}", "title": titulo, "city": "Madrid", "author": {"name": "Empresa Ficticia, S.L."},
            "link": f"https://www.infojobs.net/madrid/qa-tester/of-iabc{n:03d}?applicationOrigin=search-new",
            "teleworking": {"id": 2, "value": modalidad}, "published": "2026-11-25T08:00:00.000Z"}


def _detalle(n, titulo="QA Tester", **campos):
    return {"id": f"abc{n:03d}", "title": titulo, "description": TEXTO, "minRequirements": "Dos años de experiencia.",
            "creationDate": "2026-11-10T09:00:00.000Z", "updateDate": "2026-11-25T08:00:00.000Z", "city": "Madrid",
            "profile": {"name": "Empresa Ficticia, S.L."}, "active": True, "archived": False, "deleted": False,
            "link": f"https://www.infojobs.net/madrid/qa-tester/of-iabc{n:03d}", **campos}


class RespuestaApi:
    def __init__(self, cuerpo, codigo=200):
        self.cuerpo, self.status_code = cuerpo, codigo

    def json(self):
        if self.cuerpo is None:
            raise ValueError("sin JSON")
        return self.cuerpo


class Api:
    def __init__(self, lista, fichas=None, codigo=200):
        self.pedidas, self.lista, self.fichas, self.codigo = [], lista, fichas or {}, codigo

    def get(self, url, params=None, headers=None, **opciones):
        self.pedidas.append((url, dict(params or {}), dict(headers or {})))
        if self.codigo != 200:
            return RespuestaApi({"error": "102"}, self.codigo)
        if url == infojobs.API_BUSQUEDA:
            return RespuestaApi({"offers": self.lista, "totalResults": len(self.lista)})
        return RespuestaApi(self.fichas.get(url.rsplit("/", 1)[1]))


def _api(api, estado=None, **opciones):
    infojobs.VISTAS.clear()
    infojobs.FICHAS.clear()
    cobertura.BUSQUEDAS.clear()
    return infojobs.buscar_api(api, CLAVE, MAPA, {} if estado is None else estado, hoy="2026-11-26",
                               **{"presupuesto": 1, "max_fichas": 10, **opciones})


def test_las_claves_salen_de_los_secretos_y_sin_ellas_no_hay_modo_api(monkeypatch):
    monkeypatch.delenv("INFOJOBS_CLIENT_ID", raising=False)
    monkeypatch.delenv("INFOJOBS_CLIENT_SECRET", raising=False)
    assert infojobs.credenciales() is None
    monkeypatch.setenv("INFOJOBS_CLIENT_ID", CLAVE[0])
    assert infojobs.credenciales() is None  # hacen falta las dos
    monkeypatch.setenv("INFOJOBS_CLIENT_SECRET", " " + CLAVE[1] + " ")
    assert infojobs.credenciales() == CLAVE
    assert infojobs._cabeceras(CLAVE)["Authorization"] == "Basic aWQtZGUtcHJ1ZWJhOnNlY3JldG8tZGUtcHJ1ZWJh"


def test_la_api_busca_por_nombre_y_lee_la_ficha_solo_de_los_titulos_de_un_cargo():
    api = Api([_resumen(1), _resumen(2, "Vendedor de mostrador"), _resumen(3, modalidad="Solo teletrabajo")],
              {"abc001": _detalle(1, externalUrlForm="https://empleo.empresa-ficticia.es/qa"),
               "abc003": _detalle(3, archived=True)})
    crudas, stats = _api(api)
    url, params, cabeceras = api.pedidas[0]
    assert url == infojobs.API_BUSQUEDA and params["country"] == "espana" and params["q"] == "analista qa"
    assert all(c["Authorization"].startswith("Basic ") for _, _, c in api.pedidas)
    assert [u.rsplit("/", 1)[1] for u, _, _ in api.pedidas[1:]] == ["abc001", "abc003"]  # la del vendedor no se pide
    assert crudas == [{"titulo": "QA Tester", "empresa": "Empresa Ficticia, S.L.", "ubicacion": "Madrid, España (Híbrido)",
                       "descripcion": TEXTO.strip() + "\nDos años de experiencia.", "remoto": None, "fuente": "InfoJobs",
                       "fecha": "2026-11-10",  # la de creación, no la de la última republicación
                       "enlace": "https://www.infojobs.net/madrid/qa-tester/of-iabc001",
                       "enlace_directo": "https://empleo.empresa-ficticia.es/qa"}]
    assert stats == {"modo": "api", "busquedas": 1, "fallidas": 0, "avisos": 3, "del_cargo": 2, "fichas": 2,
                     "cerradas": 1, "con_descripcion": 1, "combinaciones_total": 2}
    # La ficha leída comprueba el enlace (activa) o lo cierra (archivada), como una de LinkedIn (v39).
    assert infojobs.FICHAS["https://www.infojobs.net/madrid/qa-tester/of-iabc001"]["estado"] == "verificada"
    assert infojobs.FICHAS["https://www.infojobs.net/madrid/qa-tester/of-iabc003"]["motivo"] == "vacante cerrada"
    # Ni las estadísticas ni lo guardado llevan la clave.
    assert CLAVE[1] not in json.dumps([crudas, stats, infojobs.FICHAS]) and "c2VjcmV0" not in json.dumps([crudas, stats])


def test_la_api_no_inventa_si_la_ficha_es_rara_vieja_o_no_dice_que_esta_activa():
    fichas = {"abc001": _detalle(1, creationDate="2026-09-01T09:00:00.000Z"),   # más de 30 días: no se guarda
              "abc002": {k: v for k, v in _detalle(2).items() if k != "active"},  # no dice si está activa
              "abc003": None, "abc004": _detalle(4, description="Corta.", minRequirements="")}
    crudas, stats = _api(Api([_resumen(n) for n in (1, 2, 3, 4)], fichas))
    assert [c["enlace"][-6:] for c in crudas] == ["abc002", "abc004"] and stats["fallidas"] == 1
    assert infojobs.FICHAS == {}  # sin «activa» o sin descripción suficiente no cuenta como comprobada


def test_una_clave_rechazada_detiene_la_fuente_y_lo_dice_sin_mostrarla():
    api = Api([_resumen(1)], codigo=401)
    crudas, stats = _api(api, presupuesto=5)
    assert crudas == [] and len(api.pedidas) == 1 and "rechazó la clave (401)" in stats["error"]
    assert CLAVE[0] not in json.dumps(stats) and CLAVE[1] not in json.dumps(stats)


class SesionApi:
    def __init__(self, respuesta):
        self.respuesta, self.pedidas = respuesta, []

    def get(self, url, headers=None, timeout=None, **_):
        self.pedidas.append((url, bool((headers or {}).get("Authorization"))))
        return self.respuesta

    def close(self):
        pass


def test_con_clave_el_enlace_se_comprueba_con_la_ficha_de_la_api_y_sin_clave_no_se_pide(monkeypatch):
    enlace = "https://www.infojobs.net/madrid/qa-tester/of-iabc001"
    ahora = datetime(2026, 11, 26, tzinfo=timezone.utc)
    monkeypatch.delenv("INFOJOBS_CLIENT_ID", raising=False)
    monkeypatch.delenv("INFOJOBS_CLIENT_SECRET", raising=False)
    sesion = SesionApi(RespuestaApi(_detalle(1)))
    sin = verificar_enlaces.comprobar(enlace, "QA Tester", sesion=sesion, ahora=ahora)
    assert sin["motivo"] == "sin comprobación directa" and sesion.pedidas == []
    monkeypatch.setenv("INFOJOBS_CLIENT_ID", CLAVE[0])
    monkeypatch.setenv("INFOJOBS_CLIENT_SECRET", CLAVE[1])
    assert not verificar_enlaces.sin_comprobacion_directa(enlace)
    assert verificar_enlaces.sin_comprobacion_directa("https://www.infojobs.net/empresas/x")  # no es un aviso
    assert verificar_enlaces.sin_comprobacion_directa("https://es.indeed.com/viewjob?jk=1")   # Indeed no cambia

    def comprobar(respuesta, titulo="QA Tester"):
        s = SesionApi(respuesta)
        r = verificar_enlaces.comprobar(enlace, titulo, sesion=s, ahora=ahora)
        assert s.pedidas == [(infojobs.API_FICHA + "abc001", True)]  # la API, nunca la página (pide captcha)
        return r["estado"], r["motivo"]
    assert comprobar(RespuestaApi(_detalle(1))) == ("verificada", "ficha específica accesible")
    assert comprobar(RespuestaApi(_detalle(1, archived=True))) == ("rechazada", "vacante cerrada")
    assert comprobar(RespuestaApi(_detalle(1, deleted=True))) == ("rechazada", "vacante cerrada")
    assert comprobar(RespuestaApi({}, 404)) == ("rechazada", "enlace roto")
    for respuesta in (RespuestaApi({}, 401), RespuestaApi({}, 500), RespuestaApi(None), RespuestaApi([1]),
                      RespuestaApi({k: v for k, v in _detalle(1).items() if k != "active"}),
                      RespuestaApi(_detalle(1, active=False)), RespuestaApi(_detalle(1, "Vendedor de mostrador"))):
        assert comprobar(respuesta)[0] == "pendiente"
