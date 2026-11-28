"""P-12.11: «Por confirmar» más rápida, con exactamente el mismo resultado.

C1: la lista ligera de pendientes ya no trae el `resumen` de cada fila y va de 1.000 en 1.000; `listar` pide el resumen
solo de la página que se muestra (1 viaje) y lo deja en la copia en memoria.
C3: «Sirve» ya no lee todo el historial de las personas para saber si ya recibieron esa vacante: pregunta solo por
esa vacante, con una consulta que no crece con los días. Nunca se repite una vacante a una persona."""
from copy import deepcopy

import pytest

from panel import revision
from panel.repositorio import ErrorRepositorio, RepositorioSupabase, configuracion_demo, hoy, ya_recibieron_de
from pruebas.panel.test_recibidas_sin_tope import PostgREST, _historial
from pruebas.panel.test_revision import Repo, _cfg, _fila


@pytest.fixture(autouse=True)
def _bandeja_sin_sugerencias_automaticas(monkeypatch):
    monkeypatch.setattr(revision, "APLICAR_SUGERENCIAS", False)


class ConSelect(PostgREST):
    """El PostgREST falso, que además devuelve solo las columnas simples pedidas en `select` (como el real)."""

    def pedir(self, metodo, ruta, **op):
        filas = super().pedir(metodo, ruta, **op)
        select = str((op.get("params") or {}).get("select") or "*")
        if metodo != "GET" or "*" in select or "(" in select or not isinstance(filas, list):
            return filas
        return [{c: f.get(c) for c in select.split(",")} for f in filas]


class Supabase(RepositorioSupabase):
    """El repositorio real, hablando con el PostgREST falso (sin red ni credenciales)."""

    def __init__(self, postgrest):
        self.pg, self._con_resumen = postgrest, True

    def pedir(self, metodo, ruta, **op):
        return self.pg.pedir(metodo, ruta, **op)


def _bandeja(n):
    """`n` pendientes sintéticas repartidas entre los perfiles de la demostración; 1 de cada 10 sin resumen guardado
    (esas se calculan al mostrarlas con el catálogo, como antes)."""
    cfg = configuracion_demo()
    perfiles = cfg["perfiles"]
    catalogo, filas = [], []
    for i in range(n):
        sin = i % 10 == 3
        vid = f"v{i:05d}"
        if sin:
            c = _fila(i, "Lugar " + str(i % 7))
            vid = c["id"]
            catalogo.append({**c, "status": "archived", "reason": "elegibilidad regional por confirmar"})
        p = perfiles[i % len(perfiles)]
        filas.append({"vacante_id": vid, "estado": "pendiente", "motivo": "elegibilidad regional por confirmar",
                      "pista": "", "ubicacion": "lugar " + str(i % 7), "sugerencia": [], "paises": [],
                      "perfiles": [{"cliente_id": p["cliente_id"], "perfil_id": p["id"], "cargo_id": p["cargo_id"],
                                    "faltan": i % 4 == 0}],
                      "prioridad": (i * 37) % 101, "creada_en": "2026-11-28T10:00:00+00:00",
                      "resumen": None if sin else {"titulo": f"Cargo {i}", "empresa": f"Empresa {i}",
                                                   "ubicacion": "Remote", "frase": f"Frase {i}", "paises": [],
                                                   "paises_sugeridos": ["CO"], "enlace": f"https://example.org/{i}"}})
    return {"panel_revisiones": filas, "catalogo_vacantes": catalogo}, {"revision": 1, "configuracion": cfg}


def _lecturas(pg, tabla):
    return [p for t, p in pg.lecturas if t == tabla]


def test_la_lista_ligera_no_trae_el_resumen_y_va_de_mil_en_mil():
    tablas, _ = _bandeja(2500)
    pg = ConSelect(tablas)
    filas = Supabase(pg).revisiones(estado="pendiente", ligera=True)
    assert len(filas) == 2500 and all("resumen" not in f for f in filas)
    paginas = _lecturas(pg, "panel_revisiones")
    assert len(paginas) == 4 and {p["limit"] for p in paginas} == {1000}  # 3 con filas + la vacía que cierra
    assert all("resumen" not in p["select"] and "catalogo" not in p["select"] for p in paginas)


