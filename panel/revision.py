"""Contrato v16: bandeja «Por confirmar». Vacantes cuya ubicación no se pudo confirmar sola (ni por el texto ni por la
ficha) y que le servirían a algún cliente si se confirma su país. Se priorizan las que ayudan a perfiles con menos de 5
y se muestran como mucho `tope` (10) a la vez. Sin IA: la persona decide con un clic y el código aplica la decisión.

- «Sirve para…» (con países cubiertos): se asigna a los perfiles a los que ayuda, solo hasta 5 y sin repetir a nadie,
  y se regeneran sus borradores de WhatsApp pendientes.
- «Solo para otro país» / «No sirve»: se descarta y no vuelve a la bandeja. «Saltar»: se aparta por ahora.
- «Aplicar a las iguales»: guarda una regla con esa ubicación exacta (nunca con ubicaciones genéricas como «Remote») y
  decide igual las demás pendientes que la tienen; desde la noche siguiente, las nuevas con esa ubicación se resuelven
  solas sin llegar a la bandeja.
"""
import re
from datetime import datetime, timedelta, timezone

from buscador import entrega, normalizar, paises, vacante
from buscador import registro
from panel.afinidad import MINIMO_POR_PERFIL, evaluar
from panel.terminos import grado

TOPE = 10  # las que se muestran a la vez en el panel
GUARDADAS = 300  # las que se guardan (para el CSV de revisión grande, contrato v17)
GUARDADAS_COMPLETA = 3000  # depuración completa de la base: todas las dudosas
DEPURACION = "depuración completa"
POR_CONFIRMAR = "elegibilidad regional por confirmar"  # razón del catálogo mientras el país no se confirma
RESUELTA_SOLA = "resuelta sola"
POSIBLE_CIERRE = "posiblemente cerrada"
DIAS_SIN_VER = 7     # una vacante que ninguna fuente lista hace una semana probablemente cerró (Expel, 13 nov)
DIAS_PUBLICADA = 30  # la misma antigüedad máxima de la entrega


def grupos_paises():
    """Regiones que el operador puede elegir de una vez (contrato v19): LATAM, Sudamérica, Centroamérica…"""
    d = paises.datos()
    cubiertos = set(d["codigos"])
    sub = {r["nombres"][0]: [c for c in r["paises"] if c in cubiertos] for r in d["subregiones"]}
    sud, centro = sub.get("south america", []), sub.get("central america", [])
    return {"LATAM": list(d["latam"]), "SUDAMERICA": sud, "CENTROAMERICA": centro,
            "SUD_CENTRO_MX": paises.ordenar(sud + centro + ["MX"]), "LATAM_ES": list(d["codigos"])}


def expandir(codigos):
    """Códigos de país con las regiones ya convertidas en sus países."""
    grupos = grupos_paises()
    salida = []
    for c in codigos or []:
        for x in grupos.get(str(c).upper(), [c]):
            if x not in salida:
                salida.append(x)
    return salida


def _sin_revisar(datos, fecha, solo_cierre=False):
    """'' si la vacante debe preguntarse; si no, por qué no: ya resuelta con las reglas vigentes o posiblemente cerrada.
    Con `solo_cierre` (contrato v25, «Coincide por funciones»: la duda es el cargo) solo mira si posiblemente cerró."""
    hoy = datetime.fromisoformat(fecha).date()
    visto = str(datos.get("visto_ultima_vez") or "")[:10]
    publicada = str(datos.get("fecha_publicacion") or "")[:10]
    try:
        if visto and (hoy - datetime.fromisoformat(visto).date()).days > DIAS_SIN_VER:
            return POSIBLE_CIERRE
        if publicada and (hoy - datetime.fromisoformat(publicada).date()).days > DIAS_PUBLICADA:
            return POSIBLE_CIERRE
    except ValueError:
        pass
    if solo_cierre:
        return ""
    # Contratos v18/v19: la lectura de lugares mejoró; si ahora se confirma (o se descarta) sola, no se pregunta.
    r = paises.elegibles(datos.get("titulo", ""), datos.get("ubicacion", ""), (datos.get("_descripcion") or "")[:8000],
                         True if datos.get("modalidad") == "remoto" else None)
    if r["confianza"] in ("alta", "media") and r["nota"] != "por zona horaria":
        return RESUELTA_SOLA
    return ""
DIAS_PENDIENTE = 7
MOTIVO = "ubicación por confirmar"
FUNCIONES = "Coincide por funciones"  # contrato v25: el título no encaja, pero la descripción sí
# Lo único que una confirmación de país puede resolver; cualquier otro motivo deja fuera la vacante para ese perfil.
MOTIVOS_PAIS = {"país sin elegibilidad confirmada", "no admite postular desde su país", "oficina en otro país"}
DECISIONES = ("sirve", "otro_pais", "no_sirve", "saltar")
_GENERICAS = re.compile(r"\b(remote|remoto|remota|remotely|hybrid|hibrido|hibrida|onsite|on site|presencial|job|jobs|"
                        r"trabajo|anywhere|n a|na|tbd|multiple locations|varias ubicaciones|location|locations|"
                        r"ubicacion|flexible|home office|wfh|work from home|desde casa|teletrabajo|office|hq|global)\b")
_PISTA = re.compile(r"\b(based|located|reside|residing|resident|residents|living|live in|from|remote|remoto|remota|"
                    r"latam|latin america|america latina|worldwide|anywhere|ubicad[oa]|residir|resident[e]s?|desde|"
                    r"time ?zone|zona horaria|utc|gmt|office|oficina|country|pais|countries|paises|hybrid|hibrid[oa])\b")


def clave_ubicacion(texto):
    return paises.clave(texto)


def es_generica(texto):
    """Una ubicación sin ningún lugar («Remote», «Remoto», «N/A»): no sirve para crear una regla."""
    resto = re.sub(r"[^a-z]+", " ", _GENERICAS.sub(" ", re.sub(r"[^a-z]+", " ", clave_ubicacion(texto)))).strip()
    return len(resto.replace(" ", "")) < 2  # «MX» o «EC» sí son un lugar


def pista(descripcion, ubicacion=""):
    """La frase del aviso con la mejor evidencia de lugar (país, región, remoto, residencia). Corta, para leer rápido."""
    d = paises.datos()
    mejor, puntos = "", 0
    for frase in re.split(r"(?<=[.!?])\s+|\n+", descripcion or ""):
        frase = " ".join(frase.split())
        if not 15 <= len(frase) <= 400:
            continue
        t = normalizar.texto(frase)
        p = 3 * len(paises._paises_nombrados(t)) + 2 * paises._nombra(t, d["fuera"]) + len(_PISTA.findall(t))
        p += 2 * paises._nombra(t, d["toda_latam"]) + 2 * paises._nombra(t, d["mundo"])
        if p > puntos:
            mejor, puntos = frase, p
    return (mejor or ubicacion or "")[:300]


