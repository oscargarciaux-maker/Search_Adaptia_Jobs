"""Sección 8.2 (decisión de Oscar, 28 nov): prueba de Apify al ritmo de Starter. Sin red y con datos ficticios.

Tope del mes respetado con el ritmo nuevo, crédito agotado = aviso (no avería) y la fuente parada hasta el mes
siguiente, prioridad a quien está bajo 5 sin fuente local, aviso del 80 % y medición sin datos personales."""
from copy import deepcopy
import json

import pytest

from buscador import apify, bodega, entrega, familias, medicion_apify, refuerzo, validacion
from buscador.estado_operativo import Central
from buscador.fuentes import linkedin_apify, publicaciones_apify
from panel import ejecutor
from panel.repositorio import configuracion_demo, hoy
from pruebas.panel.test_rescate import CON_DATO, _oferta

ACTOR = "curious_coder/linkedin-jobs-scraper"
COMBOS = [("qa", ["QA Engineer"], f"P{i}", {"location": "Colombia"}) for i in range(5)]


def _dia(n):
    return f"2026-12-{n:02d}"


# ── Ritmo y tope ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_config_separa_tope_del_plan_y_ritmo_diario():
    cfg = bodega.config()["apify"]
    assert 0 < cfg["ritmo_diario_usd"] <= cfg["tope_mensual_usd"] <= 100


def test_al_ritmo_de_starter_los_5_se_gastan_en_8_dias_y_nunca_se_pasa_del_tope():
    estado = {}
    por_dia = []
    for n in range(1, 13):
        control = apify.Presupuesto(estado, _dia(n), mensual=5, corrida=3, diario=0.63)
        # muchos intentos (reintentos, varias corridas del día): nunca más del ritmo ni del tope
        por_dia.append(round(sum(control.reservar(0.025) for _ in range(100)), 6))
    assert all(d <= 0.63 for d in por_dia)
    assert round(sum(por_dia), 6) <= 5 and round(sum(por_dia), 2) == 5.0
    assert sum(1 for d in por_dia if d > 0) == 8 and por_dia[8:] == [0, 0, 0, 0]


def test_sin_ritmo_se_reparte_el_tope_entre_los_dias_como_antes():
    control = apify.Presupuesto({}, _dia(1), mensual=5)
    assert control.diario == pytest.approx(5 / 31)
    assert apify.Presupuesto({}, _dia(1), mensual=5, diario=9).diario == 5  # el ritmo nunca pasa del tope


def test_con_starter_basta_cambiar_el_tope_a_19():
    estado = {}
    total = 0
    for n in range(1, 32):
        control = apify.Presupuesto(estado, _dia(n), mensual=19, corrida=3, diario=0.63)
        total += sum(control.reservar(0.025) for _ in range(100))
    assert round(total, 2) == 19.0


# ── Crédito agotado: aviso, no avería, y la fuente se detiene hasta el mes siguiente ────────────────────────────

class ClienteSinCredito:
    def __init__(self, error):
        self.ultimo_error, self.posts, self.error = None, 0, error

    def post_json(self, url, cuerpo, headers=None, timeout=None):
        self.posts += 1
        self.ultimo_error = dict(self.error)
        return None

    def json(self, *a, **k):
        raise AssertionError("sin ejecución no se consulta nada más")


@pytest.mark.parametrize("error", [{"http": 402, "tipo": "", "mensaje": ""},
                                   {"http": 403, "tipo": "not-enough-usage-to-run-paid-actor", "mensaje": "..."},
                                   {"http": 403, "tipo": "monthly-usage-limit-too-low", "mensaje": "..."}])
def test_credito_agotado_detiene_la_fuente_el_resto_del_mes(error):
    estado = {}
    control = apify.Presupuesto(estado, _dia(10), diario=0.63)
    cliente = ClienteSinCredito(error)
    crudas, stats = linkedin_apify.buscar(cliente, ACTOR, COMBOS, {}, _dia(10), token="token-ficticio",
                                          control_gasto=control)
    assert crudas == [] and cliente.posts == 1                  # no insiste con las demás búsquedas
    assert stats["credito_agotado"] and "error" not in stats    # aviso, no error de la fuente
    assert estado["bloqueado_tope"] == 5
    # La siguiente corrida (mismo mes, mismo estado guardado) ni siquiera llama a Apify.
    otra = ClienteSinCredito(error)
    _, stats2 = linkedin_apify.buscar(otra, ACTOR, COMBOS, {}, _dia(11), token="token-ficticio",
                                      control_gasto=apify.Presupuesto(estado, _dia(11), diario=0.63))
    assert otra.posts == 0 and stats2["credito_agotado"]
    # Si se compra Starter a mitad de mes (tope 19), vuelve a reservar sin borrar nada.
    assert apify.Presupuesto(estado, _dia(12), mensual=19, diario=0.63).reservar(0.025) == 0.025
    # El mes siguiente vuelve a reservar.
    assert apify.Presupuesto(estado, "2027-01-01", diario=0.63).reservar(0.025) == 0.025


