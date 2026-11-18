"""Adaptador del control privado al motor de captura existente, sin datos de clientes en reportes públicos."""
import argparse
from contextlib import contextmanager
from functools import lru_cache
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from buscador import bodega, entrega, familias, paises, normalizar
from buscador import registro
from panel.afinidad import (AMPLIACIONES, MINIMO_POR_PERFIL, TOPE_POSTS_SIN_CONFIRMAR, evaluar, evaluar_ampliada,
                            evaluar_post, post_ubicacion)
from panel.acciones import ENFOQUE_COMPLETO, ENFOQUE_FALTANTES
from panel.modelos import Configuracion
from pydantic import ValidationError
from panel.repositorio import RepositorioSupabase, hoy
from panel.terminos import en_espanol, espanol_del_mapa, grado, sugerir


def validar_version(version):
    try:
        return Configuracion.model_validate(version["configuracion"]).validar_publicacion()
    except (ValidationError,ValueError,KeyError):
        raise RuntimeError("La configuración privada no es válida; revísala en el panel. No se muestran datos de clientes.") from None


MAX_PAISES_POR_FILA = 10  # contrato v40: países sueltos que se buscan por fila (las regiones cuentan como uno)


@lru_cache(maxsize=1)
def regiones_busqueda():
    """Contrato v40: `datos/regiones_busqueda.yaml` con los miembros de LATAM desde paises.yaml."""
    ruta = Path(__file__).resolve().parent.parent / "datos" / "regiones_busqueda.yaml"
    try:
        crudo = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}
    for clave, r in crudo.items():
        r.setdefault("miembros", list(paises.datos()["latam"]) if clave == "latam" else [])
    return crudo


def _region_de(codigos):
    """(clave, región, países cubiertos) de la región que una fila abarca, o None."""
    for clave, r in regiones_busqueda().items():
        miembros = set(r.get("miembros") or [])
        dentro = set(codigos) & miembros
        if miembros and len(dentro) >= 6 and len(dentro) >= 0.6 * len(miembros):
            return clave, r, dentro
    return None


def _clave_ciudad(ciudad):
    return "CIUDAD_" + normalizar.texto(ciudad).replace(" ", "_").upper()


def lugares_perfil(p, nombres=None):
    """Lugares de búsqueda de un perfil. Contrato v40: salen de TODAS sus filas de «¿Dónde trabajaría?» (antes solo de
    donde vive y sus oficinas):
    - remoto en un país → «remoto en ese país»; híbrido o presencial → ese país y las ciudades de la fila;
    - una fila que abarca una región (Europa, LATAM…) → la región, más sus países principales que la fila incluye;
    - «remoto en LATAM» solo para quien vive en LATAM; «remoto en cualquier parte» para todo el que acepta remoto.
    Vale para cualquier país del mundo y cualquier cargo. Los países de fuera van por su nombre en inglés (v24)."""
    nombres = nombres or {x["codigo"]: x["nombre"] for x in paises.datos()["paises"]}
    nombres = {**{x["codigo"]: x["nombre_en"] for x in paises.mundo()["lista"]}, **nombres}
    latam = set(paises.datos()["latam"])
    lugares = {}
    for fila in p.filas:
        remoto = "remoto" in fila.modalidades
        oficina = bool({"hibrido", "presencial"} & set(fila.modalidades))
        codigos = [c for c in fila.paises if c in nombres]
        region = _region_de(codigos)
        sueltos = codigos
        if region:
            clave, r, dentro = region
            if remoto:
                lugares["REMOTO" if clave == "latam" else "REMOTO_REGION_" + clave.upper()] = \
                    {"location": r["linkedin"], "f_WT": "2"}
            if oficina:
                lugares["REGION_" + clave.upper()] = {"location": r["linkedin"]}
            principales = [c for c in r.get("principales", []) if c in dentro]
            sueltos = principales + [c for c in codigos if c not in dentro]
        for codigo in sueltos[:MAX_PAISES_POR_FILA]:
            if remoto:
                lugares["REMOTO_" + codigo] = {"location": nombres[codigo], "f_WT": "2"}
            if oficina:
                lugares[codigo] = {"location": nombres[codigo]}
        if oficina:
            for ciudad in fila.ciudades:
                lugares[_clave_ciudad(ciudad)] = {"location": ciudad}
    if "remoto" in p.modalidades:
        if p.vive_en in latam:
            lugares["REMOTO"] = {"location": "Latin America", "f_WT": "2"}
        lugares["REMOTO_MUNDO"] = {"location": "Worldwide", "f_WT": "2"}
    return lugares


def paises_de_lugares(lugares):
    """Códigos de país de unos lugares de búsqueda («REMOTO_AE» → AE, «US» → US); las regiones y ciudades no cuentan."""
    salida = []
    for clave in lugares:
        codigo = clave[7:] if clave.startswith("REMOTO_") else clave
        if len(codigo) == 2 and codigo.isalpha() and codigo.isupper() and codigo not in salida:
            salida.append(codigo)
    return salida


# Países con fuentes propias además de LinkedIn e Indeed (Computrabajo, Elempleo, Get on Board): fuera de ellos una
# persona depende solo de LinkedIn e Indeed y recibe el doble de turnos (contrato v40).
def _con_fuentes_propias():
    from buscador.fuentes import computrabajo, sitemaps_empleo
    return set(computrabajo.SITIOS) | {"ES"} | {c for s in sitemaps_empleo.SITIOS.values() for c in s["sitemaps"]}


def fuentes_en(pais):
    """Contrato v44 (decisión de Oscar: «cualquier persona, en cualquier país»): fuentes que buscan para alguien que
    vive en `pais`, con títulos en español si solo habla español. LinkedIn y los portales de empresas cubren todo el
    mundo; Get on Board aporta remotas abiertas a cualquier país (y a LATAM); Indeed, sus 62 países; las locales,
    donde existen. Sin IA: sale de las listas de cada fuente."""
    from buscador.fuentes import computrabajo, elempleo, indeed, sitemaps_empleo
    salida = ["LinkedIn", "Portales de empresas", "Get on Board (remotas)"]
    if pais in indeed.PAISES:
        salida.append("Indeed")
    if pais in computrabajo.SITIOS:
        salida.append("Computrabajo")
    if pais in elempleo.PAISES:
        salida.append("Elempleo")
    salida += [nombre for nombre, s in sitemaps_empleo.SITIOS.items() if pais in s["sitemaps"]]
    return salida


PESO_CORTO = 2
PESO_POCAS_FUENTES = 2