def sugerencia(texto):
    """Países cubiertos que nombra la pista (para preseleccionar el botón «Sirve para…»)."""
    cubiertos = set(paises.datos()["codigos"])
    return [c for c in paises._paises_nombrados(normalizar.texto(texto or "")) if c in cubiertos]


def con_paises(datos, codigos, por="operador"):
    """La vacante con los países confirmados (nota visible en el panel). Contrato v23: los cubiertos van a `paises`;
    todos (también los de fuera de LATAM y España) a `paises_mundo`; «MUNDO» marca alcance mundial."""
    cubiertos = set(paises.datos()["codigos"])
    codigos = list(codigos)
    return dict(datos, paises=[c for c in codigos if c in cubiertos],
                paises_mundo=[c for c in codigos if c != "MUNDO"],
                alcance_mundial="MUNDO" in codigos or bool(datos.get("alcance_mundial")) and not codigos,
                confianza_pais="alta", nota_pais=f"confirmada por {por}")


def _datos_ligeros(fila_catalogo):
    """Los datos que guardó la búsqueda nocturna más la descripción, sin volver a calcular etiquetas: para recorrer
    cientos de vacantes rápido (botón «Cargar todas», contrato v19). Las tarjetas usan `_datos`."""
    datos = dict((fila_catalogo or {}).get("datos") or {})
    datos["_descripcion"] = (fila_catalogo or {}).get("description_full") or ""
    return datos


def _datos(fila_catalogo):
    datos = dict((fila_catalogo or {}).get("datos") or {})
    return vacante.reetiquetar(dict(datos, _descripcion=(fila_catalogo or {}).get("description_full") or ""),
                               publicada=True)


def resumen_de(datos, motivo="", s=None):
    """Contrato v34: lo que la bandeja muestra de una vacante, calculado de noche y guardado en `panel_revisiones.resumen`
    para que el panel liste sin leer el catálogo ni las descripciones. `datos` lleva `_descripcion` (para la sugerencia)."""
    from panel.sugerir import sugerir
    if motivo == FUNCIONES:  # contrato v25: la duda es el cargo, no el país
        s = {"decision": "sirve", "paises": [], "motivo": "El título es otro, pero las funciones coinciden.", "frase": ""}
    elif s is None:
        s = sugerir(datos) if datos.get("titulo") else {"decision": "", "paises": [], "motivo": "", "frase": ""}
    return {"titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": datos.get("ubicacion", ""), "modalidad": datos.get("modalidad", ""),
            "salario": str(datos.get("salario") or ""), "idioma": datos.get("idioma", ""),
            "publicada": datos.get("fecha_publicacion", ""), "enlace": datos.get("enlace", ""),
            "paises": list(datos.get("paises_mundo") or datos.get("paises") or [])[:8],
            "sugerida": s["decision"], "paises_sugeridos": s["paises"], "por_que": s["motivo"], "frase": s["frase"],
            # 18 nov: para la tarjeta de «Por confirmar» (nivel y un extracto corto de la descripción).
            "nivel": datos.get("nivel") or "", "extracto": extracto(datos.get("_descripcion") or "")}


def extracto(texto, largo=260):
    """Primeras líneas legibles de la descripción, cortadas en una palabra (sin HTML ni saltos)."""
    limpio = " ".join(re.sub(r"<[^>]+>|\*\*", " ", texto or "").split())
    if len(limpio) <= largo:
        return limpio
    return limpio[:largo].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _candidatos_funciones(repo, perfiles, recibidas, estrictas, fecha, desde, motivo_de, ya):
    """Contrato v25: vacantes cuyo título no encaja con un cargo pero la descripción coincide por funciones. Solo para
    los perfiles de ese cargo que cumplen todos sus filtros y nunca la recibieron."""
    salida = []
    for fila in repo.candidatas_por_funciones(desde):
        if fila["id"] in ya:
            continue
        datos = _datos_ligeros(fila)
        if datos.get("idioma") not in ("es", "en") or not datos.get("titulo") or \
                _sin_revisar(datos, fecha, solo_cierre=True):
            continue
        familias_f = {f["familia"] for f in datos.get("familias") or [] if f.get("coincidencia") == "funciones"}
        sirve, halladas = [], []
        for cargo, p in perfiles:
            if "cargo:" + str(cargo.id) not in familias_f or fila["id"] in recibidas.get(str(p.id), set()):
                continue
            if not evaluar(datos, p, fecha)["compatible"]:
                continue
            desc = normalizar.texto(datos.get("_descripcion", ""))[:12000]
            halladas = halladas or [t for t in cargo.funciones if normalizar.contiene_frase(desc, normalizar.texto(t))]
            sirve.append({"perfil_id": str(p.id), "cliente_id": str(p.cliente_id), "cargo_id": str(cargo.id),
                          "faltan": estrictas.get(p.id, 0) < MINIMO_POR_PERFIL})
        if sirve:
            salida.append({"vacante_id": fila["id"], "motivo": FUNCIONES,
                           "pista": "Funciones encontradas: " + ", ".join(halladas[:10]),
                           "ubicacion": clave_ubicacion(datos.get("ubicacion", "")), "sugerencia": [],
                           "perfiles": sirve, "prioridad": sum(100 if s["faltan"] else 10 for s in sirve)
                           + max(0, 30 - _edad(datos, fecha)), "resumen": resumen_de(datos, FUNCIONES)})
    return salida


APLICAR_SUGERENCIAS = True  # contrato v32: las sugerencias claras se aplican solas en la cola de la noche


def _revisiones_sin_texto(repo, estado=None):
    """Filas de la bandeja con su catálogo pero sin descripciones (contrato v34)."""
    try:
        return repo.revisiones(estado=estado, sin_descripcion=True)
    except TypeError:  # repositorios de prueba antiguos
        return repo.revisiones(estado=estado)


