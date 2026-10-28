"""Lectores de cada fuente con respuestas guardadas (sin red) y la limpieza de la bodega."""
import pandas as pd

from buscador import bodega, vacante
from buscador.fuentes import ats, brave, getonbrd, indeed, linkedin_apify, linkedin_publico, remotos

TARJETAS_LINKEDIN = """
<li><div class="base-card" data-entity-urn="urn:li:jobPosting:4483216798">
  <h3 class="base-search-card__title">  Senior Product Designer (UX/UI)  </h3>
  <h4 class="base-search-card__subtitle"><a>BairesDev</a></h4>
  <span class="job-search-card__location">Bogotá, Distrito Capital, Colombia</span>
  <time class="job-search-card__listdate" datetime="2026-10-27">hace 1 día</time></div></li>
<li><div data-entity-urn="urn:li:jobPosting:4480062142">
  <h3 class="base-search-card__title">Desarrollador Backend Java</h3>
  <h4 class="base-search-card__subtitle">Empresa &amp; Cía</h4>
  <span class="job-search-card__location">Caracas, Venezuela</span></div></li>
"""


def test_tarjetas_de_linkedin():
    filas = linkedin_publico.tarjetas(TARJETAS_LINKEDIN)
    assert [f["id"] for f in filas] == ["4483216798", "4480062142"]
    assert filas[0]["titulo"] == "Senior Product Designer (UX/UI)" and filas[0]["empresa"] == "BairesDev"
    assert filas[0]["fecha"] == "2026-10-27" and filas[1]["fecha"] == ""
    assert filas[1]["empresa"] == "Empresa & Cía"
    assert filas[0]["enlace"] == "https://www.linkedin.com/jobs/view/4483216798"


def test_ficha_de_linkedin():
    pagina = '<div class="show-more-less-html__markup">Buscamos <b>diseñador</b><br>con Figma</div>'
    descripcion, cerrado, _, _ = linkedin_publico.ficha(pagina)
    assert "diseñador" in descripcion and "Figma" in descripcion and not cerrado
    assert linkedin_publico.ficha(pagina + "No longer accepting applications")[1]


def test_consulta_or_y_combinaciones():
    assert linkedin_publico.consulta_or(["product designer", "ux designer"]) == '"product designer" OR "ux designer"'
    combos = linkedin_publico.combinaciones([{"id": "x", "consultas": ["a"]}], [("CO", "Colombia"), ("VE", "Venezuela")])
    assert [c[2] for c in combos] == ["CO", "VE", "LATAM", "REMOTO"]


class _Respuesta:
    def __init__(self, texto, status=200, url="https://example.com"):
        self.text, self.status_code, self.url = texto, status, url


class _ClienteFalso:
    """Devuelve respuestas guardadas por URL; cuenta las peticiones."""

    def __init__(self, paginas):
        self.paginas, self.peticiones = paginas, 0

    def get(self, url, params=None, **k):
        self.peticiones += 1
        if params:
            url = url + "?" + "&".join(f"{a}={b}" for a, b in sorted(params.items()))
        for clave, respuesta in self.paginas.items():
            if clave in url:
                return respuesta
        return _Respuesta("", 404)


def test_linkedin_rota_combinaciones_y_respeta_el_presupuesto():
    cliente = _ClienteFalso({"seeMoreJobPostings": _Respuesta(TARJETAS_LINKEDIN),
                             "jobPosting/": _Respuesta('<div class="show-more-less-html__markup">Figma</div>')})
    mapa = [{"id": "diseno", "consultas": ["product designer"]}, {"id": "dev", "consultas": ["backend developer"]}]
    estado = {"dev@CO": "2026-10-27"}
    crudas, stats = linkedin_publico.buscar(cliente, mapa, [("CO", "Colombia")], estado, presupuesto=2, hoy="2026-10-28")
    assert stats["busquedas"] == 2
    assert estado["diseno@CO"] == "2026-10-28"           # la nunca revisada va primero
    assert len(crudas) == 2 and all(c["fuente"] == "LinkedIn" for c in crudas)