def persona_de_busqueda(p, rid, nombres=None, corto=False):
    """Contrato v40: {familia, perfil, lugares, peso} de una persona para repartir las búsquedas. Peso = meta del día,
    ×2 si quedó bajo el mínimo (o es nueva) y ×2 si ninguno de sus países tiene fuentes propias. Sus lugares incluyen
    sus países, para casar también con Indeed y Computrabajo («CO», «CO:REMOTO»)."""
    lugares = lugares_perfil(p, nombres)
    codigos = paises_de_lugares(lugares) or [p.vive_en]
    peso = float(p.meta_diaria or 0)
    if corto:
        peso *= PESO_CORTO
    if not set(codigos) & _con_fuentes_propias():
        peso *= PESO_POCAS_FUENTES
    # Lugares principales: donde vive (su primera fila) y las regiones de sus filas. Van primero cada día (17 nov: los
    # turnos de quien vive en Emiratos se iban en países sueltos de Europa y «remoto en Emiratos» nunca llegaba).
    primera = lugares_perfil(p.model_copy(update={"ubicaciones": p.filas[:1]}), nombres) if p.filas else {}
    principales = [k for k in lugares if (k in primera and k != "REMOTO_MUNDO") or k.startswith(("REMOTO_REGION_", "REGION_"))]
    return {"familia": rid, "perfil": str(p.id), "lugares": sorted(set(lugares) | set(codigos)), "peso": peso,
            "corto": bool(corto), "principales": principales}


def consultas_espanol(cargo, raw, maximo=12):
    """Títulos en español del cargo: los suyos y, si faltan, los del mapa de cargos (`sugerir`)."""
    propios = [cargo.nombre, *raw["terminos_exactos"], *raw["terminos_similares"]]
    sugeridos = sugerir(cargo.nombre, consultar_esco=False)
    candidatos = propios + sugeridos["terminos_exactos"] + sugeridos["terminos_similares"]
    vistos, salida = set(), []
    for t in candidatos:
        clave = normalizar.texto(t)
        if clave and clave not in vistos and en_espanol(t):
            vistos.add(clave)
            salida.append(t)
    return salida[:maximo]


def objetivo_mundo(cfg):
    """Contrato v24: países (de cualquier parte) que necesitan los perfiles activos: residencia, mudanza, permiso
    legal y el país de sus ciudades cuando se reconoce. Y si algún perfil acepta horario de otras zonas."""
    salida = set()
    acepta = False
    for p in cfg.perfiles_activos():
        salida |= {p.vive_en, *p.paises_presenciales_extra, *p.puede_trabajar_en}
        for ciudad in p.ciudades:
            salida |= set(paises.alcance("", ciudad).get("paises_mundo") or [])
        acepta = acepta or bool(p.acepta_horario)
    return sorted(salida), acepta


# Contrato v45: con «Buscar ahora» para quien falta, las fuentes tienen el doble de presupuesto.
FACTOR_A_FONDO = 2


def preparar(version, fecha, aprendidos=None, cortos=(), enfocar=None):
    """`cortos` (contrato v37): ids de perfiles que en la última búsqueda quedaron bajo el mínimo (o no recibieron
    nada, como los nuevos). Sus lugares van primero en cada fuente y sus avisos reciben ficha primero.
    `enfocar` (contrato v45, «Buscar ahora» para quien falta): ids de los perfiles que hoy no llegan a su meta. Solo
    ellos tienen turnos de búsqueda, sus lugares van primero y piden los 30 días, y las fuentes tienen el doble de
    presupuesto. El mapa y los cargos son los de siempre (la clasificación y el lote del día no cambian)."""
    cfg = validar_version(version)
    # Con `enfocar`, solo ellos van primero y piden 30 días (no los cortos de la última búsqueda que ya cumplen).
    enfocar = None if enfocar is None else {str(x) for x in enfocar}
    cortos = enfocar if enfocar is not None else {str(x) for x in cortos}
    primero, personas = {}, []
    aprendidos = aprendidos or {}
    mapa, roles = [], []
    nombres = {**{p["codigo"]: p["nombre"] for p in paises.mundo()["lista"]},
               **{p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}}
    comunidades = {c.id for c in cfg.clientes if c.comunidad}
    for c in cfg.cargos:
        perfiles = cfg.perfiles_activos(c.id) if c.activo else []
        comunidad = [p for p in perfiles if p.cliente_id in comunidades]
        # Contrato v21: un cargo sin cupo propio se busca igual si Comunidad tiene perfiles en él (recibe lo que sobra).
        if not perfiles or (not c.cupo and not comunidad):
            continue
        raw = c.model_dump(mode="json")
        if not raw["terminos_exactos"]:
            raw["terminos_exactos"] = sugerir(c.nombre, consultar_esco=False)["terminos_exactos"]
        lugares = {}
        for p in perfiles:
            lugares.update(lugares_perfil(p, nombres))
        rid = "cargo:" + str(c.id)
        for p in perfiles:  # contrato v40: cada persona con sus lugares y su peso
            if enfocar is None or str(p.id) in enfocar:
                personas.append(persona_de_busqueda(p, rid, nombres, str(p.id) in cortos))
        for p in perfiles:
            if str(p.id) in cortos:
                primero.setdefault(rid, set()).update(lugares_perfil(p, nombres))
                primero[rid].update(p.paises_oficina)
                primero[rid].update(x for fila in p.filas if "remoto" in fila.modalidades for x in fila.paises)
        # PR 1b: para quien solo acepta avisos en español, LinkedIn busca además los títulos en español en sus lugares.
        solo_es = [p for p in perfiles if set(p.idiomas) == {"es"}]
        consultas_es = consultas_espanol(c, raw) if solo_es else []
        lugares_es = {}
        for p in solo_es:
            lugares_es.update({k: v for k, v in lugares_perfil(p, nombres).items() if k != "REMOTO_MUNDO"})
        # Contrato v25: títulos aprobados desde «Coincide por funciones» cuentan como similares del cargo.
        similares = list(dict.fromkeys(raw["terminos_similares"] + list(aprendidos.get(str(c.id)) or [])))
        raw["terminos_similares"] = similares
        mapa.append({"id": rid, "nombre": c.nombre, "consultas": [c.nombre, *raw["terminos_exactos"], *raw["terminos_similares"]],
            "exactos": raw["terminos_exactos"], "similares": similares, "cercanos": raw.get("terminos_cercanos", []),
            "funciones": raw.get("funciones", []),
            # Contrato v44: los títulos en español de la familia del mapa clasifican los avisos (como en `grado`), pero
            # no se buscan: no van en `consultas`/`similares`, que rotan en todas las fuentes.
            "similares_es": list(espanol_del_mapa(c.nombre)),
            "excluir": raw["terminos_excluidos"], "herramientas": [], "lugares": list(lugares.items()),
            "_control_cargo": raw,
            "consultas_es": consultas_es, "lugares_es": list(lugares_es.items()) if consultas_es else [],
            # Contrato v44: países de quienes solo hablan español (Indeed y Computrabajo buscan ahí con títulos en español).
            "paises_es": paises_de_lugares(lugares_es) if consultas_es else [],
            # Contrato v36: también el país donde vive quien acepta remoto (Indeed busca ahí; antes solo oficinas).
            "paises_objetivo": sorted({x for p in perfiles for x in p.paises_oficina} |
                                      {f for p in perfiles for fila in p.filas if "remoto" in fila.modalidades
                                       for f in fila.paises}),
            # Contrato v40: países donde se busca (Indeed, Computrabajo): los de sus lugares, no los 30 de «Europa».
            "paises_busqueda": sorted({x for p in perfiles for x in paises_de_lugares(lugares_perfil(p, nombres))}),
            "solo_remoto": all(p.modalidades == ["remoto"] for p in perfiles)})
        roles.append({"id": rid, "nombre": c.nombre, "familias": [rid], "cupo": c.cupo,
                      "_perfiles": [p.model_dump(mode="json") for p in perfiles], "_hoy": fecha,
                      "_comunidad": [p.model_dump(mode="json") for p in comunidad]})
    configuracion = {"por_rol": 20, "roles": roles, "preferir_remotas": True, "max_por_empresa": 2,
                     "dias_frescura": 30, "idiomas": ["es", "en"], "techo": cfg.techo_diario}
    motor = bodega.config()
    motor["paises_activos"] = sorted({p for x in mapa for p in x["paises_objetivo"]})
    # Contrato v27: la antigüedad del perfil solo ordena; la captura trae hasta el límite del sistema.
    from panel.afinidad import ANTIGUEDAD_SISTEMA
    motor["dias_maximos"] = ANTIGUEDAD_SISTEMA
    motor["control_dirigido"] = True
    motor["paises_objetivo_mundo"], motor["acepta_horario"] = objetivo_mundo(cfg)
    motor["lugares_primero"] = {k: sorted(v) for k, v in primero.items()}
    motor["personas_busqueda"] = personas
    motor["presupuestos"].update(linkedin_busquedas=min(300, max(24, len(roles) * 24)),
        indeed_busquedas=min(72, max(6, len(roles) * 8)), getonbrd_busquedas=min(30, len(roles) * 4),
        computrabajo_busquedas=min(90, max(12, len(roles) * 12)),
        elempleo_busquedas=min(30, max(6, len(roles) * 3)),
        apify_busquedas=0,  # contrato v11: Apify solo para perfiles bajo el mínimo (rescate dirigido)
        empresas_por_probar=20, remotos_paginas=24)
    if enfocar is not None:
        pres = motor["presupuestos"]
        for clave in ("linkedin_busquedas", "linkedin_fichas", "indeed_busquedas", "getonbrd_busquedas",
                      "computrabajo_busquedas", "computrabajo_fichas", "elempleo_busquedas", "elempleo_fichas",
                      "hireline_fichas", "magneto_fichas"):
            if pres.get(clave):
                pres[clave] = int(pres[clave] * FACTOR_A_FONDO)
        motor["a_fondo"] = True
    return mapa, configuracion, motor


