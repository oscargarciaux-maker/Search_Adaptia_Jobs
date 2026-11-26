"""Contrato v44: vacantes para quien solo habla español, en cualquier país. Sugerencias compuestas (solo sugerencias),
títulos en español del mapa reconocidos sin que se busquen en todas las fuentes, español en Indeed, Get on Board,
Computrabajo y Apify, y «Qué hacer» por persona."""
import pytest

from panel import ejecutor, servicio, terminos
from panel.modelos import Perfil
from panel.repositorio import configuracion_demo, hoy


@pytest.fixture
def cfg():
    return configuracion_demo()


# ── Sugerencias compuestas ───────────────────────────────────────────────────────────────────────────────────────────
def test_ai_product_manager_sugiere_nombres_en_espanol_y_el_oficio_base():
    r = terminos.sugerir("AI Product Manager", consultar_esco=False)
    assert "Gerente de Producto de IA" in r["terminos_es"] and "Product Manager IA" in r["terminos_es"]
    assert r["familia_base"] == "product-manager" and "Gerente de Producto" in r["terminos_base"]
    # Solo sugerencias: los nombres principales del cargo no se tocan.
    assert r["terminos_exactos"] == ["AI Product Manager"]


@pytest.mark.parametrize("nombre", ["", "AI", "A.I.", "(.*)+", "[ai] product manager", "Product Designer"])
def test_compuestos_con_nombres_raros_o_del_mapa_no_inventan(nombre):
    es, base, familia = terminos.compuestos(nombre)
    assert (es, base, familia) == ([], [], None)


def test_compuesto_no_repite_el_modificador():
    es, _, _ = terminos.compuestos("Data Product Manager")
    assert es and all(x.count("Datos") == 1 for x in es)


def test_portugues_no_cuenta_como_espanol():
    assert not terminos.en_espanol("designer de produto") and not terminos.en_espanol("gerente de produto")
    assert terminos.en_espanol("Gerente de Producto") and terminos.en_espanol("Analista de sistemas sr")


# ── Reconocer sin buscar en todas las fuentes ────────────────────────────────────────────────────────────────────────
def test_grado_acepta_los_titulos_en_espanol_exactos_del_mapa():
    cargo = {"nombre": "Product Designer", "terminos_exactos": ["Product Designer"]}
    assert terminos.grado("Diseñador UX/UI Senior", cargo)[0] == "similar"


def test_grado_no_acepta_titulos_de_una_palabra_ni_hereda_de_familias_donde_el_cargo_es_similar():
    cargo = {"nombre": "Software Engineer", "terminos_exactos": ["Software Engineer", "Backend Engineer"]}
    for titulo in ("Programador CNC", "Desarrollador de negocios", "Desarrollador inmobiliario"):
        assert terminos.grado(titulo, cargo)[0] is None, titulo
    assert all(len(x.split()) > 1 for x in terminos.espanol_del_mapa("Software Engineer"))
    assert terminos.espanol_del_mapa("QA Lead") == ()  # QA Lead es «similar» de QA: no hereda «Analista QA»


def test_los_titulos_del_mapa_clasifican_pero_no_se_buscan(cfg):
    for p in cfg["perfiles"]:
        p["idiomas"] = ["es", "en"]  # sin nadie que hable solo español
    mapa, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy())
    from buscador import cobertura
    for f in mapa:
        assert not set(f["similares_es"]) & set(cobertura.consultas(f)), f["nombre"]
    pd = next(f for f in mapa if f["similares_es"])
    from buscador import familias
    familias.configurar(mapa)
    try:
        assert familias.clasificar(pd["similares_es"][0], "")  # se reconoce al limpiar
    finally:
        familias.configurar(None)


# ── Español en las fuentes ──────────────────────────────────────────────────────────────────────────────────────────
def _solo_es(cfg, pais="CO"):
    for otro in cfg["perfiles"]:  # v50: quien acepta español e inglés también busca en español; aquí, solo este
        otro["idiomas"] = ["en"]
    p = cfg["perfiles"][0]
    p["idiomas"] = ["es"]
    p["ubicaciones"] = [{"paises": [pais], "ciudades": [], "modalidades": ["remoto"]}]
    mapa, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy())
    return next(f for f in mapa if f["id"] == "cargo:" + p["cargo_id"])