def preparar_cola(repo, cfg, fecha, estrictas, filas_hoy=(), completa=False, avance=None):
    """Arma la cola del día al final de la búsqueda (panel/ejecutor.registrar). Devuelve solo conteos.
    `completa` (contrato v17, botón «Cargar todas las dudosas»): todas las vacantes por confirmar del catálogo, también
    las que hoy no le sirven a ningún cliente, para depurar la base entera."""
    perfiles = [(c, p) for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))]
    if not perfiles and not completa:
        return {"por_confirmar": 0}
    desde = None if completa else (datetime.fromisoformat(fecha) - timedelta(days=2)).date().isoformat()
    recibidas = repo.recibidas([str(p.id) for _, p in perfiles])
    for f in filas_hoy:
        recibidas.setdefault(f["perfil_id"], set()).add(f["vacante_id"])
    candidatos, leidas, fuera_idioma, ya_claras = [], 0, 0, 0
    automaticas = {}  # vacante_id → sugerencia clara que se aplica sola (contrato v32)
    filas_catalogo = repo.candidatas_por_confirmar(desde)  # se recorre por páginas, sin guardarlas (contrato v34)
    total = len(filas_catalogo) if isinstance(filas_catalogo, list) else 0
    if avance and not total and hasattr(repo, "contar_por_confirmar"):
        try:
            total = repo.contar_por_confirmar(desde) or 0
        except Exception as e:  # noqa: BLE001 — sin total el avance muestra solo las leídas
            registro.aviso("revision:contar", e)
    sin_revisar = {}  # vacante_id → motivo: cada vacante se evalúa una sola vez por llamada

    def motivo_de(vid, datos):
        if vid not in sin_revisar:
            sin_revisar[vid] = _sin_revisar(datos, fecha)
        return sin_revisar[vid]
    for fila in filas_catalogo:
        leidas += 1
        if avance and leidas % 20 == 0:
            avance(leidas, total)
        datos = _datos_ligeros(fila)
        if datos.get("idioma") not in ("es", "en") or not datos.get("titulo"):
            fuera_idioma += 1
            continue
        if datos.get("confianza_pais") != "baja" and datos.get("nota_pais") != "por zona horaria" or \
                motivo_de(fila["id"], datos):
            ya_claras += 1
            continue
        sirve = []
        for cargo, p in perfiles:
            if fila["id"] in recibidas.get(str(p.id), set()) or not grado(datos["titulo"], cargo.model_dump(mode="json"))[0]:
                continue
            if set(evaluar(datos, p, fecha)["motivos"]) - MOTIVOS_PAIS:
                continue
            sirve.append({"perfil_id": str(p.id), "cliente_id": str(p.cliente_id), "cargo_id": str(cargo.id),
                          "faltan": estrictas.get(p.id, 0) < MINIMO_POR_PERFIL})
        if sirve or completa:
            texto = pista(datos.get("_descripcion", ""), datos.get("ubicacion", ""))
            # Contrato v32: si el aviso lo dice claro (países cubiertos sin extranjeros, o solo extranjeros), la
            # sugerencia se aplica sola y no ocupa la bandeja. «Sin evidencia» o mezclas siguen preguntándose.
            from panel.sugerir import sugerir
            s_auto = sugerir(datos)
            if not completa and APLICAR_SUGERENCIAS and (
                    s_auto["decision"] == "otro_pais" or (s_auto["decision"] == "sirve" and s_auto["paises"])):
                automaticas[fila["id"]] = s_auto
            # Las cargadas a mano (botón) siempre son «depuración completa»: la búsqueda siguiente no las vence.
            candidatos.append({"vacante_id": fila["id"], "motivo": DEPURACION if completa else MOTIVO, "pista": texto,
                               "ubicacion": clave_ubicacion(datos.get("ubicacion", "")), "sugerencia": sugerencia(texto),
                               "perfiles": sirve, "prioridad": sum(100 if s["faltan"] else 10 for s in sirve)
                               + max(0, 30 - _edad(datos, fecha)), "resumen": resumen_de(datos, s=s_auto)})
    if not completa and hasattr(repo, "candidatas_por_funciones"):
        candidatos += _candidatos_funciones(repo, perfiles, recibidas, estrictas, fecha, desde, motivo_de,
                                            {c["vacante_id"] for c in candidatos})
    existentes = {r["vacante_id"]: r for r in _revisiones_sin_texto(repo)}
    # Las pendientes de otras noches que hay que volver a mirar leen su descripción por grupos de 100 y la sueltan.
    releer = [vid for vid, r in existentes.items() if r.get("estado") == "pendiente" and vid not in sin_revisar
              and r.get("motivo") != FUNCIONES and ((r.get("catalogo_vacantes") or {}).get("datos") or {}).get("titulo")
              and (r.get("catalogo_vacantes") or {}).get("reason") == POR_CONFIRMAR]
    for inicio in range(0, len(releer), 100):
        grupo = releer[inicio:inicio + 100]
        sin_texto = [v for v in grupo if "description_full" not in existentes[v]["catalogo_vacantes"]]
        textos = repo.descripciones(sin_texto) if sin_texto else {}
        for vid in grupo:
            cat = existentes[vid]["catalogo_vacantes"]
            motivo_de(vid, _datos_ligeros({**cat, "description_full": textos.get(vid, cat.get("description_full"))}))
    reglas = {r["texto"]: r for r in repo.reglas() if r.get("activa", True)}
    ids = {c["vacante_id"] for c in candidatos}
    # Las que ya tienen una regla del operador se registran y se deciden al instante (no ocupan lugar en la bandeja).
    nuevas = [dict(c, estado="pendiente") for c in candidatos if c["vacante_id"] not in existentes
              and c["ubicacion"] in reglas and not es_generica(c["ubicacion"])]
    por_regla = len(nuevas)
    ahora = datetime.now(timezone.utc)
    vencer = {}  # motivo → [vacante_id]: se actualizan en lote al final (una petición por motivo)
    for vid, r in existentes.items():  # pendientes viejas o que ya no le sirven a nadie: vencidas
        creada = (r.get("creada_en") or ahora.isoformat()).replace("Z", "+00:00")
        edad = ahora - datetime.fromisoformat(creada)
        if r.get("estado") != "pendiente":
            continue
        catalogo_fila = r.get("catalogo_vacantes") or {}
        if catalogo_fila and catalogo_fila.get("reason") != POR_CONFIRMAR and r.get("motivo") != FUNCIONES:
            # El sistema ya la resolvió (ficha, Get on Board, reglas) o dejó de ser entregable: no hace falta preguntar.
            vencer.setdefault(RESUELTA_SOLA, []).append(vid)
            continue
        datos_fila = _datos_ligeros(catalogo_fila) if (catalogo_fila.get("datos") or {}).get("titulo") else {}
        if datos_fila and r.get("motivo") == FUNCIONES:
            motivo_fuera = _sin_revisar(datos_fila, fecha, solo_cierre=True)
        else:
            motivo_fuera = motivo_de(vid, datos_fila) if datos_fila else ""
        if motivo_fuera:
            vencer.setdefault(motivo_fuera, []).append(vid)
            continue
        if r.get("motivo") == DEPURACION:  # las de la depuración completa esperan a la persona (hasta 30 días)
            if edad > timedelta(days=30):
                vencer.setdefault("", []).append(vid)
        elif not completa and (vid not in ids or edad > timedelta(days=DIAS_PENDIENTE)):
            vencer.setdefault("", []).append(vid)
    for motivo, vids in vencer.items():
        for vid in vids:
            existentes[vid] = dict(existentes[vid], estado="vencida")
        repo.vencer_revisiones(vids, motivo)
    pendientes = sum(1 for vid, r in existentes.items() if r.get("estado") == "pendiente" and vid in ids)
    limite = GUARDADAS_COMPLETA if completa else GUARDADAS
    ya_nuevas = {n["vacante_id"] for n in nuevas}
    for c in sorted(candidatos, key=lambda x: -x["prioridad"]):
        if pendientes >= limite:
            break
        if c["vacante_id"] in existentes or c["vacante_id"] in ya_nuevas:
            continue
        nuevas.append(dict(c, estado="pendiente"))
        ya_nuevas.add(c["vacante_id"])
        pendientes += 1
    con_resumen = getattr(repo, "con_resumen", lambda: False)()
    if not con_resumen:  # contrato v34: sin SQL 018 la fila se guarda como antes y el panel calcula el resumen
        nuevas = [{k: v for k, v in n.items() if k != "resumen"} for n in nuevas]
    if nuevas:
        repo.guardar_revisiones(nuevas)
    if con_resumen:  # las pendientes de noches anteriores sin resumen lo reciben una vez (como mucho GUARDADAS)
        por_id = {c["vacante_id"]: c["resumen"] for c in candidatos}
        faltan = {vid: por_id[vid] for vid, r in existentes.items()
                  if r.get("estado") == "pendiente" and vid in por_id and not r.get("resumen")}
        try:
            repo.resumir_revisiones(dict(list(faltan.items())[:GUARDADAS]))
        except Exception as e:  # noqa: BLE001 — sin resumen el panel lo calcula al mostrarla
            registro.aviso("revision:resumen", e)
    for c in nuevas:  # las que ya tienen regla del operador se deciden solas
        regla = reglas.get(c["ubicacion"])
        if regla and not es_generica(c["ubicacion"]):
            resultado = regla.get("resultado") or {}
            try:
                if resultado.get("paises"):
                    decidir(repo, c["vacante_id"], "sirve", resultado["paises"], fecha=fecha, por="regla")
                else:
                    decidir(repo, c["vacante_id"], "otro_pais", fecha=fecha, por="regla")
            except Exception as e:  # noqa: BLE001 — una regla que no aplica no impide armar la cola
                registro.aviso("revision:281", e)
    por_sugerencia = 0
    pendientes_ids = {r["vacante_id"] for r in _revisiones_sin_texto(repo, "pendiente")}
    for vid, s_auto in automaticas.items():
        if vid not in pendientes_ids:
            continue
        try:
            if s_auto["decision"] == "sirve":
                decidir(repo, vid, "sirve", s_auto["paises"], fecha=fecha, por="sugerencia")
            else:
                decidir(repo, vid, "otro_pais", fecha=fecha, por="sugerencia")
            por_sugerencia += 1
        except Exception as e:  # noqa: BLE001 — si no se puede aplicar, queda en la bandeja para la persona
            registro.aviso("revision:sugerencia", e)
    actuales = _revisiones_sin_texto(repo, "pendiente")
    diagnostico = {}
    if completa and not leidas and hasattr(repo, "conteo_dudosas"):
        try:  # una carga vacía se explica con conteos (sin datos de clientes)
            diagnostico = repo.conteo_dudosas()
        except Exception:  # noqa: BLE001
            diagnostico = {}
    return {"por_confirmar": len(actuales), "resueltas_por_regla": por_regla, "agregadas": len(nuevas) - por_regla,
            "resueltas_por_sugerencia": por_sugerencia,
            "diagnostico": diagnostico,
            "leidas_del_catalogo": leidas, "fuera_por_idioma": fuera_idioma, "ya_claras": ya_claras,
            "por_confirmar_faltantes": sum(1 for r in actuales if any(p.get("faltan") for p in r.get("perfiles") or []))}


