"""Contrato real del actor, gasto acotado y ofertas formales de LinkedIn."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from buscador import apify, cobertura, entrega, familias, vacante
from buscador.fuentes import linkedin_apify, linkedin_publico, publicaciones_apify

HOY = "2026-11-04"
TEXTO = "We are hiring a UX Designer for our fully remote team across Latin America. Work with Figma and research. " * 5
ITEM = {"id": "1234567890", "title": "UX Designer", "linkedinUrl": "https://www.linkedin.com/jobs/view/1234567890/",
        "jobState": "LISTED", "descriptionText": TEXTO, "postedDate": "2026-11-03T10:00:00Z",
        "company": {"name": "Empresa"}, "location": {"parsed": {"text": "Remote - LATAM"}},
        "workplaceType": "remote", "applyMethod": {"companyApplyUrl": "https://jobs.lever.co/a/1"}}


class Cliente:
    def __init__(self, items=None, estado="SUCCEEDED"):
        self.items, self.estado, self.posts = items if items is not None else [ITEM], estado, []
    def post_json(self, url, cuerpo, **op):
        self.posts.append((url, cuerpo, op))
        return {"data": {"id": "run", "status": self.estado, "defaultDatasetId": "dataset", "usageTotalUsd": 0.002}}
    def json(self, url, **op):
        return self.items


def test_presupuesto_diario_mensual_y_reinicio_no_reponen_credito():
    estado, guardados = {}, []
    p = apify.Presupuesto(estado, HOY, guardar=lambda e: guardados.append(dict(e)))
    total = sum(p.reservar(0.025) for _ in range(100))
    assert 0 < total <= 5 / 30
    assert guardados
    assert apify.Presupuesto(estado, HOY).reservar(0.025) == 0
    for dia in range(5, 31):
        p = apify.Presupuesto(estado, f"2026-11-{dia:02d}")
        for _ in range(100):
            p.reservar(0.025)
    assert sum(estado["reservas"].values()) <= 5


def test_reserva_concurrente_y_cambio_de_mes():
    estado = {}
    p = apify.Presupuesto(estado, HOY)
    with ThreadPoolExecutor(8) as ex:
        sum(ex.map(p.reservar, [0.025] * 30))
    assert sum(estado["reservas"].values()) <= 5 / 30
    p = apify.Presupuesto(estado, "2026-12-01")
    assert estado["mes"] == "2026-12" and not estado["reservas"]
    assert p.reservar(0.025) > 0


def test_schema_harvest_sin_cookies_ni_filtros_de_nivel():
    cuerpo = linkedin_apify.entrada("harvestapi/linkedin-job-search", ["ux designer", "interaction designer"],
                                    {"location": "Spain", "f_WT": "2"}, 30, 20)
    assert cuerpo == {"jobTitles": ['"ux designer" OR "interaction designer"'], "maxItems": 20,
                       "locations": ["Spain"], "workplaceType": ["remote"], "postedLimit": "month", "sortBy": "date"}
    mundo = linkedin_apify.entrada("harvestapi/linkedin-job-search", ["ux designer"],
                                   {"location": "Worldwide", "f_WT": "2"}, 1, 20)
    assert "locations" not in mundo and mundo["workplaceType"] == ["remote"]
    with pytest.raises(ValueError):
        linkedin_apify.entrada("actor-sin-adaptador", ["ux"], {}, 30, 20)


def test_api_limita_cargo_y_no_incluye_token_en_url():
    cliente = Cliente()
    items, stats = apify.ejecutar(cliente, "harvestapi/linkedin-job-search", {"maxItems": 1}, "ficticio", 0.01)
    url, cuerpo, op = cliente.posts[0]
    assert "maxTotalChargeUsd=0.01" in url and "ficticio" not in url
    assert op["headers"]["Authorization"] == "Bearer ficticio"
    assert items == [ITEM] and stats["run_id"] == "run"


def test_no_relanzar_si_inicio_no_confirmado():
    class Roto(Cliente):
        def post_json(self, *args, **kwargs):
            return None
    items, stats = apify.ejecutar(Roto(), "actor", {}, "ficticio", 0.01)
    assert items == [] and stats["error"] and stats["tope_reservado_usd"] == 0.01


def test_error_del_proveedor_es_visible_y_oculta_token():
    class Roto(Cliente):
        ultimo_error = {"http": 403, "mensaje": "denegado ficticio"}
        def post_json(self, *args, **kwargs):
            return None
    _, stats = apify.ejecutar(Roto(), "actor", {}, "ficticio", 0.01)
    assert stats["detalle"]["http"] == 403 and "ficticio" not in str(stats)


def test_normalizar_salida_harvest_y_entrega():
    cruda = linkedin_apify.normalizar_item(ITEM)
    assert cruda["ubicacion"] == "Remote - LATAM" and cruda["empresa"] == "Empresa"
    assert cruda["fecha"] == "2026-11-03" and cruda["enlace_directo"] == "https://jobs.lever.co/a/1"
    v = vacante.crear(cruda["titulo"], cruda["empresa"], cruda["enlace"], cruda["fuente"], cruda["ubicacion"],
                       descripcion=cruda["descripcion"], fecha=cruda["fecha"], remoto=cruda["remoto"], hoy=HOY)
    elegidas, _ = entrega.elegir([v], {}, HOY)
    assert len(elegidas["ux-ui-designer"]) == 1


def test_ofertas_cerradas_posts_y_descripciones_cortas_no_pasan():
    items = [ITEM, dict(ITEM, closedAt=HOY), dict(ITEM, descriptionText="corto"),
             dict(ITEM, linkedinUrl="https://www.linkedin.com/posts/empresa_123")]
    cliente = Cliente(items)
    mapa = [next(f for f in familias.mapa() if f["id"] == "diseno-producto-ux")]
    datos, salud = linkedin_apify.buscar(cliente, "harvestapi/linkedin-job-search",
        linkedin_publico.combinaciones(mapa, [("ES", "España")]), {}, HOY, presupuesto=1, token="ficticio",
        prioritarias={"diseno-producto-ux"})
    assert len(datos) == 1 and sum(salud["descartadas"].values()) == 3
    assert "REMOTO" in next(iter(salud["por_lugar"]))


def test_reserva_antes_de_ejecutar_y_consulta_fallida_no_mueve_rotacion():
    estado, guardados = {}, []
    presupuesto = apify.Presupuesto({}, HOY, guardar=lambda e: guardados.append(True))
    class Roto(Cliente):
        def post_json(self, *args, **kwargs):
            assert guardados
            return None
    combos = [("ux", ["ux designer"], "REMOTO", {"location": "Latin America", "f_WT": "2"})]
    datos, salud = linkedin_apify.buscar(Roto(), "harvestapi/linkedin-job-search", combos, estado, HOY,
                                        presupuesto=1, token="ficticio", control_gasto=presupuesto)
    assert datos == [] and salud["error"] and estado == {}


def test_publicacion_con_enlace_formal_se_resuelve_automaticamente():
    post = {"text": TEXTO + " https://www.linkedin.com/jobs/view/1234567890/",
            "url": "https://www.linkedin.com/posts/empresa_hiring-activity-1234567890123456789",
            "author": {"type": "company", "name": "Empresa"}}
    class ConFicha(Cliente):
        def get(self, url, **op):
            html = '<h1>UX Designer</h1><a class="topcard__org-name-link">Empresa original</a>'
            html += '<span class="topcard__flavor--bullet">Remote - LATAM</span>'
            html += '<div class="show-more-less-html__markup">' + TEXTO + '</div>'
            return type("R", (), {"status_code": 200, "text": html})()
    datos, salud = publicaciones_apify.buscar(ConFicha([post]), "actor", ["ux"], {"diseno-producto-ux"}, HOY,
                                              token="ficticio")
    assert len(datos) == 1 and salud["pendientes_revision"] == 0
    assert datos[0]["empresa"] == "Empresa original" and "/jobs/view/" in datos[0]["enlace"]
