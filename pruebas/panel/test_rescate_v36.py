"""Contrato v36 (caso Danna, 17 nov): quien va bajo el mínimo se completa con toda la bodega de la noche —no solo con lo
que entró a algún lote—, comprobando al momento los enlaces que falten. Indeed busca también en EE. UU. y otros países de
los perfiles, y LinkedIn reparte la lectura de fichas entre todos los lugares buscados."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from buscador import familias, vacante
from buscador.fuentes import indeed, linkedin_publico
from panel import ejecutor
from panel.repositorio import configuracion_demo, hoy

TEXTO = ("We are hiring a Product Designer for our product team. You will run user research, design flows in Figma "
         "and work with engineering every day. ") * 3


def _vacante(n, empresa=None, ubicacion="Chicago, IL", verificada=True, titulo="Product Designer"):
    v = vacante.crear(titulo, empresa or f"Empresa {n}", f"https://jobs.lever.co/e/d-{n}", "Lever",
                      ubicacion=ubicacion, descripcion=TEXTO, fecha=hoy(), hoy=hoy(), remoto=None)
    ahora = datetime.now(timezone.utc).isoformat()
    v["verificacion"] = {"estado": "verificada" if verificada else "pendiente",
                         "enlaces": [{"url": v["enlace"], "estado": "verificada" if verificada else "pendiente",
                                      "comprobada_en": ahora if verificada else ""}]}
    v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
    return v


@pytest.fixture
def cfg():
    c = configuracion_demo()
    for p in c["perfiles"][1:]:
        p["activo"] = False
    p = c["perfiles"][0]  # Product Designer: vive en EE. UU. (Chicago), remoto, híbrido o presencial
    p.update(vive_en="US", modalidades=["remoto", "hibrido", "presencial"], ciudades=["Chicago"],
             idiomas=["es", "en"], ingles_maximo="native", ubicaciones=[])
    return c


class Repo:
    """Supabase mínimo: un lote del día vacío (nada de EE. UU. entró al cupo) y una asignación anterior."""
    def __init__(self, recibidas=()):
        self.ejecucion, self.asignaciones, self.recibidas = None, [], list(recibidas)

    def pedir(self, metodo, ruta, **op):
        params = op.get("params") or {}
        if ruta == "panel_ejecuciones":
            if metodo == "GET":
                return [self.ejecucion] if self.ejecucion else []
            if metodo == "POST":
                self.ejecucion = {"id": "e1", **op["json"]}
            if metodo == "PATCH":
                self.ejecucion.update(op["json"])
        elif ruta == "panel_asignaciones":
            if metodo == "GET":
                return self.recibidas if not params.get("offset") else []
            self.asignaciones.extend(op["json"])
        return []


def test_danna_se_completa_con_la_bodega_aunque_nada_entrara_al_lote(cfg):
    p = cfg["perfiles"][0]
    bodega = [_vacante(1), _vacante(2), _vacante(3, empresa="Acme"), _vacante(4, empresa="Acme"),
              _vacante(5, empresa="Acme"), _vacante(6, verificada=False),
              _vacante(7, ubicacion="Bogotá, Colombia"),  # presencial en otro país: no le sirve
              _vacante(8)]
    repo = Repo(recibidas=[{"perfil_id": p["id"], "vacante_id": bodega[-1]["id"]}])  # la 8 ya la recibió
    comprobadas, subidas = [], []

    def comprobar(url, titulo, ahora=None, **_):  # como el real: la comprobación lleva la hora de la ronda
        comprobadas.append(url)
        return {"url": url, "destino": url, "estado": "verificada", "motivo": "ficha vigente",
                "comprobada_en": ahora.isoformat(), "http": 200, "saltos": 0, "ruta": []}
    original = ejecutor._rescatar

    def rescatar(*a, **k):
        return original(*a, **{**k, "comprobar": comprobar, "subir": subidas.extend})
    ejecutor._rescatar = rescatar
    try:
        ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy(), vacantes=bodega, cache_enlaces={})
    finally:
        ejecutor._rescatar = original
    ids = [a["vacante_id"] for a in repo.asignaciones if a["perfil_id"] == p["id"]]
    assert len(ids) == 5  # completa el mínimo con la bodega
    assert bodega[7]["id"] not in ids and bodega[6]["id"] not in ids  # ya recibida / otro país
    assert sum(i in ids for i in (bodega[2]["id"], bodega[3]["id"], bodega[4]["id"])) == 2  # máximo 2 por empresa
    assert bodega[5]["id"] in ids and comprobadas == [bodega[5]["enlace"]]  # su enlace se comprobó al momento
    assert [f["id"] for f in subidas] == [bodega[5]["id"]]  # y la comprobación quedó en el catálogo
    assert all({"rescatada": "bodega"} in a["explicacion"] for a in repo.asignaciones)
    assert repo.ejecucion["resumen"]["rescatadas"] == 5


def test_sin_bodega_el_registro_sigue_como_antes(cfg):
    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    assert repo.asignaciones == [] and repo.ejecucion["resumen"]["rescatadas"] == 0


def test_indeed_busca_en_estados_unidos_y_completa_la_ubicacion():
    llamadas = []

    def scrape(**k):
        llamadas.append(k["country_indeed"])
        return pd.DataFrame([{"title": "Product Designer", "company": "Acme", "location": "Remote",
                              "description": TEXTO, "date_posted": hoy(), "job_url": "https://www.indeed.com/viewjob?jk=1",
                              "job_url_direct": "", "is_remote": True}])
    mapa = [{"id": "cargo:x", "consultas": ["Product Designer"], "paises_objetivo": ["US"]}]
    crudas, stats = indeed.buscar(mapa, ["CO"], {}, 4, scrape=scrape)
    assert set(llamadas) == {"usa"} and crudas[0]["ubicacion"] == "Remote, United States"
    assert indeed.ubicacion("Chicago, IL", "US") == "Chicago, IL" and indeed.ubicacion("Remoto", "CO") == "Remoto"


def test_preparar_busca_en_el_pais_de_quien_trabaja_en_remoto(cfg):
    cfg["perfiles"][0].update(modalidades=["remoto"], ciudades=[])
    mapa, _, _ = ejecutor.preparar({"revision": 1, "configuracion": cfg}, hoy())
    assert "US" in mapa[0]["paises_objetivo"]


class _R:
    def __init__(self, texto, codigo=200):
        self.text, self.status_code = texto, codigo


def test_linkedin_reparte_las_fichas_entre_todos_los_lugares():
    def tarjetas(n, lugar):
        return "".join(f'<li><div data-entity-urn="urn:li:jobPosting:{lugar}{i}"><h3 class="base-search-card__title">'
                       f'Product Designer</h3><h4 class="base-search-card__subtitle">E{i}</h4>'
                       f'<span class="job-search-card__location">X</span></div></li>' for i in range(n))

    class Cliente:
        def __init__(self):
            self.fichas = []

        def get(self, url, params=None):
            if "jobPosting/" in url:
                self.fichas.append(url.rsplit("/", 1)[1])
                return _R('<div class="show-more-less-html__markup">' + TEXTO + "</div>")
            return _R(tarjetas(10 if params["location"] == "Latin America" else 3,
                               "1" if params["location"] == "Latin America" else "2"))
    mapa = [{"id": "f", "consultas": ["Product Designer"],
             "lugares": [("REMOTO", {"location": "Latin America", "f_WT": "2"}), ("CIUDAD_CHICAGO", {"location": "Chicago"})]}]
    cliente = Cliente()
    linkedin_publico.buscar(cliente, mapa, [], {}, 10, max_fichas=6, max_paginas=1)
    assert sum(f.startswith("2") for f in cliente.fichas) == 3  # Chicago recibe sus fichas aunque haya 10 remotas
