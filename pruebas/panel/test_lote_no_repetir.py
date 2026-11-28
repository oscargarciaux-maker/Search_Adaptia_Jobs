"""P-12.15: el lote del día no vuelve a dar a una persona una vacante que ya recibió por otro camino.

El lote (`entregas_diarias`) solo excluye lo que ya entró a algún lote. Una vacante que la persona recibió por el
rescate («completar a quien va corto con toda la bodega»), por un post o por «Sirve» de «Por confirmar» no queda en
`entregas_diarias`, así que podía entrar a un lote posterior y asignarse otra vez a la misma persona: aparecía de nuevo
en el panel y en el CSV. Ahora el lote también mira lo que cada persona ya recibió (la misma lectura de la P-12.1)."""
from uuid import NAMESPACE_URL, uuid5

from panel import revision
from panel.repositorio import hoy
from pruebas.panel.test_recibidas_sin_tope import PostgREST, _vacante, cfg, registrar  # noqa: F401 (fixtures)


HOY = "e1"  # el id que el PostgREST falso da a la ejecución de hoy


def _asignacion(perfil_id, vacante_id, ejecucion_id="ayer"):
    return {"id": str(uuid5(NAMESPACE_URL, f"{ejecucion_id}-{perfil_id}-{vacante_id}")), "ejecucion_id": ejecucion_id,
            "perfil_id": perfil_id, "vacante_id": vacante_id}


def _del_lote(cfg, v, cargo=0):
    return {"vacante_id": v["id"], "delivery_date": hoy(), "role_id": "cargo:" + cfg["cargos"][cargo]["id"],
            "match_grade": "exact", "snapshot": v}


class ConPasadas(PostgREST):
    """Como Supabase, con lo asignado en las pasadas anteriores de hoy (`asignadas_de`, contrato v49)."""
    def asignadas_de(self, ejecucion_id):
        salida = {}
        for a in self.tablas.get("panel_asignaciones", []):
            if a.get("ejecucion_id") == ejecucion_id:
                salida.setdefault(a["perfil_id"], set()).add(a["vacante_id"])
        return salida


def _de(repo, perfil_id):
    return [a["vacante_id"] for a in repo.asignadas if a["perfil_id"] == perfil_id]


def test_rescatada_ayer_no_vuelve_en_el_lote_de_hoy(cfg, registrar):
    p = cfg["perfiles"][0]
    rescatada, nueva = _vacante(1), _vacante(2)
    repo = ConPasadas({"panel_asignaciones": [_asignacion(p["id"], rescatada["id"])],
                       "entregas_diarias": [_del_lote(cfg, rescatada), _del_lote(cfg, nueva)]})
    registrar(repo, cfg, [])
    assert _de(repo, p["id"]) == [nueva["id"]]  # antes: la rescatada de ayer volvía a asignársele
    assert repo.ejecucion["resumen"]["lote_ya_recibidas"] == 1


def test_tampoco_si_el_lote_la_trae_fusionada_con_otro_id(cfg, registrar):
    """La misma oferta de otro portal puede entrar al lote con otro id y la recibida entre sus `_ids_fusionados`."""
    p = cfg["perfiles"][0]
    recibida, fusionada = _vacante(1), _vacante(3)
    fusionada["_ids_fusionados"] = sorted({recibida["id"], fusionada["id"]})
    repo = ConPasadas({"panel_asignaciones": [_asignacion(p["id"], recibida["id"])],
                       "entregas_diarias": [_del_lote(cfg, fusionada)]})
    registrar(repo, cfg, [])
    assert _de(repo, p["id"]) == []


def test_otra_persona_si_la_recibe_en_el_lote(cfg, registrar):
    """Se mira por persona: que otro cliente ya la tuviera no le quita el lote a quien nunca la recibió."""
    cfg["perfiles"][1].update(cfg["perfiles"][0], id=cfg["perfiles"][1]["id"], cliente_id=cfg["perfiles"][1]["cliente_id"],
                              activo=True)
    p, otro = cfg["perfiles"][0], cfg["perfiles"][1]
    rescatada = _vacante(1)
    repo = ConPasadas({"panel_asignaciones": [_asignacion(p["id"], rescatada["id"])],
                       "entregas_diarias": [_del_lote(cfg, rescatada)]})
    registrar(repo, cfg, [])
    assert _de(repo, p["id"]) == [] and _de(repo, otro["id"]) == [rescatada["id"]]


def test_lo_de_las_pasadas_anteriores_de_hoy_se_vuelve_a_registrar(cfg, registrar):
    """En la misma ejecución del día no es una repetición (la fila ya existe y la base ignora la copia): la vacante del
    lote se vuelve a registrar como siempre y sigue contando para la meta, el techo y Comunidad."""
    p = cfg["perfiles"][0]
    del_lote = _vacante(1)
    repo = ConPasadas({"panel_asignaciones": [_asignacion(p["id"], del_lote["id"], ejecucion_id=HOY)],
                       "entregas_diarias": [_del_lote(cfg, del_lote)]})
    registrar(repo, cfg, [])
    assert _de(repo, p["id"]) == [del_lote["id"]]
    assert repo.ejecucion["resumen"]["lote_ya_recibidas"] == 0


