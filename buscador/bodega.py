"""Bodega nocturna: recoge de todas las fuentes, limpia, guarda 30 días y publica. Sin IA.

Uso:  python -m buscador.bodega --salida <carpeta>  [--modo diario|inicial] [--consulta "texto" --pais CO]
<carpeta> trae la corrida anterior en <carpeta>/trabajo/ (bodega.json.gz, estado.json, empresas_ats.csv) y recibe la
nueva, más la página y los datos publicados (ver publicar.py). El flujo bodega.yml la sube a la rama `publicado`.
"""
import argparse
import gzip
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from buscador import enlaces, familias, normalizar, paises, vacante
from buscador.fuentes import ats, brave, getonbrd, indeed, linkedin_apify, linkedin_publico, remotos
from buscador.http import Cliente

RAIZ = Path(__file__).resolve().parent.parent


def config():
    return yaml.safe_load((RAIZ / "datos" / "config.yaml").read_text(encoding="utf-8"))


def _leer_json(ruta, defecto):
    ruta = Path(ruta)
    if not ruta.exists():
        return defecto
    abrir = gzip.open if ruta.suffix == ".gz" else open
    with abrir(ruta, "rt", encoding="utf-8") as f:
        return json.load(f)


def _guardar_json(ruta, datos, comprimido=False):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if comprimido:
        with gzip.open(ruta, "wt", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    else:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)


def _paises_activos(cfg):
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    return [(c, nombres[c]) for c in cfg["paises_activos"] if c in nombres]


def _fecha_de(v):
    return v.get("fecha_publicacion") or v.get("visto_primera_vez") or ""


def recoger(cfg, estado, hoy, trabajo, solo_mapa=None):
    """Corre las fuentes en paralelo (cada una con su cliente y su parte del estado). Devuelve
    (crudas, empresas para probar, enlaces de portales leídos, empresas cuyos portales se leyeron, salud)."""
    p = cfg["presupuestos"]
    mapa = solo_mapa or familias.mapa()
    activos = _paises_activos(cfg)
    limite = p["minutos_por_fuente"] * 60
    salud = {}
    for clave in ("linkedin", "indeed", "apify", "ats_probadas", "remotos_cache"):
        estado.setdefault(clave, {})

    def correr(nombre, funcion):
        t0 = time.monotonic()
        try:
            resultado = funcion()
        except Exception as e:  # noqa: BLE001 — una fuente que falla no detiene a las demás
            salud[nombre] = {"error": f"{type(e).__name__}: {e}"[:300], "segundos": round(time.monotonic() - t0)}
            return []
        crudas, stats = resultado[0], resultado[-1]
        salud[nombre] = dict(stats, segundos=round(time.monotonic() - t0))
        return resultado

    def f_linkedin():
        return linkedin_publico.buscar(Cliente(pausa=tuple(p["pausa_linkedin"])), mapa, activos, estado["linkedin"],
                                       p["linkedin_busquedas"], hoy=hoy, max_fichas=p["linkedin_fichas"],
                                       max_dias=cfg["dias_maximos"], limite_segundos=limite)

    def f_indeed():
        return indeed.buscar(mapa, [c for c, _ in activos], estado["indeed"], p["indeed_busquedas"], hoy=hoy,
                             max_dias=cfg["dias_maximos"], limite_segundos=limite)

    def f_apify():
        combos = linkedin_publico.combinaciones(mapa, activos)
        return linkedin_apify.buscar(Cliente(), cfg["apify"]["actor_linkedin"], combos, estado["apify"], hoy,
                                     presupuesto=p["apify_busquedas"], max_dias=cfg["dias_maximos"],
                                     limite_segundos=limite)

    def f_remotos():
        consultas = sorted({c for f in mapa for c in f["consultas"][:1]})
        return remotos.buscar(Cliente(pausa=(0.3, 0.8)), consultas, estado["remotos_cache"],
                              max_paginas=p["remotos_paginas"])

    def f_getonbrd():
        return getonbrd.buscar(Cliente(pausa=(0.3, 0.8)), sorted({f["consultas"][0] for f in mapa})[:p["getonbrd_busquedas"]])

    filas_ats = ats.leer_lista(ats.RUTA, trabajo / "empresas_ats.csv")

    def f_ats():
        return ats.buscar(Cliente(pausa=(0.05, 0.2)), filas_ats)

    with ThreadPoolExecutor(6) as ex:
        tareas = {n: ex.submit(correr, n, f) for n, f in [("LinkedIn", f_linkedin), ("Indeed", f_indeed),
                                                            ("LinkedIn (Apify)", f_apify), ("Tableros remotos", f_remotos),
                                                            ("Get on Board", f_getonbrd), ("Portales de empresas", f_ats)]}
        resultados = {n: t.result() for n, t in tareas.items()}
    crudas, empresas = [], set()
    for n, r in resultados.items():
        if not r:
            continue
        crudas.extend(r[0])
        if n == "Tableros remotos":
            empresas |= set(r[1])
    ats_crudas = resultados.get("Portales de empresas") or [[], set(), {}]
    enlaces_ats = {c["enlace"] for c in ats_crudas[0]}
    empresas_leidas = ats_crudas[1] if len(ats_crudas) == 3 else set()
    # Empresas de LinkedIn e Indeed con cargos del mapa: candidatas a tener portal propio
    for c in crudas:
        if c.get("fuente") in ("LinkedIn", "Indeed", "LinkedIn (Apify)") and c.get("empresa") and familias.clasificar(c["titulo"]):
            empresas.add(c["empresa"])
    # Descubrir portales nuevos: nombres de empresas y tableros que encuentre Brave
    nuevos = []
    try:
        t0 = time.monotonic()
        nuevos, probadas = ats.descubrir(Cliente(pausa=(0.05, 0.15)), sorted(empresas), estado["ats_probadas"],
                                         p["empresas_por_probar"], hoy, filas_ats)
        tableros_brave, stats_brave = brave.buscar(Cliente(pausa=(1.0, 1.3)), p["brave_busquedas"],
                                                   date.fromisoformat(hoy).timetuple().tm_yday)
        salud["Brave (descubre empresas)"] = stats_brave
        conocidos = {(f["sistema"], f["slug"]) for f in filas_ats + nuevos}
        for t in tableros_brave:
            if (t["sistema"], t["slug"]) not in conocidos:
                nuevos.append({"empresa": t["slug"], "sistema": t["sistema"], "slug": t["slug"], "origen": "Brave",
                               "agregada": hoy})
        salud["Descubrir portales"] = {"empresas_probadas": probadas, "portales_nuevos": len(nuevos),
                                       "segundos": round(time.monotonic() - t0)}
    except Exception as e:  # noqa: BLE001
        salud["Descubrir portales"] = {"error": str(e)[:300]}
    ats.guardar_lista(ats.leer_lista(trabajo / "empresas_ats.csv") + nuevos, trabajo / "empresas_ats.csv")
    return crudas, enlaces_ats, empresas_leidas, salud


