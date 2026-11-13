"""Bodega nocturna: recoge de todas las fuentes, limpia, guarda 30 días y publica. Sin IA.

Uso:  python -m buscador.bodega --salida <carpeta>  [--modo diario|inicial] [--consulta "texto" --pais CO]
<carpeta> trae la corrida anterior en <carpeta>/trabajo/ (bodega.json.gz, estado.json, empresas_ats.csv) y recibe la
nueva, más la página y los datos publicados (ver publicar.py). El flujo bodega.yml la sube a la rama `publicado`.
"""
import argparse
from copy import deepcopy
import gzip
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from buscador import calidad, contrato, cobertura, enlaces, familias, normalizar, paises, tiempos, vacante
from buscador.fuentes import (ats, brave, computrabajo, getonbrd, indeed, linkedin_apify, linkedin_publico,
                              publicaciones_apify, remotos)
from buscador.http import Cliente

RAIZ = Path(__file__).resolve().parent.parent


_config_operativa = None


def afinidad_vigente(original, actual, rol, roles, inventario):
    """¿La vacante elegida hoy para `rol` le sigue sirviendo? Sale de la validación final (13 nov).
    - Si ya no está en el inventario (cerrada o vieja), no.
    - Si entró por ampliación (contratos v9 y v11: filtros relajados para llegar a 5), sí: entró así a propósito y va
      marcada; compararla con los filtros estrictos daba una falsa alarma (QA, 13 nov).
    - Si encaja igual de bien en varios cargos, vale cualquiera de los empatados: esas vacantes se reparten por turnos
      entre los cargos, y comparar solo con el primero daba otra falsa alarma (UX/UI frente a Product Designer)."""
    if actual["id"] not in inventario:
        return False
    if original.get("_ampliacion"):
        return True
    from buscador import entrega
    empatados, _ = entrega.roles_de(actual, roles)
    return any(r["id"] == rol["id"] for r in empatados)


