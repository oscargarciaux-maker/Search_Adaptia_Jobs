"""8.1 (decisiones del cliente, 27 nov): huecos por país, solo para el operador. Perfiles ficticios."""
import uuid
from collections import Counter

from fastapi.testclient import TestClient

from panel import afinidad, ejecutor, huecos, servicio
from panel.api import crear_app
from panel.modelos import Configuracion
from panel.repositorio import RepositorioDemo, configuracion_demo

MINIMO = servicio.AVISO_BAJO  # P-11.3: los huecos se miden con la meta (10), no con el rescate (5)


def _id(n):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"huecos-{n}"))


def _cfg(perfiles):
    """La configuración de demostración con estos perfiles (todos del primer cargo y del primer cliente)."""
    cfg = configuracion_demo()
    base = cfg["perfiles"][0]
    cfg["perfiles"] = [{**base, "id": _id(n), "ubicaciones": [], **cambios} for n, cambios in perfiles.items()]
    return cfg


PERFILES = {
    "co": {"vive_en": "CO"},                               # país con fuentes locales: cubierto
    "ke": {"vive_en": "KE"},                               # sin fuente local, pero llega a 10: riesgo
    "gh": {"vive_en": "GH", "idiomas": ["en"]},            # bajo 10 por falta de fuentes: hueco
    "et": {"vive_en": "ET"},                               # bajo 10 por un cargo sin vacantes en ningún sitio: no es hueco
    # Vive en Colombia, híbrido en Tanzania y remoto en cualquier parte y en Uganda: Uganda no crea país.
    "mundo": {"vive_en": "CO", "ubicaciones": [
        {"paises": ["CO"], "ciudades": [], "modalidades": ["remoto"]},
        {"paises": ["TZ"], "ciudades": ["Dar es Salaam"], "modalidades": ["hibrido"]},
        {"paises": ["UG"], "ciudades": [], "modalidades": ["remoto"]}]},
}


def _fila(n, hoy, codigo="", listas=0, por_comprobar=0, dias=3):
    return {"perfil_id": _id(n), "cargo": "Product Designer", "hoy": hoy, "dias_medidos": dias, "listas": listas,
            "por_comprobar": por_comprobar, "causa": "texto para el operador", "causa_codigo": codigo}


def _cobertura():
    return {"minimo": MINIMO, "perfiles": [
        _fila("co", 12), _fila("ke", 11),
        _fila("gh", 7, servicio.CAUSA_POCAS_EN_FUENTES),  # 7: sobre el rescate (5) pero bajo la meta (10)
        _fila("et", 0, servicio.CAUSA_SIN_VACANTES_CARGO),
        _fila("mundo", 10)]}


def _tabla():
    cfg = Configuracion.model_validate(_cfg(PERFILES))
    return {f["pais"]: f for f in huecos.por_pais(_cobertura(), cfg)}


def test_estado_por_pais_distingue_cubierto_riesgo_y_hueco():
    t = _tabla()
    assert t["CO"]["estado"] == "cubierto" and t["CO"]["pedido"] == "" and t["CO"]["fuentes_locales"] > 0
    assert t["KE"]["estado"] == "riesgo" and t["KE"]["bajo_minimo"] == 0
    assert t["GH"]["estado"] == "hueco" and t["GH"]["bajo_minimo"] == 1
    assert t["GH"]["fuentes"] == list(ejecutor.FUENTES_GENERICAS)
    # El cargo que no tiene vacantes en ningún sitio no es un hueco del país: queda solo en riesgo.
    assert t["ET"]["estado"] == "riesgo" and t["ET"]["bajo_minimo"] == 1
    # Híbrido en Tanzania crea país; la remota en Uganda (y en cualquier parte) no.
    assert t["TZ"]["estado"] == "riesgo" and "UG" not in t
    assert t["CO"]["perfiles"] == 2
    assert list(t)[0] == "GH"  # los huecos van primero


def test_otras_causas_no_son_hueco():
    pocas = servicio.CAUSA_POCAS_EN_FUENTES
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, pocas, listas=3), MINIMO)
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, pocas, por_comprobar=4), MINIMO)
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, pocas, dias=0), MINIMO)  # sin medir
    assert not huecos.es_hueco_por_fuentes(_fila("x", MINIMO, pocas), MINIMO)
    for codigo in (servicio.CAUSA_SIN_VACANTES_CARGO, servicio.CAUSA_LISTAS_SIN_RECIBIR, servicio.CAUSA_AJUSTE_PERFIL,
                   servicio.CAUSA_POR_COMPROBAR, ""):
        assert not huecos.es_hueco_por_fuentes(_fila("x", 2, codigo), MINIMO), codigo
    assert huecos.es_hueco_por_fuentes(_fila("x", 2, servicio.CAUSA_OTRO_PAIS), MINIMO)
    assert huecos.es_hueco_por_fuentes(_fila("x", 2, pocas), MINIMO)


def test_huecos_decide_por_codigo_y_no_por_el_texto():
    """8.1b: cambiar la frase para el operador no cambia qué es hueco."""
    fila = _fila("x", 2, servicio.CAUSA_POCAS_EN_FUENTES)
    assert huecos.es_hueco_por_fuentes({**fila, "causa": "cualquier otra frase"}, MINIMO)
    assert not huecos.es_hueco_por_fuentes({**fila, "causa_codigo": servicio.CAUSA_AJUSTE_PERFIL,
                                            "causa": "Pocas vacantes nuevas en las fuentes revisadas"}, MINIMO)


