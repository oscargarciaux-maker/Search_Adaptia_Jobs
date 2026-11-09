"""Un fallo real debe identificarse sin divulgar el mensaje privado del servidor."""
from types import SimpleNamespace

import pytest

from buscador import supabase


@pytest.mark.parametrize("codigo,clase", [("57014","tiempo_consulta"),("42501","permisos"),("PGRST202","funcion_no_disponible")])
def test_error_rpc_se_clasifica_sin_exponer_detalles(monkeypatch,codigo,clase):
    monkeypatch.setattr(supabase,"credenciales",lambda: ("https://prueba.supabase.co","credencial-ficticia"))
    sesion=SimpleNamespace(post=lambda *a,**kw: SimpleNamespace(status_code=500,json=lambda:
        {"code":codigo,"message":"detalle privado de la base que no debe publicarse"}))
    resultado=supabase.reconciliar_ofertas(sesion, pausa=0)
    assert codigo in resultado["errores"][0] and clase in resultado["errores"][0]
    assert "detalle privado" not in str(resultado)


def _sesion(respuestas, llamadas):
    def post(*a, **kw):
        llamadas.append(1)
        codigo = respuestas[min(len(llamadas), len(respuestas)) - 1]
        if codigo is None:
            return SimpleNamespace(status_code=200, json=lambda: {"archivadas": 0, "filas_unicas": 3, "sin_identificar": 0})
        return SimpleNamespace(status_code=500, json=lambda: {"code": codigo, "message": "detalle privado"})
    return SimpleNamespace(post=post)


def test_tiempo_agotado_se_reintenta_una_vez_y_queda_registrado(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    r = supabase.reconciliar_ofertas(_sesion(["57014", None], llamadas), pausa=0)
    assert len(llamadas) == 2 and not r.get("errores") and r["reintento_por_tiempo"] and r["filas_unicas"] == 3


def test_segundo_tiempo_agotado_sigue_fallando_y_no_se_insiste_mas(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    r = supabase.reconciliar_ofertas(_sesion(["57014", "57014"], llamadas), pausa=0)
    assert len(llamadas) == 2 and len(r["errores"]) == 2 and r["reintento_por_tiempo"]
    assert all("tiempo_consulta" in e for e in r["errores"])


@pytest.mark.parametrize("codigo", ["42501", "PGRST202", "P0001"])
def test_otros_errores_no_se_reintentan(monkeypatch, codigo):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    r = supabase.reconciliar_ofertas(_sesion([codigo, None], llamadas), pausa=0)
    assert len(llamadas) == 1 and r["errores"] and "reintento_por_tiempo" not in r
