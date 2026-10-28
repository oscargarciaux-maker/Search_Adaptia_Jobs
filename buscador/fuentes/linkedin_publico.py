"""LinkedIn: buscador público de empleos (sin sesión, sin cookie). Adaptado de tools/jobspy_buscar.py de ux_job_agent.

Cada familia del mapa se busca en cada país y en remoto para LATAM, con sus consultas unidas por OR (LinkedIn lo acepta:
probado el 28 oct 2026). Hay más combinaciones que las que caben en una noche sin que LinkedIn bloquee, así que cada
corrida toma las combinaciones que hace más tiempo no se revisan y les pide los avisos desde la última revisión
(entre 1 y 30 días). En unos días se cubre todo, y la bodega guarda 30 días.
"""
import html
import re
import time
from datetime import datetime, timezone

from buscador import enlaces

NOMBRE = "LinkedIn"
BUSQUEDA = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
AVISO = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
CERRADO = re.compile(r"No longer accepting applications|Ya no se aceptan solicitudes|closed-job", re.I)
# Lugares de búsqueda además de cada país: remoto para toda la región
LUGARES_EXTRA = [("LATAM", {"location": "Latin America"}), ("REMOTO", {"location": "Latin America", "f_WT": "2"})]


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
    return [(f["id"], f["consultas"], clave, params) for f in mapa for clave, params in lugares]


def consulta_or(consultas, maximo=4):
    """Las primeras consultas de la familia unidas por OR, entre comillas."""
    return " OR ".join(f'"{c}"' for c in consultas[:maximo])


def buscar(cliente, mapa, paises_activos, estado, presupuesto, hoy=None, max_fichas=250, max_dias=30,
           reloj=time.monotonic, limite_segundos=None):
    """Recorre las combinaciones menos recientes hasta gastar el presupuesto de búsquedas.
    estado: dict {clave_combinacion: fecha ISO de la última revisión}; se actualiza aquí.
    Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    todas = combinaciones(mapa, paises_activos)
    todas.sort(key=lambda c: estado.get(f"{c[0]}@{c[2]}", ""))
    vistos, avisos = set(), []
    hechas = fallidas = seguidas = 0
    for familia, consultas, lugar, params in todas:
        if hechas >= presupuesto or seguidas >= 4 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        clave = f"{familia}@{lugar}"
        ultima = estado.get(clave)
        dias = max_dias if not ultima else min(max_dias, max(1, (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days + 1))
        for pagina in range(3):
            if hechas >= presupuesto:
                break
            r = cliente.get(BUSQUEDA, params=dict(params, keywords=consulta_or(consultas), f_TPR=f"r{dias * 86400}",
                                                  start=str(pagina * 10)))
            hechas += 1
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
                    avisos.append(f)
            if len(filas) < 10:
                break
        if seguidas == 0:
            estado[clave] = hoy
    # Descripción completa y estado de los avisos (los remotos y los más nuevos primero: ahí la descripción decide el país)
    avisos.sort(key=lambda a: (a["lugar_busqueda"] not in ("LATAM", "REMOTO"), a["fecha"] or ""), reverse=False)
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
        if a["lugar_busqueda"] == "REMOTO":
            remoto = True
        crudas.append({
            "titulo": a["titulo"], "empresa": a["empresa"], "ubicacion": a["ubicacion"], "descripcion": descripcion,
            "fecha": a["fecha"], "enlace": a["enlace"], "enlace_directo": externo if enlaces.sirve(externo) else "",
            "remoto": remoto, "fuente": NOMBRE,
        })
    stats = {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), "con_descripcion": con_ficha,
             "cerradas": cerradas, "combinaciones_revisadas": sum(1 for c in todas if estado.get(f"{c[0]}@{c[2]}") == hoy),
             "combinaciones_total": len(todas)}
    return crudas, stats
