"""Contrato v49: más vacantes para quien va corto, sobre todo quien solo acepta avisos en español. Completar hasta la
meta, comprobar enlaces por necesidad, leer en Computrabajo solo lo útil, reconocer lo que se busca y leer bien el
español de los avisos («Modalidad: 100% remoto | Latinoamérica»)."""
from datetime import datetime, timezone

import pytest

from buscador import bodega, cobertura, entrega, familias, normalizar, paises, vacante, verificar_enlaces
from buscador.fuentes import computrabajo as ct
from panel import ejecutor, terminos
from panel.modelos import Configuracion
from panel.repositorio import configuracion_demo, hoy
from pruebas.panel.test_rescate_v36 import Repo
from pruebas.test_computrabajo import FICHA, LISTADO, Respuesta

ES = ("Buscamos una persona para nuestro equipo de producto. Vas a diseñar flujos en Figma, armar prototipos y "
      "wireframes, cuidar el sistema de diseño y trabajar con desarrollo todos los días. Ofrecemos trabajo remoto. ") * 2
EN = ("We are hiring for our product team. You will design flows in Figma, build wireframes and prototyping, keep the "
      "design system and work with engineering every day. We offer a remote role. ") * 2


def _vacante(n, descripcion=ES, ubicacion="Remoto, Colombia", verificada=True, titulo="Product Designer", empresa=None):
    v = vacante.crear(titulo, empresa or f"Empresa {n}", f"https://jobs.lever.co/e/es-{n}", "Lever", ubicacion=ubicacion,
                      descripcion=descripcion, fecha=hoy(), hoy=hoy(), remoto=True)
    ahora = datetime.now(timezone.utc).isoformat()
    v["verificacion"] = {"estado": "verificada" if verificada else "pendiente",
                         "enlaces": [{"url": v["enlace"], "estado": "verificada" if verificada else "pendiente",
                                      "comprobada_en": ahora if verificada else ""}]}
    return v


@pytest.fixture
def cfg():
    """Un solo perfil activo: Product Designer, Colombia, remoto y SOLO avisos en español, con meta de 8 al día."""
    c = configuracion_demo()
    for p in c["perfiles"][1:]:
        p["activo"] = False
    c["perfiles"][0].update(vive_en="CO", modalidades=["remoto"], ciudades=[], idiomas=["es"], meta_diaria=8,
                            ubicaciones=[])
    return c


# ── Completar hasta la meta diaria (decisión de Oscar) ─────────────────────────────────────────────────────────────
def test_quien_solo_acepta_espanol_se_completa_hasta_su_meta_con_la_bodega(cfg):
    p = cfg["perfiles"][0]
    en_espanol = [_vacante(n) for n in range(1, 11)]
    en_ingles = [_vacante(n, EN) for n in range(11, 21)]
    de_mexico = [_vacante(n, ubicacion="Desde casa, Mexico") for n in range(21, 26)]
    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy(), vacantes=en_ingles + de_mexico + en_espanol,
                       cache_enlaces={})
    ids = [a["vacante_id"] for a in repo.asignaciones if a["perfil_id"] == p["id"]]
    assert len(ids) == 8  # su meta, no solo el mínimo de 5
    assert set(ids) <= {v["id"] for v in en_espanol}  # ni en inglés ni de otro país
    assert repo.ejecucion["resumen"]["rescatadas"] == 8


def test_del_minimo_a_la_meta_no_se_pasa_del_techo_del_dia(cfg):
    p = cfg["perfiles"][0]
    cfg["techo_diario"] = 6
    p["meta_diaria"] = 6
    c = Configuracion.model_validate(cfg)
    perfil = next(x for x in c.perfiles if str(x.id) == p["id"])
    # El lote ya usó 4 de las 6 del techo: caben 2 vacantes nuevas más allá del mínimo.
    completar = ejecutor.Completar(c, {}, [], ["l1", "l2", "l3", "l4"])
    assert completar.objetivo(perfil) == 6 and completar.libre == 2
    for n in range(5):  # hasta el mínimo siempre cabe, aunque se acabe el techo
        assert completar.cabe(perfil, f"v{n}")
        completar.anotar(perfil, f"v{n}")
    assert completar.libre < 0 and not completar.cabe(perfil, "otra")
    assert completar.cabe(perfil, "l1")  # una que ya está en el lote de hoy no gasta techo
    assert completar.falta(perfil) == 1


def test_comunidad_sigue_en_el_minimo(cfg):
    cfg["clientes"][0]["comunidad"] = True
    c = Configuracion.model_validate(cfg)
    perfil = next(x for x in c.perfiles if x.activo)
    assert ejecutor.Completar(c, {}, [], []).objetivo(perfil) == 5


