"""P-16.2 (idea de Oscar, 28 nov): el crédito de Apify va entero a POSTS de LinkedIn para quien va corto.

Sin red ni Apify de verdad (respuestas falsas): el rescate de fichas formales queda apagado, los posts usan el ritmo
del día sin pasar nunca del tope del mes, las consultas llevan solo cargo, idioma y modalidad (nunca el país), quien
va en 0 va primero y un post «remoto» sin región ya no se descarta: queda «ubicación sin confirmar» (v28)."""
import pytest

from buscador import apify, bodega, contrato, entrega, familias, refuerzo, vacante
from buscador.fuentes import publicaciones_apify as pa
from panel import afinidad, ejecutor
from panel.repositorio import configuracion_demo, hoy
from pruebas.panel.test_posts import BUENO, VALIDAS, ClientePosts, _post

ACTOR = "harvestapi/linkedin-post-search"


def _dia(n):
    return f"2027-01-{n:02d}"  # un mes de 31 días


# ── Reparto del crédito ────────────────────────────────────────────────────────────────────────────────────────────

def test_config_manda_el_credito_a_los_posts_y_alcanza_el_mes():
    cfg = bodega.config()["apify"]
    assert cfg["rescate_busquedas"] == 0 and cfg["publicaciones_por_dia"] == 0
    # El ritmo del día alcanza un mes de 31 días sin pasar del tope (aunque el ciclo de Apify no empiece el día 1).
    assert 31 * cfg["ritmo_diario_usd"] <= cfg["tope_mensual_usd"]
    # Con la cuenta gratis caben 75 posts al día; el tope de la configuración no los recorta.
    assert pa.posts_que_caben(cfg["ritmo_diario_usd"], cfg["posts_rescate"]) == 75


def test_rescate_formal_apagado_no_llama_a_apify():
    llamadas = []
    with ejecutor.activar({"configuracion": configuracion_demo()}, hoy()):
        _, stats = refuerzo.rescate_apify([], {}, hoy(), entrega.config(), familias.mapa(),
                                          lambda c: llamadas.append(c) or ([], {}), lambda a, b: a + b,
                                          max_busquedas=0)
    assert llamadas == [] and "apagado" in stats["omitida"]


def test_posts_piden_lo_que_cabe_en_el_dia_y_nunca_pasan_del_tope_del_mes():
    estado, reservado = {}, 0.0
    for n in range(1, 32):
        control = apify.Presupuesto(estado, _dia(n), mensual=5, corrida=3, diario=0.16)
        cliente = ClientePosts([_post(BUENO)])
        consultas = [f"q{i}" for i in range(12)]
        _, _, stats = pa.buscar_posts(cliente, ACTOR, consultas, VALIDAS, _dia(n), maximo=300, token="t",
                                      control_gasto=control)
        assert "maxTotalChargeUsd=0.16" in cliente.cargos[0]  # lo del día, no los 0,61 que pediría el tope de 300
        reservado += stats["usd_reservado"]
    assert round(reservado, 6) <= 5 and round(sum(estado["reservas"].values()), 6) == round(reservado, 6)
    # El mes ya no alcanza: no se llama a Apify (aviso de presupuesto, no avería).
    agotado = apify.Presupuesto({"mes": "2027-01", "reservas": {"2027-01-01": 5}}, _dia(31), mensual=5, diario=0.16)
    cliente = ClientePosts([])
    assert pa.buscar_posts(cliente, ACTOR, ["q"], VALIDAS, _dia(31), maximo=300, token="t",
                           control_gasto=agotado)[2] == {"omitida": "presupuesto de Apify agotado"}
    assert cliente.cargos == []


def test_cada_consulta_pide_su_parte_de_los_posts_del_dia():
    class Cliente(ClientePosts):
        def post_json(self, url, cuerpo, headers=None, timeout=None):
            self.cuerpo = cuerpo
            return super().post_json(url, cuerpo, headers, timeout)
    cliente = Cliente([])
    control = apify.Presupuesto({}, _dia(1), mensual=5, diario=0.16)
    pa.buscar_posts(cliente, ACTOR, [f"q{i}" for i in range(12)], VALIDAS, _dia(1), maximo=300, token="t",
                    control_gasto=control)
    assert cliente.cuerpo["maxPosts"] == 75 // 12 and cliente.cuerpo["postedLimit"] == "24h"


# ── Consultas: solo cargo, idioma y modalidad ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def cfg():
    return configuracion_demo()  # perfiles 0–2: Product Designer; 3: Frontend; 4: QA


