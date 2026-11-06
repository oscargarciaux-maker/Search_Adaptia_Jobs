"""Probar autenticación PostgreSQL y SELECT 1 en transacción de solo lectura. Sin DDL, datos ni secretos en logs."""
import os

import psycopg

from buscador import migraciones, supabase


def comprobar():
    url = supabase.base(os.environ.get("SUPABASE_URL", ""))
    with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""), url) as conn:
        try:
            with conn.transaction():
                conn.execute("set transaction read only")
                if conn.execute("select 1").fetchone() != (1,):
                    raise RuntimeError("[DB_CONSULTA] La conexión no confirmó la consulta de prueba.")
                if conn.execute("select current_setting('transaction_read_only')").fetchone() != ("on",):
                    raise RuntimeError("[DB_CONSULTA] No se confirmó la transacción de solo lectura.")
        except psycopg.Error as e:
            raise RuntimeError(migraciones.error_conexion(e)) from None
    return "[DB_OK] Autenticación y consulta de solo lectura confirmadas. Sin migraciones ni cambios de datos."


def main():
    try:
        mensaje = comprobar()
    except RuntimeError as e:
        print("::error::" + str(e))
        raise SystemExit(1) from None
    except Exception:
        print("::error::[DB_DIAGNOSTICO] No se pudo completar la comprobación; los detalles se omiten para proteger credenciales.")
        raise SystemExit(1) from None
    print(mensaje)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(mensaje + "\n")


if __name__ == "__main__":
    main()