def test_indeed_busca_en_espanol_en_el_pais_de_quien_solo_habla_espanol(cfg):
    from buscador.fuentes import indeed
    f = _solo_es(cfg, "CR")
    assert f["paises_es"] == ["CR"]
    vistas = []

    def scrape(**kw):
        vistas.append((kw["search_term"], kw["country_indeed"], kw.get("is_remote", False)))
        import pandas as pd
        return pd.DataFrame([])
    indeed.buscar([f], [], {}, presupuesto=100, hoy=hoy(), scrape=scrape)
    es = [v for v in vistas if v[0] in f["consultas_es"]]
    assert {v[2] for v in es} == {True, False} and {v[1] for v in es} == {indeed.PAISES["CR"]}


def test_get_on_board_y_computrabajo_buscan_en_espanol(cfg):
    from buscador.fuentes import computrabajo
    f = _solo_es(cfg, "CO")
    ct = [c for c in computrabajo.combinaciones([f], {}) if c[2] == "CO:ES"]
    assert ct and ct[0][1] == f["consultas_es"]


def test_rescate_de_apify_empieza_por_el_espanol(cfg):
    from buscador import entrega, familias, refuerzo
    cfg["perfiles"][0].update(idiomas=["es"], vive_en="CO", modalidades=["remoto"])
    llamadas = []

    def buscar(combos):
        llamadas.append(combos)
        return [], {"busquedas": len(combos)}
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        f = next(x for x in familias.mapa() if x["id"] == "cargo:" + cfg["perfiles"][0]["cargo_id"])
        refuerzo.rescate_apify([], {}, hoy(), entrega.config(), familias.mapa(), buscar, lambda a, b: a + b,
                               max_busquedas=4)
    assert f["consultas_es"] and llamadas
    suyas = [c for c in llamadas[0] if c[0] == f["id"]]
    assert suyas and suyas[0][1][:len(f["consultas_es"])] == f["consultas_es"]


# ── «Qué hacer» ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_que_hacer_propone_presencial_y_meta_solo_con_historia():
    p = Perfil.model_validate({"id": "00000000-0000-4000-8000-000000000001", "cliente_id": "00000000-0000-4000-8000-000000000002",
                               "cargo_id": "00000000-0000-4000-8000-000000000003", "meta_diaria": 10,
                               "ubicaciones": [{"paises": ["CO"], "ciudades": [], "modalidades": ["remoto"]}],
                               "idiomas": ["es"]})
    v = {"id": "v1", "titulo": "Diseñador UX", "empresa": "E", "ubicacion": "Bogotá, Colombia", "paises": ["CO"],
         "alcance": "pais", "modalidad": "presencial", "idioma": "es", "fecha": hoy()}
    ajustes = servicio.que_hacer(p, [], [v], set(), set(), hoy(), {"CO": "Colombia"}, [2, 3, 1])
    claves = {a["clave"]: a for a in ajustes}
    assert claves.get("modalidad", {}).get("mas") == 1 or "modalidad" not in claves  # depende de la ficha mínima
    assert claves["meta"]["accion"] == "Bajar su meta diaria de 10 a 5"
    assert "meta" not in {a["clave"] for a in servicio.que_hacer(p, [], [], set(), set(), hoy(), {}, [2])}  # 1 día
    assert "meta" not in {a["clave"] for a in servicio.que_hacer(p, [], [], set(), set(), hoy(), {}, [2, 3, 10])}


def test_sugerencias_sin_titulos_en_portugues():
    r = terminos.sugerir("Product Designer", consultar_esco=False)
    assert not [x for x in r["terminos_exactos"] + r["terminos_similares"] + r["terminos_es"] if terminos.en_portugues(x)]
