"""LinkedIn: buscador público de empleos (sin sesión, sin cookie).

Cada familia del mapa se busca en cada país y en remoto para LATAM, con sus consultas unidas por OR (LinkedIn lo acepta:
probado el 28 oct 2026). Hay más combinaciones que las que caben en una noche sin que LinkedIn bloquee, así que cada
corrida toma las combinaciones que hace más tiempo no se revisan y les pide los avisos desde la última revisión
(entre 1 y 30 días). En unos días se cubre todo, y la bodega guarda 30 días.
"""
import html
import re
import time
from datetime import datetime, timedelta, timezone

from buscador import cobertura, enlaces

NOMBRE = "LinkedIn"
BUSQUEDA = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
AVISO = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
CERRADO = re.compile(r"No longer accepting applications|Ya no se aceptan solicitudes|closed-job", re.I)
# Lugares de búsqueda además de cada país: remoto para toda la región
LUGARES_EXTRA = [("LATAM", {"location": "Latin America"}), ("REMOTO", {"location": "Latin America", "f_WT": "2"}),
                 ("REMOTO_MUNDO", {"location": "Worldwide", "f_WT": "2"}),
                 ("REMOTO_ES", {"location": "Spain", "f_WT": "2"})]


def texto_html(fragmento):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento or ""))).strip()


def tarjetas(pagina):
    """Avisos de una página de resultados: título, empresa, ubicación, fecha, enlace e id."""
    filas = []
    for tarjeta in re.split(r"<li[\s>]", pagina or ""):
        aviso = re.search(r"urn:li:jobPosting:(\d+)", tarjeta)
        if not aviso:
            continue

        def campo(patron):
            m = re.search(patron, tarjeta)
            return texto_html(m.group(1)) if m else ""

        fecha = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', tarjeta)
        filas.append({
            "id": aviso.group(1),
            "titulo": campo(r"base-search-card__title[^>]*>([\s\S]*?)</h3>"),
            "empresa": campo(r"base-search-card__subtitle[^>]*>([\s\S]*?)</h4>"),
            "ubicacion": campo(r"job-search-card__location[^>]*>([\s\S]*?)</span>"),
            "fecha": fecha.group(1) if fecha else "",
            "enlace": "https://www.linkedin.com/jobs/view/" + aviso.group(1),
        })
    return filas


def ficha(pagina):
    """(descripción completa, si ya no recibe postulaciones, enlace externo, remoto) de la página pública del aviso."""
    marca = re.search(r"show-more-less-html__markup[^>]*>([\s\S]*?)</div>", pagina or "")
    descripcion = texto_html(marca.group(1).replace("<br>", "\n").replace("</li>", "\n")) if marca else ""
    # El enlace externo de postulación está detrás del inicio de sesión: el directo sale al juntar con la copia del
    # portal de la empresa. La modalidad remota sale de la búsqueda (filtro remoto) o de la descripción.
    return descripcion, bool(CERRADO.search(pagina or "")), "", None


def combinaciones(mapa, paises_activos):
    """Todas las combinaciones (familia, lugar) que se pueden buscar."""
    lugares = [(p, {"location": nombre}) for p, nombre in paises_activos] + LUGARES_EXTRA
    return [(f["id"], cobertura.consultas(f), clave, params) for f in mapa for clave, params in f.get("lugares", lugares)]


def consulta_or(consultas, maximo=4):
    """Las primeras consultas de la familia unidas por OR, entre comillas."""
    return " OR ".join(f'"{c}"' for c in consultas[:maximo])



