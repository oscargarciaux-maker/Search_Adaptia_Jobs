"""Contrato v42 (18 nov, aprobado por Oscar): 1.333 vacantes de portales de empresas con solo 57 comprobadas. Lo que el
portal de la propia empresa listó hoy cuenta como abierto 24 h; Computrabajo y Get on Board siguen comprobándose."""
from datetime import datetime, timezone

from buscador import vacante, verificar_enlaces as ve

AHORA = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)


def _v(enlace, titulo="Product Designer", fuente="Portales de empresas (greenhouse)", directo=""):
    return vacante.crear(titulo, "Acme " + enlace[-3:], enlace, fuente, ubicacion="Remote",
                         descripcion="Design " * 60, enlace_directo=directo, hoy="2026-11-18")


def test_listado_hoy_en_el_portal_de_la_empresa_cuenta_como_comprobado():
    url = "https://boards.greenhouse.io/acme/jobs/123"
    v = _v(url)
    cache = {}
    assert ve.incorporar([v], cache, ve.vistas_en_portales({url}, AHORA)) == 1
    r = ve.anotar(v, cache, AHORA)
    assert r["estado"] == "verificada" and r["url_utilizable"] == url
    assert cache[url]["motivo"] == "vista hoy en el portal de la empresa"
    # Un aviso del mismo portal que hoy no apareció en su listado sigue sin comprobar.
    otra = _v("https://boards.greenhouse.io/acme/jobs/999")
    assert ve.anotar(otra, cache, AHORA)["estado"] == "pendiente"


def test_vacante_de_linkedin_con_enlace_directo_del_portal_queda_comprobada():
    linkedin, directo = "https://www.linkedin.com/jobs/view/4300000001", "https://jobs.lever.co/acme/abc"
    v = _v(linkedin, fuente="LinkedIn", directo=directo)
    cache = {}
    ve.incorporar([v], cache, ve.vistas_en_portales({directo}, AHORA))
    r = ve.anotar(v, cache, AHORA)
    assert r["estado"] == "verificada" and r["url_utilizable"] == directo
    assert linkedin not in cache  # LinkedIn conserva su propia comprobación (v39)


def test_no_se_marca_linkedin_indeed_ni_agregadores():
    vistas = ve.vistas_en_portales({"https://www.linkedin.com/jobs/view/1", "https://co.indeed.com/viewjob?jk=1",
                                    "https://jooble.org/desc/1", "", "https://jobs.ashbyhq.com/acme/1"}, AHORA)
    assert list(vistas) == ["https://jobs.ashbyhq.com/acme/1"]


def test_la_comprobacion_vence_a_las_24_horas():
    url = "https://apply.workable.com/acme/j/ABC123"
    v = _v(url)
    cache = {}
    ve.incorporar([v], cache, ve.vistas_en_portales({url}, AHORA))
    despues = datetime(2026, 11, 19, 13, tzinfo=timezone.utc)
    assert ve.anotar(v, cache, despues)["estado"] == "pendiente"


def test_lo_ya_comprobado_no_se_vuelve_a_pedir_y_el_turno_queda_para_otros_sitios():
    url = "https://jobs.lever.co/acme/def"
    v = _v(url)
    cache = {}
    ve.incorporar([v], cache, ve.vistas_en_portales({url}, AHORA))
    pedidas = []

    def comprobar(u, titulo):
        pedidas.append(u)
        return {"url": u, "estado": "verificada", "motivo": "ok", "comprobada_en": AHORA.isoformat(), "http": 200,
                "saltos": 0, "ruta": [u], "destino": u}

    ct = _v("https://co.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-disenador-ABC", fuente="Computrabajo")
    ve.auditar([v, ct], cache, maximo=5, segundos=5, hilos=1, comprobar_url=comprobar, ahora=AHORA)
    assert url not in pedidas
