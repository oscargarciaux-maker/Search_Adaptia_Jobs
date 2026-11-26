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
    assert {"analista qa", "analista de pruebas"} <= set(nombres) and len(nombres) == stats["busquedas"] == 4
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
    ya = {p["keyword"] for _, p, _ in primera.pedidas}
    assert all(p["keyword"] not in ya for _, p, _ in segunda.pedidas)


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
              _aviso(6, ciudad="Córdoba")]                                    # hay otra Córdoba en Argentina
    crudas, stats = _buscar(Cliente([Respuesta(_pagina(avisos))]), presupuesto=1)
    assert [c["enlace"][-6:] for c in crudas] == ["abc002", "abc003", "abc004", "abc006"]
    assert [c["fecha"] for c in crudas] == ["2026-11-20", "", "", "2026-11-20"]
    assert list(infojobs.VISTAS) == ["https://www.infojobs.net/madrid/qa-tester/of-iabc006"]
    # Una ciudad con homónima en otro país («Córdoba», «Guadalajara») nunca abre ese país.
    from buscador import paises
    for ciudad in ("Córdoba", "Guadalajara", "Cartagena", "Valencia", "Mérida"):
        ubicacion = infojobs.vacante(_aviso(7, ciudad=ciudad))["ubicacion"]
        assert set(paises.alcance("", ubicacion).get("paises_mundo") or []) <= {"ES"}, ubicacion


def test_al_primer_captcha_la_fuente_se_detiene_y_no_insiste():
    cliente = Cliente([Respuesta(_pagina([_aviso(1)])), Respuesta(CAPTCHA), Respuesta(_pagina([_aviso(2)]))])
    estado = {}
    crudas, stats = _buscar(cliente, estado)
    assert len(cliente.pedidas) == 2 and stats == {"busquedas": 2, "bloqueada": True, "avisos": 1, "vistas": 1,
                                                   "combinaciones_total": 2}
    assert len(crudas) == 1
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
