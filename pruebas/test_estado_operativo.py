"""Fallos de red/cortes y recuperación. Las transacciones/concurrencia se prueban en PostgreSQL real."""
from copy import deepcopy
from collections import Counter
import json
from types import SimpleNamespace

import pytest
import requests

from buscador import bodega, entrega, incremental, supabase, validacion
from buscador.estado_operativo import Central, Cola
from pruebas.test_catalogo_frescura import oferta, HOY, AHORA


class Sesion:
    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def post(self, url, **op):
        self.llamadas.append((url, deepcopy(op)))
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return SimpleNamespace(status_code=200, json=lambda: respuesta)

    def close(self):
        self.cierres = getattr(self, "cierres", []) + [len(self.llamadas)]


@pytest.fixture
def presupuesto():
    return {"mes": HOY[:7], "reservas": {HOY: 0.01}}


def central(monkeypatch, presupuesto, respuestas=()):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://example.supabase.co", "prueba"))
    espejo = []
    sesion = Sesion([presupuesto, *respuestas])
    c = Central(presupuesto, lambda p: espejo.append(deepcopy(p)), sesion)
    return c, sesion, espejo


def test_reserva_confirmada_se_refleja_antes_de_autorizar(monkeypatch, presupuesto):
    siguiente = {"mes": HOY[:7], "reservas": {HOY: 0.035}}
    c, sesion, espejo = central(monkeypatch, presupuesto, [{"monto_micro": 25000, "estado": siguiente}])
    control = c.control_apify(HOY)
    assert control.reservar(0.025) == 0.025
    assert espejo[-1] == siguiente and control.reservado == 0.025
    solicitud = sesion.llamadas[-1][1]["json"]
    assert solicitud["p_monto"] == 25000 and solicitud["p_mensual"] == 5000000
    assert solicitud["p_ejecucion"] == c.ejecucion


@pytest.mark.parametrize("respuesta", [requests.Timeout(), {"monto_micro": -1},
    {"monto_micro": 30000}, {"monto_micro": 25000, "estado": {}}, {}])
def test_reserva_ambigua_no_autoriza_ni_reintenta(monkeypatch, presupuesto, respuesta):
    c, sesion, espejo = central(monkeypatch, presupuesto, [respuesta])
    control = c.control_apify(HOY)
    with pytest.raises(RuntimeError):
        control.reservar(0.025)
    assert len(sesion.llamadas) == 2 and control.reservado == 0
    assert espejo == [presupuesto]


def test_tras_un_rato_sin_uso_se_abre_conexion_nueva_antes_de_pedir_y_sin_reintentar(monkeypatch, presupuesto):
    # Contrato v51: la reserva del refuerzo de Apify fallaba a diario. Era la primera llamada tras más de una hora sin
    # usar la conexión con Supabase.
    from buscador import estado_operativo
    siguiente = {"mes": HOY[:7], "reservas": {HOY: 0.035}}
    c, sesion, _ = central(monkeypatch, presupuesto, [{"monto_micro": 25000, "estado": siguiente},
                                                      {"monto_micro": 25000, "estado": siguiente}])
    reloj = [1000.0]
    monkeypatch.setattr(estado_operativo.time, "monotonic", lambda: reloj[0])
    c._ultimo_uso = reloj[0]
    reloj[0] += estado_operativo.INACTIVIDAD - 1
    c.control_apify(HOY).reservar(0.025)
    assert not hasattr(sesion, "cierres")     # uso reciente: la misma conexión
    reloj[0] += estado_operativo.INACTIVIDAD + 1
    c.control_apify(HOY).reservar(0.025)
    assert sesion.cierres == [2]              # se cerró antes de la tercera petición…
    assert len(sesion.llamadas) == 3          # …y cada reserva se pidió una sola vez


def test_el_error_dice_la_causa_sin_direccion_ni_clave(monkeypatch, presupuesto):
    c, sesion, _ = central(monkeypatch, presupuesto, [requests.ConnectionError("https://example.supabase.co clave")])
    with pytest.raises(RuntimeError) as e:
        c.rpc("apify_reservar", {})
    texto = str(e.value)
    assert "apify_reservar: ConnectionError" in texto and "sin reintento automático" in texto
    assert "example.supabase.co" not in texto and "clave" not in texto

    def pagina_de_error(url, **op):  # un 502 de la pasarela con una página en vez de datos
        def sin_json():
            raise ValueError("no es JSON")
        return SimpleNamespace(status_code=502, json=sin_json)
    sesion.post = pagina_de_error
    with pytest.raises(RuntimeError, match="apify_reservar: HTTP 502 sin datos"):
        c.rpc("apify_reservar", {})


def test_fallo_copia_local_no_devuelve_autorizacion(monkeypatch, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto, [{"monto_micro": 25000, "estado": presupuesto}])
    def falla(p): raise OSError("Disco lleno")
    c.guardar_presupuesto = falla
    control = c.control_apify(HOY)
    with pytest.raises(OSError): control.reservar(0.025)
    assert control.reservado == 0


