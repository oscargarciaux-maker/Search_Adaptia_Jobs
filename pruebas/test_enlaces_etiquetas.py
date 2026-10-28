"""Enlaces (original, portal, agregador), etiquetas y unión de copias del mismo aviso."""
import pytest
import yaml

from buscador import enlaces, etiquetas, vacante


@pytest.mark.parametrize("url,esperado", [
    ("https://job-boards.greenhouse.io/clara/jobs/5230221007", "original"),
    ("https://boards.greenhouse.io/nubank/jobs/123", "original"),
    ("https://jobs.lever.co/truelogic/abc", "original"),
    ("https://jobs.ashbyhq.com/truelogic/32e296cd", "original"),
    ("https://apply.workable.com/devsu/j/ABC123/", "original"),
    ("https://jobs.smartrecruiters.com/Globant/744000", "original"),
    ("https://empresa.wd5.myworkdayjobs.com/es/External/job/Bogota/Designer_R123", "original"),
    ("https://careers.mercadolibre.com/job/123", "original"),
    ("https://www.rappi.com/trabaja-con-nosotros", "original"),
    ("https://www.linkedin.com/jobs/view/4483216798", "portal"),
    ("https://co.indeed.com/viewjob?jk=e3c44b38b9e7123c", "portal"),
    ("https://www.computrabajo.com.co/ofertas-de-trabajo/oferta-de-trabajo-de-disenador", "portal"),
    ("https://co.computrabajo.com/trabajo-de-disenador", "portal"),
    ("https://mx.indeed.com/viewjob?jk=1", "portal"),
    ("https://www.bumeran.com.pe/empleos/disenador-1.html", "portal"),
    ("https://www.jooble.org/desc/1", "agregador"),
    ("https://co.jooble.org/desc/1", "agregador"),
    ("https://www.elempleo.com/co/ofertas-trabajo/disenador-ui-ux-1886783875", "portal"),
    ("https://www.getonbrd.com/jobs/design-ux/product-designer", "portal"),
    ("https://jooble.org/desc/123", "agregador"),
    ("https://co.bebee.com/job/abc", "agregador"),
    ("https://co.trabajo.org/oferta-123", "agregador"),
    ("https://www.jobleads.com/co/job/123", "agregador"),
    ("https://co.talent.com/view?id=123", "agregador"),
    ("https://www.jobted.com.co/job/d7d8fef7217eb2a85cc0c30c960eb422", "agregador"),
    ("https://co.sercanto.com/detail/a/disenadora", "agregador"),
    ("https://www.buscojobs.com.co/disenador-ui-ux-ID-23099172", "agregador"),
    ("https://jobicy.com/jobs/154105-senior-product-designer", "agregador"),
    ("https://remotive.com/remote-jobs/design/ux-designer-123", "agregador"),
    ("https://himalayas.app/companies/acme/jobs/designer", "agregador"),
    ("https://www.upwork.com/freelance-jobs/apply/abc", "agregador"),
    ("https://hirefinity.p3d.66ghz.com/remote-jobs/ux-ui-designer", "agregador"),
    ("https://www.acme-design.com/blog/post", "desconocido"),
    ("", "agregador"),
])
def test_tipo_de_enlace(url, esperado):
    assert enlaces.tipo(url) == esperado


def test_mejor_enlace_nunca_agregador():
    assert enlaces.mejor(["https://jooble.org/x", "https://jobs.lever.co/a/b"]) == "https://jobs.lever.co/a/b"
    assert enlaces.mejor(["https://www.linkedin.com/jobs/view/1", "https://jobs.lever.co/a/b"]) == "https://jobs.lever.co/a/b"
    assert enlaces.mejor(["https://jooble.org/x"]) == ""


def test_original_en_la_pagina_del_agregador():
    html = """<a href="https://www.linkedin.com/company/acme">Acme</a>
              <a href="/otra-vacante">Ver más</a>
              <a class="apply" href="https://jobs.lever.co/acme/123?ref=remotive">Apply for this position</a>"""
    assert enlaces.original_en_html(html, "https://remotive.com/remote-jobs/design/x") == "https://jobs.lever.co/acme/123?ref=remotive"
    assert enlaces.original_en_html("<a href='/x'>x</a>", "https://jobicy.com/jobs/1") == ""


def test_dominios_sin_repetir_entre_listas():
    d = yaml.safe_load(open(enlaces.RUTA, encoding="utf-8"))
    vistos = {}
    for lista in ("originales", "portales", "agregadores"):
        for dominio in d[lista]:
            assert dominio not in vistos, f"{dominio} está en {lista} y en {vistos.get(dominio)}"
            vistos[dominio] = lista


