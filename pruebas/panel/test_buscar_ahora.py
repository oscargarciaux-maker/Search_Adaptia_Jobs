"""18 nov: «Buscar ahora» en el Resumen lanza bodega.yml desde el servidor del panel, con su propia llave de GitHub
(panel/acciones.py). La llave nunca sale del servidor; sin ella el botón no aparece."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from panel import acciones
from panel.api import crear_app
from panel.repositorio import ErrorRepositorio, RepositorioDemo

H = {"origin": "http://testserver"}
TOKEN = "github_pat_de_prueba_no_real"


class Respuesta:
    def __init__(self, estado=200, datos=None):
        self.status_code, self._datos = estado, datos or {}

    def json(self):
        return self._datos


class SesionFalsa:
    """Imita a la API de GitHub y guarda lo que se le pidió."""
    def __init__(self, corridas=(), estado_post=204, estado_get=200):
        self.corridas, self.estado_post, self.estado_get = list(corridas), estado_post, estado_get
        self.pedidos = []

    def request(self, metodo, url, headers=None, timeout=None, **kw):
        self.pedidos.append((metodo, url, headers, kw))
        if metodo == "POST":
            return Respuesta(self.estado_post)
        if self.estado_get != 200:
            return Respuesta(self.estado_get)
        if url.endswith("/actions/runs"):
            return Respuesta(datos={"workflow_runs": self.corridas})
        return Respuesta(datos={"default_branch": "main"})


def _c(flujo="bodega.yml", status="completed", rama="main", **kw):
    return {"path": ".github/workflows/" + flujo, "status": status, "head_branch": rama, "created_at": _ahora(), **kw}


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh(**kw):
    sesion = SesionFalsa(**kw)
    return acciones.AccionesGitHub(TOKEN, "dueno/repo", sesion=sesion), sesion


def test_lanza_la_busqueda_diaria_de_la_rama_principal():
    gh, sesion = _gh()
    assert gh.lanzar() == {"lanzada": True}
    metodo, url, cabeceras, kw = sesion.pedidos[-1]
    assert metodo == "POST" and url.endswith("/repos/dueno/repo/actions/workflows/bodega.yml/dispatches")
    # Sin `enfoque` en la completa: también funciona con un bodega.yml anterior a v45 (orden del despliegue).
    assert kw["json"] == {"ref": "main", "inputs": {"modo": "diario", "prueba": "false"}}
    assert cabeceras["Authorization"] == "Bearer " + TOKEN


def test_no_lanza_si_ya_hay_una_en_cola_o_corriendo():
    gh, sesion = _gh(corridas=[_c(status="in_progress")])
    with pytest.raises(ErrorRepositorio) as e:
        gh.lanzar()
    assert e.value.estado == 409 and not any(p[0] == "POST" for p in sesion.pedidos)


def test_lanza_aunque_la_maquina_se_haya_encendido_hace_poco(monkeypatch):
    """CI del PR #130: con el reloj monotónico por debajo de 180 s (máquina o panel recién encendidos), el primer
    pedido no puede tomarse como «ya se pidió hace un momento»."""
    monkeypatch.setattr(acciones.time, "monotonic", lambda: 5.0)
    gh, _ = _gh()
    assert gh.lanzar() == {"lanzada": True}
    with pytest.raises(ErrorRepositorio):
        gh.lanzar()


def test_no_lanza_dos_veces_seguidas():
    gh, sesion = _gh()
    gh.lanzar()
    with pytest.raises(ErrorRepositorio):
        gh.lanzar()
    assert sum(p[0] == "POST" for p in sesion.pedidos) == 1


def test_una_corrida_de_otra_rama_no_cuenta():
    gh, _ = _gh(corridas=[_c(status="completed", rama="prueba")])
    assert gh.estado()["en_curso"] is None


def test_estado_dice_en_cola_corriendo_y_la_pedida_hoy():
    r = acciones.resumir([_c(status="queued", event="workflow_dispatch")], "main")
    assert r["en_curso"]["estado"] == "en_cola" and r["ultima_pedida"]["estado"] == "en_cola"
    r = acciones.resumir([_c(conclusion="cancelled", event="workflow_dispatch")], "main")
    assert r["en_curso"] is None and r["ultima_pedida"]["estado"] == "cancelled"  # el panel avisa que se canceló
    r = acciones.resumir([_c(event="workflow_dispatch", conclusion="success", created_at="2020-01-01T12:00:00Z")],
                         "main")
    assert r["ultima_pedida"] is None  # la de otro día no es de hoy


@pytest.mark.parametrize("corrida,bloquea", [
    (_c("profunda.yml", "in_progress"), True),     # larga: lanzar ahora haría esperar y la captura la cancelaría
    (_c("preparar.yml", "queued"), True),          # esperando turno: lanzar la cancelaría
    (_c("incremental.yml", "queued"), True),
    (_c("incremental.yml", "in_progress"), False), # dura minutos: se espera detrás sin riesgo
    (_c("bodega.yml", "in_progress", rama="otra"), True),  # ocupa el mismo grupo aunque sea de otra rama
    (_c("pruebas.yml", "in_progress"), False),     # fuera del grupo
])
def test_no_lanza_si_otra_tarea_del_grupo_ocupa_el_turno(corrida, bloquea):
    gh, sesion = _gh(corridas=[corrida])
    if bloquea:
        with pytest.raises(ErrorRepositorio) as e:
            gh.lanzar()
        assert e.value.estado == 409 and "Espera" in e.value.mensaje
    else:
        assert gh.lanzar() == {"lanzada": True}


def test_el_grupo_coincide_con_los_flujos():
    import yaml
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2] / ".github/workflows"
    grupo = {f.name for f in raiz.glob("*.yml")
             if ((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("concurrency") or {}).get("group") == "publicar"}
    assert grupo == acciones.GRUPO_PUBLICAR and set(acciones.NOMBRES) == grupo


@pytest.mark.parametrize("codigo", [401, 403, 404, 500])
def test_un_error_de_github_se_explica_sin_mostrar_la_llave(codigo):
    gh, _ = _gh(estado_get=codigo)
    with pytest.raises(ErrorRepositorio) as e:
        gh.estado()
    assert TOKEN not in e.value.mensaje and e.value.estado == 502


def _real(monkeypatch, token, repositorio):
    monkeypatch.setenv("GITHUB_ACCIONES_TOKEN", token)
    monkeypatch.setenv("GITHUB_REPOSITORIO", repositorio)
    return crear_app(demo=False, repositorio=RepositorioDemo(), origen="https://panel.example",
                     operadores=["operador@example.org"])


def test_sin_llave_el_boton_no_aparece(monkeypatch):
    assert _real(monkeypatch, "", "").state.acciones is None


def test_con_llave_mal_escrita_el_panel_arranca_sin_boton(monkeypatch):
    assert _real(monkeypatch, TOKEN, "sin-barra").state.acciones is None
    assert _real(monkeypatch, "con espacio", "dueno/repo").state.acciones is None


def test_espacios_al_pegar_se_quitan(monkeypatch):
    app = _real(monkeypatch, " " + TOKEN + "\n", " dueno/repo ")
    assert app.state.acciones.repositorio == "dueno/repo"


def test_api_lanza_y_bloquea_en_la_demo():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    estado = api.get("/api/busqueda").json()
    assert {k: estado[k] for k in ("disponible", "en_curso", "ocupado", "ultima_pedida")} == \
        {"disponible": True, "en_curso": None, "ocupado": None, "ultima_pedida": None}
    assert estado["plan"]["tipo"] == "faltantes" and estado["plan"]["faltan"]  # la demo: 3 perfiles bajo su meta
    assert api.post("/api/busqueda", json={}).status_code == 403  # sin origen: como cualquier escritura
    assert api.post("/api/busqueda", json={}, headers=H).json() == {"lanzada": True, "tipo": "faltantes"}
    assert api.get("/api/busqueda").json()["en_curso"]["estado"] == "corriendo"
    assert api.post("/api/busqueda", json={}, headers=H).status_code == 409


def test_un_error_de_github_deja_el_boton_con_el_motivo_y_sin_la_llave():
    gh, _ = _gh(estado_get=401)
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo(), acciones=gh))
    r = api.get("/api/busqueda")
    assert r.status_code == 200 and r.json()["disponible"] is True and "rechazó la llave" in r.json()["ocupado"]
    assert TOKEN not in r.text
    r = api.post("/api/busqueda", json={}, headers=H)
    assert r.status_code == 502 and TOKEN not in r.text


# ── Contrato v45: un solo botón que decide ─────────────────────────────────────────────────────────────────────────
class GitHubAnotado:
    def __init__(self):
        self.enfoques = []

    def estado(self, fresco=False):
        return {"en_curso": None, "ocupado": None, "ultima_pedida": None}

    def lanzar(self, enfoque="completo"):
        self.enfoques.append(enfoque)
        return {"lanzada": True}


def _repo_con(ejecuciones, por_perfil):
    class Repo(RepositorioDemo):
        def ejecuciones(self):
            return ejecuciones

        def asignaciones_por_perfil(self, ids):
            from collections import Counter
            return Counter({(ids[0], pid): n for pid, n in por_perfil.items()})
    return Repo()


def _de_hoy(estado="completa", **resumen):
    """La fila del día de una búsqueda que ya armó su lote (contrato v43: `revision_del_lote`)."""
    from panel.repositorio import hoy
    return [{"id": "e1", "fecha": hoy(), "estado": estado, "resumen": {"revision_del_lote": 1, **resumen}}]


def test_sin_busqueda_hoy_lanza_la_completa():
    gh = GitHubAnotado()
    api = TestClient(crear_app(demo=True, repositorio=_repo_con([], {}), acciones=gh))
    assert api.get("/api/busqueda").json()["plan"]["tipo"] == "completa"
    assert api.post("/api/busqueda", json={}, headers=H).json()["tipo"] == "completa" and gh.enfoques == ["completo"]


def test_busqueda_fallida_hoy_tambien_lanza_la_completa():
    gh = GitHubAnotado()
    api = TestClient(crear_app(demo=True, repositorio=_repo_con(_de_hoy("fallida"), {}), acciones=gh))
    api.post("/api/busqueda", json={}, headers=H)
    assert gh.enfoques == ["completo"]


def test_si_todos_cumplen_no_lanza_y_lo_dice():
    from panel.modelos import Configuracion
    from panel.repositorio import configuracion_demo
    cfg = Configuracion.model_validate(configuracion_demo())
    todos = {str(p.id): int(p.meta_diaria or 0) + 1 for p in cfg.perfiles}
    gh = GitHubAnotado()
    api = TestClient(crear_app(demo=True, repositorio=_repo_con(_de_hoy(), todos), acciones=gh))
    assert api.get("/api/busqueda").json()["plan"]["tipo"] == "nada"
    r = api.post("/api/busqueda", json={}, headers=H)
    assert r.status_code == 409 and "meta" in r.json()["detail"] and gh.enfoques == []


def test_con_perfiles_bajo_su_meta_lanza_a_fondo_solo_para_ellos():
    gh = GitHubAnotado()
    api = TestClient(crear_app(demo=True, repositorio=_repo_con(_de_hoy(), {}), acciones=gh))
    plan = api.get("/api/busqueda").json()["plan"]
    assert plan["tipo"] == "faltantes" and all(f["hoy"] < f["meta"] for f in plan["faltan"])
    api.post("/api/busqueda", json={}, headers=H)
    assert gh.enfoques == ["faltantes"]


def test_la_captura_horaria_de_madrugada_no_cuenta_como_busqueda_del_dia():
    # La captura horaria crea la fila del día sin lote (sin `revision_del_lote`): el botón hace la completa.
    from panel import servicio
    from panel.repositorio import hoy
    for filas in ([{"id": "e1", "fecha": hoy(), "estado": "parcial", "resumen": {}}], _de_hoy("en_curso")):
        assert servicio.plan_busqueda(_repo_con(filas, {}))["tipo"] == "completa"


def test_solo_cuenta_quien_todavia_puede_recibir_mas():
    # Con 5 o más, solo hay más si su cargo tiene cupo libre en el lote; Comunidad nunca (recibe lo que sobra).
    from panel import ejecutor
    from panel.modelos import Configuracion
    from panel.repositorio import configuracion_demo, hoy
    datos = configuracion_demo()
    datos["clientes"][-1]["comunidad"] = True
    cfg = Configuracion.model_validate(datos)
    comunidad = {c.id for c in cfg.clientes if c.comunidad}
    reales = [p for p in cfg.perfiles_activos() if p.cliente_id not in comunidad and (p.meta_diaria or 0) > 5]
    assert reales
    p = reales[0]
    cargo = next(c.nombre for c in cfg.cargos if c.id == p.cargo_id)
    version = {"configuracion": datos, "revision": 1}

    def faltan(n, libre):
        filas = _de_hoy(faltantes={cargo: libre})
        return {str(x.id) for x, _, _ in ejecutor.faltan_hoy(_repo_con(filas, {str(p.id): n}), version, hoy())}
    assert str(p.id) in faltan(2, 0)  # bajo el mínimo: el rescate la completa
    assert str(p.id) not in faltan(5, 0)  # cupo del cargo lleno: otra búsqueda no le suma
    assert str(p.id) in faltan(5, 3)
    todos = ejecutor.faltan_hoy(_repo_con(_de_hoy(), {}), version, hoy())
    assert todos and not [x for x, _, _ in todos if x.cliente_id in comunidad]
    assert any(p.cliente_id in comunidad for p in cfg.perfiles_activos())


def test_plan_nunca_falla():
    from panel import servicio

    class Roto(RepositorioDemo):
        def operativa(self, fecha=None):
            raise RuntimeError("Supabase no responde")
    assert servicio.plan_busqueda(Roto())["tipo"] == "completa"


def test_correr_con_faltantes_enfoca_solo_en_ellos(monkeypatch, tmp_path):
    from contextlib import contextmanager
    from panel import ejecutor
    from panel.repositorio import hoy
    repo = _repo_con(_de_hoy(), {})
    vistos = {}

    class Alto(Exception):
        pass

    @contextmanager
    def activar(version, fecha, aprendidos=None, cortos=(), enfocar=None):
        vistos["enfocar"] = enfocar
        raise Alto
        yield  # pragma: no cover
    monkeypatch.setattr(ejecutor, "activar", activar)
    monkeypatch.setattr(ejecutor, "iniciar", lambda *a: {"id": "e1", "resumen": {}})
    monkeypatch.setattr(ejecutor, "perfiles_cortos", lambda *a: set())
    esperados = {str(p.id) for p, _, _ in ejecutor.faltan_hoy(repo, repo.operativa(hoy()), hoy())}
    for enfoque, esperado in (("faltantes", esperados), ("completo", None)):
        try:
            ejecutor.correr(str(tmp_path), repo=repo, enfoque=enfoque)
        except Alto:
            pass
        assert vistos["enfocar"] == esperado and (esperado is None or esperado)


def test_faltantes_solo_reparte_entre_quienes_faltan_y_es_corta():
    # Contrato v47: turnos solo para quienes faltan, sin el resto de combinaciones, presupuestos de siempre con tope
    # de tiempo y una sola ronda de refuerzo.
    from panel import ejecutor
    from panel.repositorio import configuracion_demo, hoy
    from buscador import cobertura
    cfg = configuracion_demo()
    uno = cfg["perfiles"][0]["id"]
    _, _, normal = ejecutor.preparar({"configuracion": cfg}, hoy())
    _, _, foco = ejecutor.preparar({"configuracion": cfg}, hoy(), enfocar={uno})
    assert [p["perfil"] for p in foco["personas_busqueda"]] == [uno]
    assert foco["presupuestos"]["linkedin_busquedas"] == normal["presupuestos"]["linkedin_busquedas"]
    assert foco["presupuestos"]["minutos_por_fuente"] == ejecutor.MINUTOS_FALTANTES < normal["presupuestos"]["minutos_por_fuente"]
    assert foco["faltantes"] and not normal.get("faltantes") and foco["refuerzo"]["rondas"] == 1
    # Contrato v48: el tope de la comprobación incluye ordenar, solo en «Buscar ahora».
    assert foco["verificacion_enlaces"]["contar_orden"] and not normal["verificacion_enlaces"].get("contar_orden")
    assert foco["verificacion_enlaces"]["segundos_corrida"] == ejecutor.SEGUNDOS_FALTANTES["verificacion"]
    assert foco["verificacion_enlaces"]["reserva_segundos"] == ejecutor.RESERVA_REFUERZO
    assert not normal["verificacion_enlaces"].get("reserva_segundos")
    persona = foco["personas_busqueda"][0]
    suyas = [(persona["familia"], ["x"], sorted(persona["lugares"])[0], {})]
    otras = [("cargo:otro", ["y"], "REMOTO_CO", {})]
    cobertura.configurar_personas(foco["personas_busqueda"])
    try:
        cobertura.configurar_faltantes(True)
        assert cobertura.repartir(suyas + otras, {}, hoy()) == suyas  # nada de los demás
        cobertura.configurar_faltantes()
        assert len(cobertura.repartir(suyas + otras, {}, hoy())) == 2
    finally:
        cobertura.configurar_personas()
        cobertura.configurar_faltantes()

def test_busquedas_por_persona_se_suman_entre_pasadas_del_dia():
    from panel import ejecutor
    antes = {"p1": {"linkedin": 4}, "p2": {"indeed": 1}}
    assert ejecutor._sumar_busquedas(antes, {"p1": {"linkedin": 6, "indeed": 2}}) == {
        "p1": {"linkedin": 10, "indeed": 2}, "p2": {"indeed": 1}}
    assert ejecutor._sumar_busquedas(antes, None) == antes and antes["p1"] == {"linkedin": 4}



# ── Contrato v47: no repetir lo ya buscado hoy ─────────────────────────────────────────────────────────────────────
def test_no_repite_lo_ya_buscado_hoy_y_sigue_con_otros_nombres_o_la_pagina_siguiente():
    from buscador import cobertura
    hoy, nombres, clave = "2026-11-18", ["A", "B", "C", "D", "E", "F"], "cargo:x@REMOTO_CO"
    estado = {}
    primera = cobertura.rotar(nombres, hoy, 4)
    b = cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado)
    assert (b.terminos, b.desde, b.dias) == (primera, 0, 30)  # fuera del modo: la de siempre
    cobertura.configurar_faltantes(True)
    try:
        cobertura.anotar_hecha(estado, b, hoy)
        otra = cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado)
        assert otra.terminos != primera and otra.desde == 0  # otros nombres del cargo
        cobertura.anotar_hecha(estado, otra, hoy)
        assert cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado) is None  # sin saber dónde quedó, no repite
        cobertura.anotar_paginas(estado, b._replace(dias=2), hoy, 3, False)
        sigue = cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado)
        assert (sigue.terminos, sigue.desde, sigue.dias) == (primera, 3, 2)  # la página 4, con los mismos días
        assert cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado, paginada=False) is None
        cobertura.anotar_paginas(estado, b, hoy, 4, True)
        assert cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado) is None  # ya no hay más páginas
        # Si cambian las condiciones del perfil (otro lugar u otros nombres), la clave es otra y sí se busca.
        assert cobertura.siguiente_busqueda(nombres, hoy, 4, "cargo:x@REMOTO_MX", estado).desde == 0
        assert cobertura.siguiente_busqueda(["G", "H"], hoy, 4, clave, estado).desde == 0
        # Ayer no cuenta: hoy se busca de nuevo.
        assert cobertura.siguiente_busqueda(nombres, "2026-11-19", 4, clave, estado).desde == 0
    finally:
        cobertura.configurar_faltantes()


def test_linkedin_en_faltantes_no_repite_y_lee_paginas_nuevas():
    from buscador import cobertura
    from buscador.fuentes import linkedin_publico

    class R:
        status_code = 200
        text = ""

    pedidas = []

    class Cliente:
        def get(self, url, params=None):
            pedidas.append((params["keywords"], params["start"]))
            return R()
    mapa = [{"id": "cargo:x", "consultas": ["A", "B", "C", "D", "E"], "lugares": [("REMOTO_CO", {"geoId": "1"})]}]
    estado = {}
    cobertura.configurar_faltantes(True)
    cobertura.configurar_personas([{"familia": "cargo:x", "perfil": "p1", "lugares": {"CO", "REMOTO_CO"}, "peso": 1, "corto": True,
                                    "principales": []}])
    try:
        for _ in range(3):
            linkedin_publico.buscar(Cliente(), mapa, [], estado, 10, hoy="2026-11-18", max_fichas=0)
    finally:
        cobertura.configurar_faltantes()
        cobertura.configurar_personas()
    # Cada pasada busca otros nombres; ninguna búsqueda (nombres + página) se repite.
    assert len(pedidas) == len(set(pedidas)) and len({k for k, _ in pedidas}) >= 2


def test_en_faltantes_no_se_leen_los_portales_ni_las_listas(monkeypatch, tmp_path):
    from buscador import bodega
    from buscador.fuentes import ats, open_seat, remotos, sitemaps_empleo, tableros_latam
    llamadas = []
    for modulo, nombre in ((ats, "buscar"), (ats, "descubrir"), (open_seat, "tableros"),
                           (tableros_latam, "tableros"), (remotos, "buscar"), (sitemaps_empleo, "buscar")):
        monkeypatch.setattr(modulo, nombre, lambda *a, _n=f"{modulo.__name__}.{nombre}", **k: llamadas.append(_n))
    from buscador import cobertura
    from buscador.fuentes import computrabajo, elempleo, getonbrd, indeed, linkedin_apify, linkedin_publico
    for modulo in (linkedin_publico, indeed, linkedin_apify, computrabajo, elempleo, getonbrd):  # sin red
        monkeypatch.setattr(modulo, "buscar", lambda *a, **k: ([], {}))
    cfg = bodega.config()
    for clave in list(cfg["presupuestos"]):
        if clave.endswith("busquedas") or clave.endswith("fichas"):
            cfg["presupuestos"][clave] = 0
    cfg["presupuestos"]["minutos_por_fuente"] = 0
    cobertura.configurar_faltantes(True)
    try:
        _, _, _, salud = bodega.recoger(cfg, {}, "2026-11-18", tmp_path)
    finally:
        cobertura.configurar_faltantes()
    assert llamadas == []
    assert all("omitida" in salud[n] for n in ("Portales de empresas", "Descubrir portales", "Open Seat",
                                                "Tableros LATAM", "Tableros remotos", "Hireline", "Magneto"))


def test_get_on_board_anota_lo_que_busca_y_en_faltantes_no_lo_repite(monkeypatch, tmp_path):
    from buscador import bodega, cobertura
    from buscador.fuentes import (ats, computrabajo, elempleo, getonbrd, indeed, linkedin_apify, linkedin_publico,
                                  remotos, sitemaps_empleo)
    pedidas = []
    monkeypatch.setattr(getonbrd, "buscar", lambda cliente, consultas: (pedidas.append(list(consultas)) or
                                                                     ([], {"respondidas": list(consultas)})))
    for modulo in (linkedin_publico, indeed, linkedin_apify, computrabajo, elempleo, sitemaps_empleo):  # sin red
        monkeypatch.setattr(modulo, "buscar", lambda *a, **k: ([], {}))
    monkeypatch.setattr(remotos, "buscar", lambda *a, **k: ([], [], {}))
    monkeypatch.setattr(ats, "buscar", lambda *a, **k: ([], set(), {}))
    monkeypatch.setattr(ats, "descubrir", lambda *a, **k: ([], 0))
    cfg = bodega.config()
    for clave in list(cfg["presupuestos"]):
        if clave.endswith("busquedas") or clave.endswith("fichas"):
            cfg["presupuestos"][clave] = 0
    cfg["presupuestos"].update(getonbrd_busquedas=1, minutos_por_fuente=0)
    mapa = [{"id": "cargo:x", "consultas": ["A", "B"], "exactos": [], "similares": [], "lugares": []}]
    estado = {}
    bodega.recoger(cfg, estado, "2026-11-18", tmp_path, solo_mapa=mapa)  # la de la noche
    cobertura.configurar_faltantes(True)
    cobertura.configurar_personas([{"familia": "cargo:x", "perfil": "p1", "lugares": {"CO", "REMOTO_CO"}, "peso": 1, "corto": True,
                                    "principales": []}])
    try:
        bodega.recoger(cfg, estado, "2026-11-18", tmp_path, solo_mapa=mapa)
    finally:
        cobertura.configurar_faltantes()
        cobertura.configurar_personas()
    assert pedidas[0] and pedidas[1] and pedidas[0] != pedidas[1]  # el segundo pase busca otro nombre


def test_faltantes_sin_personas_no_busca_para_todos_y_sigue_paginas_de_otras_vueltas():
    from buscador import cobertura
    hoy, nombres, clave = "2026-11-18", ["A", "B", "C", "D", "E", "F", "G", "H"], "cargo:x@REMOTO_CO"
    cobertura.configurar_faltantes(True)
    try:
        assert cobertura.repartir([("cargo:x", ["A"], "REMOTO_CO", {})], {}, hoy) == []
        estado = {}
        primera = cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado)
        cobertura.anotar_hecha(estado, primera, hoy)
        cobertura.anotar_paginas(estado, primera, hoy, 1, True)  # la primera vuelta se agotó
        segunda = cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado)
        cobertura.anotar_hecha(estado, segunda, hoy)
        cobertura.anotar_paginas(estado, segunda, hoy, 3, False)  # la segunda tiene más páginas
        sigue = cobertura.siguiente_busqueda(nombres, hoy, 4, clave, estado)
        assert (sigue.terminos, sigue.desde) == (segunda.terminos, 3)
    finally:
        cobertura.configurar_faltantes()


def test_get_on_board_no_anota_lo_que_fallo(monkeypatch, tmp_path):
    from buscador import bodega
    from buscador.fuentes import (ats, computrabajo, elempleo, getonbrd, indeed, linkedin_apify, linkedin_publico,
                                  remotos, sitemaps_empleo)
    monkeypatch.setattr(getonbrd, "buscar", lambda cliente, consultas: ([], {"respondidas": []}))
    for modulo in (linkedin_publico, indeed, linkedin_apify, computrabajo, elempleo, sitemaps_empleo):
        monkeypatch.setattr(modulo, "buscar", lambda *a, **k: ([], {}))
    monkeypatch.setattr(remotos, "buscar", lambda *a, **k: ([], [], {}))
    monkeypatch.setattr(ats, "buscar", lambda *a, **k: ([], set(), {}))
    monkeypatch.setattr(ats, "descubrir", lambda *a, **k: ([], 0))
    cfg = bodega.config()
    cfg["presupuestos"].update(getonbrd_busquedas=2, minutos_por_fuente=0)
    estado = {}
    mapa = [{"id": "cargo:x", "consultas": ["A", "B"], "exactos": [], "similares": [], "lugares": []}]
    bodega.recoger(cfg, estado, "2026-11-18", tmp_path, solo_mapa=mapa)
    assert not estado.get("getonbrd")


# ── Contrato v49: «Buscar ahora» desde el detalle de un cliente ────────────────────────────────────────────────────
def _datos_dos_perfiles():
    """La demo con un segundo perfil (nuevo, sin asignaciones) en el primer cliente."""
    from copy import deepcopy
    from panel.repositorio import configuracion_demo
    datos = configuracion_demo()
    primero = next(p for p in datos["perfiles"] if p["cliente_id"] == datos["clientes"][0]["id"])
    primero["meta_diaria"] = int(primero.get("meta_diaria") or 10) - 5  # sin pasar el techo del día
    datos["perfiles"].append({**deepcopy(primero), "id": "0f0e0d0c-0b0a-4000-8000-000000000049", "meta_diaria": 5})
    return datos


def _cliente_con_perfiles():
    from panel.modelos import Configuracion
    cfg = Configuracion.model_validate(_datos_dos_perfiles())
    c = cfg.clientes[0]
    return str(c.id), [str(p.id) for p in cfg.perfiles_activos() if p.cliente_id == c.id], cfg


def _repo_pedido(ejecuciones, por_perfil):
    class Repo(type(_repo_con(ejecuciones, por_perfil))):
        def operativa(self, fecha):
            return {"revision": 1, "configuracion": _datos_dos_perfiles()}
    repo = Repo()
    return repo


def test_pedido_sin_lote_hace_la_completa_con_sus_perfiles_primero():
    from panel.repositorio import hoy
    cid, suyos, _ = _cliente_con_perfiles()
    gh, repo = GitHubAnotado(), _repo_pedido([], {})
    api = TestClient(crear_app(demo=True, repositorio=repo, acciones=gh))
    plan = api.get("/api/busqueda", params={"cliente_id": cid}).json()["plan"]
    assert plan["tipo"] == "completa" and "primero" in plan["motivo"]
    r = api.post("/api/busqueda", json={"cliente_id": cid}, headers=H)
    assert r.json() == {"lanzada": True, "tipo": "completa"} and gh.enfoques == ["pedido"]
    assert repo.ajuste("busqueda_pedida") == {"fecha": hoy(), "perfiles": suyos}


def test_pedido_con_lote_solo_para_sus_perfiles_bajo_su_meta():
    cid, suyos, cfg = _cliente_con_perfiles()
    lleno = suyos[0]
    meta = next(int(p.meta_diaria or 0) for p in cfg.perfiles if str(p.id) == lleno)
    gh, repo = GitHubAnotado(), _repo_pedido(_de_hoy(), {lleno: meta})  # uno cumple; los demás cuentan 0 (como uno nuevo)
    api = TestClient(crear_app(demo=True, repositorio=repo, acciones=gh))
    plan = api.get("/api/busqueda", params={"cliente_id": cid}).json()["plan"]
    assert plan["tipo"] == "pedido" and {f["perfil_id"] for f in plan["faltan"]} == set(suyos) - {lleno}
    assert all(f["hoy"] == 0 for f in plan["faltan"])
    assert api.post("/api/busqueda", json={"cliente_id": cid}, headers=H).json()["tipo"] == "pedido"
    assert gh.enfoques == ["pedido"] and set(repo.ajuste("busqueda_pedida")["perfiles"]) == set(suyos) - {lleno}


def test_pedido_con_todos_en_su_meta_no_lanza():
    cid, _, cfg = _cliente_con_perfiles()
    gh, repo = GitHubAnotado(), _repo_pedido(_de_hoy(), {str(p.id): int(p.meta_diaria or 0) for p in cfg.perfiles})
    api = TestClient(crear_app(demo=True, repositorio=repo, acciones=gh))
    assert api.get("/api/busqueda", params={"cliente_id": cid}).json()["plan"]["tipo"] == "nada"
    r = api.post("/api/busqueda", json={"cliente_id": cid}, headers=H)
    assert r.status_code == 409 and "meta" in r.json()["detail"]
    assert gh.enfoques == [] and repo.ajuste("busqueda_pedida") is None


def test_pedido_de_un_cliente_que_no_esta_en_uso_o_no_es_valido():
    from uuid import uuid4
    gh, repo = GitHubAnotado(), _repo_pedido(_de_hoy(), {})
    api = TestClient(crear_app(demo=True, repositorio=repo, acciones=gh))
    otro = str(uuid4())
    plan = api.get("/api/busqueda", params={"cliente_id": otro}).json()["plan"]
    assert plan["tipo"] == "nada" and "Aplicar cambios" in plan["motivo"]
    r = api.post("/api/busqueda", json={"cliente_id": otro}, headers=H)
    assert r.status_code == 409 and "Aplicar cambios" in r.json()["detail"]
    assert api.post("/api/busqueda", json={"cliente_id": "no-es-un-id"}, headers=H).status_code == 422
    assert api.post("/api/busqueda", json={"cliente_id": otro, "perfiles": ["x"]}, headers=H).status_code == 422
    assert api.get("/api/busqueda", params={"cliente_id": "no-es-un-id"}).status_code == 422
    assert gh.enfoques == [] and repo.ajuste("busqueda_pedida") is None


def test_pedido_de_un_cliente_archivado_no_lanza():
    cid, _, _ = _cliente_con_perfiles()

    class Repo(type(_repo_pedido([], {}))):
        def operativa(self, fecha):
            datos = _datos_dos_perfiles()
            for c in datos["clientes"]:
                c["activo"] = c["activo"] and c["id"] != cid
            return {"revision": 1, "configuracion": datos}
    gh = GitHubAnotado()
    api = TestClient(crear_app(demo=True, repositorio=Repo(), acciones=gh))
    assert api.post("/api/busqueda", json={"cliente_id": cid}, headers=H).status_code == 409 and gh.enfoques == []


def test_pedido_ninguna_entrada_del_flujo_lleva_identificadores():
    cid, suyos, _ = _cliente_con_perfiles()
    gh, sesion = _gh()
    api = TestClient(crear_app(demo=True, repositorio=_repo_pedido(_de_hoy(), {}), acciones=gh))
    assert api.post("/api/busqueda", json={"cliente_id": cid}, headers=H).status_code == 200
    envios = [kw for metodo, _, _, kw in sesion.pedidos if metodo == "POST"]
    assert envios == [{"json": {"ref": "main", "inputs": {"modo": "diario", "prueba": "false", "enfoque": "pedido"}}}]
    assert not any(x in str(sesion.pedidos) for x in [cid, *suyos])
    with pytest.raises(ValueError):  # nunca un texto libre como enfoque
        acciones.AccionesGitHub(TOKEN, "dueno/repo", sesion=SesionFalsa()).lanzar("pedido; echo x")
    with pytest.raises(ValueError):
        acciones.AccionesDemo().lanzar(cid)


def test_bodega_yml_ofrece_pedido_como_opcion_cerrada():
    import yaml
    from pathlib import Path
    flujo = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/bodega.yml").read_text("utf-8"))
    entradas = (flujo.get("on") or flujo.get(True))["workflow_dispatch"]["inputs"]
    assert entradas["enfoque"]["type"] == "choice" and set(entradas["enfoque"]["options"]) == set(acciones.ENFOQUES)
    assert all(e.get("type") in ("choice", "boolean") for e in entradas.values())  # ninguna entrada de texto libre


def _correr_pedido(monkeypatch, tmp_path, repo):
    from contextlib import contextmanager
    from panel import ejecutor
    vistos = {}

    class Alto(Exception):
        pass

    @contextmanager
    def activar(version, fecha, aprendidos=None, cortos=(), enfocar=None):
        vistos.update(enfocar=enfocar, cortos=set(cortos))
        raise Alto
        yield  # pragma: no cover
    monkeypatch.setattr(ejecutor, "activar", activar)
    monkeypatch.setattr(ejecutor, "iniciar", lambda *a: {"id": "e1", "resumen": {}})
    monkeypatch.setattr(ejecutor, "perfiles_cortos", lambda *a: set())
    try:
        ejecutor.correr(str(tmp_path), repo=repo, enfoque="pedido")
    except Alto:
        pass
    return vistos


def test_correr_pedido_con_lote_enfoca_en_los_pedidos_activos_y_vacia_el_ajuste(monkeypatch, tmp_path):
    from panel.repositorio import hoy
    _, suyos, _ = _cliente_con_perfiles()
    repo = _repo_pedido(_de_hoy(), {})
    repo.guardar_ajuste("busqueda_pedida", {"fecha": hoy(), "perfiles": [*suyos, "perfil-que-ya-no-existe"]})
    assert _correr_pedido(monkeypatch, tmp_path, repo)["enfocar"] == set(suyos)
    assert repo.ajuste("busqueda_pedida") == {}
    assert _correr_pedido(monkeypatch, tmp_path, repo)["enfocar"] is None  # ya usado: la búsqueda normal


def test_correr_pedido_sin_lote_hace_la_completa_con_ellos_primero(monkeypatch, tmp_path):
    from panel.repositorio import hoy
    _, suyos, _ = _cliente_con_perfiles()
    repo = _repo_pedido([], {})
    repo.guardar_ajuste("busqueda_pedida", {"fecha": hoy(), "perfiles": suyos})
    vistos = _correr_pedido(monkeypatch, tmp_path, repo)
    assert vistos["enfocar"] is None and set(suyos) <= vistos["cortos"]


def test_correr_pedido_de_otro_dia_o_vacio_hace_la_busqueda_normal(monkeypatch, tmp_path):
    _, suyos, _ = _cliente_con_perfiles()
    for pedida in ({"fecha": "2020-01-01", "perfiles": suyos}, {}, {"fecha": "x", "perfiles": "no-es-lista"}, None):
        repo = _repo_pedido(_de_hoy(), {})
        if pedida is not None:
            repo.guardar_ajuste("busqueda_pedida", pedida)
        vistos = _correr_pedido(monkeypatch, tmp_path, repo)
        assert vistos["enfocar"] is None and vistos["cortos"] == set()


def test_correr_pedido_si_no_se_puede_leer_el_ajuste_no_falla(monkeypatch, tmp_path):
    class Roto(type(_repo_pedido([], {}))):
        def ajuste(self, clave, defecto=None):
            raise RuntimeError("Supabase no responde")
    assert _correr_pedido(monkeypatch, tmp_path, Roto())["enfocar"] is None