# ── Comprobar enlaces por necesidad ────────────────────────────────────────────────────────────────────────────────
def test_la_cola_de_comprobacion_empieza_por_lo_de_cada_persona(cfg):
    with ejecutor.activar({"revision": 1, "configuracion": cfg}, hoy()):
        suyas = [_vacante(n, verificada=False) for n in range(1, 4)]
        ajenas = [_vacante(n, EN, verificada=False) for n in range(4, 30)] + \
                 [_vacante(30, ubicacion="Desde casa, Mexico", verificada=False)]
        cola = verificar_enlaces.cola_por_necesidad(ajenas + suyas, hoy())
        assert {v["id"] for v in cola} == {v["id"] for v in suyas}  # solo su idioma y su ubicación
        comprobadas = []

        def comprobar(url, titulo, ahora=None, **_):
            comprobadas.append(url)
            return {"url": url, "destino": url, "estado": "verificada", "motivo": "ficha vigente",
                    "comprobada_en": ahora.isoformat(), "http": 200, "saltos": 0, "ruta": []}
        original = verificar_enlaces.comprobar
        verificar_enlaces.comprobar = comprobar
        try:
            r = verificar_enlaces.preparar(ajenas + suyas, set(), hoy(), {}, cfg={"vacantes_por_corrida": 6,
                                                                                 "segundos_corrida": 30})
        finally:
            verificar_enlaces.comprobar = original
        assert r["por_necesidad"] == 3 and set(comprobadas[:3]) == {v["enlace"] for v in suyas}
    assert verificar_enlaces.cola_por_necesidad([_vacante(1)], hoy()) == []  # fuera del modo panel no hay cola


def test_primero_quien_tiene_menos_de_donde_elegir(cfg):
    otro = dict(cfg["perfiles"][1], activo=True, cargo_id=cfg["perfiles"][0]["cargo_id"], vive_en="CO",
                modalidades=["remoto"], ciudades=[], idiomas=["es", "en"], ubicaciones=[], meta_diaria=5)
    cfg["perfiles"][1] = otro
    with ejecutor.activar({"revision": 1, "configuracion": cfg}, hoy()):
        espanol = _vacante(1, verificada=False)
        ingles = [_vacante(n, EN, verificada=False) for n in range(2, 8)]
        cola = verificar_enlaces.cola_por_necesidad(ingles + [espanol], hoy())
        assert cola[0]["id"] == espanol["id"]  # la única de quien solo acepta español va primero


def test_sirve_a_corta_mira_el_idioma_cuando_ya_se_sabe():
    cobertura.configurar_personas([{"familia": "f", "perfil": "p", "lugares": ["CO"], "peso": 1, "corto": True,
                                    "idiomas": ["es"]}])
    try:
        v = {"familias": [{"familia": "f", "coincidencia": "exacto"}], "paises": ["CO"]}
        assert cobertura.sirve_a_corta(v) and cobertura.sirve_a_corta(dict(v, idioma="es"))
        assert not cobertura.sirve_a_corta(dict(v, idioma="en"))
    finally:
        cobertura.configurar_personas()


def test_quien_solo_acepta_espanol_tiene_el_doble_de_turnos(cfg):
    c = Configuracion.model_validate(cfg)
    p = next(x for x in c.perfiles if x.activo)
    solo_es = ejecutor.persona_de_busqueda(p, "cargo:x")
    bilingue = ejecutor.persona_de_busqueda(p.model_copy(update={"idiomas": ["es", "en"]}), "cargo:x")
    assert solo_es["peso"] == 2 * bilingue["peso"] and solo_es["idiomas"] == ["es"]


# ── Computrabajo: fichas solo de cargos buscados y relectura ───────────────────────────────────────────────────────
class Cliente:
    def __init__(self):
        self.pedidas = []

    def get(self, url, params=None):
        self.pedidas.append(url)
        return Respuesta(LISTADO if "/trabajo-de-" in url else FICHA)


def test_computrabajo_no_gasta_fichas_en_titulos_de_otro_cargo():
    mapa = [{"id": "contaduria", "nombre": "Contador", "consultas": ["Contador"], "exactos": ["contador"],
             "similares": [], "cercanos": []}]
    familias.configurar(mapa)  # el listado trae «Diseñador UX/UI» y «Product Designer»: ninguno es del cargo buscado
    try:
        cliente = Cliente()
        crudas, stats = ct.buscar(cliente, mapa, [("CO", "Colombia")], {}, 5, hoy="2026-11-12")
    finally:
        familias.configurar()
    assert stats["avisos"] == 2 and stats["del_cargo"] == 0 and stats["con_descripcion"] == 0
    assert len(cliente.pedidas) == 1 and all(not c["descripcion"] for c in crudas)  # solo la página de búsqueda


