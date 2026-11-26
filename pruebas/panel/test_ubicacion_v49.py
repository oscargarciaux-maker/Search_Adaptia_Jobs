"""Contrato v49: la ubicación sin fugas. Si el aviso nombra un país, manda ese país; presencial/híbrida exige ciudad;
el horario solo abre avisos sin país y solo para quien lo marcó. Casos tomados de la bodega del 25 nov (datos públicos)."""
import pytest

from buscador import bodega, paises
from panel.afinidad import MOTIVO_CIUDAD_SIN_CONFIRMAR, MOTIVO_SIN_CIUDAD, evaluar, evaluar_post
from panel.modelos import Perfil
from panel.repositorio import hoy

BASE = {"id": "00000000-0000-0000-0000-000000000001", "cliente_id": "00000000-0000-0000-0000-000000000002",
        "cargo_id": "00000000-0000-0000-0000-000000000003", "idiomas": ["es", "en"]}
CUBIERTOS = sorted(paises.datos()["codigos"])


def perfil(pais, modalidades=("remoto",), ciudades=(), **extra):
    return Perfil.model_validate({**BASE, **extra, "ubicaciones": [
        {"paises": [pais] if pais else [], "ciudades": list(ciudades), "modalidades": list(modalidades)}]})


def guardada(modalidad="remoto", paises_v=(), mundo=None, ubicacion="", confianza="alta", **extra):
    """Una vacante como quedó guardada en el catálogo o en un lote (sin volver a leer su ubicación)."""
    return {"titulo": "Product Designer", "modalidad": modalidad, "paises": list(paises_v),
            "paises_mundo": list(paises_v if mundo is None else mundo), "confianza_pais": confianza,
            "ubicacion": ubicacion, "idioma": "es", "fecha_publicacion": hoy(), "nota_pais": "", **extra}


def leida(ubicacion, descripcion="", titulo="Product Designer", remoto=None):
    """Una vacante etiquetada hoy por el motor con esa ubicación y descripción."""
    r = paises.elegibles(titulo, ubicacion, descripcion, remoto)
    return guardada(r["modalidad"], r["paises"], r["paises_mundo"], ubicacion, r["confianza"], nota_pais=r["nota"],
                    alcance_mundial=r["alcance_mundial"], zona_utc=r["zona_utc"])


def sirve(v, p):
    return evaluar(v, p, hoy())["compatible"]


# ── El horario no abre una remota de otro país ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ubicacion,pais", [("Desde casa, Mexico", "MX"), ("Remote, Peru", "PE"),
                                            ("Desde casa, Ecuador", "EC")])
def test_remota_de_otro_pais_con_horario_no_llega_a_colombia(ubicacion, pais):
    v = guardada("remoto", [pais], ubicacion=ubicacion, confianza="media", zona_utc=[-7, -3])
    assert not sirve(v, perfil("CO"))
    # Ni marcando el horario: el aviso nombra un país y manda ese país.
    assert not sirve(v, perfil("CO", acepta_horario=["UTC-5"]))
    assert sirve(v, perfil(pais))


def test_solo_franja_horaria_sirve_a_quien_marco_ese_horario():
    v = leida("Remote", "You must overlap with EST hours.")
    assert v["nota_pais"] == "por zona horaria" and v["confianza_pais"] == "baja"
    sin_marcar = evaluar(v, perfil("CO"), hoy())
    assert not sin_marcar["compatible"] and sin_marcar["motivos"] == ["país sin elegibilidad confirmada"]
    marcado = evaluar(v, perfil("CO", acepta_horario=["UTC-5"]), hoy())
    assert marcado["compatible"] and "Remota con horario compatible" in marcado["pruebas"]
    assert not sirve(v, perfil("ES", acepta_horario=["UTC+1"]))  # otra franja


def test_la_zona_no_confirma_una_residencia_sin_confirmar():
    v = guardada("remoto", CUBIERTOS, [], "Remote", "baja", zona_utc=[-7, -3],
                 nota_pais="restricción de residencia sin confirmar")
    assert not sirve(v, perfil("CO", acepta_horario=["UTC-5"]))


