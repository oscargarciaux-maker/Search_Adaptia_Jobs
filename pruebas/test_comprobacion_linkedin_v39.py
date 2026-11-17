"""Contrato v39 (17 nov): de 100 vacantes de Product Designer que servían a los clientes, 73 no se entregaron porque
LinkedIn bloqueaba la comprobación de su página (429) e Indeed la de la suya (401). La ficha pública que ya lee la
búsqueda prueba lo mismo con el mismo rigor: título del aviso, descripción y sin «ya no recibe postulaciones»."""
from datetime import datetime, timezone
from types import SimpleNamespace

from buscador import vacante, verificar_enlaces as ve
from buscador.fuentes import linkedin_publico as lp

AHORA = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
URL = "https://www.linkedin.com/jobs/view/4321"


def ficha(titulo="Senior Product Designer", cerrada=False, descripcion=True):
    return ('<section><h2 class="top-card-layout__title font-sans">' + titulo + "</h2>"
            + ('<figcaption class="closed-job__flavor--closed">No longer accepting applications</figcaption>' if cerrada else "")
            + ('<div class="show-more-less-html__markup">We design products...</div>' if descripcion else "")
            + "</section>")


def test_ficha_abierta_cerrada_o_dudosa():
    assert ve.ficha_linkedin(ficha(), "Senior Product Designer") == ("verificada", "ficha de LinkedIn abierta")
    assert ve.ficha_linkedin(ficha(cerrada=True), "Senior Product Designer") == ("rechazada", "vacante cerrada")
    # Un aviso que ya no existe también responde 200, pero sin su título: nunca aprueba.
    assert ve.ficha_linkedin("<html>Otras vacantes</html>", "Senior Product Designer")[0] == "pendiente"
    assert ve.ficha_linkedin(ficha("Data Engineer"), "Senior Product Designer")[0] == "pendiente"
    assert ve.ficha_linkedin(ficha(descripcion=False), "Senior Product Designer")[0] == "pendiente"


class Sesion:
    def __init__(self, http=200, texto=""):
        self.http, self.texto, self.pedidas = http, texto, []

    def get(self, url, **op):
        self.pedidas.append(url)
        return SimpleNamespace(status_code=self.http, text=self.texto)


def test_la_comprobacion_de_linkedin_lee_la_ficha_publica():
    sesion = Sesion(texto=ficha())
    r = ve.comprobar(URL, "Senior Product Designer", sesion=sesion, validar_url=lambda u: True, ahora=AHORA)
    assert sesion.pedidas == [ve.LINKEDIN_FICHA + "4321"] and r["estado"] == "verificada" and r["url"] == URL
    assert ve.comprobar(URL, "X", sesion=Sesion(429), ahora=AHORA)["estado"] == "pendiente"  # bloqueo ≠ cierre
    assert ve.comprobar(URL, "X", sesion=Sesion(404), ahora=AHORA)["estado"] == "rechazada"
    assert ve.aviso_linkedin("https://co.linkedin.com/jobs/view/product-designer-at-acme-98765") == "98765"


def _vacante(enlace=URL, titulo="Senior Product Designer"):
    return vacante.crear(titulo, "Acme", enlace, "LinkedIn", ubicacion="Bogotá", descripcion="x " * 200,
                         hoy="2026-11-17")


def test_las_fichas_leidas_en_la_busqueda_valen_como_comprobacion():
    v = _vacante()
    cache = {}
    leidas = {URL: {"estado": "verificada", "motivo": "ficha de LinkedIn abierta", "comprobada_en": "2026-11-17T11:00:00Z"}}
    assert ve.incorporar([v], cache, leidas) == 1
    assert ve.anotar(v, cache, AHORA)["estado"] == "verificada"
    # Una comprobación más reciente no se pisa con una lectura anterior.
    cache[URL]["comprobada_en"] = "2026-11-17T11:30:00Z"
    assert ve.incorporar([v], cache, leidas) == 0
    cerrada = {URL: {"estado": "rechazada", "motivo": "vacante cerrada", "comprobada_en": "2026-11-17T11:45:00Z"}}
    ve.incorporar([v], cache, cerrada)
    assert ve.anotar(v, cache, AHORA)["estado"] == "rechazada"


def test_la_busqueda_anota_lo_que_dijo_cada_ficha():
    lp.FICHAS.clear()
    lp._anotar_ficha(URL, "Senior Product Designer", ficha())
    lp._anotar_ficha(URL + "9", "Senior Product Designer", ficha(cerrada=True))
    lp._anotar_ficha(URL + "8", "Senior Product Designer", "<html></html>")
    assert lp.FICHAS[URL]["estado"] == "verificada" and lp.FICHAS[URL + "9"]["estado"] == "rechazada"
    assert URL + "8" not in lp.FICHAS  # lo dudoso no se anota: la comprobación normal lo intentará
    lp.FICHAS.clear()


def test_indeed_no_se_pregunta_y_vale_el_enlace_directo():
    v = vacante.crear("Product Designer", "Acme", "https://co.indeed.com/viewjob?jk=abc", "Indeed",
                      ubicacion="Bogotá", descripcion="x " * 200, enlace_directo="https://jobs.lever.co/acme/1",
                      hoy="2026-11-17")
    pedidas = []

    def comprobar(u, titulo, **op):
        pedidas.append(u)
        return {"url": u, "estado": "verificada", "motivo": "ficha específica accesible", "destino": u,
                "comprobada_en": "2026-11-17T12:00:00Z", "http": 200, "saltos": 0, "ruta": [u]}
    ve.auditar([v], {}, comprobar_url=comprobar, ahora=AHORA)
    assert pedidas == ["https://jobs.lever.co/acme/1"] and v["verificacion"]["estado"] == "verificada"


def test_tras_varios_bloqueos_linkedin_descansa(monkeypatch):
    monkeypatch.setattr(ve, "PAUSA_LINKEDIN", 0)
    vs = [_vacante(f"https://www.linkedin.com/jobs/view/{n}") for n in range(10)]
    pedidas = []

    def comprobar(u, titulo, **op):
        pedidas.append(u)
        return {"url": u, "estado": "pendiente", "motivo": "acceso bloqueado o fallo temporal", "destino": u,
                "comprobada_en": "2026-11-17T12:00:00Z", "http": 429, "saltos": 0, "ruta": [u]}
    ve.auditar(vs, {}, comprobar_url=comprobar, ahora=AHORA)
    assert len(pedidas) == ve.BLOQUEOS_LINKEDIN
