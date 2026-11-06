"""Ensayo acotado del SQL pendiente: transacción revertida siempre, sin captura ni Apify."""
import os

import psycopg

from buscador import migraciones, supabase


def identidades(conn):
    """Leer solo IDs y relaciones, sin descripciones ni filas completas."""
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute("set local statement_timeout='15s'")
        filas = conn.execute("select id,datos->>'duplicada_de',datos->'ids_agrupados' from public.catalogo_vacantes").fetchall()
    ciclos = migraciones.ciclos_aliases(filas)
    return {'ciclos_aliases_sin_referencia_explicita':len(ciclos),'muestra_ids':[list(c) for c in ciclos[:5]]}


def ensayar(conn):
    # El mismo bloqueo del instalador; el ensayo nunca registra una migración como aplicada.
    with conn.transaction(force_rollback=True):
        conn.execute("set local lock_timeout='3s'")
        conn.execute("set local statement_timeout='30s'")
        conn.execute("select pg_advisory_xact_lock(hashtextextended('adaptia.migraciones',0))")
        pendientes = migraciones.pendientes(conn, migraciones.descubrir())
        migraciones.aplicar(conn, pendientes)
        return [m.version for m in pendientes]


def main():
    try:
        with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""),
                supabase.base(os.environ.get("SUPABASE_URL", ""))) as conn:
            print(identidades(conn), flush=True)
            versiones = ensayar(conn)
    except psycopg.Error as e:
        print("::error::" + migraciones.error_sql(e))
        raise SystemExit(1) from None
    except RuntimeError as e:
        print("::error::" + str(e))
        raise SystemExit(1) from None
    except Exception:
        print("::error::No se confirmó el ensayo; se omiten detalles privados.")
        raise SystemExit(1) from None
    print("Ensayo revertido, sin instalación ni cambios conservados: " + (", ".join(versiones) or "ninguna pendiente"))


if __name__ == "__main__":
    main()
