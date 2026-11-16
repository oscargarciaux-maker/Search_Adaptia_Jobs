"""SQL 017 (16 nov): el lote del día admite más de 20 vacantes por cargo (hasta 600, el techo máximo). Reproduce el
fallo de la búsqueda manual del 15 nov («Rol o cantidad inválida») con 25 en un cargo: con todas las migraciones se
guarda; 601 sigue rechazándose. También comprueba que `ofertas` y `entrega_de_hoy` quedan sin permisos públicos aunque
Supabase los conceda por defecto. Solo PostgreSQL local aislado."""
import json
import os
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones


def _lote(fecha, n):
    filas = [[{"id": f"{i:016x}", "_capturada_entrega": "2026-11-16T00:30:00Z"}, "exacto"] for i in range(1, n + 1)]
    return json.dumps([{"identificador": fecha, "revision": 0,
                        "payload": {"fecha": fecha, "elegidas": {"cargo:producto": filas}}}])


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Solo PostgreSQL local aislado")
    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_lote_" + uuid4().hex
    with conectar() as c:
        for rol in ("anon", "authenticated", "service_role"):
            if not c.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                c.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol),
                    sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
        c.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
    try:
        with conectar(nombre) as c:
            # Como Supabase: lo que se crea en public recibe permisos para anon y authenticated por defecto.
            c.execute("alter default privileges in schema public grant all on tables to anon, authenticated")
            with c.transaction():
                migraciones.aplicar(c, migraciones.descubrir())
            for objeto in ("public.ofertas", "public.entrega_de_hoy"):
                for rol in ("anon", "authenticated"):
                    assert not c.execute("select has_table_privilege(%s,%s,'SELECT')", (rol, objeto)).fetchone()[0], \
                        f"{rol} conserva permisos sobre {objeto}"
            c.execute("select public.operacion_inicializar(%s::jsonb)",
                      (json.dumps({"mes": "2026-11", "reservas": {}}),))
            fecha = c.execute("select ((now() at time zone 'America/Bogota')::date)::text").fetchone()[0]
            r = c.execute("select public.estado_guardar('lote', %s::jsonb)", (_lote(fecha, 25),)).fetchone()[0]
            assert int(r[0]["revision"]) > 0, r
            try:
                c.execute("select public.estado_guardar('lote', %s::jsonb)", (_lote(fecha + "x", 601),))
                raise AssertionError("Se aceptaron 601 en un cargo")
            except psycopg.errors.RaiseException:
                pass
        print("Lote del día: 25 por cargo se guardan (SQL 017), 601 se rechazan; ofertas y entrega_de_hoy sin permisos "
              "públicos: aprobado.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database {} with (force)").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