@contextmanager
def activar(version, fecha, aprendidos=None, cortos=(), enfocar=None):
    mapa, cfg, motor = preparar(version, fecha, aprendidos, cortos, enfocar)
    from buscador import cobertura, contrato
    cobertura.configurar_primero(motor.get("lugares_primero"))
    cobertura.configurar_personas(motor.get("personas_busqueda"))
    cobertura.configurar_a_fondo(motor.get("a_fondo"))
    anterior_e, anterior_b, anterior_c = entrega._config_operativa, bodega._config_operativa, contrato._PANEL
    familias.configurar(mapa)
    entrega._config_operativa, bodega._config_operativa, contrato._PANEL = cfg, motor, True
    try:
        yield cfg
    finally:
        familias.configurar()
        cobertura.configurar_primero()
        cobertura.configurar_personas()
        cobertura.configurar_a_fondo()
        entrega._config_operativa, bodega._config_operativa, contrato._PANEL = anterior_e, anterior_b, anterior_c


def perfiles_cortos(repo, version, fecha):
    """Contrato v37: perfiles activos que en la última búsqueda registrada (hoy o antes) quedaron bajo el mínimo.
    Un perfil nuevo no tiene asignaciones y cuenta como corto. Si no se puede leer, ninguno (todo como antes)."""
    try:
        cfg = validar_version(version)
        ids = [str(p.id) for p in cfg.perfiles if p.activo]
        ultimas = [e for e in (repo.ejecuciones() or []) if str(e.get("fecha", "")) <= fecha]
        conteo = repo.conteo_asignaciones(ultimas[0]["id"], ids) if ultimas else Counter()
        return {i for i in ids if conteo.get(i, 0) < MINIMO_POR_PERFIL}
    except Exception as e:  # noqa: BLE001 — sin este dato la búsqueda reparte como siempre
        registro.aviso("ejecutor:cortos", e)
        return set()


LOTE_ARMADO = {"parcial", "completa"}


def faltan_hoy(repo, version, fecha, ejecuciones=None):
    """Contrato v45: [(perfil, recibidas hoy, meta)] de quienes hoy no llegan a su meta y todavía pueden recibir más, o
    None si hoy aún no hay una búsqueda que haya armado su lote (no hay fila, falló, o solo corrió la captura horaria).
    Puede recibir más quien está bajo el mínimo de 5 (rescate y reutilización lo completan) o cuyo cargo tiene cupo
    libre en el lote del día. Comunidad no cuenta: recibe lo que sobra. Sin IA: cuenta las asignaciones del día."""
    de_hoy = [e for e in (ejecuciones if ejecuciones is not None else repo.ejecuciones()) or []
              if str(e.get("fecha", "")) == fecha]
    resumen = (de_hoy[0].get("resumen") or {}) if de_hoy else {}
    if not de_hoy or de_hoy[0].get("estado") not in LOTE_ARMADO or resumen.get("revision_del_lote") is None:
        return None
    cfg = validar_version(version)
    comunidades = {c.id for c in cfg.clientes if c.comunidad}
    cargos = {c.id: c.nombre for c in cfg.cargos}
    cupo_libre = resumen.get("faltantes") or {}
    eid = str(de_hoy[0]["id"])
    conteo = repo.asignaciones_por_perfil([eid])
    salida = []
    for p in cfg.perfiles_activos():
        n, meta = conteo.get((eid, str(p.id)), 0), int(p.meta_diaria or 0)
        if p.cliente_id in comunidades or n >= meta:
            continue
        if n < MINIMO_POR_PERFIL or cupo_libre.get(cargos.get(p.cargo_id, ""), 1) > 0:
            salida.append((p, n, meta))
    return salida


