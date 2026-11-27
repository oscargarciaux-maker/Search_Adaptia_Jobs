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
    # Primer lote cortado y repetido una vez; el lote de ofertas pasa a la primera.
    assert len(llamadas) == 3 and not r.get("errores") and r["reintento_por_tiempo"] and r["filas_unicas"] == 3


def test_segundo_tiempo_agotado_sigue_fallando_y_no_se_insiste_mas(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    r = supabase.reconciliar_ofertas(_sesion(["57014", "57014"], llamadas), pausa=0)
    assert len(llamadas) == 2 and len(r["errores"]) == 2 and r["reintento_por_tiempo"]
    assert all("tiempo_consulta" in e for e in r["errores"])


@pytest.mark.parametrize("codigo", ["42501", "P0001"])
def test_otros_errores_no_se_reintentan(monkeypatch, codigo):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    r = supabase.reconciliar_ofertas(_sesion([codigo, None], llamadas), pausa=0)
    assert len(llamadas) == 1 and r["errores"] and "reintento_por_tiempo" not in r


def _sesion_lotes(paginas, llamadas):
    """Supabase ficticio con SQL 021: cada función devuelve sus páginas en orden."""
    def post(url, json=None, **kw):
        funcion = url.rsplit("/", 1)[1]
        llamadas.append((funcion, json))
        datos = paginas[funcion].pop(0)
        return SimpleNamespace(status_code=200 if "code" not in datos else 404, json=lambda: datos)
    return SimpleNamespace(post=post)


def test_reconciliacion_recorre_todos_los_lotes_y_suma_lo_archivado(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    paginas = {"reconciliar_referencias_lote": [{"revisadas": 5000, "siguiente": "ff00"}, {"revisadas": 7, "siguiente": None}],
               "reconciliar_ofertas_lote": [{"archivadas": 2, "siguiente": 500, "filas_unicas": 9, "sin_identificar": 1},
                                            {"archivadas": 1, "siguiente": None, "filas_unicas": 8, "sin_identificar": 1}]}
    r = supabase.reconciliar_ofertas(_sesion_lotes(paginas, llamadas), pausa=0)
    assert r == {"archivadas": 3, "filas_unicas": 8, "sin_identificar": 1, "lotes": 4}
    assert [c[1]["desde"] for c in llamadas] == ["", "ff00", 0, 500]
    assert all(c[1]["limite"] <= 5000 for c in llamadas)


def test_sin_sql_021_usa_la_funcion_de_una_llamada(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://prueba.supabase.co", "credencial-ficticia"))
    llamadas = []
    paginas = {"reconciliar_referencias_lote": [{"code": "PGRST202", "message": "no existe"}],
               "reconciliar_ofertas": [{"archivadas": 0, "filas_unicas": 3, "sin_identificar": 0}]}
    r = supabase.reconciliar_ofertas(_sesion_lotes(paginas, llamadas), pausa=0)
    assert [c[0] for c in llamadas] == ["reconciliar_referencias_lote", "reconciliar_ofertas"]
    assert r == {"archivadas": 0, "filas_unicas": 3, "sin_identificar": 0}
