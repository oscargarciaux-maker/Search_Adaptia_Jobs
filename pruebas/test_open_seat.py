"""Open Seat (17 nov, sugerida por Oscar): su lista pública de empresas que contratan en LATAM se suma a los portales que
lee ats.py; sus avisos no se toman (solo traen un resumen corto)."""
from buscador.fuentes import open_seat


class Cliente:
    def __init__(self, datos):
        self.datos, self.pedidas = datos, []

    def json(self, url, **k):
        self.pedidas.append(url)
        return self.datos


def test_toma_solo_sistemas_que_sabemos_leer_y_slugs_seguros():
    datos = {"companies": [
        {"ats": "greenhouse", "slug": "homeward", "name": "Homeward"},
        {"ats": "Lever", "slug": "acme-latam", "name": "Acme"},
        {"ats": "bamboohr", "slug": "otra", "name": "Otra"},           # no sabemos leer BambooHR
        {"ats": "ashby", "slug": "../../evil", "name": "Mala"},        # el slug va dentro de una dirección web
        {"ats": "workable", "slug": "x y", "name": "Con espacio"},
        {"ats": "greenhouse", "slug": "Homeward", "name": "Repetida"},
        "no es un objeto"]}
    cliente = Cliente(datos)
    filas, stats = open_seat.tableros(cliente, "2026-11-17")
    assert cliente.pedidas == [open_seat.URL_EMPRESAS]
    assert [(f["sistema"], f["slug"], f["origen"]) for f in filas] == [("greenhouse", "homeward", "Open Seat"),
                                                                       ("lever", "acme-latam", "Open Seat")]
    assert stats == {"empresas": 7, "portales": 2, "omitidas": 3}


def test_si_la_lista_no_se_puede_leer_la_busqueda_sigue():
    assert open_seat.tableros(Cliente(None), "2026-11-17")[0] == []
    assert open_seat.tableros(Cliente({"otra": 1}), "2026-11-17")[0] == []
