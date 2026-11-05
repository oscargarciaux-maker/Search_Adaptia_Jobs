"""Búsquedas gratuitas adicionales para roles bajo meta, con límites y sin repetir entregas."""
from concurrent.futures import ThreadPoolExecutor

from buscador import cobertura
from buscador.fuentes import getonbrd, indeed, linkedin_publico
from buscador.http import Cliente


def buscar(mapa, activos, estado, hoy, ronda, cfg, dias_maximos=30):
    prioritarias = {f["id"] for f in mapa}
    limite = cfg.get("minutos_por_fuente", 3) * 60
    desfase = 4 * ronda  # nuevas variantes en cada ronda, sin volver a la misma consulta

    def linkedin():
        return linkedin_publico.buscar(Cliente(pausa=(1, 2.5)), mapa, activos, estado.setdefault("linkedin", {}),
                                       cfg.get("linkedin_busquedas", 18), hoy=hoy,
                                       max_fichas=cfg.get("linkedin_fichas", 60), max_dias=dias_maximos,
                                       limite_segundos=limite, prioritarias=prioritarias, desfase_terminos=desfase)

    def fuente_indeed():
        return indeed.buscar(mapa, [c for c, _ in activos], estado.setdefault("indeed", {}),
                             cfg.get("indeed_busquedas", 6), hoy=hoy, max_dias=dias_maximos,
                             limite_segundos=limite, prioritarias=prioritarias, desfase_terminos=desfase)

    def gob():
        terminos = [q for f in mapa for q in cobertura.rotar(cobertura.consultas(f), hoy, 2, desfase=desfase)]
        return getonbrd.buscar(Cliente(pausa=(0.3, 0.8)), terminos[:cfg.get("getonbrd_busquedas", 6)])

    crudas, salud = [], {}
    with ThreadPoolExecutor(3) as ex:
        tareas = [(nombre, ex.submit(funcion)) for nombre, funcion in
                  (("LinkedIn", linkedin), ("Indeed", fuente_indeed), ("Get on Board", gob))]
        for nombre, tarea in tareas:
            try:
                datos, stats = tarea.result()
                crudas.extend(datos)
                salud[nombre] = stats
            except Exception as e:  # una fuente no anula los otros refuerzos
                salud[nombre] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return crudas, salud


def completar(vacantes, entregadas, hoy, cfg_entrega, cfg_refuerzo, mapa, recoger, incorporar, iniciales=None):
    """Reevalúa después de cada ronda; nunca marca entregadas ni cambia restricciones para cumplir una cifra."""
    from buscador import entrega
    rondas = []
    for numero in range(1, cfg_refuerzo.get("rondas", 2) + 1):
        _, evaluacion = entrega.elegir(vacantes, entregadas, hoy, cfg_entrega, iniciales=iniciales)
        faltantes = {rid: r["faltan"] for rid, r in evaluacion["roles"].items() if r["faltan"]}
        if not faltantes:
            break
        familias = {f for rol in cfg_entrega["roles"] if rol["id"] in faltantes for f in rol["familias"]}
        nuevas, fuentes = recoger([f for f in mapa if f["id"] in familias], numero)
        vacantes = incorporar(vacantes, nuevas)
        rondas.append({"ronda": numero, "faltantes_antes": faltantes, "crudas": len(nuevas), "fuentes": fuentes})
    return vacantes, rondas