def iniciar(repo, version, fecha):
    """Fija una versión diaria y permite releer la misma ejecución al reintentar.
    Contrato v43: si la configuración se confirmó mientras la búsqueda corría, la fila del día pasa a la versión más
    nueva y anota la anterior (como SQL 019); antes la búsqueda se caía al final y se perdía todo lo encontrado."""
    e = repo.pedir("GET", "panel_ejecuciones", params={"fecha": "eq." + fecha, "limit": 1})
    if not e:
        e = repo.pedir("POST", "panel_ejecuciones", json={"fecha": fecha, "revision": version["revision"]},
                       params={"on_conflict": "fecha"}, headers={"Prefer":"resolution=ignore-duplicates"})  # repositorio aplica cabeceras comunes
        e = repo.pedir("GET", "panel_ejecuciones", params={"fecha": "eq." + fecha, "limit": 1})
    ejecucion = e[0]
    if ejecucion["revision"] < version["revision"]:
        resumen = dict(ejecucion.get("resumen") or {})
        resumen["revisiones_anteriores"] = [*(resumen.get("revisiones_anteriores") or []), ejecucion["revision"]]
        repo.pedir("PATCH", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"]},
                   json={"revision": version["revision"], "resumen": resumen})
        ejecucion = {**ejecucion, "revision": version["revision"], "resumen": resumen}
    return ejecucion


def vigente(repo, version, fecha):
    """Contrato v43: la versión confirmada más nueva para hoy; si no se puede leer, la que ya se tiene."""
    try:
        nueva = repo.operativa(fecha) if hasattr(repo, "operativa") else None
    except Exception as e:  # noqa: BLE001 — sin la lectura se asigna con la versión con la que empezó la búsqueda
        registro.aviso("ejecutor:vigente", e)
        return version
    return nueva if nueva and nueva.get("revision", 0) > version.get("revision", 0) else version


def _embudo_por_nombre(reporte):
    """Embudo de la nocturna por nombre de cargo; las capturas horarias conservan el último guardado."""
    embudo = ((reporte or {}).get("entrega") or {}).get("embudo") or {}
    return {e["nombre"]: {k: v for k, v in e.items() if k != "nombre"} for e in embudo.values()
            if isinstance(e, dict) and "nombre" in e}


DIAS_REUTILIZAR = 14


def _paginas(repo, ruta, params, tamano=500, maximo=5000):
    salida = []
    for inicio in range(0, maximo, tamano):
        lote = repo.pedir("GET", ruta, params={**params, "limit": tamano, "offset": inicio}) or []
        salida.extend(lote)
        if len(lote) < tamano:
            break
    return salida


def _reutilizar(repo, cfg, fecha, estrictas, filas, fila):
    """Contrato v11: a cada perfil con menos del mínimo se le añaden vacantes elegidas en días anteriores (para otros
    clientes o por el cupo) que cumplen sus filtros —con las mismas ampliaciones— y que esa persona nunca recibió.
    No cambia la selección del día ni el cupo: solo la asignación por persona. Devuelve cuántas se añadieron."""
    bajos = [(c, p) for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))
             if estrictas.get(p.id, 0) < MINIMO_POR_PERFIL]
    if not bajos:
        return 0
    desde = (datetime.fromisoformat(fecha) - timedelta(days=DIAS_REUTILIZAR)).date().isoformat()
    previas = _paginas(repo, "entregas_diarias", {"delivery_date": f"gte.{desde}", "select": "*",
                                                  "order": "delivery_date.desc,vacante_id"})
    previas = [r for r in previas if r.get("delivery_date", "") < fecha]
    ids = ",".join(str(p.id) for _, p in bajos)
    recibidas = {}
    for r in _paginas(repo, "panel_asignaciones", {"perfil_id": f"in.({ids})", "select": "perfil_id,vacante_id"}):
        recibidas.setdefault(r["perfil_id"], set()).add(r["vacante_id"])
    clientes = ",".join({str(p.cliente_id) for _, p in bajos})
    enviadas = {}
    for b in _paginas(repo, "panel_borradores", {"cliente_id": f"in.({clientes})", "select": "cliente_id,vacantes"}):
        enviadas.setdefault(b["cliente_id"], set()).update(b.get("vacantes") or [])
    hoy_por_perfil = {}
    for f in filas:
        hoy_por_perfil.setdefault(f["perfil_id"], set()).add(f["vacante_id"])
    añadidas = 0
    for cargo, p in bajos:
        raw = cargo.model_dump(mode="json")
        vistas = recibidas.get(str(p.id), set()) | enviadas.get(str(p.cliente_id), set()) | hoy_por_perfil.get(str(p.id), set())
        for row in previas:
            if estrictas.get(p.id, 0) >= MINIMO_POR_PERFIL:
                break
            if row["vacante_id"] in vistas or not grado(row["snapshot"].get("titulo") or "", raw, cercanos=True)[0]:
                continue
            match, extra = evaluar(row["snapshot"], p, fecha), [{"reutilizada": row["delivery_date"]}]
            if not match["compatible"]:
                nivel = next((n for n in AMPLIACIONES if evaluar_ampliada(row["snapshot"], p, fecha, n)["compatible"]), None)
                if not nivel:
                    continue
                match, extra = evaluar_ampliada(row["snapshot"], p, fecha, nivel), [*extra, {"ampliacion": nivel}]
            vistas.add(row["vacante_id"])
            estrictas[p.id] = estrictas.get(p.id, 0) + 1
            filas.append(fila(row, p, str(cargo.id), match["pruebas"], extra))
            añadidas += 1
    return añadidas


# Contrato v36 (caso Danna, 17 nov): completar el mínimo con TODA la bodega, no solo con lo que entró a algún lote.
MAX_COMPROBAR_RESCATE = 80  # enlaces que se comprueban al momento para estos perfiles (no usa Apify)
SEGUNDOS_RESCATE = 150


