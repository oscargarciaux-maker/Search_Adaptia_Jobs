"""Ensayo en PostgreSQL local aislado de SQL 014 (contrato v16): bandeja «Por confirmar» y reglas de ubicación."""
import os
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Solo PostgreSQL local aislado")

    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
                               password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_revision_" + uuid4().hex
    with conectar() as c:
        for rol in ("anon", "authenticated", "service_role"):
            if not c.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                c.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol),
                          sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
        c.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
    try:
        with conectar(nombre) as c:
            with c.transaction():
                migraciones.aplicar(c, migraciones.descubrir())
            for tabla in ("panel_revisiones", "panel_reglas_ubicacion"):
                for rol in ("anon", "authenticated"):
                    assert not c.execute("select has_table_privilege(%s,%s,'SELECT')", (rol, "public." + tabla)).fetchone()[0]
                assert c.execute("select relrowsecurity from pg_class where relname=%s", (tabla,)).fetchone()[0]
            c.execute("insert into public.catalogo_vacantes(id,datos,status,observed_at) values('aaaaaaaaaaaaaaaa','{}','archived',now())")
            c.execute("set role service_role")
            c.execute("""insert into public.panel_revisiones(vacante_id,pista,ubicacion,sugerencia,perfiles,prioridad)
                         values('aaaaaaaaaaaaaaaa','Remote - LATAM','remote latam','["CO"]','[]',100)""")
            c.execute("update public.panel_revisiones set estado='confirmada', paises='[\"CO\"]' where vacante_id='aaaaaaaaaaaaaaaa'")
            for malo in ("insert into public.panel_revisiones(vacante_id) values('no-existe')",
                         "update public.panel_revisiones set estado='otra' where vacante_id='aaaaaaaaaaaaaaaa'",
                         "insert into public.panel_reglas_ubicacion(texto,resultado,origen) values('x y','[]','operador')",
                         "insert into public.panel_reglas_ubicacion(texto,resultado,origen) values('lugar','{}','ia')"):
                try:
                    with c.transaction():
                        c.execute(malo)
                    raise AssertionError("Se aceptó: " + malo)
                except psycopg.errors.Error:
                    pass
            c.execute("""insert into public.panel_reglas_ubicacion(texto,resultado,origen)
                         values('pueblo ejemplo','{"paises":["CO"]}','operador')""")
            assert c.execute("select count(*) from public.panel_reglas_ubicacion").fetchone()[0] == 1
            # Contrato v17: la limpieza de `ofertas` lee lo decidido en la bandeja.
            c.execute("reset role")
            c.execute("insert into public.catalogo_vacantes(id,datos,status,observed_at) values('bbbbbbbbbbbbbbbb','{}','archived',now())")
            c.execute("set role service_role")
            c.execute("""insert into public.panel_revisiones(vacante_id,pista,ubicacion,sugerencia,perfiles,prioridad,estado,motivo)
                         values('bbbbbbbbbbbbbbbb','Paris','paris','[]','[]',1,'descartada','no sirve (operador)')""")
            from buscador import limpiar_fuera_objetivo, paises
            try:
                assert limpiar_fuera_objetivo._cargar_reglas(c) == {"aaaaaaaaaaaaaaaa": "conservar", "bbbbbbbbbbbbbbbb": "borrar"}
            finally:
                paises.cargar_reglas()
        print("Bandeja SQL 014: solo servicio con RLS, estados válidos, vacante existente y reglas con origen y forma, decisiones leídas por la limpieza: aprobados.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
