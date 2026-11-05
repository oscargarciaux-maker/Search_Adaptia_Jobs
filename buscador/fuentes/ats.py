"""Portales de empleo de las empresas (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee): API públicas,
gratis, y todo lo que publican está abierto y es el aviso original.

La lista de empresas (`datos/empresas_ats.csv`) crece sola: cada noche se prueban, en cada sistema, los nombres de las
empresas que trajeron las demás fuentes (LinkedIn, Indeed, tableros remotos) y las que descubre Brave. Las que tienen
portal quedan en la lista y se leen todas las noches.
"""
import csv
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from requests import RequestException
from urllib3.exceptions import HTTPError

from buscador import familias, normalizar

NOMBRE = "Portales de empresas"
RUTA = Path(__file__).resolve().parent.parent.parent / "datos" / "empresas_ats.csv"   # lista inicial (en main)
CAMPOS = ["empresa", "sistema", "slug", "origen", "agregada"]
SISTEMAS = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters", "recruitee"]


def url_api(sistema, slug):
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
        "lever": f"https://api.lever.co/v0/postings/{slug}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "workable": f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
        "smartrecruiters": f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100",
        "recruitee": f"https://{slug}.recruitee.com/api/offers/",
    }[sistema]


def tiene_forma(sistema, datos):
    """true si la respuesta es un tablero de ese sistema con al menos una vacante (algunos responden 200 vacío)."""
    if sistema == "lever":
        return isinstance(datos, list) and len(datos) > 0
    if sistema == "smartrecruiters":
        return isinstance(datos, dict) and datos.get("totalFound", 0) > 0
    if sistema == "recruitee":
        return isinstance(datos, dict) and len(datos.get("offers") or []) > 0
    return isinstance(datos, dict) and len(datos.get("jobs") or []) > 0


def respuesta_valida(sistema, datos):
    if sistema == "lever":
        return isinstance(datos, list)
    campo = {"smartrecruiters": "content", "recruitee": "offers"}.get(sistema, "jobs")
    return isinstance(datos, dict) and isinstance(datos.get(campo), list)


def slugs_para(nombre):
    """Nombres de tablero a probar para una empresa: 'Mercado Libre' → mercadolibre, mercado-libre."""
    base = normalizar.empresa(nombre)
    base = re.sub(r"\b(colombia|mexico|brasil|brazil|argentina|chile|peru|latam|latin america|technologies|technology|"
                  r"tech|labs|digital|software|solutions|services|global|holdings)\b", " ", base).strip()
    salida = []
    for s in (base.replace(" ", ""), base.replace(" ", "-")):
        if len(s) > 2 and s not in salida:
            salida.append(s)
    return salida


def _dia(valor):
    if not valor:
        return ""
    try:
        if isinstance(valor, (int, float)):
            return datetime.fromtimestamp(valor / 1000 if valor > 1e11 else valor, tz=timezone.utc).date().isoformat()
        return str(valor)[:10]
    except (ValueError, OSError):
        return ""


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", normalizar_html(html))).strip()


def normalizar_html(html):
    import html as h
    return h.unescape(h.unescape(str(html or "")))


