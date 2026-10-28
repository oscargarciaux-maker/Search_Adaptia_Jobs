"""Get on Board: portal tech de LATAM con API pública. Se postula en el mismo sitio (es un portal, no una copia)."""
import re
from datetime import datetime, timezone
from html import unescape

NOMBRE = "Get on Board"
URL = "https://www.getonbrd.com/api/v0/search/jobs"


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(str(html or "")))).strip()


def vacante(item):
    a = (item or {}).get("attributes") or {}
    empresa = ((((a.get("company") or {}).get("data") or {}).get("attributes")) or {}).get("name", "")
    paises = ", ".join(a.get("countries") or [])
    remoto = bool(a.get("remote")) or a.get("remote_modality") in ("fully_remote", "remote_local", "remote")
    zona = a.get("remote_zone") or ""
    publicado = a.get("published_at")
    fecha = datetime.fromtimestamp(publicado, tz=timezone.utc).date().isoformat() if isinstance(publicado, (int, float)) else ""
    ubicacion = ("Remote " + (zona or "") + " " if remoto else "") + paises
    return {"titulo": a.get("title", ""), "empresa": empresa, "ubicacion": ubicacion.strip(),
            "descripcion": _texto(" ".join(str(a.get(k) or "") for k in ("description_headline", "description",
                                                                           "functions", "desirable")))[:8000],
            "fecha": fecha, "enlace": ((item or {}).get("links") or {}).get("public_url", ""),
            "remoto": True if remoto else None, "fuente": NOMBRE}


def buscar(cliente, consultas):
    vistos, crudas = set(), []
    for q in consultas:
        datos = cliente.json(URL, params={"query": q, "per_page": 100, "expand": '["company"]'})
        for item in (datos or {}).get("data") or []:
            v = vacante(item)
            if v["enlace"] and v["enlace"] not in vistos:
                vistos.add(v["enlace"])
                crudas.append(v)
    return crudas, {"busquedas": len(consultas), "avisos": len(crudas)}
