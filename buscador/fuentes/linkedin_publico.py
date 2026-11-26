"""LinkedIn: buscador público de empleos (sin sesión, sin cookie).

Cada familia del mapa se busca en cada país y en remoto para LATAM, con sus consultas unidas por OR (LinkedIn lo acepta:
probado el 28 oct 2026). Hay más combinaciones que las que caben en una noche sin que LinkedIn bloquee, así que cada
corrida toma las combinaciones que hace más tiempo no se revisan y les pide los avisos desde la última revisión
(entre 1 y 30 días). En unos días se cubre todo, y la bodega guarda 30 días.
"""
import html
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from buscador import cobertura, enlaces
from buscador import ficha as ficha_texto

NOMBRE = "LinkedIn"
BUSQUEDA = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
AVISO = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
CERRADO = re.compile(r"No longer accepting applications|Ya no se aceptan solicitudes|closed-job", re.I)
# Contrato v39: lo que dijo cada ficha leída en esta búsqueda (abierta o cerrada, con la hora), para que valga como
# comprobación del enlace sin volver a preguntarle a LinkedIn. Enlace → {estado, motivo, comprobada_en}.
FICHAS = {}


def _anotar_ficha(enlace, titulo, pagina):
    from buscador import verificar_enlaces
    estado, motivo = verificar_enlaces.ficha_linkedin(pagina, titulo)
    if estado != "pendiente":
        FICHAS[enlace] = {"estado": estado, "motivo": motivo, "destino": AVISO + enlace.rstrip("/").rsplit("/", 1)[-1],
                          "comprobada_en": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
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

        def campo(patron, tarjeta=tarjeta):
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
    # Contrato v34: con sus saltos de línea, viñetas y negritas (antes quedaba en un solo párrafo).
    descripcion = ficha_texto.a_texto("<div>" + marca.group(1) + "</div>") if marca else ""
    # El enlace externo de postulación está detrás del inicio de sesión: el directo sale al juntar con la copia del
    # portal de la empresa. La modalidad remota sale de la búsqueda (filtro remoto) o de la descripción.
    return descripcion, bool(CERRADO.search(pagina or "")), "", None


def combinaciones(mapa, paises_activos):
    """Todas las combinaciones (familia, lugar) que se pueden buscar."""
    lugares = [(p, {"location": nombre}) for p, nombre in paises_activos] + LUGARES_EXTRA
    salida = [(f["id"], cobertura.consultas(f), clave, params) for f in mapa for clave, params in f.get("lugares", lugares)]
    # PR 1b: títulos en español en los lugares de los perfiles que solo aceptan avisos en español (modo panel).
    salida += [(f["id"], f["consultas_es"], clave + ":ES", params) for f in mapa if f.get("consultas_es")
               for clave, params in f.get("lugares_es", [])]
    return salida


POR_PAGINA = 10  # avisos por página de la búsqueda pública


def consulta_or(consultas, maximo=4):
    """Las primeras consultas de la familia unidas por OR, entre comillas."""
    return " OR ".join(f'"{c}"' for c in consultas[:maximo])



def buscar(cliente, mapa, paises_activos, estado, presupuesto, hoy=None, max_fichas=250, max_dias=30,
           reloj=time.monotonic, limite_segundos=None, prioritarias=(), desfase_terminos=0, max_paginas=3,
           fraccion_busqueda=0.5):
    """Recorre las combinaciones menos recientes hasta gastar el presupuesto de búsquedas.
    estado: dict {clave_combinacion: fecha ISO de la última revisión}; se actualiza aquí.
    Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    # Contrato v37: buscar páginas solo hasta la mitad del tiempo; el resto es para leer fichas (sin descripción no se
    # entrega). El 16 nov se revisaron los 55 lugares pero solo se leyeron 40 fichas de 765 avisos.
    limite_busqueda = None if limite_segundos is None else limite_segundos * fraccion_busqueda
    todas = combinaciones(mapa, paises_activos)
    todas = cobertura.repartir(todas, estado, hoy, prioritarias)
    vistos, avisos = set(), []
    hechas = fallidas = seguidas = 0
    por_familia, por_lugar = {}, {}
    for familia, consultas, lugar, params in todas:
        if hechas >= presupuesto or seguidas >= 4 or (limite_busqueda is not None and reloj() - inicio >= limite_busqueda):
            break
        # Contrato v47: en modo faltantes, lo ya buscado hoy no se repite (otros términos o la página siguiente).
        b = cobertura.siguiente_busqueda(consultas, hoy, 4, f"{familia}@{lugar}", estado, desfase=desfase_terminos,
                                         max_dias=max_dias)
        if b is None:
            continue
        for pagina in range(b.desde, b.desde + max_paginas):
            if hechas >= presupuesto or (limite_busqueda is not None and reloj() - inicio >= limite_busqueda):
                break
            r = cliente.get(BUSQUEDA, params=dict(params, keywords=consulta_or(b.terminos), f_TPR=f"r{b.dias * 86400}",
                                                  start=str(pagina * 10)))
            hechas += 1
            por_familia[familia] = por_familia.get(familia, 0) + 1
            por_lugar[lugar] = por_lugar.get(lugar, 0) + 1
            cobertura.anotar_busqueda("linkedin", familia, lugar)
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
            cobertura.anotar_paginas(estado, b, hoy, pagina + 1, len(filas) < POR_PAGINA)
            if len(filas) < POR_PAGINA:
                break
        if seguidas == 0:
            cobertura.anotar_hecha(estado, b, hoy)
    # Descripción completa y estado de los avisos: primero los de las familias prioritarias (la entrega diaria solo usa
    # avisos con descripción) y los remotos (ahí la descripción decide el país)
    # Contrato v36: por turnos entre los lugares buscados (la 1.ª de cada lugar, luego la 2.ª…), para que las búsquedas
    # de cada perfil (p. ej. Chicago o EE. UU.) también reciban fichas; antes casi todas iban a las remotas de LATAM.
    # Contrato v50: primero las fichas de los avisos cuyo título es de un cargo buscado. LinkedIn devuelve muchos que no
    # lo son (26 nov, Product Manager en Colombia: 82 de 320) y solo alcanza unas 290 peticiones por noche: el 25 nov se
    # leyeron 75 fichas de 818 avisos sin mirar el título, y los del cargo se quedaban sin descripción (sin ella no se
    # sabe el idioma ni se entrega). Los demás solo reciben ficha si sobra cupo (título genérico + descripción, v25).
    from buscador import familias
    del_cargo = {a["id"] for a in avisos if familias.clasificar(a["titulo"])}
    avisos.sort(key=lambda a: a["id"] not in del_cargo)  # estable: los turnos por lugar se cuentan entre los del cargo
    turno, vistos_lugar = {}, Counter()
    for a in avisos:
        turno[id(a)] = vistos_lugar[a["lugar_busqueda"]]
        vistos_lugar[a["lugar_busqueda"]] += 1
    # Contrato v37: primero los avisos de los lugares de quien va corto.
    avisos.sort(key=lambda a: (a["id"] not in del_cargo, a["familia"] not in prioritarias,
                               not cobertura.va_primero(a["familia"], a["lugar_busqueda"]),
                               turno[id(a)], "REMOTO" not in a["lugar_busqueda"],
                               -(int((a["fecha"] or "0000-00-00").replace("-", "")))))
    crudas, con_ficha, cerradas, fichas_del_cargo = [], 0, 0, 0
    for a in avisos:
        descripcion, cerrado, externo, remoto = "", False, "", None
        if con_ficha < max_fichas and seguidas < 4 and not (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            r = cliente.get(AVISO + a["id"])
            if r is not None and r.status_code == 200:
                descripcion, cerrado, externo, remoto = ficha(r.text)
                _anotar_ficha(a["enlace"], a["titulo"], r.text)
                con_ficha += 1
                fichas_del_cargo += a["id"] in del_cargo
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
            "_busqueda": f"{a['familia']}@{a['lugar_busqueda']}",  # contrato v40: de qué búsqueda salió
        })
    stats = {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), "con_descripcion": con_ficha,
             "del_cargo": len(del_cargo), "fichas_del_cargo": fichas_del_cargo,
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
    candidatas = cobertura.por_necesidad(candidatas)  # contrato v50: por turnos entre personas, primero quien va corta
    crudas, leidas, cerradas, seguidas, peticiones = [], 0, 0, 0, 0
    for v in candidatas:
        if peticiones >= max_fichas or seguidas >= 4 or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        r = cliente.get(AVISO + aviso_id(v))
        peticiones += 1
        if r is None or r.status_code != 200:
            seguidas += 1 if (r is not None and r.status_code == 429) else 0
            continue
        seguidas = 0
        descripcion, cerrado, _, _ = ficha(r.text)
        _anotar_ficha(v["enlace"], v["titulo"], r.text)
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