def _edad(datos, fecha):
    try:
        return (datetime.fromisoformat(fecha) - datetime.fromisoformat((datos.get("fecha_publicacion") or fecha)[:10])).days
    except ValueError:
        return 30


def listar(repo, fecha, pagina=None, por_pagina=25, cliente_id=None, todas=None, version=None):
    """Lo que ve el panel: pendientes ordenadas, con nombres de clientes (panel privado) y cuántas tienen la misma
    ubicación (para «aplicar a las iguales»).
    Contrato v29: con `pagina`, todas las pendientes por páginas, con el total real y el filtro por cliente. Se leen sin
    descripción (ligeras) y la descripción se pide solo para la página. Sin `pagina`, la cola de hoy (`tope`).
    18 nov (velocidad): el servidor puede pasar `todas` (pendientes ligeras y ordenadas) y `version` desde sus copias en
    memoria, para no leerlas en cada pantalla."""
    if todas is None:
        todas = sorted(repo.revisiones(estado="pendiente", ligera=True), key=lambda r: -(r.get("prioridad") or 0))
    tope = int((repo.ajuste("revision", {}) or {}).get("tope", TOPE))
    utiles = {r["vacante_id"] for r in todas[:tope]}
    filtradas = [r for r in todas if not cliente_id or any(p.get("cliente_id") == cliente_id
                                                           for p in r.get("perfiles") or [])]
    if pagina is None:
        pendientes = filtradas[:tope]
    else:
        pendientes = filtradas[(pagina - 1) * por_pagina:pagina * por_pagina]
    # Contrato v34: las filas con resumen (guardado de noche, SQL 018) se muestran tal cual; solo las que no lo tienen
    # leen el catálogo con su descripción y se calculan aquí, como antes.
    pendientes = [dict(r) for r in pendientes]  # la copia en memoria no se modifica
    sin_resumen = [r for r in pendientes if not r.get("resumen")]
    faltan = [r["vacante_id"] for r in sin_resumen if "description_full" not in (r.get("catalogo_vacantes") or {})]
    filas = repo.filas_catalogo(faltan) if faltan else {}
    for r in sin_resumen:
        if r["vacante_id"] in filas:
            r["catalogo_vacantes"] = {**(r.get("catalogo_vacantes") or {}), **filas[r["vacante_id"]]}
    version = (version if version is not None else repo.operativa(fecha)) or {}
    clientes = {c["id"]: c["nombre"] for c in (version.get("configuracion") or {}).get("clientes", [])}
    nombres_cargo = {c["id"]: c["nombre"] for c in (version.get("configuracion") or {}).get("cargos", [])}
    por_ubicacion = {}
    for r in todas:
        if not es_generica(r.get("ubicacion")):
            por_ubicacion[r["ubicacion"]] = por_ubicacion.get(r["ubicacion"], 0) + 1
    salida, calculados = [], {}
    originales = {r["vacante_id"]: r for r in todas}
    for r in pendientes:
        res = r.get("resumen")
        if not res:
            res = resumen_de(_datos(r.get("catalogo_vacantes")), r.get("motivo", ""))
            calculados[r["vacante_id"]] = res
            if r["vacante_id"] in originales:
                originales[r["vacante_id"]]["resumen"] = res  # la copia en memoria ya no lo vuelve a calcular
        frase = r.get("pista", "") if r.get("motivo") == FUNCIONES else res.get("frase", "")
        salida.append({**{k: res.get(k, "") for k in ("titulo", "empresa", "ubicacion", "modalidad", "salario",
                                                       "idioma", "publicada", "enlace", "sugerida", "por_que",
                                                       "nivel", "extracto")},
                       "cargos": sorted({nombres_cargo.get(p.get("cargo_id"), "") for p in r.get("perfiles") or []}
                                        - {""}),
                       "vacante_id": r["vacante_id"], "paises_sugeridos": res.get("paises_sugeridos") or [],
                       "paises": res.get("paises") or [], "frase": frase,
                       "pista": r.get("pista", ""), "sugerencia": r.get("sugerencia", []),
                       "motivo": r.get("motivo", ""), "funciones": r.get("motivo") == FUNCIONES,
                       "clientes": sorted({clientes.get(p["cliente_id"], "") for p in r.get("perfiles") or []} - {""}),
                       "cliente_ids": sorted({p["cliente_id"] for p in r.get("perfiles") or [] if p.get("cliente_id")}),
                       "ayuda_faltantes": any(p.get("faltan") for p in r.get("perfiles") or []),
                       "iguales": max(0, por_ubicacion.get(r.get("ubicacion"), 0) - 1),
                       "mas_util": r["vacante_id"] in utiles})
    if calculados and getattr(repo, "con_resumen", lambda: False)():
        _guardar_resumenes(repo, calculados)
    if pagina is None:
        return {"pendientes": salida, "total": len(salida), "en_espera": len(todas),
                "ayudan_faltantes": sum(1 for s in salida if s["ayuda_faltantes"])}
    por_cliente = {}
    for r in todas:
        for c in {p.get("cliente_id") for p in r.get("perfiles") or []} - {None, ""}:
            por_cliente[c] = por_cliente.get(c, 0) + 1
    return {"pendientes": salida, "total": len(filtradas), "en_espera": len(todas), "pagina": pagina,
            "por_cliente": por_cliente,
            "paginas": max(1, -(-len(filtradas) // por_pagina)), "por_pagina": por_pagina,
            "ayudan_faltantes": sum(1 for r in filtradas if any(p.get("faltan") for p in r.get("perfiles") or []))}


def _guardar_resumenes(repo, resumenes):
    """18 nov: el resumen calculado al mostrar una pendiente se guarda (SQL 018) en segundo plano, para que la próxima
    vez no haya que leer su descripción. Si falla, se vuelve a calcular la próxima vez."""
    import threading

    def guardar():
        try:
            repo.resumir_revisiones(resumenes)
        except Exception as e:  # noqa: BLE001
            registro.aviso("revision:resumen", e)
    threading.Thread(target=guardar, daemon=True).start()


def decidir(repo, vacante_id, decision, codigos=(), aplicar_a_iguales=False, fecha=None, por="operador", comprobar=None,
            regenerar=True):
    """Aplica una decisión de la bandeja. Devuelve qué pasó (asignaciones creadas, iguales resueltas, regla y las filas
    decididas). Con `regenerar=False` (el servidor del panel, 18 nov) no rehace los borradores aquí: los rehace en
    segundo plano para que la decisión responda al momento."""
    from panel.repositorio import ErrorRepositorio, hoy
    fecha = fecha or hoy()
    if decision not in DECISIONES:
        raise ErrorRepositorio("Decisión no reconocida.", 422)
    filas = repo.revisiones(vacante_id=vacante_id)
    if not filas or filas[0].get("estado") not in ("pendiente", "saltada"):
        raise ErrorRepositorio("Esta vacante ya se decidió. Recarga la bandeja.", 409)
    rev = filas[0]
    codigos = expandir(codigos)
    asignadas = 0
    funciones = rev.get("motivo") == FUNCIONES
    if decision == "sirve":
        # Contrato v23: varias etiquetas a la vez, de cualquier parte (LATAM y EE. UU., Mundo…). Contrato v25: las de
        # «Coincide por funciones» ya tienen la ubicación comprobada y no exigen país.
        validos = set(paises.mundo()["codigos"]) | set(paises.datos()["reconocidos"]) | {"MUNDO"}
        if (not codigos and not funciones) or set(codigos) - validos:
            raise ErrorRepositorio("Elige al menos un país o una región de la lista.", 422)
        asignadas = _asignar(repo, rev, codigos, fecha, por, comprobar)
        cambios = {"estado": "confirmada", "paises": codigos}
    elif decision == "saltar":
        cambios = {"estado": "saltada"}
    else:
        cambios = {"estado": "descartada", "paises": []}
    if decision != "saltar":  # contrato v17: quién decidió y qué; el aprendizaje solo usa decisiones de lugar del operador
        from panel.aprender import ETIQUETAS
        cambios["motivo"] = (ETIQUETAS[decision] if por == "operador" else
                             "decidida por sugerencia clara" if por == "sugerencia" else "decidida por regla")
    repo.actualizar_revision(vacante_id, {**cambios, "decidida_en": datetime.now(timezone.utc).isoformat()})
    if funciones:
        if decision == "sirve":
            aprender_titulo(repo, rev)  # contrato v25: desde mañana este título entra como similar
        # «No sirve» no archiva: la vacante puede servir a otro cargo.
    else:
        _al_catalogo(repo, rev, decision, codigos, por)
    iguales, regla, decididas = 0, False, [vacante_id]
    if aplicar_a_iguales and decision in ("sirve", "otro_pais") and not es_generica(rev.get("ubicacion")):
        repo.guardar_regla({"texto": rev["ubicacion"], "origen": "operador", "activa": True,
                            "resultado": {"paises": codigos} if decision == "sirve" else {"extranjero": True},
                            "ejemplos": [vacante_id]})
        regla = True
        # Lista ligera: cada una se vuelve a leer completa al decidirla; los borradores se rehacen una vez al final.
        for otra in repo.revisiones(estado="pendiente", ligera=True):
            if otra["vacante_id"] != vacante_id and otra.get("ubicacion") == rev["ubicacion"]:
                r = decidir(repo, otra["vacante_id"], decision, codigos, False, fecha, por, comprobar, regenerar=False)
                iguales += 1
                asignadas += r["asignadas"]
                decididas.append(otra["vacante_id"])
    if regenerar and decision == "sirve" and asignadas:
        try:  # los borradores pendientes y sin editar se rehacen con la vacante confirmada
            from panel import borradores
            borradores.generar(repo, fecha)
        except Exception as e:  # noqa: BLE001
            registro.aviso("revision:389", e)
    return {"decision": decision, "asignadas": asignadas, "iguales": iguales, "regla": regla, "decididas": decididas}


def _asignar(repo, rev, codigos, fecha, por, comprobar):
    """Asignaciones para los perfiles a los que ayuda la vacante confirmada: solo hasta 5 y sin repetir a nadie."""
    from panel.ejecutor import validar_version
    from panel.repositorio import ErrorRepositorio
    if not rev.get("perfiles"):
        return 0  # depuración completa: hoy no le sirve a nadie; la decisión queda para la base y el aprendizaje
    ejecucion = repo.ejecucion(fecha)
    version = repo.operativa(fecha)
    if not ejecucion or not version:
        raise ErrorRepositorio("Todavía no hay búsqueda de hoy. Inténtalo después de la búsqueda de la noche.", 409)
    cfg = validar_version(version)
    fila_catalogo = rev.get("catalogo_vacantes") or {}
    funciones = rev.get("motivo") == FUNCIONES
    datos = con_paises(_datos(fila_catalogo), codigos, por) if codigos else _datos(fila_catalogo)
    perfiles = {str(p.id): p for p in cfg.perfiles if p.activo}
    cargos = {str(c.id): c for c in cfg.cargos}
    ids = [p["perfil_id"] for p in rev.get("perfiles") or [] if p["perfil_id"] in perfiles]
    conteo = repo.conteo_asignaciones(ejecucion["id"], ids)
    recibidas = repo.recibidas(ids)
    nuevas = []
    for info in rev.get("perfiles") or []:
        p, cargo = perfiles.get(info["perfil_id"]), cargos.get(info.get("cargo_id"))
        if not p or not cargo or conteo.get(str(p.id), 0) >= MINIMO_POR_PERFIL:
            continue
        if rev["vacante_id"] in recibidas.get(str(p.id), set()):
            continue
        match = evaluar(datos, p, fecha)
        afinidad, evidencia = grado(datos.get("titulo", ""), cargo.model_dump(mode="json"))
        if funciones and not afinidad:
            afinidad, evidencia = "cercano", {"regla": "coincide por funciones, confirmada por el operador"}
        if not match["compatible"] or not afinidad:
            continue
        nuevas.append({"ejecucion_id": ejecucion["id"], "cliente_id": str(p.cliente_id), "perfil_id": str(p.id),
                       "cargo_id": str(cargo.id), "vacante_id": rev["vacante_id"],
                       "match_grade": entrega.GRADO_CONTRATO.get(afinidad, "similar"),
                       "explicacion": [*match["pruebas"], evidencia or {"regla": "similitud textual"},
                                       {"confirmada": {"paises": codigos, "por": por}} if codigos else
                                       {"funciones": True, "por": por}],
                       "filtros": p.model_dump(mode="json"), "cargo_configuracion": cargo.model_dump(mode="json")})
    if nuevas:
        repo.crear_asignaciones(nuevas)
        if comprobar and not _comprobada_hace_poco(fila_catalogo.get("datos") or {}):
            # comprobar el enlace ahora, para poder compartirla hoy; si ya se comprobó en las últimas 24 h (v31), no
            enlace = (fila_catalogo.get("datos") or {}).get("enlace", "")
            if enlace:
                resultado = comprobar(enlace, datos.get("titulo", ""))
                if resultado.get("estado") == "verificada":
                    nuevos = dict(fila_catalogo.get("datos") or {})
                    nuevos["verificacion"] = {"estado": "verificada", "motivo": resultado.get("motivo", ""),
                                              "enlaces": [resultado]}
                    repo.actualizar_catalogo_datos(rev["vacante_id"], nuevos)
    return len(nuevas)


def _comprobada_hace_poco(datos, horas=24):
    """Si el enlace ya tiene una comprobación positiva de menos de `horas` (contrato v31: 24 h para compartir)."""
    ver = datos.get("verificacion") or {}
    if ver.get("estado") != "verificada":
        return False
    fechas = [ver.get("comprobada_en") or ""] + [e.get("comprobada_en") or "" for e in ver.get("enlaces") or []
                                                 if isinstance(e, dict) and e.get("estado") == "verificada"]
    ahora = datetime.now(timezone.utc)
    for f in fechas:
        try:
            cuando = datetime.fromisoformat(f.replace("Z", "+00:00"))
        except ValueError:
            continue
        if cuando.tzinfo and 0 <= (ahora - cuando).total_seconds() < horas * 3600:
            return True
    return False


def aplicar_confirmacion(actual, explicacion):
    """Para `servicio.resultados`: una asignación confirmada se evalúa con los países decididos."""
    for e in explicacion or []:
        if isinstance(e, dict) and isinstance(e.get("confirmada"), dict):
            return con_paises(actual, e["confirmada"].get("paises") or [], e["confirmada"].get("por", "operador"))
    return actual



# ── Contrato v17: revisión masiva por CSV (sin IA) y lista de reglas ───────────────────────────────────────────────
# Se lee de izquierda a derecha: la respuesta sugerida, por qué, y los datos para comprobarla (ampliación v17).
COLUMNAS_CSV = ["decision", "pais", "por_que", "cargo", "empresa", "ubicacion", "modalidad", "frase_del_aviso", "enlace",
                "le_serviria_a", "aplicar_a_iguales", "comentario", "vacante_id"]
PREGUNTA = ("¿Puede postularse alguien que vive en LATAM o en España? Sí → «sí» y el país (o LATAM). Solo de otro país → "
            "«otro país». No se puede saber → «no sirve». La columna «decision» ya trae una sugerencia: corrige solo las "
            "que veas mal y lee las que vienen vacías.")
_DECISIONES_CSV = {"sirve": "sirve", "si": "sirve", "si sirve": "sirve", "otro pais": "otro_pais",
                   "otro_pais": "otro_pais", "solo otro pais": "otro_pais", "no sirve": "no_sirve", "no_sirve": "no_sirve",
                   "no": "no_sirve", "saltar": "saltar"}
_SI = {"si", "x", "true", "1", "yes"}


def exportar_csv(repo, fecha):
    """Todas las pendientes (no solo las 10 de la vista) con columnas para llenar."""
    import csv
    import io
    version = repo.operativa(fecha) or {}
    clientes = {c["id"]: c["nombre"] for c in (version.get("configuracion") or {}).get("clientes", [])}
    from panel.sugerir import ETIQUETA, sugerir
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(COLUMNAS_CSV)
    escritor.writerow(["", "", PREGUNTA] + [""] * (len(COLUMNAS_CSV) - 3))  # sin vacante_id: al subir se ignora
    filas = []
    for r in repo.revisiones(estado="pendiente"):
        if r.get("motivo") == FUNCIONES:  # contrato v25: el CSV es de ubicaciones; estas se deciden en el panel
            continue
        datos = _datos_ligeros(r.get("catalogo_vacantes"))
        s = sugerir(datos)
        nombres = sorted({clientes.get(p["cliente_id"], "") for p in r.get("perfiles") or []} - {""})
        filas.append(((s["grupo"], -r.get("prioridad", 0)), [
            ETIQUETA[s["decision"]], texto_paises(s["paises"]), s["motivo"], datos.get("titulo", ""),
            datos.get("empresa", ""), datos.get("ubicacion", ""), datos.get("modalidad", ""), s["frase"],
            datos.get("enlace", ""), ", ".join(nombres), "", "", r["vacante_id"]]))
    for _, fila in sorted(filas, key=lambda x: x[0]):
        escritor.writerow(fila)
    return "﻿" + salida.getvalue()  # BOM: Excel lo abre con tildes correctas


def texto_paises(codigos):
    """«LATAM», «LATAM y España» o los nombres: lo que se escribe en la columna «pais»."""
    d = paises.datos()
    codigos = list(codigos or [])
    if set(d["latam"]) <= set(codigos):
        return "LATAM y España" if "ES" in codigos else "LATAM"
    nombres = {p["codigo"]: p["nombre"] for p in d["cubiertos"]}
    return ", ".join(nombres.get(c, c) for c in codigos)


def leer_paises(texto):
    """Lo contrario de `texto_paises`: acepta nombres, siglas, «LATAM», «LATAM y España» o «todos». '?' si no se entiende."""
    d = paises.datos()
    nombres = {normalizar.texto(p["nombre"]): p["codigo"] for p in d["cubiertos"]}
    codigos = []
    for crudo in [x.strip() for x in re.split(r"[,/;]| y | e | o | u | and | or ", texto or "") if x.strip()]:
        t = normalizar.texto(crudo)
        if t in ("latam", "latinoamerica", "america latina", "latin america"):
            nuevos = list(d["latam"])
        elif t in ("sudamerica", "suramerica", "south america"):
            nuevos = grupos_paises()["SUDAMERICA"]
        elif t in ("centroamerica", "central america"):
            nuevos = grupos_paises()["CENTROAMERICA"]
        elif t in ("todos", "todas", "latam y espana"):
            nuevos = list(d["codigos"])
        elif len(crudo) == 2 and crudo.upper() in d["codigos"]:
            nuevos = [crudo.upper()]
        else:
            nuevos = [nombres.get(t, "?")]
        codigos += [c for c in nuevos if c not in codigos]
    return codigos


def importar_csv(repo, contenido, fecha=None, comprobar=None):
    """Aplica cada fila llenada como un clic en la bandeja. Devuelve aplicadas, omitidas y errores por fila."""
    import csv
    import io
    texto = (contenido or "").lstrip("﻿")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4000], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.DictReader(io.StringIO(texto), dialect=dialecto))[:GUARDADAS_COMPLETA + 1]
    resultado = {"aplicadas": 0, "omitidas": 0, "errores": []}
    for n, fila in enumerate(filas, start=2):
        if not (fila.get("vacante_id") or "").strip():
            continue  # la fila de instrucciones
        decision = _DECISIONES_CSV.get(normalizar.texto(fila.get("decision") or ""))
        if not decision:
            if (fila.get("decision") or "").strip():
                resultado["errores"].append({"fila": n, "motivo": "Decisión no reconocida: usa sirve, otro país, no sirve o saltar."})
            else:
                resultado["omitidas"] += 1
            continue
        codigos = leer_paises(fila.get("pais") or "")
        if decision == "sirve" and not codigos:
            codigos = (fila.get("pais_sugerido") or "").split()
        try:
            decidir(repo, (fila.get("vacante_id") or "").strip(), decision, codigos,
                    normalizar.texto(fila.get("aplicar_a_iguales") or "") in _SI, fecha, "operador", comprobar)
            resultado["aplicadas"] += 1
        except Exception as e:  # noqa: BLE001 — se informa la fila y se sigue con las demás
            resultado["errores"].append({"fila": n, "motivo": getattr(e, "mensaje", None) or str(e)[:200]})
    return resultado


