"""Esquema versionado y preparación transaccional, con conexión administrativa limitada al paso de instalación."""
from dataclasses import dataclass
from contextlib import contextmanager
from hashlib import sha256, file_digest
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

import psycopg
from psycopg.conninfo import conninfo_to_dict

from buscador import respaldo
from buscador.tls_supabase import autoridades

RAIZ = Path(__file__).resolve().parent.parent
DIARIO = """
create table if not exists public.adaptia_migraciones (
 version text primary key, nombre text not null, sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
 aplicada_en timestamptz not null default now()
);
alter table public.adaptia_migraciones enable row level security;
revoke all on public.adaptia_migraciones from public,anon,authenticated,service_role;
"""


@dataclass(frozen=True)
class Migracion:
    version: str
    nombre: str
    digest: str
    cuerpo: str


def sin_transaccion_externa(texto):
    lineas = texto.splitlines()
    utiles = [i for i, linea in enumerate(lineas) if linea.strip() and not linea.lstrip().startswith("--")]
    if utiles and lineas[utiles[0]].strip().lower() == "begin;":
        if lineas[utiles[-1]].strip().lower() != "commit;":
            raise RuntimeError("Migración con transacción externa incompleta.")
        lineas[utiles[0]] = lineas[utiles[-1]] = ""
    return "\n".join(lineas)


def descubrir(raiz=RAIZ):
    archivos = [("001", raiz / "supabase/esquema.sql")]
    for ruta in sorted((raiz / "supabase/migraciones").glob("*.sql")):
        m = re.fullmatch(r"(\d{3})_[a-z0-9_]+\.sql", ruta.name)
        if not m: raise RuntimeError("Nombre de migración inválido; usar NNN_nombre.sql.")
        archivos.append((m[1], ruta))
    versiones = [v for v, _ in archivos]
    if versiones != sorted(set(versiones)):
        raise RuntimeError("Las versiones de migración deben ser únicas y crecientes.")
    return [Migracion(v, p.name, sha256(p.read_bytes()).hexdigest(), sin_transaccion_externa(p.read_text())) for v, p in archivos]


def error_conexion(error, directa=False):
    """Clasificar en memoria; nunca devolver el error libpq que puede contener la URI/contraseña."""
    texto = str(error).casefold()
    estado = getattr(error, "sqlstate", None)
    if estado == "28P01" or "password authentication failed" in texto:
        return "[DB_AUTENTICACION] El servidor rechazó la autenticación. Revisar contraseña de la base y codificación de caracteres especiales en la URI."
    if "tenant or user not found" in texto:
        return "[DB_USUARIO] El pooler no reconoce el usuario/proyecto. Volver a copiar la URI Session pooler del proyecto correcto."
    if "certificate" in texto or "sslrootcert" in texto:
        return "[DB_TLS] No se pudo verificar el certificado TLS. Revisar servidor y certificado; conservar la verificación TLS."
    if "network is unreachable" in texto or "no route to host" in texto:
        return ("[DB_IPV6] La conexión directa no tiene ruta de red desde el ejecutor. Usar Session pooler, puerto 5432."
                if directa else "[DB_RED] No hay ruta de red al pooler. Revisar disponibilidad y restricciones de red del proyecto.")
    if any(t in texto for t in ("could not translate host", "name or service not known", "name resolution", "nodename nor servname")):
        return "[DB_DNS] No se pudo resolver el servidor. Revisar la URI copiada y la disponibilidad del proyecto."
    if "timeout" in texto or "timed out" in texto:
        return "[DB_TIEMPO] La conexión agotó su tiempo. Revisar proyecto activo, Session pooler y restricciones de red."
    if "connection refused" in texto:
        return "[DB_RECHAZADA] El servidor rechazó la conexión de red. Revisar puerto 5432, estado del proyecto y acceso de red."
    if estado == "3D000":
        return "[DB_BASE] El servidor no reconoce el nombre de la base. Copiar la URI completa del proyecto."
    return "[DB_CONEXION] No se pudo establecer la conexión. Revisar disponibilidad, conexión Session pooler y acceso del proyecto; el error original se omite para proteger credenciales."



def error_sql(error):
    """Solo código SQL y categorías controladas; nunca filas, consultas ni conexión."""
    codigo = str(getattr(error, "sqlstate", "") or "sin_codigo")
    if not re.fullmatch(r"[A-Z0-9]{5}", codigo): codigo = "sin_codigo"
    clases = {"23505": "identidad_unica", "23503": "referencia_pendiente", "57014": "tiempo_consulta",
              "55P03": "bloqueo", "42501": "permisos"}
    mensaje = str(error).casefold()
    propios = {"ciclo de identidades": "ciclo_de_identidad", "principal todavía no": "principal_pendiente",
               "archivo histórico no coincide": "archivo_no_coincide", "referencias a ofertas": "referencias_externas"}
    clase = clases.get(codigo) or next((v for k,v in propios.items() if k in mensaje), "error_sql")
    return f"[DB_SQL {codigo}; {clase}] No se confirmó la actualización; la transacción fallida se revierte."


