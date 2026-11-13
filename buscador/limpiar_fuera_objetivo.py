"""Revisión y limpieza de `ofertas` contra el objetivo (contrato v13): vacantes que una persona de LATAM o España puede
aprovechar, escritas en español o inglés. Incluye y amplía la limpieza del contrato v12 (portugués y solo Brasil).

Cada fila de `ofertas` se vuelve a juzgar con las reglas vigentes (`vacante.reetiquetar`, `paises.elegibles`) usando la
vacante completa del catálogo; si no hay catálogo, con la propia fila (título, ubicación, modalidad, idioma):
- **borrar**: idioma distinto de español o inglés; presencial o híbrida fuera de LATAM y España; remota solo para
  otros países (incluido «solo Brasil»).
- **revisar**: la ubicación no se puede confirmar. No se borra salvo que el operador lo pida por su número.
- el resto se conserva y no aparece en el listado.

Sin `--aplicar` solo escribe el listado (`revision.html` y `revision.csv`) y una huella de lo propuesto; no cambia nada.
Con `--aplicar` exige la huella del listado revisado (si los datos cambiaron, hay que volver a revisar), admite números
a conservar y números de «revisar» a borrar, y en una sola transacción borra esas filas de `ofertas` y archiva sus
vacantes activas en el catálogo. `entregas_diarias` y `panel_asignaciones` (historial privado) no se tocan.
El listado lleva solo datos públicos de los avisos (título, empresa, ubicación, enlace), nunca datos de clientes.
"""
import argparse
import csv
import hashlib
import html
import json
import os
import re
from collections import Counter
from pathlib import Path

from buscador import paises, vacante

BORRAR, REVISAR = "borrar", "revisar"
IDIOMAS = {"pt": "portugués", "fr": "francés", "de": "alemán", "it": "italiano"}
RAZON = "contrato v13: fuera del objetivo (idioma o país)"
MODOS_OFERTA = {"remote": True, "remoto": True}


def _motivo_lugar(v):
    """Motivo de país, o '' si se puede aplicar desde LATAM o España. `v` ya recalculada."""
    if v.get("paises"):
        return ""
    if v.get("confianza_pais") not in ("alta", "media"):
        return ""
    nota = v.get("nota_pais") or ""
    if nota == "país fuera de la cobertura":
        return "solo para Brasil" if v.get("modalidad") == "remoto" else "presencial o híbrida en Brasil"
    if v.get("modalidad") == "remoto":
        return "remota solo para otros países"
    return "presencial o híbrida fuera de LATAM y España"


def decidir(datos=None, descripcion="", oferta=None):
    """(decisión, motivo): ('borrar'|'revisar'|'', texto). Usa la vacante del catálogo si existe; si no, la fila."""
    oferta = oferta or {}
    if datos and datos.get("titulo"):
        v = vacante.reetiquetar(dict(datos, _descripcion=descripcion or ""))
        idioma = v.get("idioma") if descripcion else datos.get("idioma")
    else:
        titulo = oferta.get("job_title") or ""
        r = paises.elegibles(titulo, oferta.get("location") or "", "", MODOS_OFERTA.get(oferta.get("work_mode")))
        v = {"paises": r["paises"], "confianza_pais": r["confianza"], "nota_pais": r["nota"], "modalidad": r["modalidad"]}
        idioma = oferta.get("posting_language") or ""
    if idioma in IDIOMAS:
        return BORRAR, "escrita en " + IDIOMAS[idioma]
    motivo = _motivo_lugar(v)
    if motivo:
        return BORRAR, motivo
    if v.get("confianza_pais") == "baja" or not v.get("paises"):
        return REVISAR, "ubicación sin confirmar"
    return "", ""


def planificar(catalogo, ofertas):
    """Listado de filas de `ofertas` a borrar o revisar, con los datos públicos para revisarlas."""
    por_id = {fila["id"]: fila for fila in catalogo}
    por_alias = {}
    for fila in catalogo:
        for i in (fila.get("datos") or {}).get("ids_agrupados") or []:
            por_alias.setdefault(str(i), fila)
    filas = []
    for o in ofertas:
        fila = por_id.get(o.get("vacante_id") or "") or por_alias.get(str(o.get("external_id") or ""))
        datos = (fila or {}).get("datos") or {}
        decision, motivo = decidir(datos, (fila or {}).get("description_full") or "", o)
        if not decision:
            continue
        filas.append({"numero": o["id"], "decision": decision, "motivo": motivo,
                      "titulo": datos.get("titulo") or o.get("job_title") or "",
                      "empresa": datos.get("empresa") or o.get("company_name") or "",
                      "ubicacion": datos.get("ubicacion") or o.get("location") or "",
                      "modalidad": datos.get("modalidad") or o.get("work_mode") or "",
                      "entregada": str(o.get("scraped_at") or "")[:10], "enlace": o.get("offer_url") or "",
                      "vacante_id": (fila or {}).get("id") or o.get("vacante_id") or ""})
    filas.sort(key=lambda f: (f["decision"] != BORRAR, f["motivo"], f["entregada"], f["numero"]))
    return filas