def test_credencial_ausente_no_habilita_alternativa(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("", ""))
    with pytest.raises(RuntimeError, match="requiere credenciales"):
        Central({}, lambda p: None)


def test_inicializacion_reenvia_corte_y_no_inventa_saldo(monkeypatch, presupuesto):
    c, sesion, _ = central(monkeypatch, presupuesto)
    assert sesion.llamadas[0][1]["json"] == {"p_importar": presupuesto}
    c.sesion = Sesion([requests.Timeout()])
    with pytest.raises(RuntimeError): c.rpc("operacion_inicializar", {"p_importar": {}})
    assert len(c.sesion.llamadas) == 1


def test_cola_recupera_sin_archivos_y_preserva_version_nueva(monkeypatch, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto)
    remoto = {"id": "a", "observed_at": "2026-11-04T14:00:00Z", "status": "closed"}
    monkeypatch.setattr(c, "leer", lambda *a: [{"identificador": "a", "payload": remoto, "revision": 40}])
    monkeypatch.setattr(c, "rpc", lambda *a: pytest.fail("No sobrescribir pendiente remoto más nuevo"))
    copias = []
    recuperadas, guardar = c.cola("catalogo", {"a": dict(remoto, observed_at=AHORA, status="active")}, copias.append)
    assert recuperadas == {"a": remoto} and copias == [recuperadas]
    recuperadas.clear()
    assert guardar.__self__.valores["a"] == remoto  # la confirmación mantiene una copia propia


def test_corte_despues_de_copia_antes_de_rpc_conserva_pendiente(monkeypatch, presupuesto):
    c, sesion, _ = central(monkeypatch, presupuesto, [requests.Timeout()])
    copias = []
    cola = Cola(c, "ofertas", lambda p: copias.append(deepcopy(p)))
    with pytest.raises(RuntimeError): cola.guardar({"x": {"external_id": "x"}})
    assert copias == [{"x": {"external_id": "x"}}] and not cola.revisiones
    assert len(sesion.llamadas) == 2


def test_confirmar_envia_revision_y_conserva_estado_si_se_pierde_respuesta(monkeypatch, presupuesto):
    c, sesion, _ = central(monkeypatch, presupuesto, [requests.Timeout(), ["x"]])
    cola = Cola(c, "registro")
    cola.valores, cola.revisiones = {"x": {"vacante_id": "x"}}, {"x": 76}
    with pytest.raises(RuntimeError): cola.guardar({})
    assert cola.revisiones == {"x": 76}
    assert sesion.llamadas[-1][1]["json"]["p_elementos"] == [{"identificador": "x", "revision": 76}]
    # Simula una nueva recuperación: confirmar una ausencia ya confirmada es idempotente en SQL.
    cola.guardar({})
    assert not cola.revisiones and not cola.valores


def test_confirmacion_incompleta_no_borra_copia_confirmable(monkeypatch, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto, [[]])
    cola = Cola(c, "ofertas")
    cola.valores, cola.revisiones = {"x": {}}, {"x": 76}
    with pytest.raises(RuntimeError, match="incompleta"): cola.guardar({})
    assert cola.revisiones == {"x": 76}


def test_lote_confirmado_se_retira_solo_del_temporal(monkeypatch, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto, [[{"identificador": HOY, "revision": 0}]])
    lote = {"fecha": HOY, "elegidas": {"ux-ui-designer": [[oferta(), "exacto"]]}}
    c.lote.valores, c.lote.revisiones = {HOY: deepcopy(lote)}, {HOY: 30}
    c.limpiar_lotes_confirmados()
    assert not c.lote.valores and lote["elegidas"]


def test_lote_previo_reconstruye_colas_con_fecha_original(monkeypatch, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto)
    v = dict(oferta(), _capturada_entrega=AHORA)
    c.lote.valores = {HOY: {"fecha": HOY, "elegidas": {"ux-ui-designer": [[v, "exacto"]]}}}
    ofertas, registro, copias = {}, {}, []
    memoria = c.recuperar_pendientes(ofertas, lambda p: copias.append(deepcopy(p)), registro,
                                    lambda p: copias.append(deepcopy(p)))
    assert ofertas and registro[v["id"]]["delivery_date"] == HOY
    assert registro[v["id"]]["selected_at"] == AHORA and len(copias) == 2
    assert all(f["delivery_date"] == HOY for f in ofertas.values())
    assert memoria[v["id"]] == HOY and memoria[v["enlace"]] == HOY


def test_leer_cola_pagina_por_clave_no_offset(monkeypatch, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto)
    llamadas = []
    def get(url, **op):
        llamadas.append(op["params"])
        datos = [{"identificador": f"{i:03}", "payload": {}, "revision": i + 1} for i in range(100)] if len(llamadas) == 1 else []
        return SimpleNamespace(status_code=200, json=lambda: datos)
    c.sesion.get = get
    assert len(c.leer("catalogo")) == 100
    assert llamadas[-1]["identificador"] == "gt.099" and "offset" not in llamadas[-1]