def listar_reglas(repo):
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    salida = []
    for r in repo.reglas():
        res = r.get("resultado") or {}
        salida.append({"texto": r["texto"], "origen": r.get("origen", ""), "activa": r.get("activa", True),
                       "usos": int(r.get("usos") or 0), "conflictos": int(r.get("conflictos") or 0),
                       "resultado": ", ".join(nombres.get(c, c) for c in res.get("paises", [])) or "Solo otro país",
                       "ejemplos": (r.get("ejemplos") or [])[:3]})
    return {"reglas": sorted(salida, key=lambda x: (not x["activa"], x["origen"] != "aprendida", -x["usos"], x["texto"]))}


def _al_catalogo(repo, rev, decision, codigos, por):
    """Contrato v17: la base queda depurada al momento (la búsqueda siguiente lo mantiene con `decisiones_operador`)."""
    if decision == "saltar" or not hasattr(repo, "archivar_catalogo"):
        return
    try:
        if decision == "sirve":
            datos = dict((rev.get("catalogo_vacantes") or {}).get("datos") or {})
            if datos:
                repo.actualizar_catalogo_datos(rev["vacante_id"], con_paises(datos, codigos, por))
        else:
            repo.archivar_catalogo(rev["vacante_id"], "descartada por el operador")
    except Exception as e:  # noqa: BLE001 — la decisión ya quedó guardada; la búsqueda siguiente la aplica igual
        registro.aviso("revision:585", e)