def _consultas(cfg, deficit=None, monkeypatch=None):
    vistas = []
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        if deficit is not None:
            ids = [p["id"] for r in entrega.config()["roles"] for p in r.get("_perfiles") or []]
            monkeypatch.setattr(entrega, "deficit_por_perfil",
                                lambda *a, **k: {ids[i]: n for i, n in deficit.items()})
        _, stats, _ = refuerzo.rescate_posts([], {}, hoy(), entrega.config(), familias.mapa(),
                                             lambda c, v, e=None: vistas.append(c) or ([], [], {}),
                                             lambda a, b: a + b)
    return vistas[0], stats


def test_consultas_sin_pais_ni_datos_de_la_persona(cfg):
    for p in cfg["perfiles"]:
        p.update(vive_en="KE")
    consultas, _ = _consultas(cfg)
    texto = " ".join(consultas).lower()
    assert consultas and not any(x in texto for x in ("kenya", "kenia", "colombia", "españa", "nairobi"))
    assert all(q.endswith((" remote", " remoto")) for q in consultas)  # todos aceptan solo remoto


def test_el_idioma_del_perfil_decide_las_palabras_de_la_consulta(cfg):
    for p in cfg["perfiles"]:
        p["idiomas"] = ["es"]
    solo_es, _ = _consultas(cfg)
    assert all(q.startswith(pa.CONTRATA_POST["es"]) and q.endswith(" remoto") for q in solo_es)
    assert any('"Product Designer"' in q for q in solo_es)  # en español también con el título en inglés
    for p in cfg["perfiles"]:
        p["idiomas"] = ["en"]
    solo_en, _ = _consultas(cfg)
    assert all(q.startswith(pa.CONTRATA_POST["en"]) and q.endswith(" remote") for q in solo_en)


def test_quien_acepta_oficina_busca_tambien_sin_modalidad(cfg):
    for p in cfg["perfiles"]:
        p["ubicaciones"] = [{"paises": ["CO"], "ciudades": ["Bogotá"], "modalidades": ["presencial"]}]
    consultas, _ = _consultas(cfg)
    assert consultas and not any(q.endswith((" remote", " remoto")) for q in consultas)


def test_terminos_de_una_palabra_no_se_usan_si_hay_frases():
    familia = {"consultas": ["QA", "QA Engineer"], "consultas_es": ["Analista QA"], "exactos": ["Software Tester"]}
    assert refuerzo.terminos_post(familia, "en") == ["QA Engineer", "Software Tester"]
    assert refuerzo.terminos_post(familia, "es") == ["Analista QA", "QA Engineer", "Software Tester"]
    assert refuerzo.terminos_post({"consultas": ["QA"]}, "en") == ["QA"]


def test_quien_va_en_cero_va_primero(cfg, monkeypatch):
    from panel.afinidad import RESCATE_BAJO
    # QA (perfil 4) en 0; Product Designer (perfil 0) con 2 faltantes: QA va primero aunque falte menos en total.
    consultas, stats = _consultas(cfg, {0: 2, 4: RESCATE_BAJO}, monkeypatch)
    assert "qa" in consultas[0].lower() or "pruebas" in consultas[0].lower()
    assert stats["perfiles_en_cero"] == 1 and stats["perfiles_con_deficit"] == 2


# ── Posts remotos sin región ───────────────────────────────────────────────────────────────────────────────────────

REMOTO_SIN_REGION = ("¡Estamos contratando! Buscamos Product Designer 100% remoto, con experiencia en Figma y design "
                     "systems. Si te interesa, envíame tu CV por DM.")


def test_post_remoto_sin_region_queda_sin_confirmar_y_no_se_descarta():
    v, motivo = pa.a_vacante(_post(REMOTO_SIN_REGION), VALIDAS, hoy())
    assert motivo == "" and v["remoto"] is True and v["ubicacion_sin_confirmar"] and v["ubicacion_deducida"] == ""
    post = vacante.crear_post(v["titulo"], v["empresa"], v["enlace"], v["ubicacion"], v["descripcion"], v["fecha"],
                              v["remoto"], v["contacto"], hoy())
    post.update(ubicacion_sin_confirmar=v["ubicacion_sin_confirmar"])
    assert contrato.entregable_post(post) == ""  # antes: «elegibilidad regional por confirmar»
    assert afinidad.post_ubicacion(post) == "sin_confirmar"  # marcado y con el tope de 2 por perfil y día


def test_post_remoto_que_nombra_su_region_no_queda_sin_confirmar():
    v, _ = pa.a_vacante(_post(REMOTO_SIN_REGION.replace("100% remoto", "100% remoto desde Colombia")), VALIDAS, hoy())
    assert v["ubicacion_sin_confirmar"] is False and "Colombia" in v["ubicacion"]
