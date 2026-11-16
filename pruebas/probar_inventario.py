"""PR 1.5: el inventario corre en un PostgreSQL local aislado con todas las migraciones, en solo lectura, y no encuentra
tablas públicas sin RLS, permisos para anon/authenticated ni funciones security definer sin search_path fijo."""
import os
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import inventario, migraciones


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Solo PostgreSQL local aislado")
    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_inventario_" + uuid4().hex
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
            datos = inventario.informe(inventario.consultar(c), inventario.usados_en_codigo())
        alertas = datos["alertas"]
        assert not alertas["tablas_sin_rls"], alertas["tablas_sin_rls"]
        assert not alertas["permisos_para_anon_o_authenticated"], alertas["permisos_para_anon_o_authenticated"]
        assert not alertas["funciones_security_definer_sin_search_path"], alertas
        assert len(datos["tablas"]) >= 15 and datos["tamano_mb"] > 0
        print("Inventario en solo lectura: RLS en todas las tablas, sin permisos públicos y funciones con search_path "
              "fijo: aprobado.")
        print("Para revisar:", {k: v for k, v in datos["posible_sobrante"].items() if k != "tablas_vacias"},
              "| foráneas sin índice:", alertas["foraneas_sin_indice"], "| duplicados:", alertas["indices_duplicados"])
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database {} with (force)").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
