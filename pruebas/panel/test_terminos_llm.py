"""P-14.2: términos ampliados por un LLM, con un LLM FALSO (nunca se llama a un servicio real)."""
from datetime import datetime, timedelta, timezone

import pytest
import requests

from buscador import llm
from panel import ampliados, terminos
from panel.contenido import cargo_operativo

ESQUEMA = terminos.ESQUEMA_AMPLIADOS
ENCENDIDO = {"llm": {"terminos_activo": True}}
AHORA = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)


class Falso(llm.Proveedor):
    """Devuelve (o lanza) lo de `respuestas` en orden; anota cada petición."""
    nombre, modelo = "falso", "modelo-falso"

    def __init__(self, *respuestas):
        self.respuestas, self.pedidos = list(respuestas), []

    def completar(self, mensajes, segundos):
        self.pedidos.append(mensajes)
        r = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        if isinstance(r, Exception):
            raise r
        return r


def cliente(*respuestas, tope=20):
    esperas = []
    c = llm.Cliente(Falso(*respuestas), tope=tope, dormir=esperas.append)
    return c, esperas


BUENO = '{"es": ["Diseñador de Interacción"], "en": ["Interaction Designer"]}'


# --- buscador/llm.py ---------------------------------------------------------------------------------------------

def test_json_valido_y_entre_comillas_de_codigo():
    c, _ = cliente("Aquí va:\n```json\n" + BUENO + "\n```")
    assert c.pedir_json("p", ESQUEMA) == {"es": ["Diseñador de Interacción"], "en": ["Interaction Designer"]}
    assert c.llamadas == 1 and c.fallos == 0


@pytest.mark.parametrize("texto", ["no es json", '{"es": ["x"]}', '{"es": [], "en": [], "otro": 1}',
                                   '{"es": "texto", "en": []}', '{"es": [1], "en": []}'])
def test_json_invalido_no_rompe_ni_reintenta(texto, capsys):
    c, esperas = cliente(texto)
    assert c.pedir_json("p", ESQUEMA) is None
    assert c.llamadas == 1 and c.fallos == 1 and esperas == []
    assert "[aviso] llm:json" in capsys.readouterr().err


def test_tiempo_agotado_reintenta_con_espera_creciente():
    c, esperas = cliente(llm.FalloPasajero("Timeout"), llm.FalloPasajero("Timeout"), BUENO)
    assert c.pedir_json("p", ESQUEMA)["en"] == ["Interaction Designer"]
    assert c.llamadas == 3 and esperas == [2.0, 4.0]


def test_siempre_pasajero_se_rinde_tras_los_reintentos(capsys):
    c, esperas = cliente(llm.FalloPasajero("HTTP 503"))
    assert c.pedir_json("p", ESQUEMA) is None
    assert c.llamadas == 3 and len(esperas) == 2 and c.fallos == 1
    assert "[aviso] llm:pasajero" in capsys.readouterr().err


def test_retry_after_largo_no_se_espera():
    c, esperas = cliente(llm.FalloPasajero("HTTP 429", espera=3600))
    assert c.pedir_json("p", ESQUEMA) is None
    assert c.llamadas == 1 and esperas == []


def test_retry_after_corto_se_respeta():
    c, esperas = cliente(llm.FalloPasajero("HTTP 429", espera=5), BUENO)
    assert c.pedir_json("p", ESQUEMA) is not None and esperas == [5]


@pytest.mark.parametrize("error", [llm.FalloDefinitivo("HTTP 401"), RuntimeError("inesperado")])
def test_fallo_definitivo_o_inesperado_no_reintenta(error):
    c, esperas = cliente(error)
    assert c.pedir_json("p", ESQUEMA) is None and c.llamadas == 1 and esperas == []


def test_tope_de_llamadas_por_corrida(capsys):
    c, _ = cliente(BUENO, tope=2)
    assert c.pedir_json("a", ESQUEMA) and c.pedir_json("b", ESQUEMA)
    assert c.agotado and c.pedir_json("c", ESQUEMA) is None
    assert len(c.proveedor.pedidos) == 2  # la tercera ni se envía
    assert "[aviso] llm:tope" in capsys.readouterr().err


def test_tope_cuenta_los_reintentos():
    c, _ = cliente(llm.FalloPasajero("Timeout"), tope=2)
    assert c.pedir_json("a", ESQUEMA) is None and c.llamadas == 2


def test_sistema_va_primero():
    c, _ = cliente(BUENO)
    c.pedir_json("pregunta", ESQUEMA, sistema="reglas")
    assert [m["role"] for m in c.proveedor.pedidos[0]] == ["system", "user"]


