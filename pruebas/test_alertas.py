"""Alertas por correo (contrato v10): cuándo se envían, a quién y sin datos de clientes."""
import json

import pytest
from fastapi.testclient import TestClient

from buscador import alertas
from panel.api import crear_app
from panel.repositorio import RepositorioDemo

SALUD_OK = {"fecha": "2026-11-12", "entrega": {"vacantes": 120, "meta_cumplida": True, "supabase": {"pendientes": 0},
            "registro_seleccion": {"pendientes": 0}, "roles": {"cargo:a": {"nombre": "QA", "entregadas": 20, "faltan": 0}}}}
SALUD_CORTA = {"fecha": "2026-11-12", "entrega": {"vacantes": 35, "meta_cumplida": False, "supabase": {"pendientes": 0},
               "registro_seleccion": {"pendientes": 0},
               "roles": {"cargo:a": {"nombre": "AI Engineer", "entregadas": 2, "faltan": 18, "ampliadas": {"sin_dato": 2}}},
               "embudo": {"cargo:a": {"principal_perdida": "sin descripción completa (no se sabe el idioma)"}}}}


@pytest.mark.parametrize("modo,resultado,salud,panel,esperado", [
    ("diario", "success", SALUD_OK, None, "exito"),
    ("diario", "failure", SALUD_CORTA, None, None),            # la noche con faltantes espera a la pasada de la mañana
    ("manana", "failure", SALUD_CORTA, None, "pocas_vacantes"),
    ("manana", "success", SALUD_OK, {"resumen": {"perfiles_bajo_minimo": 2}}, "pocas_vacantes"),
    ("diario", "failure", None, None, "fallo"),                 # no llegó a producir resultados
    ("diario", "failure", {"entrega": dict(SALUD_OK["entrega"], supabase={"pendientes": 3})}, None, "fallo"),
])
def test_decidir(modo, resultado, salud, panel, esperado):
    assert alertas.decidir(modo, resultado, salud, panel) == esperado


def test_capturas_horarias_solo_avisan_al_tercer_fallo_seguido():
    assert [alertas.decidir("horaria", "failure", None, None, n) for n in (1, 2, 3, 4)] == [None, None, "fallo", None]
    assert alertas.decidir("horaria", "success", None, None, 0) is None


def test_contenido_por_cargo_sin_datos_de_clientes():
    asunto, cuerpo, texto = alertas.contenido("pocas_vacantes", "manana", SALUD_CORTA,
                                              {"resumen": {"meta": 120, "perfiles_bajo_minimo": 1}},
                                              "https://github.com/x/y/actions/runs/1", "https://panel.example.org")
    assert "35 de 120" in asunto and "AI Engineer: 2 (faltan 18), 2 por ampliación" in texto
    assert "Mayor pérdida: sin descripción completa" in texto and "1 perfil(es)" in texto
    assert "panel.example.org" in cuerpo and "<script" not in cuerpo


class Ajustes:
    disponible = True

    def __init__(self, alertas_cfg, estado=None):
        self.datos = {"alertas": alertas_cfg, "alertas_estado": estado or {}}

    def leer(self, clave, defecto=None):
        return self.datos.get(clave, defecto)

    def guardar(self, clave, valor):
        self.datos[clave] = valor
        return True

    def ejecucion_panel(self, fecha):
        return None


class Resend:
    def __init__(self):
        self.enviados = []

    def post(self, url, timeout, headers, json):
        self.enviados.append(json)
        return type("R", (), {"status_code": 200})()


def _salida(tmp_path, salud):
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos/salud.json").write_text(json.dumps(salud))
    return tmp_path


def test_correr_envia_a_los_destinatarios_y_respeta_tipos(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RESEND_API_KEY", "re_ficticia")
    monkeypatch.setenv("ALERTAS_REMITENTE", "Adaptia <alertas@example.org>")
    salida, resend = _salida(tmp_path, SALUD_OK), Resend()
    r = alertas.correr("diario", "success", salida, Ajustes({"destinatarios": ["op@example.org"]}), resend)
    assert "enviada a 1" in r and resend.enviados[0]["to"] == ["op@example.org"] and "op@example.org" not in r
    r = alertas.correr("diario", "success", salida, Ajustes({"destinatarios": ["op@example.org"], "tipos": ["fallo"]}), resend)
    assert "desactivada" in r and len(resend.enviados) == 1


def test_sin_clave_o_sin_destinatario_no_envia(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    salida, resend = _salida(tmp_path, SALUD_OK), Resend()
    assert "no enviada" in alertas.correr("diario", "success", salida, Ajustes({"destinatarios": ["op@example.org"]}), resend)
    assert "sin destinatario" in alertas.correr("diario", "success", salida, Ajustes({}), resend)
    assert not resend.enviados


def test_contador_horario_se_guarda_y_se_reinicia(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_ficticia")
    monkeypatch.setenv("ALERTAS_REMITENTE", "alertas@example.org")
    aj, resend = Ajustes({"destinatarios": ["op@example.org"]}), Resend()
    for _ in range(3):
        alertas.correr("horaria", "failure", tmp_path, aj, resend)
    assert aj.datos["alertas_estado"]["fallos_horarios_seguidos"] == 3 and len(resend.enviados) == 1
    alertas.correr("horaria", "success", tmp_path, aj, resend)
    assert aj.datos["alertas_estado"]["fallos_horarios_seguidos"] == 0


@pytest.mark.parametrize("malo", ["sin-arroba", "a@b", "x" * 120 + "@example.org", "a b@example.org"])
def test_correos_invalidos_se_rechazan(malo):
    with pytest.raises(ValueError):
        alertas.configuracion_valida({"destinatarios": [malo]})


def test_api_de_ajustes_en_demostracion(tmp_path):
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    origen = {"origin": "http://testserver"}
    assert api.get("/api/ajustes/alertas").json()["destinatarios"] == []
    assert api.post("/api/alertas/prueba", headers=origen).status_code == 422
    r = api.put("/api/ajustes/alertas", json={"destinatarios": [" op@example.org ", "op@example.org"], "tipos": ["fallo"]},
                headers=origen)
    assert r.status_code == 200 and r.json() == {"destinatarios": ["op@example.org"], "tipos": ["fallo"]}
    assert api.put("/api/ajustes/alertas", json={"destinatarios": ["no-es-correo"]}, headers=origen).status_code == 422
    assert api.post("/api/alertas/prueba", headers=origen).json()["enviado"] is False
