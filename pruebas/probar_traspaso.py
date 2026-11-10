"""Traspaso real entre dos bases nuevas de un PostgreSQL local aislado (nunca Supabase)."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import tempfile
from uuid import uuid4

import psycopg
from psycopg import sql

from buscador import migraciones, respaldo, traspaso


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise SystemExit("Solo habilitado para PostgreSQL local aislado explícito")
    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
            password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    @contextmanager
    def nueva():
        db = "adaptia_traspaso_" + uuid4().hex
        with conectar() as admin: admin.execute(sql.SQL("create database {}").format(sql.Identifier(db)))
        try:
            with conectar(db) as conn: yield conn
        finally:
            with conectar() as admin: admin.execute(sql.SQL("drop database {} with (force)").format(sql.Identifier(db)))
    with conectar() as admin:
        for rol in ("anon", "authenticated", "service_role"):
            if not admin.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                admin.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol), sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
    llave = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory() as carpeta:
        raiz = Path(carpeta)
        trabajo = raiz / "trabajo"
        trabajo.mkdir()
        (trabajo / "estado.json").write_text('{"rotacion": 7}')
        with nueva() as origen:
            plan = migraciones.planificar(origen, trabajo, raiz / "inicial.enc", llave)
            migraciones.preparar(origen, trabajo, plan, instancia_nueva=True)
            origen.execute("""insert into public.catalogo_vacantes(id,datos,status,observed_at)
                 values('aaaaaaaaaaaaaaaa','{"titulo":"QA Engineer"}','active',now());
                insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
                 values('aaaaaaaaaaaaaaaa','2026-11-10','qa','exact',now(),'{"titulo":"QA Engineer"}');
                insert into public.ofertas(external_id,job_title,company_name,vacante_id)
                 values('traspaso','QA Engineer','Empresa ficticia','aaaaaaaaaaaaaaaa');""")
            siguiente = origen.execute("select last_value+1 from public.ofertas_id_seq").fetchone()[0]

            # Un destino con tablas de otra aplicación del mismo nombre se rechaza sin tocarlo.
            with nueva() as ocupado:
                ocupado.execute("create table public.ofertas(id int)")
                try:
                    traspaso.trasladar(origen, ocupado, trabajo, llave, raiz / "rechazado.enc", "https://otro.supabase.co")
                    raise AssertionError("Se aceptó un destino con tablas propias")
                except RuntimeError:
                    pass
                assert ocupado.execute("select count(*) from information_schema.tables where table_schema='public'").fetchone()[0] == 1
            assert not traspaso.trasladada(origen)

            # Si la restauración falla a mitad, el destino queda vacío y el origen sigue operando.
            with nueva() as destino:
                original = respaldo.restaurar
                def fallar(*a, **k):
                    original(*a, **k)
                    raise RuntimeError("fallo simulado tras restaurar")
                respaldo.restaurar = fallar
                try:
                    traspaso.trasladar(origen, destino, trabajo, llave, raiz / "fallido.enc", "https://destino.supabase.co")
                    raise AssertionError("Se ignoró un fallo de restauración")
                except RuntimeError:
                    pass
                finally:
                    respaldo.restaurar = original
                assert not respaldo.existentes(destino, respaldo.TABLAS)
                assert not traspaso.trasladada(origen)

            # Un ensayo copia y comprueba igual, pero el origen sigue operando.
            with nueva() as practica:
                traspaso.trasladar(origen, practica, trabajo, llave, raiz / "ensayo.enc", "https://prueba.supabase.co", ensayo=True)
                assert respaldo.existentes(practica, respaldo.TABLAS) and not traspaso.trasladada(origen)
                traspaso.exigir_vigente(origen)

            with nueva() as destino:
                inv = traspaso.trasladar(origen, destino, trabajo, llave, raiz / "traspaso.enc", "https://destino.supabase.co")
                assert inv["tablas"]["ofertas"] == 1 and inv["tablas"]["catalogo_vacantes"] == 1
                for tabla in respaldo.TABLAS:
                    consulta = sql.SQL("select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]')::text from public.{} t").format(sql.Identifier(tabla))
                    if tabla == "estado_operativo":  # el origen gana solo la marca de traslado
                        consulta = sql.SQL("select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]')::text from public.estado_operativo t where identificador<>'trasladada'")
                    assert origen.execute(consulta).fetchone() == destino.execute(consulta).fetchone(), tabla
                assert migraciones.aplicadas(destino) == migraciones.aplicadas(origen)
                assert destino.execute("insert into public.ofertas(external_id,job_title,company_name) values('nueva','QA','Ensayo') returning id").fetchone()[0] == siguiente
                assert not destino.execute("select has_table_privilege('anon','public.estado_operativo','SELECT')").fetchone()[0]
                # El destino queda listo para operar: marca de instalación vigente y sin marca de traslado.
                assert not migraciones.corte(destino, migraciones.descubrir())["necesaria"]
                assert not traspaso.trasladada(destino)
                assert traspaso.trasladada(origen)["destino"] == "https://destino.supabase.co"
                try:
                    traspaso.exigir_vigente(origen)
                    raise AssertionError("Un origen trasladado siguió aceptando operaciones")
                except RuntimeError:
                    pass
                try:  # repetir el traspaso no mezcla historiales
                    traspaso.exigir_destino_libre(destino)
                    raise AssertionError("Se aceptó repetir sobre un destino ocupado")
                except RuntimeError:
                    pass
    print("Traspaso: destino ajeno rechazado, fallo sin restos, once tablas/secuencias idénticas, destino operativo y origen detenido: aprobados.")


if __name__ == "__main__":
    main()