def test_limit_reached_no_bloquea_el_mes():
    # Es un tipo genérico de Apify (también para límites pasajeros): no se toma como crédito agotado.
    estado = {}
    cliente = ClienteSinCredito({"http": 403, "tipo": "limit-reached", "mensaje": ""})
    _, stats = linkedin_apify.buscar(cliente, ACTOR, COMBOS[:1], {}, _dia(10), token="t",
                                     control_gasto=apify.Presupuesto(estado, _dia(10)))
    assert not stats.get("credito_agotado") and "bloqueado_tope" not in estado


def test_si_no_se_puede_anotar_el_bloqueo_se_avisa_y_la_fuente_igual_se_detiene(capsys):
    class ControlQueFalla(apify.Presupuesto):
        def marcar_agotado(self):
            raise RuntimeError("Supabase no respondió")
    cliente = ClienteSinCredito({"http": 402})
    crudas, stats = linkedin_apify.buscar(cliente, ACTOR, COMBOS, {}, _dia(10), token="t",
                                          control_gasto=ControlQueFalla({}, _dia(10)))
    assert crudas == [] and cliente.posts == 1 and stats["credito_agotado"] and "error" not in stats
    assert "[aviso] apify:bloqueo" in capsys.readouterr().err


def test_la_clave_rechazada_sigue_siendo_un_error_y_no_un_bloqueo():
    estado = {}
    cliente = ClienteSinCredito({"http": 401, "tipo": "user-or-token-not-found", "mensaje": ""})
    _, stats = linkedin_apify.buscar(cliente, ACTOR, COMBOS, {}, _dia(10), token="t",
                                     control_gasto=apify.Presupuesto(estado, _dia(10)))
    assert stats["clave_invalida"] and not estado.get("bloqueado")


def test_posts_sin_credito_tambien_bloquean():
    estado = {}
    control = apify.Presupuesto(estado, _dia(10), diario=0.63)
    _, _, stats = publicaciones_apify.buscar_posts(ClienteSinCredito({"http": 402}), "harvestapi/linkedin-post-search",
                                                   ["qa"], {"qa"}, _dia(10), token="t", control_gasto=control)
    assert stats["credito_agotado"] and estado["bloqueado_tope"] == 5 and "error" not in stats


def test_publicaciones_del_dia_sin_credito_tambien_bloquean():
    estado = {}
    _, stats = publicaciones_apify.buscar(ClienteSinCredito({"http": 402}), "harvestapi/linkedin-post-search", ["qa"],
                                          {"qa"}, _dia(10), token="t",
                                          control_gasto=apify.Presupuesto(estado, _dia(10), diario=0.63))
    assert stats["credito_agotado"] and estado["bloqueado_tope"] == 5 and "error" not in stats


def test_credito_agotado_no_es_averia():
    reporte = {"fuentes": {"LinkedIn (Apify) rescate": {"credito_agotado": True, "aviso": "sin crédito"}},
               "vacantes_en_bodega": 10,
               "entrega": {"meta_cumplida": True, "supabase": {"enviadas": 1, "filas": 1}}}
    assert validacion.errores(reporte) == []
    assert validacion.estado(reporte) == validacion.COMPLETA


def test_la_bodega_avisa_del_credito_agotado_y_del_80_por_ciento(tmp_path, capsys):
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    (trabajo / "apify_presupuesto.json").write_text(json.dumps(
        {"mes": hoy()[:7], "reservas": {hoy(): 4.1}, "bloqueado_tope": 5}), encoding="utf-8")
    salud = {"LinkedIn (Apify) rescate": {"avisos": 3, "usd_reservado": 0.4, "usd_reportado": 0.12}}
    medido = bodega._medir_apify(trabajo, hoy(), salud, {"tope_mensual_usd": 5, "ritmo_diario_usd": 0.63})
    err = capsys.readouterr().err
    assert "[aviso] apify" in err and "sin crédito" in err and "80 %" in err
    assert medido["corrida"]["avisos"] == 3 and medido["mes"]["usd_reportado"] == 0.12


