"""Búsquedas gratuitas adicionales para roles bajo meta, con límites y sin repetir entregas."""
from concurrent.futures import ThreadPoolExecutor

from buscador import cobertura, normalizar
from buscador.fuentes import getonbrd, indeed, linkedin_publico, publicaciones_apify
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
                  max_busquedas=0):
    """Contrato v11: Apify solo donde falta. Para cada perfil por debajo del mínimo (los de más déficit primero) busca
    con los términos de su cargo —incluidos los cercanos— en su país y en las remotas abiertas a él, en vez de rotar
    combinaciones a ciegas. `buscar_apify(combinaciones)` devuelve (crudas, estadísticas)."""
    if max_busquedas <= 0:
        # P-16.2: apagado por defecto (`apify.rescate_busquedas: 0`): traía las mismas fichas que LinkedIn gratis (147
        # de 154 ya recibidas el 28 nov) y el crédito va entero a los posts.
        return vacantes, {"omitida": "rescate formal apagado (apify.rescate_busquedas = 0): el crédito va a los posts"}
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


def terminos_post(familia, idioma):
    """P-16.2: nombres del cargo para buscar posts en `idioma`, sin los cercanos (otro oficio) y solo de dos palabras o
    más si los hay (un post solo cuenta si nombra el cargo con una frase del mapa: `cargo_de`; «QA» a secas trae de
    todo). En español se alternan los títulos en español y los demás (un post en español suele nombrar el cargo en
    inglés: «Buscamos Product Designer»); en inglés, sin los títulos en español. Los términos ampliados de la P-14.2
    llegan solos: entran en `consultas` y `consultas_es` del cargo."""
    en_es = list(familia.get("consultas_es") or [])
    generales = [t for campo in ("consultas", "exactos", "similares") for t in familia.get(campo) or []]
    if idioma == "en":
        claves_es = {normalizar.titulo_base(t) for t in en_es}
        candidatos = [t for t in generales if normalizar.titulo_base(t) not in claves_es]
    else:
        candidatos = _intercalar([en_es, generales])
    salida, vistas = [], set()
    for t in candidatos:
        clave = normalizar.titulo_base(t)
        if clave and clave not in vistas:
            vistas.add(clave)
            salida.append(t)
    frases = [t for t in salida if len(normalizar.titulo_base(t).split()) > 1]
    return frases or salida


def consultas_de_perfil(familia, perfil, hoy):
    """P-16.2: consultas de posts para una persona, de la más útil a la menos, alternando sus idiomas: los nombres
    principales del cargo (en español, el título en español y el general) y uno más que rota cada día (así, en unos
    días, se prueban todos). Quien acepta remoto busca con una forma de decirlo en su idioma («remoto», «teletrabajo»,
    «trabajo desde casa»; «remote», «work from home») que rota por día y por consulta, sin sumar consultas; quien
    acepta además oficina, también sin modalidad. Solo cargo, idioma y modalidad: nunca su país, su ciudad ni nada
    suyo."""
    idiomas = [i for i in ("es", "en") if i in (perfil.get("idiomas") or ("es", "en"))]
    modalidades = set(perfil.get("modalidades") or ())
    con_remoto = "remoto" in modalidades
    sin_modalidad = not modalidades or bool(modalidades - {"remoto"})  # acepta oficina (o no lo dice)
    modos = [True] * con_remoto + [False] * sin_modalidad
    por_idioma = []
    for idioma in idiomas:
        terminos = terminos_post(familia, idioma)
        fijos = 2 if idioma == "es" else 1
        elegidos = terminos[:fijos] + cobertura.rotar(terminos[fijos:], hoy, 1)
        formas = publicaciones_apify.REMOTO_POST[idioma]
        por_idioma.append([publicaciones_apify.consulta_post(
            t, idioma, cobertura.rotar(formas, hoy, 1, desfase=k)[0] if remoto else False)
            for k, t in enumerate(elegidos) for remoto in modos])
    return _intercalar(por_idioma)


def _intercalar(listas):
    """Una de cada lista por vuelta, sin repetir."""
    salida = []
    for i in range(max((len(x) for x in listas), default=0)):
        for lista in listas:
            if i < len(lista) and lista[i] not in salida:
                salida.append(lista[i])
    return salida


def rescate_posts(vacantes, entregadas, hoy, cfg_entrega, mapa, buscar_posts, incorporar, iniciales=None,
                  max_consultas=12):
    """Contrato v11 (segunda parte) y P-16.2: el crédito de Apify va a los posts de LinkedIn (el mercado oculto) para
    los perfiles bajo el umbral del rescate. Primero quien hoy va en 0; después quien vive en un país sin fuente local;
    después el de más déficit. Cada persona aporta sus consultas (`consultas_de_perfil`) y se toman por turnos, una de
    cada una por vuelta, hasta `max_consultas`. Una ficha formal enlazada entra como vacante normal; un post sin ficha
    queda en la lista de posts (nunca en el inventario, el cupo ni `ofertas`). `buscar_posts(consultas, familias,
    empresas_pais)` devuelve (formales, posts, estadísticas). Devuelve (vacantes, estadísticas solo con conteos, posts
    aptos)."""
    from buscador import contrato, entrega
    from panel.afinidad import RESCATE_BAJO
    elegidas, _ = entrega.elegir(vacantes, entregadas, hoy, cfg_entrega, iniciales=iniciales)
    deficit = entrega.deficit_por_perfil(elegidas, cfg_entrega["roles"], hoy)
    if not deficit:
        return vacantes, {"perfiles_con_deficit": 0, "omitida": "todos los perfiles llegan al mínimo"}, []
    por_id = {f["id"]: f for f in mapa}
    sin_local = sin_fuente_local(cfg_entrega["roles"], deficit)
    en_cero = {pid for pid, n in deficit.items() if n >= RESCATE_BAJO}  # hoy no tiene ninguna
    pedidos = sorted([((p["id"] not in en_cero, p["id"] not in sin_local, -deficit[p["id"]]), rol, p)
                      for rol in cfg_entrega["roles"] for p in rol.get("_perfiles") or [] if p["id"] in deficit],
                     key=lambda x: x[0])
    por_perfil, validas = [], set()
    for _, rol, p in pedidos:
        familia = por_id.get(next(iter(rol.get("familias") or []), None))  # en modo panel, un cargo = una familia
        if familia:
            validas.add(familia["id"])
            por_perfil.append(consultas_de_perfil(familia, p, hoy))
    consultas = _intercalar(por_perfil)[:max_consultas]
    formales, posts, stats = buscar_posts(consultas, validas, publicaciones_apify.paises_por_empresa(vacantes))
    if formales:
        vacantes = incorporar(vacantes, formales)
    posts = [p for p in posts if not contrato.entregable_post(p)]
    return vacantes, {"perfiles_con_deficit": len(deficit), "perfiles_en_cero": len(en_cero), "consultas": len(consultas),
                      **{k: v for k, v in stats.items() if k in ("publicaciones", "fichas_formales", "posts", "descartadas",
                                                                  "ubicacion_deducida", "ubicacion_sin_confirmar",
                                                                  *CAMPOS_GASTO)}}, posts