def vacantes_de(sistema, datos, empresa, slug):
    """Vacantes crudas del tablero de una empresa."""
    base = {"empresa": empresa, "fuente": f"{NOMBRE} ({sistema})"}
    salida = []
    if sistema == "greenhouse":
        for j in datos.get("jobs") or []:
            salida.append(dict(base, titulo=j.get("title", ""), ubicacion=(j.get("location") or {}).get("name", ""),
                               enlace=j.get("absolute_url", ""), fecha=_dia(j.get("first_published")),
                               publicada_en=j.get("first_published", ""), fecha_origen="first_published",
                               descripcion=_texto(j.get("content"))[:30000], remoto=None))
    elif sistema == "lever":
        for j in datos:
            cat = j.get("categories") or {}
            contenido = [j.get("descriptionPlain") or _texto(j.get("description"))]
            for lista in j.get("lists") or []:
                contenido += [_texto(lista.get("text")), _texto(lista.get("content"))]
            contenido += [_texto(j.get("additionalPlain") or j.get("additional"))]
            salida.append(dict(base, titulo=j.get("text", ""),
                               ubicacion=" ".join(x for x in [cat.get("location", ""), " ".join(cat.get("allLocations") or [])] if x),
                               enlace=j.get("hostedUrl", ""), fecha=_dia(j.get("createdAt")),
                               publicada_en=j.get("createdAt", ""),
                               descripcion="\n".join(x for x in contenido if x)[:30000],
                               remoto=True if (j.get("workplaceType") == "remote") else None))
    elif sistema == "ashby":
        for j in datos.get("jobs") or []:
            if j.get("isListed") is False:
                continue
            lugares = [j.get("location") or ""] + [x.get("location", "") for x in j.get("secondaryLocations") or []]
            salida.append(dict(base, titulo=j.get("title", ""), ubicacion=", ".join(x for x in lugares if x),
                               enlace=j.get("jobUrl", ""), fecha=_dia(j.get("publishedAt")),
                               publicada_en=j.get("publishedAt", ""),
                               descripcion=(j.get("descriptionPlain") or _texto(j.get("descriptionHtml")))[:30000],
                               remoto=True if j.get("isRemote") else None))
    elif sistema == "workable":
        for j in datos.get("jobs") or []:
            salida.append(dict(base, titulo=j.get("title", ""),
                               ubicacion=", ".join(x for x in [j.get("city"), j.get("state"), j.get("country")] if x),
                               enlace=j.get("url") or j.get("shortlink") or "", fecha=_dia(j.get("published_on") or j.get("created_at")),
                               publicada_en=j.get("published_on") or j.get("created_at", ""),
                               descripcion="", _detalle=j.get("shortcode", ""),
                               remoto=True if j.get("telecommuting") else None))
    elif sistema == "smartrecruiters":
        for j in datos.get("content") or []:
            loc = j.get("location") or {}
            salida.append(dict(base, titulo=j.get("name", ""),
                               ubicacion=", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                               enlace=f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}", fecha=_dia(j.get("releasedDate")),
                               publicada_en=j.get("releasedDate", ""),
                               descripcion="", _detalle=j.get("id", ""), remoto=True if loc.get("remote") else None))
    elif sistema == "recruitee":
        for j in datos.get("offers") or []:
            salida.append(dict(base, titulo=j.get("title", ""), ubicacion=j.get("location", ""),
                               enlace=j.get("careers_url", ""), fecha=_dia(j.get("published_at")),
                               publicada_en=j.get("published_at", ""),
                               descripcion=_texto(j.get("description"))[:30000], remoto=True if j.get("remote") else None))
    return [v for v in salida if v["titulo"] and v["enlace"]]


