"""Get on Board: portal tech de LATAM con API pública. Se postula en el mismo sitio (es un portal, no una copia).

Contrato v18: su política de trabajo remoto (`remote_modality`) dice desde dónde se puede postular, tal como la muestra
la ficha pública:
- `fully_remote` — «Candidates can reside anywhere in the world» / «100% remoto desde cualquier país»;
- `remote_local` — «candidates must reside in <país>» (el país viene en `location_tenants`).
Antes se perdía y la ubicación quedaba «Remote Remoto», que no dice nada."""
import re
from collections import Counter
from datetime import datetime, timezone
from html import unescape

from buscador import registro
from buscador.http import motivo_del_fallo

NOMBRE = "Get on Board"
URL = "https://www.getonbrd.com/api/v0/search/jobs"
URL_CATEGORIAS = "https://www.getonbrd.com/api/v0/categories"
EXPAND = '["company","location_tenants"]'


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(str(html or "")))).strip()


def _nombres(relacion):
    """Nombres de una relación expandida de la API ({"data": [{"attributes": {"name": ...}}]})."""
    datos = (relacion or {}).get("data") if isinstance(relacion, dict) else None
    datos = datos if isinstance(datos, list) else [datos] if isinstance(datos, dict) else []
    return [str((d.get("attributes") or {}).get("name") or "").strip() for d in datos
            if isinstance(d, dict) and (d.get("attributes") or {}).get("name")]


def ubicacion(a):
    """Ubicación legible con lo que dice la política remota del aviso (contrato v18)."""
    modalidad = a.get("remote_modality") or ""
    remoto = bool(a.get("remote")) or modalidad in ("fully_remote", "remote_local", "remote", "temporarily_remote")
    zona = (a.get("remote_zone") or "").strip()
    lugares = [str(c) for c in a.get("countries") or [] if str(c).strip().lower() not in ("remote", "remoto")]
    if modalidad == "fully_remote":
        return "Remote - " + (zona or "Worldwide")  # zona: si el aviso la acota, la acota
    if modalidad == "remote_local":
        donde = _nombres(a.get("location_tenants")) or lugares
        return "Remote - " + "; ".join(donde) if donde else "Remote"  # sin país: sigue por confirmar
    if remoto:
        return " ".join(x for x in ("Remote", zona, ", ".join(lugares)) if x)
    return ", ".join(lugares)


def vacante(item):
    a = (item or {}).get("attributes") or {}
    empresa = ((((a.get("company") or {}).get("data") or {}).get("attributes")) or {}).get("name", "")
    remoto = bool(a.get("remote")) or a.get("remote_modality") in ("fully_remote", "remote_local", "remote")
    publicado = a.get("published_at")
    fecha = datetime.fromtimestamp(publicado, tz=timezone.utc).date().isoformat() if isinstance(publicado, (int, float)) else ""
    return {"titulo": a.get("title", ""), "empresa": empresa, "ubicacion": ubicacion(a),
            "descripcion": _texto(" ".join(str(a.get(k) or "") for k in ("description_headline", "description",
                                                                           "functions", "desirable")))[:30000],
            "fecha": fecha, "enlace": ((item or {}).get("links") or {}).get("public_url", ""),
            "remoto": True if remoto else None, "fuente": NOMBRE}


def buscar(cliente, consultas):
    """Vacantes crudas y estadísticas; `respondidas` (contrato v47): las consultas que sí respondieron."""
    vistos, crudas, respondidas, motivos = set(), [], [], Counter()
    for q in consultas:
        datos = cliente.json(URL, params={"query": q, "per_page": 100, "expand": EXPAND})
        if datos is not None:
            respondidas.append(q)
        else:
            motivos[motivo_del_fallo(cliente)] += 1
        for item in (datos or {}).get("data") or []:
            v = vacante(item)
            if v["enlace"] and v["enlace"] not in vistos:
                vistos.add(v["enlace"])
                crudas.append(v)
    # Contrato v51: el 26 nov ninguna búsqueda respondió desde GitHub y el reporte no decía por qué.
    stats = {"busquedas": len(consultas), "avisos": len(crudas), "respondidas": respondidas,
             "fallidas": len(consultas) - len(respondidas)}
    if motivos:
        stats["motivos"] = dict(motivos)
        registro.aviso("getonbrd", RuntimeError(f"{stats['fallidas']} búsquedas sin respuesta: {dict(motivos)}"))
    return crudas, stats


def catalogo(cliente, max_peticiones, vistos=None):
    """P-17.2: recorre las categorías de Get on Board con paginación (`/categories/{id}/jobs`), sin depender de qué
    términos se buscaron. Gasta como máximo `max_peticiones` (incluida la de la lista de categorías) y no repite
    enlaces de `vistos`. Devuelve (vacantes, estadísticas)."""
    vistos = set(vistos or ())
    crudas, peticiones, fallidas, motivos = [], 0, 0, Counter()
    stats = {"catalogo_peticiones": 0, "catalogo_avisos": 0, "catalogo_fallidas": 0}
    if max_peticiones < 2:
        return crudas, stats
    lista = cliente.json(URL_CATEGORIAS)
    peticiones += 1
    if lista is None:
        motivos[motivo_del_fallo(cliente)] += 1
        fallidas += 1
    ids = [str(c.get("id")) for c in (lista or {}).get("data") or [] if isinstance(c, dict) and c.get("id")]
    paginas = {i: 1 for i in ids}  # categoría -> siguiente página; se quita al llegar a la última
    # Primero la página 1 de todas (cada categoría aporta algo) y después las siguientes, hasta el tope.
    while paginas and peticiones < max_peticiones:
        for cat in list(paginas):
            if peticiones >= max_peticiones:
                break
            pagina = paginas[cat]
            datos = cliente.json(f"{URL_CATEGORIAS}/{cat}/jobs",
                                 params={"per_page": 100, "page": pagina, "expand": EXPAND})
            peticiones += 1
            if datos is None:
                fallidas += 1
                motivos[motivo_del_fallo(cliente)] += 1
                del paginas[cat]
                continue
            for item in datos.get("data") or []:
                v = vacante(item)
                if v["enlace"] and v["enlace"] not in vistos:
                    vistos.add(v["enlace"])
                    crudas.append(v)
            total = ((datos.get("meta") or {}).get("total_pages")) or 1
            if pagina >= total or not datos.get("data"):
                del paginas[cat]
            else:
                paginas[cat] = pagina + 1
    stats = {"catalogo_peticiones": peticiones, "catalogo_avisos": len(crudas), "catalogo_fallidas": fallidas}
    if motivos:
        stats["catalogo_motivos"] = dict(motivos)
        registro.aviso("getonbrd", RuntimeError(f"catálogo: {fallidas} peticiones sin respuesta: {dict(motivos)}"))
    return crudas, stats
