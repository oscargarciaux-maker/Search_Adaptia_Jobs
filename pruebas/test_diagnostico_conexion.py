"""Diagnósticos concretos sin credenciales y consulta PostgreSQL estrictamente de lectura."""
from contextlib import nullcontext

import psycopg
import pytest

from buscador import diagnostico_conexion, migraciones


@pytest.mark.parametrize("error,directa,codigo", [
    (psycopg.errors.InvalidPassword("dato privado"), False, "DB_AUTENTICACION"),
    (psycopg.OperationalError("password authentication failed: dato privado"), False, "DB_AUTENTICACION"),
    (psycopg.OperationalError("Tenant or user not found: dato privado"), False, "DB_USUARIO"),
    (psycopg.OperationalError("certificate verify failed: dato privado"), False, "DB_TLS"),
    (psycopg.OperationalError("Network is unreachable: dato privado"), True, "DB_IPV6"),
    (psycopg.OperationalError("Network is unreachable: dato privado"), False, "DB_RED"),
    (psycopg.OperationalError("could not translate host name: dato privado"), False, "DB_DNS"),
    (psycopg.OperationalError("connection timeout expired: dato privado"), False, "DB_TIEMPO"),
    (psycopg.OperationalError("connection refused: dato privado"), False, "DB_RECHAZADA"),
    (psycopg.errors.InvalidCatalogName("dato privado"), False, "DB_BASE"),
    (psycopg.OperationalError("dato privado"), False, "DB_CONEXION"),
])
def test_clasificar_sin_exponer_error_original(error, directa, codigo):
    mensaje = migraciones.error_conexion(error, directa)
    assert mensaje.startswith("[" + codigo + "]")
    assert "dato privado" not in mensaje


@pytest.mark.parametrize("dsn,codigo", [
    ("", "DB_SECRETO"),
    ("no es una URI", "DB_URI"),
    ("host=db.proyecto.supabase.co", "DB_PASSWORD"),
    ("host=db.proyecto.supabase.co password=[YOUR-PASSWORD]", "DB_PASSWORD"),
    ("host=db.otro.supabase.co password=ensayo", "DB_PROYECTO"),
    ("host=db.proyecto.supabase.co password=ensayo port=6543", "DB_PUERTO"),
    ("host=db.proyecto.supabase.co password=ensayo hostaddr=127.0.0.1", "DB_OPCIONES"),
])
def test_validacion_local_identifica_campo_sin_contactar(monkeypatch, dsn, codigo):
    monkeypatch.setattr(psycopg, "connect", lambda **k: pytest.fail("No conectar si la configuración es inválida"))
    with pytest.raises(RuntimeError, match="\\[" + codigo + "\\]") as e:
        migraciones.conexion(dsn, "https://proyecto.supabase.co")
    assert "password=ensayo" not in str(e.value)


def test_probe_solo_lectura_y_consultas_permitidas(monkeypatch):
    consultas = []
    class Conn:
        def transaction(self): return nullcontext()
        def execute(self, q):
            consultas.append(q)
            return type("Fila", (), {"fetchone": lambda self: (1,) if q == "select 1" else ("on",)})()
    monkeypatch.setattr(migraciones, "conexion", lambda *a: nullcontext(Conn()))
    assert diagnostico_conexion.comprobar().startswith("[DB_OK]")
    assert consultas == ["set transaction read only", "select 1", "select current_setting('transaction_read_only')"]


def test_probe_rechaza_transaccion_sin_lectura_confirmada(monkeypatch):
    class Conn:
        def transaction(self): return nullcontext()
        def execute(self, q):
            return type("Fila", (), {"fetchone": lambda self: (1,) if q == "select 1" else ("off",)})()
    monkeypatch.setattr(migraciones, "conexion", lambda *a: nullcontext(Conn()))
    with pytest.raises(RuntimeError, match="DB_CONSULTA"): diagnostico_conexion.comprobar()


def test_error_inesperado_del_probe_no_se_imprime(monkeypatch, capsys):
    def fallar(): raise ValueError("contraseña privada")
    monkeypatch.setattr(diagnostico_conexion, "comprobar", fallar)
    with pytest.raises(SystemExit): diagnostico_conexion.main()
    salida = capsys.readouterr().out
    assert "DB_DIAGNOSTICO" in salida and "contraseña privada" not in salida
