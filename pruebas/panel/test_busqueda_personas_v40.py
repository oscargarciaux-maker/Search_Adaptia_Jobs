"""Contrato v40 (17 nov, pedido de Oscar): la búsqueda se arma leyendo a cada persona, para cualquier cargo y
cualquier parte del mundo. Antes, quien vivía en Emiratos y trabajaría en remoto para Europa recibía 3 búsquedas de
LinkedIn al día y Europa nunca se buscaba."""
from uuid import uuid4

from buscador import cobertura
from buscador.fuentes import indeed
from panel import ejecutor
from panel.modelos import Configuracion, Perfil
from panel.revision import expandir


def _perfil(ubicaciones, idiomas=("es", "en"), meta=10):
    return Perfil.model_validate({"id": str(uuid4()), "cliente_id": str(uuid4()), "cargo_id": str(uuid4()),
                                  "idiomas": list(idiomas), "meta_diaria": meta, "ubicaciones": ubicaciones})


def _lugares(*ubicaciones, **op):
    return ejecutor.lugares_perfil(_perfil(list(ubicaciones), **op))


def test_cualquier_pais_del_mundo_se_busca_donde_vive():
    japon = _lugares({"paises": ["JP"], "modalidades": ["remoto"]})
    assert japon == {"REMOTO_JP": {"location": "Japan", "f_WT": "2"},
                     "REMOTO_MUNDO": {"location": "Worldwide", "f_WT": "2"}}
    assert "REMOTO" not in japon  # «remoto en LATAM» solo para quien vive en LATAM
    assert "REMOTO" in _lugares({"paises": ["CO"], "modalidades": ["remoto"]})


def test_cada_fila_cuenta_con_sus_modalidades_y_ciudades():
    p = _lugares({"paises": ["DE"], "ciudades": ["Berlín"], "modalidades": ["hibrido"]},
                 {"paises": ["CO"], "modalidades": ["remoto"]}, idiomas=("es",))
    assert set(p) == {"DE", "CIUDAD_BERLIN", "REMOTO_CO", "REMOTO_MUNDO"}
    pasto = _lugares({"paises": ["CO"], "ciudades": ["Pasto"], "modalidades": ["presencial"]})
    assert set(pasto) == {"CO", "CIUDAD_PASTO"}  # una ciudad pequeña también es un lugar


def test_una_region_se_busca_como_region_y_en_sus_paises_principales():
    europa = expandir(["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV",
                       "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB", "CH", "NO"])
    p = _lugares({"paises": ["AE"], "modalidades": ["remoto"]}, {"paises": europa, "modalidades": ["remoto"]})
    assert p["REMOTO_REGION_EUROPA"] == {"location": "European Union", "f_WT": "2"}
    assert {"REMOTO_AE", "REMOTO_GB", "REMOTO_DE", "REMOTO_NL"} <= set(p)
    assert "REMOTO_LV" not in p  # Letonia va dentro de la búsqueda de la región, no suelta
    sueltos = [k for k in p if k.startswith("REMOTO_") and len(k) == 9]
    assert len(sueltos) <= ejecutor.MAX_PAISES_POR_FILA + 1
    latam = _lugares({"paises": ["CO"], "modalidades": ["remoto"]},
                     {"paises": expandir(["LATAM"]), "modalidades": ["remoto"]})
    assert {"REMOTO", "REMOTO_MX", "REMOTO_AR"} <= set(latam)


def test_peso_por_meta_por_ir_corta_y_por_pocas_fuentes():
    colombia = ejecutor.persona_de_busqueda(_perfil([{"paises": ["CO"], "modalidades": ["remoto"]}]), "cargo:x")
    emiratos = ejecutor.persona_de_busqueda(_perfil([{"paises": ["AE"], "modalidades": ["remoto"]}]), "cargo:x")
    corta = ejecutor.persona_de_busqueda(_perfil([{"paises": ["CO"], "modalidades": ["remoto"]}]), "cargo:x", corto=True)
    assert (colombia["peso"], emiratos["peso"], corta["peso"]) == (10, 20, 20)
    assert {"REMOTO_AE", "AE"} <= set(emiratos["lugares"])  # casa también con Indeed («AE», «AE:REMOTO»)


def _personas(*filas_por_persona, familia="cargo:x"):
    return [ejecutor.persona_de_busqueda(_perfil(f), familia) for f in filas_por_persona]


def test_quien_no_comparte_lugares_recibe_su_parte():
    # Diez personas en Colombia comparten búsquedas; una sola en Emiratos no comparte ninguna.
    personas = _personas(*([[{"paises": ["CO"], "modalidades": ["remoto"]}]] * 10),
                         [{"paises": ["AE"], "modalidades": ["remoto"]}])
    combos = [("cargo:x", ["q"], lugar, {}) for lugar in ("REMOTO_CO", "REMOTO", "REMOTO_MUNDO", "REMOTO_AE",
                                                            "CO", "MX", "AR", "CL")]
    cobertura.configurar_personas(personas)
    try:
        primeras = [c[2] for c in cobertura.repartir(combos, {}, "2026-11-18")[:3]]
    finally:
        cobertura.configurar_personas()
    assert "REMOTO_AE" in primeras
    # Lo que no es de nadie va al final, con el reparto de siempre.
    assert [c[2] for c in cobertura.repartir(combos, {}, "2026-11-18")]  # sin personas: como antes