def test_aviso_del_80_por_ciento():
    assert medicion_apify.avisos_de_gasto({"reservas": {"a": 3.9}}, 5) == []
    assert "80 %" in medicion_apify.avisos_de_gasto({"reservas": {"a": 2.0, "b": 2.1}}, 5)[0]
    assert "sin crédito" in medicion_apify.avisos_de_gasto({"reservas": {}, "bloqueado_tope": 5}, 5)[0]
    assert medicion_apify.avisos_de_gasto({"reservas": {}, "bloqueado_tope": 5}, 19) == []  # se compró Starter


# ── Presupuesto central (Supabase, SQL 023) ────────────────────────────────────────────────────────────────────────

class Sesion:
    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def post(self, url, **op):
        from types import SimpleNamespace
        self.llamadas.append((url, deepcopy(op)))
        r = self.respuestas.pop(0)
        return SimpleNamespace(status_code=200, json=lambda: r)

    def close(self):
        pass


def _central(monkeypatch, respuestas):
    from buscador import supabase
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://example.supabase.co", "prueba"))
    inicial = {"mes": hoy()[:7], "reservas": {}}
    espejo = []
    sesion = Sesion([inicial, *respuestas])
    return Central(inicial, lambda p: espejo.append(deepcopy(p)), sesion), sesion, espejo


def test_central_reserva_con_ritmo_y_marca_el_mes_agotado(monkeypatch):
    siguiente = {"mes": hoy()[:7], "reservas": {hoy(): 0.025}, "bloqueado_tope": None}
    bloqueado = dict(siguiente, bloqueado_tope=5.0)
    c, sesion, espejo = _central(monkeypatch, [{"monto_micro": 25000, "estado": siguiente}, bloqueado])
    control = c.control_apify(hoy(), 5, 3, 0.63)
    assert control.reservar(0.025) == 0.025
    url, op = sesion.llamadas[-1]
    assert url.endswith("/rpc/apify_reservar_ritmo")
    assert op["json"]["p_diario"] == 630000 and op["json"]["p_mensual"] == 5000000
    control.marcar_agotado()
    url, op = sesion.llamadas[-1]
    assert url.endswith("/rpc/apify_marcar_agotado") and op["json"]["p_mensual"] == 5000000
    assert espejo[-1]["bloqueado_tope"] == 5.0
    n = len(sesion.llamadas)
    assert control.reservar(0.025) == 0 and len(sesion.llamadas) == n  # bloqueado: ni se pide


def test_la_migracion_023_no_redefine_la_reserva_de_la_003():
    # El comportamiento de la 023 se prueba en PostgreSQL real (pruebas/probar_concurrencia_estado.py, job `sql`).
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[2] / "supabase/migraciones/023_apify_ritmo.sql").read_text(encoding="utf-8")
    assert "public.apify_reservar(" not in sql


# ── Prioridad: primero quien está bajo 5 sin fuente local ─────────────────────────────────────────────────────────

def test_rescate_va_primero_a_quien_no_tiene_fuente_local():
    cfg = configuracion_demo()
    cfg["perfiles"][0].update(vive_en="CO")   # Colombia: Computrabajo, Elempleo, Indeed…
    cfg["perfiles"][1].update(vive_en="KE")   # Kenia: solo LinkedIn, portales de empresas y Get on Board
    cfg["perfiles"][2]["activo"] = False
    llamadas = []
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        ofertas = [_oferta("Frontend Developer", f"F{n}", CON_DATO) for n in range(6)] + \
                  [_oferta("QA Engineer", f"Q{n}", CON_DATO) for n in range(6)]
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        _, stats = refuerzo.rescate_apify(ofertas, {}, hoy(), entrega.config(), familias.mapa(),
                                          lambda c: llamadas.append(c) or ([], {"busquedas": len(c)}),
                                          lambda a, b: a + b, max_busquedas=16)
    lugares = [c[2] for c in llamadas[0]]
    assert stats["perfiles_sin_fuente_local"] == 1
    kenia = [i for i, x in enumerate(lugares) if "KE" in x]
    colombia = [i for i, x in enumerate(lugares) if "CO" in x]
    assert kenia and colombia and max(kenia) < min(colombia)  # Kenia primero; Colombia (con déficit) después


def test_posts_van_primero_al_cargo_de_quien_no_tiene_fuente_local():
    cfg = configuracion_demo()   # perfiles 0–2: Product Designer (Colombia/España); 3: Frontend; 4: QA
    cfg["perfiles"][3].update(vive_en="KE")
    vistas = []
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        refuerzo.rescate_posts([], {}, hoy(), entrega.config(), familias.mapa(),
                               lambda c, v, e=None: vistas.append(c) or ([], [], {}), lambda a, b: a + b)
    assert "Frontend" in vistas[0][0]  # sin el cambio iba primero Product Designer (más déficit sumado)