@pytest.mark.parametrize("opciones,entorno,hay", [
    ({}, {}, False),
    ({"proveedor": "ninguno", "url": "https://x/v1", "modelo": "m"}, {"LLM_API_KEY": "k"}, False),
    ({"proveedor": "openai_compatible", "url": "https://x/v1", "modelo": "m"}, {}, False),  # sin clave
    ({"proveedor": "openai_compatible", "url": "", "modelo": "m"}, {"LLM_API_KEY": "k"}, False),
    ({"proveedor": "otro", "url": "https://x/v1", "modelo": "m"}, {"LLM_API_KEY": "k"}, False),
    ({"proveedor": "openai_compatible", "url": "https://x/v1", "modelo": "m"}, {"LLM_API_KEY": "k"}, True),
    ({"proveedor": "openai_compatible", "url": "https://x/v1", "modelo": "m", "clave_env": "OTRA"},
     {"OTRA": "k"}, True),
])
def test_cliente_desde_la_configuracion(opciones, entorno, hay):
    c = llm.cliente({"llm": opciones}, entorno=entorno)
    assert (c is not None) == hay
    if hay:
        assert c.tope == llm.TOPE_POR_CORRIDA and c.proveedor.url == "https://x/v1/chat/completions"


def test_la_configuracion_del_repo_viene_apagada():
    assert llm.opciones()["terminos_activo"] is False and llm.cliente() is None
    assert not ampliados.activo()


class Respuesta:
    def __init__(self, status, cuerpo=None, headers=None):
        self.status_code, self._cuerpo, self.headers = status, cuerpo, headers or {}

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class Sesion:
    def __init__(self, resultado):
        self.resultado, self.enviado = resultado, None

    def post(self, url, timeout, json, headers):
        self.enviado = {"url": url, "timeout": timeout, "json": json, "headers": headers}
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


@pytest.mark.parametrize("resultado,error", [
    (Respuesta(429, headers={"Retry-After": "7"}), llm.FalloPasajero),
    (Respuesta(503), llm.FalloPasajero),
    (requests.Timeout("lento"), llm.FalloPasajero),
    (requests.ConnectionError("sin red"), llm.FalloPasajero),
    (Respuesta(401), llm.FalloDefinitivo),
    (Respuesta(200, {"sin": "choices"}), llm.FalloDefinitivo),
    (Respuesta(200), llm.FalloDefinitivo),
])
def test_proveedor_compatible_clasifica_los_fallos(resultado, error):
    p = llm.Compatible("https://x/v1/", "m", "clave", Sesion(resultado))
    with pytest.raises(error) as e:
        p.completar([{"role": "user", "content": "p"}], 9)
    if isinstance(resultado, Respuesta) and resultado.headers:
        assert e.value.espera == 7


def test_proveedor_compatible_envia_el_formato_de_chat():
    sesion = Sesion(Respuesta(200, {"choices": [{"message": {"content": BUENO}}]}))
    p = llm.Compatible("https://x/v1", "m", "clave", sesion)
    assert p.completar([{"role": "user", "content": "p"}], 9) == BUENO
    assert sesion.enviado["url"] == "https://x/v1/chat/completions" and sesion.enviado["timeout"] == 9
    assert sesion.enviado["headers"]["Authorization"] == "Bearer clave"
    assert sesion.enviado["json"]["model"] == "m" and sesion.enviado["json"]["temperature"] == 0


# --- panel/terminos.py: lo que se envía y el filtro --------------------------------------------------------------

DISENO = {"id": "c1", "nombre": "Product Designer", "terminos_exactos": ["UX Designer"],
          "terminos_similares": ["Diseñador UX"], "terminos_excluidos": ["motion"], "terminos_cercanos": [],
          "funciones": ["figma"], "cupo": 20, "activo": True}


def test_el_prompt_solo_lleva_el_cargo_y_sus_terminos():
    cargo = {**DISENO, "id": "id-secreto", "cliente": "Ana Pérez", "ciudad": "Medellín", "telefono": "+573000000000"}
    p = terminos.prompt_ampliados(cargo)
    assert "Product Designer" in p and "UX Designer" in p and "Diseñador UX" in p
    for dato in ("id-secreto", "Ana", "Medellín", "+57", "figma", "motion"):
        assert dato not in p


