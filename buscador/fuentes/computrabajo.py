"""Computrabajo: portal donde se postula en el mismo sitio, en 17 países de la región. Sin sesión ni cookies.

Se leen solo rutas permitidas por su robots.txt: la búsqueda `/trabajo-de-<cargo>` (con `?p=` para paginar, sin los
filtros que bloquea) y la ficha `/ofertas-de-trabajo/...`. La publicación sale de `datePosted` (schema.org) de la ficha;
el texto visible suele ser la fecha de actualización («(actualizada)») y esa nunca se toma como publicación.
Como LinkedIn, rota las combinaciones (familia, país) y cada corrida toma las que hace más tiempo no se revisan.
"""
import html
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

from buscador import cobertura

NOMBRE = "Computrabajo"
SITIOS = {"AR": "ar", "BO": "bo", "CL": "cl", "CO": "co", "CR": "cr", "DO": "do", "EC": "ec", "GT": "gt", "HN": "hn",
          "MX": "mx", "NI": "ni", "PA": "pa", "PE": "pe", "PR": "pr", "PY": "py", "SV": "sv", "UY": "uy", "VE": "ve"}
CERRADA = re.compile(r"oferta (ya )?no est[aá] disponible|oferta (ha )?(caducad|finalizad|expirad)|ya no acepta", re.I)


def _texto(fragmento):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento or ""))).strip()


def slug(consulta):
    """«Diseñador UX/UI» → «disenador-ux-ui» (formato de la búsqueda de Computrabajo)."""
    base = unicodedata.normalize("NFKD", consulta).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def fecha_relativa(texto, hoy):
    """«Hace 3 días», «Hace 5 horas», «Ayer», «Hoy» → fecha ISO; «(actualizada)» u otra cosa → ""."""
    t = (texto or "").lower()
    if "actualizad" in t:
        return ""
    base = date.fromisoformat(hoy)
    if "ayer" in t:
        return (base - timedelta(days=1)).isoformat()
    m = re.search(r"hace\s+(\d+)\s+(minuto|hora|d[ií]a|mes)", t)
    if m:
        n, unidad = int(m.group(1)), m.group(2)
        dias = 0 if unidad in ("minuto", "hora") else n if unidad.startswith("d") else 30 * n
        return (base - timedelta(days=dias)).isoformat()
    return base.isoformat() if re.search(r"\bhoy\b|hace\s+(unos\s+)?minutos", t) else ""


def tarjetas(pagina, sitio):
    """Avisos de una página de resultados: título, empresa, ciudad, modalidad, enlace e id."""
    filas = []
    for bloque in re.findall(r'<article class="box_offer[^"]*"[^>]*data-id=\'([0-9A-F]+)\'(.*?)</article>', pagina or "", re.S):
        aviso, cuerpo = bloque
        enlace = re.search(r'<a class="js-o-link[^"]*" href="([^"#]+)', cuerpo)
        titulo = re.search(r'<a class="js-o-link[^"]*"[^>]*>(.*?)</a>', cuerpo, re.S)
        empresa = re.search(r'offer-grid-article-company-url>(.*?)</a>', cuerpo, re.S) or \
            re.search(r'<p class="dFlex[^"]*fs16[^"]*">(.*?)</p>', cuerpo, re.S)
        lugar = re.search(r'<p class="fs16 fc_base mt5">\s*<span class="mr10">(.*?)</span>', cuerpo, re.S)
        modo = re.search(r'i_home_office"></span>(.*?)</span>', cuerpo, re.S)
        if not (enlace and titulo):
            continue
        ruta = enlace.group(1)
        filas.append({"id": aviso, "titulo": _texto(titulo.group(1)), "empresa": _texto(empresa.group(1)) if empresa else "",
                      "ciudad": _texto(lugar.group(1)) if lugar else "", "modalidad": _texto(modo.group(1)) if modo else "",
                      "enlace": ruta if ruta.startswith("http") else f"https://{sitio}.computrabajo.com{ruta}"})
    return filas


