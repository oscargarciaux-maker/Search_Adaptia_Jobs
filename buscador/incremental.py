"""Capturas cortas gratuitas: no consumen Apify, no descubren empresas y no crean entregas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from buscador import entrega, familias
from buscador.fuentes import ats, indeed, linkedin_publico
from buscador.http import Cliente


def recoger(cfg, estado, hoy, trabajo):
    opciones = cfg.get("incremental", {})
    limite = opciones.get("minutos_por_fuente", 2) * 60
    prioritarias = {f for r in entrega.config()["roles"] for f in r["familias"]}
    mapa = [f for f in familias.mapa() if f["id"] in prioritarias]
    hora = datetime.now(timezone.utc).hour
    estado.setdefault("linkedin", {})
    estado.setdefault("indeed", {})

    def linkedin():
        return linkedin_publico.buscar(Cliente(pausa=(0.5, 1), espera_429=(5, 10), timeout=15), mapa, [],
            estado["linkedin"], opciones.get("linkedin_busquedas", 24), hoy=hoy, max_dias=2,
            max_fichas=opciones.get("linkedin_fichas", 48), max_paginas=1,
            limite_segundos=limite, prioritarias=prioritarias, desfase_terminos=hora * 4)

    def fuente_indeed():
        return indeed.buscar(mapa, cfg["paises_activos"], estado["indeed"], opciones.get("indeed_busquedas", 6),
                             hoy=hoy, max_dias=2, limite_segundos=limite, prioritarias=prioritarias,
                             desfase_terminos=hora)

    def portales():
        filas = ats.leer_lista(ats.RUTA, trabajo / "empresas_ats.csv")
        if filas:
            desplazamiento = hora * opciones.get("rotacion_empresas", 30) % len(filas)
            filas = filas[desplazamiento:] + filas[:desplazamiento]
        return ats.buscar(Cliente(pausa=(0.05, 0.1), espera_429=(2, 4), timeout=15), filas,
                          limite_segundos=limite, max_detalles=opciones.get("ats_detalles", 20),
                          prioritarias=prioritarias)

    crudas, enlaces, leidas, salud = [], set(), set(), {}
    with ThreadPoolExecutor(3) as ex:
        tareas = [(n, ex.submit(f)) for n, f in (("LinkedIn", linkedin), ("Indeed", fuente_indeed),
                                                ("Portales de empresas", portales))]
        for nombre, tarea in tareas:
            try:
                resultado = tarea.result()
                crudas.extend(resultado[0])
                salud[nombre] = resultado[-1]
                if nombre == "Portales de empresas":
                    enlaces.update(v["enlace"] for v in resultado[0])
                    leidas.update(resultado[1])
            except Exception as e:
                salud[nombre] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return crudas, enlaces, leidas, salud