def test_indeed_con_resultado_guardado():
    def scrape(**k):
        assert k["country_indeed"] == "venezuela"
        return pd.DataFrame([{"title": "Desarrollador Full Stack", "company": "Acme", "location": "Caracas",
                              "description": "React y Node", "date_posted": pd.Timestamp("2026-10-25"),
                              "job_url": "https://ve.indeed.com/viewjob?jk=1", "job_url_direct": "https://jobs.lever.co/acme/1",
                              "is_remote": False}])
    crudas, stats = indeed.buscar([{"id": "fullstack", "consultas": ["full stack developer"]}], ["VE", "BO"], {}, 5,
                                  hoy="2026-10-28", scrape=scrape)
    assert stats["busquedas"] == 1                        # Bolivia no está en Indeed
    assert crudas[0]["fecha"] == "2026-10-25" and crudas[0]["enlace_directo"] == "https://jobs.lever.co/acme/1"


def test_portales_de_empresas():
    gh = {"jobs": [{"title": "Product Designer", "location": {"name": "Remote - LATAM"},
                    "absolute_url": "https://job-boards.greenhouse.io/clara/jobs/1", "first_published": "2026-10-20T10:00:00Z",
                    "content": "&lt;p&gt;Figma&lt;/p&gt;"}]}
    lever = [{"text": "UX Designer", "categories": {"location": "Bogotá"}, "hostedUrl": "https://jobs.lever.co/x/1",
              "createdAt": 1792000000000, "descriptionPlain": "Figma", "workplaceType": "remote"}]
    ashby = {"jobs": [{"title": "Designer", "location": "Mexico City", "isRemote": True, "jobUrl": "https://jobs.ashbyhq.com/x/1",
                       "publishedAt": "2026-10-21T00:00:00Z", "descriptionPlain": "x", "isListed": True},
                      {"title": "Oculta", "isListed": False, "jobUrl": "https://jobs.ashbyhq.com/x/2"}]}
    assert ats.vacantes_de("greenhouse", gh, "Clara", "clara")[0]["descripcion"] == "Figma"
    lv = ats.vacantes_de("lever", lever, "X", "x")[0]
    assert lv["remoto"] is True and lv["fecha"].startswith("2026")
    assert [v["titulo"] for v in ats.vacantes_de("ashby", ashby, "X", "x")] == ["Designer"]
    assert ats.tiene_forma("greenhouse", gh) and not ats.tiene_forma("greenhouse", {"jobs": []})
    assert ats.slugs_para("Mercado Libre Colombia S.A.S.") == ["mercadolibre", "mercado-libre"]


def test_tableros_remotos_resuelven_el_original():
    cliente = _ClienteFalso({"remotive.com/remote-jobs/design/1": _Respuesta(
        '<a href="https://jobs.lever.co/acme/1">Apply for this position</a>', url="https://remotive.com/remote-jobs/design/1")})
    cache = {}
    crudas = [{"titulo": "UX Designer", "empresa": "Acme", "enlace": "https://remotive.com/remote-jobs/design/1"},
              {"titulo": "UI Designer", "empresa": "Beta", "enlace": "https://remotive.com/remote-jobs/design/2"}]
    resueltas, abiertas = remotos.resolver(cliente, crudas, cache, maximo=10)
    assert [v["enlace"] for v in resueltas] == ["https://jobs.lever.co/acme/1"]
    assert cache["https://remotive.com/remote-jobs/design/2"] == ""
    _, abiertas2 = remotos.resolver(cliente, crudas, cache, maximo=10)
    assert abiertas2 == 0                                  # la segunda noche no vuelve a abrir


