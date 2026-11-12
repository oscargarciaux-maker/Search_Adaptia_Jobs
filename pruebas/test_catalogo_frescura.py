"""Captura independiente, precisión temporal, historial y lotes diarios recuperables."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from buscador import bodega, catalogo, contrato, entrega, incremental, paises, preparacion, supabase, tiempos, vacante
from buscador.fuentes import ats

HOY = "2026-11-04"
AHORA = "2026-11-04T12:00:00Z"
TEXTO = "We are hiring a UX Designer to improve our digital product through user research and prototyping. " * 5


def oferta(n=1, empresa=None, **op):
    return vacante.crear("UX Designer", empresa or f"Empresa {n}", f"https://jobs.lever.co/a/{n}", "Lever",
        ubicacion="Remote - LATAM", descripcion=TEXTO + f" Position {n}", hoy=HOY, capturada=AHORA, **op)


@pytest.mark.parametrize("valor", ["2026-11-04", "2026-11-04T10:00:00", "incorrecto", None])
def test_no_inventar_hora_para_fecha_sin_precision(valor):
    assert tiempos.instante(valor) == ""


def test_normalizar_zona_horaria_y_distinguir_detectada():
    assert tiempos.instante("2026-11-04T06:00:00-05:00") == "2026-11-04T11:00:00Z"
    v = oferta(fecha="2026-11-04")
    assert v["publicada_en"] == "" and v["detectada_en"] == AHORA
    assert oferta(fecha="2026-11-04T06:00:00-05:00")["publicada_en"] == "2026-11-04T11:00:00Z"


def test_greenhouse_updated_no_es_fecha_de_publicacion():
    datos = {"jobs": [{"title": "UX Designer", "absolute_url": "https://boards.greenhouse.io/a/1",
                        "updated_at": AHORA, "content": TEXTO}]}
    row = ats.vacantes_de("greenhouse", datos, "Empresa", "a")[0]
    assert row["fecha"] == "" and row["publicada_en"] == ""
    datos["jobs"][0]["first_published"] = "2026-11-03T10:00:00Z"
    assert ats.vacantes_de("greenhouse", datos, "Empresa", "a")[0]["publicada_en"] == "2026-11-03T10:00:00Z"


def test_releer_bodega_no_refresca_la_ultima_observacion():
    v = oferta()
    assert vacante.reetiquetar(dict(v))["vista_en"] == AHORA
    nueva = dict(v, vista_en="2026-11-04T13:00:00Z", detectada_en="2026-11-04T13:00:00Z")
    unida = vacante.unir(v, nueva)
    assert unida["detectada_en"] == AHORA and unida["vista_en"] == nueva["vista_en"]
    legado = dict(v)
    legado.pop("detectada_en")
    assert vacante.unir(legado, nueva)["detectada_en"] == ""


@pytest.mark.parametrize("titulo,lugar", [
    ("Product Owner (Remote in Estonia)", "Estonia"),
    ("Freelance Software Tester (Remote in Réunion, Monaco)", "Réunion or Monaco"),
    ("Freelance Software Tester (Remote in Germany & the Netherlands)", "Germany or the Netherlands"),
])
def test_revisar_inventario_retira_residencias_fuera_de_cobertura_sin_cambiar_snapshot(titulo, lugar):
    v = oferta()
    v.update(titulo=titulo, ubicacion="Remote in EMEA", paises=["ES"],
             _descripcion="Location: Must be physically located in " + lugar + ". " + TEXTO)
    original = deepcopy(v)
    retiradas = []
    salida, _, _ = bodega.limpiar([v], [], HOY, 30, set(), set(), retiradas=retiradas)
    assert not salida and len(retiradas) == 1
    assert retiradas[0][1:] == ("archived", "sin elegibilidad regional")
    assert retiradas[0][0]["paises"] == [] and v == original


def test_unir_no_pierde_hora_al_cruzar_medianoche_utc():
    v = oferta(fecha="2026-11-03T23:30:00-05:00")
    assert vacante.unir(v, dict(v))["publicada_en"] == "2026-11-04T04:30:00Z"


def test_schema_ats_malformado_no_confirma_cierre():
    class Cliente:
        def json(self, *a, **op):
            return {}
    _, leidas, stats = ats.buscar(Cliente(), [{"empresa": "Empresa", "sistema": "greenhouse", "slug": "a"}])
    assert not leidas and stats["fallidos"] == 1


def test_catalogo_no_tiene_cuota_de_20_y_reintenta_sin_borrar():
    vs = [oferta(i) for i in range(25)]
    pendientes, estados = {}, []
    def fallo(rows):
        return {"filas": len(rows), "enviadas": 0, "errores": ["503"], "confirmadas": []}
    r = catalogo.sincronizar(vs, [], pendientes, fallo, lambda p: estados.append(deepcopy(p)), AHORA)
    assert r["activas_elegibles"] == r["pendientes"] == 25 and estados[0]
    def exito(rows):
        assert all(row["status"] == "active" for row in rows)
        return {"filas": len(rows), "enviadas": len(rows), "confirmadas": [row["id"] for row in rows]}
    r = catalogo.sincronizar([], [], pendientes, exito, lambda p: None, AHORA)
    assert r["pendientes"] == 0 and not pendientes


def test_pendiente_mas_nuevo_no_se_pierde_por_reintento_antiguo():
    v = oferta()
    nuevo = catalogo.fila(v, "2026-11-04T15:00:00Z", "closed", "cierre observado")
    pendientes = {v["id"]: nuevo}
    catalogo.sincronizar([v], [], pendientes, lambda rows: {"confirmadas": []}, lambda p: None, AHORA)
    assert pendientes[v["id"]]["status"] == "closed"


def test_antiguedad_no_se_confunde_con_cierre():
    vieja = oferta(1, fecha="2026-08-01")
    cerrada = oferta(2)
    eventos = []
    bodega.limpiar([vieja, cerrada], [], HOY, 30, set(), {cerrada["empresa"]}, retiradas=eventos)
    assert {v["id"]: estado for v, estado, _ in eventos} == {vieja["id"]: "archived", cerrada["id"]: "closed"}


def test_perder_calidad_retira_del_catalogo_sin_borrar_historia():
    v = dict(oferta(), _descripcion="Sin contenido verificable")
    pendientes = {}
    catalogo.sincronizar([v], [], pendientes, lambda rows: {"confirmadas": []}, lambda p: None, AHORA)
    assert pendientes[v["id"]]["status"] == "archived"
    assert pendientes[v["id"]]["reason"] == "sin descripción completa"


def _hora(n):
    return (datetime(2026, 11, 4, 12, tzinfo=timezone.utc) + timedelta(hours=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _visto(v, n):
    return dict(v, vista_en=_hora(n), visto_ultima_vez=_hora(n)[:10])


def _exito(enviadas):
    def subir(rows):
        enviadas.append([row["id"] for row in rows])
        return {"filas": len(rows), "enviadas": len(rows), "confirmadas": [row["id"] for row in rows]}
    return subir


def test_volver_a_ver_una_vacante_no_reescribe_todo_el_catalogo_cada_hora():
    vs = [oferta(i) for i in range(60)]
    memoria, enviadas, pendientes = {}, [], {}
    r = catalogo.sincronizar([_visto(v, 0) for v in vs], [], pendientes, _exito(enviadas), lambda p: None, _hora(0), memoria)
    assert len(enviadas[0]) == 60 and r["sin_cambios"] == 0 and len(memoria) == 60
    por_hora = []
    for n in range(1, 7):  # solo cambia la marca de «vista»: cada fila se renueva una vez por rotación
        r = catalogo.sincronizar([_visto(v, n) for v in vs], [], pendientes, _exito(enviadas), lambda p: None, _hora(n), memoria)
        por_hora.append(enviadas[-1])
        assert r["filas"] == r["enviadas"] == len(enviadas[-1]) and r["sin_cambios"] == 60 - len(enviadas[-1])
    assert sorted(i for lote in por_hora for i in lote) == sorted(v["id"] for v in vs)
    assert max(len(lote) for lote in por_hora) < 60 and not pendientes


def test_cambio_de_contenido_cierre_o_verificacion_se_envia_en_la_hora():
    vs = [oferta(i) for i in range(12)]
    memoria, enviadas = {}, []
    catalogo.sincronizar(vs, [], {}, _exito(enviadas), lambda p: None, _hora(0), memoria)
    hora = catalogo._hora(_hora(1))
    en_turno = {v["id"] for v in vs if int(v["id"][:8], 16) % catalogo.ROTACION_HORAS == hora % catalogo.ROTACION_HORAS}
    verificada = dict(vs[0], verificacion={"estado": "verificada", "enlaces": [{"comprobada_en": _hora(1)}]})
    cerrada = dict(vs[1], _descripcion="")  # deja de ser entregable: pasa a archivada
    catalogo.sincronizar([verificada, cerrada, *vs[2:]], [], {}, _exito(enviadas), lambda p: None, _hora(1), memoria)
    assert set(enviadas[-1]) == {vs[0]["id"], vs[1]["id"]} | en_turno


def test_fallo_al_subir_no_marca_como_sincronizado_y_se_reintenta():
    v = oferta()
    memoria, pendientes = {}, {}
    catalogo.sincronizar([v], [], pendientes, lambda rows: {"confirmadas": [], "errores": ["503"]}, lambda p: None,
                         _hora(0), memoria)
    assert v["id"] in pendientes and not memoria
    enviadas = []
    catalogo.sincronizar([v], [], pendientes, _exito(enviadas), lambda p: None, _hora(1), memoria)
    assert enviadas == [[v["id"]]] and memoria[v["id"]][1] == _hora(1) and not pendientes


def test_sin_memoria_o_tras_doce_horas_se_envia_completo_y_se_olvidan_retiradas():
    vs = [oferta(i) for i in range(30)]
    memoria, enviadas = {}, []
    catalogo.sincronizar(vs, [], {}, _exito(enviadas), lambda p: None, _hora(0), memoria)
    catalogo.sincronizar(vs, [], {}, _exito(enviadas), lambda p: None, _hora(12), memoria)
    assert len(enviadas[-1]) == 30
    catalogo.sincronizar(vs[:10], [], {}, _exito(enviadas), lambda p: None, _hora(13), memoria)
    assert set(memoria) == {v["id"] for v in vs[:10]}
    catalogo.sincronizar(vs, [], {}, _exito(enviadas), lambda p: None, _hora(14), {})
    assert len(enviadas[-1]) == 30


def test_frescura_no_confunde_fecha_desconocida_con_publicacion_reciente():
    vs = [oferta(1, publicada_en="2026-11-04T11:00:00Z"), oferta(2, fecha="2026-11-04")]
    r = tiempos.medir(vs, AHORA)
    assert r["con_hora_publicacion"] == r["sin_hora_publicacion"] == r["publicadas_24h_confirmadas"] == 1
    assert r["observadas_2h"] == 2 and r["retardo_publicacion_deteccion_p90_min"] == 60


def config_dos(monkeypatch):
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=2)
    monkeypatch.setattr(entrega, "config", lambda: cfg)


def test_repetir_dia_no_selecciona_otras_20_y_completa_solo_plazas(monkeypatch, tmp_path):
    config_dos(monkeypatch)
    memoria, lote, pendientes = {}, {}, {}
    def guardar(l):
        lote.clear()
        lote.update(deepcopy(l))
    subir = lambda rows: {"filas": len(rows), "enviadas": len(rows), "confirmadas": [r["external_id"] for r in rows]}
    r1 = entrega.correr([oferta(1)], memoria, HOY, AHORA, tmp_path, subir=subir, pendientes=pendientes,
                        persistir_lote=guardar)
    r2 = entrega.correr([oferta(i) for i in range(1, 6)], memoria, HOY, "2026-11-04T13:00:00Z", tmp_path,
                        subir=subir, pendientes=pendientes, lote=deepcopy(lote), persistir_lote=guardar)
    ids = {v["id"] for v, _ in lote["elegidas"]["ux-ui-designer"]}
    r3 = entrega.correr([oferta(i) for i in range(1, 10)], memoria, HOY, "2026-11-04T14:00:00Z", tmp_path,
                        subir=subir, pendientes=pendientes, lote=deepcopy(lote), persistir_lote=guardar)
    assert (r1["vacantes"], r2["vacantes"], r3["vacantes"]) == (1, 2, 2)
    assert ids == {v["id"] for v, _ in lote["elegidas"]["ux-ui-designer"]}
    assert lote["elegidas"]["ux-ui-designer"][0][0]["_capturada_entrega"] == AHORA


def test_lote_permanece_si_se_interrumpe_la_cola(monkeypatch, tmp_path):
    config_dos(monkeypatch)
    lote = {}
    def guardar(l): lote.update(deepcopy(l))
    def interrumpir(p): raise OSError("interrumpido")
    with pytest.raises(OSError):
        entrega.correr([oferta(1)], {}, HOY, AHORA, tmp_path, persistir=interrumpir, persistir_lote=guardar)
    assert lote["elegidas"]
    pendientes = {}
    entrega.correr([], {}, HOY, AHORA, tmp_path, lote=lote, pendientes=pendientes)
    assert len(pendientes) == 1


def test_tope_por_empresa_se_aplica_al_lote_completo(monkeypatch, tmp_path):
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=3)
    monkeypatch.setattr(entrega, "config", lambda: cfg)
    iniciales = {"ux-ui-designer": [(oferta(1, "Acme"), "exacto"), (oferta(2, "Acme"), "exacto")]}
    elegidas, _ = entrega.elegir([oferta(3, "Acme"), oferta(4, "Otra")], {}, HOY, iniciales=iniciales)
    assert len(elegidas["ux-ui-designer"]) == 3
    assert [v["empresa"] for v, _ in elegidas["ux-ui-designer"]].count("Acme") == 2


def test_captura_incremental_no_crea_lotes_ni_usa_apify(monkeypatch, tmp_path):
    from buscador.fuentes import linkedin_apify
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "exigir_catalogo", lambda: None)
    def prohibido(*a, **k): raise AssertionError("No debe seleccionar ni consumir Apify")
    monkeypatch.setattr(entrega, "correr", prohibido)
    monkeypatch.setattr(linkedin_apify, "buscar", prohibido)
    crudas = [{"titulo": "UX Designer", "empresa": "Empresa", "enlace": "https://jobs.lever.co/a/1",
                "fuente": "Lever", "descripcion": TEXTO, "ubicacion": "Remote - LATAM"}]
    monkeypatch.setattr(incremental, "recoger", lambda *a, **k: (crudas, set(), set(), {}))
    cfg = bodega.config()
    cfg["verificacion_enlaces"] = {"vacantes_por_captura": 0, "segundos_captura": 0}
    monkeypatch.setattr(bodega, "config", lambda: cfg)
    monkeypatch.setattr(supabase, "subir_catalogo", lambda rows: {"filas": len(rows), "enviadas": len(rows),
                                                               "confirmadas": [r["id"] for r in rows]})
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    archivo = trabajo / "entregadas.json"
    archivo.write_text('{"anterior":"2026-11-03"}')
    r = bodega.correr(tmp_path, modo="incremental", hoy=HOY)
    assert r["modo"] == "incremental" and r["catalogo"]["activas_elegibles"] == 1
    assert archivo.read_text() == '{"anterior":"2026-11-03"}'
    assert not (trabajo / "lote_entrega.json").exists()
    memoria = bodega._leer_json(trabajo / "catalogo_sincronizado.json.gz", {})
    assert memoria and r["catalogo"]["enviadas"] >= 1 and set(memoria) <= {v["id"] for v in bodega._leer_json(trabajo / "bodega.json.gz", [])}


def test_migracion_faltante_detiene_captura_antes_de_fuentes(monkeypatch, tmp_path):
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    def falta(): raise RuntimeError("Aplicar 002_catalogo.sql")
    monkeypatch.setattr(supabase, "exigir_catalogo", falta)
    monkeypatch.setattr(incremental, "recoger", lambda *a, **k: pytest.fail("No debe iniciar fuentes"))
    with pytest.raises(RuntimeError, match="002_catalogo"):
        bodega.correr(tmp_path, modo="incremental", hoy=HOY)


def test_registro_recupera_snapshot_del_dia_sin_descargar_historico():
    v = oferta()
    class Sesion:
        def get(self, url, **op):
            filas = [{"vacante_id": v["id"], "delivery_date": HOY}]
            if url.endswith("/ofertas"):
                filas = [{"offer_url": v["enlace"], "delivery_date": HOY}]
            if op["params"]["select"].startswith("role_id"):
                filas = [{"role_id": "ux-ui-designer", "match_grade": "exact", "selected_at": AHORA, "snapshot": v}]
            return type("R", (), {"status_code": 200, "json": lambda self: filas})()
    memoria, lote = supabase.leer_entregas(HOY, Sesion())
    assert memoria[v["id"]] == HOY and lote["elegidas"]["ux-ui-designer"][0][0]["id"] == v["id"]


def test_recuperacion_identifica_v1_del_dia_sin_snapshot_canonico(monkeypatch):
    v = oferta()
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://example.supabase.co", "sb_secret_prueba"))
    class Sesion:
        def get(self, url, **op):
            filas = [{"offer_url": v["enlace"], "delivery_date": HOY}] if url.endswith("/ofertas") else []
            return type("R", (), {"status_code": 200, "json": lambda self: filas})()
    _, lote = supabase.leer_entregas(HOY, Sesion())
    assert lote["v1_sin_registro_hoy"] == [contrato.url_limpia(v["enlace"])]


@pytest.mark.parametrize("con_lote_local", [False, True])
def test_perder_registro_y_estado_no_crea_otro_lote_ni_gasta_apify(monkeypatch, tmp_path, con_lote_local):
    import json
    v = oferta()
    monkeypatch.setenv("CATALOGO_ACTIVO", "true")
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "exigir_catalogo", lambda: None)
    monkeypatch.setattr(supabase, "leer_entregas", lambda hoy: ({v["enlace"]: HOY},
        {"fecha": HOY, "elegidas": {}, "v1_sin_registro_hoy": [contrato.url_limpia(v["enlace"])]}))
    if con_lote_local:
        trabajo = tmp_path / "trabajo"
        trabajo.mkdir()
        (trabajo / "lote_entrega.json").write_text(json.dumps({"fecha": HOY,
            "elegidas": {"ux-ui-designer": [[v, "exacto"]]}}))
    def recoger(*a, **k):
        raise RuntimeError("captura alcanzada con lote recuperable")
    monkeypatch.setattr(bodega, "recoger", recoger)
    esperado = "captura alcanzada" if con_lote_local else "sin registro de selección ni lote recuperable"
    with pytest.raises(RuntimeError, match=esperado):
        bodega.correr(tmp_path, hoy=HOY)
    assert not (tmp_path / "trabajo/entregadas.json").exists()


def test_sin_siete_dias_reales_no_se_declara_listo_para_whatsapp():
    ahora = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
    r = {"capturada_en": AHORA, "catalogo": {"filas": 1, "enviadas": 1, "pendientes": 0}, "historico_entregas": [],
         "frescura": {"observadas_2h": 1}, "entrega": {"vacantes": 1},
         "seleccion_actual": {"roles": {"qa": {"vacantes": [{"afinidad_vigente": True}]}}},
         "verificacion_enlaces": {"seleccion_del_dia": {"vacantes": 1, "estados": {"verificada": 1}}}}
    assert not preparacion.evaluar(r, ahora)["apto_para_piloto_whatsapp"]
    r["historico_entregas"] = [{"fecha": (ahora.date() - timedelta(days=i)).isoformat(), "meta_cumplida": True,
                                 "pendientes_supabase": 0, "registro_confirmado": True,
                                 "enlaces_comprobados": True} for i in range(7)]
    assert preparacion.evaluar(r, ahora)["apto_para_piloto_whatsapp"]
    r["seleccion_actual"]["roles"]["qa"]["vacantes"][0]["afinidad_vigente"] = False
    assert not preparacion.evaluar(r, ahora)["apto_para_piloto_whatsapp"]
    r["seleccion_actual"]["roles"]["qa"]["vacantes"][0]["afinidad_vigente"] = True
    r["historico_entregas"][3]["registro_confirmado"] = False
    assert not preparacion.evaluar(r, ahora)["apto_para_piloto_whatsapp"]


def test_subregiones_y_titulo_global_no_inventan_elegibilidad():
    sur = paises.elegibles("UX Designer", "Remote - South America")
    assert "CO" in sur["paises"] and "MX" not in sur["paises"] and "ES" not in sur["paises"]
    assert paises.elegibles("Global Product Manager", "Remote - United States")["paises"] == []
    assert paises.elegibles("UX Designer", "Remote - Worldwide", "Details. " * 1000 + "This role is US-only.")["paises"] == []


def test_un_dominio_parecido_no_se_convierte_en_url_o_id_linkedin():
    falsa = "https://evil-linkedin.com/jobs/view/1234567890"
    assert contrato.url_limpia(falsa) == falsa
    assert not contrato.external_id(falsa).startswith("lnkd-")
    assert contrato.portal(falsa) != "LinkedIn"
    assert not contrato.external_id("https://evil-linkedin.com/posts/ana_activity-7391234567890123456-abcd").startswith("lnkdpost-")


@pytest.fixture(autouse=True)
def reconciliacion_de_integracion_simulada(monkeypatch):
    from buscador import supabase
    monkeypatch.setattr(supabase, "reconciliar_ofertas", lambda: {"archivadas": 0, "sin_identificar": 0})


def test_revisar_estonia_del_inventario_y_conservar_historico():
    v = dict(oferta(), titulo="Product Owner", ubicacion="Tartu, Condado de Tartu, Estonia", paises=paises.datos()["codigos"], modalidad="remoto", confianza_pais="baja")
    v.pop("_lugares")  # registro guardado antes de existir las observaciones de ubicación
    original = deepcopy(v)
    retiradas = []
    salida, _, _ = bodega.limpiar([v], [], HOY, 30, set(), set(), retiradas=retiradas)
    assert not salida and retiradas[0][1:] == ("archived", "sin elegibilidad regional")
    pendientes = {}
    catalogo.sincronizar(salida, retiradas, pendientes, lambda rows: {"confirmadas": []}, lambda p: None, AHORA)
    assert pendientes[v["id"]]["status"] == "archived"
    assert pendientes[v["id"]]["datos"]["paises"] == [] and v == original