def test_huella_cambia_con_el_nombre_o_los_terminos_y_no_con_lo_demas():
    h = terminos.huella_ampliados(DISENO)
    assert h == terminos.huella_ampliados({**DISENO, "funciones": ["sketch"], "cupo": 3, "terminos_excluidos": []})
    assert h == terminos.huella_ampliados({**DISENO, "nombre": "product  designer"})
    assert h != terminos.huella_ampliados({**DISENO, "nombre": "UX Researcher"})
    assert h != terminos.huella_ampliados({**DISENO, "terminos_similares": ["Diseñador UX", "Diseñador UI"]})


def test_filtro_de_los_terminos_propuestos():
    cargo = cargo_operativo(DISENO)
    propuesta = {
        "es": ["Diseñador de Interacción", "Diseñador", "Diseñador UX", "Diseñador Gráfico", "Diseñador 3D",
               "Diseñador de Motion", "Designer de produto", "Interaction Designer", "  Diseñadora de Producto Digital. "],
        "en": ["Interaction Designer", "Designer", "UX Designer", "Diseñador de Experiencia", "Graphic Designer",
               "http://spam.example", "Interaction Designer"]}
    assert terminos.filtrar_ampliados(propuesta, cargo) == ["Diseñador de Interacción", "Interaction Designer"]
    # Fuera: una sola palabra, ya usado, otro oficio del mapa (gráfico), cifras, excluido (motion), portugués,
    # idioma cambiado, URL, repetidos y el femenino de un nombre del mapa («Diseñadora de Producto Digital»).


def test_filtro_respeta_el_maximo_por_idioma_y_lo_que_no_es_lista():
    cargo = cargo_operativo(DISENO)
    muchos = {"es": [], "en": [f"Interaction Designer {x}" for x in ("Alpha", "Beta", "Gamma")]}
    assert len(terminos.filtrar_ampliados(muchos, cargo, maximo=2)) == 2
    assert terminos.filtrar_ampliados(None, cargo) == []
    assert terminos.filtrar_ampliados({"es": [None, 3], "en": "x"}, cargo) == []


def test_un_termino_ampliado_se_reconoce_con_grado_solo_si_el_titulo_lo_contiene():
    titulo = "Interaction Designer - Fintech"
    assert terminos.grado(titulo, cargo_operativo(DISENO))[0] is None
    con = cargo_operativo(DISENO, ampliados=["Interaction Designer"])
    assert terminos.grado(titulo, con) == ("similar", {"regla": "término ampliado", "termino": "Interaction Designer",
                                                      "grado": "similar"})
    assert terminos.grado("Interaction Designers", con)[0] == "similar"  # plural
    # Sin similitud textual: «Interactive Designer» se parece (≥ 90) pero no lo contiene.
    assert terminos.grado("Interactive Designer", con)[0] is None
    assert cargo_operativo(con) == con  # aplicarlo dos veces da lo mismo
    assert "terminos_ampliados" not in cargo_operativo(DISENO)  # sin ampliados, el cargo de siempre


# --- panel/ampliados.py: caché por cargo -------------------------------------------------------------------------

class Repo:
    def __init__(self, ajustes=None):
        self.ajustes, self.guardados = dict(ajustes or {}), 0

    def ajuste(self, clave, defecto=None):
        return self.ajustes.get(clave, defecto)

    def guardar_ajuste(self, clave, valor):
        self.ajustes[clave], self.guardados = valor, self.guardados + 1
        return valor


class Cfg:
    def __init__(self, *cargos):
        self.cargos = list(cargos)


OTRO = {**DISENO, "id": "c2", "nombre": "UX Researcher", "terminos_exactos": [], "terminos_similares": []}


def test_apagado_no_pide_nada():
    c, _ = cliente(BUENO)
    assert ampliados.actualizar(Repo(), Cfg(DISENO), cliente=c, opciones={"llm": {"terminos_activo": False}}) \
        == {"pedidos": 0, "nuevos": 0, "fallidos": 0, "pendientes": 0}
    assert c.llamadas == 0


def test_una_llamada_por_cargo_y_la_cache_evita_repetir():
    repo, (c, _) = Repo(), cliente(BUENO)
    r = ampliados.actualizar(repo, Cfg(DISENO, OTRO, {**OTRO, "id": "c3", "activo": False}), cliente=c, ahora=AHORA,
                             opciones=ENCENDIDO)
    assert r == {"pedidos": 2, "nuevos": 2, "fallidos": 0, "pendientes": 2} and c.llamadas == 2
    guardado = repo.ajustes[ampliados.CLAVE]["c1"]
    assert guardado["huella"] == terminos.huella_ampliados(DISENO) and guardado["en"] == ["Interaction Designer"]
    assert guardado["modelo"] == "modelo-falso"
    c2, _ = cliente(BUENO)
    assert ampliados.actualizar(repo, Cfg(DISENO, OTRO), cliente=c2, ahora=AHORA, opciones=ENCENDIDO)["pedidos"] == 0
    assert c2.llamadas == 0 and repo.guardados == 1
    # Un cargo editado se vuelve a pedir; el que no cambió, no.
    c3, _ = cliente(BUENO)
    editado = {**DISENO, "terminos_similares": ["Diseñador UX", "Diseñador UI"]}
    assert ampliados.actualizar(repo, Cfg(editado, OTRO), cliente=c3, ahora=AHORA, opciones=ENCENDIDO)["pedidos"] == 1