def test_los_codigos_de_hueco_los_produce_cobertura():
    """La tabla solo reconoce códigos que `cobertura()` puede dar (si se renombra uno allí, esto falla)."""
    assert huecos.CAUSAS_HUECO == {servicio.CAUSA_POCAS_EN_FUENTES, servicio.CAUSA_OTRO_PAIS}
    assert afinidad.MOTIVO_OTRO_PAIS in servicio.SUGERENCIAS


def _repo_con(cfg):
    """Demostración con esta configuración y 4 búsquedas medidas en las que nadie recibió nada (todos bajo 10). Las
    vacantes de la demo no admiten postular desde DE ni GH: la causa es un ajuste del perfil."""
    repo = RepositorioDemo()
    repo.operativa = lambda fecha: {"revision": 1, "configuracion": cfg}
    repo.versiones = lambda revisiones: {int(r): cfg for r in revisiones}
    repo.ejecuciones = lambda: [{"id": f"e{i}", "fecha": "2026-11-1" + str(7 - i), "revision": 1} for i in range(4)]
    repo.asignaciones_por_perfil = lambda ids: Counter()
    return repo


def test_indeed_cuenta_como_fuente_local_en_la_tabla_y_en_la_fila():
    """Decisión del 28 nov: un país con Indeed no dice «Cobertura limitada» ni sale en riesgo; uno sin fuente local, sí."""
    assert "Indeed" in ejecutor.fuentes_en("DE") and huecos.fuentes_locales("DE") == ["Indeed"]
    assert huecos.fuentes_locales("GH") == []
    cfg = _cfg({"de": {"vive_en": "DE", "idiomas": ["en"]}, "gh": {"vive_en": "GH", "idiomas": ["en"]}})
    cob = servicio.cobertura(_repo_con(cfg), "2026-11-17")
    filas = {f["vive_en"]: f for f in cob["perfiles"]}
    for pais, limitada in (("DE", False), ("GH", True)):
        f = filas[pais]
        assert f["estado"] == "pendiente" and f["causa_codigo"] == servicio.CAUSA_AJUSTE_PERFIL, pais
        assert f["pocas_fuentes"] is limitada and ("Cobertura limitada" in f["causa"]) is limitada, pais
    tabla = {f["pais"]: f["estado"] for f in huecos.por_pais(cob, Configuracion.model_validate(cfg))}
    assert tabla == {"DE": "cubierto", "GH": "riesgo"}  # un ajuste del perfil: no es hueco


def test_el_pedido_solo_lleva_pais_idiomas_familias_y_modalidades():
    t = _tabla()
    texto = t["GH"]["pedido"]
    assert texto == ("Usa la skill nueva-fuente para Ghana: idioma(s) en, familias de cargo Diseño de producto y UX/UI, "
                     "modalidades remoto. Busca portales locales donde se postula ahí mismo, sin sesión. Es para hoy: "
                     "deja el PR listo para revisar.")
    assert "híbrido" in t["TZ"]["pedido"] and "remoto" not in t["TZ"]["pedido"]
    cfg = _cfg(PERFILES)
    for fila in t.values():
        for privado in [c["nombre"] for c in cfg["clientes"]] + [p["id"] for p in cfg["perfiles"]] + ["Product Designer"]:
            assert privado not in fila["pedido"]
        assert not any(ch.isdigit() for ch in fila["pedido"])  # ni conteos por persona


def test_aviso_al_guardar_solo_por_paises_nuevos_sin_fuente_local():
    antes = _cfg({"co": {"vive_en": "CO"}, "ke": {"vive_en": "KE"}})
    assert huecos.aviso_al_guardar(antes, antes) == []  # nada nuevo: no repite el aviso
    despues = _cfg({"co": {"vive_en": "CO"}, "ke": {"vive_en": "KE"}, "gh": {"vive_en": "GH"},
                    "de": {"vive_en": "DE"}})
    assert huecos.aviso_al_guardar(antes, despues) == ["Ghana: sin fuente local; riesgo de quedar bajo 10."]
    assert huecos.aviso_al_guardar(None, antes) == ["Kenia: sin fuente local; riesgo de quedar bajo 10."]
    remoto = _cfg({"mundo": PERFILES["mundo"]})
    assert huecos.aviso_al_guardar(None, remoto) == ["Tanzania: sin fuente local; riesgo de quedar bajo 10."]
    archivado = _cfg({"gh": {"vive_en": "GH", "activo": False}})
    assert huecos.aviso_al_guardar(None, archivado) == []
    cliente_archivado = _cfg({"gh": {"vive_en": "GH"}})
    cliente_archivado["clientes"][0]["activo"] = False  # nadie lo busca: no avisa
    assert huecos.aviso_al_guardar(None, cliente_archivado) == []


def test_api_avisa_al_guardar_sin_bloquear():
    repo = RepositorioDemo()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    estado = api.get("/api/config").json()
    cfg = estado["borrador"]
    cfg["perfiles"][0] = {**cfg["perfiles"][0], "vive_en": "GH", "ubicaciones": []}
    r = api.put("/api/config", json={"revision": estado["revision"], "configuracion": cfg},
                headers={"Origin": "http://testserver"})
    assert r.status_code == 200, r.text
    assert r.json()["avisos_cobertura"] == ["Ghana: sin fuente local; riesgo de quedar bajo 10."]
    assert api.get("/api/config").json()["borrador"]["perfiles"][0]["vive_en"] == "GH"  # se guardó


def test_api_de_cobertura_trae_la_tabla_de_huecos():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    r = api.get("/api/cobertura").json()
    assert isinstance(r["huecos"], list) and r["huecos"]
    assert {f["estado"] for f in r["huecos"]} <= {"cubierto", "riesgo", "hueco"}
    assert all(set(f) == {"pais", "nombre", "perfiles", "bajo_minimo", "fuentes", "fuentes_locales", "estado", "pedido"}
               for f in r["huecos"])
