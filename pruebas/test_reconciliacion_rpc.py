"""Un fallo real debe identificarse sin divulgar el mensaje privado del servidor."""
from types import SimpleNamespace

import pytest

from buscador import supabase


@pytest.mark.parametrize("codigo,clase", [("57014","tiempo_consulta"),("42501","permisos"),("PGRST202","funcion_no_disponible")])
def test_error_rpc_se_clasifica_sin_exponer_detalles(monkeypatch,codigo,clase):
    monkeypatch.setattr(supabase,"credenciales",lambda: ("https://prueba.supabase.co","credencial-ficticia"))
    sesion=SimpleNamespace(post=lambda *a,**kw: SimpleNamespace(status_code=500,json=lambda:
        {"code":codigo,"message":"detalle privado de la base que no debe publicarse"}))
    resultado=supabase.reconciliar_ofertas(sesion)
    assert codigo in resultado["errores"][0] and clase in resultado["errores"][0]
    assert "detalle privado" not in str(resultado)