def test_un_fallo_se_reintenta_al_dia_siguiente_y_conserva_lo_anterior():
    repo = Repo({ampliados.CLAVE: {"c1": {"huella": terminos.huella_ampliados(DISENO), "fecha": AHORA.isoformat(),
                                          "es": [], "en": ["Interaction Designer"], "fallo": True}}})
    c, _ = cliente("roto")
    assert ampliados.actualizar(repo, Cfg(DISENO), cliente=c, ahora=AHORA + timedelta(hours=2),
                                opciones=ENCENDIDO)["pedidos"] == 0  # aún no
    r = ampliados.actualizar(repo, Cfg(DISENO), cliente=c, ahora=AHORA + timedelta(hours=25), opciones=ENCENDIDO)
    assert r["pedidos"] == 1 and r["fallidos"] == 1
    assert repo.ajustes[ampliados.CLAVE]["c1"]["en"] == ["Interaction Designer"]  # no se pierde por el fallo


def test_un_fallo_de_un_cargo_cambiado_no_hereda_terminos_viejos():
    repo = Repo({ampliados.CLAVE: {"c1": {"huella": "vieja", "fecha": AHORA.isoformat(), "es": [],
                                          "en": ["Graphic Artist"]}}})
    c, _ = cliente(llm.FalloDefinitivo("HTTP 401"))
    ampliados.actualizar(repo, Cfg(DISENO), cliente=c, ahora=AHORA, opciones=ENCENDIDO)
    assert repo.ajustes[ampliados.CLAVE]["c1"]["en"] == [] and repo.ajustes[ampliados.CLAVE]["c1"]["fallo"]


def test_el_tope_corta_y_lo_que_falta_queda_para_la_siguiente():
    repo, (c, _) = Repo(), cliente(BUENO, tope=1)
    r = ampliados.actualizar(repo, Cfg(DISENO, OTRO), cliente=c, ahora=AHORA, opciones=ENCENDIDO)
    assert r["pedidos"] == 1 and r["pendientes"] == 2 and list(repo.ajustes[ampliados.CLAVE]) == ["c1"]


def test_sin_proveedor_avisa_y_no_guarda(capsys):
    repo = Repo()
    r = ampliados.actualizar(repo, Cfg(DISENO), ahora=AHORA, opciones=ENCENDIDO)  # sin url ni clave
    assert r["pedidos"] == 0 and r["pendientes"] == 1 and repo.guardados == 0
    assert "[aviso] ampliados:sin-proveedor" in capsys.readouterr().err


def test_un_repo_que_falla_no_tumba_la_busqueda(capsys):
    class Roto(Repo):
        def ajuste(self, clave, defecto=None):
            raise RuntimeError("supabase caído")
    c, _ = cliente(BUENO)
    assert ampliados.actualizar(Roto(), Cfg(DISENO), cliente=c, opciones=ENCENDIDO)["pedidos"] == 0
    assert "[aviso] ampliados:actualizar" in capsys.readouterr().err


def test_por_cargo_solo_lo_vigente_y_filtrado(monkeypatch):
    guardados = {"c1": {"huella": terminos.huella_ampliados(DISENO), "es": ["Diseñador Gráfico"],
                        "en": ["Interaction Designer"]},
                 "c2": {"huella": "vieja", "es": [], "en": ["User Research Specialist"]}}
    cargos = {"c1": DISENO, "c2": OTRO}
    assert ampliados.por_cargo(guardados, cargos) == {"c1": ["Interaction Designer"]}
    # Un excluido nuevo del operador lo saca sin volver a pedir nada.
    assert ampliados.por_cargo(guardados, {"c1": {**DISENO, "terminos_excluidos": ["interaction"]}}) == {}
    repo = Repo({ampliados.CLAVE: guardados})
    assert ampliados.leer(repo, cargos) == {}  # apagado (la configuración del repo)
    monkeypatch.setattr(ampliados, "activo", lambda cfg=None: True)
    assert ampliados.leer(repo, cargos) == {"c1": ["Interaction Designer"]}


