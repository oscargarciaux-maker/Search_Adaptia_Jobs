"""Contrato v44: Hireline y Magneto (portales en español) sin red, con un sitemap y fichas recortadas como las reales."""
import json

from buscador.fuentes import sitemaps_empleo as se

HOY = "2026-11-18"
SITEMAP_HL = """<?xml version="1.0" encoding="UTF-8"?><urlset>
<url><loc>https://hireline.io/mx/empleos/disenador-ux-ui-remoto/115001</loc><lastmod>2026-11-15</lastmod></url>
<url><loc>https://hireline.io/mx/empleos/ejecutivo-de-servicios/106436</loc><lastmod>2026-11-15</lastmod></url>
<url><loc>https://hireline.io/mx/empleos/product-designer-sr/90001</loc><lastmod>2026-09-01</lastmod></url>
<url><loc>https://hireline.io/mx/empleos/desarrollador-frontend-react-hibrido/115002</loc></url>
</urlset>"""


def _ficha(titulo="Diseñador UX/UI (Remoto)", remota=True, hasta="2026-12-01", pais="México"):
    posting = {"@context": "https://schema.org/", "@type": "JobPosting", "title": titulo,
               "description": "<p>Diseña productos digitales para equipos de LATAM.</p>" * 3,
               "datePosted": "2026-11-14", "validThrough": hasta,
               "hiringOrganization": {"@type": "Organization", "name": "Empresa MX"},
               "jobLocation": {"@type": "Place", "address": {"addressLocality": ["Monterrey"], "addressCountry": "MX"}},
               "applicantLocationRequirements": [{"@type": "Country", "name": pais}],
               "baseSalary": {"currency": "MXN", "value": {"minValue": "45000", "maxValue": "50000",
                                                           "unitText": "MONTH"}}}
    if remota:
        posting["jobLocationType"] = "TELECOMMUTE"
    return '<script type="application/ld+json">' + json.dumps(posting) + "</script>"


class Respuesta:
    def __init__(self, texto, codigo=200):
        self.text, self.status_code = texto, codigo


class Cliente:
    def __init__(self, paginas):
        self.paginas, self.pedidas = paginas, []

    def get(self, url):
        self.pedidas.append(url)
        return Respuesta(self.paginas[url]) if url in self.paginas else Respuesta("", 404)


MAPA = [{"id": "cargo:pd", "consultas": ["Product Designer"], "exactos": ["Product Designer"], "similares": [],
         "consultas_es": ["Diseñador UX/UI", "Diseñador de Producto"]},
        {"id": "cargo:fe", "consultas": ["Frontend Developer"], "exactos": ["Desarrollador Frontend"], "similares": []}]


def test_del_sitemap_solo_las_recientes_que_nombran_un_cargo():
    c = se.candidatos(se.entradas(SITEMAP_HL), MAPA, HOY, "/empleos/")
    assert c == [("https://hireline.io/mx/empleos/disenador-ux-ui-remoto/115001", "cargo:pd"),
                 ("https://hireline.io/mx/empleos/desarrollador-frontend-react-hibrido/115002", "cargo:fe")]
    # «product-designer-sr» es de septiembre (más de 30 días) y «ejecutivo de servicios» no es un cargo buscado.


def test_titulo_de_la_direccion_en_los_dos_formatos():
    assert se.titulo_de_enlace("https://hireline.io/mx/empleos/disenador-ux-ui-remoto/115001") == "disenador ux ui remoto"
    assert se.titulo_de_enlace("https://www.magneto365.com/co/empleos/disenador-ux-medellin-1121716") == \
        "disenador ux medellin"


def test_ficha_remota_dice_desde_donde_se_postula_y_no_inventa():
    d = se.ficha(_ficha(), HOY, "MX")
    assert d["ubicacion"] == "México (Remoto)" and d["remoto"] is True and d["empresa"] == "Empresa MX"
    assert d["fecha"] == "2026-11-14" and not d["cerrada"] and "MXN" in d["descripcion"]
    presencial = se.ficha(_ficha("Desarrollador Frontend (Híbrido)", remota=False), HOY, "MX")
    assert presencial["ubicacion"] == "Monterrey, México (Híbrido)" and presencial["remoto"] is None
    assert se.ficha(_ficha(hasta="2026-11-01"), HOY, "MX")["cerrada"] is True
    assert se.ficha("<html>sin datos</html>", HOY, "MX") is None
    # Hireline escribe el país con su nombre («MÉXICO»), Magneto con su código («CO»).
    nombre = _ficha("Desarrollador Frontend", remota=False).replace('"addressCountry": "MX"', '"addressCountry": "M\\u00c9XICO"')
    assert se.ficha(nombre, HOY, "MX")["ubicacion"] == "Monterrey, México"