def ficha(pagina, hoy):
    """(descripción, fecha de publicación o "", cerrada)."""
    pagina = pagina or ""
    inicio = pagina.find("Descripción de la oferta")
    descripcion = ""
    if inicio >= 0:
        fin = min([i for i in (pagina.find("Palabras clave", inicio), pagina.find("<h2", inicio + 30)) if i > 0] or [inicio + 20000])
        descripcion = _texto(pagina[inicio + len("Descripción de la oferta"):fin].replace("<br", "\n<br"))
    # La publicación está en los datos estructurados de la oferta (schema.org JobPosting.datePosted). El texto visible
    # suele ser la fecha de actualización: solo se usa si no dice «actualizada».
    publicada = re.search(r'"datePosted"\s*:\s*"(\d{4}-\d{2}-\d{2})', pagina)
    fechas = re.findall(r'<p class="fc_aux fs13">\s*([^<]*(?:Hace|Ayer|Hoy)[^<]*)</p>', pagina)
    fecha = publicada.group(1) if publicada and publicada.group(1) <= hoy else \
        fecha_relativa(html.unescape(fechas[-1]) if fechas else "", hoy)
    return descripcion[:30000], fecha, bool(CERRADA.search(pagina))


def modalidad(texto):
    """(remoto para `vacante.crear`, sufijo de ubicación). «Presencial y remoto» es híbrido; no se inventa nada más."""
    t = (texto or "").lower()
    if "presencial y remoto" in t or "híbrido" in t or "hibrido" in t:
        return None, " (Híbrido)"
    if "remoto" in t:
        return True, " (Remoto)"
    if "presencial" in t:
        return None, " (Presencial)"
    return None, ""


def buscar(cliente, mapa, paises_activos, estado, presupuesto, hoy=None, max_fichas=120, reloj=time.monotonic,
           limite_segundos=None, prioritarias=(), max_paginas=2, desfase_terminos=0):
    """Recorre (familia, país) menos recientes hasta gastar el presupuesto de páginas y lee las fichas.
    `paises_activos`: [(código, nombre)]. Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    nombres = dict(paises_activos)
    todas = [(f["id"], cobertura.consultas(f), codigo, {}) for f in mapa
             for codigo in f.get("paises_objetivo", list(nombres)) if codigo in SITIOS]
    todas = cobertura.repartir(todas, estado, hoy, prioritarias)
    avisos, vistos = [], set()
    hechas = fallidas = seguidas = 0
    for familia, consultas, codigo, _ in todas:
        if hechas >= presupuesto or seguidas >= 4 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        consulta = cobertura.rotar(consultas, hoy, 1, desfase=desfase_terminos)[0]
        sitio = SITIOS[codigo]
        for pagina in range(1, max_paginas + 1):
            if hechas >= presupuesto:
                break
            url = f"https://{sitio}.computrabajo.com/trabajo-de-{slug(consulta)}" + (f"?p={pagina}" if pagina > 1 else "")
            r = cliente.get(url)
            hechas += 1
            if r is None or r.status_code != 200:
                fallidas += 1
                seguidas += 1
                break
            seguidas = 0
            filas = tarjetas(r.text, sitio)
            for f in filas:
                if f["id"] not in vistos:
                    vistos.add(f["id"])
                    avisos.append(dict(f, pais=codigo, familia=familia))
            if len(filas) < 20:
                break
        estado[f"{familia}@{codigo}"] = hoy
    avisos.sort(key=lambda a: a["familia"] not in prioritarias)
    crudas, con_ficha, cerradas = [], 0, 0
    for a in avisos:
        descripcion, fecha, cerrada = "", "", False
        if con_ficha < max_fichas and seguidas < 4 and not (limite_segundos and reloj() - inicio > limite_segundos):
            r = cliente.get(a["enlace"])
            if r is not None and r.status_code == 200:
                descripcion, fecha, cerrada = ficha(r.text, hoy)
                con_ficha += 1
                seguidas = 0
            elif r is not None and r.status_code in (403, 429):
                seguidas += 1
        if cerrada:
            cerradas += 1
            continue
        remoto, sufijo = modalidad(a["modalidad"])
        crudas.append({"titulo": a["titulo"], "empresa": a["empresa"],
                       "ubicacion": ", ".join(x for x in (a["ciudad"], nombres.get(a["pais"], a["pais"])) if x) + sufijo,
                       "descripcion": descripcion, "fecha": fecha, "enlace": a["enlace"], "enlace_directo": "",
                       "remoto": remoto, "fuente": NOMBRE})
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), "con_descripcion": con_ficha,
                    "cerradas": cerradas, "combinaciones_total": len(todas)}