@pytest.mark.parametrize("texto,nivel", [
    ("Advanced English (C1) is required", "avanzado"),
    ("Inglés intermedio", "intermedio"),
    ("English: native", "nativo"),
    ("Fluent in English is a must", "fluido"),
    ("Se requiere persona bilingüe", "fluido"),
    ("We need B2 English", "intermedio"),
    ("C1 English required", "fluido"),
    ("Inglés básico", "basico"),
    ("Fluent in Python and SQL", ""),
    ("Excelente manejo de Figma", ""),
])
def test_ingles(texto, nivel):
    assert etiquetas.ingles(texto) == nivel


def test_idioma_anos_y_salario():
    assert etiquetas.idioma("We are looking for a designer with experience in Figma") == "en"
    assert etiquetas.idioma("Buscamos diseñador con experiencia en Figma para nuestro equipo") == "es"
    assert etiquetas.idioma("Você vai atuar com design de produto; não é necessário inglês") == "pt"
    assert etiquetas.anos_min("Mínimo 3 años de experiencia en diseño") == 3
    assert etiquetas.anos_min("5+ years of experience; 2 years in fintech") == 2
    assert etiquetas.anos_min("Somos una empresa con 15 años en el mercado") is None
    assert etiquetas.salario("Salario: $3.000.000 - $4.000.000 COP mensuales") == "$3.000.000 - $4.000.000 COP"
    assert etiquetas.salario("USD 2,500 - 3,000 per month") == "USD 2,500 - 3,000 per month"
    assert etiquetas.salario("Trabajo con 2 personas") == ""
    assert etiquetas.salario("Cleo has raised $300M from top investors.") == ""
    assert etiquetas.salario("Procesamos US$ 2.000 millones en transacciones. Salario: USD 1,500 - 2,000 per month") \
        == "USD 1,500 - 2,000 per month"


def _v(**k):
    base = dict(titulo="Product Designer", empresa="Acme S.A.S.", enlace="https://www.linkedin.com/jobs/view/1",
                fuente="LinkedIn", ubicacion="Bogotá, Colombia", descripcion="", fecha="2026-10-20", hoy="2026-10-28")
    base.update(k)
    return vacante.crear(**base)


def test_crear_descarta_lo_que_no_sirve():
    assert _v(titulo="Cajero de supermercado") is None                      # no es de ninguna familia
    assert _v(enlace="https://jooble.org/desc/1") is None                    # solo agregador
    v = _v(enlace="https://jooble.org/desc/1", enlace_directo="https://jobs.lever.co/acme/1")
    assert v["enlace"] == "https://jobs.lever.co/acme/1" and v["tipo_enlace"] == "original"


def test_crear_calcula_familias_paises_y_etiquetas():
    v = _v(titulo="Senior Product Designer (UX/UI)", descripcion="We need advanced English and 4+ years of experience. "
           "Figma, prototyping and design systems. Remote LATAM.", ubicacion="Latin America", remoto=True)
    assert v["familias"][0] == {"familia": "diseno-producto-ux", "coincidencia": "exacto"}
    assert "VE" in v["paises"] and v["modalidad"] == "remoto"
    assert v["ingles"] == "avanzado" and v["anos_min"] == 4 and v["nivel"] == "senior" and v["idioma"] == "en"
    assert "figma" in [h.lower() for h in v["herramientas"]]
    assert "_descripcion" not in vacante.publica(v)


def test_juntar_copias_del_mismo_aviso():
    linkedin = _v(titulo="Diseñador UX/UI (Medellín)", ubicacion="Medellín, Colombia")
    ats = _v(titulo="Diseñador UX/UI", empresa="ACME", enlace="https://jobs.lever.co/acme/9", fuente="Lever",
             ubicacion="Remote - Mexico", fecha="2026-10-18")
    otra = _v(titulo="Data Analyst", enlace="https://www.linkedin.com/jobs/view/2")
    juntas = vacante.juntar([linkedin, ats, otra])
    assert len(juntas) == 2
    ux = next(v for v in juntas if "UX" in v["titulo"])
    assert ux["enlace"] == "https://www.linkedin.com/jobs/view/1"
    assert ux["enlace_directo"] == "https://jobs.lever.co/acme/9"
    assert set(ux["paises"]) == {"CO", "MX"}
    assert ux["fecha_publicacion"] == "2026-10-18"
    assert ux["fuentes"] == ["Lever", "LinkedIn"]


def test_juntar_misma_descripcion_con_otro_cargo():
    texto = "Buscamos una persona para diseñar flujos, prototipos y pruebas con usuarios en Figma. " * 5
    a = _v(titulo="Diseñador UX", descripcion=texto)
    b = _v(titulo="Diseñador de producto", descripcion=texto, enlace="https://www.linkedin.com/jobs/view/3")
    assert len(vacante.juntar([a, b])) == 1
