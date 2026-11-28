"""Computrabajo: lectura sin red de la búsqueda y la ficha, fechas sin confundir actualización con publicación."""
from buscador import bodega
from buscador.fuentes import computrabajo as ct

LISTADO = """
<article class="box_offer sel " data-id='0657B70A7568A0EE61373E686DCF3405' data-lc="x">
 <h2 class="fs18 fwB prB"> <a class="js-o-link fc_base" href="/ofertas-de-trabajo/oferta-de-trabajo-de-disenador-ux-ui-en-bogota-0657B70A7568A0EE61373E686DCF3405#lc=x"> Dise&#xF1;ador(a) UX/UI Senior </a></h2>
 <p class="dFlex vm_fx fs16 fc_base mt5"> <a class="fc_base t_ellipsis" href="https://co.computrabajo.com/empresas/x" offer-grid-article-company-url> Empresa Ejemplo S.A.S </a> </p>
 <p class="fs16 fc_base mt5"> <span class="mr10"> Bogot&#xE1;, D.C., Bogot&#xE1;, D.C. </span> </p>
 <div class="fs13 mt15"> <span class="dIB mr10"> <span class="icon i_home_office"></span> Presencial y remoto </span> </div>
 <p class="fs13 fc_aux mt15"> Hace 2 d&#xED;as </p>
</article>
<article class="box_offer " data-id='AA11BB22CC33DD44EE55FF6600112233' data-lc="y">
 <h2 class="fs18 fwB prB"> <a class="js-o-link fc_base" href="/ofertas-de-trabajo/oferta-de-trabajo-de-product-designer-remoto-AA11BB22CC33DD44EE55FF6600112233"> Product Designer </a></h2>
 <p class="dFlex vm_fx fs16 fc_base mt5"> <a class="fc_base" offer-grid-article-company-url> Otra Empresa </a> </p>
 <p class="fs16 fc_base mt5"> <span class="mr10"> Medell&#xED;n, Antioquia </span> </p>
 <div class="fs13 mt15"> <span class="dIB mr10"> <span class="icon i_home_office"></span> Remoto </span> </div>
</article>
"""
TEXTO = ("Buscamos diseñador de producto con experiencia en investigación de usuarios, prototipos y sistemas de diseño. "
         "Trabajarás con equipos de ingeniería y producto en una plataforma digital. ") * 3
FICHA = f"""<div class="mb40 pb40 bb1"><h2 class="fwB fs18 mb20">Descripción de la oferta</h2>
<div class="mbB"><span class="tag base mb10">Remoto</span></div><p class="mbB">{TEXTO}<br />Requisitos: 3 años.</p>
<p class="fc_aux fs13 mbB mtB">Palabras clave: ux</p><p class="fc_aux fs13">Hace 3 d&#xED;as</p></div>"""


def test_tarjetas_de_busqueda():
    filas = ct.tarjetas(LISTADO, "co")
    assert [f["id"] for f in filas] == ["0657B70A7568A0EE61373E686DCF3405", "AA11BB22CC33DD44EE55FF6600112233"]
    assert filas[0]["titulo"] == "Diseñador(a) UX/UI Senior" and filas[0]["empresa"] == "Empresa Ejemplo S.A.S"
    assert filas[0]["ciudad"] == "Bogotá, D.C., Bogotá, D.C." and filas[0]["modalidad"] == "Presencial y remoto"
    assert filas[0]["enlace"].startswith("https://co.computrabajo.com/ofertas-de-trabajo/") and "#" not in filas[0]["enlace"]


def test_ficha_fecha_y_cierre():
    descripcion, fecha, cerrada = ct.ficha(FICHA, "2026-11-12")
    assert "investigación de usuarios" in descripcion and "Palabras clave" not in descripcion
    assert fecha == "2026-11-09" and not cerrada
    _, fecha, _ = ct.ficha(FICHA.replace("Hace 3 d&#xED;as", "Hace 2 d&#xED;as (actualizada)"), "2026-11-12")
    assert fecha == ""  # una actualización no es la fecha de publicación
    con_datos = FICHA.replace("Hace 3 d&#xED;as", "Hace 1 d&#xED;a (actualizada)") + \
        '<script type="application/ld+json">{"@type": "JobPosting", "datePosted": "2026-11-05"}</script>'
    assert ct.ficha(con_datos, "2026-11-12")[1] == "2026-11-05"  # la publicación real, no la actualización
    assert ct.ficha("<p>Esta oferta ya no está disponible</p>", "2026-11-12")[2]


