"""Limpieza única del contrato v12: retira de `ofertas` las vacantes en portugués o solo para Brasil, y las archiva en
el catálogo. Decisión de Oscar (12 nov 2026): solo se entregan vacantes en español o inglés, y Brasil solo dentro de
remotas abiertas a varios países.

Sin `--aplicar` solo simula: cuenta lo que retiraría, por motivo y por día, sin cambiar nada. Con `--aplicar` (el flujo
lo exige junto con la palabra BORRAR y una copia cifrada previa) lo hace en una sola transacción:
- borra esas filas de `ofertas` (la tabla que lee la web del cliente). Se pueden reconstruir: el catálogo y
  `entregas_diarias` conservan la vacante completa, y la copia cifrada guarda la fila tal como estaba;
- pasa esas vacantes del catálogo a `archived` con el motivo, para que no aparezcan en el panel, los mensajes ni la
  estimación. `entregas_diarias` y `panel_asignaciones` (historial privado) no se tocan.
Los registros solo traen conteos: ni títulos, ni empresas, ni enlaces.
"""
import argparse
import json
import os
from collections import Counter

from buscador import contrato, etiquetas, vacante

MOTIVO_IDIOMA = "en portugués"
MOTIVO_PAIS = "solo para Brasil"
RAZON = "contrato v12: idioma o país fuera de la cobertura"


def motivo_catalogo(fila):
    """Motivo por el que una fila del catálogo queda fuera del contrato v12, o ''."""
    datos = dict(fila.get("datos") or {})
    desc = fila.get("description_full") or datos.get("_descripcion") or ""
    titulo = datos.get("titulo") or ""
    if desc and etiquetas.idioma(f"{titulo}\n{desc}") == "pt":
        return MOTIVO_IDIOMA
    guardados = set(datos.get("paises") or [])
    if guardados and guardados <= {"BR"}:
        return MOTIVO_PAIS
    if guardados and "BR" in guardados and titulo:
        # Recalcular con las reglas vigentes: una remota de varios países se conserva; local o «Remoto, Brasil», no.
        actual = vacante.reetiquetar(dict(datos, _descripcion=desc))
        if not actual["paises"] and actual.get("nota_pais") == "país fuera de la cobertura":
            return MOTIVO_PAIS
    return ""


def motivo_oferta(fila):
    """Las filas de `ofertas` dicen su propio alcance: contratar solo en Brasil queda fuera aunque no haya catálogo."""
    valor = fila.get("hire_countries") or []
    paises = {p for p in (valor if isinstance(valor, (list, tuple)) else str(valor).split("|")) if p}
    return MOTIVO_PAIS if paises and paises <= {"BR"} else ""


def planificar(catalogo, ofertas):
    """(ids del catálogo a archivar {id: motivo}, ids de ofertas a borrar {id: motivo}, resumen solo con conteos)."""
    marcadas, enlaces, alias = {}, {}, {}
    for fila in catalogo:
        motivo = fila["motivo"] if "motivo" in fila else motivo_catalogo(fila)
        if not motivo:
            continue
        marcadas[fila["id"]] = motivo
        datos = fila.get("datos") or {}
        for i in [fila["id"], *(datos.get("ids_agrupados") or [])]:
            alias[str(i)] = motivo
        for u in [datos.get("enlace"), datos.get("enlace_directo"), *(datos.get("enlaces_alternativos") or [])]:
            if u:
                enlaces[contrato.url_limpia(u)] = motivo
    borrar = {}
    for o in ofertas:
        motivo = (marcadas.get(o.get("vacante_id") or "") or alias.get(str(o.get("external_id") or ""))
                  or enlaces.get(contrato.url_limpia(o.get("offer_url") or "")) or motivo_oferta(o))
        if motivo:
            borrar[o["id"]] = motivo
    por_dia = Counter(str(o.get("scraped_at") or "")[:10] or "sin fecha" for o in ofertas if o["id"] in borrar)
    resumen = {"catalogo_revisado": len(catalogo), "catalogo_a_archivar": len(marcadas),
               "catalogo_por_motivo": dict(Counter(marcadas.values())),
               "ofertas_revisadas": len(ofertas), "ofertas_a_borrar": len(borrar),
               "ofertas_por_motivo": dict(Counter(borrar.values())), "ofertas_por_dia": dict(sorted(por_dia.items()))}
    return marcadas, borrar, resumen


def leer(conn):
    """El catálogo se lee por tandas y se queda solo con lo necesario (sin descripciones en memoria)."""
    catalogo = []
    with conn.transaction(), conn.cursor(name="limpieza_v12") as cur:
        cur.itersize = 500
        # Todas las filas, también cerradas o archivadas: una vacante ya entregada sigue en `ofertas` aunque haya cerrado.
        cur.execute("select id, datos, description_full from public.catalogo_vacantes")
        for i, d, t in cur:
            fila = {"id": i, "datos": d or {}, "description_full": t or ""}
            motivo = motivo_catalogo(fila)
            datos = fila["datos"]
            catalogo.append({"id": i, "motivo": motivo, "datos": {k: datos.get(k) for k in (
                "ids_agrupados", "enlace", "enlace_directo", "enlaces_alternativos")} if motivo else {}})
    with conn.cursor() as cur:
        cur.execute("select id, external_id, offer_url, vacante_id, hire_countries, scraped_at from public.ofertas")
        columnas = [c.name for c in cur.description]
        ofertas = [dict(zip(columnas, f)) for f in cur]
    return catalogo, ofertas


def aplicar(conn, marcadas, borrar):
    """Una sola transacción: si algo falla, no cambia nada."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0))")
        cur.execute("delete from public.ofertas where id = any(%s)", (list(borrar),))
        borradas = cur.rowcount
        cur.execute("""update public.catalogo_vacantes set status = 'archived', reason = %s
                       where id = any(%s) and status = 'active'""", (RAZON, list(marcadas)))
        archivadas = cur.rowcount
    return {"ofertas_borradas": borradas, "catalogo_archivado": archivadas}


def correr(conn, aplicar_cambios=False):
    catalogo, ofertas = leer(conn)
    marcadas, borrar, resumen = planificar(catalogo, ofertas)
    resumen["modo"] = "aplicado" if aplicar_cambios else "simulación (no se cambió nada)"
    if aplicar_cambios:
        resumen.update(aplicar(conn, marcadas, borrar))
    return resumen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="Borra y archiva; sin esto solo simula")
    p.add_argument("--confirmar", default="", help="Debe ser BORRAR junto con --aplicar")
    a = p.parse_args()
    if a.aplicar and a.confirmar != "BORRAR":
        raise SystemExit("Para aplicar escribe BORRAR en «confirmar». No se cambió nada.")
    from buscador.migraciones import conexion
    with conexion(os.environ.get("SUPABASE_DB_URL", ""), os.environ.get("SUPABASE_URL", "")) as conn:
        resumen = correr(conn, a.aplicar)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write("## Limpieza de portugués y Brasil (contrato v12)\n\n```json\n"
                    + json.dumps(resumen, ensure_ascii=False, indent=2) + "\n```\n")


if __name__ == "__main__":
    main()