def test_computrabajo_relee_las_guardadas_sin_descripcion():
    def guardada(n, descripcion="", fuente="Computrabajo"):
        return {"id": f"c{n}", "titulo": "Product Designer", "empresa": "Empresa", "fuente": fuente, "modalidad": "remoto",
                "enlace": f"https://co.computrabajo.com/ofertas-de-trabajo/oferta-{n}", "ubicacion": "Bogotá, Colombia",
                "_descripcion": descripcion, "visto_ultima_vez": "2026-11-12", "visto_primera_vez": "2026-11-10"}
    previas = [guardada(1), guardada(2, "x" * 300), guardada(3, fuente="LinkedIn"), guardada(4)]
    cliente = Cliente()
    crudas, stats = ct.completar_descripciones(cliente, previas, 5, hoy="2026-11-12")
    assert stats == {"pendientes": 2, "peticiones": 2, "con_descripcion": 2, "cerradas": 0}
    assert {c["enlace"] for c in crudas} == {previas[0]["enlace"], previas[3]["enlace"]}
    assert all(len(c["descripcion"]) >= 200 and c["fecha"] == "2026-11-09" and c["remoto"] is True for c in crudas)
    assert ct.completar_descripciones(Cliente(), previas, 1, hoy="2026-11-12")[1]["peticiones"] == 1  # su presupuesto


# ── Reconocer lo que se busca ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("titulo,esperado", [
    ("Desarrolladores Full Stack", "exacto"), ("Desarrolladoras Fullstack Senior", "exacto"),
    ("Full Stack Developers", "similar"), ("Desarrollador Full Stack", "exacto"), ("Contadores", None),
])
def test_los_plurales_cuentan(titulo, esperado):
    cargo = {"nombre": "Desarrollador Full Stack", "terminos_exactos": ["Desarrollador Fullstack"],
             "terminos_similares": ["Full Stack Developer"], "terminos_excluidos": []}
    assert terminos.grado(titulo, cargo)[0] == esperado


def test_singular_es_simetrico_y_no_toca_palabras_cortas():
    assert normalizar.singular("desarrolladores analistas gerentes lideres") == "desarrollador analista gerente lider"
    assert normalizar.singular("qa ux sales business analysis") == "qa ux sale business analysis"


@pytest.mark.parametrize("titulo,esperado", [
    ("Contador", True), ("Vendedora de mostrador", True), ("Asesor comercial", True), ("Enfermera jefe", True),
    ("Ejecutivo de cuenta", True), ("Diseñador UX/UI", True), ("Product Manager IA", True),
    ("Product Designer", False), ("Account Executive", False), ("Director of Engineering", False),
    ("Director de Ingeniería", True), ("Supervisor, Warehouse and Operations", False),
    ("Designer de Produto", False), ("Gerente de Produto", False),
])
def test_titulos_en_espanol_tambien_de_oficios_generales(titulo, esperado):
    assert terminos.en_espanol(titulo) is esperado


def test_en_espanol_solo_se_busca_lo_que_despues_se_reconoce(cfg):
    c = Configuracion.model_validate(cfg)
    cargo = c.cargos[0]  # Product Designer: título exacto de su familia del mapa
    raw = cargo.model_dump(mode="json")
    consultas = ejecutor.consultas_espanol(cargo, raw)
    assert consultas and all(terminos.en_espanol(t) for t in consultas)
    assert all(terminos.grado(t, raw)[0] for t in consultas)  # antes se buscaban similares del mapa que nadie reconocía
    fuera = cargo.model_copy(update={"nombre": "Asesor comercial"})
    assert ejecutor.consultas_espanol(fuera, {**raw, "terminos_exactos": [], "terminos_similares": []}) == \
        ["Asesor comercial"]


# ── Modalidad y alcance en el español de los avisos ────────────────────────────────────────────────────────────────
RELLENO = "Buscamos una persona con experiencia para sumarse a nuestro equipo. "


@pytest.mark.parametrize("descripcion,modalidad,latam", [
    ("Modalidad: 100% remoto | Latinoamérica", "remoto", True),
    ("Trabajo 100 % remoto desde cualquier país de Latinoamérica.", "remoto", True),
    ("Posición remota para LATAM, contrato indefinido.", "remoto", True),
    ("Modalidad: remoto. Horario de lunes a viernes.", "remoto", False),       # remota, pero solo de su país
    ("Somos una empresa líder en Latinoamérica con oficinas en Bogotá.", "presencial", False),
    ("No es 100% remoto: se requiere asistir a la oficina.", "presencial", False),
    ("Atendemos clientes de toda Latinoamérica desde nuestra sede.", "presencial", False),
])
def test_modalidad_y_alcance_en_espanol(descripcion, modalidad, latam):
    r = paises.elegibles("Product Designer", "Bogotá, Distrito Capital, Colombia", RELLENO + descripcion, None)
    assert r["modalidad"] == modalidad, r
    assert ({"MX", "AR", "CL"} <= set(r["paises"])) is latam, r
    assert "CO" in r["paises"]


# ── «Buscar ahora» para quien falta ────────────────────────────────────────────────────────────────────────────────
def test_la_busqueda_para_quien_falta_lee_hireline_y_magneto():
    from buscador.fuentes import sitemaps_empleo
    assert not set(sitemaps_empleo.SITIOS) & bodega.OMITIDAS_FALTANTES
    assert bodega.OMITIDAS_FALTANTES == {"Tableros remotos", "Portales de empresas"}


def test_el_lote_no_cambia_para_el_modo_heredado():
    assert all("_cargo" not in r for r in entrega.config()["roles"])  # sin panel no hay cargo operativo ni evidencia
