"""Ensayo acotado del SQL pendiente: transacción revertida siempre, sin captura ni Apify."""
import os
import re
import time

import psycopg
from psycopg import sql

from buscador import migraciones, supabase


def medir_lotes(conn):
    """Recorrer los lotes de SQL 021 como la API: cada uno es una sentencia con su propio límite de tiempo."""
    lotes, mas_lento, archivadas, r = 0, 0, 0, {}
    for funcion, desde, limite in supabase.LOTES_RECONCILIACION:
        while desde is not None:
            t0 = time.perf_counter()
            consulta = sql.SQL("select public.{}(%s,%s)").format(sql.Identifier(funcion))
            r = conn.execute(consulta, (desde, limite)).fetchone()[0]
            mas_lento = max(mas_lento, round((time.perf_counter() - t0) * 1000))
            lotes += 1
            archivadas += int(r.get("archivadas") or 0)
            desde = r.get("siguiente")
    return {"lotes": lotes, "lote_mas_lento_ms": mas_lento, "archivadas": archivadas,
            "filas_unicas": r.get("filas_unicas"), "sin_identificar": r.get("sin_identificar")}


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
            if conn.execute("select to_regprocedure('public.reconciliar_ofertas_lote(bigint,integer)')").fetchone()[0]:
                resultado = medir_lotes(conn)
            else:
                resultado = conn.execute("select public.reconciliar_ofertas()").fetchone()[0]
        print({"perfil_revertido_ms":round((time.perf_counter()-t0)*1000),"resultado":resultado}, flush=True)
        return True
    except psycopg.Error as e:
        # El contexto completo puede contener datos. Solo reconocer nombres/etapas estáticos.
        contexto = e.diag.context or ""
        etapas = [("with recursive aliases", "identidades"), ("with metadatos", "identidades"), ("with semillas", "identidades"),
                  ("with recursive recorrido", "identidades"), ("with destinos", "resolver_urls"),
                  ("update public.ofertas", "actualizar_enlaces")]
        etapa = next((nombre for marca,nombre in etapas if marca in contexto.lower()), "sin_identificar")
        linea = re.search(r'function (?:public\.)?reconciliar_(?:ofertas|ofertas_lote|referencias_lote)\([^)]*\) line (\d+)', contexto)
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


# 012 y 013 solo crean tablas privadas del panel (ajustes, contactos y borradores); 015 solo reemplaza las
# comprobaciones de guardar y programar (metas por perfil, contrato v21) y 016 solo añade «Aplicar hoy» (contrato v27):
# se pueden ensayar igual. 018 solo añade la columna `panel_revisiones.resumen` (contrato v34). 019 solo reemplaza
# las funciones `panel_publicar` y `panel_publicar_hoy` («Confirmar y aplicar», contrato v43), sin tablas ni datos.
# 020 solo añade el número corto de cada vacante (`catalogo_vacantes.numero`, su secuencia y disparadores; contrato v48).
# 021 solo reemplaza la reconciliación por lotes cortos y añade un índice parcial; sin tablas ni datos nuevos.
# 022 solo crea la tabla privada `estado_trabajo` (detalle por cargo fuera de la rama pública); sin tocar otras.
# 023 solo añade la tabla privada `apify_bloqueos` y las funciones de reserva con ritmo diario (8.2); reemplaza
# `apify_estado` con un campo más. No toca datos. 024 solo añade un índice a `panel_asignaciones` (P-12.1).
ENSAYABLES = {"006", "007", "008", "009", "010", "011", "012", "013", "014", "015", "016", "017", "018", "019", "020",
              "021", "022", "023", "024"}


def ensayar(conn):
    # El mismo bloqueo del instalador; el ensayo nunca registra una migración como aplicada.
    with conn.transaction(force_rollback=True):
        conn.execute("set local lock_timeout='3s'")
        conn.execute("set local statement_timeout='30s'")
        conn.execute("select pg_advisory_xact_lock(hashtextextended('adaptia.migraciones',0))")
        pendientes = migraciones.pendientes(conn, migraciones.descubrir())
        if any(m.version not in ENSAYABLES for m in pendientes):
            raise RuntimeError("Este ensayo admite únicamente las migraciones " + "/".join(sorted(ENSAYABLES)) +
                               " de esta revisión; usar el instalador respaldado para otras versiones.")
        migraciones.aplicar(conn, pendientes)
        if any(m.version in {"008", "010", "011", "021"} for m in pendientes):
            conn.execute("set local statement_timeout='3s'")
            conn.execute("set local role service_role")
            t0 = time.perf_counter()
            resultado = (medir_lotes(conn) if any(m.version == "021" for m in pendientes)
                         else conn.execute("select public.reconciliar_ofertas()").fetchone()[0])
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
