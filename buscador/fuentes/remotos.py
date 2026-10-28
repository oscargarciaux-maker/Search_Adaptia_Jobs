"""Tableros de empleo remoto (Remotive, Working Nomads, Himalayas, RemoteOK, Jobicy, We Work Remotely).

Son copias de avisos de otros: nunca se entrega su enlace. Para Remotive y Working Nomads se abre la página y se toma el
botón de postular (el original); las que no lo dejan ver (Himalayas, RemoteOK, Jobicy y We Work Remotely responden 403
o lo esconden) aportan los nombres de sus empresas, que la fuente de portales prueba para leer sus avisos originales.
"""
import re
from html import unescape

from buscador import enlaces, familias

NOMBRE = "Tableros remotos"
REMOTIVE_CATEGORIAS = ["design", "software-development", "data", "devops", "product", "marketing", "customer-support",
                       "writing", "sales-business", "qa", "all-others", "finance", "human-resources"]
WWR_CATEGORIAS = ["remote-design-jobs", "remote-full-stack-programming-jobs", "remote-front-end-programming-jobs",
                  "remote-back-end-programming-jobs", "remote-devops-sysadmin-jobs", "remote-management-and-finance-jobs",
                  "remote-product-jobs", "remote-customer-support-jobs", "remote-sales-and-marketing-jobs",
                  "all-other-remote-jobs"]


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(str(html or "")))).strip()


def _es_de_alguna_familia(titulo):
    return bool(familias.clasificar(titulo))


def remotive(cliente):
    salida = []
    for cat in REMOTIVE_CATEGORIAS:
        datos = cliente.json("https://remotive.com/api/remote-jobs", params={"category": cat, "limit": 200})
        for j in (datos or {}).get("jobs") or []:
            salida.append({"titulo": j.get("title", ""), "empresa": j.get("company_name", ""),
                           "ubicacion": "Remote - " + (j.get("candidate_required_location") or ""),
                           "descripcion": _texto(j.get("description"))[:8000], "fecha": str(j.get("publication_date", ""))[:10],
                           "enlace": j.get("url", ""), "remoto": True, "fuente": "Remotive"})
    return salida


def working_nomads(cliente):
    datos = cliente.json("https://www.workingnomads.com/api/exposed_jobs/") or []
    return [{"titulo": j.get("title", ""), "empresa": j.get("company_name", ""),
             "ubicacion": "Remote - " + (j.get("location") or ""), "descripcion": _texto(j.get("description"))[:8000],
             "fecha": str(j.get("pub_date", ""))[:10], "enlace": j.get("url", ""), "remoto": True,
             "fuente": "Working Nomads"} for j in datos if isinstance(j, dict)]


def himalayas(cliente, consultas):
    salida = {}
    for q in consultas:
        datos = cliente.json("https://himalayas.app/jobs/api/search", params={"q": q, "limit": 100})
        for j in (datos or {}).get("jobs") or []:
            salida[j.get("guid")] = {"titulo": j.get("title", ""), "empresa": j.get("companyName", "")}
    return list(salida.values())


def remoteok(cliente):
    datos = cliente.json("https://remoteok.com/api") or []
    return [{"titulo": j.get("position", ""), "empresa": j.get("company", "")} for j in datos[1:] if isinstance(j, dict)]


def jobicy(cliente):
    datos = cliente.json("https://jobicy.com/api/v2/remote-jobs", params={"count": 100}) or {}
    return [{"titulo": j.get("jobTitle", ""), "empresa": j.get("companyName", "")} for j in datos.get("jobs") or []]


def wwr(cliente):
    salida = []
    for cat in WWR_CATEGORIAS:
        r = cliente.get(f"https://weworkremotely.com/categories/{cat}.rss")
        if r is None or r.status_code != 200:
            continue
        for item in re.findall(r"<item>([\s\S]*?)</item>", r.text):
            titulo = re.search(r"<title>([\s\S]*?)</title>", item)
            if titulo and ":" in titulo.group(1):
                empresa, cargo = unescape(titulo.group(1)).split(":", 1)
                salida.append({"titulo": cargo.strip(), "empresa": empresa.strip()})
    return salida


def resolver(cliente, vacantes, cache, maximo):
    """Abre la página de cada copia y cambia su enlace por el original. Las que no lo tienen se descartan.
    cache: {enlace del tablero: original o ''} para no abrir la misma página dos noches."""
    salida, abiertas = [], 0
    for v in vacantes:
        url = v["enlace"]
        if url in cache:
            original = cache[url]
        elif abiertas < maximo:
            abiertas += 1
            r = cliente.get(url)
            original = ""
            if r is not None and r.status_code == 200:
                final = r.url
                if enlaces.host(final) != enlaces.host(url) and enlaces.sirve(final):
                    original = final  # Working Nomads redirige directo al aviso de la empresa
                else:
                    original = enlaces.original_en_html(r.text, final)
            cache[url] = original
        else:
            continue
        if original:
            salida.append(dict(v, enlace=original, enlace_directo=""))
    return salida, abiertas


def buscar(cliente, consultas_himalayas, cache, max_paginas=300):
    """(vacantes crudas con enlace original, empresas para probar en los portales, estadísticas)."""
    con_pagina = [v for v in remotive(cliente) + working_nomads(cliente) if _es_de_alguna_familia(v["titulo"])]
    resueltas, abiertas = resolver(cliente, con_pagina, cache, max_paginas)
    empresas = {v["empresa"] for v in con_pagina if v["empresa"]}
    solo_nombres = []
    for lector in (lambda: himalayas(cliente, consultas_himalayas), lambda: remoteok(cliente), lambda: jobicy(cliente),
                   lambda: wwr(cliente)):
        try:
            solo_nombres.extend(lector())
        except Exception:  # noqa: BLE001 — un tablero caído no detiene a los demás
            continue
    empresas |= {x["empresa"] for x in solo_nombres if x.get("empresa") and _es_de_alguna_familia(x.get("titulo", ""))}
    stats = {"con_pagina": len(con_pagina), "paginas_abiertas": abiertas, "con_original": len(resueltas),
             "empresas_para_portales": len(empresas)}
    return resueltas, sorted(empresas), stats
