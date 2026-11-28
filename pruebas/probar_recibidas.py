"""SQL 024 (P-12.1): «lo que ya recibió» cada persona se lee completo por páginas ordenadas por `id` y el índice
`panel_asignaciones(perfil_id, vacante_id)` evita recorrer toda la tabla. En PostgreSQL real comprueba: 1) que el plan
de la lectura (`perfil_id = any(...)`, como la pide PostgREST) usa el índice; 2) que `paginar` lee las 12.000
asignaciones ficticias de una persona sin perder ni repetir ninguna, con el orden de `uuid` de PostgreSQL.
Solo PostgreSQL local aislado y datos ficticios."""
import json
import os
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones
from panel.repositorio import por_ids

INDICE = "panel_asignaciones_perfil_vacante"
PERSONAS, POR_PERSONA, GRANDE = 200, 300, 12_000


def _plan(c, consulta, valores):
    plan = c.execute("explain (format json) " + consulta, valores).fetchone()[0]
    return json.dumps(plan)


def _pedir_sql(c):
    """Lo mínimo de PostgREST para `panel_asignaciones`: `in.(…)`, `gt.` sobre `id`, `order=id` y `limit`."""
    def pedir(metodo, ruta, params):
        assert metodo == "GET" and ruta == "panel_asignaciones" and params["order"] == "id"
        perfiles = params["perfil_id"].removeprefix("in.(").removesuffix(")").split(",")
        desde = params.get("id", "").removeprefix("gt.") or None
        filas = c.execute("select id::text, perfil_id::text, vacante_id from public.panel_asignaciones "
                          "where perfil_id = any(%s::uuid[]) and (%s::uuid is null or id > %s::uuid) "
                          "order by id limit %s", (perfiles, desde, desde, params["limit"])).fetchall()
        return [{"id": i, "perfil_id": p, "vacante_id": v} for i, p, v in filas]
    return pedir


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Solo PostgreSQL local aislado")

    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_recibidas_" + uuid4().hex
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
            assert c.execute("select to_regclass(%s)", ("public." + INDICE,)).fetchone()[0], "Falta el índice de 024"
            # Datos ficticios: 200 personas con 300 asignaciones cada una y una con 12.000 (60 días de historial).
            c.execute("insert into public.panel_versiones(revision, vigente_desde, configuracion) "
                      "values (1, current_date, '{}')")
            c.execute("insert into public.panel_ejecuciones(fecha, revision) "
                      "select current_date - g, 1 from generate_series(0, 59) g")
            c.execute("insert into public.catalogo_vacantes(id, datos, observed_at, status) "
                      "select lpad(to_hex(g), 16, '0'), '{}'::jsonb, now(), 'active' from generate_series(1, %s) g",
                      (GRANDE,))
            personas = [str(uuid4()) for _ in range(PERSONAS)]
            c.execute("""
                with e as (select id, row_number() over (order by fecha) - 1 as n from public.panel_ejecuciones)
                insert into public.panel_asignaciones(ejecucion_id, cliente_id, perfil_id, cargo_id, vacante_id,
                                                      match_grade, explicacion, filtros, cargo_configuracion)
                select e.id, gen_random_uuid(), p.perfil::uuid, gen_random_uuid(), lpad(to_hex(v.n), 16, '0'),
                       'exact', '[]', '{}', '{}'
                from unnest(%s::text[]) with ordinality as p(perfil, k)
                cross join lateral generate_series(1, case when p.k = 1 then %s else %s end) as v(n)
                join e on e.n = v.n %% 60
                """, (personas, GRANDE, POR_PERSONA))
            c.execute("analyze public.panel_asignaciones")
            total = c.execute("select count(*) from public.panel_asignaciones").fetchone()[0]
            assert total == GRANDE + (PERSONAS - 1) * POR_PERSONA, total
            # 1) La lectura de quien va corto (unas pocas personas de muchas, como la pide PostgREST) usa el índice.
            consulta = ("select id, perfil_id, vacante_id from public.panel_asignaciones where perfil_id = any(%s::uuid[]) "
                        "order by id limit 500")
            plan = _plan(c, consulta, (personas[1:2],))
            assert INDICE in plan, "La lectura de lo recibido no usa el índice de 024: " + plan[:400]
            plan = _plan(c, "select vacante_id from public.panel_asignaciones where perfil_id = any(%s::uuid[])",
                         (personas[1:6],))
            assert INDICE in plan, "La búsqueda por persona no usa el índice de 024: " + plan[:400]
            # 2) Keyset sobre PostgreSQL real: las 12.000 de una persona, completas y sin repetir.
            filas = list(por_ids(_pedir_sql(c), "panel_asignaciones", "perfil_id", [personas[0]], "id,perfil_id,vacante_id"))
            vacantes = [f["vacante_id"] for f in filas]
            assert len(vacantes) == GRANDE == len(set(vacantes)), len(vacantes)
            assert [f["id"] for f in filas] == sorted(f["id"] for f in filas)  # el orden de uuid de PostgreSQL
            juntas = list(por_ids(_pedir_sql(c), "panel_asignaciones", "perfil_id", personas, "id,perfil_id,vacante_id"))
            assert len(juntas) == total, len(juntas)  # varias tandas de 50 personas, sin perder filas
        print("SQL 024: la lectura de lo recibido usa el índice por persona y lee 12.000 asignaciones de una persona "
              f"(y {total} en tandas) sin tope ni repetidas: aprobado.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database {} with (force)").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