def test_sin_personas_el_reparto_no_cambia():
    combos = [("cargo:x", ["q"], lugar, {}) for lugar in ("REMOTO", "CO", "MX")]
    assert cobertura.repartir(combos, {}, "2026-11-18") == cobertura._repartir_familias(combos, {}, "2026-11-18")


def test_lo_que_lleva_tres_busquedas_sin_nada_util_pasa_al_final():
    personas = _personas([{"paises": ["CO", "MX"], "modalidades": ["remoto"]}])
    combos = [("cargo:x", ["q"], lugar, {}) for lugar in ("REMOTO_CO", "REMOTO_MX")]
    cobertura.configurar_personas(personas)
    cobertura.configurar_rendimiento({"cargo:x@REMOTO_CO": {"utiles": 0, "ceros": 3, "fecha": "2026-11-17"}})
    try:
        assert cobertura.repartir(combos, {}, "2026-11-18")[0][2] == "REMOTO_MX"
    finally:
        cobertura.configurar_personas()
        cobertura.configurar_rendimiento()


def test_medir_lo_que_trajo_cada_busqueda():
    estado = {"linkedin": {"cargo:x@REMOTO_AE": "2026-11-18", "cargo:x@REMOTO_CO": "2026-11-18"},
              "rendimiento": {"cargo:x@REMOTO_AE": {"utiles": 0, "ceros": 2, "fecha": "2026-11-17"},
                              "cargo:x@VIEJA": {"utiles": 1, "ceros": 0, "fecha": "2026-09-01"}}}
    crudas = [{"enlace": "https://www.linkedin.com/jobs/view/1", "_busqueda": "cargo:x@REMOTO_CO"}]
    vacantes = [{"enlace": "https://www.linkedin.com/jobs/view/1", "familias": [{"familia": "cargo:x"}],
                 "visto_primera_vez": "2026-11-18"}]
    r = cobertura.medir(estado, crudas, vacantes, "2026-11-18")
    assert r["cargo:x@REMOTO_CO"] == {"utiles": 1, "ceros": 0, "fecha": "2026-11-18"}
    assert r["cargo:x@REMOTO_AE"]["ceros"] == 3 and "cargo:x@VIEJA" not in r


def test_busquedas_por_persona_y_relectura_primero_para_quien_va_corta():
    personas = _personas([{"paises": ["AE"], "modalidades": ["remoto"]}], [{"paises": ["CO"], "modalidades": ["remoto"]}])
    personas[0]["corto"] = True
    cobertura.configurar_personas(personas)
    try:
        cobertura.anotar_busqueda("linkedin", "cargo:x", "REMOTO_AE")
        cobertura.anotar_busqueda("indeed", "cargo:x", "AE:REMOTO")
        cobertura.anotar_busqueda("linkedin", "cargo:x", "REMOTO_MUNDO")
        cuenta = cobertura.busquedas_por_persona()
        assert cuenta[personas[0]["perfil"]] == {"linkedin": 2, "indeed": 1}
        assert cuenta[personas[1]["perfil"]] == {"linkedin": 1}
        de_emiratos = {"familias": [{"familia": "cargo:x"}], "paises": [], "paises_mundo": ["AE"]}
        assert cobertura.sirve_a_corta(de_emiratos)
        assert not cobertura.sirve_a_corta({"familias": [{"familia": "cargo:x"}], "paises": ["CO"]})
    finally:
        cobertura.configurar_personas()


def test_indeed_en_todos_los_paises_que_admite():
    assert {"AE", "JP", "IN", "SG", "SA", "PL", "SE"} <= set(indeed.PAISES) and len(indeed.PAISES) == 62
    assert indeed.ubicacion("Remote", "AE") == "Remote, United Arab Emirates"
    assert indeed.ubicacion("Bogotá", "CO") == "Bogotá"


def test_un_cargo_nuevo_y_cualquier_persona_entran_a_la_busqueda():
    from panel.repositorio import configuracion_demo
    cfg = Configuracion.model_validate(configuracion_demo())
    nuevo = {"id": str(uuid4()), "nombre": "Enfermera de cuidados intensivos", "cupo": 5, "activo": True,
             "terminos_exactos": [], "terminos_similares": [], "terminos_excluidos": []}
    cliente = cfg.clientes[0].model_dump(mode="json")
    perfil = {"id": str(uuid4()), "cliente_id": cliente["id"], "cargo_id": nuevo["id"], "idiomas": ["en"],
              "meta_diaria": 5, "ubicaciones": [{"paises": ["NZ"], "ciudades": ["Auckland"],
                                                 "modalidades": ["presencial"]}]}
    datos = cfg.model_dump(mode="json")
    datos["cargos"].append(nuevo)
    datos["perfiles"].append(perfil)
    datos["techo_diario"] = 600
    version = {"revision": 1, "configuracion": datos, "vigente_desde": "2026-11-18"}
    mapa, _, motor = ejecutor.preparar(version, "2026-11-18")
    familia = next(f for f in mapa if f["id"] == "cargo:" + nuevo["id"])
    assert {"NZ", "CIUDAD_AUCKLAND"} <= {clave for clave, _ in familia["lugares"]}
    assert familia["paises_busqueda"] == ["NZ"]
    persona = next(p for p in motor["personas_busqueda"] if p["perfil"] == perfil["id"])
    assert persona["peso"] == 10  # meta 5 × 2: Nueva Zelanda no tiene fuentes propias