def huella(filas):
    """Código corto de la lista propuesta: si cambia, lo revisado ya no es lo mismo que se borraría."""
    ids = sorted(f["numero"] for f in filas if f["decision"] == BORRAR)
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:10]


def resumen(filas, revisadas):
    return {"ofertas_revisadas": revisadas, "propuestas_para_borrar": sum(f["decision"] == BORRAR for f in filas),
            "para_revisar_a_mano": sum(f["decision"] == REVISAR for f in filas),
            "por_motivo": dict(Counter(f["motivo"] for f in filas)), "huella": huella(filas)}


def escribir_listado(filas, datos_resumen, carpeta):
    """revision.csv (para abrir en una hoja de cálculo) y revision.html (para leer con enlaces)."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    columnas = ["numero", "decision", "motivo", "titulo", "empresa", "ubicacion", "modalidad", "entregada", "enlace"]
    with open(carpeta / "revision.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    e = html.escape
    secciones = []
    for decision, titulo, ayuda in ((BORRAR, "Propuestas para borrar", "Se borran al aplicar, salvo los números que escribas en «conservar»."),
                                    (REVISAR, "Para revisar a mano", "No se borran, salvo los números que escribas en «borrar_tambien».")):
        grupo = [f for f in filas if f["decision"] == decision]
        cuerpo = "".join(
            f"<tr><td>{f['numero']}</td><td>{e(f['motivo'])}</td><td>{e(f['titulo'])}</td><td>{e(f['empresa'])}</td>"
            f"<td>{e(f['ubicacion'])}</td><td>{e(f['modalidad'])}</td><td>{e(f['entregada'])}</td>"
            + (f"<td><a href=\"{e(f['enlace'])}\" target=\"_blank\" rel=\"noopener noreferrer\">abrir</a></td></tr>"
               if f["enlace"].startswith(("http://", "https://")) else "<td>—</td></tr>")
            for f in grupo)
        secciones.append(f"<h2>{titulo} ({len(grupo)})</h2><p>{ayuda}</p><table><thead><tr><th>Número</th><th>Motivo</th>"
                         f"<th>Cargo</th><th>Empresa</th><th>Ubicación</th><th>Modalidad</th><th>Entregada</th>"
                         f"<th>Aviso</th></tr></thead><tbody>{cuerpo}</tbody></table>")
    motivos = "".join(f"<li>{e(m)}: {n}</li>" for m, n in datos_resumen["por_motivo"].items())
    pagina = (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
        "content=\"width=device-width, initial-scale=1\"><title>Revisión de vacantes</title><style>"
        "body{font-family:system-ui,sans-serif;margin:24px;color:#1e3028;background:#fff}table{border-collapse:collapse;"
        "width:100%;font-size:14px}th,td{border-bottom:1px solid #d8e0dc;padding:6px 8px;text-align:left;vertical-align:top}"
        "th{background:#eef3f0;position:sticky;top:0}code{background:#eef3f0;padding:2px 6px;border-radius:4px}</style>"
        "</head><body><h1>Revisión de vacantes fuera del objetivo</h1>"
        f"<p>Revisadas: {datos_resumen['ofertas_revisadas']} vacantes de la tabla de ofertas. Huella de esta lista: "
        f"<code>{e(datos_resumen['huella'])}</code> (cópiala en «huella» al aplicar).</p><ul>{motivos}</ul>"
        + "".join(secciones) + "</body></html>")
    (carpeta / "revision.html").write_text(pagina, encoding="utf-8")


def _numeros(texto):
    return {int(n) for n in re.findall(r"\d+", texto or "")}


def elegir(filas, huella_revisada, conservar="", borrar_tambien=""):
    """Números de `ofertas` a borrar tras la revisión. Falla con un mensaje claro si algo no cuadra."""
    actual = huella(filas)
    if (huella_revisada or "").strip() != actual:
        raise SystemExit(f"La huella no coincide ({huella_revisada or 'vacía'} ≠ {actual}): los datos cambiaron o se "
                         "copió mal. Vuelve a lanzar la revisión sin «aplicar», revisa el listado nuevo y usa su huella. "
                         "No se cambió nada.")
    propuestas = {f["numero"] for f in filas if f["decision"] == BORRAR}
    a_revisar = {f["numero"] for f in filas if f["decision"] == REVISAR}
    conservar, extra = _numeros(conservar), _numeros(borrar_tambien)
    if conservar - propuestas:
        raise SystemExit(f"En «conservar» hay números que no están entre las propuestas: {sorted(conservar - propuestas)}. "
                         "No se cambió nada.")
    if extra - a_revisar - propuestas:  # un número de las propuestas aquí no estorba: ya se iba a borrar
        raise SystemExit(f"En «borrar_tambien» hay números que no están en el listado: {sorted(extra - a_revisar - propuestas)}. "
                         "No se cambió nada.")
    if conservar & extra:
        raise SystemExit(f"Estos números están a la vez en «conservar» y en «borrar_tambien»: {sorted(conservar & extra)}. "
                         "No se cambió nada.")
    return (propuestas - conservar) | extra


def leer(conn):
    catalogo = []
    with conn.transaction(), conn.cursor(name="revision_v13") as cur:
        cur.itersize = 500
        # Solo las vacantes que están en `ofertas` (por su id o por un id agrupado; índice GIN de SQL 005).
        cur.execute("""select c.id, c.datos, c.description_full from public.catalogo_vacantes c
                       where c.id in (select vacante_id from public.ofertas where vacante_id is not null)
                          or c.datos->'ids_agrupados' ?| (select coalesce(array_agg(external_id), '{}')
                                                         from public.ofertas)""")
        for i, d, t in cur:
            catalogo.append({"id": i, "datos": d or {}, "description_full": t or ""})
    with conn.cursor() as cur:
        cur.execute("""select id, external_id, offer_url, vacante_id, job_title, company_name, location, work_mode,
                              posting_language, scraped_at from public.ofertas""")
        columnas = [c.name for c in cur.description]
        ofertas = [dict(zip(columnas, f)) for f in cur]
    return catalogo, ofertas


def aplicar(conn, filas, numeros):
    vacantes = sorted({f["vacante_id"] for f in filas if f["numero"] in numeros and f["vacante_id"]})
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0))")
        cur.execute("delete from public.ofertas where id = any(%s)", (sorted(numeros),))
        borradas = cur.rowcount
        cur.execute("update public.catalogo_vacantes set status = 'archived', reason = %s "
                    "where id = any(%s) and status = 'active'", (RAZON, vacantes))
        archivadas = cur.rowcount
    return {"ofertas_borradas": borradas, "catalogo_archivado": archivadas}


def _cargar_reglas(conn):
    """Contrato v17: las reglas de ubicación del operador y aprendidas también cuentan al revisar `ofertas`."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("select texto, resultado, origen, activa from public.panel_reglas_ubicacion")
            paises.cargar_reglas([{"texto": t, "resultado": r, "origen": o, "activa": a} for t, r, o, a in cur])
    except Exception:  # noqa: BLE001 — sin la tabla (instalaciones anteriores a SQL 014) se revisa sin reglas
        paises.cargar_reglas()


