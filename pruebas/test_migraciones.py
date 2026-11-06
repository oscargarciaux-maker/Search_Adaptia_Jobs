"""Límites del instalador; las transacciones se comprueban además en PostgreSQL real aislado."""
from argparse import Namespace
import json
from types import SimpleNamespace

import pytest
import requests
from psycopg.conninfo import make_conninfo

from buscador import migraciones, preparar, respaldo, supabase


@pytest.fixture(autouse=True)
def sin_archivos_reales_de_actions(monkeypatch):
    for k in ("GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ACTIONS", "GITHUB_REF"):
        monkeypatch.delenv(k, raising=False)


def test_migraciones_en_orden_y_hash_del_sql_original():
    versiones = migraciones.descubrir()
    assert [m.version for m in versiones] == ["001", "002", "003", "004", "005", "006", "007"]
    assert all(len(m.digest) == 64 for m in versiones)
    assert "begin;\n" not in versiones[1].cuerpo.lower()
    assert "begin\n" in versiones[1].cuerpo.lower()  # conserva el cuerpo PL/pgSQL


def test_transaccion_externa_se_retira_sin_tocar_funciones():
    texto = "-- explicación\nbegin;\ncreate function f() returns void as $$ begin null; end; $$ language plpgsql;\ncommit;\n"
    cuerpo = migraciones.sin_transaccion_externa(texto)
    assert "$$ begin null; end; $$" in cuerpo
    assert not cuerpo.strip().endswith("commit;")
    with pytest.raises(RuntimeError): migraciones.sin_transaccion_externa("begin;\nselect 1;")


@pytest.mark.parametrize("nombre", ["001_duplicada.sql", "otra.sql", "004_Espacios.sql"])
def test_rechazar_versiones_ambiguas(tmp_path, nombre):
    carpeta = tmp_path / "supabase/migraciones"
    carpeta.mkdir(parents=True)
    (tmp_path / "supabase/esquema.sql").write_text("select 1;")
    (carpeta / nombre).write_text("select 2;")
    with pytest.raises(RuntimeError): migraciones.descubrir(tmp_path)


@pytest.mark.parametrize("host,usuario,puerto", [
    ("db.otro.supabase.co", "postgres", "5432"),
    ("aws-0.pooler.supabase.com", "postgres.otro", "5432"),
    ("aws-0.pooler.supabase.com", "postgres.proyecto", "6543"),
    ("db.proyecto.supabase.co.evil", "postgres", "5432")])
def test_conexion_rechaza_proyecto_o_pooler_incorrecto(monkeypatch, host, usuario, puerto):
    monkeypatch.setattr(migraciones.psycopg, "connect", lambda **k: pytest.fail("No contactar un destino incorrecto"))
    dsn = make_conninfo(host=host, user=usuario, port=puerto, password="prueba-privada")
    with pytest.raises(RuntimeError, match="mismo proyecto"):
        migraciones.conexion(dsn, "https://proyecto.supabase.co")


def test_tls_no_se_degrada_por_la_uri(monkeypatch):
    capturadas = {}
    monkeypatch.setattr(migraciones.psycopg, "connect", lambda **k: capturadas.update(k))
    dsn = make_conninfo(host="aws-0.pooler.supabase.com", user="postgres.proyecto", port="5432", password="prueba", sslmode="disable")
    migraciones.conexion(dsn, "https://proyecto.supabase.co")
    assert capturadas["sslmode"] == "verify-full" and capturadas["sslrootcert"]
    assert capturadas["connect_timeout"] == 20 and capturadas["autocommit"]


def test_error_de_conexion_no_expone_contrasena(monkeypatch):
    def fallar(**k): raise migraciones.psycopg.OperationalError("dato privado de conexión")
    monkeypatch.setattr(migraciones.psycopg, "connect", fallar)
    with pytest.raises(RuntimeError) as error:
        migraciones.conexion("host=db.proyecto.supabase.co password=prueba", "https://proyecto.supabase.co")
    assert "dato privado" not in str(error.value)