def decisiones_para_busqueda(filas):
    """{vacante_id: decisión} para `bodega` (`confirmar_ubicacion.aplicar_operador`)."""
    from panel.aprender import ETIQUETAS
    salida = {}
    for f in filas or []:
        if f.get("estado") == "confirmada" and f.get("paises"):
            salida[f["vacante_id"]] = {"paises": list(f["paises"])}
        elif f.get("estado") == "descartada" and f.get("motivo") == ETIQUETAS["otro_pais"]:
            salida[f["vacante_id"]] = {"extranjero": True}
        elif f.get("estado") == "descartada" and f.get("motivo") == ETIQUETAS["no_sirve"]:
            salida[f["vacante_id"]] = {"descartada": True}
    return salida


_TRABAJO = {"estado": "inactivo", "avance": {"leidas": 0, "total": 0}, "resultado": None, "error": ""}
_CANDADO_TRABAJO = __import__("threading").Lock()


def estado_carga():
    """Lo que el panel consulta cada 2 s mientras corre «Cargar todas» (sin datos de clientes)."""
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in _TRABAJO.items()}


def iniciar_carga(repo, fecha):
    """Arranca «Cargar todas» en segundo plano (una a la vez) y responde al instante: una petición larga podía
    cortarse en el alojamiento y el botón se quedaba sin respuesta (13 nov)."""
    import threading
    with _CANDADO_TRABAJO:
        if _TRABAJO["estado"] == "en_curso":
            return estado_carga()
        _TRABAJO.update(estado="en_curso", avance={"leidas": 0, "total": 0}, resultado=None, error="")

    def avance(leidas, total):
        _TRABAJO["avance"] = {"leidas": leidas, "total": total}

    def correr():
        from panel.repositorio import ErrorRepositorio
        try:
            resultado = cargar_todas(repo, fecha, avance)
            _TRABAJO.update(estado="listo", resultado=resultado)
        except ErrorRepositorio as e:
            _TRABAJO.update(estado="error", error=getattr(e, "mensaje", "") or "No se pudo cargar la bandeja.")
        except Exception:  # noqa: BLE001 — nunca se muestran datos internos; el panel ofrece reintentar
            _TRABAJO.update(estado="error", error="No se pudo cargar la bandeja. Inténtalo de nuevo en unos minutos.")
    threading.Thread(target=correr, name="cargar-dudosas", daemon=True).start()
    return estado_carga()


