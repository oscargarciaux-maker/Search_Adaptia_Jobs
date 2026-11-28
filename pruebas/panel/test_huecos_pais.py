"""8.1 (decisiones del cliente, 27 nov): huecos por país, solo para el operador. Perfiles ficticios."""
import inspect
import uuid

from fastapi.testclient import TestClient

from panel import huecos, servicio
from panel.api import crear_app
from panel.modelos import Configuracion
from panel.repositorio import RepositorioDemo, configuracion_demo

MINIMO = servicio.MINIMO_POR_PERFIL


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
    "ke": {"vive_en": "KE"},                               # sin fuente local, pero llega a 5: riesgo
    "gh": {"vive_en": "GH", "idiomas": ["en"]},            # bajo 5 por falta de fuentes: hueco
    "et": {"vive_en": "ET"},                               # bajo 5 por un cargo sin vacantes en ningún sitio: no es hueco
    # Vive en Colombia, híbrido en Tanzania y remoto en cualquier parte y en Uganda: Uganda no crea país.
    "mundo": {"vive_en": "CO", "ubicaciones": [
        {"paises": ["CO"], "ciudades": [], "modalidades": ["remoto"]},
        {"paises": ["TZ"], "ciudades": ["Dar es Salaam"], "modalidades": ["hibrido"]},
        {"paises": ["UG"], "ciudades": [], "modalidades": ["remoto"]}]},
}


def _fila(n, hoy, causa="", listas=0, por_comprobar=0, dias=3):
    return {"perfil_id": _id(n), "cargo": "Product Designer", "hoy": hoy, "dias_medidos": dias, "listas": listas,
            "por_comprobar": por_comprobar, "causa": causa}


def _cobertura():
    return {"minimo": MINIMO, "perfiles": [
        _fila("co", 6), _fila("ke", 7),
        _fila("gh", 2, huecos.CAUSA_POCAS_VACANTES + " para su ubicación e idioma."),
        _fila("et", 0, "Aún no hay vacantes de este cargo en lo buscado: la próxima búsqueda lo incluye."),
        _fila("mundo", 5)]}


def _tabla():
    cfg = Configuracion.model_validate(_cfg(PERFILES))
    return {f["pais"]: f for f in huecos.por_pais(_cobertura(), cfg)}


def test_estado_por_pais_distingue_cubierto_riesgo_y_hueco():
    t = _tabla()
    assert t["CO"]["estado"] == "cubierto" and t["CO"]["pedido"] == "" and t["CO"]["fuentes_locales"] > 0
    assert t["KE"]["estado"] == "riesgo" and t["KE"]["bajo_minimo"] == 0
    assert t["GH"]["estado"] == "hueco" and t["GH"]["bajo_minimo"] == 1
    assert t["GH"]["fuentes"] == list(huecos.GENERICAS)
    # El cargo que no tiene vacantes en ningún sitio no es un hueco del país: queda solo en riesgo.
    assert t["ET"]["estado"] == "riesgo" and t["ET"]["bajo_minimo"] == 1
    # Híbrido en Tanzania crea país; la remota en Uganda (y en cualquier parte) no.
    assert t["TZ"]["estado"] == "riesgo" and "UG" not in t
    assert t["CO"]["perfiles"] == 2
    assert list(t)[0] == "GH"  # los huecos van primero


def test_otras_causas_no_son_hueco():
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, huecos.CAUSA_POCAS_VACANTES, listas=3), MINIMO)
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, huecos.CAUSA_POCAS_VACANTES, por_comprobar=4), MINIMO)
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, huecos.CAUSA_POCAS_VACANTES, dias=0), MINIMO)  # sin medir
    assert not huecos.es_hueco_por_fuentes(_fila("x", 2, "4 vacantes del cargo no le sirven por «modalidad diferente»"),
                                           MINIMO)  # un ajuste del perfil
    assert huecos.es_hueco_por_fuentes(_fila("x", 2, "4 vacantes del cargo no le sirven por «oficina en otro país»: "
                                                     "añadir una ubicación donde trabajaría daría más."), MINIMO)
    assert not huecos.es_hueco_por_fuentes(_fila("x", MINIMO, huecos.CAUSA_POCAS_VACANTES), MINIMO)


def test_las_causas_que_se_leen_existen_en_cobertura():
    """Si `servicio.cobertura` cambia el texto de sus causas, la tabla dejaría de ver huecos: esto lo avisa."""
    fuente = inspect.getsource(servicio.cobertura)
    assert huecos.CAUSA_POCAS_VACANTES in fuente and "oficina en otro país" in servicio.SUGERENCIAS


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
    assert huecos.aviso_al_guardar(antes, despues) == ["Ghana: sin fuente local; riesgo de quedar bajo 5."]
    assert huecos.aviso_al_guardar(None, antes) == ["Kenia: sin fuente local; riesgo de quedar bajo 5."]
    remoto = _cfg({"mundo": PERFILES["mundo"]})
    assert huecos.aviso_al_guardar(None, remoto) == ["Tanzania: sin fuente local; riesgo de quedar bajo 5."]
    archivado = _cfg({"gh": {"vive_en": "GH", "activo": False}})
    assert huecos.aviso_al_guardar(None, archivado) == []


def test_api_avisa_al_guardar_sin_bloquear():
    repo = RepositorioDemo()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    estado = api.get("/api/config").json()
    cfg = estado["borrador"]
    cfg["perfiles"][0] = {**cfg["perfiles"][0], "vive_en": "GH", "ubicaciones": []}
    r = api.put("/api/config", json={"revision": estado["revision"], "configuracion": cfg},
                headers={"Origin": "http://testserver"})
    assert r.status_code == 200, r.text
    assert r.json()["avisos_cobertura"] == ["Ghana: sin fuente local; riesgo de quedar bajo 5."]
    assert api.get("/api/config").json()["borrador"]["perfiles"][0]["vive_en"] == "GH"  # se guardó


def test_api_de_cobertura_trae_la_tabla_de_huecos():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    r = api.get("/api/cobertura").json()
    assert isinstance(r["huecos"], list) and r["huecos"]
    assert {f["estado"] for f in r["huecos"]} <= {"cubierto", "riesgo", "hueco"}
    assert all(set(f) == {"pais", "nombre", "perfiles", "bajo_minimo", "fuentes", "fuentes_locales", "estado", "pedido"}
               for f in r["huecos"])
