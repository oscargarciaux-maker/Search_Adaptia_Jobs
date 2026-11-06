"""Recorrido administrativo real SOLO en bases nuevas de un PostgreSQL local de pruebas."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import tempfile
from uuid import uuid4

from cryptography.exceptions import InvalidTag
import psycopg
from psycopg import sql

from buscador import migraciones, respaldo


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise SystemExit("Solo habilitado para PostgreSQL local aislado explícito")
    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    @contextmanager
    def nueva():
        db = "adaptia_auto_" + uuid4().hex
        with conectar() as admin: admin.execute(sql.SQL("create database {}").format(sql.Identifier(db)))
        try:
            with conectar(db) as conn: yield db, conn
        finally:
            with conectar() as admin: admin.execute(sql.SQL("drop database {}").format(sql.Identifier(db)))
    with conectar() as admin:
        for rol in ("anon", "authenticated", "service_role"):
            if not admin.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                admin.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol), sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
    ms = migraciones.descubrir()
    llave = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory() as carpeta:
        raiz = Path(carpeta)
        trabajo = raiz / "trabajo"
        trabajo.mkdir()
        with nueva() as (_, conn):
            plan = migraciones.planificar(conn, trabajo, raiz / "nueva.enc", llave)
            assert plan["necesaria"] and Path(plan["copia"]).exists()
            try:
                migraciones.preparar(conn, trabajo, plan)
                raise AssertionError("Instancia usada sin contador pudo inicializarse vacía")
            except psycopg.errors.RaiseException:
                pass
            assert not conn.execute("select to_regclass('public.ofertas')").fetchone()[0]
            assert not migraciones.aplicadas(conn)  # el SQL y el diario se revirtieron juntos
            r = migraciones.preparar(conn, trabajo, plan, instancia_nueva=True)
            assert r["aplicadas"] == [m.version for m in ms]
            journal = conn.execute("select version,aplicada_en from public.adaptia_migraciones order by version").fetchall()
            otro = migraciones.planificar(conn, trabajo, raiz / "no-necesaria.enc", llave)
            assert not otro["necesaria"] and not (raiz / "no-necesaria.enc").exists()
            assert not migraciones.preparar(conn, trabajo, otro)["aplicadas"]
            assert journal == conn.execute("select version,aplicada_en from public.adaptia_migraciones order by version").fetchall()
            # Reescribir un archivo ya aplicado falla antes de crear otra copia o tocar el esquema.
            cambiada = [migraciones.Migracion("001", ms[0].nombre, "0" * 64, ms[0].cuerpo), *ms[1:]]
            try:
                migraciones.planificar(conn, trabajo, raiz / "prohibida.enc", llave, cambiada)
                raise AssertionError("Se aceptó reescribir una migración")
            except RuntimeError:
                pass
            assert not (raiz / "prohibida.enc").exists()
        print("Instalación nueva, repetición sin replay y SQL/hash con rollback: aprobados.")

        # Instancia anterior instalada a mano, con historia y crédito utilizado.
        with nueva() as (origen, conn):
            for m in ms[:2]: conn.execute(m.cuerpo)
            fecha = conn.execute("select (now() at time zone 'America/Bogota')::date::text").fetchone()[0]
            presupuesto = {"mes": fecha[:7], "reservas": {fecha: 0.035}}
            (trabajo / "apify_presupuesto.json").write_text(json.dumps(presupuesto))
            (trabajo / "estado.json").write_text('{"fuente":"corte de ensayo"}')
            conn.execute("""insert into public.catalogo_vacantes(id,datos,observed_at,status)
                values('aaaaaaaaaaaaaaaa','{"titulo":"QA"}',now(),'closed');
                insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
                values('aaaaaaaaaaaaaaaa',current_date,'qa','exact',now(),'{"id":"aaaaaaaaaaaaaaaa"}');
                insert into public.ofertas(external_id,job_title,company_name,salary_min,delivery_date)
                values('ensayo','QA','Empresa ficticia',123456789.123456789,current_date);""")
            plan = migraciones.planificar(conn, trabajo, raiz / "anterior.enc", llave)
            # Borrar la copia después de preparar impide aplicar.
            invalido = dict(plan, digest="f" * 64)
            try:
                migraciones.preparar(conn, trabajo, invalido)
                raise AssertionError("No se exigió el respaldo del corte")
            except RuntimeError:
                pass
            assert not migraciones.aplicadas(conn)
            migraciones.preparar(conn, trabajo, plan)
            assert conn.execute("select sum(micro_usd) from public.apify_reservas").fetchone()[0] == 35000
            assert conn.execute("select count(*) from public.ofertas").fetchone()[0] == 1
            assert not conn.execute("select has_table_privilege('service_role','public.adaptia_migraciones','SELECT')").fetchone()[0]
            # Una migración inválida revierte también su primer ALTER correcto.
            cuerpo = "alter table public.ofertas add column prueba_fallida text; select no_existe;"
            mala = migraciones.Migracion("008", "008_fallida.sql", sha256(cuerpo.encode()).hexdigest(), cuerpo)
            plan = migraciones.planificar(conn, trabajo, raiz / "antes-fallo.enc", llave, ms + [mala])
            try:
                migraciones.preparar(conn, trabajo, plan, ms + [mala])
                raise AssertionError("SQL inválido se confirmó")
            except psycopg.errors.UndefinedColumn:
                pass
            assert not conn.execute("select 1 from information_schema.columns where table_schema='public' and table_name='ofertas' and column_name='prueba_fallida'").fetchone()
            assert "008" not in migraciones.aplicadas(conn)
            # Dos procesos/conexiones parten del mismo corte: solo uno aplica.
            cuerpo = "alter table public.ofertas add column prueba_concurrencia text;"
            buena = migraciones.Migracion("008", "008_correcta.sql", sha256(cuerpo.encode()).hexdigest(), cuerpo)
            versiones = ms + [buena]
            plan = migraciones.planificar(conn, trabajo, raiz / "concurrencia.enc", llave, versiones)
            def intentar(_):
                with conectar(origen) as otra:
                    try:
                        migraciones.preparar(otra, trabajo, plan, versiones)
                        return True
                    except RuntimeError:
                        return False
            with ThreadPoolExecutor(2) as ex:
                assert sum(ex.map(intentar, range(2))) == 1
            assert len(migraciones.aplicadas(conn)) == len(ms) + 1
            # Backup de las siete tablas y ambas secuencias; el archivo no contiene el texto en claro.
            conn.execute("select public.estado_guardar('ofertas','[{\"identificador\":\"pendiente\",\"revision\":0,\"payload\":{\"external_id\":\"pendiente\"}}]')")
            conn.execute("insert into public.ofertas(external_id,job_title,company_name) select 'lote-'||n,'QA','Ensayo' from generate_series(1,201) n")
            # Archivo con decimal anidado y una fusión todavía pendiente: recuperar sin aplicar limpieza al corte.
            conn.execute("""update public.ofertas set vacante_id='aaaaaaaaaaaaaaaa' where external_id='ensayo';
                insert into public.ofertas(external_id,job_title,company_name,vacante_id,salary_min)
                 values('copia-archivada','QA','Ensayo','aaaaaaaaaaaaaaaa',123456789.123456789);
                insert into public.catalogo_vacantes(id,datos,status,observed_at)
                 values('bbbbbbbbbbbbbbbb','{"duplicada_de":"aaaaaaaaaaaaaaaa"}','archived',now());
                alter table public.ofertas disable trigger oferta_unica;
                insert into public.ofertas(external_id,job_title,company_name,vacante_id)
                 values('alias-pendiente','QA','Ensayo','bbbbbbbbbbbbbbbb');
                alter table public.ofertas enable trigger oferta_unica;""")
            siguiente_id = conn.execute("select last_value+1 from public.ofertas_id_seq").fetchone()[0]
            copia = respaldo.crear(conn, trabajo, raiz / "completo.enc", llave)
            assert b"Empresa ficticia" not in copia.read_bytes()
            with nueva() as (_, destino):
                with destino.transaction(): migraciones.aplicar(destino, versiones)
                corrupta = raiz / "corrupta.enc"
                b = bytearray(copia.read_bytes())
                b[len(b) // 2] ^= 1
                corrupta.write_bytes(b)
                try:
                    respaldo.restaurar(destino, corrupta, llave, raiz / "trabajo-corrupto")
                    raise AssertionError("Se restauró un cifrado alterado")
                except InvalidTag:
                    pass
                assert not destino.execute("select count(*) from public.ofertas").fetchone()[0]
                respaldo.restaurar(destino, copia, llave, raiz / "trabajo-restaurado")
                for tabla in respaldo.TABLAS:
                    consulta = sql.SQL("select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]')::text from public.{} t").format(sql.Identifier(tabla))
                    assert conn.execute(consulta).fetchone() == destino.execute(consulta).fetchone(), tabla
                for nombre in respaldo.SECUENCIAS:
                    consulta = sql.SQL("select last_value,is_called from public.{}").format(sql.Identifier(nombre))
                    assert conn.execute(consulta).fetchone() == destino.execute(consulta).fetchone(), nombre
                assert (raiz / "trabajo-restaurado/estado.json").read_bytes() == (trabajo / "estado.json").read_bytes()
                assert destino.execute("insert into public.ofertas(external_id,job_title,company_name) values('nueva','QA','Ensayo') returning id").fetchone()[0] == siguiente_id
                assert destino.execute("select tgenabled from pg_trigger where tgname='oferta_unica'").fetchone()[0] == 'O'
                assert not destino.execute("select has_table_privilege('anon','public.estado_operativo','SELECT')").fetchone()[0]
        print("Actualización manual → automática sin perder crédito/historia, respaldo obligatorio y migradores concurrentes: aprobados.")
        print("Copia AES-GCM y restauración: siete tablas, dos secuencias, decimales exactos, pendiente, permisos y trabajo; corrupción rechazada.")


if __name__ == "__main__":
    main()
