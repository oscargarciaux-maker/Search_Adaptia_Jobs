"""No confundir un HTTP 200 con una oferta vigente y utilizable."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import socket

import pytest
import requests

from buscador import bodega, contrato, entrega, vacante, verificar_enlaces as ve

AHORA = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
URL = "https://jobs.lever.co/acme/1"
TEXTO = "We are hiring a UX Designer for our digital product, conducting user research and prototyping. " * 5


def html(extra="", titulo="UX Designer"):
    return f"<html><title>{titulo} - Acme</title><main><h1>{titulo}</h1><p>{TEXTO}</p>{extra}</main></html>"


class Respuesta:
    encoding = "utf-8"
    def __init__(self, texto="", http=200, headers=None):
        self.texto, self.status_code, self.headers = texto, http, headers or {}
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def iter_content(self, *a): yield self.texto.encode()


class Sesion:
    def __init__(self, paginas): self.paginas, self.consultas = paginas, []
    def get(self, url, **op):
        assert op["allow_redirects"] is False and op["stream"] is True
        self.consultas.append(url)
        valor = self.paginas[url]
        if isinstance(valor, Exception): raise valor
        return valor


def comprobar(paginas, url=URL, **op):
    return ve.comprobar(url, "UX Designer", sesion=Sesion(paginas), validar_url=lambda u: True, ahora=AHORA, **op)


def oferta(n=1):
    return vacante.crear("UX Designer", f"Empresa {n}", f"https://jobs.lever.co/acme/{n}", "Lever",
        ubicacion="Remote LATAM", descripcion=TEXTO, hoy="2026-11-05")


def resultado(u, titulo="UX Designer", estado="verificada", ahora=AHORA, **op):
    return {"url": u, "estado": estado, "motivo": "ficha específica accesible" if estado == "verificada" else "enlace roto",
            "destino": u, "comprobada_en": ahora.isoformat().replace("+00:00", "Z"), "saltos": 0,
            "http": 200 if estado == "verificada" else 404, "ruta": [u], "_titulo": titulo, **op}


@pytest.mark.parametrize("codigo,estado", [(404, "rechazada"), (410, "rechazada"), (402, "rechazada"),
    (403, "pendiente"), (429, "pendiente"), (500, "pendiente")])
def test_codigos_http_sin_confundir_bloqueo_con_cierre(codigo, estado):
    assert comprobar({URL: Respuesta(http=codigo)})["estado"] == estado


def test_200_exige_vacante_no_pagina_generica():
    assert comprobar({URL: Respuesta(html())})["estado"] == "verificada"
    u = "https://lemon.io/for-developers/?utm_source=portal"
    r = comprobar({u: Respuesta(html(titulo="Jobs for developers"))}, url=u)
    assert r["estado"] == "rechazada" and r["motivo"] == "página general sin vacante"
    assert comprobar({URL: Respuesta("<title>Portal del candidato</title><div id='app'></div>")})["estado"] == "pendiente"


@pytest.mark.parametrize("texto,motivo", [
    ("This job is no longer available.", "vacante cerrada"),
    ("Esta vacante ha sido cerrada.", "vacante cerrada"),
    ("Pay USD 10 to apply.", "postulación con cobro"),
    ("Suscríbete para acceder a la oferta.", "postulación con cobro"),
    ("Pague para se candidatar.", "postulación con cobro")])
def test_rechazo_con_evidencia_en_ficha(texto, motivo):
    r = comprobar({URL: Respuesta(html(texto))})
    assert r["estado"] == "rechazada" and r["motivo"] == motivo


def test_salario_formacion_paga_y_advertencia_no_son_cobro():
    t = "We offer competitive pay and paid training. We never ask you to pay to apply. No payment is required to apply."
    assert comprobar({URL: Respuesta(html(t))})["estado"] == "verificada"


@pytest.mark.parametrize("advertencia", ["Do not pay to apply.", "You should not pay to apply.",
    "You shouldn't pay to apply.", "No debes pagar para postular.", "No es necesario pagar para aplicar."])
def test_advertencias_contra_pagos_no_generan_falso_rechazo(advertencia):
    assert comprobar({URL: Respuesta(html(advertencia))})["estado"] == "verificada"


def test_expiracion_jobposting_aunque_html_responda_200():
    ld = {"@type": "JobPosting", "title": "UX Designer", "validThrough": "2026-11-04T23:00:00Z"}
    r = comprobar({URL: Respuesta(html('<script type="application/ld+json">' + json.dumps(ld) + '</script>'))})
    assert r["motivo"] == "vacante cerrada"


def test_cobro_en_datos_estructurados_y_vuelta_al_listado_general():
    ld = {"@type": "JobPosting", "title": "UX Designer", "description": "<p>Pay a fee to apply.</p>"}
    r = comprobar({URL: Respuesta('<script type="application/ld+json">' + json.dumps(ld) + '</script>')})
    assert r["motivo"] == "postulación con cobro"
    fin = "https://job-boards.eu.greenhouse.io/acme?error=true"
    r = comprobar({URL: Respuesta(http=302, headers={"Location": fin}), fin: Respuesta('<h1>Careers at Acme</h1>')})
    assert r["motivo"] == "página general sin vacante"


def test_redireccion_sin_ciclo_se_comprueba_en_destino():
    fin = "https://jobs.ashbyhq.com/acme/1"
    r = comprobar({URL: Respuesta(http=302, headers={"Location": fin}), fin: Respuesta(html())})
    assert r["estado"] == "verificada" and r["destino"] == fin and r["saltos"] == 1


def test_ciclos_http_y_meta_refresh():
    fin = "https://jobs.ashbyhq.com/acme/1"
    r = comprobar({URL: Respuesta(http=302, headers={"Location": fin}),
        fin: Respuesta('<meta http-equiv="refresh" content="0;url=' + URL + '">')})
    assert r["motivo"] == "ciclo de redirecciones"


def test_redireccion_a_agregador_o_red_privada_no_se_consulta():
    for destino, motivo in [("https://www.flexjobs.com/jobs/1", "destino agregador o de pago"),
                            ("http://127.0.0.1/admin", "destino no público")]:
        sesion = Sesion({URL: Respuesta(http=302, headers={"Location": destino})})
        r = ve.comprobar(URL, "UX Designer", sesion=sesion, validar_url=lambda u: "127.0.0.1" not in u)
        assert r["motivo"] == motivo and sesion.consultas == [URL]


def test_paso_visible_de_aplicar_tambien_se_revisa():
    fin = "https://careers.acme.com/apply/1"
    r = comprobar({URL: Respuesta(html(f'<a href="{fin}">Apply now</a>')),
        fin: Respuesta(html("Subscribe to apply."))})
    assert r["motivo"] == "postulación con cobro"
    r = comprobar({URL: Respuesta(html(f'<a href="{fin}">Apply now</a>')),
        fin: Respuesta("<title>Sign in</title><h1>Sign in</h1>")})
    assert r["estado"] == "pendiente" and r["motivo"] == "requiere iniciar sesión"


def test_timeout_y_exceso_bytes_no_aprueban_ni_declaran_cierre():
    assert comprobar({URL: requests.Timeout()})["estado"] == "pendiente"
    assert comprobar({URL: Respuesta(html())}, max_bytes=20)["estado"] == "pendiente"


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"])
def test_validacion_dns_rechaza_redes_locales(ip):
    assert not ve.publica(URL, resolver=lambda *a, **k: [(0, 0, 0, "", (ip, 443))])


def test_dns_temporalmente_no_disponible_queda_pendiente():
    def resolver(*a, **k): raise socket.gaierror("DNS temporal")
    r = ve.comprobar(URL, "UX Designer", sesion=Sesion({}), validar_url=lambda u: ve.publica(u, resolver))
    assert r["estado"] == "pendiente"


def test_un_enlace_malo_no_contamina_el_bueno_ni_sale_en_filas():
    v = oferta()
    v["enlace_directo"] = "https://jobs.ashbyhq.com/acme/1"
    cache = {v["enlace"]: resultado(v["enlace"], estado="rechazada"),
             v["enlace_directo"]: resultado(v["enlace_directo"])}
    ve.anotar(v, cache, AHORA)
    assert v["verificacion"]["estado"] == "verificada"
    assert [f["offer_url"] for f in contrato.filas(v)] == [v["enlace_directo"]]


def test_cache_no_renueva_hora_y_caduca_y_compara_titulo():
    v = oferta()
    cache = {v["enlace"]: resultado(v["enlace"])}
    ve.anotar(v, cache, AHORA + timedelta(hours=5))
    assert v["verificacion"]["comprobada_en"] == cache[v["enlace"]]["comprobada_en"]
    ve.anotar(v, cache, AHORA + timedelta(hours=6))
    assert v["verificacion"]["estado"] == "pendiente"
    assert not ve.vigente(cache[v["enlace"]], "QA Engineer", AHORA)


def test_presupuesto_no_aprueba_las_ofertas_no_revisadas():
    vs = [oferta(i) for i in range(4)]
    cache = {}
    ve.auditar(vs, cache, maximo=2, ahora=AHORA,
               comprobar_url=lambda u, t, **op: resultado(u, ahora=op["ahora"]))
    assert ve.resumen(vs)["estados"] == {"verificada": 2, "pendiente": 2}
    def prohibido(*a, **k): raise AssertionError("No renovar una comprobación vigente")
    assert ve.auditar(vs[:2], cache, ahora=AHORA, comprobar_url=prohibido) == 0


def test_candidatas_sin_verificar_no_se_entregan_y_se_busca_reemplazo(monkeypatch):
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=2)
    monkeypatch.setattr(entrega, "config", lambda: cfg)
    vs = [oferta(i) for i in range(1, 4)]
    def revisar(u, titulo, **op):
        return resultado(u, ahora=op["ahora"], estado="rechazada" if u.endswith("/1") else "verificada")
    monkeypatch.setattr(ve, "comprobar", revisar)
    ve.preparar(vs, {}, "2026-11-05", {}, cfg={"vacantes_por_corrida": 3})
    seleccion, _ = entrega.elegir(vs, {}, "2026-11-05")
    assert [v["id"] for v, _ in seleccion["ux-ui-designer"]] == [vs[1]["id"], vs[2]["id"]]


def test_revision_de_lote_historico_no_lo_reescribe(monkeypatch):
    v = oferta()
    lote = {"fecha": "2026-11-05", "elegidas": {"ux-ui-designer": [[dict(v), "exacto"]]}}
    original = deepcopy(lote)
    monkeypatch.setattr(ve, "comprobar", lambda u, t, **op: resultado(u, estado="rechazada", ahora=op["ahora"]))
    r = ve.preparar([v], {}, "2026-11-05", {}, lote=lote, incremental=True)
    assert lote == original and r["seleccion_del_dia"]["estados"] == {"rechazada": 1}


def test_produccion_audita_antes_de_nueva_seleccion(monkeypatch, tmp_path):
    from buscador import supabase
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "subir", lambda filas: {"filas": len(filas), "enviadas": 0, "confirmadas": []})
    monkeypatch.setattr(ve, "comprobar", lambda *a, **k: None)
    monkeypatch.setattr(bodega, "recoger", lambda *a, **k: ([dict(titulo="UX Designer", empresa="A",
        enlace=URL, fuente="Lever", ubicacion="Remote LATAM", descripcion=TEXTO)], set(), set(), {}))
    cfg = bodega.config()
    cfg["refuerzo"]["rondas"] = 0
    monkeypatch.setattr(bodega, "config", lambda: cfg)
    monkeypatch.delenv("CATALOGO_ACTIVO", raising=False)
    r = bodega.correr(tmp_path, hoy="2026-11-05")
    assert r["entrega"]["vacantes"] == 0 and not r["entrega"]["meta_cumplida"]
    assert r["verificacion_enlaces"]["estados"] == {"pendiente": 1}


def test_validacion_no_aprueba_historial_si_sus_enlaces_actuales_fallaron():
    from buscador import validacion
    r = {"vacantes_en_bodega": 120, "entrega": {"meta_cumplida": True,
         "supabase": {"filas": 120, "enviadas": 120}},
         "verificacion_enlaces": {"seleccion_del_dia": {"vacantes": 120,
                                  "estados": {"verificada": 108, "pendiente": 5, "rechazada": 7}}}}
    assert any("selección histórica" in error for error in validacion.errores(r))


def test_cierre_confirmado_se_guarda_sin_borrar_snapshot_historico(monkeypatch, tmp_path):
    from buscador import incremental, supabase
    v = oferta()
    lote = {"fecha": "2026-11-05", "elegidas": {"ux-ui-designer": [[v, "exacto"]]}}
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    archivo = trabajo / "lote_entrega.json"
    original = json.dumps(lote)
    archivo.write_text(original)
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: None)
    monkeypatch.setattr(supabase, "exigir_catalogo", lambda: None)
    monkeypatch.setattr(incremental, "recoger", lambda *a: ([dict(titulo=v["titulo"], empresa=v["empresa"],
        enlace=v["enlace"], fuente="Lever", ubicacion="Remote LATAM", descripcion=TEXTO)], set(), set(), {}))
    monkeypatch.setattr(ve, "comprobar", lambda u, t, **op:
        resultado(u, estado="rechazada", ahora=op["ahora"], motivo="vacante cerrada"))
    filas = []
    def subir(rows):
        filas.extend(rows)
        return {"filas": len(rows), "enviadas": len(rows), "confirmadas": [r["id"] for r in rows]}
    monkeypatch.setattr(supabase, "subir_catalogo", subir)
    r = bodega.correr(tmp_path, modo="incremental", hoy="2026-11-05")
    assert r["vacantes_en_bodega"] == 0 and filas[0]["status"] == "closed"
    assert archivo.read_text() == original
    assert r["verificacion_enlaces"]["seleccion_del_dia"]["estados"] == {"rechazada": 1}
