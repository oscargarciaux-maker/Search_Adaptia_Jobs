"""Brave Search (solo si existe el secreto BRAVE_API_KEY): descubre empresas que publican vacantes en Greenhouse, Lever,
Ashby o Workable para que la fuente de portales las lea gratis cada noche. No trae vacantes directamente."""
import os
import re

from buscador import familias

NOMBRE = "Brave (descubre empresas)"
URL = "https://api.search.brave.com/res/v1/web/search"
SITIOS = {"greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/([a-z0-9_-]+)", "lever": r"jobs\.lever\.co/([a-z0-9_.-]+)",
          "ashby": r"jobs\.ashbyhq\.com/([a-z0-9_.%-]+)", "workable": r"apply\.workable\.com/([a-z0-9_-]+)"}
DOMINIOS = {"greenhouse": "boards.greenhouse.io", "lever": "jobs.lever.co", "ashby": "jobs.ashbyhq.com",
            "workable": "apply.workable.com"}
REGIONES = ["latam", "latin america", "remote colombia", "remote mexico", "remoto", "south america"]


def consultas_del_dia(n, dia_del_anio):
    """n consultas que rotan cada día: sistema × familia × región."""
    todas = []
    for f in familias.mapa():
        for sistema, dominio in DOMINIOS.items():
            for region in REGIONES:
                todas.append((sistema, f'site:{dominio} "{f["consultas"][0]}" {region}'))
    inicio = (dia_del_anio * n) % len(todas)
    return [todas[(inicio + i) % len(todas)] for i in range(min(n, len(todas)))]


def buscar(cliente, n, dia_del_anio, clave=None):
    """Tableros encontrados: lista de {"sistema", "slug"}, y estadísticas."""
    clave = clave or os.environ.get("BRAVE_API_KEY", "")
    if not clave:
        return [], {"omitida": "sin BRAVE_API_KEY"}
    hallados, hechas = {}, 0
    for sistema, q in consultas_del_dia(n, dia_del_anio):
        datos = cliente.json(URL, params={"q": q, "count": 20},
                             headers={"Accept": "application/json", "X-Subscription-Token": clave})
        hechas += 1
        for res in ((datos or {}).get("web") or {}).get("results") or []:
            m = re.search(SITIOS[sistema], res.get("url", ""), re.I)
            if m and m.group(1).lower() not in ("embed", "jobs"):
                hallados[(sistema, m.group(1).lower())] = {"sistema": sistema, "slug": m.group(1).lower()}
    return list(hallados.values()), {"busquedas": hechas, "tableros": len(hallados)}