def test_003_faltante_detiene_antes_de_capturar(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTADO_SUPABASE_ACTIVO", "true")
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "exigir_catalogo", lambda: None)
    def falla(*a, **k): raise RuntimeError("Falta 003")
    monkeypatch.setattr(Central, "__init__", falla)
    monkeypatch.setattr(incremental, "recoger", lambda *a, **k: pytest.fail("No iniciar captura"))
    with pytest.raises(RuntimeError, match="003"):
        bodega.correr(tmp_path, modo="incremental", hoy=HOY)


def test_horaria_recupera_colas_y_seleccion_sin_gastar_ni_crear_entrega(monkeypatch, tmp_path, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto)
    monkeypatch.setenv("ESTADO_SUPABASE_ACTIVO", "true")
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "exigir_catalogo", lambda: None)
    v = dict(oferta(), _capturada_entrega=AHORA)
    lote = {"fecha": HOY, "elegidas": {"ux-ui-designer": [[v, "exacto"]]}}
    monkeypatch.setattr(supabase, "leer_lote", lambda hoy: deepcopy(lote))
    monkeypatch.setattr(Central, "__init__", lambda self, *a: self.__dict__.update(c.__dict__))
    def recuperar(self, nombre, local, guardar):
        p = {"anterior": {"external_id": "anterior"}} if nombre == "ofertas" else {}
        return p, guardar
    monkeypatch.setattr(Central, "cola", recuperar)
    monkeypatch.setattr(Central, "cargar_lote", lambda self, hoy, local: local)
    monkeypatch.setattr(Central, "limpiar_lotes_confirmados", lambda self: None)
    monkeypatch.setattr(entrega, "correr", lambda *a, **k: pytest.fail("No crear otra entrega"))
    from buscador.fuentes import linkedin_apify
    monkeypatch.setattr(linkedin_apify, "buscar", lambda *a, **k: pytest.fail("No usar Apify en la horaria"))
    monkeypatch.setattr(incremental, "recoger", lambda *a, **k: ([], set(), set(), {}))
    monkeypatch.setattr(bodega, "limpiar", lambda *a, **k: ([v], Counter(), Counter()))
    cfg = bodega.config()
    cfg["verificacion_enlaces"] = {"vacantes_por_captura": 0, "segundos_captura": 0}
    monkeypatch.setattr(bodega, "config", lambda: cfg)
    def subir(rows, **op):
        return {"filas": len(rows), "enviadas": len(rows), "confirmadas": [r.get("id") or r.get("external_id") for r in rows]}
    monkeypatch.setattr(supabase, "subir_catalogo", subir)
    monkeypatch.setattr(supabase, "subir", subir)
    r = bodega.correr(tmp_path, modo="incremental", hoy=HOY)
    assert r["estado_operativo"]["reintentos"]["ofertas"]["enviadas"] == 1
    assert not any(r["estado_operativo"]["pendientes"].values())
    assert r["verificacion_enlaces"]["seleccion_del_dia"]["vacantes"] == 1
    assert json.loads((tmp_path / "trabajo/lote_entrega.json").read_text(encoding="utf-8"))["elegidas"]


def test_operacion_pendiente_no_se_declara_sincronizada():
    r = {"catalogo": {"filas": 1, "enviadas": 1}, "estado_operativo": {
        "activo": True, "pendientes": {"registro": 1}, "lotes_pendientes": 1}}
    assert validacion.errores_catalogo(r)


def test_diaria_recupera_canonico_antes_de_importar_archivo_atrasado(monkeypatch, tmp_path, presupuesto):
    c, _, _ = central(monkeypatch, presupuesto)
    monkeypatch.setenv("ESTADO_SUPABASE_ACTIVO", "true")
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "exigir_catalogo", lambda: None)
    monkeypatch.setattr(Central, "__init__", lambda self, *a: self.__dict__.update(c.__dict__))
    monkeypatch.setattr(Central, "cola", lambda self, n, p, g: (p, g))
    vs = [dict(oferta(i), _capturada_entrega=AHORA) for i in (1, 2)]
    completo = {"fecha": HOY, "elegidas": {"ux-ui-designer": [[v, "exacto"] for v in vs]}}
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    (trabajo / "lote_entrega.json").write_text(json.dumps({"fecha": HOY,
        "elegidas": {"ux-ui-designer": [[vs[0], "exacto"]]}}), encoding="utf-8")
    monkeypatch.setattr(supabase, "leer_lote", lambda hoy: deepcopy(completo))
    def comprobar(self, hoy, local):
        assert local == completo
        raise RuntimeError("Canónico recuperado antes de importar el temporal")
    monkeypatch.setattr(Central, "cargar_lote", comprobar)
    monkeypatch.setattr(bodega, "recoger", lambda *a, **k: pytest.fail("No iniciar fuentes en este ensayo"))
    with pytest.raises(RuntimeError, match="Canónico recuperado"):
        bodega.correr(tmp_path, hoy=HOY)


@pytest.fixture(autouse=True)
def reconciliacion_de_integracion_simulada(monkeypatch):
    from buscador import supabase
    monkeypatch.setattr(supabase, "reconciliar_ofertas", lambda: {"archivadas": 0, "sin_identificar": 0})
