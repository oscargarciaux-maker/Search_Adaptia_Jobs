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
            # SQL 019 (contrato v43): confirmar deja la versión vigente desde hoy en Bogotá.
            assert c.execute("select vigente_desde = (now() at time zone 'America/Bogota')::date from public.panel_versiones").fetchone()[0]
            assert c.execute("select public.panel_publicar(1)").fetchone()[0] == publicada
            mala = json.loads(json.dumps(cfg))
            mala["techo_diario"] = 0
            try:
                c.execute("select public.panel_guardar(1,%s::jsonb)", (json.dumps(mala),))
                raise AssertionError("Se guardó un techo diario de 0")
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
            # SQL 015 (contrato v21): con techo 130 se guarda y programa una suma de 125; ya no exige 120 exactos.
            c.execute("set role service_role")
            r = c.execute("select revision from public.panel_configuracion").fetchone()[0]
            amplia = json.loads(json.dumps(cfg))
            amplia["techo_diario"], amplia["cargos"][0]["cupo"] = 130, amplia["cargos"][0]["cupo"] + 5
            assert c.execute("select public.panel_guardar(%s,%s::jsonb)", (r, json.dumps(amplia))).fetchone()[0]["revision"] == r + 1
            assert c.execute("select public.panel_publicar(%s)", (r + 1,)).fetchone()[0]["revision"] == r + 1
            excesiva = json.loads(json.dumps(amplia))
            excesiva["techo_diario"] = 601
            try:
                c.execute("select public.panel_guardar(%s,%s::jsonb)", (r + 1, json.dumps(excesiva)))
                raise AssertionError("Se guardó un techo diario mayor que 600")
            except psycopg.errors.RaiseException:
                pass
            # Un borrador por encima del techo se guarda, pero no se programa.
            pasada = json.loads(json.dumps(amplia))
            pasada["cargos"][0]["cupo"] += 10
            c.execute("select public.panel_guardar(%s,%s::jsonb)", (r + 1, json.dumps(pasada)))
            try:
                c.execute("select public.panel_publicar(%s)", (r + 2,))
                raise AssertionError("Se programó una suma mayor que el techo")
            except psycopg.errors.RaiseException:
                pass
            # «Aplicar hoy» (016, hoy alias de panel_publicar por SQL 019) también rechaza lo que supera el techo.
            try:
                c.execute("select public.panel_publicar_hoy(%s)", (r + 2,))
                raise AssertionError("Se aplicó hoy una suma mayor que el techo")
            except psycopg.errors.RaiseException:
                pass
            c.execute("reset role")
            c.execute("update public.panel_ejecuciones set estado='completa' where id=%s", (ejecucion,))
            c.execute("set role service_role")
            c.execute("select public.panel_guardar(%s,%s::jsonb)", (r + 2, json.dumps(amplia)))
            hoy_bogota = c.execute("select (now() at time zone 'America/Bogota')::date").fetchone()[0]
            c.execute("reset role")
            c.execute("update public.panel_ejecuciones set fecha=%s where id=%s", (hoy_bogota, ejecucion))
            c.execute("set role service_role")
            aplicada = c.execute("select public.panel_publicar_hoy(%s)", (r + 3,)).fetchone()[0]
            assert aplicada["vigente_desde"] == hoy_bogota.isoformat()
            c.execute("reset role")
            revision, anteriores = c.execute("select revision,resumen->'revisiones_anteriores' from "
                                             "public.panel_ejecuciones where id=%s", (ejecucion,)).fetchone()
            # SQL 019: cada confirmación del día anota la versión anterior (la primera fue la 1).
            assert revision == r + 3 and anteriores[0] == 1 and anteriores[-1] != r + 3
            assert c.execute("select count(*) from public.panel_asignaciones").fetchone()[0] == 1  # nada se borra
            # Importar clientes (15 nov): el borrador resultante de «borrar del todo» lo acepta el SQL real y se programa.
            from panel import importar
            r, actual = c.execute("select revision, borrador from public.panel_configuracion").fetchone()
            previa = importar.previa(actual, "nombre;cargo;vive_en;meta_diaria\nPersona A;Cargo importado;Chile;8\n"
                                     "Persona B;QA;España;5\n", "borrar")
            assert previa["errores"] == 0, previa
            assert c.execute("select public.panel_guardar(%s,%s::jsonb)",
                             (r, json.dumps(previa["configuracion"]))).fetchone()[0]["revision"] == r + 1
            assert c.execute("select public.panel_publicar(%s)", (r + 1,)).fetchone()[0]["revision"] == r + 1
            nombres = c.execute("select array_agg(x->>'nombre' order by x->>'nombre') from public.panel_configuracion, "
                                "jsonb_array_elements(borrador->'clientes') x").fetchone()[0]
            assert nombres == ["Persona A", "Persona B"], nombres
            viejo = cfg["clientes"][0]["id"]
            c.execute("insert into public.panel_contactos(cliente_id, telefono) values (%s, '+573000000000')", (viejo,))
            c.execute("delete from public.panel_contactos where cliente_id=%s", (viejo,))
            assert not c.execute("select 1 from public.panel_contactos where cliente_id=%s", (viejo,)).fetchone()
        print("Panel SQL: RLS, acceso exclusivo de servicio, techo diario, revisión concurrente, vigencia siguiente, "
              "historial protegido e importación de clientes: aprobados.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database {}").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
