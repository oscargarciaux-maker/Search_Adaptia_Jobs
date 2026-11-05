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


def conexion(dsn, url):
    """No aceptar una base distinta a la API configurada ni un pooler Transaction."""
    try:
        opciones = conninfo_to_dict(dsn)
        host = opciones.get("host", "").lower()
        ref = urlparse(url).hostname or ""
        if not re.fullmatch(r"[a-z0-9]+\.supabase\.co", ref):
            raise ValueError()
        proyecto = ref.split(".")[0]
        local = os.environ.get("ADAPTIA_PRUEBA_SQL") == "true" and host in ("127.0.0.1", "localhost")
        if not local:
            directo = host == "db." + ref
            pooler = host.endswith(".pooler.supabase.com") and opciones.get("user") == "postgres." + proyecto
            if not (directo or pooler) or opciones.get("port", "5432") != "5432": raise ValueError()
            # Evitar opciones que cambien el destino real o degraden TLS de la URI.
            if set(opciones) - {"host", "port", "user", "password", "dbname", "sslmode"}: raise ValueError()
            opciones.update(sslmode="verify-full", sslrootcert="/etc/ssl/certs/ca-certificates.crt")
        opciones.update(connect_timeout=20, application_name="adaptia_migraciones")
        return psycopg.connect(**opciones, autocommit=True)
    except (ValueError, psycopg.Error):
        raise RuntimeError("No se pudo conectar al mismo proyecto: revisar SUPABASE_DB_URL, contraseña, Session pooler 5432, TLS y red.") from None


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