def test_ejecutor_y_panel_ven_el_mismo_cargo(monkeypatch):
    from panel import ejecutor, servicio
    monkeypatch.setattr(ampliados, "activo", lambda cfg=None: True)
    repo = Repo({"titulos_aprendidos": {"c1": ["Aprendido Designer"]},
                 ampliados.CLAVE: {"c1": {"huella": terminos.huella_ampliados(DISENO), "es": [],
                                          "en": ["Interaction Designer"]}}})

    class Cargo(dict):
        id = "c1"

        def model_dump(self, mode=None):
            return dict(self)
    assert ejecutor.ampliados_de(repo, Cfg(Cargo(DISENO))) == {"c1": ["Interaction Designer"]}
    vigente = servicio._ConfiguracionVigente(repo, {"cargos": [DISENO], "perfiles": []}).cargo("c1")
    assert vigente["terminos_ampliados"] == ["Interaction Designer"]
    assert "Aprendido Designer" in vigente["terminos_similares"]
    # La copia guardada en la asignación (el cargo operativo de la búsqueda) no cuenta como cargo editado.
    guardado = cargo_operativo(DISENO, ["Aprendido Designer"], ampliados=["Interaction Designer"])
    assert not servicio._cargo_editado(vigente, guardado)
    assert servicio._cargo_editado(cargo_operativo(DISENO, ["Aprendido Designer"]), guardado)
def test_filtro_no_deja_un_oficio_vecino_ni_uno_que_se_le_parece():
    pm = cargo_operativo({**DISENO, "nombre": "Product Manager", "terminos_exactos": [], "terminos_similares": [],
                          "terminos_excluidos": []})
    # «Product Owner» es otra familia del mapa (aunque el Product Manager tenga «product lead», que la toca), y
    # «Product Owners» se le parece tanto que `grado` lo reconocería. Un nombre del mismo oficio que el mapa no tiene
    # y no se parece a otro sí pasa.
    assert terminos.filtrar_ampliados({"es": [], "en": ["Product Owner", "Product Owners", "Platform Product Manager"]},
                                      pm) == ["Platform Product Manager"]


def test_la_busqueda_usa_los_ampliados_y_sin_ellos_queda_igual():
    from panel import ejecutor
    from panel.repositorio import configuracion_demo, hoy
    cfg = configuracion_demo()
    for p in cfg["perfiles"]:
        p["idiomas"] = ["es", "en"]
    antes, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy())
    cargo = next(f for f in antes if f["consultas_es"])
    cid = cargo["id"].removeprefix("cargo:")
    nuevos = ["Diseñador de Interacción Digital", "Interaction Designer Fintech"]
    despues, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy(), ampliados={cid: nuevos})
    f = next(x for x in despues if x["id"] == cargo["id"])
    assert f["consultas"][-2:] == nuevos and f["_control_cargo"]["terminos_ampliados"] == nuevos
    assert "Diseñador de Interacción Digital" in f["consultas_es"] or len(cargo["consultas_es"]) == 12
    assert "Interaction Designer Fintech" not in f["consultas_es"]
    # Sin ampliados, el mapa de la búsqueda es exactamente el de antes.
    igual, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy(), ampliados={})
    assert [x["consultas"] for x in igual] == [x["consultas"] for x in antes]
    assert all("terminos_ampliados" not in x["_control_cargo"] for x in igual)


def test_evaluacion_sin_conexion_cuenta_lo_nuevo_del_cargo():
    from buscador import evaluar_terminos
    vacantes = [{"id": "1", "titulo": "GIS Mapping Specialist (remote)", "idioma": "en", "modalidad": "remoto"},
                {"id": "2", "titulo": "Cartógrafo Digital", "idioma": "es", "modalidad": "remoto"},
                {"id": "3", "titulo": "Graphic Designer", "idioma": "en", "modalidad": "remoto"}]
    r = evaluar_terminos.evaluar(vacantes, {"Cartógrafo Digital": {"es": [], "en": ["GIS Mapping Specialist",
                                                                                   "Graphic Designer"]}}, "2026-11-28")
    fila = r["cargos"]["Cartógrafo Digital"]
    assert fila["terminos_propuestos"] == 2 and fila["terminos_usados"] == 1  # «Graphic Designer» es otro oficio
    assert all(pasos["cargo"] == [1, 2] for pasos in fila["perfiles"].values())
    assert "Cartógrafo Digital" in evaluar_terminos._texto(r)