def _vigente_24h(v, ahora):
    """True si la vacante tiene un enlace comprobado como vigente en las últimas 24 h (el plazo para compartir, v31)."""
    from buscador import tiempos
    for e in (v.get("verificacion") or {}).get("enlaces") or []:
        fecha = tiempos.instante(e.get("comprobada_en") or "")
        if e.get("estado") == "verificada" and fecha:
            edad = (ahora - datetime.fromisoformat(fecha.replace("Z", "+00:00"))).total_seconds()
            if 0 <= edad < 24 * 3600:
                return True
    return False


def _rescatar(repo, cfg, fecha, estrictas, filas, fila, vacantes, cache=None, comprobar=None, subir=None,
              maximo=MAX_COMPROBAR_RESCATE, segundos=SEGUNDOS_RESCATE):
    """Contrato v36: a cada perfil que sigue bajo el mínimo se le dan vacantes de toda la bodega de la noche que cumplen
    su ubicación e idioma (lo demás ordena, v27), con enlace comprobado en 24 h, que esa persona nunca recibió —aunque
    otro cliente sí— y con máximo 2 por empresa. Los enlaces que falten se comprueban aquí mismo (como mucho
    `MAX_COMPROBAR_RESCATE`) y su comprobación se guarda en el catálogo para poder compartirlas. No cuentan en el cupo ni
    van a `ofertas`: solo la asignación por persona, como las reutilizadas (v11)."""
    from datetime import timezone
    from buscador import catalogo, contrato, tiempos, verificar_enlaces
    bajos = [(c, p) for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))
             if estrictas.get(p.id, 0) < MINIMO_POR_PERFIL]
    if not bajos or not vacantes:
        return 0
    ahora = datetime.now(timezone.utc)
    ids = ",".join(str(p.id) for _, p in bajos)
    vistas = {}
    for r in _paginas(repo, "panel_asignaciones", {"perfil_id": f"in.({ids})", "select": "perfil_id,vacante_id"}):
        vistas.setdefault(r["perfil_id"], set()).add(r["vacante_id"])
    for f in filas:
        vistas.setdefault(f["perfil_id"], set()).add(f["vacante_id"])
    utiles = [v for v in vacantes if v.get("tipo") != "post" and v.get("titulo")
              and not contrato.entregable(dict(v, verificacion=None), panel=True)]
    # 1) Candidatas de cada perfil, de mejor a peor (grado, lo que no cumple, más reciente).
    candidatas = {}
    for cargo, p in bajos:
        raw = cargo.model_dump(mode="json")
        lista = []
        for v in utiles:
            if v["id"] in vistas.get(str(p.id), set()):
                continue
            afinidad, _ = grado(v["titulo"], raw, cercanos=True)
            if afinidad not in entrega.GRADOS:  # «funciones» nunca se entrega sola (v25)
                continue
            match, extra = evaluar(v, p, fecha), []
            if not match["compatible"]:
                nivel = next((n for n in AMPLIACIONES if evaluar_ampliada(v, p, fecha, n)["compatible"]), None)
                if not nivel:
                    continue
                match, extra = evaluar_ampliada(v, p, fecha, nivel), [{"ampliacion": nivel}]
            lista.append((entrega.GRADOS.index(afinidad) + len(match.get("incumple") or ()) + 2 * bool(extra),
                          -int((v.get("fecha_publicacion") or "0000-00-00").replace("-", "")[:8] or 0),
                          v, afinidad, match, extra))
        lista.sort(key=lambda x: x[:2])
        candidatas[(cargo.id, p.id)] = lista
    # 2) Comprobar al momento los enlaces de las que podrían entrar (las 3 mejores por plaza que falta).
    por_comprobar, ya = [], set()
    for cargo, p in bajos:
        falta = MINIMO_POR_PERFIL - estrictas.get(p.id, 0)
        for x in candidatas[(cargo.id, p.id)][:falta * 3]:
            v = x[2]
            if v["id"] not in ya and not _vigente_24h(v, ahora):
                ya.add(v["id"])
                por_comprobar.append(v)
    comprobadas = []
    if por_comprobar:
        cache = {} if cache is None else cache
        try:
            verificar_enlaces.auditar(por_comprobar, cache, maximo=maximo, segundos=segundos, comprobar_url=comprobar)
            comprobadas = [v for v in por_comprobar if _vigente_24h(v, datetime.now(timezone.utc))]
        except Exception as e:  # noqa: BLE001 — sin comprobar, simplemente no se entregan
            registro.aviso("ejecutor:rescate", e)
    if comprobadas:
        try:  # la comprobación nueva queda en el catálogo: el panel y WhatsApp la leen de ahí
            from buscador import supabase
            (subir or supabase.subir_catalogo)([catalogo.fila(v, tiempos.ahora()) for v in comprobadas])
        except Exception as e:  # noqa: BLE001
            registro.aviso("ejecutor:rescate-catalogo", e)
    # 3) Asignar con enlace vigente, sin repetir a la persona y con máximo 2 por empresa.
    añadidas = 0
    ahora = datetime.now(timezone.utc)
    empresa_de = {v["id"]: normalizar.texto(v.get("empresa") or "") for v in vacantes}
    for cargo, p in bajos:
        empresas = Counter(empresa_de.get(f["vacante_id"], "") for f in filas if f["perfil_id"] == str(p.id))
        for _, _, v, afinidad, match, extra in candidatas[(cargo.id, p.id)]:
            if estrictas.get(p.id, 0) >= MINIMO_POR_PERFIL:
                break
            empresa = normalizar.texto(v.get("empresa") or "")
            if v["id"] in vistas.setdefault(str(p.id), set()) or empresas[empresa] >= 2 or not _vigente_24h(v, ahora):
                continue
            row = {"vacante_id": v["id"], "snapshot": v, "match_grade": entrega.GRADO_CONTRATO.get(afinidad, "close")}
            vistas[str(p.id)].add(v["id"])
            empresas[empresa] += 1
            estrictas[p.id] = estrictas.get(p.id, 0) + 1
            filas.append(fila(row, p, str(cargo.id), match["pruebas"], [{"rescatada": "bodega"}, *extra]))
            añadidas += 1
    return añadidas


DIAS_POSTS = 2  # un post se comparte el día en que se leyó o el siguiente (su comprobación vale 24 h)