def test_fechas_relativas_y_modalidad():
    assert [ct.fecha_relativa(t, "2026-11-12") for t in ("Hace 5 horas", "Ayer", "Hace 1 mes", "Publicada")] == \
        ["2026-11-12", "2026-11-11", "2026-10-13", ""]
    assert ct.modalidad("Presencial y remoto") == (None, " (Híbrido)")
    assert ct.modalidad("Remoto") == (True, " (Remoto)") and ct.modalidad("") == (None, "")
    assert ct.slug("Diseñador UX/UI") == "disenador-ux-ui"


class Respuesta:
    def __init__(self, texto, codigo=200):
        self.text, self.status_code = texto, codigo


class Cliente:
    def __init__(self):
        self.pedidas = []

    def get(self, url, params=None):
        self.pedidas.append(url)
        return Respuesta(LISTADO if "/trabajo-de-" in url else FICHA)


def test_busqueda_completa_y_vacantes_utilizables():
    mapa = [{"id": "diseno-producto-ux", "consultas": ["Product Designer"], "exactos": [], "similares": [], "cercanos": []}]
    cliente, estado = Cliente(), {}
    crudas, stats = ct.buscar(cliente, mapa, [("CO", "Colombia"), ("ES", "España")], estado, 5, hoy="2026-11-12")
    assert stats["busquedas"] == 1 and stats["avisos"] == 2 and stats["con_descripcion"] == 2  # España no tiene sitio
    assert cliente.pedidas[0] == "https://co.computrabajo.com/trabajo-de-product-designer"
    assert not any("?" in u and "p=" not in u for u in cliente.pedidas)  # sin filtros bloqueados por robots.txt
    assert crudas[0]["ubicacion"] == "Bogotá, D.C., Bogotá, D.C., Colombia (Híbrido)" and crudas[1]["remoto"] is True
    assert estado["diseno-producto-ux@CO"] == "2026-11-12"
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-12", 30, set(), set())
    v = next(x for x in vacantes if x["empresa"] == "Otra Empresa")
    assert v["paises"] == ["CO"] and v["modalidad"] == "remoto" and v["fuente"] == "Computrabajo"
    assert v["fecha_publicacion"] == "2026-11-09" and v["idioma"] == "es"


def test_bloqueos_seguidos_detienen_la_fuente():
    class Bloqueado:
        def __init__(self):
            self.n = 0

        def get(self, url, params=None):
            self.n += 1
            return Respuesta("", 403)
    mapa = [{"id": f"f{i}", "consultas": ["QA"], "exactos": [], "similares": [], "cercanos": []} for i in range(10)]
    cliente = Bloqueado()
    _, stats = ct.buscar(cliente, mapa, [("CO", "Colombia")], {}, 50, hoy="2026-11-12")
    assert cliente.n == 4 and stats["fallidas"] == 4


# ── P-17.1: remotas por cargo (`/trabajo-de-<cargo>-en-remoto`) ─────────────────────────────────────────────────────
# Respuesta guardada (recortada) de la búsqueda remota: el remoto completo lleva el icono `i_home`, no `i_home_office`.
LISTADO_REMOTO = """
<article class="box_offer sel " data-id='2E462883CC17D6DE61373E686DCF3405' data-blind="false" data-lc="ListOffers-Score4-0">
    <h2 class="fs18 fwB prB">
        <a class="js-o-link fc_base" href="/ofertas-de-trabajo/oferta-de-trabajo-de-desarrollador-java-en-bogota-dc-2E462883CC17D6DE61373E686DCF3405#lc=ListOffers-Score4-0">
            Desarrollador/a Java Jr
        </a>
    </h2>
    <p class="dFlex vm_fx fs16 fc_base mt5">
            <a class="fc_base t_ellipsis" href="https://co.computrabajo.com/empresas/x" target='_blank' offer-grid-article-company-url>
                Empresa Remota SAS
            </a>
    </p>
    <p class="fs16 fc_base mt5">
        <span class="mr10">
            Bogot&#xE1;, D.C., Bogot&#xE1;, D.C.
        </span>
    </p>
        <div class="fs13 mt15">
                <span class="dIB mr10">
                    <span class="icon i_home"></span>
                    Remoto
                </span>
        </div>
    <p class="fs13 fc_aux mt15">
        Hace  22  horas
    </p>
</article>
<article class="box_offer " data-id='BB11BB22CC33DD44EE55FF6600112233' data-lc="y">
 <h2 class="fs18 fwB prB"> <a class="js-o-link fc_base" href="/ofertas-de-trabajo/oferta-de-trabajo-de-desarrollador-BB11BB22CC33DD44EE55FF6600112233"> Desarrollador Backend </a></h2>
 <p class="dFlex vm_fx fs16 fc_base mt5"> <a class="fc_base" offer-grid-article-company-url> Sin Icono SAS </a> </p>
 <p class="fs16 fc_base mt5"> <span class="mr10"> Cali, Valle del Cauca </span> </p>
</article>
"""