def correr(conn, carpeta="revision", aplicar_cambios=False, huella_revisada="", conservar="", borrar_tambien=""):
    _cargar_reglas(conn)
    try:
        return _correr(conn, carpeta, aplicar_cambios, huella_revisada, conservar, borrar_tambien)
    finally:
        paises.cargar_reglas()


def _correr(conn, carpeta, aplicar_cambios, huella_revisada, conservar, borrar_tambien):
    catalogo, ofertas = leer(conn)
    filas = planificar(catalogo, ofertas)
    datos_resumen = resumen(filas, len(ofertas))
    escribir_listado(filas, datos_resumen, carpeta)
    datos_resumen["modo"] = "revisión (no se cambió nada)"
    if aplicar_cambios:
        numeros = elegir(filas, huella_revisada, conservar, borrar_tambien)
        datos_resumen.update(aplicar(conn, filas, numeros), modo="aplicado",
                             conservadas_a_pedido=len(_numeros(conservar)),
                             borradas_de_revisar=len(_numeros(borrar_tambien)))
    return datos_resumen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--confirmar", default="")
    p.add_argument("--huella", default="")
    p.add_argument("--conservar", default="")
    p.add_argument("--borrar-tambien", default="")
    p.add_argument("--carpeta", default="revision")
    a = p.parse_args()
    if a.aplicar and a.confirmar != "BORRAR":
        raise SystemExit("Para aplicar escribe BORRAR en «confirmar». No se cambió nada.")
    aviso = ""
    if not a.aplicar and (a.huella or a.conservar or a.borrar_tambien or a.confirmar):
        aviso = ("Escribiste datos para borrar pero NO marcaste la casilla «aplicar»: esta ejecución solo revisó y no "
                 "borró nada. Para borrar, vuelve a lanzarla marcando «aplicar».")
    from buscador.migraciones import conexion
    with conexion(os.environ.get("SUPABASE_DB_URL", ""), os.environ.get("SUPABASE_URL", "")) as conn:
        datos_resumen = correr(conn, a.carpeta, a.aplicar, a.huella, a.conservar, a.borrar_tambien)
    if aviso:
        print("AVISO:", aviso)
    print(json.dumps(datos_resumen, ensure_ascii=False, indent=2))
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(("> ⚠️ **" + aviso + "**\n\n" if aviso else "") + "## Vacantes fuera del objetivo\n\n"
                    f"- Modo: **{datos_resumen['modo']}**\n"
                    f"- Propuestas para borrar: **{datos_resumen['propuestas_para_borrar']}**\n"
                    f"- Para revisar a mano: **{datos_resumen['para_revisar_a_mano']}**\n"
                    f"- Huella de esta lista: `{datos_resumen['huella']}`\n\n"
                    "El listado completo está abajo, en **Artifacts → listado-para-revisar** (abre `revision.html`).\n\n"
                    "```json\n" + json.dumps(datos_resumen, ensure_ascii=False, indent=2) + "\n```\n")


if __name__ == "__main__":
    main()
