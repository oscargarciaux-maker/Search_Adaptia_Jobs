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
        # Contrato v49: también un título en español por cargo (para quien solo acepta español), sin repetir.
        terminos += [q for f in mapa for q in cobertura.rotar(f.get("consultas_es") or [], hoy, 1, desfase=desfase)
                     if q not in terminos]
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


def completar(vacantes, entregadas, hoy, cfg_entrega, cfg_refuerzo, mapa, recoger, incorporar, iniciales=None,
              medir=None):
    """Reevalúa después de cada ronda; nunca marca entregadas ni cambia restricciones para cumplir una cifra.
    `medir(texto)` (P-12.3, opcional) es un administrador de contexto que mide cuánto tarda cada reevaluación: solo
    recibe texto fijo con el número de ronda."""
    from contextlib import nullcontext
    from buscador import entrega
    medir = medir or (lambda texto: nullcontext({}))
    rondas = []
    for numero in range(1, cfg_refuerzo.get("rondas", 2) + 1):
        with medir(f"Refuerzo, ronda {numero}: evaluar faltantes"):
            _, evaluacion = entrega.elegir(vacantes, entregadas, hoy, cfg_entrega, iniciales=iniciales)
        # Contrato v11: también refuerza un cargo con cupo cubierto si alguno de sus perfiles no llega al umbral del
        # rescate (`cobertura.rescate_bajo`; P-11.3).
        faltantes = {rid: r["faltan"] or r.get("faltan_para_minimo", 0) for rid, r in evaluacion["roles"].items()
                     if r["faltan"] or r.get("perfiles_bajo_minimo")}
        if not faltantes:
            break
        familias = {f for rol in cfg_entrega["roles"] if rol["id"] in faltantes for f in rol["familias"]}
        nuevas, fuentes = recoger([f for f in mapa if f["id"] in familias], numero)
        vacantes = incorporar(vacantes, nuevas)
        rondas.append({"ronda": numero, "faltantes_antes": faltantes, "crudas": len(nuevas), "fuentes": fuentes})
    return vacantes, rondas


# Lo que el rescate y los posts devuelven de su gasto (8.2): solo cifras y motivos, nunca perfiles ni cargos.
CAMPOS_GASTO = ("error", "clave_invalida", "omitida", "credito_agotado", "aviso", "usd_reservado", "usd_reportado")


def sin_fuente_local(roles, deficit):
    """8.2: ids de los perfiles con déficit que viven (o aceptan oficina) en un país que solo buscan LinkedIn, los
    portales de empresas y Get on Board (la regla de la 8.1/8.1b, `panel.ejecutor.fuentes_locales`; Indeed cuenta
    como local). Su gasto de Apify va primero. Se calcula una vez por perfil."""
    from panel.ejecutor import fuentes_locales
    from panel.huecos import paises_del_perfil
    from panel.modelos import Perfil
    perfiles = {p["id"]: p for rol in roles for p in rol.get("_perfiles") or [] if p["id"] in deficit}
    return {pid for pid, p in perfiles.items()
            if any(not fuentes_locales(c) for c in paises_del_perfil(Perfil.model_validate(p)))}


def rescate_apify(vacantes, entregadas, hoy, cfg_entrega, mapa, buscar_apify, incorporar, iniciales=None,
                  max_busquedas=4):
    """Contrato v11: Apify solo donde falta. Para cada perfil por debajo del mínimo (los de más déficit primero) busca
    con los términos de su cargo —incluidos los cercanos— en su país y en las remotas abiertas a él, en vez de rotar
    combinaciones a ciegas. `buscar_apify(combinaciones)` devuelve (crudas, estadísticas)."""
    from buscador import entrega
    from panel.ejecutor import lugares_perfil
    from panel.modelos import Perfil
    elegidas, _ = entrega.elegir(vacantes, entregadas, hoy, cfg_entrega, iniciales=iniciales)
    deficit = entrega.deficit_por_perfil(elegidas, cfg_entrega["roles"], hoy)
    if not deficit:
        return vacantes, {"perfiles_con_deficit": 0, "omitida": "todos los perfiles llegan al mínimo"}
    por_id = {f["id"]: f for f in mapa}
    sin_local = sin_fuente_local(cfg_entrega["roles"], deficit)
    # 8.2: primero quien está bajo el umbral del rescate (`rescate_bajo`) sin fuente local; después el resto con déficit, el de más
    # déficit primero.
    pedidos = sorted([((p["id"] not in sin_local, -deficit[p["id"]]), rol, p) for rol in cfg_entrega["roles"]
                      for p in rol.get("_perfiles") or [] if p["id"] in deficit], key=lambda x: x[0])
    combinaciones, vistas = [], set()
    for _, rol, p in pedidos:
        familia = por_id.get(rol["familias"][0])
        if not familia:
            continue
        consultas = cobertura.consultas(familia)
        if set(p.get("idiomas") or []) == {"es"} and familia.get("consultas_es"):
            # Contrato v44: quien solo habla español busca primero con los títulos en español.
            consultas = familia["consultas_es"] + [c for c in consultas if c not in familia["consultas_es"]]
        for lugar, params in lugares_perfil(Perfil.model_validate(p)).items():
            if (rol["id"], lugar) not in vistas:
                vistas.add((rol["id"], lugar))
                combinaciones.append((rol["id"], consultas, lugar, params))
    crudas, stats = buscar_apify(combinaciones[:max_busquedas])
    if crudas:
        vacantes = incorporar(vacantes, crudas)
    return vacantes, {"perfiles_con_deficit": len(deficit), "faltan_para_minimo": sum(deficit.values()),
                      "perfiles_sin_fuente_local": len(sin_local),
                      "busquedas": stats.get("busquedas", 0), "avisos": len(crudas),
                      **{k: stats[k] for k in CAMPOS_GASTO if k in stats}}