def limpiar(previas, crudas, hoy, dias_maximos, enlaces_ats, empresas_leidas, consulta=""):
    """Convierte, junta con lo anterior, quita viejas y cerradas. Devuelve (vacantes, títulos sin familia, conteos)."""
    sin_familia = Counter()
    nuevas, descartes = [], Counter()
    for c in crudas:
        v = vacante.crear(c.get("titulo"), c.get("empresa"), c.get("enlace"), c.get("fuente", ""),
                          ubicacion=c.get("ubicacion", ""), descripcion=c.get("descripcion", ""), fecha=c.get("fecha", ""),
                          remoto=c.get("remoto"), enlace_directo=c.get("enlace_directo", ""), hoy=hoy,
                          consulta=consulta)
        if v is None:
            if c.get("titulo") and enlaces.sirve(c.get("enlace", "")) and not familias.clasificar(c["titulo"]):
                sin_familia[normalizar.titulo_base(c["titulo"])] += 1
                descartes["sin familia en el mapa"] += 1
            else:
                descartes["sin enlace donde postular"] += 1
            continue
        if not v["paises"]:
            descartes["no se puede aplicar desde LATAM"] += 1
            continue
        nuevas.append(v)
    limite = (date.fromisoformat(hoy) - timedelta(days=dias_maximos)).isoformat()
    vistas_hoy = {v["id"] for v in nuevas}
    todas = vacante.juntar([vacante.reetiquetar(dict(v)) for v in previas] + nuevas)
    salida = []
    for v in todas:
        if _fecha_de(v) and _fecha_de(v) < limite:
            descartes["más de %d días" % dias_maximos] += 1
            continue
        # Portal de la empresa leído hoy y el aviso ya no está: se cerró
        de_portal = any(enlaces.tipo(u) == "original" for u in (v["enlace"], v["enlace_directo"]))
        if de_portal and v["empresa"] in empresas_leidas and v["id"] not in vistas_hoy and \
                not ({v["enlace"], v["enlace_directo"]} & enlaces_ats):
            descartes["cerrada en el portal de la empresa"] += 1
            continue
        salida.append(v)
    return salida, sin_familia, descartes