def buscar(cliente, mapa, paises_activos, estado, presupuesto, hoy=None, max_fichas=250, max_dias=30,
           reloj=time.monotonic, limite_segundos=None, prioritarias=(), desfase_terminos=0, max_paginas=3):
    """Recorre las combinaciones menos recientes hasta gastar el presupuesto de búsquedas.
    estado: dict {clave_combinacion: fecha ISO de la última revisión}; se actualiza aquí.
    Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    todas = combinaciones(mapa, paises_activos)
    todas = cobertura.repartir(todas, estado, hoy, prioritarias)
    vistos, avisos = set(), []
    hechas = fallidas = seguidas = 0
    por_familia, por_lugar = {}, {}
    for familia, consultas, lugar, params in todas:
        if hechas >= presupuesto or seguidas >= 4 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        clave = f"{familia}@{lugar}"
        terminos = cobertura.rotar(consultas, hoy, 4, desfase=desfase_terminos)
        clave_terminos = cobertura.clave_consulta(clave, terminos)
        ultima = estado.get(clave_terminos)
        dias = max_dias if not ultima else min(max_dias, max(1, (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days + 1))
        for pagina in range(max_paginas):
            if hechas >= presupuesto:
                break
            r = cliente.get(BUSQUEDA, params=dict(params, keywords=consulta_or(terminos), f_TPR=f"r{dias * 86400}",
                                                  start=str(pagina * 10)))
            hechas += 1
            por_familia[familia] = por_familia.get(familia, 0) + 1
            por_lugar[lugar] = por_lugar.get(lugar, 0) + 1
            if r is None or r.status_code != 200:
                fallidas += 1
                seguidas += 1
                break
            seguidas = 0
            filas = tarjetas(r.text)
            for f in filas:
                if f["id"] not in vistos:
                    vistos.add(f["id"])
                    f["lugar_busqueda"] = lugar
                    f["familia"] = familia
                    avisos.append(f)
            if len(filas) < 10:
                break
        if seguidas == 0:
            estado[clave] = hoy
            estado[clave_terminos] = hoy
    # Descripción completa y estado de los avisos: primero los de las familias prioritarias (la entrega diaria solo usa
    # avisos con descripción) y los remotos (ahí la descripción decide el país)
    avisos.sort(key=lambda a: (a["familia"] not in prioritarias, "REMOTO" not in a["lugar_busqueda"],
                               -(int((a["fecha"] or "0000-00-00").replace("-", "")))))
    crudas, con_ficha, cerradas = [], 0, 0
    for a in avisos:
        descripcion, cerrado, externo, remoto = "", False, "", None
        if con_ficha < max_fichas and seguidas < 4 and not (limite_segundos and reloj() - inicio > limite_segundos):
            r = cliente.get(AVISO + a["id"])
            if r is not None and r.status_code == 200:
                descripcion, cerrado, externo, remoto = ficha(r.text)
                con_ficha += 1
                seguidas = 0
            elif r is not None and r.status_code == 429:
                seguidas += 1
        if cerrado:
            cerradas += 1
            continue
        if "REMOTO" in a["lugar_busqueda"]:
            remoto = True
        crudas.append({
            "titulo": a["titulo"], "empresa": a["empresa"], "ubicacion": a["ubicacion"], "descripcion": descripcion,
            "fecha": a["fecha"], "enlace": a["enlace"], "enlace_directo": externo if enlaces.sirve(externo) else "",
            "remoto": remoto, "fuente": NOMBRE,
        })
    stats = {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), "con_descripcion": con_ficha,
             "cerradas": cerradas, "combinaciones_revisadas": sum(1 for c in todas if estado.get(f"{c[0]}@{c[2]}") == hoy),
             "combinaciones_total": len(todas), "por_familia": por_familia, "por_lugar": por_lugar}
    return crudas, stats


def completar_descripciones(cliente, previas, max_fichas, hoy=None, max_dias=21, reloj=time.monotonic,
                            limite_segundos=None, prioritarias=()):
    """Relee la ficha pública de avisos de LinkedIn ya guardados que se quedaron sin descripción (LinkedIn limita cuántas
    fichas se leen por búsqueda). Sin descripción no se sabe el idioma y la vacante no se puede entregar.
    Primero los cargos prioritarios y los más recientes. Devuelve (crudas con descripción, estadísticas); al unirlas
    con la copia guardada se conserva la descripción más larga."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    desde = (datetime.fromisoformat(hoy) - timedelta(days=max_dias)).date().isoformat()
    def aviso_id(v):
        m = re.search(r"linkedin\.com/jobs/view/(\d+)", v.get("enlace") or "")
        return m.group(1) if m else ""
    candidatas = [v for v in previas if len(v.get("_descripcion") or "") < 200 and aviso_id(v)
                  and (v.get("fecha_publicacion") or v.get("visto_ultima_vez") or "") >= desde]
    candidatas.sort(key=lambda v: v.get("fecha_publicacion") or v.get("visto_primera_vez") or "", reverse=True)
    candidatas.sort(key=lambda v: not any(f["familia"] in prioritarias for f in v.get("familias", [])))  # estable
    crudas, leidas, cerradas, seguidas, peticiones = [], 0, 0, 0, 0
    for v in candidatas:
        if peticiones >= max_fichas or seguidas >= 4 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        r = cliente.get(AVISO + aviso_id(v))
        peticiones += 1
        if r is None or r.status_code != 200:
            seguidas += 1 if (r is not None and r.status_code == 429) else 0
            continue
        seguidas = 0
        descripcion, cerrado, _, _ = ficha(r.text)
        if cerrado:
            cerradas += 1
            continue
        if len(descripcion) < 200:
            continue
        leidas += 1
        crudas.append({"titulo": v["titulo"], "empresa": v["empresa"], "ubicacion": v.get("ubicacion", ""),
                       "descripcion": descripcion, "fecha": v.get("fecha_publicacion", ""), "enlace": v["enlace"],
                       "enlace_directo": "", "remoto": True if v.get("modalidad") == "remoto" else None,
                       "fuente": NOMBRE})
    return crudas, {"pendientes": len(candidatas), "peticiones": peticiones, "con_descripcion": leidas,
                    "cerradas": cerradas, "bloqueos_seguidos": seguidas}
