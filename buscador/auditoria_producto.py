"""Diagnóstico manual en solo lectura; SQL devuelve solo agregados y fichas públicas acotadas."""
import json
import os
from urllib.parse import parse_qs, urlparse

from buscador import migraciones, supabase


def consultar(conn, url=""):
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute("set local statement_timeout = '30s'")
        informe = {}
        for tabla, campo in (("ofertas", "search_tag"), ("entregas_diarias", "role_id")):
            # Identificadores constantes internos; nunca provienen del formulario.
            informe[tabla] = conn.execute(f"select delivery_date::text, {campo}, count(*) from public.{tabla} "
                f"where delivery_date=(select max(delivery_date) from public.{tabla}) "
                f"group by delivery_date,{campo} order by {campo}").fetchall()
        informe["qa_seleccionada"] = conn.execute("""select e.vacante_id, e.match_grade,
            e.snapshot->>'titulo', c.status, c.datos->'verificacion'->>'estado'
            from public.entregas_diarias e left join public.catalogo_vacantes c on c.id=e.vacante_id
            where e.role_id='qa' and e.delivery_date=(select max(delivery_date) from public.entregas_diarias)
            order by e.vacante_id limit 20""").fetchall()
        if conn.execute("select to_regclass('public.resumen_entregas_actual')").fetchone()[0]:
            informe["resumen_actual"] = conn.execute("""select role_id,seleccionadas,listas_ahora,
                por_verificar,retiradas,revisar_afinidad from public.resumen_entregas_actual
                where delivery_date=(select max(delivery_date) from public.entregas_diarias)
                order by role_id""").fetchall()
            informe["qa_actual"] = conn.execute("""select vacante_id,job_title,estado_actual
                from public.seleccion_estado_actual where role_id='qa'
                and delivery_date=(select max(delivery_date) from public.entregas_diarias)
                order by estado_actual,job_title limit 20""").fetchall()
            informe["qa_catalogo"] = conn.execute("""select count(*) as en_catalogo,
                count(*) filter(where e.vacante_id is null) as sin_seleccionar
                from public.catalogo_vacantes c left join public.entregas_diarias e on e.vacante_id=c.id
                where c.status='active' and c.datos->>'rol_entrega_actual'='qa'""").fetchone()
        if url:
            p = urlparse(url)
            # Buscar el identificador público de Indeed también entre sus dominios nacionales.
            jk = parse_qs(p.query).get("jk", [""])[0] if (p.hostname or "").endswith(".indeed.com") else ""
            patron = "%jk=" + jk + "%" if jk and jk.isalnum() else url
            informe["caso_ofertas"] = conn.execute("""with objetivo as (
                select job_title,company_name from public.ofertas where offer_url like %s limit 1)
                select o.id,o.external_id,o.job_title,o.status,o.delivery_date::text,o.search_tag,
                       o.source_portal,o.offer_url
                from public.ofertas o join objetivo t using(job_title,company_name)
                order by o.id limit 10""", (patron,)).fetchall()
            informe["caso_catalogo"] = conn.execute("""select id,datos->>'titulo',status,reason,observed_at::text,
                datos->'verificacion'->>'estado',datos->'verificacion'->>'motivo'
                from public.catalogo_vacantes where datos->>'enlace' like %s or datos->>'enlace_directo' like %s
                limit 10""", (patron, patron)).fetchall()
            informe["caso_seleccion"] = conn.execute("""select e.vacante_id,e.delivery_date::text,e.role_id,
                e.snapshot->>'titulo',c.datos->>'enlace',c.datos->>'enlace_directo'
                from public.entregas_diarias e join public.catalogo_vacantes c on c.id=e.vacante_id
                where c.datos->>'enlace' like %s or c.datos->>'enlace_directo' like %s limit 10""",
                (patron, patron)).fetchall()
        return informe


def main():
    try:
        with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""),
                supabase.base(os.environ.get("SUPABASE_URL", ""))) as conn:
            resultado = consultar(conn, os.environ.get("VACANTE_PUBLICA_URL", "").strip()[:2048])
    except Exception:
        print("::error::No se pudo completar la auditoría de solo lectura. Revisar el diagnóstico de conexión; no se muestran detalles privados.")
        raise SystemExit(1) from None
    texto = json.dumps(resultado, ensure_ascii=False, indent=2, default=str)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Auditoría de producto (solo lectura)\n```json\n" + texto.replace("```", "") + "\n```\n")


if __name__ == "__main__":
    main()
