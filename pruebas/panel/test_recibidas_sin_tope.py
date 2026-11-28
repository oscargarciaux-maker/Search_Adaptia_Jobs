"""P-12.1: «lo que ya recibió» cada persona se lee completo, ordenado y una sola vez por corrida.

Antes `ejecutor._paginas` pedía páginas con OFFSET, sin orden, y se detenía en 5.000 filas sin avisar (y una página
vacía o nula también cortaba en silencio): con más historial, una persona podía recibir otra vez una vacante que ya
tuvo. Ahora la lectura es por clave (keyset) y sin tope; si no termina bien, ese día no se completa a nadie."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import pytest

from buscador import familias, vacante
from panel import ejecutor
from panel.repositorio import ErrorRepositorio, configuracion_demo, hoy, paginar

TEXTO = ("We are hiring a Product Designer for our product team. You will run user research, design flows in Figma "
         "and work with engineering every day. ") * 3


def _vacante(n):
    v = vacante.crear("Product Designer", f"Empresa {n}", f"https://jobs.lever.co/e/r-{n}", "Lever",
                      ubicacion="Chicago, IL", descripcion=TEXTO, fecha=hoy(), hoy=hoy(), remoto=None)
    ahora = datetime.now(timezone.utc).isoformat()
    v["verificacion"] = {"estado": "verificada",
                         "enlaces": [{"url": v["enlace"], "estado": "verificada", "comprobada_en": ahora}]}
    v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
    return v


@pytest.fixture
def cfg():
    c = configuracion_demo()
    for p in c["perfiles"][1:]:
        p["activo"] = False
    c["perfiles"][0].update(vive_en="US", modalidades=["remoto", "hibrido", "presencial"], ciudades=["Chicago"],
                            idiomas=["es", "en"], ingles_maximo="native", ubicaciones=[])
    return c


def _cumple(valor, filtro):
    operador, _, dato = str(filtro).partition(".")
    valor = "" if valor is None else str(valor)
    if operador == "in":
        return valor in dato.strip("()").split(",")
    return {"eq": valor == dato, "gt": valor > dato, "gte": valor >= dato, "lt": valor < dato}[operador]


class PostgREST:
    """Supabase mínimo que respeta filtros, `order`, `limit` y `offset` como PostgREST. Sin `order` devuelve las filas
    en el orden en que se guardaron (como PostgreSQL, sin garantía)."""
    ESPECIALES = {"select", "order", "limit", "offset", "on_conflict"}

    def __init__(self, tablas, fallar=None):
        self.tablas, self.fallar, self.ejecucion, self.asignadas, self.lecturas = tablas, fallar, None, [], []

    def pedir(self, metodo, ruta, **op):
        params = dict(op.get("params") or {})
        if ruta == "panel_ejecuciones":
            if metodo == "POST":
                self.ejecucion = {"id": "e1", **op["json"]}
            elif metodo == "PATCH":
                self.ejecucion.update(op["json"])
            return [self.ejecucion] if self.ejecucion else []
        if metodo == "POST" and ruta == "panel_asignaciones":
            self.asignadas.extend(op["json"])
            return []
        if metodo != "GET":
            return []
        self.lecturas.append((ruta, params))
        if self.fallar and self.fallar(ruta, params):
            return self.fallar(ruta, params)()
        filas = [f for f in self.tablas.get(ruta, [])
                 if all(_cumple(f.get(k), v) for k, v in params.items() if k not in self.ESPECIALES and "->" not in k)]
        for parte in reversed([p for p in str(params.get("order") or "").split(",") if p]):
            columna, _, sentido = parte.partition(".")
            filas = sorted(filas, key=lambda f: str(f.get(columna) or ""), reverse=sentido == "desc")
        inicio = int(params.get("offset") or 0)
        return filas[inicio:inicio + int(params["limit"])] if "limit" in params else filas[inicio:]


def _historial(perfil_id, ya_recibidas, total=12_000):
    """`total` asignaciones anteriores de una persona; las que importan quedan al final del orden de guardado (más
    allá de la fila 5.000) y con `id` (uuid) en cualquier lugar del orden por clave."""
    relleno = [f"{n:016x}" for n in range(total - len(ya_recibidas))]
    return [{"id": str(uuid5(NAMESPACE_URL, f"asignacion-{n}")), "perfil_id": perfil_id, "vacante_id": v}
            for n, v in enumerate(relleno + list(ya_recibidas))]


def _registrar(repo, cfg, bodega):
    original = ejecutor._rescatar

    def rescatar(*a, **k):  # sin red: todas las de la bodega ya tienen el enlace comprobado hoy
        return original(*a, **{**k, "comprobar": lambda *_, **__: None, "subir": lambda filas: None})
    ejecutor._rescatar = rescatar
    try:
        ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy(), vacantes=bodega, cache_enlaces={})
    finally:
        ejecutor._rescatar = original


def test_doce_mil_asignaciones_anteriores_no_repiten_ninguna(cfg):
    p = cfg["perfiles"][0]
    bodega = [_vacante(n) for n in range(6)]
    nueva = _vacante(99)  # la única que nunca recibió
    repo = PostgREST({"panel_asignaciones": _historial(p["id"], [v["id"] for v in bodega])})
    _registrar(repo, cfg, bodega + [nueva])
    ids = [a["vacante_id"] for a in repo.asignadas if a["perfil_id"] == p["id"]]
    assert ids == [nueva["id"]]  # con el tope de 5.000, las 6 de la bodega volvían a llegarle
    assert repo.ejecucion["resumen"]["rescatadas"] == 1


def test_recibidas_se_pide_una_sola_vez_por_corrida(cfg):
    p = cfg["perfiles"][0]
    repo = PostgREST({"panel_asignaciones": _historial(p["id"], [], total=3)})
    _registrar(repo, cfg, [_vacante(n) for n in range(3)])
    lecturas = [params for ruta, params in repo.lecturas if ruta == "panel_asignaciones" and "perfil_id" in params]
    assert len(lecturas) == 1  # antes: una en reutilizar, otra en el rescate y otra en los posts
    assert lecturas[0]["order"] == "id" and "id" in lecturas[0]["select"].split(",")
    assert repo.ejecucion["resumen"]["rescatadas"] == 3  # lo asignado por un paso lo ve el siguiente: sin repetir


@pytest.mark.parametrize("fallo", ["nula", "error"])
def test_una_lectura_que_falla_a_mitad_no_deja_completar(cfg, capsys, fallo):
    p = cfg["perfiles"][0]
    bodega = [_vacante(n) for n in range(6)]
    hoy_rows = [{"vacante_id": "h000000000000001", "delivery_date": hoy(), "role_id": "cargo:" + cfg["cargos"][0]["id"],
                 "match_grade": "exact", "snapshot": dict(_vacante(50), id="h000000000000001")}]

    def segunda_pagina(ruta, params):  # la segunda página se pierde (respuesta vacía del servidor o error de red)
        if ruta == "panel_asignaciones" and (params.get("offset") or str(params.get("id", "")).startswith("gt.")):
            if fallo == "nula":
                return lambda: None

            def error():
                raise ErrorRepositorio()
            return error
        return None
    repo = PostgREST({"panel_asignaciones": _historial(p["id"], [v["id"] for v in bodega]),
                      "entregas_diarias": hoy_rows}, fallar=segunda_pagina)
    _registrar(repo, cfg, bodega)
    ids = [a["vacante_id"] for a in repo.asignadas if a["perfil_id"] == p["id"]]
    assert ids == ["h000000000000001"]  # lo del día se registra; nada se completa con un historial a medias
    resumen = repo.ejecucion["resumen"]
    assert resumen["rescatadas"] == resumen["reutilizadas"] == resumen["posts"] == 0
    err = capsys.readouterr().err
    assert "[aviso] ejecutor:recibidas" in err and "hoy no se completa a nadie" in err
    assert p["id"] not in err and p["cliente_id"] not in err  # el aviso no lleva datos de clientes


def test_el_lote_del_dia_se_lee_completo_aunque_pase_de_500(cfg):
    """Antes `registrar` pedía el lote del día con `limit: 500` y el techo llega a 600."""
    filas = [{"vacante_id": f"{n:016x}", "delivery_date": hoy(), "role_id": "otro", "match_grade": "exact",
              "snapshot": {}} for n in range(600)]
    repo = PostgREST({"entregas_diarias": filas})
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    del_dia = [params for ruta, params in repo.lecturas
               if ruta == "entregas_diarias" and params.get("delivery_date") == "eq." + hoy()]
    assert len(del_dia) == 2 and del_dia[1]["vacante_id"] == "gt." + filas[499]["vacante_id"]


# ── paginar: nunca una lectura a medias en silencio ────────────────────────────────────────────────────────────────

def test_paginar_lee_todo_en_orden_de_clave():
    filas = [{"id": f"{n:04d}"} for n in reversed(range(1234))]
    repo = PostgREST({"t": filas})
    assert [f["id"] for f in paginar(repo.pedir, "t", "id", {"select": "id"}, 100)] == sorted(f["id"] for f in filas)
    assert len(repo.lecturas) == 13 and all("offset" not in params for _, params in repo.lecturas)


def test_paginar_agrega_la_clave_a_la_seleccion():
    repo = PostgREST({"t": [{"id": "1", "x": 1}]})
    list(paginar(repo.pedir, "t", "id", {"select": "x"}))
    assert repo.lecturas[0][1]["select"] == "x,id"


@pytest.mark.parametrize("respuesta", [None, {"mensaje": "no es una lista"}, [{"id": "1"}] * 3])
def test_paginar_falla_con_una_respuesta_inesperada(respuesta):
    with pytest.raises(ErrorRepositorio):
        list(paginar(lambda *a, **k: respuesta, "t", "id", {}, 2))


def test_paginar_falla_si_la_pagina_no_avanza():
    with pytest.raises(ErrorRepositorio):  # p. ej. un servidor que ignora el filtro `gt.`
        list(paginar(lambda *a, **k: [{"id": "1"}, {"id": "2"}], "t", "id", {}, 2))
