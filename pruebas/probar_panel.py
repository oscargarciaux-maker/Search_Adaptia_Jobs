"""SQL de control en PostgreSQL local aislado: permisos, cuotas, conflictos e historial."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones
from panel.repositorio import configuracion_demo


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Solo PostgreSQL local aislado")
    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_panel_" + uuid4().hex
    with conectar() as c:
        for rol in ("anon", "authenticated", "service_role"):
            if not c.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                c.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol),
                    sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
        c.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
    try:
        cfg = configuracion_demo()
        with conectar(nombre) as c:
            with c.transaction():
                migraciones.aplicar(c, migraciones.descubrir())
            for rol in ("anon", "authenticated"):
                assert not c.execute("select has_table_privilege(%s,'public.panel_configuracion','SELECT')", (rol,)).fetchone()[0]
                assert not c.execute("select has_function_privilege(%s,'public.panel_guardar(integer,jsonb)','EXECUTE')", (rol,)).fetchone()[0]
            c.execute("set role service_role")
            guardar = c.execute("select public.panel_guardar(0,%s::jsonb)", (json.dumps(cfg),)).fetchone()[0]
            assert guardar["revision"] == 1
            publicada = c.execute("select public.panel_publicar(1)").fetchone()[0]
            assert c.execute("select vigente_desde > (now() at time zone 'America/Bogota')::date from public.panel_versiones").fetchone()[0]
            assert c.execute("select public.panel_publicar(1)").fetchone()[0] == publicada
            mala = json.loads(json.dumps(cfg))
            mala["cargos"][0]["cupo"] += 1
            try:
                c.execute("select public.panel_guardar(1,%s::jsonb)", (json.dumps(mala),))
                raise AssertionError("Se guardó un presupuesto superior a 120")
            except psycopg.errors.RaiseException:
                pass
            assert c.execute("select revision from public.panel_configuracion").fetchone()[0] == 1
        barrera = Barrier(2)
        def guardar_concurrente(i):
            datos = json.loads(json.dumps(cfg))
            datos["clientes"][0]["nombre"] = "Referencia " + str(i)
            with conectar(nombre) as c:
                c.execute("set role service_role")
                barrera.wait(timeout=10)
                try:
                    c.execute("select public.panel_guardar(1,%s::jsonb)", (json.dumps(datos),))
                    return True
                except psycopg.errors.SerializationFailure:
                    return False
        with ThreadPoolExecutor(2) as ex:
            assert sum(ex.map(guardar_concurrente, (1, 2))) == 1
        with conectar(nombre) as c:
            assert c.execute("select configuracion->'clientes'->0->>'nombre' from public.panel_versiones where revision=1").fetchone()[0] == cfg["clientes"][0]["nombre"]
            c.execute("insert into public.catalogo_vacantes(id,datos,status,observed_at) values('abcdef0123456789','{}','active',now())")
            ejecucion = c.execute("insert into public.panel_ejecuciones(fecha,revision) values(current_date,1) returning id").fetchone()[0]
            p = cfg["perfiles"][0]
            c.execute("""insert into public.panel_asignaciones(ejecucion_id,cliente_id,perfil_id,cargo_id,vacante_id,match_grade,explicacion,filtros,cargo_configuracion)
                values(%s,%s,%s,%s,'abcdef0123456789','exact','[]',%s::jsonb,%s::jsonb)""",
                (ejecucion, p["cliente_id"], p["id"], p["cargo_id"], json.dumps(p), json.dumps(cfg["cargos"][0])))
            try:
                c.execute("delete from public.catalogo_vacantes where id='abcdef0123456789'")
                raise AssertionError("Se borró una vacante con historial de cliente")
            except psycopg.errors.ForeignKeyViolation:
                pass
            assert c.execute("select count(*) from public.panel_asignaciones").fetchone()[0] == 1
        print("Panel SQL: RLS, acceso exclusivo de servicio, 120 cupos, revisión concurrente, vigencia siguiente e historial protegido: aprobados.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database {}").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
