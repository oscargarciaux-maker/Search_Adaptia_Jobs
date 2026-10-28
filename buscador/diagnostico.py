"""Diagnóstico: revisa la configuración, cada fuente con una consulta mínima, las claves opcionales y la última bodega.
Imprime una lista de chequeo en español (y la deja en el resumen de GitHub Actions). Uso: python -m buscador.diagnostico"""
import os
import sys

import requests

from buscador import bodega, familias, paises
from buscador.fuentes import ats, getonbrd, linkedin_publico, remotos
from buscador.http import Cliente


def revisar():
    filas = []

    def chequeo(nombre, funcion):
        try:
            ok, detalle = funcion()
        except Exception as e:  # noqa: BLE001
            ok, detalle = False, f"{type(e).__name__}: {e}"[:200]
        filas.append((ok, nombre, detalle))

    cfg = bodega.config()
    chequeo("Configuración (datos/config.yaml)", lambda: (bool(cfg["paises_activos"]) and cfg["dias_maximos"] > 0,
                                                         f"{len(cfg['paises_activos'])} países, {cfg['dias_maximos']} días"))
    chequeo("Mapa de cargos", lambda: (len(familias.mapa()) > 0, f"{len(familias.mapa())} familias"))
    chequeo("Países", lambda: (len(paises.datos()["codigos"]) > 0, f"{len(paises.datos()['codigos'])} países"))
    cliente = Cliente(pausa=(0.5, 1.0))

    def linkedin():
        r = cliente.get(linkedin_publico.BUSQUEDA, params={"keywords": "product designer", "location": "Colombia"})
        n = len(linkedin_publico.tarjetas(r.text)) if r is not None and r.status_code == 200 else 0
        return n > 0, f"{n} avisos en una búsqueda de prueba" if n else f"respondió {getattr(r, 'status_code', 'sin conexión')}"
    chequeo("LinkedIn público (sin sesión)", linkedin)

    def indeed():
        from jobspy import scrape_jobs
        df = scrape_jobs(site_name=["indeed"], search_term="developer", results_wanted=5, country_indeed="colombia", verbose=0)
        return len(df) > 0, f"{len(df)} avisos en una búsqueda de prueba"
    chequeo("Indeed (JobSpy)", indeed)

    def portales():
        filas_ats = ats.leer_lista()
        datos = cliente.json(ats.url_api(filas_ats[0]["sistema"], filas_ats[0]["slug"])) if filas_ats else None
        return bool(filas_ats) and datos is not None, f"{len(filas_ats)} empresas en la lista inicial"
    chequeo("Portales de empresas", portales)
    chequeo("Remotive", lambda: (len(remotos.remotive(cliente)) > 0, "responde"))
    chequeo("Get on Board", lambda: (len(getonbrd.buscar(cliente, ["designer"])[0]) > 0, "responde"))

    def apify():
        token = os.environ.get("APIFY_TOKEN", "")
        if not token:
            return None, "sin APIFY_TOKEN: LinkedIn se busca solo con la vía pública (menos volumen)"
        r = requests.get("https://api.apify.com/v2/users/me", params={"token": token}, timeout=20)
        actor = cfg["apify"]["actor_linkedin"]
        if r.status_code != 200:
            return False, f"la clave no funciona (Apify respondió {r.status_code})"
        return (True, f"clave válida; actor: {actor}") if actor else (None, "clave válida, pero falta elegir el actor en datos/config.yaml")
    chequeo("Apify (opcional)", apify)

    def brave_():
        clave = os.environ.get("BRAVE_API_KEY", "")
        if not clave:
            return None, "sin BRAVE_API_KEY: no se descubren empresas nuevas por búsqueda web"
        r = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": "site:jobs.lever.co designer", "count": 1},
                         headers={"X-Subscription-Token": clave, "Accept": "application/json"}, timeout=20)
        return r.status_code == 200, f"Brave respondió {r.status_code}"
    chequeo("Brave Search (opcional)", brave_)

    def publicado():
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not repo:
            return None, "sin GITHUB_REPOSITORY (solo se revisa dentro de GitHub Actions)"
        r = requests.get(f"https://raw.githubusercontent.com/{repo}/publicado/datos/salud.json", timeout=20)
        if r.status_code != 200:
            return False, "todavía no hay rama publicado: corre la Bodega nocturna una vez"
        s = r.json()
        return True, f"última bodega {s['fecha']}: {s['vacantes_en_bodega']} vacantes"
    chequeo("Última bodega publicada", publicado)
    return filas


def main():
    filas = revisar()
    simbolo = {True: "✅", False: "❌", None: "➖"}
    lineas = ["## Diagnóstico del buscador", ""] + [f"- {simbolo[ok]} **{n}**: {d}" for ok, n, d in filas]
    texto = "\n".join(lineas)
    print(texto)
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    sys.exit(1 if any(ok is False for ok, _, _ in filas) else 0)


if __name__ == "__main__":
    main()