@pytest.mark.parametrize("valor", ["", "123", "!" * 43])
def test_clave_invalida_no_crea_respaldo(valor):
    with pytest.raises(RuntimeError, match="32 bytes"): respaldo.clave(valor)


def test_sql_aplicado_no_se_reescribe(monkeypatch):
    ms = migraciones.descubrir()
    monkeypatch.setattr(migraciones, "aplicadas", lambda c: {"001": (ms[0].nombre, "0" * 64)})
    with pytest.raises(RuntimeError, match="cambió"): migraciones.pendientes(None, ms)


def test_version_anterior_no_intenta_revertir_schema(monkeypatch):
    monkeypatch.setattr(migraciones, "aplicadas", lambda c: {"999": ("999_futura.sql", "0" * 64)})
    with pytest.raises(RuntimeError, match="anterior"): migraciones.pendientes(None, migraciones.descubrir())


def respuesta(datos, estado=200): return SimpleNamespace(status_code=estado, json=lambda: datos)


def test_marca_antigua_ausente_es_compatible(monkeypatch):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://proyecto.supabase.co", "prueba"))
    sesion = SimpleNamespace(get=lambda *a, **k: respuesta({"code": "PGRST205"}, 404))
    assert preparar.marca(sesion) is None


@pytest.mark.parametrize("payload", [{}, {"migraciones": {}}, {"migraciones": {"001": "inválido"}}, None])
def test_marca_corrupta_no_se_confunde_con_instalacion_manual(monkeypatch, payload):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://proyecto.supabase.co", "prueba"))
    sesion = SimpleNamespace(get=lambda *a, **k: respuesta([{"payload": payload}]))
    with pytest.raises(RuntimeError, match="sin volver al modo local"): preparar.marca(sesion)


@pytest.mark.parametrize("respuesta_o_error", [respuesta({}, 403), respuesta({}, 500), requests.Timeout()])
def test_marca_desconocida_no_vuelve_al_modo_local(monkeypatch, respuesta_o_error):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://proyecto.supabase.co", "prueba"))
    def get(*a, **k):
        if isinstance(respuesta_o_error, Exception): raise respuesta_o_error
        return respuesta_o_error
    with pytest.raises(RuntimeError, match="sin volver al modo local"):
        preparar.marca(SimpleNamespace(get=get))


def args(**op):
    return Namespace(prueba=False, modo="incremental", manual=False, fase="respaldo", instancia_nueva=False,
                     salida="salida", privado="privado", **op)