def test_la_admision_solo_conserva_por_horario_lo_que_no_nombra_pais(monkeypatch):
    monkeypatch.setattr(bodega, "_config_operativa", {"paises_objetivo_mundo": [], "acepta_horario": True})
    assert bodega._sirve_a_perfiles(leida("Remote", "You must overlap with EST hours."))
    assert not bodega._sirve_a_perfiles(guardada("remoto", [], ["US"], "Remote, United States", zona_utc=[-7, -3]))


# ── «Anywhere in <lugar>» no es para cualquier país ────────────────────────────────────────────────────────────────
def test_anywhere_in_un_lugar_manda_el_lugar():
    nueva = leida("Anywhere in France, Belgium, Spain", remoto=True)
    assert not nueva["alcance_mundial"] and nueva["paises"] == ["ES"]
    # Como quedó guardada antes de v49: alcance mundial y los 20 países cubiertos.
    vieja = guardada("remoto", CUBIERTOS, ["BE", "ES", "FR"], "Anywhere in France, Belgium, Spain", alcance_mundial=True)
    for v in (nueva, vieja):
        assert not sirve(v, perfil("CO")) and not sirve(v, perfil("US"))
        assert sirve(v, perfil("ES")) and sirve(v, perfil("FR"))


def test_el_alcance_mundial_de_verdad_sigue_sirviendo_a_todos():
    v = leida("Remote - Worldwide")
    assert v["alcance_mundial"]
    assert sirve(v, perfil("CO")) and sirve(v, perfil("DE")) and sirve(v, perfil("AE"))
    assert not paises.mundo_acotado("Anywhere in the world") and paises.mundo_acotado("Anywhere in the US")
    # Mundial guardado con un país nombrado y `paises` restringido: manda lo restringido.
    assert not sirve(guardada("remoto", ["ES"], ["ES", "FR"], "Remote", alcance_mundial=True), perfil("CO"))


# ── La residencia obligatoria manda sobre la ubicación ─────────────────────────────────────────────────────────────
def test_remota_con_residencia_en_otro_pais_no_llega_por_su_ubicacion():
    vieja = guardada("remoto", ["AR"], ["AR", "CO"], "Colombia", nota_pais="restricción explícita de residencia")
    assert not sirve(vieja, perfil("CO")) and sirve(vieja, perfil("AR"))
    nueva = leida("United States", "This is a remote role. Candidates must reside in Canada.", remoto=True)
    assert nueva["paises_mundo"] == ["CA"]
    assert sirve(nueva, perfil("CA")) and not sirve(nueva, perfil("US")) and not sirve(nueva, perfil("CO"))


@pytest.mark.parametrize("frase,restringe", [
    ("We are a leading US-based company building payments software.", False),
    ("You will support our US based clients and their engineering teams.", False),
    ("Join a Europe-based startup with customers worldwide.", False),
    ("Candidates must be US-based.", True),
    ("We are only considering US-based candidates for this role.", True),
    ("This position is US only.", True),
])
def test_us_based_solo_restringe_si_habla_de_la_persona(frase, restringe):
    r = paises.elegibles("Product Designer", "Remote - LATAM", frase, True)
    assert (r["paises"] == []) is restringe, r


# ── La ciudad no anula el país ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("pais,ciudad,ubicacion,pais_aviso,esperado", [
    ("CL", "Santiago", "Santiago, Región Metropolitana, Chile", "CL", True),
    ("CL", "Santiago", "Santiago de Cali, Valle del Cauca, Colombia", "CO", False),
    ("CL", "Santiago", "Santiago de Surco, Lima, Perú", "PE", False),
    ("CL", "Santiago", "Santiago de Compostela, Galicia, Spain", "ES", False),
    ("ES", "Valencia", "Valencia, Comunidad Valenciana, España", "ES", True),
    ("ES", "Valencia", "Valencia, Carabobo, Venezuela", "VE", False),
    ("CR", "San José", "San José, Costa Rica", "CR", True),
    ("CR", "San José", "San Jose, CA", "US", False),
    ("US", "Paris", "Paris, TX", "US", True),
    ("US", "Paris", "Paris, Île-de-France, France", "FR", False),
])
def test_ciudad_con_el_mismo_nombre_en_otro_pais(pais, ciudad, ubicacion, pais_aviso, esperado):
    cubierto = pais_aviso in CUBIERTOS
    v = guardada("presencial", [pais_aviso] if cubierto else [], [pais_aviso], ubicacion)
    assert sirve(v, perfil(pais, ("hibrido", "presencial"), [ciudad])) is esperado