def test_buscar_lee_sitemap_y_fichas_con_presupuesto_y_quita_cerradas():
    paginas = {"https://hireline.io/mx/sitemap_ofertas.xml": SITEMAP_HL,
               "https://hireline.io/mx/empleos/disenador-ux-ui-remoto/115001": _ficha(),
               "https://hireline.io/mx/empleos/desarrollador-frontend-react-hibrido/115002":
                   _ficha("Desarrollador Frontend", remota=False, hasta="2026-11-01")}
    cli = Cliente(paginas)
    crudas, stats = se.buscar(cli, "Hireline", MAPA, hoy=HOY, max_fichas=10)
    assert [v["titulo"] for v in crudas] == ["Diseñador UX/UI (Remoto)"] and crudas[0]["fuente"] == "Hireline"
    assert stats["cerradas"] == 1 and stats["candidatas"] == 2
    assert stats["sitemaps_fallidos"] == 1  # el sitemap de Colombia no está en la prueba: no detiene nada
    assert not any("?k=" in u or "/api/" in u for u in cli.pedidas)  # robots.txt: ni búsqueda ni API
    crudas, _ = se.buscar(Cliente(paginas), "Hireline", MAPA, hoy=HOY, max_fichas=1)
    assert len(crudas) == 1


def test_los_dos_sitios_son_portales_donde_se_postula():
    from buscador import enlaces
    assert enlaces.sirve("https://hireline.io/mx/empleos/disenador-ux-ui-remoto/115001")
    assert enlaces.sirve("https://www.magneto365.com/co/empleos/disenador-ux-1121716")


# ── RemotosLatam y WeRemoto: solo empresas (portales), nunca sus avisos ─────────────────────────────────────────────
PAGINA_TABLERO = """<a href="https://job-boards.greenhouse.io/platacard/jobs/123">Diseñador</a>
<a href="https://boards.greenhouse.io/embed/job_app?for=x">x</a>
<a href="https://apply.workable.com/j/ABC123">j</a>
<a href="https://apply.workable.com/remote-talent-latam/j/0B7D/apply/?utm_source=weremoto.com">w</a>
<a href="https://jobs.lever.co/superside/abc">l</a>
<a href="https://jobs.ashbyhq.com/wistia/xyz">a</a>
<a href="https://remotoslatam.com/empleo/disenador-ux-123">aviso del tablero</a>"""


def test_tableros_solo_aportan_portales_de_empresas():
    from buscador.fuentes import tableros_latam as tl
    assert tl.portales(PAGINA_TABLERO) == {("greenhouse", "platacard"), ("workable", "remote-talent-latam"),
                                            ("lever", "superside"), ("ashby", "wistia")}

    class Cli:
        def __init__(self):
            self.pedidas = []

        def get(self, url):
            self.pedidas.append(url)
            return Respuesta(PAGINA_TABLERO) if "remotoslatam" in url else Respuesta("", 503)
    cli = Cli()
    filas, stats = tl.tableros(cli, HOY)
    assert {(f["sistema"], f["slug"]) for f in filas} == tl.portales(PAGINA_TABLERO)
    assert all(f["origen"] == "RemotosLatam" for f in filas)
    assert stats["WeRemoto"]["fallidas"] == len(tl.PAGINAS["WeRemoto"])  # si no responde, no detiene nada
    assert not any("?" in u or "/api/" in u for u in cli.pedidas)  # robots.txt: sin parámetros ni API


# ── Cualquier país (decisión de Oscar): toda persona tiene dónde buscarse, también si solo habla español ────────────
def test_todo_pais_del_mundo_tiene_al_menos_tres_fuentes_y_los_hispanohablantes_mas():
    from buscador import paises
    from panel.ejecutor import fuentes_en
    for p in paises.mundo()["lista"]:
        f = fuentes_en(p["codigo"])
        assert {"LinkedIn", "Portales de empresas", "Get on Board (remotas)"} <= set(f), p["codigo"]
    hispanos = ["AR", "BO", "CL", "CO", "CR", "CU", "DO", "EC", "ES", "GT", "HN", "MX", "NI", "PA", "PE", "PR", "PY",
                "SV", "UY", "VE", "US"]
    for c in hispanos:
        assert len(fuentes_en(c)) >= 4 or c == "CU", (c, fuentes_en(c))  # Cuba: sin Indeed ni portales locales
    assert {"Computrabajo", "Elempleo", "Magneto", "Hireline"} <= set(fuentes_en("CO"))
