"""Contrato v49: errores que encontró la revisión «thermos» de la rama, cada uno con la prueba que lo habría detectado."""
from copy import deepcopy

from fastapi.testclient import TestClient

from buscador import familias, paises, vacante
from panel import ejecutor
from panel.afinidad import evaluar
from panel.api import crear_app
from panel.modelos import Perfil
from panel.repositorio import ErrorRepositorio, hoy
from pruebas.panel.test_buscar_ahora import H, GitHubAnotado, _cliente_con_perfiles, _repo_pedido
from pruebas.panel.test_espanol_v49 import _vacante
from pruebas.panel.test_espanol_v49 import cfg  # noqa: F401 — un perfil solo español con meta de 8
from pruebas.panel.test_rescate_v36 import Repo
from pruebas.panel.test_ubicacion_v49 import BASE, guardada, leida, perfil, sirve


# 1 ── Juntar dos copias de una vacante «otro_oficio» tumbaba la búsqueda de la noche ───────────────────────────────
def test_juntar_copias_con_el_grado_otro_oficio_no_falla():
    assert familias.ORDEN_GRADOS == ["exacto", "similar", "cercano", "funciones", "otro_oficio"]
    a = _vacante(1)
    a["familias"] = [{"familia": "cargo:x", "coincidencia": "otro_oficio"}]
    b = deepcopy(a)
    b["familias"] = [{"familia": "cargo:x", "coincidencia": "otro_oficio"}, {"familia": "cargo:y", "coincidencia": "similar"}]
    unida = vacante.unir(a, b)  # antes: ValueError: 'otro_oficio' is not in list
    assert unida["familias"] == [{"familia": "cargo:y", "coincidencia": "similar"},
                                 {"familia": "cargo:x", "coincidencia": "otro_oficio"}]
    assert len(vacante.juntar([a, b])) == 1
    # Si otra copia la reconoce como del cargo, gana el grado más fuerte.
    b["familias"] = [{"familia": "cargo:x", "coincidencia": "exacto"}]
    assert vacante.unir(a, b)["familias"] == [{"familia": "cargo:x", "coincidencia": "exacto"}]


# 2 ── Cada pasada del día volvía a completar desde cero (17, 33, 49…) ───────────────────────────────────────────────
class RepoDelDia(Repo):
    """Como el de v36, pero recuerda lo asignado entre pasadas del mismo día (igual que Supabase)."""
    def asignadas_de(self, ejecucion_id):
        salida = {}
        for a in self.asignaciones:
            salida.setdefault(a["perfil_id"], set()).add(a["vacante_id"])
        return salida

    def pedir(self, metodo, ruta, **op):
        if ruta == "panel_asignaciones" and metodo == "GET":
            return [{"perfil_id": a["perfil_id"], "vacante_id": a["vacante_id"]} for a in self.asignaciones] \
                if not (op.get("params") or {}).get("offset") else []
        return super().pedir(metodo, ruta, **op)


def test_varias_pasadas_del_dia_no_pasan_de_la_meta_ni_del_techo(cfg):  # noqa: F811
    p = cfg["perfiles"][0]  # meta de 8
    bodega = [_vacante(n) for n in range(1, 41)]
    repo = RepoDelDia()
    totales = []
    for _ in range(4):  # 6:30, 8:30, la de cada hora y un «Buscar ahora»
        ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy(), vacantes=bodega, cache_enlaces={})
        totales.append(len({a["vacante_id"] for a in repo.asignaciones if a["perfil_id"] == p["id"]}))
    assert totales == [8, 8, 8, 8]  # antes: 8, 16, 24, 32


def test_lo_ya_asignado_hoy_cuenta_para_la_meta_y_para_el_techo(cfg):  # noqa: F811
    from panel.modelos import Configuracion
    cfg["techo_diario"] = 10
    c = Configuracion.model_validate(cfg)
    p = next(x for x in c.perfiles if x.activo)
    filas = [{"perfil_id": str(p.id), "vacante_id": "l1"}]
    completar = ejecutor.Completar(c, {p.id: 1}, filas, ["l1"], {str(p.id): {"l1", "r1", "r2", "r3"}})
    assert completar.estrictas[p.id] == 4 and completar.falta(p) == 4  # 1 del lote + 3 de pasadas anteriores
    assert completar.libre == 6 and completar.usadas == {"l1", "r1", "r2", "r3"}
    assert ejecutor.Completar(c, {p.id: 1}, filas, ["l1"]).falta(p) == 7  # sin pasadas anteriores, como antes


def test_si_no_se_puede_leer_lo_de_hoy_solo_se_completa_el_minimo(cfg):  # noqa: F811
    class RepoRoto(Repo):
        def asignadas_de(self, ejecucion_id):
            raise ErrorRepositorio("sin conexión", 503)
    repo = RepoRoto()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy(), vacantes=[_vacante(n) for n in range(1, 21)],
                       cache_enlaces={})
    assert len(repo.asignaciones) == 5  # prudente: nunca de más por un dato que falta