def test_los_alrededores_no_cruzan_de_pais():
    valencia = perfil("ES", ("presencial",), ["Valencia"])
    assert not sirve(guardada("presencial", [], ["US"], "Santa Monica, CA"), valencia)
    assert not sirve(guardada("presencial", [], ["US"], "Valencia, CA"), valencia)


# ── Presencial e híbrida exigen ciudad (decisión de Oscar) ─────────────────────────────────────────────────────────
def test_sin_ciudad_no_llegan_presenciales_ni_hibridas():
    bogota = guardada("hibrido", ["CO"], ubicacion="Bogotá, Distrito Capital, Colombia")
    sin_ciudad = evaluar(bogota, perfil("CO", ("remoto", "hibrido", "presencial")), hoy())
    assert not sin_ciudad["compatible"] and sin_ciudad["motivos"] == [MOTIVO_SIN_CIUDAD]
    con_ciudad = perfil("CO", ("remoto", "hibrido", "presencial"), ["Bogotá"])
    assert evaluar(bogota, con_ciudad, hoy())["pruebas"][0] == "Oficina en su ciudad"
    assert evaluar(guardada("hibrido", ["CO"], ubicacion="Medellín, Antioquia, Colombia"), con_ciudad,
                   hoy())["motivos"] == ["oficina en otra ciudad"]
    # El aviso no dice ciudad («Colombia»): no se puede confirmar que sea la suya.
    assert evaluar(guardada("presencial", ["CO"], ubicacion="Colombia"), con_ciudad,
                   hoy())["motivos"] == [MOTIVO_CIUDAD_SIN_CONFIRMAR]
    # Las remotas no cambian: siguen por país.
    assert sirve(guardada("remoto", ["CO"], ubicacion="Colombia"), con_ciudad)


def test_los_alrededores_de_su_ciudad_siguen_contando():
    p = perfil("CO", ("presencial",), ["Bogotá"])
    assert sirve(guardada("presencial", ["CO"], ubicacion="Chía, Cundinamarca, Colombia"), p)


def test_la_region_como_ubicacion_ya_no_sirve_a_un_presencial():
    v = leida("Latin America")
    assert v["modalidad"] == "presencial" and "CO" in v["paises"]
    assert not sirve(v, perfil("CO", ("presencial",), ["Bogotá"]))


def test_una_fila_que_no_acepta_la_modalidad_no_pide_ciudad():
    r = evaluar(guardada("presencial", ["CO"], ubicacion="Bogotá, Colombia"), perfil("CO"), hoy())
    assert r["motivos"] == ["modalidad diferente"]
    r = evaluar(guardada("presencial", [], ["US"], "New York, NY"), perfil("CO"), hoy())
    assert r["motivos"] == ["modalidad diferente", "oficina en otro país"]


# ── El país sale de la ciudad cuando la fila no lo trae ────────────────────────────────────────────────────────────
def test_fila_solo_con_ciudad_toma_su_pais():
    p = perfil(None, ("remoto", "presencial"), ["Madrid"])
    assert p.ubicaciones[0].paises == ["ES"] and p.vive_en == "ES"
    assert sirve(guardada("remoto", ["ES"], ubicacion="España"), p)
    assert not sirve(guardada("remoto", ["CO"], ubicacion="Colombia"), p)


