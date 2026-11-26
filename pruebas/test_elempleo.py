"""PR 1b: Elempleo (Colombia) sin red, con páginas recortadas como las reales (ItemList y JobPosting de schema.org)."""
import json

from buscador import bodega
from buscador.fuentes import elempleo as ee

LISTADO = '<html><script type="application/ld+json" id="itemListStructuredData">' + json.dumps({
    "@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "item": {
            "@id": "https://www.elempleo.com/co/ofertas-trabajo/disenadora-ui-ux-senior-1886785168?trabajo=x",
            "@type": "WebPage", "name": "Diseñador(a) ui/ux senior."}},
        {"@type": "ListItem", "position": 2, "item": {
            "@id": "https://www.elempleo.com/co/ofertas-trabajo/disenador-ui-ux-hibrido-en-bogota-1886783875",
            "@type": "WebPage", "name": "Diseñador ui/ux - hibrido en bogotá"}}]}) + "</script></html>"


def _ficha(remota=True, hasta="2026-12-25", salario=True):
    posting = {"@context": "https://schema.org/", "@type": "JobPosting", "title": "Diseñador(a) UI/UX Senior.",
               "description": "<p>Buscamos un diseñador UX/UI con experiencia en productos digitales.</p>"
                              "<p>Trabajarás con equipos de producto en Colombia.</p>" * 3,
               "datePosted": "2026-11-10", "validThrough": hasta, "employmentType": "FULL_TIME",
               "hiringOrganization": {"@type": "Organization", "name": "Empresa Ejemplo"},
               "jobLocation": {"@type": "Place", "address": {"addressLocality": "Bogotá D.C.", "addressCountry": "CO"}},
               "applicantLocationRequirements": {"@type": "Country", "name": "Colombia"}}
    if remota:
        posting["jobLocationType"] = "TELECOMMUTE"
    if salario:
        posting["baseSalary"] = {"currency": "COP", "value": {"minValue": 8000001, "maxValue": 10000000,
                                                              "unitText": "MONTH"}}
    return '<script type="application/ld+json">' + json.dumps(posting) + "</script>"


class Respuesta:
    def __init__(self, texto, codigo=200):
        self.text, self.status_code = texto, codigo


class Cliente:
    def __init__(self, fichas):
        self.pedidas, self.fichas = [], fichas

    def get(self, url, params=None):
        self.pedidas.append(url)
        return Respuesta(LISTADO if "/ofertas-empleo/" in url else self.fichas.pop(0))


def test_lista_y_ficha_estructuradas():
    assert [t for _, t in ee.tarjetas(LISTADO)] == ["Diseñador(a) ui/ux senior.", "Diseñador ui/ux - hibrido en bogotá"]
    assert all("?" not in u for u, _ in ee.tarjetas(LISTADO))
    d = ee.ficha(_ficha(), "2026-11-15")
    assert d["ubicacion"] == "Colombia (Remoto)" and d["remoto"] is True and d["fecha"] == "2026-11-10"
    assert d["empresa"] == "Empresa Ejemplo" and "Salario: COP 8.000.001 - 10.000.000 mensual" in d["descripcion"]
    presencial = ee.ficha(_ficha(remota=False, salario=False), "2026-11-15")
    assert presencial["ubicacion"] == "Bogotá D.C., Colombia" and presencial["remoto"] is None
    assert "Salario" not in presencial["descripcion"]  # sin salario en la ficha no se inventa
    assert ee.ficha(_ficha(hasta="2026-11-01"), "2026-11-15")["cerrada"]
    assert ee.ficha("<html>sin datos</html>", "2026-11-15") is None


def test_busqueda_completa_y_vacantes_utilizables():
    mapa = [{"id": "diseno-producto-ux", "consultas": ["Product Designer"], "consultas_es": ["diseñador ux/ui"],
             "exactos": [], "similares": [], "cercanos": [], "paises_objetivo": ["CO"]}]
    cliente, estado = Cliente([_ficha(), _ficha(remota=False, hasta="2026-11-01")]), {}
    crudas, stats = ee.buscar(cliente, mapa, estado, 5, hoy="2026-11-15")
    assert cliente.pedidas[0] == "https://www.elempleo.com/co/ofertas-empleo/trabajo-disenador-ux-ui"  # en español
    # Contrato v50: después, también con los demás nombres del cargo (antes, con títulos en español, solo con esos).
    assert cliente.pedidas[1] == "https://www.elempleo.com/co/ofertas-empleo/trabajo-product-designer"
    assert stats["busquedas"] == 2 and stats["avisos"] == 2 and stats["cerradas"] == 1 and len(crudas) == 1
    assert estado["diseno-producto-ux@CO:ES"] == estado["diseno-producto-ux@CO"] == "2026-11-15"
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-15", 30, set(), set())
    v = vacantes[0]
    assert v["paises"] == ["CO"] and v["modalidad"] == "remoto" and v["fuente"] == "Elempleo" and v["idioma"] == "es"
    assert v["fecha_publicacion"] == "2026-11-10" and v["salario"]


def test_cargos_sin_perfiles_en_colombia_no_se_buscan():
    mapa = [{"id": "x", "consultas": ["QA"], "exactos": [], "similares": [], "cercanos": [], "paises_objetivo": ["MX"]}]
    cliente = Cliente([])
    assert ee.buscar(cliente, mapa, {}, 5, hoy="2026-11-15")[1]["busquedas"] == 0 and not cliente.pedidas


def test_bloqueos_seguidos_detienen_la_fuente():
    class Bloqueado:
        n = 0

        def get(self, url, params=None):
            self.n += 1
            return Respuesta("", 403)
    mapa = [{"id": f"f{i}", "consultas": [f"cargo {i}"], "exactos": [], "similares": [], "cercanos": []} for i in range(9)]
    b = Bloqueado()
    ee.buscar(b, mapa, {}, 20, hoy="2026-11-15")
    assert b.n == 4


def test_fecha_sin_ceros_se_normaliza():
    assert ee._fecha("2026-10-6") == "2026-10-06" and ee._fecha("2026-11-10T00:00:00") == "2026-11-10"
    assert ee._fecha("") == "" and ee._fecha("ayer") == ""
