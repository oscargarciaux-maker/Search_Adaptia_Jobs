"""Contrato v50 §3: Tecnoempleo (España), sin red y con datos ficticios. Búsqueda por nombre y ficha con JobPosting; se
postula en el propio portal (decisión de Oscar del 26 nov: pasa de agregador a portal)."""
import json

from buscador import bodega, cobertura, enlaces
from buscador.fuentes import tecnoempleo as te

FICHA_QA = "https://www.tecnoempleo.com/qa-tester-empresa-ficticia/selenium-postman/rf-aaaa1111bbbb2222cccc"
FICHA_OTRA = "https://www.tecnoempleo.com/vendedor-de-mostrador-tienda/excel/rf-dddd3333eeee4444ffff"
LISTADO = (f'<html><a class="x" href="{FICHA_QA}"><img src="logo.png"></a>'
           f'<h3><a href="{FICHA_QA}" title="oferta">QA Tester <b>Junior</b></a></h3>'
           f'<h3><a href="{FICHA_OTRA}">Vendedor de mostrador</a></h3>'
           '<a href="https://www.tecnoempleo.com/ofertas-trabajo/?pagina=2">Siguiente</a></html>')


def _ficha(titulo="QA Tester Junior", publicada="2026-11-20", hasta=None, ciudad="Granada"):
    posting = {"@context": "https://schema.org/", "@type": "JobPosting", "title": titulo, "datePosted": publicada,
               "description": "<p>Buscamos un/a QA Tester para diseñar casos de prueba, ejecutar pruebas manuales y "
                              "automatizadas con Selenium y Postman y reportar defectos en Jira junto a desarrollo.</p>" * 2,
               "hiringOrganization": {"@type": "Organization", "name": "Empresa Ficticia"},
               "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "ES",
                                                              "addressLocality": ciudad}}}
    if hasta:
        posting["validThrough"] = hasta
    return '<html><script type="application/ld+json">' + json.dumps(posting) + "</script></html>"


class Respuesta:
    def __init__(self, texto, codigo=200):
        self.text, self.status_code = texto, codigo


class Cliente:
    def __init__(self, fichas=None, listado=LISTADO):
        self.pedidas, self.fichas, self.listado = [], fichas, listado

    def get(self, url, params=None, **_):
        self.pedidas.append((url, dict(params or {})))
        if url == te.BUSQUEDA:
            return self.listado if isinstance(self.listado, Respuesta) else Respuesta(self.listado)
        return Respuesta(self.fichas.pop(0) if self.fichas else _ficha())


MAPA = [{"id": "qa", "consultas": ["qa tester", "qa engineer"], "consultas_es": ["analista qa"],
         "paises_objetivo": ["ES"], "paises_es": ["ES"]},
        {"id": "product-manager", "consultas": ["product manager"], "paises_objetivo": ["MX"]}]


def test_lee_la_busqueda_y_solo_la_ficha_de_los_titulos_de_un_cargo_buscado():
    assert te.tarjetas(LISTADO) == [(FICHA_QA, "QA Tester Junior"), (FICHA_OTRA, "Vendedor de mostrador")]
    cliente = Cliente()
    crudas, stats = te.buscar(cliente, MAPA, {}, 1, hoy="2026-11-26")
    assert [u for u, _ in cliente.pedidas] == [te.BUSQUEDA, FICHA_QA]  # la del vendedor no se abre
    assert cliente.pedidas[0][1] == {"te": "analista qa"}
    assert stats["busquedas"] == 1 and stats["avisos"] == 2 and stats["del_cargo"] == 1 and stats["con_descripcion"] == 1
    assert crudas == [{"titulo": "QA Tester Junior", "empresa": "Empresa Ficticia", "ubicacion": "Granada, España",
                       "remoto": None, "descripcion": crudas[0]["descripcion"], "fecha": "2026-11-20",
                       "enlace": FICHA_QA, "enlace_directo": "", "fuente": "Tecnoempleo"}]
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-26", 30, set(), set())
    v = vacantes[0]
    assert v["paises"] == ["ES"] and v["idioma"] == "es" and v["fuente"] == "Tecnoempleo" and v["tipo_enlace"] == "portal"


def test_solo_para_cargos_con_alguien_en_espana_y_sin_repetir_nombres_el_mismo_dia():
    estado = {}
    primera, segunda = Cliente(), Cliente()
    _, stats = te.buscar(primera, MAPA, estado, 2, hoy="2026-11-26")
    te.buscar(segunda, MAPA, estado, 5, hoy="2026-11-26")  # la segunda pasada del día sigue con el nombre que falta
    nombres = [p["te"] for u, p in primera.pedidas + segunda.pedidas if u == te.BUSQUEDA]
    assert sorted(nombres) == ["analista qa", "qa engineer", "qa tester"] and "product manager" not in nombres
    cobertura.configurar_personas([{"familia": "qa", "perfil": "p", "lugares": ["ES"], "peso": 5, "corto": True,
                                    "idiomas": ["es", "en"]}])
    cobertura.configurar_faltantes(True)
    try:
        tercera = Cliente()
        te.buscar(tercera, MAPA, estado, 5, hoy="2026-11-26")
    finally:
        cobertura.configurar_faltantes(False)
        cobertura.configurar_personas()
    assert tercera.pedidas == []


def test_fichas_cerradas_o_sin_datos_y_portal_caido():
    cliente = Cliente([_ficha(hasta="2026-11-01"), "<html>sin datos</html>"])
    crudas, stats = te.buscar(cliente, MAPA, {}, 2, hoy="2026-11-26")
    assert crudas == [] and stats["cerradas"] == 1
    caido = Cliente(listado=Respuesta("", 503))
    crudas, stats = te.buscar(caido, MAPA, {}, 10, hoy="2026-11-26")
    assert crudas == [] and stats["fallidas"] == 3 and len(caido.pedidas) == 3  # tres fallos seguidos lo detienen


def test_tecnoempleo_es_un_portal_donde_se_postula_y_esta_registrado():
    from buscador import contrato
    from panel import ejecutor
    assert enlaces.tipo(FICHA_QA) == "portal" and enlaces.sirve(FICHA_QA) and contrato.portal(FICHA_QA) == "Tecnoempleo"
    assert "tecnoempleo.com" not in enlaces.dominios()["agregadores"]
    assert bodega.config()["presupuestos"]["tecnoempleo_busquedas"] > 0
    assert "Tecnoempleo" in ejecutor.fuentes_en("ES") and "Tecnoempleo" not in ejecutor.fuentes_en("CO")
