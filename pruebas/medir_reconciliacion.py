"""Medir cuánto tarda reconciliar_ofertas() con volúmenes parecidos a los reales; solo en PG local aislado.

Datos ficticios: catálogo con aliases explícitos (`duplicada_de`), ofertas y selecciones. Imprime milisegundos por
escenario para ver qué parte crece con el volumen. No forma parte de la aceptación: es una medición.
"""
import json
import os
import time
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones


def poblar(c, catalogo, explicitas, ofertas):
    c.execute("""insert into public.catalogo_vacantes(id,datos,status,observed_at)
     select substr(md5('v-'||n),1,16),jsonb_build_object(
      'enlace','https://jobs.lever.co/med/'||n,
      'enlaces_alternativos',jsonb_build_array('https://www.linkedin.com/jobs/view/'||(8000000000::bigint+n)||'/?trk=x'),
      'ids_agrupados',jsonb_build_array(substr(md5('v-'||n),1,16)),
      'resumen',repeat('Condiciones del puesto. ',40)),'active',now()
     from generate_series(1,%s) n""", (catalogo - explicitas,))
    # Copias fusionadas: archivadas y apuntando a una principal (como hace bodega.py al juntar fuentes).
    c.execute("""insert into public.catalogo_vacantes(id,datos,status,observed_at)
     select substr(md5('d-'||n),1,16),jsonb_build_object(
      'enlace','https://jobs.lever.co/dup/'||n,'duplicada_de',substr(md5('v-'||(1+n%%%s)),1,16),
      'ids_agrupados',jsonb_build_array(substr(md5('d-'||n),1,16)),
      'resumen',repeat('Condiciones del puesto. ',40)),'archived',now()
     from generate_series(1,%s) n""", (catalogo - explicitas, explicitas))
    c.execute("""insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
     select substr(md5('v-'||n),1,16),current_date,'qa','exact',now(),
      jsonb_build_object('enlace','https://jobs.lever.co/med/'||n) from generate_series(1,%s) n""", (ofertas,))
    c.execute("""insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id)
     select 'med-'||n,'QA','Ensayo','https://jobs.lever.co/med/'||n,substr(md5('v-'||n),1,16)
     from generate_series(1,%s) n""", (ofertas,))
    c.execute("analyze")


def medir(c, consulta="select public.reconciliar_ofertas()"):
    tiempos = []
    for _ in range(3):
        with c.transaction():
            c.execute("set local role service_role")
            t0 = time.perf_counter()
            c.execute(consulta)
            tiempos.append(round((time.perf_counter() - t0) * 1000))
    return min(tiempos)


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise SystemExit("Solo PostgreSQL local de pruebas")

    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
                               password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    escenarios = [(int(x) for x in e.split(":")) for e in
                  os.environ.get("ESCENARIOS", "60000:0:1000,60000:10000:1000,60000:0:5000,150000:15000:5000").split(",")]
    for catalogo, explicitas, ofertas in escenarios:
        nombre = "adaptia_medir_" + uuid4().hex
        with conectar() as admin:
            admin.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
            for rol in ("anon", "authenticated", "service_role"):
                if not admin.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                    admin.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol), sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
        try:
            with conectar(nombre) as c:
                with c.transaction():
                    migraciones.aplicar(c, migraciones.descubrir())
                t0 = time.perf_counter()
                poblar(c, catalogo, explicitas, ofertas)
                poblado = round(time.perf_counter() - t0)
                print(json.dumps({"catalogo": catalogo, "explicitas": explicitas, "ofertas": ofertas,
                                  "poblado_s": poblado, "reconciliar_ms": medir(c)}), flush=True)
        finally:
            with conectar() as admin:
                admin.execute(sql.SQL("drop database {}").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
