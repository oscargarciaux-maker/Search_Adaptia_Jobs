"""Diagnósticos concretos sin credenciales y consulta PostgreSQL estrictamente de lectura."""
from contextlib import nullcontext
from pathlib import Path

import psycopg
import pytest

from buscador import diagnostico_conexion, migraciones
from buscador import tls_supabase


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


def test_autoridades_incluyen_raiz_supabase_y_se_retiraran():
    with tls_supabase.autoridades() as ruta:
        datos = Path(ruta).read_bytes()
        assert tls_supabase.CA.read_bytes() in datos
        assert datos.count(b"-----BEGIN CERTIFICATE-----") > 1
    assert not Path(ruta).exists()


def test_raiz_alterada_no_se_acepta(monkeypatch, tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    # Alterar una firma conserva el formato X.509, pero debe invalidar la huella fijada.
    original = x509.load_pem_x509_certificate(tls_supabase.CA.read_bytes())
    der = bytearray(original.public_bytes(serialization.Encoding.DER))
    der[-1] ^= 1
    cert = x509.load_der_x509_certificate(bytes(der))
    distinta = tmp_path / "distinta.crt"
    distinta.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    monkeypatch.setattr(tls_supabase, "CA", distinta)
    with pytest.raises(RuntimeError, match="DB_TLS_CA"):
        with tls_supabase.autoridades(): pytest.fail("No aceptar otra raíz")


def test_raiz_disponible_durante_conexion_y_tls_sigue_verificado(monkeypatch):
    from psycopg.conninfo import make_conninfo
    vistos = []
    def conectar(**op):
        assert op["sslmode"] == "verify-full"
        assert tls_supabase.CA.read_bytes() in Path(op["sslrootcert"]).read_bytes()
        vistos.append(op["sslrootcert"])
        raise psycopg.OperationalError("certificate verify failed: dato privado")
    monkeypatch.setattr(psycopg, "connect", conectar)
    dsn = make_conninfo(host="aws-0.pooler.supabase.com", user="postgres.proyecto", password="ensayo")
    with pytest.raises(RuntimeError, match="DB_TLS"):
        migraciones.conexion(dsn, "https://proyecto.supabase.co")
    assert vistos and not Path(vistos[0]).exists()