PRUEBA = {"minutos_por_fuente": 3, "linkedin_busquedas": 6, "linkedin_fichas": 8, "indeed_busquedas": 2,
          "apify_busquedas": 2, "remotos_paginas": 8, "empresas_por_probar": 5, "brave_busquedas": 2,
          "getonbrd_busquedas": 3}


def correr(salida, modo="diario", consulta=None, pais=None, hoy=None, prueba=False):
    inicio = time.monotonic()
    cfg = config()
    if prueba:
        cfg["presupuestos"].update(PRUEBA)
    hoy = hoy or datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
    salida = Path(salida)
    trabajo = salida / "trabajo"
    estado = _leer_json(trabajo / "estado.json", {})
    previas = _leer_json(trabajo / "bodega.json.gz", [])
    if modo == "inicial":
        estado = {k: v for k, v in estado.items() if k not in ("linkedin", "indeed", "apify")}
    solo = None
    if consulta:
        # Búsqueda profunda: las familias que coinciden con el texto, o una familia temporal con el texto tal cual
        base = normalizar.titulo_base(consulta)
        solo = [f for f in familias.mapa() if base in f["_titulos"]["exacto"] or base in f["_titulos"]["similar"]
                or normalizar.contiene_frase(normalizar.titulo_base(f["nombre"]), base)]
        if not solo:
            solo = [{"id": "consulta", "consultas": [consulta], "nombre": consulta}]
        if pais:
            cfg["paises_activos"] = [pais]
        estado_busqueda = {}  # una búsqueda profunda no mueve la rotación de la noche
        crudas, enlaces_ats, leidas, salud = recoger(cfg, dict(estado_busqueda, ats_probadas=estado.get("ats_probadas", {}),
                                                                remotos_cache=estado.get("remotos_cache", {})),
                                                      hoy, trabajo, solo_mapa=solo)
    else:
        crudas, enlaces_ats, leidas, salud = recoger(cfg, estado, hoy, trabajo)
    vacantes, sin_familia, descartes = limpiar(previas, crudas, hoy, cfg["dias_maximos"], enlaces_ats, leidas,
                                               consulta=consulta or "")
    _guardar_json(trabajo / "bodega.json.gz", vacantes, comprimido=True)
    _guardar_json(trabajo / "estado.json", estado)
    reporte = {
        "fecha": hoy, "hora_utc": datetime.now(timezone.utc).strftime("%H:%M"), "modo": modo,
        "consulta": consulta or "", "pais": pais or "",
        "minutos": round((time.monotonic() - inicio) / 60, 1),
        "vacantes_en_bodega": len(vacantes), "crudas_hoy": len(crudas),
        "nuevas_hoy": sum(1 for v in vacantes if v["visto_primera_vez"] == hoy),
        "fuentes": salud, "descartes": dict(descartes),
        "por_familia": dict(Counter(f["familia"] for v in vacantes for f in v["familias"]).most_common()),
        "por_pais": dict(Counter(p for v in vacantes for p in v["paises"]).most_common()),
        "por_fuente": dict(Counter(fu for v in vacantes for fu in v["fuentes"]).most_common()),
    }
    from buscador import publicar
    publicar.publicar(salida, vacantes, reporte, sin_familia)
    return reporte


def main():
    ap = argparse.ArgumentParser(description="Bodega nocturna de vacantes")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--modo", default="diario", choices=["diario", "inicial"])
    ap.add_argument("--consulta", default="")
    ap.add_argument("--pais", default="")
    ap.add_argument("--prueba", action="store_true", help="presupuestos mínimos, para probar que todo funciona")
    a = ap.parse_args()
    reporte = correr(a.salida, a.modo, a.consulta or None, a.pais or None, prueba=a.prueba)
    print(json.dumps({k: reporte[k] for k in ("fecha", "minutos", "vacantes_en_bodega", "nuevas_hoy", "crudas_hoy",
                                              "descartes")}, ensure_ascii=False, indent=1))
    for n, s in reporte["fuentes"].items():
        print(f"  {n}: {s}")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