def _posts(repo, cfg, fecha, estrictas, filas, fila):
    """Contrato v11 (segunda parte): a cada perfil que sigue bajo el mínimo se le asignan posts de LinkedIn del cargo,
    solo hasta completar el mínimo. Cumplen sus filtros (los datos que el post no dice se admiten como «sin dato»,
    igual que una ampliación) y esa persona nunca los recibió. No cuentan en el cupo ni van a `ofertas`."""
    from buscador import contrato, vacante as vacante_mod
    bajos = [(c, p) for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))
             if estrictas.get(p.id, 0) < MINIMO_POR_PERFIL]
    if not bajos:
        return 0
    desde = (datetime.fromisoformat(fecha) - timedelta(days=DIAS_POSTS)).date().isoformat()
    posts = _paginas(repo, "catalogo_vacantes", {"status": "eq.active", "datos->>tipo": "eq.post",
                                                 "observed_at": f"gte.{desde}", "select": "id,datos,description_full",
                                                 "order": "observed_at.desc"}, maximo=1000)
    candidatos = []
    for row in posts:
        datos = vacante_mod.reetiquetar(dict(row.get("datos") or {}, _descripcion=row.get("description_full") or ""),
                                        publicada=True)
        if datos.get("tipo") == "post" and not contrato.entregable_post(datos):
            candidatos.append({"vacante_id": row["id"], "snapshot": datos})
    if not candidatos:
        return 0
    ids = ",".join(str(p.id) for _, p in bajos)
    vistas_por_perfil = {}
    for r in _paginas(repo, "panel_asignaciones", {"perfil_id": f"in.({ids})", "select": "perfil_id,vacante_id"}):
        vistas_por_perfil.setdefault(r["perfil_id"], set()).add(r["vacante_id"])
    for f in filas:
        vistas_por_perfil.setdefault(f["perfil_id"], set()).add(f["vacante_id"])
    añadidos = 0
    # Contrato v28: primero los posts con ubicación clara, después los deducidos y al final los sin confirmar.
    candidatos.sort(key=lambda row: ("", "deducida", "sin_confirmar").index(post_ubicacion(row["snapshot"])))
    for cargo, p in bajos:
        raw = cargo.model_dump(mode="json")
        vistas = vistas_por_perfil.setdefault(str(p.id), set())
        sin_confirmar = 0
        for row in candidatos:
            if estrictas.get(p.id, 0) >= MINIMO_POR_PERFIL:
                break
            afinidad, _ = grado(row["snapshot"]["titulo"], raw, cercanos=True)
            if row["vacante_id"] in vistas or not afinidad:
                continue
            marca = post_ubicacion(row["snapshot"])
            if marca == "sin_confirmar" and sin_confirmar >= TOPE_POSTS_SIN_CONFIRMAR:
                continue
            match, extra = evaluar_post(row["snapshot"], p, fecha), [{"tipo": "post"}]
            if not match["compatible"]:
                continue
            if marca:
                extra.append({"post_ubicacion": marca, "pista": row["snapshot"].get("ubicacion_deducida", "")})
                sin_confirmar += marca == "sin_confirmar"
            vistas.add(row["vacante_id"])
            estrictas[p.id] = estrictas.get(p.id, 0) + 1
            filas.append(fila(dict(row, match_grade=entrega.GRADO_CONTRATO.get(afinidad, "close")), p, str(cargo.id),
                              match["pruebas"], extra))
            añadidos += 1
    return añadidos


def _sumar_busquedas(anteriores, nuevas):
    """«Búsquedas hoy» por persona y fuente: suma las pasadas del día (una segunda búsqueda o una captura horaria no
    borran lo que ya se buscó hoy)."""
    salida = {p: dict(f) for p, f in (anteriores or {}).items() if isinstance(f, dict)}
    for perfil, fuentes in (nuevas or {}).items():
        for fuente, n in (fuentes or {}).items():
            salida.setdefault(perfil, {})[fuente] = salida.get(perfil, {}).get(fuente, 0) + int(n or 0)
    return salida