def test_prueba_no_contacta_base_ni_activa(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_DB_URL", "conexión privada")
    monkeypatch.setattr(migraciones, "conexion", lambda *a: pytest.fail("No conectar en prueba"))
    archivo = tmp_path / "env"
    monkeypatch.setenv("GITHUB_ENV", str(archivo))
    a = args()
    a.prueba = True
    preparar.correr(a)
    assert archivo.read_text() == "ESTADO_SUPABASE_ACTIVO=false\nCATALOGO_ACTIVO=false\n"


def test_marca_activa_sin_variables_habilita_captura(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("ESTADO_SUPABASE_ACTIVO", raising=False)
    monkeypatch.delenv("CAPTURA_HORARIA_ACTIVA", raising=False)
    monkeypatch.setattr(preparar, "marca", lambda: {"migraciones": {m.version: m.digest for m in migraciones.descubrir()}})
    salida = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    preparar.correr(args())
    assert "ejecutar=true" in salida.read_text()


def test_actualizacion_pendiente_exige_acceso_administrativo(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(preparar, "marca", lambda: {"migraciones": {"001": "hash antiguo"}})
    with pytest.raises(RuntimeError, match="pendiente"): preparar.correr(args())


def test_desactivar_horario_manual_sigue_respetandose(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("CAPTURA_HORARIA_ACTIVA", "false")
    monkeypatch.setenv("ESTADO_SUPABASE_ACTIVO", "true")
    monkeypatch.setattr(preparar, "marca", lambda: None)
    salida = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    preparar.correr(args())
    assert "ejecutar=false" in salida.read_text()


def test_acceso_sin_clave_de_cifrado_no_contacta_base(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_URL", "conexión de ensayo")
    monkeypatch.delenv("SUPABASE_BACKUP_KEY", raising=False)
    monkeypatch.setattr(migraciones, "conexion", lambda *a: pytest.fail("No contactar sin poder respaldar"))
    with pytest.raises(RuntimeError, match="BACKUP_KEY"): preparar.correr(args())


def test_rest_sin_confirmar_no_activa_captura(monkeypatch, tmp_path):
    import secrets
    from contextlib import nullcontext
    monkeypatch.setenv("SUPABASE_DB_URL", "conexión de ensayo")
    monkeypatch.setenv("SUPABASE_BACKUP_KEY", secrets.token_urlsafe(32))
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://proyecto.supabase.co", "prueba"))
    monkeypatch.setattr(migraciones, "conexion", lambda *a: nullcontext(None))
    monkeypatch.setattr(migraciones, "preparar", lambda *a, **k: {"aplicadas": [], "vigentes": 3, "presupuesto": {"mes": "2026-11", "reservas": {}}})
    def sin_confirmar(*a): raise RuntimeError("REST no confirmó")
    monkeypatch.setattr(preparar, "comprobar_rest", sin_confirmar)
    privado = tmp_path / "privado"
    privado.mkdir()
    (privado / "plan.json").write_text(json.dumps({}))
    a = args()
    a.fase, a.privado, a.salida = "aplicar", str(privado), str(tmp_path / "salida")
    entorno = tmp_path / "env"
    monkeypatch.setenv("GITHUB_ENV", str(entorno))
    with pytest.raises(RuntimeError, match="REST no confirmó"): preparar.correr(a)
    assert not entorno.exists()
    assert not (tmp_path / "salida/trabajo/apify_presupuesto.json").exists()


def test_respaldo_se_sube_antes_de_aplicar_sql():
    texto = (migraciones.RAIZ / ".github/actions/preparar-supabase/action.yml").read_text()
    assert texto.index("--fase respaldo") < texto.index("uses: actions/upload-artifact@v4") < texto.index("--fase aplicar")
    assert "continue-on-error" not in texto


@pytest.mark.parametrize('codigo,categoria', [('23505','identidad_unica'),('23503','referencia_pendiente'),('57014','tiempo_consulta'),('55P03','bloqueo'),('42501','permisos')])
def test_error_sql_explica_categoria_sin_revelar_datos(codigo, categoria):
    class ErrorPrivado(Exception):
        sqlstate = codigo
    mensaje = migraciones.error_sql(ErrorPrivado('URI privada; fila privada; contraseña privada'))
    assert codigo in mensaje and categoria in mensaje and 'privada' not in mensaje


def test_ensayo_de_migracion_revierte_transaccion_tambien_al_fallar(monkeypatch):
    from buscador import diagnostico_migraciones
    from contextlib import contextmanager
    transacciones = []
    class Conexion:
        @contextmanager
        def transaction(self, **op):
            transacciones.append(op)
            try: yield
            finally: transacciones.append('salida')
        def execute(self, consulta): pass
    monkeypatch.setattr(migraciones, 'pendientes', lambda *a: [])
    def fallo(*a): raise RuntimeError('fallo controlado')
    monkeypatch.setattr(migraciones, 'aplicar', fallo)
    with pytest.raises(RuntimeError): diagnostico_migraciones.ensayar(Conexion())
    assert transacciones == [{'force_rollback': True}, 'salida']


def test_ciclos_solo_aliases_y_no_referencias_explicitas():
    assert migraciones.ciclos_aliases([('a',None,['a','b']),('b',None,['a','b'])]) == [('a','b')]
    assert not migraciones.ciclos_aliases([('a','b',['a','b']),('b','a',['a','b'])])
    assert not migraciones.ciclos_aliases([('a',None,['a','b']),('b',None,['b'])])
    assert not migraciones.ciclos_aliases([('a',None,['a','c']),('b',None,['b','c']),('c',None,['c'])])
