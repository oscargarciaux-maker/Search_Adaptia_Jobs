"""LinkedIn con un actor de Apify sin sesión (solo si existe el secreto APIFY_TOKEN).

El actor recibe enlaces de búsqueda pública de LinkedIn (los mismos que arma linkedin_publico) y devuelve los avisos con su
descripción; Apify se encarga de que LinkedIn no bloquee. Nunca se le da una cookie ni una sesión: un actor que la pida no
se usa. El actor se elige en datos/config.yaml (paso 6 del plan: se prueban dos con las mismas búsquedas).
Los nombres de los campos cambian entre actores; `normalizar_item` acepta los más comunes.
"""
import os
import time
from urllib.parse import urlencode

from buscador import cobertura, enlaces
from buscador.apify import Presupuesto, ejecutar
from buscador.fuentes import linkedin_publico

NOMBRE = "LinkedIn (Apify)"
API = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def url_busqueda(consultas, params, dias):
    q = dict(params, keywords=linkedin_publico.consulta_or(consultas), f_TPR=f"r{dias * 86400}")
    return "https://www.linkedin.com/jobs/search/?" + urlencode(q)


def _valor(item, *claves):
    for clave in claves:
        valor = item
        for parte in clave.split("."):
            valor = valor.get(parte) if isinstance(valor, dict) else None
        if valor not in (None, "", []):
            return valor
    return ""


def _primero(item, *claves):
    valor = _valor(item, *claves)
    if isinstance(valor, dict):
        valor = valor.get("name") or valor.get("text") or ""
    return str(valor) if valor not in (None, "") else ""


def normalizar_item(item):
    enlace = _primero(item, "linkedinUrl", "link", "jobUrl", "url", "jobLink")
    # Nunca convertir posts/perfiles en un enlace de empleo inventado a partir de un id.
    descripcion = _primero(item, "descriptionText", "description", "jobDescription")
    if not descripcion:
        descripcion = linkedin_publico.texto_html(_primero(item, "descriptionHtml"))
    ubicacion = _primero(item, "location.parsed.text", "location.linkedinText", "location.name", "jobLocation", "place")
    if not ubicacion and isinstance(item.get("location"), str):
        ubicacion = item["location"]
    modo = _primero(item, "workplaceType", "workType", "remote").lower()
    return {
        "titulo": _primero(item, "title", "jobTitle", "position"),
        "empresa": _primero(item, "companyName", "company.name", "company_name", "company"),
        "ubicacion": ubicacion,
        "descripcion": descripcion[:30000],
        "fecha": _primero(item, "postedDate", "postedAt", "publishedAt", "listedAt", "datePosted")[:10],
        "enlace": enlace,
        "enlace_directo": _primero(item, "applyMethod.companyApplyUrl", "applyUrl", "applyLink", "externalApplyLink", "companyApplyUrl"),
        "remoto": True if modo == "remote" or _valor(item, "workRemoteAllowed") is True else None,
        "fuente": NOMBRE,
    }


def entrada(actor, consultas, params, dias, maximo):
    if actor != "harvestapi/linkedin-job-search":
        raise ValueError("Actor sin adaptador de entrada verificado; configurar harvestapi/linkedin-job-search")
    cuerpo = {"jobTitles": [linkedin_publico.consulta_or(consultas)], "maxItems": maximo,
              "postedLimit": "24h" if dias <= 1 else "week" if dias <= 7 else "month", "sortBy": "date"}
    if params.get("location") and params["location"] != "Worldwide":
        cuerpo["locations"] = [params["location"]]
    if params.get("f_WT") == "2":
        cuerpo["workplaceType"] = ["remote"]
    return cuerpo


def buscar(cliente, actor, combinaciones, estado, hoy, max_por_busqueda=20, presupuesto=60, max_dias=30,
           token=None, reloj=time.monotonic, limite_segundos=None, prioritarias=(), control_gasto=None,
           tope_consulta_usd=0.025, build="0.0.61"):
    """Ofertas formales: reparto de consultas, esquema real del actor y crédito reservado antes de iniciar."""
    token = token or os.environ.get("APIFY_TOKEN", "")
    if not token or not actor:
        return [], {"omitida": "sin APIFY_TOKEN o sin actor en datos/config.yaml"}
    from datetime import datetime
    inicio = reloj()
    control_gasto = control_gasto or Presupuesto({}, hoy)
    pendientes = cobertura.repartir(combinaciones, estado, hoy, prioritarias)[:presupuesto]
    crudas, ejecuciones, descartes = [], [], {}
    por_familia, por_lugar = {}, {}
    for familia, consultas, lugar, params in pendientes:
        restante = limite_segundos - (reloj() - inicio) if limite_segundos else 180
        if restante <= 1:
            break
        terminos = cobertura.rotar(consultas, hoy, 4)
        clave = f"{familia}@{lugar}"
        ultima = estado.get(cobertura.clave_consulta(clave, terminos))
        dias = max_dias if not ultima else min(max_dias, max(1, (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days + 1))
        # Validar el adaptador antes de reservar dinero.
        cuerpo = entrada(actor, terminos, params, dias, max_por_busqueda)
        cargo = control_gasto.reservar(tope_consulta_usd)
        if not cargo:
            break
        # Dejar margen para el inicio y no pedir más resultados que el crédito de esta ejecución.
        maximo = min(max_por_busqueda, max(1, int((cargo - 0.002) / 0.001)))
        cuerpo["maxItems"] = maximo
        items, stats = ejecutar(cliente, actor, cuerpo, token, cargo, max_items=maximo,
                                build=build, limite_segundos=min(180, restante))
        ejecuciones.append(stats)
        por_familia[familia] = por_familia.get(familia, 0) + 1
        por_lugar[lugar] = por_lugar.get(lugar, 0) + 1
        if stats.get("error"):
            continue
        for item in items:
            motivo = ""
            if not isinstance(item, dict):
                motivo = "registro malformado"
            elif item.get("closedAt") or item.get("jobState", "LISTED") not in ("LISTED", "ACTIVE"):
                motivo = "oferta cerrada o no publicada"
            else:
                v = normalizar_item(item)
                if not v["titulo"] or not v["empresa"] or not enlaces.es_linkedin(v["enlace"]):
                    motivo = "sin título, empresa o enlace formal"
                elif len(v["descripcion"]) < 200:
                    motivo = "sin descripción suficiente"
                else:
                    crudas.append(v)
            if motivo:
                descartes[motivo] = descartes.get(motivo, 0) + 1
        estado[clave] = hoy
        estado[cobertura.clave_consulta(clave, terminos)] = hoy
    resumen = {"busquedas": len(ejecuciones), "avisos": len(crudas), "descartadas": descartes,
                    "por_familia": por_familia, "por_lugar": por_lugar, "ejecuciones": ejecuciones,
                    "reserva_corrida_usd": control_gasto.reservado,
                    "tope_mes_usd": control_gasto.mensual, "tope_diario_usd": round(control_gasto.diario, 6)}
    if not ejecuciones:
        resumen["omitida"] = "presupuesto diario/mensual reservado o tiempo agotado"
    elif any(e.get("error") for e in ejecuciones) and not crudas:
        resumen["error"] = "Apify no produjo ofertas: revisar sus ejecuciones y crédito disponible"
    return crudas, resumen