def cargar_todas(repo, fecha, avance=None):
    """Botón «Cargar todas las dudosas de la base»: llena la bandeja al momento, sin esperar la búsqueda."""
    from panel.ejecutor import validar_version
    from panel.repositorio import ErrorRepositorio
    version = repo.operativa(fecha)
    if not version:
        raise ErrorRepositorio("Primero programa una configuración en «Cargos y cupos».", 409)
    cfg = validar_version(version)
    ejecucion = repo.ejecucion(fecha)
    conteo = repo.conteo_asignaciones(ejecucion["id"], [str(p.id) for p in cfg.perfiles]) if ejecucion else {}
    estrictas = {p.id: conteo.get(str(p.id), 0) for p in cfg.perfiles}
    return preparar_cola(repo, cfg, fecha, estrictas, completa=True, avance=avance)


# ── Descarga de la base para el cliente (13 nov): `ofertas` sin las vacantes con país sin confirmar ──────────────────
EXCLUIDAS_BASE = {"descartada por el operador"}


def sin_confirmar(fila):
    """True si la vacante de esta fila de `ofertas` tiene el país sin confirmar o el operador la descartó."""
    cat = fila.get("catalogo_vacantes") or {}
    razon = cat.get("reason") or ""
    return cat.get("confianza") == "baja" or razon.startswith(POR_CONFIRMAR) or razon in EXCLUIDAS_BASE


