"""Get on Board: portal tech de LATAM con API pública. Se postula en el mismo sitio (es un portal, no una copia).

Contrato v18: su política de trabajo remoto (`remote_modality`) dice desde dónde se puede postular, tal como la muestra
la ficha pública:
- `fully_remote` — «Candidates can reside anywhere in the world» / «100% remoto desde cualquier país»;
- `remote_local` — «candidates must reside in <país>» (el país viene en `location_tenants`).
Antes se perdía y la ubicación quedaba «Remote Remoto», que no dice nada."""
import re
from datetime import datetime, timezone
from html import unescape

NOMBRE = "Get on Board"
URL = "https://www.getonbrd.com/api/v0/search/jobs"


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
    vistos, crudas = set(), []
    for q in consultas:
        datos = cliente.json(URL, params={"query": q, "per_page": 100, "expand": '["company","location_tenants"]'})
        for item in (datos or {}).get("data") or []:
            v = vacante(item)
            if v["enlace"] and v["enlace"] not in vistos:
                vistos.add(v["enlace"])
                crudas.append(v)
    return crudas, {"busquedas": len(consultas), "avisos": len(crudas)}