# 3 ── Un «Buscar ahora» rechazado no pisa el pedido que ya está en cola ────────────────────────────────────────────
def test_un_pedido_rechazado_conserva_el_que_ya_estaba_en_cola():
    cid, suyos, _ = _cliente_con_perfiles()

    class GitHubOcupado(GitHubAnotado):
        def lanzar(self, enfoque="completo"):
            raise ErrorRepositorio("Ya hay una búsqueda en curso.", 409)
    repo = _repo_pedido([], {})
    en_cola = {"fecha": hoy(), "perfiles": ["perfil-del-primer-cliente"]}
    repo.guardar_ajuste("busqueda_pedida", en_cola)
    api = TestClient(crear_app(demo=True, repositorio=repo, acciones=GitHubOcupado()))
    assert api.post("/api/busqueda", json={"cliente_id": cid}, headers=H).status_code == 409
    assert repo.ajuste("busqueda_pedida") == en_cola  # antes quedaban los perfiles del segundo cliente


# 4 y 5 ── «Anywhere in LATAM» sigue abierta a LATAM; «cualquier parte del mundo» sigue siendo mundial ───────────────
def test_anywhere_in_una_region_sigue_abierta_a_la_region():
    for ubicacion in ("Anywhere in LATAM", "Remote - Anywhere in Latin America", "Remote (Anywhere in South America)"):
        v = leida(ubicacion, remoto=True)
        assert "CO" in v["paises"] and not v["alcance_mundial"], ubicacion
        assert sirve(v, perfil("CO")) and not sirve(v, perfil("US")), ubicacion


def test_cualquier_parte_del_mundo_es_mundial():
    for ubicacion in ("Remoto desde cualquier parte del mundo", "Remote - Anywhere in the world",
                      "Anywhere across the globe"):
        assert not paises.mundo_acotado(ubicacion), ubicacion
    v = leida("Remoto desde cualquier parte del mundo", remoto=True)
    assert v["alcance_mundial"] and v["confianza_pais"] == "alta" and sirve(v, perfil("CO")) and sirve(v, perfil("DE"))
    assert paises.mundo_acotado("Remoto en cualquier parte de México")


# 6 y 9 ── «work from anywhere in the US» no abre el aviso; «US-based role» y «(USA-based)» restringen ──────────────
def test_anywhere_in_the_us_en_la_descripcion_no_abre_a_latam():
    texto = "In this US-based fully remote role you can work from anywhere in the US. " * 4
    r = paises.elegibles("Marketing Manager", "Remote, USA", texto, True)
    assert r["paises"] == [] and r["nota"] != "contratación remota explícita", r
    v = leida("Remote, USA", texto, remoto=True)
    assert not sirve(v, perfil("CO")) and sirve(v, perfil("US"))
    # El caso legítimo no cambia: «work from anywhere» a secas sí es para cualquier país.
    libre = paises.elegibles("Marketing Manager", "Remote", "You can work from anywhere. " * 8, True)
    assert "CO" in libre["paises"]


def test_anywhere_in_una_region_en_la_descripcion_vale_para_esa_region():
    def paises_de(frase, ubicacion="Venezuela"):
        return set(paises.elegibles("Full Stack Software Engineer", ubicacion, (frase + " ") * 6, True)["paises"])
    latam = paises_de("This is a remote role: work from anywhere in LATAM or Europe with a professional setup.")
    assert {"CO", "MX", "AR", "VE"} <= latam  # antes de este arreglo quedaba solo para Venezuela
    assert {"MX", "CO", "AR"} <= paises_de("You can work from anywhere in Mexico or South America.")
    assert paises_de("Work from anywhere in Europe as long as your contract allows it.", "Madrid") == {"ES"}
    assert paises_de("Work from anywhere in India, long term.", "Remote") == set()
    # Un lugar que no se reconoce no decide: manda la ubicación del aviso.
    assert paises_de("You can work from anywhere in your country of residence.") == {"VE"}


def test_usa_based_en_el_titulo_restringe():
    r = paises.elegibles("Product Manager - Patient Experience (USA-based)", "Remote", "", True)
    assert r["paises"] == [] and r["confianza"] == "alta", r


# 7 ── Perfil anterior: la ciudad con una homónima mayor en otro país no pierde la suya ─────────────────────────────
def test_perfil_anterior_conserva_su_ciudad_aunque_haya_otra_mayor_con_el_mismo_nombre():
    p = Perfil.model_validate({**BASE, "vive_en": "ES", "modalidades": ["hibrido", "presencial"],
                               "ciudades": ["Mérida", "Guadalajara"]})
    assert p.filas[0].paises == ["ES"] and p.filas[0].ciudades == ["Mérida", "Guadalajara"]
    merida = guardada("hibrido", ["ES"], ubicacion="Mérida, Extremadura, España")
    assert evaluar(merida, p, hoy())["compatible"]  # antes: «falta la ciudad en el perfil»
    assert sirve(guardada("presencial", ["ES"], ubicacion="Guadalajara, Castilla-La Mancha, España"), p)
    assert not sirve(guardada("presencial", ["ES"], ubicacion="Sevilla, Andalucía, España"), p)
