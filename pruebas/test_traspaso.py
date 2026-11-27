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
    from buscador import arranque
    import json
    if dia is not None:
        (tmp_path / "metricas_entrega.json").write_text(json.dumps({"2026-11-10": dia, "2026-11-09": {"meta_cumplida": True}}),
                                                       encoding="utf-8")
    assert arranque.falta_completar(arranque.leer_dia(tmp_path, "2026-11-10")) is esperado
    assert arranque.falta_completar(arranque.leer_dia(tmp_path / "no-existe", "2026-11-10")) is True


class _Conexion:
    def __init__(self, nombre, abiertas):
        self.nombre = nombre
        abiertas.append(nombre)
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _trasladar_simulado(monkeypatch, pasos, guardar_falla=False):
    from contextlib import nullcontext
    monkeypatch.setattr(traspaso, "exigir_vigente", lambda c: None)
    monkeypatch.setattr(traspaso, "exigir_destino_libre", lambda c: None)
    monkeypatch.setattr(traspaso.migraciones, "bloqueo", lambda c: nullcontext())
    monkeypatch.setattr(traspaso.respaldo, "crear", lambda conn, trabajo, copia, llave: pasos.append("crear"))
    monkeypatch.setattr(traspaso, "inventario", lambda c: {"tablas": {}, "secuencias": {}})
    monkeypatch.setattr(traspaso, "restaurar", lambda c, copia, llave: pasos.append("restaurar") or {"tablas": {}, "secuencias": {}})
    monkeypatch.setattr(traspaso, "marcar", lambda c, ref: pasos.append("marcar"))
    def guardar(copia):
        pasos.append("guardar")
        if guardar_falla:
            raise RuntimeError("Storage caído (ficticio)")
    return guardar


def test_la_copia_se_guarda_antes_de_restaurar_y_de_marcar(monkeypatch, tmp_path):
    pasos = []
    guardar = _trasladar_simulado(monkeypatch, pasos)
    traspaso.trasladar(object(), object(), tmp_path, "llave", tmp_path / "c.enc", "https://destino", guardar=guardar)
    assert pasos == ["crear", "guardar", "restaurar", "marcar"]


def test_si_no_se_puede_guardar_la_copia_no_se_toca_el_destino_ni_se_marca(monkeypatch, tmp_path):
    pasos = []
    guardar = _trasladar_simulado(monkeypatch, pasos, guardar_falla=True)
    with pytest.raises(RuntimeError, match="Storage caído"):
        traspaso.trasladar(object(), object(), tmp_path, "llave", tmp_path / "c.enc", "https://destino", guardar=guardar)
    assert pasos == ["crear", "guardar"]


def _entorno_traspaso(monkeypatch, tmp_path, abiertas):
    monkeypatch.setenv("SUPABASE_BACKUP_KEY", "A" * 43)
    monkeypatch.setenv("SUPABASE_URL", "https://origen.supabase.co")
    monkeypatch.setenv("SUPABASE_URL_DESTINO", "https://destino.supabase.co")
    monkeypatch.setattr(traspaso.migraciones, "conexion", lambda dsn, url: _Conexion(url, abiertas))
    monkeypatch.setattr("sys.argv", ["traspaso", "--fase", "traspaso", "--salida", str(tmp_path / "salida"),
                                     "--privado", str(tmp_path / "privado")])


def test_sin_la_clave_del_destino_el_traspaso_no_empieza(monkeypatch, tmp_path):
    abiertas = []
    _entorno_traspaso(monkeypatch, tmp_path, abiertas)
    monkeypatch.delenv("SUPABASE_SECRET_KEY_DESTINO", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_SECRET_KEY_DESTINO"):
        traspaso.main()
    assert abiertas == ["https://origen.supabase.co"]  # nunca se abrió el destino


def test_el_traspaso_guarda_la_copia_en_el_storage_del_destino(monkeypatch, tmp_path, capsys):
    from pruebas.test_almacen_respaldos import StorageFalso, _cifrado_ficticio
    abiertas, storage, usados = [], StorageFalso(), []
    _entorno_traspaso(monkeypatch, tmp_path, abiertas)
    monkeypatch.setenv("SUPABASE_SECRET_KEY_DESTINO", "sb_secret_ficticia")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    original = traspaso.almacen_respaldos.Almacen
    def almacen(url, clave):
        usados.append(url)
        return original(url, clave, sesion=storage, pausa=0)
    monkeypatch.setattr(traspaso.almacen_respaldos, "Almacen", almacen)
    def trasladar(origen, destino, trabajo, llave, copia, ref, ensayo=False, guardar=None):
        copia.parent.mkdir(parents=True)
        _cifrado_ficticio(copia, filas=5)
        guardar(copia)
        return {"tablas": {"ofertas": 5}, "secuencias": {}}
    monkeypatch.setattr(traspaso, "trasladar", trasladar)
    traspaso.main()
    assert usados == ["https://destino.supabase.co"]
    assert [n.split("/")[0] for n in storage.objetos] and all(n.startswith("traspaso/") for n in storage.objetos)
    assert any(n.endswith("/manifiesto.json") for n in storage.objetos)
    salida = capsys.readouterr().out
    assert "bucket privado `respaldos` del DESTINO" in salida and "sb_secret" not in salida
