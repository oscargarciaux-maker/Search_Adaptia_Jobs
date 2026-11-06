"""Migración de filas reales de ejemplo y escritores concurrentes; únicamente en PG local aislado."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise SystemExit("Solo PostgreSQL local de pruebas")
    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_unicas_" + uuid4().hex
    with conectar() as admin:
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
        for rol in ("anon", "authenticated", "service_role"):
            if not admin.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                admin.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol), sql.SQL("bypassrls") if rol=="service_role" else sql.SQL("")))
    try:
        with conectar(nombre) as c:
            ms = migraciones.descubrir()
            with c.transaction(): migraciones.aplicar(c, ms[:-1])
            c.execute("""insert into public.catalogo_vacantes(id,datos,status,observed_at) values
             ('aaaaaaaaaaaaaaaa','{"enlace":"https://jobs.lever.co/a/1","enlace_directo":"https://es.indeed.com/viewjob?jk=abc123"}','active',now()),
             ('bbbbbbbbbbbbbbbb','{"enlace":"https://jobs.lever.co/a/ambigua"}','active',now()),
             ('cccccccccccccccc','{"enlace":"https://jobs.lever.co/a/ambigua"}','active',now()),
             ('dddddddddddddddd','{"enlace":"https://jobs.lever.co/a/otra"}','active',now());
             insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
              values('aaaaaaaaaaaaaaaa',current_date,'qa','exact',now(),'{"titulo":"QA Engineer","conservar":"snapshot"}');
             insert into public.ofertas(id,external_id,job_title,company_name,offer_url) overriding system value values
              (37,'portal-a','QA Engineer','Empresa','https://jobs.lever.co/a/1?utm_source=linkedin'),
              (38,'portal-b','QA Engineer','Empresa','https://es.indeed.com/viewjob?jk=abc123'),
              (39,'ambigua-a','Otro puesto','Empresa','https://jobs.lever.co/a/ambigua'),
              (40,'ambigua-b','Otro puesto','Empresa','https://jobs.lever.co/a/ambigua');
             select setval('public.ofertas_id_seq',40);""")
            original = c.execute("select to_jsonb(o) from public.ofertas o where id=38").fetchone()[0]
            with c.transaction(): migraciones.aplicar(c, ms[-1:])
            assert c.execute("select id from public.ofertas where vacante_id='aaaaaaaaaaaaaaaa'").fetchall() == [(37,)]
            fila = c.execute("select fila_original from public.ofertas_enlaces_historicos where oferta_id=38").fetchone()[0]
            assert all(fila[k] == v for k,v in original.items())
            assert len(c.execute("select enlaces_alternativos from public.ofertas where id=37").fetchone()[0]) == 2
            assert c.execute("select count(*) from public.ofertas where vacante_id is null").fetchone()[0] == 2
            assert c.execute("select snapshot->>'conservar' from public.entregas_diarias").fetchone()[0] == "snapshot"
            assert c.execute("select public.reconciliar_ofertas()->>'archivadas'").fetchone()[0] == "0"
            with c.transaction(): c.execute(ms[-1].cuerpo)
            assert c.execute("select count(*) from public.ofertas_enlaces_historicos").fetchone()[0] == 1
            c.execute("""insert into public.ofertas(external_id,job_title,company_name,offer_url)
             values('portal-b','QA Engineer','Empresa','https://es.indeed.com/viewjob?jk=abc123') on conflict(external_id) do nothing""")
            assert c.execute("select count(*) from public.ofertas where vacante_id='aaaaaaaaaaaaaaaa'").fetchone()[0] == 1
            assert c.execute("select count(*) from public.ofertas_enlaces_historicos").fetchone()[0] == 1
            assert not c.execute("select has_table_privilege('anon','public.ofertas_enlaces_historicos','SELECT')").fetchone()[0]
            assert not c.execute("select has_function_privilege('authenticated','public.reconciliar_ofertas()','EXECUTE')").fetchone()[0]
        barrera = Barrier(2)
        def insertar(n):
            with conectar(nombre) as c:
                c.execute("set role service_role")
                barrera.wait(timeout=10)
                c.execute("""insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id)
                 values(%s,'QA Engineer','Otra empresa',%s,'dddddddddddddddd')""", ("copia-"+str(n),"https://jobs.lever.co/a/otra-"+str(n)))
        with ThreadPoolExecutor(2) as ex: list(ex.map(insertar,(1,2)))
        with conectar(nombre) as c:
            assert c.execute("select count(*) from public.ofertas where vacante_id='dddddddddddddddd'").fetchone()[0] == 1
            assert c.execute("select count(*) from public.ofertas_enlaces_historicos where vacante_id='dddddddddddddddd'").fetchone()[0] == 1
            # Una copia reenviada no genera otra fila operativa ni otro archivo por enlace.
            for n in (1,2):
                c.execute("""insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id)
                 values(%s,'QA Engineer','Otra empresa',%s,'dddddddddddddddd') on conflict(external_id) do nothing""",
                 ("copia-"+str(n),"https://jobs.lever.co/a/otra-"+str(n)))
            assert c.execute("select count(*) from public.ofertas_enlaces_historicos where vacante_id='dddddddddddddddd'").fetchone()[0] == 1
        print("Filas 37/38 → una oportunidad, archivo íntegro, ambigüedad conservada, migración repetible y concurrencia: aprobados.")
    finally:
        with conectar() as admin:
            admin.execute(sql.SQL("drop database {}").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
