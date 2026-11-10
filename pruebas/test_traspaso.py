"""Protecciones del traspaso que no requieren PostgreSQL (el recorrido real está en probar_traspaso)."""
from types import SimpleNamespace

import pytest

from buscador import preparar, traspaso


def test_comparar_detecta_diferencias_sin_mostrar_datos():
    base = {"tablas": {"ofertas": 3, "catalogo_vacantes": 10}, "secuencias": {"ofertas_id_seq": [3, True]}}
    traspaso.comparar(base, base)
    with pytest.raises(RuntimeError, match="ofertas: origen 3, destino 2"):
        traspaso.comparar(base, {**base, "tablas": {"ofertas": 2, "catalogo_vacantes": 10}})
    with pytest.raises(RuntimeError, match="secuencia ofertas_id_seq"):
        traspaso.comparar(base, {**base, "secuencias": {"ofertas_id_seq": [2, True]}})


def _respuesta(datos, estado=200):
    return SimpleNamespace(status_code=estado, json=lambda: datos)


def test_captura_se_detiene_si_la_base_fue_trasladada(monkeypatch):
    monkeypatch.setattr(preparar.supabase, "credenciales", lambda: ("https://origen.supabase.co", "clave-ficticia"))
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    sesion = SimpleNamespace(get=lambda *a, **k: _respuesta([{"identificador": "trasladada"}]))
    assert preparar.trasladada_rest(sesion)
    monkeypatch.setattr(preparar, "trasladada_rest", lambda: True)
    args = SimpleNamespace(prueba=False, modo="incremental", fase="aplicar", manual=False, instancia_nueva=False)
    with pytest.raises(RuntimeError, match="se trasladó"):
        preparar.correr(args)


@pytest.mark.parametrize("respuesta", [_respuesta([]), _respuesta({"code": "PGRST205"}, 404)])
def test_base_sin_marca_o_sin_tabla_no_se_considera_trasladada(monkeypatch, respuesta):
    monkeypatch.setattr(preparar.supabase, "credenciales", lambda: ("https://origen.supabase.co", "clave-ficticia"))
    assert not preparar.trasladada_rest(SimpleNamespace(get=lambda *a, **k: respuesta))


def test_traspaso_rechaza_destino_igual_al_origen(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_BACKUP_KEY", "A" * 43)
    monkeypatch.setenv("SUPABASE_URL", "https://mismo.supabase.co")
    monkeypatch.setenv("SUPABASE_URL_DESTINO", "https://mismo.supabase.co/")
    class Conexion:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(traspaso.migraciones, "conexion", lambda dsn, url: Conexion())
    monkeypatch.setattr("sys.argv", ["traspaso", "--fase", "traspaso", "--salida", str(tmp_path)])
    with pytest.raises(RuntimeError, match="mismo proyecto"):
        traspaso.main()


@pytest.mark.parametrize("dia,esperado", [
    (None, True),  # la nocturna no corrió: la mañana hace el día completo
    ({"meta_cumplida": False, "registro_confirmado": True, "pendientes_supabase": 0}, True),
    ({"meta_cumplida": True, "registro_confirmado": False, "pendientes_supabase": 0}, True),
    ({"meta_cumplida": True, "registro_confirmado": True, "pendientes_supabase": 3}, True),
    ({"meta_cumplida": True, "registro_confirmado": True, "pendientes_supabase": 0}, False),
])
def test_pasada_de_la_manana_solo_si_falta(tmp_path, dia, esperado):
    from buscador import validacion
    import json
    if dia is not None:
        (tmp_path / "metricas_entrega.json").write_text(json.dumps({"2026-11-10": dia, "2026-11-09": {"meta_cumplida": True}}))
    assert validacion.hace_falta_completar(tmp_path, "2026-11-10") is esperado
    assert validacion.hace_falta_completar(tmp_path / "no-existe", "2026-11-10") is True
