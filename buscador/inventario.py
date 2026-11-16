"""Inventario de la base (PR 1.5, 16 nov): qué tablas, índices y funciones existen, cuánto ocupan y qué no se usa.

Solo lectura (transacción `read only`) y solo cifras: nunca lee filas ni datos de clientes. Incluye comprobaciones al
estilo de Splinter, el revisor oficial de Supabase:
- tablas públicas sin RLS o con permisos para `anon`/`authenticated`;
- índices sin uso o duplicados;
- claves foráneas sin índice;
- funciones `security definer` sin `search_path` fijo.

Uso: `python -m buscador.inventario` con SUPABASE_DB_URL (flujo «Inventario de la base»).
"""
import json
import os
import sys

from buscador import migraciones, supabase

LIMITE_GRATIS_MB = 500

CONSULTAS = {
    "tablas": """
        select c.relname, c.reltuples::bigint, pg_total_relation_size(c.oid), c.relrowsecurity,
               coalesce(s.n_tup_ins, 0), coalesce(s.n_tup_upd, 0), coalesce(s.n_tup_del, 0),
               greatest(s.last_autoanalyze, s.last_analyze, s.last_autovacuum, s.last_vacuum)::text
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        left join pg_stat_user_tables s on s.relid = c.oid
        where n.nspname = 'public' and c.relkind = 'r' order by pg_total_relation_size(c.oid) desc""",
    "indices_sin_uso": """
        select s.relname, s.indexrelname, pg_relation_size(s.indexrelid)
        from pg_stat_user_indexes s join pg_index i on i.indexrelid = s.indexrelid
        where s.schemaname = 'public' and s.idx_scan = 0 and not i.indisprimary and not i.indisunique
        order by pg_relation_size(s.indexrelid) desc""",
    "indices_duplicados": """
        select array_agg(c.relname order by c.relname)
        from pg_index i join pg_class c on c.oid = i.indexrelid join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
        group by i.indrelid, i.indkey::text, coalesce(i.indexprs::text, ''), coalesce(i.indpred::text, '')
        having count(*) > 1""",
    "foraneas_sin_indice": """
        select cl.relname, co.conname
        from pg_constraint co join pg_class cl on cl.oid = co.conrelid join pg_namespace n on n.oid = cl.relnamespace
        where co.contype = 'f' and n.nspname = 'public' and not exists (
            select 1 from pg_index i where i.indrelid = co.conrelid
            and (i.indkey::int2[])[0:array_length(co.conkey, 1) - 1] = co.conkey)""",
    "permisos_publicos": """
        select table_name, grantee, string_agg(privilege_type, ',' order by privilege_type)
        from information_schema.role_table_grants
        where table_schema = 'public' and grantee in ('anon', 'authenticated')
        group by table_name, grantee order by table_name""",
    "funciones": """
        select p.proname, p.prosecdef,
               coalesce(array_to_string(p.proconfig, ','), '') like '%search_path%'
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.prokind = 'f' order by p.proname""",
    "vistas": """select viewname from pg_views where schemaname = 'public' order by viewname""",
    "tamano": "select pg_database_size(current_database())",
}


def consultar(conn):
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute("set local statement_timeout = '30s'")
        filas = {nombre: conn.execute(sql).fetchall() for nombre, sql in CONSULTAS.items()}
        # La estimación del planificador vale 0 en tablas pequeñas nunca analizadas: ahí se cuenta de verdad (rápido).
        exactas = []
        for fila in filas["tablas"]:
            if fila[1] < 50_000:
                total = conn.execute(f'select count(*) from public."{fila[0]}"').fetchone()[0]  # nosec B608 — nombre del catálogo
                fila = (fila[0], total, *fila[2:])
            exactas.append(fila)
        filas["tablas"] = exactas
        return filas


def usados_en_codigo(raiz="."):
    """Nombres que aparecen en el código y las migraciones (para marcar funciones y vistas sin llamadas)."""
    texto = []
    for carpeta in ("buscador", "panel", "web/src", "supabase"):
        for dirpath, _, archivos in os.walk(os.path.join(raiz, carpeta)):
            for a in archivos:
                if a.endswith((".py", ".ts", ".tsx", ".sql")):
                    with open(os.path.join(dirpath, a), encoding="utf-8", errors="ignore") as f:
                        texto.append(f.read())
    return "\n".join(texto)


def informe(filas, codigo=""):
    mb = lambda b: round((b or 0) / 1_048_576, 2)  # noqa: E731
    sin_llamada = lambda nombre: codigo.count(nombre) <= 1  # noqa: E731 — solo su propia definición
    tablas = [{"tabla": t, "filas_aprox": max(0, n), "mb": mb(b), "rls": rls, "insertadas": i, "actualizadas": u,
               "borradas": d, "ultimo_mantenimiento": m or ""} for t, n, b, rls, i, u, d, m in filas["tablas"]]
    total = mb(filas["tamano"][0][0])
    salida = {
        "tamano_mb": total, "limite_plan_gratis_mb": LIMITE_GRATIS_MB,
        "uso_del_limite": f"{round(100 * total / LIMITE_GRATIS_MB)} %",
        "tablas": tablas,
        "alertas": {
            "tablas_sin_rls": [t["tabla"] for t in tablas if not t["rls"]],
            "permisos_para_anon_o_authenticated": [f"{t}: {g} ({p})" for t, g, p in filas["permisos_publicos"]],
            "funciones_security_definer_sin_search_path": [f for f, definer, fijo in filas["funciones"]
                                                           if definer and not fijo],
            "indices_duplicados": [list(x[0]) for x in filas["indices_duplicados"]],
            "foraneas_sin_indice": [f"{t}.{c}" for t, c in filas["foraneas_sin_indice"]],
        },
        "posible_sobrante": {
            "indices_sin_uso": [f"{t}.{i} ({mb(b)} MB)" for t, i, b in filas["indices_sin_uso"]],
            "funciones_sin_llamada_en_codigo": [f for f, _, _ in filas["funciones"] if codigo and sin_llamada(f)],
            "vistas_sin_llamada_en_codigo": [v for (v,) in filas["vistas"] if codigo and sin_llamada(v)],
            "tablas_vacias": [t["tabla"] for t in tablas if t["filas_aprox"] == 0],
        },
        "nota": "Solo cifras y nombres de objetos; ninguna fila ni dato de clientes. «Posible sobrante» es una "
                "lista para revisar, no para borrar: un índice sin uso puede servir a una consulta mensual.",
    }
    return salida


def main():
    url = supabase.base(os.environ.get("SUPABASE_URL", ""))
    with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""), url) as conn:
        datos = informe(consultar(conn), usados_en_codigo())
    texto = json.dumps(datos, ensure_ascii=False, indent=2, default=str)
    print(texto)
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write("## Inventario de la base\n\n```json\n" + texto + "\n```\n")
    graves = datos["alertas"]["tablas_sin_rls"] or datos["alertas"]["permisos_para_anon_o_authenticated"]
    sys.exit(1 if graves else 0)


if __name__ == "__main__":
    main()