def test_perfil_anterior_con_ciudad_de_otro_pais_la_pone_en_su_fila():
    p = Perfil.model_validate({**BASE, "vive_en": "CO", "modalidades": ["presencial"], "ciudades": ["Medellín", "Madrid"]})
    assert [(f.paises, f.ciudades) for f in p.filas] == [(["CO"], ["Medellín"]), (["ES"], ["Madrid"])]
    assert sirve(guardada("presencial", ["ES"], ubicacion="Madrid, Comunidad de Madrid, España"), p)
    assert not sirve(guardada("presencial", ["CO"], ubicacion="Bogotá, Colombia"), p)  # ni por cercana a «Madrid» (CO)


# ── Invariante: nunca llega un aviso cuyo país nombrado no está en el perfil ───────────────────────────────────────
VACANTES = [
    guardada("remoto", ["MX"], ubicacion="Desde casa, Mexico", confianza="media", zona_utc=[-8, -4]),
    guardada("remoto", ["CO"], ubicacion="Colombia", confianza="media", zona_utc=[-7, -3]),
    guardada("remoto", [], ["US"], "Remote, United States", zona_utc=[-7, -3], nota_pais="remoto fuera de LATAM y España"),
    guardada("remoto", CUBIERTOS, ["BE", "ES", "FR"], "Anywhere in France, Belgium, Spain", alcance_mundial=True),
    guardada("remoto", ["ES"], ["BE", "ES", "FR"], "Anywhere in France, Belgium, Spain", alcance_mundial=True),
    guardada("remoto", ["AR"], ["AR", "CO"], "Colombia"),
    guardada("remoto", [], ["CH", "GB", "HR", "PL"], "Remote, Croatia, Switzerland, Poland", zona_utc=[-5, 1]),
    guardada("presencial", ["CO"], ubicacion="Santiago de Cali, Valle del Cauca, Colombia"),
    guardada("hibrido", ["PE"], ubicacion="Santiago de Surco, Lima, Perú"),
    guardada("presencial", ["ES"], ubicacion="Madrid, Comunidad de Madrid, España"),
    guardada("hibrido", ["MX"], ubicacion="Ciudad de México, DIF, Mexico"),
    guardada("presencial", [], ["US"], "Santa Monica, CA"),
    guardada("remoto", CUBIERTOS, [], "Remote - Worldwide", alcance_mundial=True),
    guardada("remoto", [c for c in CUBIERTOS if c != "ES"], ubicacion="Remote - LATAM"),
]
PERFILES = [perfil(pais, modalidades, ciudades, acepta_horario=horario)
            for pais, ciudades in (("CO", ["Bogotá"]), ("MX", ["Ciudad de México"]), ("CL", ["Santiago"]),
                                   ("ES", ["Madrid", "Valencia"]), ("US", ["New York"]), ("DE", ["Berlin"]))
            for modalidades in (("remoto",), ("remoto", "hibrido", "presencial"))
            for horario in ([], ["UTC-5", "UTC+1"])]


def test_invariante_el_pais_nombrado_manda():
    aceptadas = 0
    for p in PERFILES:
        suyos = {c for f in p.filas for c in f.paises}
        for v in VACANTES:
            if not sirve(v, p):
                continue
            aceptadas += 1
            nombrados = set(v["paises"]) | set(v["paises_mundo"])
            mundial = v.get("alcance_mundial") and not v["paises_mundo"]
            assert nombrados & suyos or mundial, (sorted(suyos), v["ubicacion"])
    assert aceptadas >= 20  # la tabla sigue probando algo: hay aceptadas en varios países


# ── Posts: el tope diario cuenta todo lo que se le perdonó ─────────────────────────────────────────────────────────
def test_un_post_al_que_se_le_perdona_la_ubicacion_queda_marcado():
    post = guardada("remoto", [], [], "", "baja", tipo="post", ubicacion_sin_confirmar=True)
    r = evaluar_post(post, perfil("CO"), hoy())
    assert r["compatible"] and r["tolerada"]
    claro = guardada("remoto", ["CO"], ubicacion="Colombia", tipo="post")
    assert "tolerada" not in evaluar_post(claro, perfil("CO"), hoy())