def test_get_on_board_y_apify():
    item = {"attributes": {"title": "Product Designer", "remote": True, "remote_zone": "LATAM", "countries": ["Chile"],
                           "published_at": 1792000000, "company": {"data": {"attributes": {"name": "Buk"}}},
                           "description": "<p>Figma</p>"},
            "links": {"public_url": "https://www.getonbrd.com/jobs/design/product-designer-buk"}}
    v = getonbrd.vacante(item)
    assert v["empresa"] == "Buk" and v["remoto"] is True and "LATAM" in v["ubicacion"]
    a = linkedin_apify.normalizar_item({"title": "UX Designer", "companyName": "Acme", "location": "Lima, Peru",
                                        "link": "https://www.linkedin.com/jobs/view/123", "postedAt": "2026-10-26",
                                        "descriptionText": "Figma", "applyUrl": "https://jobs.lever.co/acme/1"})
    assert a["enlace_directo"] == "https://jobs.lever.co/acme/1" and a["fecha"] == "2026-10-26"
    assert linkedin_apify.buscar(None, "", [], {}, "2026-10-28", token="")[1]["omitida"]


def test_brave_rota_consultas_y_se_omite_sin_clave():
    a, b = brave.consultas_del_dia(5, 1), brave.consultas_del_dia(5, 2)
    assert len(a) == 5 and a != b
    assert brave.buscar(None, 5, 1, clave="")[1]["omitida"]


def test_limpiar_junta_quita_viejas_y_cerradas():
    hoy = "2026-10-28"
    previa_vieja = vacante.crear("Product Designer", "Vieja", "https://www.linkedin.com/jobs/view/9", "LinkedIn",
                                 "Bogotá, Colombia", fecha="2026-09-01", hoy="2026-09-01")
    previa_cerrada = vacante.crear("UX Designer", "Clara", "https://job-boards.greenhouse.io/clara/jobs/7",
                                   "Portales de empresas (greenhouse)", "Remote - LATAM", fecha="2026-10-20", hoy="2026-10-20")
    crudas = [
        {"titulo": "UX/UI Designer", "empresa": "Acme", "enlace": "https://www.linkedin.com/jobs/view/1", "fuente": "LinkedIn",
         "ubicacion": "Lima, Peru", "fecha": "2026-10-27"},
        {"titulo": "UX/UI Designer", "empresa": "ACME S.A.", "enlace": "https://jobs.lever.co/acme/1",
         "fuente": "Portales de empresas (lever)", "ubicacion": "Remote - LATAM", "fecha": "2026-10-26"},
        {"titulo": "Cajero", "empresa": "Super", "enlace": "https://www.linkedin.com/jobs/view/2", "fuente": "LinkedIn"},
        {"titulo": "Product Designer", "empresa": "Gringa", "enlace": "https://www.linkedin.com/jobs/view/3",
         "fuente": "LinkedIn", "ubicacion": "New York, NY, United States"},
        {"titulo": "Designer UX", "empresa": "Copia", "enlace": "https://jooble.org/x", "fuente": "X"},
    ]
    vacantes, sin_familia, descartes = bodega.limpiar([previa_vieja, previa_cerrada], crudas, hoy, 30,
                                                      enlaces_ats={"https://jobs.lever.co/acme/1"},
                                                      empresas_leidas={"Clara", "ACME S.A."})
    assert [v["empresa"] for v in vacantes] == ["Acme"]
    assert vacantes[0]["enlace_directo"] == "https://jobs.lever.co/acme/1"
    assert sin_familia["cajero"] == 1
    assert descartes["no se puede aplicar desde LATAM"] == 1
    assert descartes["más de 30 días"] == 1
    assert descartes["cerrada en el portal de la empresa"] == 1
    assert descartes["sin enlace donde postular"] == 1


def test_limpiar_vuelve_a_leer_el_salario_de_las_previas():
    hoy = "2026-10-28"
    previa = vacante.crear("Product Designer", "Cleo", "https://www.linkedin.com/jobs/view/5", "LinkedIn",
                           "Remote - LATAM", descripcion="Cleo has raised $300M from investors.", fecha="2026-10-27",
                           hoy="2026-10-27")
    previa["salario"] = "$300M"  # como quedó con el código anterior
    vacantes, _, _ = bodega.limpiar([previa], [], hoy, 30, enlaces_ats=set(), empresas_leidas=set())
    assert vacantes[0]["salario"] == ""