def registrar(repo, version, fecha, reporte=None, reglas_info=None, vacantes=None, cache_enlaces=None,
              limites_rescate=(MAX_COMPROBAR_RESCATE, SEGUNDOS_RESCATE), revision_lote=None):
    """Reconstruible desde la selección confirmada, incluso tras perder el proceso anterior.
    Contrato v43: asigna con la versión confirmada más nueva (aunque la búsqueda empezara con otra); una vacante del
    lote llega también a perfiles de otros cargos que la aceptan; Comunidad recibe después de los clientes reales,
    prefiere lo que ellos no recibieron y se corta en su meta diaria."""
    version = vigente(repo, version, fecha)
    ejecucion = iniciar(repo, version, fecha)
    cfg = validar_version(version)
    clientes = {str(c.id): c for c in cfg.clientes}

    def de_comunidad(p):
        return bool(getattr(clientes.get(str(p.cliente_id)), "comunidad", False))
    activos = [c for c in cfg.cargos if c.activo]
    cargos_json = {str(c.id): c.model_dump(mode="json") for c in activos}
    seleccionadas = repo.pedir("GET", "entregas_diarias", params={"delivery_date": "eq." + fecha, "select": "*", "limit": 500})
    filas, conteos, estrictas, ampliables = [], {}, {}, []
    def fila(row, p, cargo_id, pruebas, extra=()):
        c = next(c for c in cfg.cargos if str(c.id) == cargo_id)
        _, evidencia = grado(row["snapshot"]["titulo"], c.model_dump(mode="json"), cercanos=True)
        return {"ejecucion_id": ejecucion["id"], "cliente_id": str(p.cliente_id),
                "perfil_id": str(p.id), "cargo_id": cargo_id, "vacante_id": row["vacante_id"],
                "match_grade": row["match_grade"], "explicacion": [*pruebas, evidencia or {"regla": "similitud textual"}, *extra],
                "filtros": p.model_dump(mode="json"), "cargo_configuracion": c.model_dump(mode="json")}
    comunidad, de_reales = [], set()
    for row in seleccionadas:
        if not row["role_id"].startswith("cargo:"):
            continue
        cargo_id = row["role_id"].split(":", 1)[1]
        conteos[cargo_id] = conteos.get(cargo_id, 0) + 1
        candidatos = [(p, cargo_id) for p in cfg.perfiles_activos(cargo_id)] if cargo_id in cargos_json else []
        # Contrato v43: si la vacante también es del otro cargo (exacto o similar; nunca solo «cercano»), llega a sus
        # perfiles sin ocupar su cupo.
        for otro, cargo in cargos_json.items():
            if otro != cargo_id and grado(row["snapshot"].get("titulo", ""), cargo)[0]:
                candidatos += [(p, otro) for p in cfg.perfiles_activos(otro)]
        for p, cid in candidatos:
            match = evaluar(row["snapshot"], p, fecha)
            if match["compatible"]:
                if de_comunidad(p):  # después de los clientes reales (abajo)
                    comunidad.append((row, p, cid, match["pruebas"]))
                    continue
                estrictas[p.id] = estrictas.get(p.id, 0) + 1
                filas.append(fila(row, p, cid, match["pruebas"]))
                de_reales.add(row["vacante_id"])
            elif cid == cargo_id and row["snapshot"].get("_ampliacion") in AMPLIACIONES:
                ampliables.append((row, p, cargo_id))
    # Contrato v43 (decisión de Oscar): Comunidad hasta su meta, primero con lo que no recibió ningún cliente real.
    comunidad.sort(key=lambda x: x[0]["vacante_id"] in de_reales)
    for row, p, cid, pruebas in comunidad:
        if estrictas.get(p.id, 0) >= (p.meta_diaria or 0):
            continue
        estrictas[p.id] = estrictas.get(p.id, 0) + 1
        filas.append(fila(row, p, cid, pruebas))
    # Contrato v9: lo ampliado solo se asigna a perfiles que no llegaron al mínimo con vacantes que cumplen todo.
    for row, p, cargo_id in ampliables:
        nivel = row["snapshot"]["_ampliacion"]
        if estrictas.get(p.id, 0) >= MINIMO_POR_PERFIL or (de_comunidad(p) and estrictas.get(p.id, 0) >= (p.meta_diaria or 0)):
            continue
        match = evaluar_ampliada(row["snapshot"], p, fecha, nivel)
        if match["compatible"]:
            estrictas[p.id] = estrictas.get(p.id, 0) + 1
            filas.append(fila(row, p, cargo_id, match["pruebas"], [{"ampliacion": nivel}]))
    reutilizadas = posts = rescatadas = 0
    try:
        reutilizadas = _reutilizar(repo, cfg, fecha, estrictas, filas, fila)
    except Exception as e:  # noqa: BLE001 — completar con días anteriores nunca impide registrar lo del día
        registro.aviso("ejecutor:329", e)
    if vacantes:
        bodega.etapa("Completar a quien va corto con toda la bodega")
        try:
            rescatadas = _rescatar(repo, cfg, fecha, estrictas, filas, fila, vacantes, cache=cache_enlaces,
                                   maximo=limites_rescate[0], segundos=limites_rescate[1])
        except Exception as e:  # noqa: BLE001 — completar nunca impide registrar lo del día
            registro.aviso("ejecutor:rescate-general", e)
    bodega.etapa(f"Asignadas {len(filas)}; completar con posts a quien va corto")
    try:
        posts = _posts(repo, cfg, fecha, estrictas, filas, fila)
    except Exception as e:  # noqa: BLE001 — los posts son el último recurso; nunca impiden registrar lo del día
        registro.aviso("ejecutor:334", e)
    for inicio in range(0, len(filas), 250):
        repo.pedir("POST", "panel_asignaciones", params={"on_conflict": "ejecucion_id,perfil_id,vacante_id"},
                    json=filas[inicio:inicio + 250], headers={"Prefer":"resolution=ignore-duplicates"})
    por_confirmar = {}
    if hasattr(repo, "candidatas_por_confirmar"):
        try:  # contrato v16: bandeja «Por confirmar» (y lo que las reglas del operador ya resuelven solas)
            from panel import revision
            bodega.etapa("Preparar la bandeja «Por confirmar»")
            por_confirmar = revision.preparar_cola(repo, cfg, fecha, estrictas, filas)
        except Exception:  # noqa: BLE001 — la bandeja es una ayuda; nunca impide registrar lo del día
            por_confirmar = {}
    faltantes = {c.nombre: max(0, c.cupo - conteos.get(str(c.id), 0)) for c in cfg.cargos if c.activo}
    from buscador.validacion import errores_catalogo, errores
    confirmado = reporte is None or not (errores_catalogo(reporte) if reporte.get("modo") == "incremental" else errores(reporte))
    repo.pedir("PATCH", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"]},
        json={"estado": "parcial" if any(faltantes.values()) or not confirmado else "completa",
              "resumen": {"vacantes": sum(conteos.values()), "meta": cfg.total, "techo": cfg.techo_diario,
                          # Contrato v43: cifras que no se contradicen en el Resumen.
                          "vacantes_vigentes": sum(n for c, n in conteos.items() if c in cargos_json),
                          "vacantes_anteriores": sum(n for c, n in conteos.items() if c not in cargos_json),
                          "asignaciones_comunidad": sum(1 for f in filas if getattr(clientes.get(f["cliente_id"]), "comunidad", False)),
                          "revision_del_lote": revision_lote if revision_lote is not None else
                                               (ejecucion.get("resumen") or {}).get("revision_del_lote"),
                          **({"revisiones_anteriores": (ejecucion.get("resumen") or {})["revisiones_anteriores"]}
                             if (ejecucion.get("resumen") or {}).get("revisiones_anteriores") else {}),
                          "metas": cfg.metas(), "faltantes": faltantes,
                          "asignaciones": len(filas),
                          "ampliadas": sum(any(isinstance(e, dict) and e.get("ampliacion") for e in f["explicacion"]) for f in filas),
                          "reutilizadas": reutilizadas, "rescatadas": rescatadas, "posts": posts, **por_confirmar,
                          **({"busquedas_por_perfil": b} if (b := _sumar_busquedas(
                              (ejecucion.get("resumen") or {}).get("busquedas_por_perfil"),
                              (reporte or {}).get("busquedas_por_perfil"))) else {}),
                          **({"reglas": reglas_info} if reglas_info else {}),
                          "perfiles_bajo_minimo": sum(1 for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))
                                                      if estrictas.get(p.id, 0) < MINIMO_POR_PERFIL),
                          **({"embudo": embudo} if (embudo := _embudo_por_nombre(reporte) or
                                                    (ejecucion.get("resumen") or {}).get("embudo")) else {})},
              "terminada_en": datetime.now().astimezone().isoformat()})


