"""Ensayo acotado del SQL pendiente: transacción revertida siempre, sin captura ni Apify."""
import os
import re
import time

import psycopg

from buscador import migraciones, supabase


def perfilar(conn):
    """Medir la función instalada sin conservar escrituras ni imprimir datos de ofertas."""
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute("set local statement_timeout='10s'")
        print({"volumen_reconciliacion": dict(conn.execute("""
          select 'catalogo',count(*) from public.catalogo_vacantes union all
          select 'selecciones',count(*) from public.entregas_diarias union all
          select 'ofertas',count(*) from public.ofertas union all
          select 'archivo',count(*) from public.ofertas_enlaces_historicos
        """).fetchall())}, flush=True)
    t0 = time.perf_counter()
    try:
        with conn.transaction(force_rollback=True):
            conn.execute("set local role service_role")
            conn.execute("set local lock_timeout='1s'")
            conn.execute("set local statement_timeout='3s'")
            resultado = conn.execute("select public.reconciliar_ofertas()").fetchone()[0]
        print({"perfil_revertido_ms":round((time.perf_counter()-t0)*1000),"resultado":resultado}, flush=True)
        return True
    except psycopg.Error as e:
        # El contexto completo puede contener datos. Solo reconocer nombres/etapas estáticos.
        contexto = e.diag.context or ""
        etapas = [("with recursive aliases", "identidades"), ("with metadatos", "identidades"),
                  ("with recursive recorrido", "identidades"), ("with destinos", "resolver_urls"),
                  ("update public.ofertas", "actualizar_enlaces")]
        etapa = next((nombre for marca,nombre in etapas if marca in contexto.lower()), "sin_identificar")
        linea = re.search(r'function (?:public\.)?reconciliar_ofertas\(\) line (\d+)', contexto)
        print({"perfil_revertido_ms":round((time.perf_counter()-t0)*1000),"codigo":e.sqlstate,
               "etapa":etapa,"linea":int(linea[1]) if linea else None},flush=True)
        return False


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
        if any(m.version not in {"006","007","008","009","010"} for m in pendientes):
            raise RuntimeError("Este ensayo admite únicamente las migraciones 006/007/008/009/010 de esta revisión; usar el instalador respaldado para otras versiones.")
        migraciones.aplicar(conn, pendientes)
        if any(m.version in {"008", "010"} for m in pendientes):
            conn.execute("set local statement_timeout='3s'")
            conn.execute("set local role service_role")
            t0 = time.perf_counter()
            resultado = conn.execute("select public.reconciliar_ofertas()").fetchone()[0]
            print({"reconciliacion_indexada_ms":round((time.perf_counter()-t0)*1000), "resultado":resultado},flush=True)
        return [m.version for m in pendientes]


def main():
    try:
        with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""),
                supabase.base(os.environ.get("SUPABASE_URL", ""))) as conn:
            perfil_ok = perfilar(conn)
            print(identidades(conn), flush=True)
            versiones = ensayar(conn)
            if not perfil_ok and not versiones:
                raise RuntimeError("La consolidación instalada no superó el perfil; no hay una reparación pendiente ensayada.")
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