def rescate_posts(vacantes, entregadas, hoy, cfg_entrega, mapa, buscar_posts, incorporar, iniciales=None,
                  max_consultas=8):
    """Contrato v11 (segunda parte): para los perfiles que siguen bajo el mínimo tras el rescate formal, busca posts de
    LinkedIn que anuncian su cargo. Una ficha formal enlazada entra como vacante normal; un post sin ficha queda en la
    lista de posts (nunca en el inventario, el cupo ni `ofertas`). `buscar_posts(consultas, familias)` devuelve
    (formales, posts, estadísticas). Devuelve (vacantes, estadísticas solo con conteos, posts aptos)."""
    from buscador import contrato, entrega
    from buscador import paises
    from buscador.fuentes.publicaciones_apify import consultas_post, paises_por_empresa
    elegidas, _ = entrega.elegir(vacantes, entregadas, hoy, cfg_entrega, iniciales=iniciales)
    deficit = entrega.deficit_por_perfil(elegidas, cfg_entrega["roles"], hoy)
    if not deficit:
        return vacantes, {"perfiles_con_deficit": 0, "omitida": "todos los perfiles llegan al mínimo"}, []
    por_id = {f["id"]: f for f in mapa}
    # 8.2: primero los cargos con alguien bajo el umbral del rescate (`rescate_bajo`) sin fuente local; dentro, el de
    # más déficit (como antes).
    sin_local = sin_fuente_local(cfg_entrega["roles"], deficit)
    roles = sorted((r for r in cfg_entrega["roles"] if any(p["id"] in deficit for p in r.get("_perfiles") or [])),
                   key=lambda r: (not any(p["id"] in sin_local for p in r.get("_perfiles") or []),
                                  -sum(deficit.get(p["id"], 0) for p in r.get("_perfiles") or [])))
    consultas, validas = [], set()
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    for rol in roles:
        # Contrato v28: también posts que nombran dónde vive quien va corto (o «remoto»), así llegan con ubicación.
        lugares = []
        for p in sorted(rol.get("_perfiles") or [], key=lambda p: p["id"] not in sin_local):
            if p["id"] in deficit:
                lugares += [nombres.get(p.get("vive_en"), "")] + (["remoto"] if "remoto" in (p.get("modalidades") or []) else [])
        lugares = [x for x in dict.fromkeys(lugares) if x][:2]
        for fid in rol["familias"]:
            if fid in por_id:
                validas.add(fid)
                consultas += consultas_post(cobertura.consultas(por_id[fid]), lugares=lugares)
    consultas = list(dict.fromkeys(consultas))[:max_consultas]
    formales, posts, stats = buscar_posts(consultas, validas, paises_por_empresa(vacantes))
    if formales:
        vacantes = incorporar(vacantes, formales)
    posts = [p for p in posts if not contrato.entregable_post(p)]
    return vacantes, {"perfiles_con_deficit": len(deficit), "consultas": len(consultas),
                      **{k: v for k, v in stats.items() if k in ("publicaciones", "fichas_formales", "posts", "descartadas",
                                                                  "ubicacion_deducida", "ubicacion_sin_confirmar",
                                                                  *CAMPOS_GASTO)}}, \
        posts