@pytest.mark.parametrize("pagina,cliente", [(1, False), (2, False), (1, True), (None, False)])
def test_listar_da_la_misma_salida_que_con_el_resumen_en_la_lista(pagina, cliente):
    tablas, version = _bandeja(2500)
    cliente_id = version["configuracion"]["clientes"][1]["id"] if cliente else None
    # Como hasta hoy: las pendientes completas (con su resumen), por páginas ordenadas por vacante y luego por prioridad.
    antes = sorted(sorted(deepcopy(tablas["panel_revisiones"]), key=lambda r: r["vacante_id"]),
                   key=lambda r: -(r.get("prioridad") or 0))
    esperado = revision.listar(Supabase(ConSelect(deepcopy(tablas))), hoy(), pagina=pagina, cliente_id=cliente_id,
                               todas=antes, version=version)
    pg = ConSelect(tablas)
    repo = Supabase(pg)
    todas = repo.revisiones(estado="pendiente", ligera=True)
    pg.lecturas.clear()
    assert revision.listar(repo, hoy(), pagina=pagina, cliente_id=cliente_id, todas=todas, version=version) == esperado
    resumenes = _lecturas(pg, "panel_revisiones")
    assert len(resumenes) == 1 and resumenes[0]["select"] == "vacante_id,resumen"  # 1 viaje, solo la página
    assert len(resumenes[0]["vacante_id"].split(",")) == len(esperado["pendientes"])
    pg.lecturas.clear()  # volver a la misma página no lo pide otra vez: queda en la copia en memoria
    assert revision.listar(repo, hoy(), pagina=pagina, cliente_id=cliente_id, todas=todas, version=version) == esperado
    assert _lecturas(pg, "panel_revisiones") == []


def test_la_demostracion_lee_el_resumen_de_la_pagina_igual():
    """El repositorio de demostración también responde `leer_resumenes` (aquí su lista ligera lo omite)."""
    tablas, version = _bandeja(60)

    class Demo(Repo):
        def revisiones(self, estado=None, vacante_id=None, ligera=False):
            filas = super().revisiones(estado, vacante_id, ligera)
            return [{k: v for k, v in f.items() if k != "resumen"} for f in filas] if ligera else filas

    r = Demo([{**c, "status": "archived"} for c in tablas["catalogo_vacantes"]])
    del_catalogo = {c["id"]: c for c in tablas["catalogo_vacantes"]}
    r.estado["revisiones"] = [{**f, **({"catalogo_vacantes": del_catalogo[f["vacante_id"]]}
                                       if f["vacante_id"] in del_catalogo else {})}
                              for f in deepcopy(tablas["panel_revisiones"])]
    esperado = revision.listar(r, hoy(), pagina=1, todas=sorted(deepcopy(r.estado["revisiones"]),
                                                               key=lambda x: -(x.get("prioridad") or 0)),
                               version=version)
    assert revision.listar(r, hoy(), pagina=1, version=version) == esperado


# C3: «¿ya la recibieron?» por vacante, sin leer el historial.

def test_ya_recibieron_es_una_consulta_acotada_que_no_crece_con_el_historial():
    vista, otra = "ya-la-vio", "nunca-la-vio"
    for total in (10, 12_000):
        pg = PostgREST({"panel_asignaciones": _historial("p1", [vista], total) + _historial("p2", [], total)})
        assert ya_recibieron_de(pg.pedir, ["p1", "p2"], otra) == set()
        assert len(pg.lecturas) == 1  # nadie la tiene: 1 viaje, con 10 o con 12.000 previas
        assert ya_recibieron_de(pg.pedir, ["p1", "p2"], vista) == {"p1"}
        assert len(pg.lecturas) == 3  # alguien la tiene: 2 viajes (el segundo, vacío, cierra la lectura)
        for _, params in pg.lecturas:
            assert params["perfil_id"] == "in.(p1,p2)" and params["vacante_id"].startswith("eq.")
            assert params["select"] == "id,perfil_id" and params["order"] == "id" and params["limit"] == 1000