# ── Medición agregada, sin datos personales ────────────────────────────────────────────────────────────────────────

class P:
    def __init__(self, pid):
        self.id = pid


def test_medicion_cuenta_lo_que_solo_trajo_apify_y_quien_llega_a_5():
    apify_v = {"fuentes": ["LinkedIn (Apify)"]}
    mixta = {"fuentes": ["LinkedIn", "LinkedIn (Apify)"]}   # otra fuente también la tenía: no cuenta
    otra = {"fuentes": ["Indeed"]}
    seleccion = {"a1": apify_v, "m1": mixta, **{f"o{i}": otra for i in range(8)}}
    filas = ([{"perfil_id": "p1", "vacante_id": v, "explicacion": []} for v in ("a1", "o1", "o2", "o3", "o4")] +
             [{"perfil_id": "p2", "vacante_id": v, "explicacion": []} for v in ("o5", "o6", "o7", "m1")] +
             [{"perfil_id": "p2", "vacante_id": "post9", "explicacion": [{"tipo": "post"}]}] +
             [{"perfil_id": "com", "vacante_id": "a1", "explicacion": []}])
    conteos = medicion_apify.contar_asignacion(filas, seleccion, [P("p1"), P("p2"), P("com")],
                                               lambda p: p.id == "com", 5)
    assert conteos == {"seleccion": 1, "utiles": 2, "perfiles_a_5": 2}


def test_acumulado_del_mes_y_costo_por_vacante_util(tmp_path):
    d1, d2 = hoy()[:8] + "01", hoy()[:8] + "02"
    medicion_apify.anotar_corrida(tmp_path, d1, {"usd_reservado": 0.5, "usd_reportado": 0.2, "avisos": 10})
    medicion_apify.anotar_corrida(tmp_path, d1, {"usd_reservado": 0.1, "usd_reportado": 0.05, "avisos": 2})
    medicion_apify.anotar_asignacion(tmp_path, d1, {"seleccion": 3, "utiles": 2, "perfiles_a_5": 1})
    medicion_apify.anotar_asignacion(tmp_path, d1, {"seleccion": 1, "utiles": 1, "perfiles_a_5": 0})  # se queda el mayor
    datos = medicion_apify.anotar_asignacion(tmp_path, d2, {"seleccion": 2, "utiles": 3, "perfiles_a_5": 1})
    mes = medicion_apify.del_mes(datos)
    assert mes["usd_reservado"] == 0.6 and mes["usd_reportado"] == 0.25 and mes["avisos"] == 12
    assert mes["corridas"] == 2 and mes["utiles"] == 5 and mes["perfiles_a_5"] == 2
    assert mes["usd_por_vacante_util"] == 0.05
    # Mes nuevo: se mide de cero.
    assert medicion_apify.leer(tmp_path, "2099-01-01")["por_dia"] == {}


def test_la_medicion_no_lleva_datos_personales(tmp_path):
    filas = [{"perfil_id": "perfil-secreto", "vacante_id": "vacante-secreta", "explicacion": [],
              "cliente_id": "cliente-secreto"}]
    conteos = medicion_apify.contar_asignacion(filas, {"vacante-secreta": {"fuentes": ["LinkedIn (Apify)"],
                                                                         "titulo": "Cargo secreto"}},
                                               [P("perfil-secreto")], lambda p: False, 5)
    medicion_apify.anotar_asignacion(tmp_path, hoy(), conteos)
    texto = (tmp_path / medicion_apify.ARCHIVO).read_text(encoding="utf-8") + medicion_apify.linea(
        medicion_apify.leer(tmp_path, hoy()))
    for privado in ("secreto", "secreta", "Cargo"):
        assert privado not in texto
    datos = json.loads((tmp_path / medicion_apify.ARCHIVO).read_text(encoding="utf-8"))
    assert set(datos) == {"mes", "por_dia"}
    assert set(datos["por_dia"][hoy()]) <= set(medicion_apify.DE_CORRIDA + medicion_apify.DE_ASIGNACION)


def test_el_reporte_publico_conserva_la_medicion_de_apify():
    from buscador import estado_privado
    reporte = {"apify": {"corrida": {"usd_reservado": 0.4}, "mes": medicion_apify.del_mes({"por_dia": {}}),
                         "avisos": [], "tope_mensual_usd": 5, "ritmo_diario_usd": 0.63}}
    publico = estado_privado.salud_publica(reporte)
    assert publico["apify"]["corrida"]["usd_reservado"] == 0.4 and "apify" not in publico["campos_no_publicados"]
    assert "Apify en el mes" in estado_privado.resumen(publico)