def _familia(**extra):
    return dict({"id": "cargo:dev", "consultas": ["Desarrollador"], "exactos": [], "similares": [], "cercanos": [],
                 "paises_objetivo": ["CO", "MX"]}, **extra)


def test_tarjeta_remota_con_icono_i_home():
    filas = ct.tarjetas(LISTADO_REMOTO, "co")
    assert [f["modalidad"] for f in filas] == ["Remoto", ""]
    assert filas[0]["titulo"] == "Desarrollador/a Java Jr" and filas[0]["empresa"] == "Empresa Remota SAS"


def test_turno_remoto_solo_donde_alguien_acepta_remoto():
    # Lugares del panel: remoto en CO; en MX solo presencial (sin «REMOTO_MX»). Las regiones no cuentan como país.
    f = _familia(lugares=[["REMOTO_CO", {}], ["MX", {}], ["REMOTO_REGION_EUROPA", {}], ["REMOTO_MUNDO", {}]])
    assert [c[2] for c in ct.combinaciones([f], {})] == ["CO", "CO:REMOTO", "MX"]
    # Sin lugares (modo heredado) no cambia nada.
    assert [c[2] for c in ct.combinaciones([_familia()], {})] == ["CO", "MX"]


def test_turno_remoto_en_espanol():
    f = _familia(consultas_es=["Desarrollador de software"], paises_es=["CO", "MX"],
                 lugares=[("REMOTO_CO", {}), ("REMOTO_MX", {})], lugares_es=[("REMOTO_CO", {}), ("MX", {})])
    lugares = [c[2] for c in ct.combinaciones([f], {})]
    assert lugares == ["CO", "CO:ES", "CO:REMOTO", "CO:ES:REMOTO", "MX", "MX:ES", "MX:REMOTO"]
    solo_es = _familia(consultas=["Desarrollador de software"], consultas_es=["Desarrollador de software"],
                       paises_es=[], lugares=[("REMOTO_CO", {})])
    assert [c[2] for c in ct.combinaciones([solo_es], {})] == ["CO", "CO:REMOTO", "MX"]


def test_busqueda_remota_pide_la_ruta_en_remoto_y_marca_remoto():
    class ClienteRemoto(Cliente):
        def get(self, url, params=None):
            self.pedidas.append(url)
            if "/trabajo-de-" in url:
                return Respuesta(LISTADO_REMOTO if "-en-remoto" in url else "")
            return Respuesta(FICHA)

    f = _familia(paises_objetivo=["CO"], lugares=[("REMOTO_CO", {})])
    cliente, estado = ClienteRemoto(), {"cargo:dev@CO": "2026-11-11"}  # el turno general ya se buscó ayer
    crudas, stats = ct.buscar(cliente, [f], [("CO", "Colombia")], estado, 1, hoy="2026-11-12")
    assert cliente.pedidas[0] == "https://co.computrabajo.com/trabajo-de-desarrollador-en-remoto"
    assert stats["busquedas"] == 1 and stats["busquedas_remoto"] == 1 and stats["avisos_remoto"] == 2  # tope respetado
    assert estado["cargo:dev@CO:REMOTO"] == "2026-11-12"
    assert all(c["remoto"] is True and c["ubicacion"].endswith("Colombia (Remoto)") for c in crudas)
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-12", 30, set(), set())
    assert {v["modalidad"] for v in vacantes} == {"remoto"} and all(v["paises"] == ["CO"] for v in vacantes)