def test_sin_las_pasadas_de_hoy_no_se_arriesga_a_repetir(cfg, registrar):
    """Si no se pudo leer lo de hoy, todo lo ya recibido queda fuera del lote: puede faltar volver a registrar una
    copia, pero nunca se repite una vacante de otro día."""
    p = cfg["perfiles"][0]
    rescatada = _vacante(1)

    class SinPasadas(PostgREST):
        def asignadas_de(self, ejecucion_id):
            raise RuntimeError("sin conexión")
    repo = SinPasadas({"panel_asignaciones": [_asignacion(p["id"], rescatada["id"])],
                       "entregas_diarias": [_del_lote(cfg, rescatada)]})
    registrar(repo, cfg, [])
    assert _de(repo, p["id"]) == []


def test_sin_las_pasadas_de_hoy_no_se_completa_de_mas(cfg, registrar):
    """Lo saltado sin saber si era de hoy cuenta para la meta: no se le dan otras tantas nuevas (antes, al volver a
    registrarse, contaba igual)."""
    p = cfg["perfiles"][0]
    p["meta_diaria"] = 5
    del_lote = [_vacante(n) for n in range(5)]
    bodega = [_vacante(n) for n in range(10, 15)]

    class SinPasadas(PostgREST):
        def asignadas_de(self, ejecucion_id):
            raise RuntimeError("sin conexión")
    repo = SinPasadas({"panel_asignaciones": [_asignacion(p["id"], v["id"], ejecucion_id=HOY) for v in del_lote],
                       "entregas_diarias": [_del_lote(cfg, v) for v in del_lote]})
    registrar(repo, cfg, bodega)
    assert _de(repo, p["id"]) == [] and repo.ejecucion["resumen"]["rescatadas"] == 0


def test_la_misma_oferta_fusionada_hoy_no_llega_dos_veces(cfg, registrar):
    """Si una pasada anterior de hoy le dio X y el lote trae Y con X entre sus fusionadas, Y no se asigna."""
    p = cfg["perfiles"][0]
    x, y = _vacante(1), _vacante(3)
    y["_ids_fusionados"] = sorted({x["id"], y["id"]})
    repo = ConPasadas({"panel_asignaciones": [_asignacion(p["id"], x["id"], ejecucion_id=HOY)],
                       "entregas_diarias": [_del_lote(cfg, y)]})
    registrar(repo, cfg, [])
    assert _de(repo, p["id"]) == []


def test_una_sola_lectura_tambien_para_por_confirmar(cfg, registrar, monkeypatch):
    """La bandeja «Por confirmar» usa la misma lectura de lo recibido (antes hacía una segunda en cada corrida)."""
    p = cfg["perfiles"][0]
    rescatada = _vacante(1)
    recibio = {}

    def cola(repo, cfg, fecha, estrictas, filas_hoy=(), recibidas=None, **_):
        recibio["recibidas"] = recibidas
        return {"por_confirmar": 0}
    monkeypatch.setattr(revision, "preparar_cola", cola)

    class ConBandeja(ConPasadas):
        def candidatas_por_confirmar(self, desde):
            return []
    repo = ConBandeja({"panel_asignaciones": [_asignacion(p["id"], rescatada["id"])],
                       "entregas_diarias": [_del_lote(cfg, rescatada)]})
    registrar(repo, cfg, [])
    primeras = [params for ruta, params in repo.lecturas
                if ruta == "panel_asignaciones" and "perfil_id" in params and "id" not in params]
    assert len(primeras) == 1
    assert rescatada["id"] in recibio["recibidas"][p["id"]]


def test_preparar_cola_usa_lo_recibido_que_le_pasan_sin_cambiarlo(monkeypatch):
    from pruebas.panel.test_revision import Repo, _cfg, _fila
    monkeypatch.setattr(revision, "APLICAR_SUGERENCIAS", False)
    config, _ = _cfg()
    candidata = _fila(1, "Remote Remoto 1")

    class SinLeer(Repo):
        def recibidas(self, perfil_ids):
            raise AssertionError("una segunda lectura de lo recibido")
    ya = {str(p.id): {candidata["id"]} for p in config.perfiles}
    copia = {k: set(v) for k, v in ya.items()}
    r = SinLeer([candidata])
    revision.preparar_cola(r, config, hoy(), {p.id: 0 for p in config.perfiles},
                           [{"perfil_id": str(config.perfiles[0].id), "vacante_id": "otra"}], recibidas=ya)
    assert r.revisiones(estado="pendiente") == [] and ya == copia  # ya la recibieron todos; lo pasado no cambia
    r = Repo([candidata])
    revision.preparar_cola(r, config, hoy(), {p.id: 0 for p in config.perfiles}, recibidas={})
    assert [x["vacante_id"] for x in r.revisiones(estado="pendiente")] == [candidata["id"]]


def test_preparar_cola_lee_solo_a_quien_falta_en_lo_recibido(monkeypatch):
    """Una persona sin entrada nunca se toma como «no recibió nada»: se lee su historial (solo el suyo)."""
    from pruebas.panel.test_revision import Repo, _cfg, _fila
    monkeypatch.setattr(revision, "APLICAR_SUGERENCIAS", False)
    config, _ = _cfg()
    candidata = _fila(1, "Remote Remoto 1")
    pedidas = []

    class Cuenta(Repo):
        def recibidas(self, perfil_ids):
            pedidas.append(list(perfil_ids))
            return {i: {candidata["id"]} for i in perfil_ids}
    ids = list(dict.fromkeys(str(p.id) for c in config.cargos if c.activo for p in config.perfiles_activos(str(c.id))))
    r = Cuenta([candidata])
    revision.preparar_cola(r, config, hoy(), {p.id: 0 for p in config.perfiles},
                           recibidas={i: {candidata["id"]} for i in ids[1:]})
    assert pedidas == [ids[:1]] and r.revisiones(estado="pendiente") == []