def conexion(dsn, url):
    """Mismo proyecto y TLS verificado, con errores acotados sin datos de la conexión."""
    if not dsn or not str(dsn).strip():
        raise RuntimeError("[DB_SECRETO] Falta SUPABASE_DB_URL en los secretos de Actions.")
    try:
        opciones = conninfo_to_dict(dsn)
    except (ValueError, psycopg.Error):
        raise RuntimeError("[DB_URI] SUPABASE_DB_URL no es una conexión PostgreSQL válida. Copiar la URI completa y codificar los caracteres especiales de la contraseña.") from None
    try:
        ref = urlparse(url).hostname or ""
    except (ValueError, TypeError):
        ref = ""
    if not re.fullmatch(r"[a-z0-9]+\.supabase\.co", ref):
        raise RuntimeError("[DB_API_URL] SUPABASE_URL debe ser la dirección API del proyecto Supabase.")
    host = opciones.get("host", "").lower()
    proyecto = ref.split(".")[0]
    directo = host == "db." + ref
    local = os.environ.get("ADAPTIA_PRUEBA_SQL") == "true" and host in ("127.0.0.1", "localhost")
    if not local:
        pooler = host.endswith(".pooler.supabase.com") and opciones.get("user") == "postgres." + proyecto
        if not (directo or pooler):
            raise RuntimeError("[DB_PROYECTO] La conexión no apunta al mismo proyecto de SUPABASE_URL o el usuario del pooler no coincide. Copiar Session pooler del proyecto correcto.")
        if opciones.get("port", "5432") != "5432":
            raise RuntimeError("[DB_PUERTO] Usar Session pooler del mismo proyecto en puerto 5432, no Transaction pooler 6543.")
        if not opciones.get("password"):
            raise RuntimeError("[DB_PASSWORD] Falta la contraseña de la base dentro de SUPABASE_DB_URL.")
        if any(t in opciones["password"].upper() for t in ("YOUR-PASSWORD", "YOUR_PASSWORD", "[PASSWORD]")):
            raise RuntimeError("[DB_PASSWORD] La URI conserva el marcador de contraseña. Sustituirlo por la contraseña real de la base, codificada para URI.")
        # Evitar opciones que cambien el destino real o degraden TLS de la URI.
        if set(opciones) - {"host", "port", "user", "password", "dbname", "sslmode"}:
            raise RuntimeError("[DB_OPCIONES] La URI contiene opciones no admitidas. Copiar la conexión Session pooler sin parámetros adicionales.")
        opciones.update(sslmode="verify-full")
    opciones.update(connect_timeout=20, application_name="adaptia_migraciones")
    try:
        if local:
            return psycopg.connect(**opciones, autocommit=True)
        with autoridades() as raiz:
            return psycopg.connect(**opciones, sslrootcert=raiz, autocommit=True)
    except psycopg.Error as e:
        raise RuntimeError(error_conexion(e, directa=directo)) from None


def aplicadas(conn):
    if not conn.execute("select to_regclass('public.adaptia_migraciones')").fetchone()[0]: return {}
    return {v: (n, h) for v, n, h in conn.execute("select version,nombre,sha256 from public.adaptia_migraciones")}


def pendientes(conn, versiones):
    anteriores = aplicadas(conn)
    esperadas = {m.version: (m.nombre, m.digest) for m in versiones}
    if any(v not in esperadas or esperadas[v] != valor for v, valor in anteriores.items()):
        raise RuntimeError("Una migración aplicada cambió o el código es anterior al esquema. Añadir una migración nueva; no reescribir SQL registrado.")
    faltantes = [m for m in versiones if m.version not in anteriores]
    if faltantes and any(v > faltantes[0].version for v in anteriores):
        raise RuntimeError("Hay un hueco en el historial de migraciones.")
    return faltantes


def aplicar(conn, versiones):
    if not versiones: return
    conn.execute(DIARIO)
    for m in versiones:
        conn.execute(m.cuerpo, prepare=False)
        conn.execute("insert into public.adaptia_migraciones(version,nombre,sha256) values(%s,%s,%s)",
                     (m.version, m.nombre, m.digest))