def leer_lista(*rutas):
    """Tableros conocidos: la lista inicial del repositorio más los que la bodega descubrió (sin repetir)."""
    filas = {}
    for ruta in rutas or (RUTA,):
        ruta = Path(ruta)
        if not ruta.exists():
            continue
        with open(ruta, encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                if fila.get("slug") and fila.get("sistema"):
                    filas.setdefault((fila["sistema"], fila["slug"]), fila)
    return list(filas.values())


def guardar_lista(filas, ruta=RUTA):
    filas = sorted({(f["sistema"], f["slug"]): f for f in filas}.values(), key=lambda f: (f["empresa"].lower(), f["sistema"]))
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for fila in filas:
            w.writerow({k: fila.get(k, "") for k in CAMPOS})


def probar(cliente, nombre, bloqueados):
    """Primer tablero con vacantes para una empresa, o None. `bloqueados`: sistemas que respondieron 429 en esta corrida
    (no se insiste: Workable limita mucho las consultas)."""
    for slug in slugs_para(nombre):
        for sistema in SISTEMAS:
            if sistema in bloqueados:
                continue
            # Recruitee usa el identificador como etiqueta DNS; los demás lo llevan en la ruta.
            # No truncar: se consultaría el tablero de una empresa distinta.
            if sistema == "recruitee" and not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", slug, re.I):
                continue
            try:
                r = cliente.get(url_api(sistema, slug), reintentar_429=False, pausar=False)
            except (RequestException, HTTPError, ValueError) as e:
                logging.getLogger(__name__).warning("Candidato de %s omitido por %s; se continúa el descubrimiento",
                                                    sistema, type(e).__name__)
                continue
            if r is None:
                continue
            if r.status_code == 429:
                bloqueados.add(sistema)
                continue
            if r.status_code != 200:
                continue
            try:
                datos = r.json()
            except ValueError:
                continue
            if tiene_forma(sistema, datos):
                return {"empresa": nombre.strip(), "sistema": sistema, "slug": slug}
    return None


def descubrir(cliente, nombres, estado, maximo, hoy, conocidas_filas, origen="otras fuentes", reprobar_dias=30, hilos=8):
    """Prueba los nombres de empresas en cada sistema; devuelve (filas nuevas con portal, empresas probadas).
    estado: {empresa normalizada: fecha de la última prueba}; no se vuelve a probar antes de `reprobar_dias`."""
    from concurrent.futures import ThreadPoolExecutor
    conocidas = {normalizar.empresa(f["empresa"]) for f in conocidas_filas}
    por_probar, vistas = [], set()
    for nombre in nombres:
        clave = normalizar.empresa(nombre)
        if not clave or clave in conocidas or clave in vistas or len(clave) < 3:
            continue
        ultima = estado.get(clave)
        if ultima and (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days < reprobar_dias:
            continue
        vistas.add(clave)
        por_probar.append(nombre)
        if len(por_probar) >= maximo:
            break
    bloqueados = set()
    with ThreadPoolExecutor(hilos) as ex:
        hallados = list(ex.map(lambda n: probar(cliente, n, bloqueados), por_probar))
    for nombre in por_probar:
        estado[normalizar.empresa(nombre)] = hoy
    nuevas = [dict(h, origen=origen, agregada=hoy) for h in hallados if h]
    return nuevas, len(por_probar)


def _tablero_completo(cliente, sistema, slug, plazo=None):
    datos = cliente.json(url_api(sistema, slug), pausar=False)
    if sistema != "smartrecruiters" or not isinstance(datos, dict):
        return datos
    # No declarar cerradas ofertas que simplemente están fuera de la primera página.
    contenido = list(datos.get("content") or [])
    total = datos.get("totalFound", len(contenido))
    while len(contenido) < total:
        if plazo and time.monotonic() >= plazo:
            return None
        pagina = cliente.json(url_api(sistema, slug) + f"&offset={len(contenido)}", pausar=False)
        nuevos = (pagina or {}).get("content") or []
        if not nuevos or {j.get("id") for j in nuevos} <= {j.get("id") for j in contenido}:
            return None  # lectura parcial: no es evidencia de cierre
        contenido.extend(nuevos)
    return dict(datos, content=contenido)


def _completar(cliente, sistema, slug, v):
    identificador = v.get("_detalle")
    if not identificador:
        return False
    if sistema == "smartrecruiters":
        url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{identificador}"
    else:
        url = f"https://apply.workable.com/api/v2/accounts/{slug}/jobs/{identificador}"
    detalle = cliente.json(url, pausar=False)
    if not isinstance(detalle, dict):
        return False
    if sistema == "smartrecruiters":
        secciones = (detalle.get("jobAd") or {}).get("sections") or {}
        texto = "\n".join(_texto(s.get("text")) for s in secciones.values() if isinstance(s, dict))
    else:
        texto = "\n".join(_texto(detalle.get(k)) for k in ("description", "requirements", "benefits"))
    if texto.strip():
        v["descripcion"] = texto[:30000]
    return len(v["descripcion"]) >= 200


def buscar(cliente, filas, max_tableros=None, limite_segundos=None, max_detalles=450, prioritarias=()):
    """Lee todos los tableros conocidos. Devuelve (vacantes crudas, tableros leídos {(sistema, slug)}, estadísticas)."""
    crudas, fallidos, leidos = [], 0, set()
    inicio = time.monotonic()
    detalles = completadas = 0
    prioritarias = set(prioritarias)
    pendientes_por_empresa = {}
    for fila in filas:
        pendientes_por_empresa[fila["empresa"]] = pendientes_por_empresa.get(fila["empresa"], 0) + 1
    for fila in filas[:max_tableros] if max_tableros else filas:
        if limite_segundos and time.monotonic() - inicio >= limite_segundos:
            break
        try:
            datos = _tablero_completo(cliente, fila["sistema"], fila["slug"],
                                      inicio + limite_segundos if limite_segundos else None)
            if not respuesta_valida(fila["sistema"], datos):
                fallidos += 1
                continue
            nuevas = vacantes_de(fila["sistema"], datos, fila["empresa"], fila["slug"])
            crudas.extend(nuevas)
            pendientes_por_empresa[fila["empresa"]] -= 1
            if pendientes_por_empresa[fila["empresa"]] == 0:
                leidos.add(fila["empresa"])
        except (AttributeError, TypeError):
            fallidos += 1
    candidatas = [v for v in crudas if v.get("_detalle")]
    candidatas.sort(key=lambda v: (not bool(prioritarias & {f["familia"] for f in familias.clasificar(v["titulo"])}),
                                    v.get("remoto") is not True))
    for v in candidatas:
        if detalles >= max_detalles or (limite_segundos and time.monotonic() - inicio >= limite_segundos):
            break
        # Detalles solo para cargos del mapa; la lista general se conserva para descubrir otros títulos.
        if not familias.clasificar(v["titulo"]):
            continue
        sistema = "smartrecruiters" if "smartrecruiters.com" in v["enlace"] else "workable"
        slug = next((f["slug"] for f in filas if f["empresa"] == v["empresa"] and f["sistema"] == sistema), "")
        detalles += 1
        completadas += bool(_completar(cliente, sistema, slug, v))
    return crudas, leidos, {"tableros": len(filas), "fallidos": fallidos, "avisos": len(crudas),
                            "detalles_consultados": detalles, "descripciones_completadas": completadas}