def _celda(columna, valor):
    """Un valor con el formato CSV del contrato v1: listas separadas por «|», idiomas como «en:B2:1», fecha y hora
    `AAAA-MM-DDThh:mm:ssZ`. Los textos (descripción incluida) van tal cual: el CSV pone comillas a sus saltos de línea."""
    from buscador import contrato
    if valor is None or valor == "":
        return ""
    if columna == "language_requirements" and isinstance(valor, list):
        partes = []
        for x in valor:
            if isinstance(x, dict):
                partes.append(f'{x.get("language") or ""}:{x.get("level") or ""}:{0 if x.get("required") is False else 1}')
            else:
                partes.append(str(x))
        return "|".join(partes)
    if isinstance(valor, list):
        return "|".join(str(x) for x in valor if x not in (None, ""))
    if columna == "scraped_at":
        from datetime import datetime, timezone
        try:
            instante = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
            return instante.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return str(valor)
    if columna in ("published_date", "delivery_date"):
        return str(valor)[:10]
    if columna in contrato.NUMEROS and isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _clave_oferta(fila):
    return fila.get("vacante_id") or fila.get("external_id") or fila.get("id")


def exportar_base(repo, fecha=None, cliente_id=None, todo=False):
    """CSV de `ofertas` con las columnas y el formato del contrato (v1 y sus extras, `buscador/contrato.py`), sin las
    vacantes con país sin confirmar ni las descartadas (reunión del 14 nov: general o por cliente, de un día o de toda la
    base). Una fila por vacante; la misma vacante asignada a dos clientes sale en el archivo de cada uno.
    - General de un día: las filas entregadas ese día más las vacantes asignadas ese día por el panel.
    - Por cliente: las vacantes que el panel le asignó (ese día, o siempre con `todo`), unidas a `ofertas`.
    Devuelve (texto, incluidas, omitidas_sin_confirmar, sin_fila): `sin_fila` cuenta las asignadas que no están en
    `ofertas` (por ejemplo un post sin ficha formal); nunca se inventa su fila."""
    import csv
    import io
    from buscador import contrato
    sin_fila = 0
    if cliente_id:
        ids = set(repo.vacantes_asignadas(fecha=None if todo else fecha, cliente_id=cliente_id))
        filas = repo.ofertas_de(vacante_ids=sorted(ids))
        sin_fila = len(ids - {f.get("vacante_id") for f in filas})
    elif todo or not fecha:
        filas = repo.base_ofertas()
    else:
        filas = repo.ofertas_de(fecha=fecha)
        vistas = {f.get("vacante_id") for f in filas}
        extra = set(repo.vacantes_asignadas(fecha=fecha)) - vistas
        if extra:
            filas += repo.ofertas_de(vacante_ids=sorted(extra))
    unicas = {}
    for f in filas:
        unicas.setdefault(_clave_oferta(f), f)
    filas = list(unicas.values())
    incluidas = [f for f in filas if not sin_confirmar(f)]
    columnas = contrato.COLUMNAS + contrato.EXTRAS
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(columnas)
    for f in incluidas:
        escritor.writerow([_celda(c, f.get(c)) for c in columnas])
    return "\ufeff" + salida.getvalue(), len(incluidas), len(filas) - len(incluidas), sin_fila


TOPE_APRENDIDOS = 200


def aprender_titulo(repo, rev):
    """Contrato v25: el título aprobado desde «Coincide por funciones» se guarda para sus cargos en
    `panel_ajustes.titulos_aprendidos` (sin repetir, hasta 200 por cargo)."""
    titulo = " ".join(str((_datos(rev.get("catalogo_vacantes")) or {}).get("titulo") or "").split())
    if not titulo or not hasattr(repo, "guardar_ajuste"):
        return False
    try:
        aprendidos = dict(repo.ajuste("titulos_aprendidos", {}) or {})
        for cargo_id in {p.get("cargo_id") for p in rev.get("perfiles") or [] if p.get("cargo_id")}:
            lista = list(aprendidos.get(cargo_id) or [])
            if titulo.casefold() not in {t.casefold() for t in lista}:
                aprendidos[cargo_id] = (lista + [titulo])[-TOPE_APRENDIDOS:]
        repo.guardar_ajuste("titulos_aprendidos", aprendidos)
        return True
    except Exception:  # noqa: BLE001 — la asignación ya quedó hecha; aprender es una ayuda
        return False