def correr(salida, modo="diario", prueba=False, repo=None, enfoque=ENFOQUE_COMPLETO):
    """`enfoque` (contrato v45): «faltantes» = «Buscar ahora» cuando la búsqueda de hoy ya corrió y hay perfiles bajo su
    meta: se busca más a fondo solo para ellos. Si hoy aún no hay búsqueda, se hace la completa."""
    fecha = hoy()
    if prueba:
        return bodega.correr(salida, modo=modo, prueba=True)
    repo = repo or RepositorioSupabase()
    version = repo.operativa(fecha)
    if not version:
        return bodega.correr(salida, modo=modo)
    enfocar = None
    if enfoque == ENFOQUE_FALTANTES and modo == "diario":
        try:
            faltan = faltan_hoy(repo, version, fecha)
            enfocar = None if faltan is None else {str(p.id) for p, _, _ in faltan}
        except Exception as e:  # noqa: BLE001 — sin el dato, la búsqueda completa de siempre
            registro.aviso("ejecutor:faltantes", e)
        if enfocar is not None and not enfocar:
            # El panel no lo lanza si todos cumplen; si cambió mientras tanto, se hace la búsqueda de siempre (el
            # flujo publica y comprueba salud.json: una salida temprana lo dejaría sin reporte).
            bodega.etapa("Todos los perfiles llegan hoy a su meta: búsqueda normal del día")
            enfocar = None
        if enfocar:
            bodega.etapa(f"Buscar más a fondo para {len(enfocar)} perfiles bajo su meta")
    ejecucion = iniciar(repo, version, fecha)
    reglas_info, reglas = {}, []
    if hasattr(repo, "decisiones_ubicacion"):
        try:  # contrato v17: aprender de las decisiones del operador y cargar todas las reglas activas, sin IA
            from panel import aprender
            reglas_info, reglas = aprender.preparar(repo)
        except Exception:  # noqa: BLE001 — sin reglas la búsqueda sigue igual que antes
            paises.cargar_reglas()
    try:
        aprendidos = {}
        if hasattr(repo, "ajuste"):
            try:  # contrato v25: títulos aprendidos en la bandeja
                aprendidos = repo.ajuste("titulos_aprendidos", {}) or {}
            except Exception:  # noqa: BLE001 — sin ellos la búsqueda sigue igual
                aprendidos = {}
        # Contrato v43 (decisión de Oscar, 18 nov): si la configuración se confirmó hoy después de armar el lote, la
        # siguiente pasada horaria también arma lote para lo que falte (excepción a «la captura horaria no entrega»).
        lote_de = (ejecucion.get("resumen") or {}).get("revision_del_lote")
        completar = modo == "incremental" and lote_de is not None and lote_de != version["revision"]
        with activar(version, fecha, aprendidos, perfiles_cortos(repo, version, fecha), enfocar):
            if completar:
                bodega._config_operativa["completar_lote"] = True
            if hasattr(repo, "decisiones_ubicacion"):
                try:  # contrato v17: cada decisión de la bandeja vale en esta búsqueda
                    from panel.revision import decisiones_para_busqueda
                    bodega._config_operativa["decisiones_operador"] = decisiones_para_busqueda(repo.decisiones_ubicacion())
                except Exception as e:  # noqa: BLE001
                    registro.aviso("ejecutor:393", e)
            previas = bodega._leer_json(Path(salida) / "trabajo/bodega.json.gz", [])
            cargos = version["configuracion"]["cargos"]
            bodega._config_operativa["empresas_objetivo"] = sorted({v["empresa"] for v in previas
                if any(c["activo"] and grado(v["titulo"],c)[0] for c in cargos)})[:120]
            reporte = bodega.correr(salida, modo=modo, hoy=fecha)
            from buscador import cobertura
            busquedas = cobertura.busquedas_por_persona()  # contrato v40, solo en el resumen privado de Supabase
            bodega.etapa("Registrar asignaciones por perfil")
            if reglas:
                try:
                    from panel import aprender
                    reglas_info["ubicaciones_resueltas_por_reglas"] = aprender.guardar_usos(repo, reglas)
                except Exception as e:  # noqa: BLE001
                    registro.aviso("ejecutor:405", e)
            # Contrato v36: la bodega completa de la noche, para completar el mínimo de cada persona.
            trabajo = Path(salida) / "trabajo"
            registrar(repo, version, fecha, dict(reporte or {}, busquedas_por_perfil=busquedas), reglas_info,
                      vacantes=bodega._leer_json(trabajo / "bodega.json.gz", []),
                      cache_enlaces=bodega._leer_json(trabajo / "verificacion_enlaces.json", {}),
                      limites_rescate=(30, 60) if modo == "incremental" else (MAX_COMPROBAR_RESCATE, SEGUNDOS_RESCATE),
                      revision_lote=version["revision"] if modo != "incremental" or completar else None)
            if modo != "incremental":
                try:  # borradores de WhatsApp listos para revisar; un fallo aquí nunca tumba la búsqueda
                    from panel import borradores
                    borradores.generar(repo, fecha)
                except Exception as e:  # noqa: BLE001
                    registro.aviso("ejecutor:412", e)
            return reporte
    except Exception:
        aviso = "La captura requiere revisión; se conserva su historial y pendientes."
        try:
            actual = (repo.pedir("GET", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"], "limit": 1}) or [{}])[0]
            if actual.get("estado") in ("parcial", "completa"):
                # Una pasada posterior fallida (mañana, cada hora) no borra el resultado ya registrado del día.
                cambio = {"resumen": {**(actual.get("resumen") or {}), "aviso_ultima_pasada": aviso}}
            else:
                cambio = {"estado": "fallida", "resumen": {"error": aviso}}
            repo.pedir("PATCH", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"]}, json=cambio)
        except Exception as e:
            registro.aviso("ejecutor:425", e)
        raise
    finally:
        paises.cargar_reglas()  # las reglas viven solo durante esta búsqueda


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", required=True)
    parser.add_argument("--modo", choices=["diario", "incremental", "inicial"], default="diario")
    parser.add_argument("--prueba", action="store_true")
    parser.add_argument("--enfoque", choices=[ENFOQUE_COMPLETO, ENFOQUE_FALTANTES], default=ENFOQUE_COMPLETO,
                        help="faltantes: «Buscar ahora» para quienes hoy no llegan a su meta (contrato v45)")
    parser.add_argument("--config", help="Versión ficticia para ensayo dirigido; requiere --prueba")
    args = parser.parse_args()
    if args.config:
        if not args.prueba: parser.error("--config requiere --prueba; producción lee únicamente Supabase")
        import json
        version = json.loads(Path(args.config).read_text())
        with activar(version,hoy()): bodega.correr(args.salida,modo=args.modo,prueba=True)
    else:
        correr(args.salida, args.modo, args.prueba, enfoque=args.enfoque)


if __name__ == "__main__":
    main()
