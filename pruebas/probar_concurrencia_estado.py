"""Ensayo real en una base nueva/temporal; sin actores Apify ni datos productivos."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--docker")
    args = p.parse_args()
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true":
        raise SystemExit("Solo habilitado explícitamente para PostgreSQL de pruebas")
    entorno = dict(os.environ)
    for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        entorno.pop(k, None)
    if args.docker:
        base = ["docker", "--host=unix:///var/run/docker.sock", "exec", "-i", args.docker,
                "psql", "-U", "postgres"]
    else:
        if entorno.get("PGHOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
            raise SystemExit("El ensayo solo admite PostgreSQL local aislado")
        base = ["psql", "-h", "127.0.0.1", "-U", "postgres"]
    def ejecutar(sql, db="postgres", permitir_error=False):
        r = subprocess.run(base + ["-d", db, "-At", "-v", "ON_ERROR_STOP=1"], input=sql,
                           text=True, capture_output=True, env=entorno, encoding="utf-8")
        if r.returncode and not permitir_error:
            raise RuntimeError(r.stderr)
        return r
    db = "adaptia_prueba_" + uuid4().hex
    ejecutar(f"create database {db};")
    try:
        raiz = Path(__file__).resolve().parent.parent
        for ruta in ("supabase/esquema.sql", "supabase/migraciones/002_catalogo.sql", "supabase/migraciones/003_estado_operativo.sql"):
            ejecutar((raiz / ruta).read_text(encoding="utf-8"), db)
        def sql(s, permitir_error=False): return ejecutar(s, db, permitir_error)
        fecha = sql("select (now()at time zone 'America/Bogota')::date;").stdout.strip()
        mes = fecha[:7]
        sql("select public.operacion_inicializar(" + "'" + json.dumps({"mes": mes, "reservas": {}}) + "');")
        def reservar(solicitud=None):
            q = f"set role service_role; select public.apify_reservar('{solicitud or uuid4()}','{uuid4()}','{fecha}',5000000,3000000,25000);"
            r = sql(q).stdout.strip().splitlines()[-1]
            return json.loads(r)["monto_micro"]
        with ThreadPoolExecutor(12) as ex:
            autorizadas = list(ex.map(lambda _: reservar(), range(40)))
        dias = int(sql(f"select extract(day from (date_trunc('month','{fecha}'::timestamp)+interval '1 month - 1 day')); ").stdout.strip())
        total = int(sql("select coalesce(sum(micro_usd),0) from public.apify_reservas;").stdout.strip())
        assert total == sum(autorizadas) <= 5_000_000 // dias
        # Mismo identificador en procesos independientes: una sola autorización.
        sql("delete from public.apify_reservas;")
        solicitud = str(uuid4())
        with ThreadPoolExecutor(8) as ex:
            repetidas = list(ex.map(lambda _: reservar(solicitud), range(12)))
        assert sum(repetidas) == 25_000 and repetidas.count(25_000) == 1
        # Importar un corte casi agotado nunca habilita más de lo restante mensual.
        sql("delete from public.apify_reservas;")
        otra = sql(f"select case when extract(day from '{fecha}'::date)=1 then '{fecha}'::date+1 else date_trunc('month','{fecha}'::timestamp)::date end;").stdout.strip()
        seed = json.dumps({"mes": mes, "reservas": {otra: 4.99}})
        sql("select public.operacion_inicializar('" + seed + "');")
        with ThreadPoolExecutor(10) as ex:
            resto = list(ex.map(lambda _: reservar(), range(30)))
        assert sum(resto) == 10_000
        assert int(sql("select sum(micro_usd) from public.apify_reservas;").stdout.strip()) == 5_000_000
        # Una sola actualización gana la revisión compartida; las restantes deben fallar.
        r = json.loads(sql("select public.estado_guardar('catalogo','[{\"identificador\":\"x\",\"revision\":0,\"payload\":{\"v\":0}}]');").stdout.strip())
        revision = r[0]["revision"]
        def cambiar(n):
            datos = json.dumps([{"identificador": "x", "revision": revision, "payload": {"v": n}}])
            return sql("set role service_role;select public.estado_guardar('catalogo','" + datos + "');", True).returncode == 0
        with ThreadPoolExecutor(8) as ex:
            ganaron = list(ex.map(cambiar, range(1, 17)))
        assert sum(ganaron) == 1
        vieja = json.dumps([{"identificador": "x", "revision": revision}])
        assert sql("set role service_role;select public.estado_confirmar('catalogo','" + vieja + "');", True).returncode != 0
        assert sql("select count(*) from public.estado_operativo where cola='catalogo' and identificador='x';").stdout.strip() == "1"
        print("Concurrencia aprobada: tope diario/mensual, solicitud repetida, actualización única y confirmación antigua.")
        # 8.2 (SQL 023): ritmo diario propio (0,63), tope del mes que nunca se pasa y bloqueo por crédito agotado.
        ejecutar((raiz / "supabase/migraciones/023_apify_ritmo.sql").read_text(encoding="utf-8"), db)
        def reservar_ritmo(mensual=5_000_000, diario=630_000, monto=25_000, permitir_error=False):
            q = (f"set role service_role; select public.apify_reservar_ritmo('{uuid4()}','{uuid4()}','{fecha}',"
                 f"{mensual},{diario},3000000,{monto});")
            r = sql(q, permitir_error)
            return r if permitir_error else json.loads(r.stdout.strip().splitlines()[-1])["monto_micro"]
        sql("delete from public.apify_reservas;")
        with ThreadPoolExecutor(12) as ex:
            ritmo = list(ex.map(lambda _: reservar_ritmo(), range(40)))
        assert sum(ritmo) == 630_000 == int(sql("select sum(micro_usd) from public.apify_reservas;").stdout.strip())
        sql("delete from public.apify_reservas;")
        sql(f"insert into public.apify_reservas(solicitud,fecha,micro_usd,origen) values('legado:x','{otra}',4990000,'legado');")
        with ThreadPoolExecutor(10) as ex:
            resto = list(ex.map(lambda _: reservar_ritmo(), range(30)))
        assert sum(resto) == 10_000  # con ritmo de Starter, el tope del mes (5) sigue mandando
        sql("delete from public.apify_reservas;")
        assert reservar_ritmo(mensual=19_000_000) == 25_000  # Starter: tope 19 admitido (la 003 solo admite 5)
        assert reservar_ritmo(mensual=5_000_000, diario=6_000_000, permitir_error=True).returncode != 0
        assert reservar_ritmo(mensual=200_000_000, permitir_error=True).returncode != 0
        assert reservar_ritmo(mensual=2_000_000, diario=630_000) == 25_000  # tope por corrida (3) mayor que el del mes
        estado = json.loads(sql(f"set role service_role; select public.apify_marcar_agotado('{fecha}',5000000);").stdout.strip().splitlines()[-1])
        assert estado["bloqueado_tope"] == 5 and reservar_ritmo() == 0 and reservar_ritmo(mensual=2_000_000) == 0
        assert json.loads(sql("select public.apify_estado();").stdout.strip())["bloqueado_tope"] == 5
        assert reservar_ritmo(mensual=19_000_000) == 25_000  # se compró Starter: se vuelve a reservar sin borrar nada
        assert sql(f"set role anon; select public.apify_marcar_agotado('{fecha}',5000000);", True).returncode != 0
        assert sql("set role anon; select count(*) from public.apify_bloqueos;", True).returncode != 0
        sql("delete from public.apify_bloqueos; delete from public.apify_reservas;")
        print("SQL 023 aprobada: ritmo diario, tope del mes, tope de Starter, bloqueo por crédito y permisos.")
        # Respaldo completo de datos + las dos secuencias en otro destino vacío.
        sql("""insert into public.catalogo_vacantes(id,datos,observed_at,status,reason)
          values('aaaaaaaaaaaaaaaa','{"titulo":"Prueba"}',now(),'closed','cierre de ensayo');
          insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
          values('aaaaaaaaaaaaaaaa',current_date,'qa','exact',now(),'{"id":"aaaaaaaaaaaaaaaa"}');
          insert into public.ofertas(external_id,job_title,company_name,delivery_date)
          values('ensayo','QA','Empresa ficticia',current_date);""")
        tablas = ["catalogo_vacantes", "entregas_diarias", "ofertas", "estado_operativo", "apify_reservas",
                  "ofertas_id_seq", "estado_operativo_revision_seq"]
        prefijo = base[:-3] if args.docker else []
        conexion = ["-U", "postgres"] if args.docker else ["-h", "127.0.0.1", "-U", "postgres"]
        dump = subprocess.run(prefijo + ["pg_dump", *conexion, "-d", db, "--format=custom", "--data-only",
            "--no-owner", "--no-privileges", *["--table=public." + t for t in tablas]],
            capture_output=True, env=entorno, check=True).stdout
        destino = db + "_restaurada"
        ejecutar(f"create database {destino};")
        try:
            for ruta in ("supabase/esquema.sql", "supabase/migraciones/002_catalogo.sql", "supabase/migraciones/003_estado_operativo.sql"):
                ejecutar((raiz / ruta).read_text(encoding="utf-8"), destino)
            subprocess.run(prefijo + ["pg_restore", *conexion, "-d", destino, "--data-only", "--no-owner",
                "--no-privileges", "--single-transaction", "--exit-on-error"], input=dump,
                capture_output=True, env=entorno, check=True)
            for tabla in tablas[:5]:
                consulta = f"select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]') from public.{tabla} t;"
                assert sql(consulta).stdout == ejecutar(consulta, destino).stdout, tabla
            for secuencia in tablas[5:]:
                consulta = f"select last_value,is_called from public.{secuencia};"
                assert sql(consulta).stdout == ejecutar(consulta, destino).stdout, secuencia
            assert ejecutar("set role anon;select * from public.estado_operativo;", destino, True).returncode != 0
            revision_actual = int(sql("select last_value from public.estado_operativo_revision_seq;").stdout.strip())
            siguiente = ejecutar("select public.estado_guardar('catalogo','[{\"identificador\":\"nueva\",\"revision\":0,\"payload\":{}}]');", destino)
            assert json.loads(siguiente.stdout)[0]["revision"] > revision_actual
            assert ejecutar("insert into public.ofertas(external_id,job_title,company_name) values('siguiente','QA','Ensayo') returning id;", destino).stdout.splitlines()[0] == "2"
            print("Restauración aprobada: cinco tablas, dos secuencias, historial, cierre, presupuesto, pendiente y permisos.")
        finally:
            ejecutar(f"drop database {destino};")
    finally:
        ejecutar(f"drop database {db};")


if __name__ == "__main__":
    main()
