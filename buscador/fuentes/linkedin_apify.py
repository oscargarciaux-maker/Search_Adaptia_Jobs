"""LinkedIn con un actor de Apify sin sesión (solo si existe el secreto APIFY_TOKEN).

El actor recibe enlaces de búsqueda pública de LinkedIn (los mismos que arma linkedin_publico) y devuelve los avisos con su
descripción; Apify se encarga de que LinkedIn no bloquee. Nunca se le da una cookie ni una sesión: un actor que la pida no
se usa. El actor se elige en datos/config.yaml (paso 6 del plan: se prueban dos con las mismas búsquedas).
Los nombres de los campos cambian entre actores; `normalizar_item` acepta los más comunes.
"""
import os
import time
from urllib.parse import urlencode

from buscador.fuentes import linkedin_publico

NOMBRE = "LinkedIn (Apify)"
API = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def url_busqueda(consultas, params, dias):
    q = dict(params, keywords=linkedin_publico.consulta_or(consultas), f_TPR=f"r{dias * 86400}")
    return "https://www.linkedin.com/jobs/search/?" + urlencode(q)


def _primero(item, *claves):
    for c in claves:
        v = item.get(c)
        if isinstance(v, dict):
            v = v.get("name") or v.get("url") or ""
        if v:
            return str(v)
    return ""


def normalizar_item(item):
    enlace = _primero(item, "link", "jobUrl", "url", "jobLink", "linkedinUrl")
    if "linkedin.com" in enlace and "/jobs/view/" not in enlace:
        jid = _primero(item, "id", "jobId")
        enlace = f"https://www.linkedin.com/jobs/view/{jid}" if jid else enlace
    return {
        "titulo": _primero(item, "title", "jobTitle", "position"),
        "empresa": _primero(item, "companyName", "company", "company_name"),
        "ubicacion": _primero(item, "location", "jobLocation", "place"),
        "descripcion": _primero(item, "descriptionText", "description", "jobDescription")[:8000],
        "fecha": _primero(item, "postedAt", "publishedAt", "postedDate", "listedAt", "datePosted")[:10],
        "enlace": enlace,
        "enlace_directo": _primero(item, "applyUrl", "applyLink", "externalApplyLink", "companyApplyUrl"),
        "remoto": True if "remote" in _primero(item, "workplaceType", "workType", "remote").lower() else None,
        "fuente": NOMBRE,
    }


def buscar(cliente, actor, combinaciones, estado, hoy, max_por_busqueda=100, presupuesto=60, max_dias=30,
           token=None, reloj=time.monotonic, limite_segundos=None):
    """Corre el actor con las combinaciones menos recientes. Devuelve (vacantes crudas, estadísticas)."""
    token = token or os.environ.get("APIFY_TOKEN", "")
    if not token or not actor:
        return [], {"omitida": "sin APIFY_TOKEN o sin actor en datos/config.yaml"}
    from datetime import datetime
    inicio = reloj()
    pendientes = sorted(combinaciones, key=lambda c: estado.get(f"{c[0]}@{c[2]}", ""))[:presupuesto]
    urls = []
    for familia, consultas, lugar, params in pendientes:
        ultima = estado.get(f"{familia}@{lugar}")
        dias = max_dias if not ultima else min(max_dias, max(1, (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days + 1))
        urls.append(url_busqueda(consultas, params, dias))
    # Se mandan en tandas para que una falla no pierda todo
    crudas, fallidas = [], 0
    for i in range(0, len(urls), 10):
        if limite_segundos and reloj() - inicio > limite_segundos:
            break
        tanda = urls[i:i + 10]
        cuerpo = {"urls": tanda, "startUrls": [{"url": u} for u in tanda], "count": max_por_busqueda,
                  "maxItems": max_por_busqueda * len(tanda), "scrapeCompany": False}
        items = cliente.post_json(API.format(actor=actor.replace("/", "~")) + f"?token={token}", cuerpo, timeout=600)
        if items is None:
            fallidas += 1
            continue
        for item in items if isinstance(items, list) else []:
            v = normalizar_item(item)
            if v["titulo"] and v["enlace"]:
                crudas.append(v)
        for familia, consultas, lugar, params in pendientes[i:i + 10]:
            estado[f"{familia}@{lugar}"] = hoy
    return crudas, {"busquedas": len(urls), "tandas_fallidas": fallidas, "avisos": len(crudas)}
