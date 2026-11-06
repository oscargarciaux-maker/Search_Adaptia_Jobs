"""Diagnóstico manual en solo lectura; SQL devuelve solo agregados y fichas públicas acotadas."""
import json
import os
from urllib.parse import parse_qs, urlparse

from buscador import migraciones, supabase, paises


def duplicados(conn):
    from collections import defaultdict
    from buscador import contrato, vacante
    seleccionadas = [r[0] for r in conn.execute("""select snapshot from public.entregas_diarias
        where delivery_date=(select max(delivery_date) from public.entregas_diarias)
        order by selected_at,vacante_id""").fetchall()]
    unicas = vacante.juntar(seleccionadas)
    urls = defaultdict(set)
    for v in unicas:
        for u in [v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])]:
            if u:
                urls[contrato.url_limpia(u)].add(v["id"])
    grupos = defaultdict(list)
    filas = conn.execute("""select id,offer_url from public.ofertas
        where delivery_date=(select max(delivery_date) from public.entregas_diarias) order by id""").fetchall()
    sin_vinculo = 0
    for identificador, u in filas:
        destinos = urls.get(contrato.url_limpia(u), set())
        if len(destinos) == 1:
            grupos[next(iter(destinos))].append(identificador)
        else:
            sin_vinculo += 1
    repetidos = [ids for ids in grupos.values() if len(ids)>1]
    return {"filas_operativas": len(filas), "selecciones_historicas": len(seleccionadas),
        "vacantes_reconocidas": len(unicas), "copias_en_seleccion": len(seleccionadas)-len(unicas),
        "grupos_con_filas_repetidas": len(repetidos), "filas_adicionales": sum(len(x)-1 for x in repetidos),
        "sin_vinculo_inequivoco": sin_vinculo, "muestra_ids": repetidos[:5]}


def consultar(conn, url=""):
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute("set local statement_timeout = '30s'")
        informe = {}
        informe["totales"] = {tabla: conn.execute(f"select count(*) from public.{tabla}").fetchone()[0]
            for tabla in ("ofertas","catalogo_vacantes","entregas_diarias")}
        informe["duplicados"] = duplicados(conn)
        if conn.execute("select to_regclass('public.ofertas_enlaces_historicos')").fetchone()[0]:
            informe["enlaces_archivados"] = conn.execute("select count(*) from public.ofertas_enlaces_historicos").fetchone()[0]
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
            condicion = "public.adaptia_url_identidad(c.datos->>'enlace')=public.adaptia_url_identidad(%s) or public.adaptia_url_identidad(c.datos->>'enlace_directo')=public.adaptia_url_identidad(%s)"
            informe["caso_catalogo"] = conn.execute("""select c.id,c.datos->>'titulo',c.status,c.reason,c.observed_at::text,
                c.datos->'verificacion'->>'estado',c.datos->'verificacion'->>'motivo',
                c.datos->>'ubicacion',c.datos->'paises',c.datos->>'confianza_pais'
                from public.catalogo_vacantes c where """+condicion+" limit 10", (url,url)).fetchall()
            informe["caso_seleccion"] = conn.execute("""select e.vacante_id,e.delivery_date::text,e.role_id,
                e.snapshot->>'titulo',c.datos->>'enlace',c.datos->>'enlace_directo'
                from public.entregas_diarias e join public.catalogo_vacantes c on c.id=e.vacante_id
                where """+condicion+" limit 10", (url,url)).fetchall()
        from collections import Counter
        geografia = Counter()
        muestra = []
        # La descripción se procesa en el runner; el informe solo contiene conteos y una muestra acotada.
        with conn.cursor(name="revision_geografica") as cursor:
            cursor.execute("""select id,datos->>'titulo',datos->>'ubicacion',description_full,datos->>'modalidad'
                from public.catalogo_vacantes where status='active' order by id""")
            for identificador,titulo,ubicacion,descripcion,modalidad in cursor:
                r = paises.elegibles(titulo or '',ubicacion or '',descripcion or '',True if modalidad=='remoto' else None)
                clase = 'fuera_de_cobertura' if not r['paises'] else 'por_confirmar' if r['confianza']=='baja' else 'con_region_identificada'
                geografia[clase] += 1
                if clase=='fuera_de_cobertura' and len(muestra)<5:
                    muestra.append({'id':identificador,'titulo':titulo,'ubicacion':ubicacion})
        informe['revision_geografica'] = {'activas_por_regla':dict(geografia),'muestra_fuera_de_cobertura':muestra}
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