def validar(conn):
    for tabla in respaldo.TABLAS:
        if not conn.execute("select c.relrowsecurity from pg_class c where c.oid=to_regclass(%s)", ("public." + tabla,)).fetchone()[0]:
            raise RuntimeError("Falta protección RLS en las tablas del proyecto.")
    # Resolución de columnas y permisos fundamentales; nunca imprimir datos de las vacantes.
    conn.execute("select id,external_id,description_full from public.ofertas limit 0")
    conn.execute("select id,datos,observed_at from public.catalogo_vacantes limit 0")
    conn.execute("select vacante_id,snapshot,delivery_date from public.entregas_diarias limit 0")
    for tabla in ("estado_operativo", "apify_reservas", "adaptia_migraciones"):
        if conn.execute("select has_table_privilege('anon',%s,'SELECT') or has_table_privilege('authenticated',%s,'SELECT')", ("public."+tabla, "public."+tabla)).fetchone()[0]:
            raise RuntimeError("Hay permisos públicos indebidos en el estado privado.")


@contextmanager
def bloqueo(conn):
    conn.execute("set lock_timeout='30s'")
    conn.execute("set statement_timeout='5min'")
    conn.execute("select pg_advisory_lock(hashtextextended('adaptia.migraciones',0))")
    try:
        yield
    finally:
        conn.execute("select pg_advisory_unlock(hashtextextended('adaptia.migraciones',0))")


def corte(conn, versiones):
    faltantes = pendientes(conn, versiones)
    lista = respaldo.existentes(conn, ("estado_operativo",))
    marca = conn.execute("select payload from public.estado_operativo where cola='control' and identificador='instalacion_automatica'").fetchone() if lista else None
    huellas = {m.version: m.digest for m in versiones}
    return {"historial": aplicadas(conn), "marca": marca[0] if marca else None, "versiones": huellas,
            "necesaria": bool(faltantes or not marca or marca[0].get("migraciones") != huellas)}


def planificar(conn, trabajo, copia, llave, versiones=None):
    versiones = versiones or descubrir()
    with bloqueo(conn):
        plan = corte(conn, versiones)
        if plan["necesaria"]:
            respaldo.crear(conn, trabajo, copia, llave)
            with Path(copia).open("rb") as f:
                plan.update(copia=str(copia), digest=file_digest(f, "sha256").hexdigest())
        return plan


def preparar(conn, trabajo, plan, versiones=None, instancia_nueva=False):
    """El workflow solo llama tras subir el respaldo del plan. Mismos escritores excluidos entre fases."""
    plan = json.loads(json.dumps(plan))
    versiones = versiones or descubrir()
    huellas = {m.version: m.digest for m in versiones}
    with bloqueo(conn):
        actual = corte(conn, versiones)
        # Tuplas del controlador pasan a listas al guardar el plan; comparar la forma JSON.
        if json.loads(json.dumps(actual)) != {k: plan[k] for k in actual}:
            raise RuntimeError("Cambió el esquema entre respaldo y aplicación; crear un corte nuevo.")
        if actual["necesaria"]:
            if not plan.get("copia") or not Path(plan["copia"]).is_file():
                raise RuntimeError("Falta el respaldo cifrado confirmado del plan; no aplicar migraciones.")
            with Path(plan["copia"]).open("rb") as f:
                if file_digest(f, "sha256").hexdigest() != plan.get("digest"):
                    raise RuntimeError("Falta el respaldo cifrado confirmado del plan; no aplicar migraciones.")
        faltantes = pendientes(conn, versiones)
        with conn.transaction():
            aplicar(conn, faltantes)
            validar(conn)
            archivo = Path(trabajo) / "apify_presupuesto.json"
            presupuesto = json.loads(archivo.read_text()) if archivo.exists() else {}
            inicializada = conn.execute("select exists(select 1 from public.estado_operativo where cola='control' and identificador='inicializado')").fetchone()[0]
            if not presupuesto and not inicializada and instancia_nueva:
                for tabla in ("ofertas", "catalogo_vacantes", "entregas_diarias", "apify_reservas"):
                    if conn.execute(psycopg.sql.SQL("select exists(select 1 from public.{})").format(psycopg.sql.Identifier(tabla))).fetchone()[0]:
                        raise RuntimeError("Instancia nueva exige base sin historial ni reservas; recuperar el corte existente.")
                presupuesto = conn.execute("select jsonb_build_object('mes',to_char(now() at time zone 'America/Bogota','YYYY-MM'),'reservas','{}'::jsonb)").fetchone()[0]
            estado = conn.execute("select public.operacion_inicializar(%s::jsonb)", (json.dumps(presupuesto),)).fetchone()[0]
            conn.execute("""insert into public.estado_operativo(cola,identificador,payload) values('control','instalacion_automatica',%s::jsonb)
              on conflict(cola,identificador) do update set payload=excluded.payload,
              revision=nextval('public.estado_operativo_revision_seq'),actualizado_en=now()
              where public.estado_operativo.payload is distinct from excluded.payload""", (json.dumps({"migraciones": huellas}),))
        return {"aplicadas": [m.version for m in faltantes], "vigentes": len(versiones), "respaldo": bool(actual["necesaria"]), "presupuesto": estado}
