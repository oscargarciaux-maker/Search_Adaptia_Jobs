"""Vistas y texto para copiar; nunca se envía WhatsApp."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time

from buscador import contrato, enlaces, registro, vacante
from panel.afinidad import (AMPLIACIONES, ETIQUETAS_AMPLIACION, MINIMO_POR_PERFIL, enlace_utilizable, evaluar,
                            evaluar_ampliada, evaluar_post, post_ubicacion)
from panel.repositorio import ErrorRepositorio, hoy
from panel.terminos import grado, sugerir

# Qué puede hacer el operador cuando un filtro, por sí solo, deja fuera vacantes. Sin sugerencia si no depende de él.
# Desde v27 solo descartan la ubicación, el idioma y las reglas del sistema: años, inglés y restricciones solo ordenan.
SUGERENCIAS = {
    "publicación fuera del plazo": "Ampliar la antigüedad de publicación",
    "oficina en otro país": "Añadir una ubicación donde trabajaría",
    "oficina en otra ciudad": "Añadir la ciudad a sus ubicaciones",
    "no admite postular desde su país": "Añadir un país donde puede trabajar en remoto",
    "modalidad diferente": "Aceptar otra modalidad",
    "idioma del aviso diferente": "Aceptar avisos en español e inglés",
    "inglés requerido superior al indicado": "Subir el nivel de inglés del perfil",  # contrato v32
}
_POR_CARGO = {}
_log = logging.getLogger(__name__)


def _del_cargo(catalogo, cargo, cercanas=False):
    """Vacantes del catálogo que corresponden al cargo (o, con `cercanas`, solo las de sus oficios vecinos). Editar
    filtros de un perfil no cambia este resultado, así que se reutiliza mientras no cambien el catálogo ni los términos."""
    clave = (catalogo["actualizado"], len(catalogo["vacantes"]), cargo["nombre"], tuple(cargo["terminos_exactos"]),
             tuple(cargo["terminos_similares"]), tuple(cargo["terminos_excluidos"]),
             tuple(cargo.get("terminos_cercanos", [])), cercanas)
    if clave not in _POR_CARGO:
        if len(_POR_CARGO) > 200:
            _POR_CARGO.clear()
        if cercanas:
            _POR_CARGO[clave] = [v for v in catalogo["vacantes"]
                                 if grado(v.get("titulo") or "", cargo, cercanos=True)[0] == "cercano"]
        else:
            _POR_CARGO[clave] = [v for v in catalogo["vacantes"] if grado(v.get("titulo") or "", cargo)[0]]
    return _POR_CARGO[clave]


def _ampliables(del_cargo, cercanas, p, fecha, ya):
    """Cuántas más recibiría el perfil por ampliación (contrato v9), sin pasar del mínimo diario."""
    if len(ya) >= MINIMO_POR_PERFIL:
        return 0
    extra = set()
    for nivel in AMPLIACIONES:
        for v in del_cargo + cercanas:
            if v["id"] not in ya and v["id"] not in extra and evaluar_ampliada(v, p, fecha, nivel)["compatible"]:
                extra.add(v["id"])
                if len(ya) + len(extra) >= MINIMO_POR_PERFIL:
                    return len(extra)
    return len(extra)


def _contar(vacantes, p, fecha):
    """(ids compatibles, filtros que por sí solos dejan fuera más vacantes, con su sugerencia)."""
    ids, solo = set(), Counter()
    for v in vacantes:
        r = evaluar(v, p, fecha)
        if r["compatible"]:
            ids.add(v["id"])
        elif len(r["motivos"]) == 1:
            solo[r["motivos"][0]] += 1
    limitantes = [{"motivo": m, "vacantes": n, "sugerencia": SUGERENCIAS[m]} for m, n in solo.items() if m in SUGERENCIAS]
    return ids, sorted(limitantes, key=lambda x: -x["vacantes"])[:3]


def vista_previa(repo, cfg, fecha=None):
    """Cuántas vacantes ya guardadas y aún no entregadas cumplirían hoy cada perfil y cargo del borrador.
    Es una estimación con las mismas reglas de la selección; no busca, no guarda y no devuelve vacantes ni clientes."""
    fecha = fecha or hoy()
    catalogo = repo.catalogo_vigente()
    clientes = {c.id for c in cfg.clientes if c.activo}
    perfiles, cargos, anteriores = {}, {}, []
    for c in cfg.cargos:
        if not c.activo:
            continue
        raw = c.model_dump(mode="json")
        if not raw["terminos_exactos"]:  # igual que la captura dirigida
            raw["terminos_exactos"] = sugerir(c.nombre, consultar_esco=False)["terminos_exactos"]
        # Contrato v27: los cargos cercanos entran directamente, después de exactos y similares.
        del_cargo = _del_cargo(catalogo, raw) + _del_cargo(catalogo, raw, cercanas=True)
        dadas = {"actualizado": catalogo["actualizado"] + "#entregadas",
                 "vacantes": catalogo.get("entregadas_vacantes") or []}
        del_dadas = _del_cargo(dadas, raw) + _del_cargo(dadas, raw, cercanas=True) if dadas["vacantes"] else []
        disponibles = set()
        for p in cfg.perfiles:
            if not p.activo or p.cargo_id != c.id or p.cliente_id not in clientes:
                continue
            ids, limitantes = _contar(del_cargo, p, fecha)
            disponibles |= ids
            # Contrato v35: las que cumplieron el perfil en los últimos 30 días, entregadas o no (evaluar ya exige 30
            # días de publicación), y su promedio diario. Es la cifra que no asusta: un perfil sencillo nunca sale en 0
            # solo porque hoy ya se entregó lo disponible.
            mes = len(ids) + sum(1 for v in del_dadas if evaluar(v, p, fecha)["compatible"])
            perfiles[str(p.id)] = {"compatibles": len(ids), "del_cargo": len(del_cargo), "limitantes": limitantes,
                                   "ampliables": _ampliables(del_cargo, [], p, fecha, ids),
                                   "ultimos_30": mes, "por_dia": round(mes / 30, 1)}
        n = len(disponibles)
        estado = ("sin_cupo" if not c.cupo else "alcanza" if n >= c.cupo else "justo" if n * 2 >= c.cupo
                  else "insuficiente")
        # Cada vacante va a un solo cargo: si coincide igual de bien con uno anterior de la lista, se lo lleva ese.
        propios = {v["id"] for v in del_cargo}
        solapes = [{"cargo": nombre, "vacantes": len(propios & ids)} for nombre, ids in anteriores if propios & ids]
        anteriores.append((c.nombre, propios))
        cargos[str(c.id)] = {"disponibles": n, "del_cargo": len(del_cargo), "cupo": c.cupo, "estado": estado,
                             "solapes": solapes}
    return {"catalogo": {"vacantes": len(catalogo["vacantes"]), "actualizado": catalogo["actualizado"]},
            "perfiles": perfiles, "cargos": cargos,
            "nota": "Estimación con vacantes ya guardadas y aún no entregadas. La búsqueda dirigida de mañana "
                    "puede encontrar otras; un cargo nuevo empieza con pocas porque todavía no se ha buscado."}


# ── Estimación con búsqueda en vivo ───────────────────────────────────────────────────────────────────────────────
# Una muestra corta en las fuentes públicas (LinkedIn sin sesión y Get on Board), nunca Apify ni cookies. Se protege la
# IP del servidor: una búsqueda a la vez y una espera mínima por perfil, porque un bloqueo de LinkedIn también afectaría
# a la captura real.
LIMITE_SEGUNDOS = 25
ESPERA_PERFIL = 120
NOTA_EN_VIVO = ("Es una muestra: las fuentes muestran solo parte de los resultados y esta búsqueda revisa pocas "
                "páginas; la búsqueda de la noche revisa más y añade otros portales.")
_EN_CURSO = threading.Lock()
_ULTIMA = {}


class _SinInsistir:
    """Ante un 429 no espera ni reintenta: la estimación se conforma con lo obtenido."""

    def __init__(self, cliente):
        self.cliente = cliente

    def get(self, url, params=None, **k):
        return self.cliente.get(url, params=params, reintentar_429=False, **k)

    def json(self, url, params=None, **k):
        return self.cliente.json(url, params=params, reintentar_429=False, **k)


def fuentes_publicas(cargo, perfil, limite_segundos):
    """Avisos crudos de LinkedIn público (país de residencia y remotas regionales) y Get on Board, en paralelo."""
    from buscador.fuentes import getonbrd, linkedin_publico
    from buscador.http import Cliente
    from panel.ejecutor import lugares_perfil
    terminos = [cargo["nombre"], *cargo["terminos_exactos"], *cargo["terminos_similares"]]
    familia = {"id": "vivo", "consultas": terminos, "lugares": list(lugares_perfil(perfil).items())}

    def linkedin():
        cliente = _SinInsistir(Cliente(pausa=(0.3, 0.7), timeout=6))
        return linkedin_publico.buscar(cliente, [familia], [], {}, presupuesto=len(familia["lugares"]),
                                       max_fichas=12, max_dias=perfil.antiguedad_dias, reloj=time.monotonic,
                                       limite_segundos=limite_segundos - 8, max_paginas=1)

    def getonboard():
        return getonbrd.buscar(_SinInsistir(Cliente(pausa=(0.2, 0.4), timeout=6)), terminos[:2])

    crudas, fuentes = [], {}
    hilos = ThreadPoolExecutor(2)
    fin = time.monotonic() + limite_segundos + 5
    try:
        for nombre, futuro in (("LinkedIn", hilos.submit(linkedin)), ("Get on Board", hilos.submit(getonboard))):
            try:
                filas, stats = futuro.result(timeout=max(0.1, fin - time.monotonic()))
                crudas += filas
                fuentes[nombre] = {k: stats.get(k, 0) for k in ("busquedas", "fallidas", "avisos")}
            except Exception:  # noqa: BLE001 - una fuente caída o lenta no impide estimar con la otra
                fuentes[nombre] = {"error": True}
    finally:
        # Sin esperar a una fuente colgada: si no, la búsqueda quedaba «en curso» y bloqueaba las siguientes (13 nov).
        hilos.shutdown(wait=False, cancel_futures=True)
    return crudas, fuentes


def estimacion_en_vivo(repo, cfg, perfil_id, fecha=None, fuentes=None, reloj=time.monotonic):
    """Cuántos avisos encontrados ahora en las fuentes públicas cumplen el perfil. No guarda nada ni devuelve vacantes."""
    fecha = fecha or hoy()
    p = next((x for x in cfg.perfiles if str(x.id) == str(perfil_id)), None)
    c = p and next((x for x in cfg.cargos if x.id == p.cargo_id), None)
    if not c:
        return {"error": "Perfil o cargo no encontrado en la configuración."}
    if not _EN_CURSO.acquire(blocking=False):
        return {"ocupado": True, "nota": "Ya hay otra búsqueda en vivo en curso (quizá en otra pestaña). Espera unos "
                                         "30 segundos y vuelve a intentarlo."}
    try:
        return _estimar_en_vivo(repo, p, c, perfil_id, fecha, fuentes, reloj)
    except ErrorRepositorio as e:  # la base no respondió: su mensaje ya está en lenguaje sencillo
        return {"error": e.mensaje}
    except Exception:  # noqa: BLE001 - el operador recibe una frase; el detalle queda en el registro del servidor
        _log.exception("La estimación en vivo falló")
        return {"error": "La búsqueda en vivo falló por un error del servidor. Inténtalo de nuevo en un minuto; "
                         "el detalle quedó en el registro del panel."}
    finally:
        _EN_CURSO.release()


def _estimar_en_vivo(repo, p, c, perfil_id, fecha, fuentes, reloj):
    """Cuerpo de `estimacion_en_vivo`, ya con el turno tomado."""
    inicio = reloj()
    falta = ESPERA_PERFIL - (inicio - _ULTIMA.get(str(perfil_id), -ESPERA_PERFIL))
    if falta > 0:
        return {"espera": int(falta) + 1,
                "nota": f"Para no saturar las fuentes, espera {int(falta) + 1} s antes de repetir este perfil."}
    _ULTIMA[str(perfil_id)] = inicio
    raw = c.model_dump(mode="json")
    if not raw["terminos_exactos"]:
        raw["terminos_exactos"] = sugerir(c.nombre, consultar_esco=False)["terminos_exactos"]
    buscar = fuentes or getattr(repo, "fuentes_en_vivo", None) or fuentes_publicas
    crudas, por_fuente = buscar(raw, p, LIMITE_SEGUNDOS)
    catalogo = repo.catalogo_vigente()
    guardadas = {v["id"] for v in catalogo["vacantes"]}
    entregadas = set(catalogo.get("entregadas") or ())
    vistas, del_cargo, ya_entregadas = set(), [], 0
    for x in crudas:
        if not grado(x.get("titulo") or "", raw)[0]:
            continue
        # `consulta` = el propio título: el cargo ya se comprobó con sus términos, no con el mapa nocturno.
        v = vacante.crear(x.get("titulo"), x.get("empresa"), x.get("enlace"), x.get("fuente", ""),
                          ubicacion=x.get("ubicacion", ""), descripcion=x.get("descripcion", ""),
                          fecha=x.get("fecha", ""), remoto=x.get("remoto"), hoy=fecha, consulta=x.get("titulo"))
        if not v or v["id"] in vistas or contrato.url_limpia(v["enlace"]) in vistas:
            continue
        vistas |= {v["id"], contrato.url_limpia(v["enlace"])}
        if v["id"] in entregadas:
            ya_entregadas += 1
            continue
        del_cargo.append(v)
    ids, limitantes = _contar(del_cargo, p, fecha)
    return {"compatibles": len(ids), "del_cargo": len(del_cargo), "nuevas": len(ids - guardadas),
            "ya_entregadas": ya_entregadas, "avisos": len(crudas), "limitantes": limitantes,
            "fuentes": por_fuente, "segundos": round(reloj() - inicio, 1), "nota": NOTA_EN_VIVO}


def resultados(repo, cliente_id=None, fecha=None):
    r = repo.resultados(cliente_id, fecha)
    salida, vistas = [], {}
    # Una búsqueda de un día anterior ya se entregó: sus enlaces dejan de recomprobarse y caducan a las 6 h (contrato
    # v9). Sus vacantes compatibles se muestran «Entregada el …», no «por confirmar» (13 nov).
    dia = ((r.get("ejecucion") or {}).get("fecha") or "")[:10]
    pasada = bool(dia) and dia < hoy()
    for row in r["filas"]:
        v = row.get("catalogo_vacantes") or {}
        datos = v.get("datos") or {}
        # Los datos públicos no traen las observaciones de ubicación ni el origen de la fecha: conservar lo que calculó
        # la bodega en vez de rehacerlo con menos evidencia.
        actual = vacante.reetiquetar(dict(datos, _descripcion=v.get("description_full") or datos.get("_descripcion", "")),
                                     publicada=True)
        # Contrato v16: una vacante confirmada en la bandeja se evalúa con los países decididos. En el catálogo seguía
        # archivada solo por «elegibilidad regional por confirmar»: eso ya no la retira.
        from panel.revision import aplicar_confirmacion
        confirmada = aplicar_confirmacion(actual, row.get("explicacion"))
        if confirmada is not actual:
            actual = confirmada
            if v.get("status") == "archived" and v.get("reason") == "elegibilidad regional por confirmar":
                v = dict(v, status="active")
                row = dict(row, catalogo_vacantes=v)
        ampliacion = next((e["ampliacion"] for e in row.get("explicacion") or [] if isinstance(e, dict) and e.get("ampliacion")), "")
        if ampliacion:
            filtros = evaluar_ampliada(actual, row["filtros"], hoy(), ampliacion)
        elif actual.get("tipo") == "post":  # contrato v28: post deducido o sin confirmar
            filtros = evaluar_post(actual, row["filtros"], hoy())
        else:
            filtros = evaluar(actual, row["filtros"], hoy())
        afinidad_cargo, _ = grado(actual["titulo"], row["cargo_configuracion"], cercanos=True)  # v27
        if not afinidad_cargo:
            filtros["compatible"] = False
            filtros["motivos"].append("el título actual no corresponde al cargo configurado")
        es_post = actual.get("tipo") == "post"  # contrato v11: post de LinkedIn sin ficha formal, con su etiqueta
        no_apta = contrato.entregable_post(actual) if es_post else contrato.entregable(actual, panel=True)
        enlace = enlace_utilizable(row) if filtros["compatible"] and not no_apta else ""
        clave = row["vacante_id"]
        if clave in vistas and (vistas[clave]["estado"] == "lista" or not enlace):
            continue
        ficha = {"id": clave, "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": datos.get("ubicacion", ""), "modalidad": datos.get("modalidad", ""),
            "idioma": datos.get("idioma", ""), "publicada": datos.get("fecha_publicacion", ""),
            "experiencia": datos.get("anos_min"), "match_grade": row["match_grade"],
            "explicacion": row["explicacion"], "cargo_id": row["cargo_id"], "enlace": enlace,
            "cargo_nombre": (row.get("cargo_configuracion") or {}).get("nombre", ""),
            "estado": "lista" if enlace else "retirada" if v.get("status") != "active" else
                      "entregada" if pasada and filtros["compatible"] and not no_apta else "por_confirmar",
            "entregada_el": dia if pasada else "",
            "motivos": filtros["motivos"], "avisos": filtros.get("avisos", []), "ampliacion": ETIQUETAS_AMPLIACION.get(ampliacion, "") if not es_post else "",
            "tipo": "post" if es_post else "", "contacto": (datos.get("contacto") or {}) if es_post else {},
            "post_ubicacion": post_ubicacion(actual)}
        if ficha["estado"] == "entregada" and enlaces.sirve(datos.get("enlace") or ""):
            ficha["enlace"] = datos["enlace"]  # para consultarla; no cuenta como lista ni va al WhatsApp
        if clave in vistas:
            salida[salida.index(vistas[clave])] = ficha
        else:
            salida.append(ficha)
        vistas[clave] = ficha
    return {**{k: r[k] for k in ("ejecucion", "clientes")}, "vacantes": salida,
            "listas": sum(v["estado"] == "lista" for v in salida)}


def ficha(repo, vacante_id, traer=True, obtener=None):
    """Contrato v29: lo que muestra el panel a la derecha de la lista. La descripción va en bloques de texto (nunca
    HTML). Si el catálogo no la tiene, se lee una sola vez de la ficha original (lista fija de dominios, 1 MB, 12 s) y
    se guarda para la próxima vez."""
    from buscador import ficha as fichas
    fila = repo.vacante(vacante_id)
    if not fila:
        raise ErrorRepositorio("Esa vacante ya no está en la base. Recarga la lista.", 404)
    datos = fila.get("datos") or {}
    texto, origen = fila.get("description_full") or datos.get("_descripcion") or "", "guardada"
    urls = [datos.get("enlace_directo"), datos.get("enlace"), *(datos.get("enlaces_alternativos") or [])]
    if not texto.strip() and datos.get("tipo") != "post":
        texto, origen = "", "sin_descripcion"
        if traer:
            try:
                texto = fichas.traer_descripcion(urls, datos.get("titulo", ""), obtener=obtener)
            except Exception as e:  # noqa: BLE001 - una ficha caída no debe romper el panel
                registro.aviso("servicio:ficha", e)
            if texto:
                origen = "traida"
                try:
                    repo.guardar_descripcion(vacante_id, texto)
                except Exception as e:  # noqa: BLE001 - se muestra aunque no se pueda guardar
                    registro.aviso("servicio:ficha-guardar", e)
    return {"id": vacante_id, "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": datos.get("ubicacion", ""), "modalidad": datos.get("modalidad", ""),
            "salario": datos.get("salario") or "", "publicada": datos.get("fecha_publicacion", ""),
            "anos_min": datos.get("anos_min"), "ingles": datos.get("ingles") or "", "nivel": datos.get("nivel") or "",
            "enlace": datos.get("enlace", ""), "enlace_directo": datos.get("enlace_directo", ""),
            "tipo": datos.get("tipo") or "", "activa": fila.get("status", "active") == "active",
            "bloques": fichas.bloques(texto), "origen": origen if texto else "sin_descripcion"}


def resumen_clientes(repo, fecha=None, dias=7):
    """Paso 8 (Resumen por cliente): recibidas de cada cliente en las últimas búsquedas, de la más antigua a la de
    hoy. Solo conteos por id; los nombres los pone el panel privado."""
    fecha = fecha or hoy()
    ejecuciones = [e for e in repo.historial_ejecuciones(dias) if str(e.get("fecha", "")) <= fecha][:dias]
    conteo = repo.asignaciones_por_cliente([str(e["id"]) for e in ejecuciones])
    por_dia = []
    for e in reversed(ejecuciones):
        clientes = {}
        for (ejecucion, cliente), n in conteo.items():
            if ejecucion == str(e["id"]):
                clientes[cliente] = clientes.get(cliente, 0) + n
        por_dia.append({"fecha": str(e["fecha"]), "estado": e.get("estado", ""), "clientes": clientes})
    return {"fecha": fecha, "busqueda_de_hoy": any(d["fecha"] == fecha for d in por_dia), "dias": por_dia}


# ── Contrato v37: cobertura por persona ──────────────────────────────────────────────────────────────────────────────
DIAS_COBERTURA = 14
DIAS_PARA_MEDIR = 3  # con menos búsquedas medidas, «aún sin datos»


def cobertura(repo, fecha=None):
    """Por cada perfil activo: si hoy llegó al mínimo, cuántos de sus últimos días lo logró (con su denominador), cuántas
    vacantes tiene listas para mañana (comprobadas y que nunca recibió) y cuántas esperan comprobación, por qué le
    faltan y totales por cargo, país e idioma. Solo cuenta lo medido: nunca reparte el inventario en días."""
    from panel.ejecutor import validar_version
    fecha = fecha or hoy()
    version = repo.operativa(fecha)
    if not version:
        return {"fecha": fecha, "perfiles": [], "grupos": {}, "alertas": [], "sin_configuracion": True}
    cfg = validar_version(version)
    ejecuciones = [e for e in repo.ejecuciones() or [] if str(e.get("fecha", "")) <= fecha][:DIAS_COBERTURA]
    conteo = repo.asignaciones_por_perfil([str(e["id"]) for e in ejecuciones])
    busquedas_ultima = ((ejecuciones[0].get("resumen") or {}).get("busquedas_por_perfil") or {}) if ejecuciones else {}
    configs = repo.versiones([e["revision"] for e in ejecuciones if e.get("revision") is not None])
    presentes = {r: {str(p["id"]) for p in (c or {}).get("perfiles", []) if p.get("activo", True)}
                 for r, c in configs.items()}
    catalogo = repo.catalogo_vigente()
    todas = list(catalogo["vacantes"]) + list(catalogo.get("entregadas_vacantes") or [])
    clientes = {c.id: c for c in cfg.clientes if c.activo}
    perfiles = [(c, p) for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))
                if p.cliente_id in clientes]
    recibidas = repo.recibidas([str(p.id) for _, p in perfiles]) if perfiles else {}
    filas = []
    for cargo, p in perfiles:
        pid = str(p.id)
        dias = [e for e in ejecuciones if pid in presentes.get(e.get("revision"), set())]
        con_minimo = sum(1 for e in dias if conteo.get((str(e["id"]), pid), 0) >= MINIMO_POR_PERFIL)
        hoy_n = conteo.get((str(ejecuciones[0]["id"]), pid), 0) if ejecuciones else 0
        raw = cargo.model_dump(mode="json")
        if not raw["terminos_exactos"]:
            raw["terminos_exactos"] = sugerir(cargo.nombre, consultar_esco=False)["terminos_exactos"]
        base = {"actualizado": catalogo["actualizado"] + "#todas", "vacantes": todas}
        del_cargo = _del_cargo(base, raw) + _del_cargo(base, raw, cercanas=True)
        ya = recibidas.get(pid, set())
        listas = pendientes = 0
        motivos = Counter()
        for v in del_cargo:
            if v["id"] in ya:
                continue
            r = evaluar(v, p, fecha)
            if not r["compatible"]:
                if len(r["motivos"]) == 1:
                    motivos[r["motivos"][0]] += 1
                continue
            if v.get("_verificacion") == "verificada":
                listas += 1
            else:
                pendientes += 1
        if hoy_n >= MINIMO_POR_PERFIL:
            estado = "cubierto"
        elif len(dias) < DIAS_PARA_MEDIR:
            estado = "sin_datos"
        else:
            estado = "pendiente"
        causa = ""
        from panel.ejecutor import _con_fuentes_propias, lugares_perfil, paises_de_lugares
        pocas_fuentes = not set(paises_de_lugares(lugares_perfil(p)) or [p.vive_en]) & _con_fuentes_propias()
        if estado != "cubierto" and hoy_n < MINIMO_POR_PERFIL:
            if not del_cargo:
                causa = "Aún no hay vacantes de este cargo en lo buscado: la próxima búsqueda lo incluye."
            elif listas:
                causa = (f"Hay {listas} {'lista' if listas == 1 else 'listas'} que aún no recibió: la próxima búsqueda "
                         "completa su mínimo con ellas.")
            elif listas + pendientes == 0 and motivos:
                m, n = motivos.most_common(1)[0]
                causa = f"{n} vacantes del cargo no le sirven por «{m}»" + (
                    f": {SUGERENCIAS[m].lower()} daría más." if m in SUGERENCIAS else ".")
            elif pendientes:
                causa = f"{pendientes} le servirían pero aún no tienen el enlace comprobado; se comprueban en la próxima búsqueda."
            else:
                causa = "Pocas vacantes nuevas en las fuentes revisadas para su ubicación e idioma."
            if pocas_fuentes and not listas:
                causa += (" Donde vive o trabajaría solo buscan LinkedIn e Indeed (no hay Computrabajo, Elempleo ni Get on "
                          "Board): tiene el doble de turnos en la búsqueda.")
        seguidos = 0
        for e in dias:
            if conteo.get((str(e["id"]), pid), 0) >= MINIMO_POR_PERFIL:
                break
            seguidos += 1
        filas.append({"perfil_id": pid, "cliente_id": str(p.cliente_id), "cliente": clientes[p.cliente_id].nombre,
                      "cargo": cargo.nombre, "vive_en": p.vive_en, "idiomas": list(p.idiomas), "estado": estado,
                      "hoy": hoy_n, "dias_con_minimo": con_minimo, "dias_medidos": len(dias),
                      "dias_seguidos_bajo": seguidos if len(dias) >= DIAS_PARA_MEDIR else 0,
                      "listas": listas, "por_comprobar": pendientes, "causa": causa,
                      # Contrato v40: páginas buscadas para esta persona en la última búsqueda, por fuente.
                      "busquedas_hoy": busquedas_ultima.get(pid, {}), "pocas_fuentes": pocas_fuentes})
    orden = {"pendiente": 0, "sin_datos": 1, "cubierto": 2}
    filas.sort(key=lambda f: (orden[f["estado"]], f["hoy"], f["cliente"]))

    def agrupar(clave):
        grupos = {}
        for f in filas:
            for k in (f[clave] if isinstance(f[clave], list) else [f[clave]]):
                g = grupos.setdefault(k, {"perfiles": 0, "dias_con_minimo": 0, "dias_medidos": 0})
                g["perfiles"] += 1
                g["dias_con_minimo"] += f["dias_con_minimo"]
                g["dias_medidos"] += f["dias_medidos"]
        return grupos
    # (Las metas nunca pasan el cupo diario: el panel no deja programarlo.)
    alertas = []
    largos = [f for f in filas if f["dias_seguidos_bajo"] >= 3]
    if largos:
        alertas.append(f"{len(largos)} {'persona lleva' if len(largos) == 1 else 'personas llevan'} 3 o más días "
                       "seguidos con menos de 5: revisa su cargo y su ubicación.")
    return {"fecha": fecha, "minimo": MINIMO_POR_PERFIL, "dias_ventana": DIAS_COBERTURA, "perfiles": filas,
            "grupos": {"cargo": agrupar("cargo"), "pais": agrupar("vive_en"), "idioma": agrupar("idiomas")},
            "alertas": alertas,
            "nota": "Cuenta solo lo medido en las búsquedas de cada día. «Listas» son vacantes guardadas, con enlace "
                    "comprobado, que esa persona nunca recibió; no es una promesa para los próximos días."}


def whatsapp(repo, cliente_id, fecha=None):
    r = resultados(repo, cliente_id, fecha)
    from panel import borradores
    listas = borradores.con_posts([v for v in r["vacantes"] if v["estado"] == "lista"])
    if not listas:
        return {"texto": "", "vacantes": 0, "nota": "No hay vacantes con filtros y enlace vigentes para copiar."}
    # Misma plantilla humana que los borradores diarios (contrato v10): cargo y lista, sin enumerar filtros.
    grupos = {}
    for v in listas:
        grupos.setdefault(v.get("cargo_nombre") or "tu perfil", []).append(v)
    contacto = next((c for c in (repo.contactos() if hasattr(repo, "contactos") else [])
                     if c.get("cliente_id") == cliente_id), {})
    nombre = contacto.get("nombre_saludo", "")
    texto = borradores.texto(nombre, list(grupos.items()), (r.get("ejecucion") or {}).get("fecha") or hoy(),
                             str(cliente_id or ""))
    return {"texto": texto, "vacantes": len(listas)}


def proponer_funciones(repo, cargo):
    """Contrato v25: huella de funciones propuesta para un cargo con el catálogo vigente. Sin IA."""
    from panel import funciones
    from panel.terminos import grado
    vacantes = repo.catalogo_vigente()["vacantes"]
    del_cargo = [v["id"] for v in vacantes if v.get("titulo") and grado(v["titulo"], cargo)[0] in ("exacto", "similar")]
    elegidos = set(del_cargo)
    otros = [v["id"] for v in vacantes if v["id"] not in elegidos]
    del_cargo, otros = funciones.muestra_estable(del_cargo, 150), funciones.muestra_estable(otros, 300)
    textos = repo.descripciones(del_cargo + otros)
    con_texto = [textos[i] for i in del_cargo if len(textos.get(i) or "") >= 200]
    if len(con_texto) < 5:
        return {"funciones": [], "vacantes": len(con_texto),
                "motivo": "Aún no hay vacantes suficientes de este cargo con descripción para proponer funciones."}
    propuestas = funciones.proponer(con_texto, [textos[i] for i in otros if textos.get(i)],
                                    excluir=[cargo.get("nombre", ""), *cargo.get("terminos_exactos", [])])
    return {"funciones": propuestas, "vacantes": len(con_texto), "motivo": "" if propuestas else
            "No se encontraron términos que distingan claramente a este cargo."}