def test_ya_recibieron_no_se_corta_si_supabase_da_menos_filas_de_las_pedidas():
    """Como en P-12.1: una respuesta corta (el `max-rows` de Supabase) no es el final; solo una página vacía."""
    filas = [{"id": f"a{n}", "perfil_id": "p1", "vacante_id": "x"} for n in range(3)]
    filas.append({"id": "a9", "perfil_id": "p2", "vacante_id": "x"})
    pg = PostgREST({"panel_asignaciones": filas}, max_filas=2)
    assert ya_recibieron_de(pg.pedir, ["p1", "p2"], "x") == {"p1", "p2"}  # la primera respuesta traía solo p1


def test_ya_recibieron_con_una_respuesta_rara_es_un_error():
    with pytest.raises(ErrorRepositorio):
        ya_recibieron_de(lambda *a, **k: None, ["p1"], "x")


def _pendiente(perfiles_previos=None):
    """Una pendiente de la bandeja para los perfiles activos de la demostración, con las asignaciones anteriores en un
    PostgREST falso (12.000 por persona)."""
    cfg, _ = _cfg()
    fila = _fila(1, "Lugar Ejemplo")

    class R(Repo):
        def recibidas(self, perfil_ids):
            raise AssertionError("«Sirve» ya no lee todo el historial")

        def ya_recibieron(self, perfil_ids, vacante_id):
            return ya_recibieron_de(self.pg.pedir, perfil_ids, vacante_id)

    r = R([fila])
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles}, recibidas={str(p.id): set()
                                                                                         for p in cfg.perfiles})
    rev = r.revisiones(estado="pendiente")[0]
    ids = [p["perfil_id"] for p in rev["perfiles"]]
    previos = perfiles_previos(ids) if perfiles_previos else []
    r.pg = PostgREST({"panel_asignaciones": [a for i in ids
                                             for a in _historial(i, [rev["vacante_id"]] if i in previos else [])]})
    return r, rev["vacante_id"], previos


def test_sirve_con_doce_mil_previas_no_repite_y_no_lee_el_historial():
    r, vid, previos = _pendiente(lambda ids: ids[:1])
    resultado = revision.decidir(r, vid, "sirve", ["CO"], regenerar=False)
    nuevas = {a["perfil_id"] for a in r.estado.get("asignaciones_extra", []) if a["vacante_id"] == vid}
    assert previos and not nuevas & set(previos)  # quien ya la tenía no la recibe otra vez
    assert resultado["asignadas"] == len(nuevas)
    lecturas = [p for t, p in r.pg.lecturas if t == "panel_asignaciones"]
    assert len(lecturas) == 2 and all(p["vacante_id"] == "eq." + vid for p in lecturas)


def test_sirve_asigna_a_quien_no_la_tenia():
    r, vid, _ = _pendiente()
    asignadas = revision.decidir(r, vid, "sirve", ["CO"], regenerar=False)["asignadas"]
    nuevas = [a["perfil_id"] for a in r.estado.get("asignaciones_extra", []) if a["vacante_id"] == vid]
    assert asignadas >= 1 and asignadas == len(nuevas) == len(set(nuevas))
    assert len([p for t, p in r.pg.lecturas if t == "panel_asignaciones"]) == 1


def test_si_no_se_puede_saber_quien_la_tiene_no_se_asigna():
    r, vid, _ = _pendiente()

    def error():
        raise ErrorRepositorio()
    r.pg.fallar = lambda ruta, params: error
    with pytest.raises(ErrorRepositorio):
        revision.decidir(r, vid, "sirve", ["CO"], regenerar=False)
    assert not r.estado.get("asignaciones_extra")
    assert r.revisiones(vacante_id=vid)[0]["estado"] == "pendiente"  # sigue en la bandeja para decidirla luego
