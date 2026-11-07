"""Migración de filas reales de ejemplo y escritores concurrentes; únicamente en PG local aislado."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from buscador import migraciones



def probar_aliases(conectar, nombre):
    from buscador.diagnostico_migraciones import ensayar
    with conectar() as admin:
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
    try:
        with conectar(nombre) as c:
            ms = migraciones.descubrir()
            with c.transaction(): migraciones.aplicar(c,[m for m in ms if m.version<"006"])
            c.execute("""insert into public.catalogo_vacantes(id,datos,status,observed_at) values
                ('1111111111111111','{"enlace":"https://jobs.lever.co/ciclo/a"}','active',now()),
                ('2222222222222222','{"enlace":"https://jobs.lever.co/ciclo/b"}','active',now());
                insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id) values
                ('ciclo-a','QA','Empresa','https://jobs.lever.co/ciclo/a','1111111111111111'),
                ('ciclo-b','QA','Empresa','https://jobs.lever.co/ciclo/b','2222222222222222');
                update public.catalogo_vacantes set datos=datos||'{"ids_agrupados":["1111111111111111","2222222222222222"]}'::jsonb;
                insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
                values('2222222222222222',current_date,'qa','exact',now(),'{"conservar":"histórico"}');""")
            antes = c.execute("select jsonb_agg(to_jsonb(c) order by id) from public.catalogo_vacantes c").fetchone()[0]
            assert ensayar(c) == ['006','007','008','009']
            assert c.execute("select jsonb_agg(to_jsonb(c) order by id) from public.catalogo_vacantes c").fetchone()[0] == antes
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 2
            assert '006' not in migraciones.aplicadas(c)
            with c.transaction(): migraciones.aplicar(c,[m for m in ms if m.version>="006"])
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 1
            assert c.execute("select count(*) from public.ofertas_enlaces_historicos").fetchone()[0] == 1
            assert c.execute("select snapshot->>'conservar' from public.entregas_diarias").fetchone()[0] == 'histórico'
            # Recrear la misma equivalencia implícita después de instalar: tanto RPC como inserción convergen.
            c.execute("update public.catalogo_vacantes set datos=datos-'duplicada_de',status='active'")
            assert c.execute("select public.adaptia_vacante_principal('2222222222222222')").fetchone()[0] == '1111111111111111'
            c.execute("select public.reconciliar_ofertas()")
            c.execute("""insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id)
                values('ciclo-c','QA','Empresa','https://jobs.lever.co/ciclo/c','2222222222222222')""")
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 1
            # Una contradicción explícita sigue abortando sin tocar ofertas ni archivo.
            c.execute("""update public.catalogo_vacantes set datos=jsonb_set(datos,'{duplicada_de}',
                to_jsonb(case when id='1111111111111111' then '2222222222222222' else '1111111111111111' end))""")
            for q in ("select public.reconciliar_ofertas()", "select public.adaptia_vacante_principal('1111111111111111')"):
                try:
                    with c.transaction(): c.execute(q)
                    raise AssertionError('Una referencia explícita contradictoria fue aceptada')
                except psycopg.errors.RaiseException: pass
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 1
        print('Aliases recíprocos, preparación desde 005, ensayo revertido, inserción y ciclos explícitos: aprobados.')
    finally:
        with conectar() as admin:
            admin.execute(sql.SQL("drop database {}").format(sql.Identifier(nombre)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lote", help="Corte externo para ensayar, sin escribir sus datos ni descripciones en el repositorio")
    args = parser.parse_args()
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
            with c.transaction(): migraciones.aplicar(c, [m for m in ms if m.version<"005"])
            if args.lote:
                from buscador import catalogo, contrato, entrega, supabase, vacante
                lote = json.loads(Path(args.lote).read_text())
                vacantes = {v["id"]: v for lista in lote["elegidas"].values() for v,_ in lista}
                agrupadas = vacante.juntar(list(vacantes.values()))
                principales = {identificador:v["id"] for v in agrupadas for identificador in [v["id"],*v.get("_ids_fusionados",[])]}
                for v in list(agrupadas) + [dict(v,duplicada_de=principales[v["id"]]) for v in vacantes.values() if principales[v["id"]]!=v["id"]]:
                    c.execute("insert into public.catalogo_vacantes select * from jsonb_populate_record(null::public.catalogo_vacantes,%s)",
                        (Jsonb(catalogo.fila(v,"2026-11-06T00:00:00Z")),))
                for row in catalogo.filas_seleccion(lote):
                    c.execute("insert into public.entregas_diarias select * from jsonb_populate_record(null::public.entregas_diarias,%s)", (Jsonb(row),))
                columnas = contrato.COLUMNAS + ["search_tag","delivery_date","source_type","match_grade"]
                campos = sql.SQL(",").join(map(sql.Identifier,columnas))
                insertar = sql.SQL("insert into public.ofertas ({}) select {} from jsonb_populate_record(null::public.ofertas,%s)").format(campos,campos)
                nombres = {r["id"]:r["nombre"] for r in entrega.config()["roles"]}
                vistas = set()
                for rol, lista in lote["elegidas"].items():
                    for v,g in lista:
                        fila = contrato.filas(v,nombres[rol],entrega.GRADO_CONTRATO[g],lote["fecha"],v["_capturada_entrega"],solo_comprobados=False)[0]
                        # Reconstruir el formato anterior: una fila por cada URL limpia.
                        for u in (v.get("enlace"),v.get("enlace_directo")):
                            if not u: continue
                            url = contrato.url_limpia(u)
                            revision = v.get("verificacion")
                            if revision is not None and url not in {contrato.url_limpia(e["url"]) for e in revision.get("enlaces",[]) if e.get("estado")=="verificada"}:
                                continue
                            if url in vistas: continue
                            vistas.add(url)
                            f = dict(fila,offer_url=url,external_id=contrato.external_id(url),source_portal=contrato.portal(url))
                            c.execute(insertar,(Jsonb(supabase.fila_db(f)),))
                antes = c.execute("select count(*) from public.ofertas").fetchone()[0]
                with c.transaction(): migraciones.aplicar(c,[m for m in ms if m.version>="005"])
                despues = c.execute("select count(*) from public.ofertas").fetchone()[0]
                archivo = c.execute("select count(*) from public.ofertas_enlaces_historicos").fetchone()[0]
                assert antes == despues + archivo
                assert c.execute("select count(*) from public.entregas_diarias").fetchone()[0] == len(vacantes)
                assert c.execute("select count(*)=count(distinct vacante_id) from public.ofertas").fetchone()[0]
                print(json.dumps({"filas_antes":antes,"filas_despues":despues,"copias_archivadas":archivo,
                    "sin_identificar":c.execute("select count(*) from public.ofertas where vacante_id is null").fetchone()[0]}))
                return
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
            with c.transaction(): migraciones.aplicar(c, [m for m in ms if m.version>="005"])
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
            c.execute("""create table public.referencia_prueba(oferta_id bigint references public.ofertas(id) on delete cascade);
             insert into public.ofertas(external_id,job_title,company_name,offer_url)
              values('referenciada','QA Engineer','Empresa','https://jobs.lever.co/a/pendiente');
             insert into public.referencia_prueba select id from public.ofertas where external_id='referenciada';
             update public.catalogo_vacantes set datos=datos||'{"enlaces_alternativos":["https://jobs.lever.co/a/pendiente"]}'::jsonb
              where id='aaaaaaaaaaaaaaaa';""")
            try:
                with c.transaction(): c.execute("select public.reconciliar_ofertas()")
                raise AssertionError("Una consolidación pudo retirar una fila con referencias")
            except psycopg.errors.RaiseException:
                pass
            assert c.execute("select count(*) from public.referencia_prueba").fetchone()[0] == 1
            assert c.execute("select count(*) from public.ofertas where external_id='referenciada'").fetchone()[0] == 1
            c.execute("drop table public.referencia_prueba")
            assert c.execute("select count(*) from public.ofertas_enlaces_historicos").fetchone()[0] == 1
            assert not c.execute("select has_table_privilege('anon','public.ofertas_enlaces_historicos','SELECT')").fetchone()[0]
            assert not c.execute("select has_function_privilege('authenticated','public.reconciliar_ofertas()','EXECUTE')").fetchone()[0]
            assert not c.execute("select has_function_privilege('anon','public.adaptia_urls_identidad(jsonb)','EXECUTE')").fetchone()[0]
            # Una copia archivada anteriormente se reconoce por los IDs agrupados del principal.
            c.execute("""update public.catalogo_vacantes set datos=jsonb_set(datos,'{enlaces_alternativos}',
             coalesce(datos->'enlaces_alternativos','[]')||'["https://jobs.lever.co/a/adicional"]'::jsonb)
             where id='aaaaaaaaaaaaaaaa';
             insert into public.catalogo_vacantes(id,datos,status,observed_at)
             values('eeeeeeeeeeeeeeee','{"enlace":"https://jobs.lever.co/a/antigua"}','archived',now());
             update public.catalogo_vacantes set datos=datos||'{"ids_agrupados":["aaaaaaaaaaaaaaaa","eeeeeeeeeeeeeeee"]}'::jsonb
              where id='aaaaaaaaaaaaaaaa';
             insert into public.ofertas(external_id,job_title,company_name,offer_url)
              values('copia-antigua','QA Engineer','Empresa','https://jobs.lever.co/a/antigua');""")
            assert c.execute("select public.adaptia_vacante_principal('eeeeeeeeeeeeeeee')").fetchone()[0] == "aaaaaaaaaaaaaaaa"
            assert c.execute("select count(*) from public.ofertas where vacante_id='aaaaaaaaaaaaaaaa'").fetchone()[0] == 1
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
            c.execute("""insert into public.catalogo_vacantes(id,datos,status,observed_at)
             select substr(md5('volumen-'||n),1,16),jsonb_build_object(
              'enlace','https://jobs.lever.co/volumen/'||n,
              'enlaces_alternativos',jsonb_build_array('https://jobs.lever.co/volumen/'||n||'?utm_source=fuente',
                'https://www.linkedin.com/jobs/view/'||(9000000000::bigint+n)||'/?trk=prueba'),
              'ids_agrupados',jsonb_build_array(substr(md5('volumen-'||n),1,16)),
              'resumen',repeat('Responsabilidades y condiciones del puesto. ',50)), 'active',now()
             from generate_series(1,18000) n;""")
            c.execute("""insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id)
                select 'volumen-'||n,'QA','Ensayo','https://jobs.lever.co/volumen/'||n,substr(md5('volumen-'||n),1,16)
                from generate_series(1,300) n;
                analyze public.catalogo_vacantes;""")
            plan = c.execute("""explain (format json) select id from public.catalogo_vacantes
                where public.adaptia_urls_identidad(datos) @> array['linkedin:9000000123']""").fetchone()[0]
            assert 'catalogo_urls_identidad' in json.dumps(plan)
            assert c.execute("""select id from public.catalogo_vacantes
                where public.adaptia_urls_identidad(datos) @> array[public.adaptia_url_identidad('https://www.linkedin.com/jobs/view/9000000123?trk=otra')]""").fetchall() == [(c.execute("select substr(md5('volumen-123'),1,16)").fetchone()[0],)]
            with c.transaction():
                c.execute("set local statement_timeout='3s'")
                c.execute("set local role service_role")
                c.execute("select public.reconciliar_ofertas()")
            assert c.execute("select count(*) from public.ofertas where vacante_id='aaaaaaaaaaaaaaaa'").fetchone()[0] == 1
            assert 'https://jobs.lever.co/a/adicional' in c.execute("select enlaces_alternativos from public.ofertas where id=37").fetchone()[0]
        probar_aliases(conectar,nombre+"_aliases")
        print("Identidad, archivo, repetición, referencias, concurrencia y catálogo de 18.000 filas / 300 ofertas con índices y límite de tres segundos: aprobados.")
    finally:
        with conectar() as admin:
            admin.execute(sql.SQL("drop database {}").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