def config():
    if _config_operativa is not None:
        return deepcopy(_config_operativa)
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
    temporal = ruta.with_name(ruta.name + ".tmp")
    if comprimido:
        with gzip.open(temporal, "wt", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    else:
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
    temporal.replace(ruta)


def _paises_activos(cfg):
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    return [(c, nombres[c]) for c in cfg["paises_activos"] if c in nombres]


def _fecha_de(v):
    return v.get("fecha_publicacion") or v.get("visto_primera_vez") or ""


def recoger(cfg, estado, hoy, trabajo, solo_mapa=None, control_apify=None, previas=None):
    """Corre las fuentes en paralelo (cada una con su cliente y su parte del estado). Devuelve
    (crudas, empresas para probar, enlaces de portales leídos, empresas cuyos portales se leyeron, salud)."""
    p = cfg["presupuestos"]
    mapa = solo_mapa or familias.mapa()
    activos = _paises_activos(cfg)
    limite = p["minutos_por_fuente"] * 60
    from buscador import entrega
    cfg_entrega = entrega.config()
    prioritarias = {f for r in cfg_entrega["roles"] for f in r["familias"]}
    from buscador.apify import Presupuesto
    control_apify = control_apify or Presupuesto(
        _leer_json(trabajo / "apify_presupuesto.json", {}), hoy,
        mensual=cfg["apify"].get("tope_mensual_usd", 5), corrida=cfg["apify"].get("tope_por_corrida_usd", 3),
        guardar=lambda datos: _guardar_json(trabajo / "apify_presupuesto.json", datos))
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
        t0 = time.monotonic()
        cliente = Cliente(pausa=tuple(p["pausa_linkedin"]))
        crudas, stats = linkedin_publico.buscar(cliente, mapa, activos, estado["linkedin"],
                                                p["linkedin_busquedas"], hoy=hoy, max_fichas=p["linkedin_fichas"],
                                                max_dias=cfg["dias_maximos"], limite_segundos=limite,
                                                prioritarias=prioritarias)
        if previas and p.get("linkedin_relectura", 0) and not solo_mapa:
            extra, stats["relectura"] = linkedin_publico.completar_descripciones(
                cliente, previas, p["linkedin_relectura"], hoy=hoy, max_dias=cfg["dias_maximos"],
                limite_segundos=max(0, limite - (time.monotonic() - t0)), prioritarias=prioritarias)
            crudas = crudas + extra
        return crudas, stats

    def f_indeed():
        return indeed.buscar(mapa, [c for c, _ in activos], estado["indeed"], p["indeed_busquedas"], hoy=hoy,
                             max_dias=cfg["dias_maximos"], limite_segundos=limite, prioritarias=prioritarias)

    def f_apify():
        combos = linkedin_publico.combinaciones(mapa, activos)
        return linkedin_apify.buscar(Cliente(), cfg["apify"]["actor_linkedin"], combos, estado["apify"], hoy,
                                     presupuesto=p["apify_busquedas"], max_dias=cfg["dias_maximos"],
                                     limite_segundos=limite, prioritarias=prioritarias, control_gasto=control_apify,
                                     max_por_busqueda=cfg["apify"].get("ofertas_por_busqueda", 20),
                                     tope_consulta_usd=cfg["apify"].get("tope_consulta_usd", 0.025),
                                     build=cfg["apify"].get("build_linkedin", "0.0.61"))

    def f_publicaciones():
        maximo = 6 if p.get("minutos_por_fuente", 50) <= 3 else cfg["apify"].get("publicaciones_por_dia", 72)
        if cfg["apify"].get("publicaciones_por_dia", 0) <= 0:
            return [], {"omitida": "crédito de Apify reservado a ofertas formales de LinkedIn"}
        return publicaciones_apify.buscar(Cliente(), cfg["apify"].get("actor_publicaciones", ""),
                                          cfg_entrega.get("consultas_publicaciones", []), prioritarias, hoy,
                                          maximo=maximo, control_gasto=control_apify)

    def f_remotos():
        consultas = sorted({c for f in mapa for c in f["consultas"][:1]})
        return remotos.buscar(Cliente(pausa=(0.3, 0.8)), consultas, estado["remotos_cache"],
                              max_paginas=p["remotos_paginas"])

    def f_getonbrd():
        combinaciones = [(f["id"], cobertura.rotar(cobertura.consultas(f), hoy, 1)[0], "GLOBAL") for f in mapa]
        turnos = cobertura.repartir(combinaciones, {}, hoy, prioritarias)
        return getonbrd.buscar(Cliente(pausa=(0.3, 0.8)), [c[1] for c in turnos[:p["getonbrd_busquedas"]]])

    def f_computrabajo():
        if not p.get("computrabajo_busquedas", 0):
            return [], {"omitida": "sin presupuesto"}
        return computrabajo.buscar(Cliente(pausa=(0.6, 1.4)), mapa, activos, estado.setdefault("computrabajo", {}),
                                   p["computrabajo_busquedas"], hoy=hoy, max_fichas=p.get("computrabajo_fichas", 150),
                                   limite_segundos=limite, prioritarias=prioritarias)

    filas_ats = ats.leer_lista(ats.RUTA, trabajo / "empresas_ats.csv")

    def f_ats():
        filas = filas_ats
        if cfg.get("control_dirigido"):
            empresas = {normalizar.empresa(x) for x in cfg.get("empresas_objetivo",[])}
            filas = [f for f in filas if normalizar.empresa(f.get("empresa","")) in empresas]
            if not filas:
                return [], set(), {"omitida": "modo dirigido: aún no hay portales asociados a los cargos"}
        return ats.buscar(Cliente(pausa=(0.05, 0.2)), filas, limite_segundos=limite, prioritarias=prioritarias)

    with ThreadPoolExecutor(8) as ex:
        tareas = {n: ex.submit(correr, n, f) for n, f in [("LinkedIn", f_linkedin), ("Indeed", f_indeed),
                                                            ("LinkedIn (Apify)", f_apify), ("Tableros remotos", f_remotos),
                                                            ("Get on Board", f_getonbrd), ("Portales de empresas", f_ats),
                                                            ("Publicaciones LinkedIn (Apify)", f_publicaciones),
                                                            ("Computrabajo", f_computrabajo)]}
        resultados = {n: t.result() for n, t in tareas.items()}
    crudas, empresas = [], set()
    for n, r in resultados.items():
        if not r:
            continue
        crudas.extend(r[0])
        if n == "Tableros remotos" and not cfg.get("control_dirigido"):
            empresas |= set(r[1])
    ats_crudas = resultados.get("Portales de empresas") or [[], set(), {}]
    enlaces_ats = {c["enlace"] for c in ats_crudas[0]}
    empresas_leidas = ats_crudas[1] if len(ats_crudas) == 3 else set()
    # Empresas de LinkedIn e Indeed con cargos del mapa: candidatas a tener portal propio
    for c in crudas:
        if c.get("fuente") in ("LinkedIn", "Indeed", "LinkedIn (Apify)", publicaciones_apify.NOMBRE) and c.get("empresa") and familias.clasificar(c["titulo"]):
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


def limpiar(previas, crudas, hoy, dias_maximos, enlaces_ats, empresas_leidas, consulta="", retiradas=None):
    """Convierte, junta con lo anterior, quita viejas y cerradas. Devuelve (vacantes, títulos sin familia, conteos)."""
    sin_familia = Counter()
    nuevas, fuera, descartes = [], [], Counter()
    def retirar(v, estado, razon):
        if retiradas is not None:
            retiradas.append((v, estado, razon))
    for c in crudas:
        v = vacante.crear(c.get("titulo"), c.get("empresa"), c.get("enlace"), c.get("fuente", ""),
                          ubicacion=c.get("ubicacion", ""), descripcion=c.get("descripcion", ""), fecha=c.get("fecha", ""),
                          remoto=c.get("remoto"), enlace_directo=c.get("enlace_directo", ""), hoy=hoy,
                          consulta=consulta, publicada_en=c.get("publicada_en", ""),
                          fecha_origen=c.get("fecha_origen", ""))
        if v is None:
            if c.get("titulo") and enlaces.sirve(c.get("enlace", "")) and not familias.clasificar(c["titulo"]):
                sin_familia[normalizar.titulo_base(c["titulo"])] += 1
                descartes["sin familia en el mapa"] += 1
            else:
                descartes["sin enlace donde postular"] += 1
            continue
        if not v["paises"]:
            fuera.append(v)
            continue
        nuevas.append(v)
    limite = (date.fromisoformat(hoy) - timedelta(days=dias_maximos)).isoformat()
    previas_validas = []
    for v in previas:
        motivo = calidad.motivo(v["titulo"], v["enlace"], v.get("fuente", ""))
        if motivo:
            descartes[motivo] += 1
            retirar(v, "archived", motivo)
        else:
            previas_validas.append(vacante.reetiquetar(dict(v)))
    # Una copia que ahora dice "fuera de la cobertura" para un enlace ya guardado es un cambio real de esa fuente:
    # se une para reemplazar su observación anterior; si nada más respalda la vacante, sale abajo sin países.
    conocidos = {contrato.url_limpia(u) for v in previas_validas
                 for u in (v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])) if u}
    for v in fuera:
        if {contrato.url_limpia(u) for u in (v["enlace"], v["enlace_directo"]) if u} & conocidos:
            nuevas.append(v)
        else:
            descartes["no se puede aplicar desde LATAM"] += 1
    vistas_hoy = {v["id"] for v in nuevas}
    todas = vacante.juntar(previas_validas + nuevas)
    ids_unidos = {v["id"] for v in todas}
    destinos = {identificador: v["id"] for v in todas for identificador in v.get("_ids_fusionados", [])}
    for v in previas_validas:
        if v["id"] not in ids_unidos:
            retirar(dict(v, duplicada_de=destinos.get(v["id"])), "archived", "fusionada con otra fuente")
    salida = []
    for v in todas:
        if _fecha_de(v) and _fecha_de(v) < limite:
            descartes["más de %d días" % dias_maximos] += 1
            retirar(v, "archived", "fuera de la ventana de búsqueda")
            continue
        # Portal de la empresa leído hoy y el aviso ya no está: se cerró
        de_portal = any(enlaces.tipo(u) == "original" for u in (v["enlace"], v["enlace_directo"]))
        if de_portal and v["empresa"] in empresas_leidas and v["id"] not in vistas_hoy and \
                not ({v["enlace"], v["enlace_directo"]} & enlaces_ats):
            descartes["cerrada en el portal de la empresa"] += 1
            retirar(v, "closed", "ausente de un listado completo de la empresa")
            continue
        if not v.get("paises"):
            retirar(v, "archived", "sin elegibilidad regional")
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
        cfg["apify"]["actor_linkedin"] = ""
        cfg["apify"]["publicaciones_por_dia"] = 0
    hoy = hoy or datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
    if not prueba and not consulta:
        from buscador import supabase
        supabase.exigir_conexion()
    usar_central = not prueba and os.environ.get("ESTADO_SUPABASE_ACTIVO", "").lower() == "true"
    usar_catalogo = usar_central or modo == "incremental" or os.environ.get("CATALOGO_ACTIVO", "").lower() == "true"
    if usar_catalogo and not prueba:
        from buscador import supabase
        supabase.exigir_catalogo()
    salida = Path(salida)
    trabajo = salida / "trabajo"
    central = None
    if usar_central:
        from buscador.estado_operativo import Central
        central = Central(_leer_json(trabajo / "apify_presupuesto.json", {}),
                          lambda datos: _guardar_json(trabajo / "apify_presupuesto.json", datos))
    def recuperar_cola(nombre, archivo):
        local = _leer_json(trabajo / archivo, {})
        guardar = lambda datos: _guardar_json(trabajo / archivo, datos)
        return central.cola(nombre, local, guardar) if central else (local, guardar)
    pendientes_catalogo, guardar_catalogo = recuperar_cola("catalogo", "pendientes_catalogo.json")
    pendientes_v1, guardar_v1 = recuperar_cola("ofertas", "pendientes_supabase.json")
    pendientes_registro, guardar_registro = recuperar_cola("registro", "pendientes_registro.json")
    estado = _leer_json(trabajo / "estado.json", {})
    previas = _leer_json(trabajo / "bodega.json.gz", [])
    salud_anterior = _leer_json(salida / "datos" / "salud.json", {})
    memoria_db = {}
    lote_previo = _leer_json(trabajo / "lote_entrega.json", {})
    if central:
        from buscador import supabase
        canonico = supabase.leer_lote(hoy)
        for rol, lista in lote_previo.get("elegidas", {}).items() if lote_previo.get("fecha") == hoy else []:
            ids = {v["id"] for filas in canonico["elegidas"].values() for v, _ in filas}
            canonico["elegidas"].setdefault(rol, []).extend((v, g) for v, g in lista if v["id"] not in ids)
        lote_previo = canonico
        lote_previo = central.cargar_lote(hoy, lote_previo)
    def guardar_lote(datos):
        _guardar_json(trabajo / "lote_entrega.json", datos)
        if central:
            central.guardar_lote(datos)
    control_central = central.control_apify(hoy, cfg["apify"].get("tope_mensual_usd", 5),
        cfg["apify"].get("tope_por_corrida_usd", 3)) if central else None
    argumentos_central = {"control_apify": control_central} if central else {}
    if usar_catalogo and not prueba and not consulta and modo != "incremental":
        from buscador import supabase
        memoria_db, lote_db = supabase.leer_entregas(hoy)
        for rol, lista in lote_previo.get("elegidas", {}).items() if lote_previo.get("fecha") == hoy else []:
            existentes = {v["id"] for v, _ in lote_db["elegidas"].get(rol, [])}
            lote_db["elegidas"].setdefault(rol, []).extend((v, g) for v, g in lista if v["id"] not in existentes)
        from buscador import entrega
        recuperables = {h for lista in lote_db["elegidas"].values() for v, _ in lista for h in entrega.huellas(v)}
        if any(u not in recuperables for u in lote_db.pop("v1_sin_registro_hoy", [])):
            raise RuntimeError("Hay filas históricas de hoy sin registro de selección ni lote recuperable. "
                               "Recuperar el estado de trabajo/artefacto y completar el registro antes de continuar; "
                               "no se inició otra selección ni búsqueda.")
        lote_previo = lote_db
    # Lo ya registrado hoy es inmutable: la entrega recibe una copia que ningún paso intermedio (verificación,
    # refuerzo) puede alterar.
    lote_registrado = deepcopy(lote_previo)
    if central:
        _guardar_json(trabajo / "lote_entrega.json", lote_previo)
        memoria_db.update(central.recuperar_pendientes(pendientes_v1, guardar_v1, pendientes_registro, guardar_registro))
    if modo == "inicial":
        estado = {k: v for k, v in estado.items() if k not in ("linkedin", "indeed", "apify")}
    solo = None
    if modo == "incremental":
        from buscador import incremental
        crudas, enlaces_ats, leidas, salud = incremental.recoger(cfg, estado, hoy, trabajo, previas=previas)
    elif consulta:
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
                                                      hoy, trabajo, solo_mapa=solo, **argumentos_central)
    else:
        crudas, enlaces_ats, leidas, salud = recoger(cfg, estado, hoy, trabajo, previas=previas, **argumentos_central)
    retiradas = []
    vacantes, sin_familia, descartes = limpiar(previas, crudas, hoy, cfg["dias_maximos"], enlaces_ats, leidas,
                                               consulta=consulta or "", retiradas=retiradas)
    from buscador import verificar_enlaces
    cache_enlaces = _leer_json(trabajo / "verificacion_enlaces.json", {})
    entregadas_revision = _leer_json(trabajo / "entregadas.json", {})
    entregadas_revision.update(memoria_db)
    cfg_revision = dict(cfg.get("verificacion_enlaces", {}))
    if prueba:
        cfg_revision.update(vacantes_por_corrida=12, vacantes_por_captura=12, segundos_corrida=30, segundos_captura=30)
    clave_n, clave_s = (("vacantes_por_captura", "segundos_captura") if modo == "incremental"
                        else ("vacantes_por_corrida", "segundos_corrida"))
    cfg_revision.setdefault(clave_n, 40 if modo == "incremental" else 300)
    cfg_revision.setdefault(clave_s, 90 if modo == "incremental" else 240)
    resumen_revision = {}
    from buscador import entrega
    config_entrega = entrega.config()
    roles_actuales = config_entrega["roles"]
    def comprobar_destinos(lista):
        nonlocal resumen_revision
        t0 = time.monotonic()
        resumen_revision = verificar_enlaces.preparar(lista, entregadas_revision, hoy, cache_enlaces,
            lote=lote_previo, incremental=modo == "incremental", cfg=cfg_revision)
        cfg_revision[clave_n] = max(0, cfg_revision[clave_n] - resumen_revision["candidatas_programadas"])
        cfg_revision[clave_s] = max(0, cfg_revision[clave_s] - (time.monotonic() - t0))
        _guardar_json(trabajo / "verificacion_enlaces.json", cache_enlaces)
        # También sincronizar cierres de seleccionadas que ya salieron del inventario activo.
        ids_lista = {v["id"] for v in lista}
        if lote_previo.get("fecha") == hoy:
            for grupo in lote_previo.get("elegidas", {}).values():
                for historica, _ in grupo:
                    if historica["id"] not in ids_lista:
                        actual = vacante.reetiquetar(dict(historica))
                        verificar_enlaces.anotar(actual, cache_enlaces)
                        if actual["verificacion"]["estado"] == "rechazada":
                            razon = actual["verificacion"]["motivo"]
                            retiradas.append((actual, "closed" if razon == "vacante cerrada" else "archived", razon))
        salida_verificada = []
        for v in lista:
            rol, _ = entrega.rol_de(v, roles_actuales)
            v["rol_entrega_actual"] = rol["id"] if rol else ""
            revision = v["verificacion"]
            if revision["estado"] == "rechazada":
                razon = revision["motivo"]
                retiradas.append((v, "closed" if razon == "vacante cerrada" else "archived", razon))
                descartes[razon] += 1
            else:
                salida_verificada.append(v)
        return salida_verificada
    if cfg.get("decisiones_operador"):
        from buscador import confirmar_ubicacion
        salud["Decisiones del operador"] = {"aplicadas": confirmar_ubicacion.aplicar_operador(vacantes, cfg["decisiones_operador"])}
    if modo != "incremental" and not consulta and not prueba and cfg.get("confirmar_ubicacion", {}).get("fichas_por_corrida"):
        # Contrato v16: antes de dejar una vacante «por confirmar», leer el país en los datos estructurados de su ficha.
        from buscador import confirmar_ubicacion
        memoria_fichas = _leer_json(trabajo / "ubicacion_fichas.json", {})
        try:
            salud["Ubicación desde la ficha"] = confirmar_ubicacion.confirmar(
                vacantes, memoria_fichas, hoy, {f for r in roles_actuales for f in r["familias"]},
                maximo=cfg["confirmar_ubicacion"]["fichas_por_corrida"],
                segundos=cfg["confirmar_ubicacion"].get("segundos", 180))
        except Exception as e:  # noqa: BLE001 — confirmar es una ayuda; nunca tumba la noche
            salud["Ubicación desde la ficha"] = {"error": f"{type(e).__name__}"}
        limite = (date.fromisoformat(hoy) - timedelta(days=confirmar_ubicacion.VIGENCIA_DIAS * 2)).isoformat()
        _guardar_json(trabajo / "ubicacion_fichas.json", {u: d for u, d in memoria_fichas.items() if d.get("fecha", "") >= limite})
    vacantes = comprobar_destinos(vacantes)
    refuerzos = []
    posts_nuevos = []
    if modo != "incremental" and not consulta and not prueba and cfg.get("refuerzo", {}).get("rondas", 0):
        from buscador import entrega, refuerzo
        entregadas = _leer_json(trabajo / "entregadas.json", {})
        entregadas.update(memoria_db)
        def incorporar(anteriores, nuevas):
            resultado, sin_mapa, razones = limpiar(anteriores, nuevas, hoy, cfg["dias_maximos"], set(), set(),
                                                  retiradas=retiradas)
            sin_familia.update(sin_mapa)
            descartes.update(razones)
            return comprobar_destinos(resultado)
        vacantes, refuerzos = refuerzo.completar(
            vacantes, entregadas, hoy, entrega.config(), cfg["refuerzo"], familias.mapa(),
            lambda mapa, ronda: refuerzo.buscar(mapa, _paises_activos(cfg), estado, hoy, ronda,
                                                 cfg["refuerzo"], cfg["dias_maximos"]), incorporar,
            iniciales=lote_previo.get("elegidas", {}) if lote_previo.get("fecha") == hoy else None)
        if cfg.get("control_dirigido") and os.environ.get("APIFY_TOKEN"):
            from buscador.apify import Presupuesto
            from buscador.fuentes import linkedin_apify
            control = control_central or Presupuesto(
                _leer_json(trabajo / "apify_presupuesto.json", {}), hoy,
                mensual=cfg["apify"].get("tope_mensual_usd", 5), corrida=cfg["apify"].get("tope_por_corrida_usd", 3),
                guardar=lambda datos: _guardar_json(trabajo / "apify_presupuesto.json", datos))

            def buscar_apify(combinaciones):
                return linkedin_apify.buscar(Cliente(), cfg["apify"]["actor_linkedin"], combinaciones, {}, hoy,
                                             presupuesto=len(combinaciones), max_dias=cfg["dias_maximos"],
                                             limite_segundos=600, control_gasto=control, max_por_busqueda=10,
                                             tope_consulta_usd=cfg["apify"].get("tope_consulta_usd", 0.025),
                                             build=cfg["apify"].get("build_linkedin", "0.0.61"), ordenar=False)
            try:
                vacantes, salud["LinkedIn (Apify) rescate"] = refuerzo.rescate_apify(
                    vacantes, entregadas, hoy, entrega.config(), familias.mapa(), buscar_apify, incorporar,
                    iniciales=lote_previo.get("elegidas", {}) if lote_previo.get("fecha") == hoy else None,
                    max_busquedas=cfg["apify"].get("rescate_busquedas", 4))
            except Exception as e:  # noqa: BLE001 — el rescate nunca tumba la noche
                salud["LinkedIn (Apify) rescate"] = {"error": f"{type(e).__name__}: {e}"[:300]}
            # Contrato v11: posts de LinkedIn para quien sigue bajo el mínimo, con lo que quede del día de Apify.
            maximo_posts = cfg["apify"].get("posts_rescate", 0)
            if maximo_posts > 0 and not prueba:
                def buscar_posts(consultas, validas):
                    return publicaciones_apify.buscar_posts(Cliente(), cfg["apify"].get("actor_publicaciones", ""),
                                                            consultas, validas, hoy, maximo=maximo_posts,
                                                            control_gasto=control, max_dias=cfg["dias_maximos"])
                try:  # los posts traen el perfil o correo de quien publicó: solo van a Supabase, nunca a `trabajo/`
                    vacantes, salud["LinkedIn (Apify) posts"], posts_nuevos = refuerzo.rescate_posts(
                        vacantes, entregadas, hoy, entrega.config(), familias.mapa(), buscar_posts, incorporar,
                        iniciales=lote_previo.get("elegidas", {}) if lote_previo.get("fecha") == hoy else None)
                except Exception as e:  # noqa: BLE001
                    salud["LinkedIn (Apify) posts"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    if not prueba and not consulta and not vacantes and not retiradas:
        raise RuntimeError("La búsqueda no produjo un catálogo válido; se conserva el estado anterior.")
    _guardar_json(trabajo / "bodega.json.gz", vacantes, comprimido=True)
    _guardar_json(trabajo / "estado.json", estado)
    resumen_catalogo = None
    if usar_catalogo and not prueba:
        from buscador import catalogo, supabase
        # Memoria auxiliar de lo confirmado (huellas, sin datos de clientes): evita reescribir todo el catálogo cada hora.
        sincronizado = _leer_json(trabajo / "catalogo_sincronizado.json.gz", {})
        sincronizado = sincronizado if isinstance(sincronizado, dict) else {}
        resumen_catalogo = catalogo.sincronizar(vacantes, retiradas, pendientes_catalogo, supabase.subir_catalogo,
                                               guardar_catalogo, sincronizado=sincronizado)
        _guardar_json(trabajo / "catalogo_sincronizado.json.gz", sincronizado, comprimido=True)
        if not resumen_catalogo.get("pendientes") and not resumen_catalogo.get("errores"):
            resumen_catalogo["identidad"] = supabase.reconciliar_ofertas()
        if posts_nuevos:
            # Contrato v11: los posts van al catálogo privado con `tipo="post"`; el panel los asigna a perfiles con
            # déficit. Si la subida falla se pierden solo esos posts (la noche siguiente se buscan otros).
            filas_posts = [catalogo.fila(p, p.get("vista_en")) for p in posts_nuevos]
            if filas_posts:
                r = dict(supabase.subir_catalogo(filas_posts))
                resumen_catalogo["posts"] = {"enviados": len(filas_posts), "confirmados": len(r.pop("confirmadas", [])),
                                             "errores": len(r.get("errores") or [])}
    reintentos_centrales = {}
    if central and (modo == "incremental" or consulta):
        from buscador import supabase
        for nombre, pendientes, subir, guardar in (
            ("ofertas", pendientes_v1, supabase.subir, guardar_v1),
            ("registro", pendientes_registro, lambda filas: supabase.subir_catalogo(filas, tabla="entregas_diarias"), guardar_registro)):
            resultado = dict(subir(list(pendientes.values())))
            for identificador in resultado.pop("confirmadas", []):
                pendientes.pop(identificador, None)
            guardar(pendientes)
            reintentos_centrales[nombre] = dict(resultado, pendientes=len(pendientes))
        central.limpiar_lotes_confirmados()
    # Entrega diaria en el formato del contrato (no en una búsqueda profunda; en una prueba no se marca nada ni se sube)
    resumen_entrega = salud_anterior.get("entrega") if modo == "incremental" else None
    historico_entregas = salud_anterior.get("historico_entregas", []) if modo == "incremental" else []
    if not consulta and modo != "incremental":
        from buscador import entrega, supabase
        entregadas = _leer_json(trabajo / "entregadas.json", {})
        entregadas.update(memoria_db)
        capturada = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        registrar = None
        if usar_catalogo and not prueba:
            from buscador import catalogo
            def registrar(lote):
                r = catalogo.registrar_seleccion(lote, pendientes_registro,
                    lambda filas: supabase.subir_catalogo(filas, tabla="entregas_diarias"), guardar_registro)
                if central:
                    central.guardar_lote(lote)
                return r
        entregadas_antes = dict(entregadas)
        resumen_entrega = entrega.correr(vacantes, entregadas if not prueba else dict(entregadas), hoy, capturada,
                                         salida / "datos" / "entregas", subir=None if prueba else supabase.subir,
                                         pendientes=pendientes_v1,
                                         persistir=None if prueba else
                                         guardar_v1,
                                         lote=lote_registrado,
                                         persistir_lote=None if prueba else
                                         guardar_lote,
                                         registrar_seleccion=registrar)
        if not prueba:
            _guardar_json(trabajo / "entregadas.json", entregadas)
            historial = _leer_json(trabajo / "metricas_entrega.json", {})
            historico_entregas = entrega.registrar_medicion(historial, resumen_entrega, hoy)
            _guardar_json(trabajo / "metricas_entrega.json", historial)
        resumen_entrega["fecha"] = hoy
        try:
            resumen_entrega["embudo"] = entrega.embudo(vacantes, entregadas_antes, hoy, resumen=resumen_entrega)
        except Exception as e:  # noqa: BLE001 — el diagnóstico nunca detiene la entrega
            resumen_entrega["embudo"] = {"error": f"{type(e).__name__}"}
    # El lote histórico conserva su snapshot; el estado actual se evalúa aparte con el catálogo y la caché.
    lote_actual = _leer_json(trabajo / "lote_entrega.json", {})
    if lote_actual.get("fecha") == hoy:
        por_id_actual = {v["id"]: v for v in vacantes}
        for v, _, _ in retiradas:
            por_id_actual[v["id"]] = v
        actuales = [dict(por_id_actual.get(v["id"], v)) for lista in lote_actual.get("elegidas", {}).values() for v, _ in lista]
        for v in actuales:
            verificar_enlaces.anotar(v, cache_enlaces)
        resumen_revision["seleccion_del_dia"] = verificar_enlaces.resumen(actuales)
    resumen_revision["rechazos_en_corrida"] = {m: n for m, n in descartes.items() if m in verificar_enlaces.RECHAZOS}
    seleccion_actual = {"fecha": lote_actual.get("fecha"), "roles": {}}
    por_id_vigente = {v["id"]: v for v in vacantes}
    estados_catalogo = {v["id"]: estado for v, estado, _ in retiradas}
    estados_catalogo.update({v["id"]: "archived" if contrato.entregable(v) else "active" for v in vacantes})
    for rol in roles_actuales:
        entradas = []
        for original, _ in lote_actual.get("elegidas", {}).get(rol["id"], []):
            actual = dict(por_id_vigente.get(original["id"], original))
            revision = verificar_enlaces.anotar(actual, cache_enlaces)
            entradas.append({"id": actual["id"], "catalog_status": estados_catalogo.get(actual["id"], "sin_catalogo"), "afinidad_vigente":
                afinidad_vigente(original, actual, rol, roles_actuales, por_id_vigente),
                "enlace": actual.get("enlace", ""), "enlace_directo": actual.get("enlace_directo", ""),
                "verificacion": revision})
        seleccion_actual["roles"][rol["id"]] = {"nombre": rol["nombre"], "meta": entrega.meta_de(rol, config_entrega), "vacantes": entradas}
    reporte = {
        "fecha": hoy, "hora_utc": datetime.now(timezone.utc).strftime("%H:%M"), "modo": modo,
        "codigo_commit": os.environ.get("GITHUB_SHA", ""), "ejecucion_id": os.environ.get("GITHUB_RUN_ID", ""),
        "consulta": consulta or "", "pais": pais or "",
        "minutos": round((time.monotonic() - inicio) / 60, 1),
        "vacantes_en_bodega": len(vacantes), "crudas_hoy": len(crudas),
        "nuevas_hoy": sum(1 for v in vacantes if v["visto_primera_vez"] == hoy),
        "fuentes": salud, "descartes": dict(descartes),
        "por_familia": dict(Counter(f["familia"] for v in vacantes for f in v["familias"]).most_common()),
        "por_pais": dict(Counter(p for v in vacantes for p in v["paises"]).most_common()),
        "por_fuente": dict(Counter(fu for v in vacantes for fu in v["fuentes"]).most_common()),
        "por_modalidad": dict(Counter(v["modalidad"] for v in vacantes)),
        "ubicacion_por_confirmar": sum(v["confianza_pais"] == "baja" for v in vacantes),
        "entrega": resumen_entrega,
        "seleccion_actual": seleccion_actual,
        "refuerzos": refuerzos,
        "historico_entregas": historico_entregas,
        "catalogo": resumen_catalogo,
        "capturada_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "frescura": tiempos.medir(vacantes),
        "verificacion_enlaces": resumen_revision,
        "estado_operativo": {"activo": bool(central), "pendientes": {
            "catalogo": len(pendientes_catalogo), "ofertas": len(pendientes_v1), "registro": len(pendientes_registro)},
            "lotes_pendientes": len(central.lote.valores) if central else None, "reintentos": reintentos_centrales},
    }
    from buscador import publicar
    publicar.publicar(salida, vacantes, reporte, sin_familia)
    return reporte


def main():
    ap = argparse.ArgumentParser(description="Bodega nocturna de vacantes")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--modo", default="diario", choices=["diario", "inicial", "incremental"])
    ap.add_argument("--consulta", default="")
    ap.add_argument("--pais", default="")
    ap.add_argument("--prueba", action="store_true", help="presupuestos mínimos, para probar que todo funciona")
    a = ap.parse_args()
    reporte = correr(a.salida, a.modo, a.consulta or None, a.pais or None, prueba=a.prueba)
    print(json.dumps({k: reporte[k] for k in ("fecha", "minutos", "vacantes_en_bodega", "nuevas_hoy", "crudas_hoy",
                                              "descartes")}, ensure_ascii=False, indent=1))
    for n, s in reporte["fuentes"].items():
        print(f"  {n}: {s}")
    print("Verificación de enlaces:", json.dumps(reporte["verificacion_enlaces"], ensure_ascii=False))
    e = reporte.get("entrega") or {}
    if not a.prueba and a.modo != "incremental" and e.get("meta_cumplida") is False:
        faltantes = ", ".join(f"{r['nombre']}: faltan {r['faltan']}" for r in e["roles"].values() if r["faltan"])
        print(f"::warning::Meta diaria incompleta tras los refuerzos. {faltantes}")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
