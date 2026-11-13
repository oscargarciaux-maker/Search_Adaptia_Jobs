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
from panel.afinidad import MINIMO_POR_PERFIL, evaluar
from panel.terminos import grado

TOPE = 10  # las que se muestran a la vez en el panel
GUARDADAS = 300  # las que se guardan (para el CSV de revisión grande, contrato v17)
DIAS_PENDIENTE = 7
MOTIVO = "ubicación por confirmar"
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
    """La vacante con los países confirmados (nota visible en el panel)."""
    return dict(datos, paises=list(codigos), confianza_pais="alta", nota_pais=f"confirmada por {por}")


def _datos(fila_catalogo):
    datos = dict((fila_catalogo or {}).get("datos") or {})
    return vacante.reetiquetar(dict(datos, _descripcion=(fila_catalogo or {}).get("description_full") or ""),
                               publicada=True)


def preparar_cola(repo, cfg, fecha, estrictas, filas_hoy=()):
    """Arma la cola del día al final de la búsqueda (panel/ejecutor.registrar). Devuelve solo conteos."""
    perfiles = [(c, p) for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))]
    if not perfiles:
        return {"por_confirmar": 0}
    desde = (datetime.fromisoformat(fecha) - timedelta(days=2)).date().isoformat()
    recibidas = repo.recibidas([str(p.id) for _, p in perfiles])
    for f in filas_hoy:
        recibidas.setdefault(f["perfil_id"], set()).add(f["vacante_id"])
    candidatos = []
    for fila in repo.candidatas_por_confirmar(desde):
        datos = _datos(fila)
        if datos.get("idioma") not in ("es", "en") or not datos.get("titulo"):
            continue
        if datos.get("confianza_pais") != "baja" and datos.get("nota_pais") != "por zona horaria":
            continue
        sirve = []
        for cargo, p in perfiles:
            if fila["id"] in recibidas.get(str(p.id), set()) or not grado(datos["titulo"], cargo.model_dump(mode="json"))[0]:
                continue
            if set(evaluar(datos, p, fecha)["motivos"]) - MOTIVOS_PAIS:
                continue
            sirve.append({"perfil_id": str(p.id), "cliente_id": str(p.cliente_id), "cargo_id": str(cargo.id),
                          "faltan": estrictas.get(p.id, 0) < MINIMO_POR_PERFIL})
        if sirve:
            texto = pista(datos.get("_descripcion", ""), datos.get("ubicacion", ""))
            candidatos.append({"vacante_id": fila["id"], "motivo": MOTIVO, "pista": texto,
                               "ubicacion": clave_ubicacion(datos.get("ubicacion", "")), "sugerencia": sugerencia(texto),
                               "perfiles": sirve, "prioridad": sum(100 if s["faltan"] else 10 for s in sirve)
                               + max(0, 30 - _edad(datos, fecha))})
    existentes = {r["vacante_id"]: r for r in repo.revisiones()}
    reglas = {r["texto"]: r for r in repo.reglas() if r.get("activa", True)}
    ids = {c["vacante_id"] for c in candidatos}
    # Las que ya tienen una regla del operador se registran y se deciden al instante (no ocupan lugar en la bandeja).
    nuevas = [dict(c, estado="pendiente") for c in candidatos if c["vacante_id"] not in existentes
              and c["ubicacion"] in reglas and not es_generica(c["ubicacion"])]
    por_regla = len(nuevas)
    ahora = datetime.now(timezone.utc)
    for vid, r in existentes.items():  # pendientes viejas o que ya no le sirven a nadie: vencidas
        creada = (r.get("creada_en") or ahora.isoformat()).replace("Z", "+00:00")
        if r.get("estado") == "pendiente" and (vid not in ids or ahora - datetime.fromisoformat(creada) > timedelta(days=DIAS_PENDIENTE)):
            repo.actualizar_revision(vid, {"estado": "vencida"})
    pendientes = sum(1 for vid, r in existentes.items() if r.get("estado") == "pendiente" and vid in ids)
    for c in sorted(candidatos, key=lambda x: -x["prioridad"]):
        if pendientes >= GUARDADAS:
            break
        if c["vacante_id"] in existentes or any(n["vacante_id"] == c["vacante_id"] for n in nuevas):
            continue
        nuevas.append(dict(c, estado="pendiente"))
        pendientes += 1
    if nuevas:
        repo.guardar_revisiones(nuevas)
    for c in nuevas:  # las que ya tienen regla del operador se deciden solas
        regla = reglas.get(c["ubicacion"])
        if regla and not es_generica(c["ubicacion"]):
            resultado = regla.get("resultado") or {}
            try:
                if resultado.get("paises"):
                    decidir(repo, c["vacante_id"], "sirve", resultado["paises"], fecha=fecha, por="regla")
                else:
                    decidir(repo, c["vacante_id"], "otro_pais", fecha=fecha, por="regla")
            except Exception:  # noqa: BLE001 — una regla que no aplica no impide armar la cola
                pass
    actuales = repo.revisiones(estado="pendiente")
    return {"por_confirmar": len(actuales), "resueltas_por_regla": por_regla,
            "por_confirmar_faltantes": sum(1 for r in actuales if any(p.get("faltan") for p in r.get("perfiles") or []))}


def _edad(datos, fecha):
    try:
        return (datetime.fromisoformat(fecha) - datetime.fromisoformat((datos.get("fecha_publicacion") or fecha)[:10])).days
    except ValueError:
        return 30


def listar(repo, fecha):
    """Lo que ve el panel: pendientes ordenadas, con nombres de clientes (panel privado) y cuántas tienen la misma
    ubicación (para «aplicar a las iguales»)."""
    todas = sorted(repo.revisiones(estado="pendiente"), key=lambda r: -r.get("prioridad", 0))
    tope = int((repo.ajuste("revision", {}) or {}).get("tope", TOPE))
    pendientes = todas[:tope]
    version = repo.operativa(fecha) or {}
    clientes = {c["id"]: c["nombre"] for c in (version.get("configuracion") or {}).get("clientes", [])}
    por_ubicacion = {}
    for r in todas:
        if not es_generica(r.get("ubicacion")):
            por_ubicacion[r["ubicacion"]] = por_ubicacion.get(r["ubicacion"], 0) + 1
    salida = []
    for r in pendientes:
        datos = _datos(r.get("catalogo_vacantes"))
        salida.append({"vacante_id": r["vacante_id"], "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
                       "ubicacion": datos.get("ubicacion", ""), "modalidad": datos.get("modalidad", ""),
                       "idioma": datos.get("idioma", ""), "publicada": datos.get("fecha_publicacion", ""),
                       "enlace": datos.get("enlace", ""), "pista": r.get("pista", ""), "sugerencia": r.get("sugerencia", []),
                       "clientes": sorted({clientes.get(p["cliente_id"], "") for p in r.get("perfiles") or []} - {""}),
                       "ayuda_faltantes": any(p.get("faltan") for p in r.get("perfiles") or []),
                       "iguales": max(0, por_ubicacion.get(r.get("ubicacion"), 0) - 1)})
    return {"pendientes": salida, "total": len(salida), "en_espera": len(todas),
            "ayudan_faltantes": sum(1 for s in salida if s["ayuda_faltantes"])}


def decidir(repo, vacante_id, decision, codigos=(), aplicar_a_iguales=False, fecha=None, por="operador", comprobar=None):
    """Aplica una decisión de la bandeja. Devuelve qué pasó (asignaciones creadas, iguales resueltas, regla)."""
    from panel.repositorio import ErrorRepositorio, hoy
    fecha = fecha or hoy()
    if decision not in DECISIONES:
        raise ErrorRepositorio("Decisión no reconocida.", 422)
    filas = repo.revisiones(vacante_id=vacante_id)
    if not filas or filas[0].get("estado") not in ("pendiente", "saltada"):
        raise ErrorRepositorio("Esta vacante ya se decidió. Recarga la bandeja.", 409)
    rev = filas[0]
    codigos = [c for c in dict.fromkeys(codigos or [])]
    asignadas = 0
    if decision == "sirve":
        cubiertos = set(paises.datos()["codigos"])
        if not codigos or set(codigos) - cubiertos:
            raise ErrorRepositorio("Elige al menos un país de LATAM o España.", 422)
        asignadas = _asignar(repo, rev, codigos, fecha, por, comprobar)
        cambios = {"estado": "confirmada", "paises": codigos}
    elif decision == "saltar":
        cambios = {"estado": "saltada"}
    else:
        cambios = {"estado": "descartada", "paises": []}
    if decision != "saltar":  # contrato v17: quién decidió y qué; el aprendizaje solo usa decisiones de lugar del operador
        from panel.aprender import ETIQUETAS
        cambios["motivo"] = ETIQUETAS[decision] if por == "operador" else "decidida por regla"
    repo.actualizar_revision(vacante_id, {**cambios, "decidida_en": datetime.now(timezone.utc).isoformat()})
    iguales, regla = 0, False
    if aplicar_a_iguales and decision in ("sirve", "otro_pais") and not es_generica(rev.get("ubicacion")):
        repo.guardar_regla({"texto": rev["ubicacion"], "origen": "operador", "activa": True,
                            "resultado": {"paises": codigos} if decision == "sirve" else {"extranjero": True},
                            "ejemplos": [vacante_id]})
        regla = True
        for otra in repo.revisiones(estado="pendiente"):
            if otra["vacante_id"] != vacante_id and otra.get("ubicacion") == rev["ubicacion"]:
                r = decidir(repo, otra["vacante_id"], decision, codigos, False, fecha, por, comprobar)
                iguales += 1
                asignadas += r["asignadas"]
    if decision == "sirve" and asignadas:
        try:  # los borradores pendientes y sin editar se rehacen con la vacante confirmada
            from panel import borradores
            borradores.generar(repo, fecha)
        except Exception:  # noqa: BLE001
            pass
    return {"decision": decision, "asignadas": asignadas, "iguales": iguales, "regla": regla}


def _asignar(repo, rev, codigos, fecha, por, comprobar):
    """Asignaciones para los perfiles a los que ayuda la vacante confirmada: solo hasta 5 y sin repetir a nadie."""
    from panel.ejecutor import validar_version
    from panel.repositorio import ErrorRepositorio
    ejecucion = repo.ejecucion(fecha)
    version = repo.operativa(fecha)
    if not ejecucion or not version:
        raise ErrorRepositorio("Todavía no hay búsqueda de hoy. Inténtalo después de la búsqueda de la noche.", 409)
    cfg = validar_version(version)
    fila_catalogo = rev.get("catalogo_vacantes") or {}
    datos = con_paises(_datos(fila_catalogo), codigos, por)
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
        if not match["compatible"] or not afinidad:
            continue
        nuevas.append({"ejecucion_id": ejecucion["id"], "cliente_id": str(p.cliente_id), "perfil_id": str(p.id),
                       "cargo_id": str(cargo.id), "vacante_id": rev["vacante_id"],
                       "match_grade": entrega.GRADO_CONTRATO.get(afinidad, "similar"),
                       "explicacion": [*match["pruebas"], evidencia or {"regla": "similitud textual"},
                                       {"confirmada": {"paises": codigos, "por": por}}],
                       "filtros": p.model_dump(mode="json"), "cargo_configuracion": cargo.model_dump(mode="json")})
    if nuevas:
        repo.crear_asignaciones(nuevas)
        if comprobar:  # comprobar el enlace ahora, para poder compartirla hoy (vigencia 6 h)
            enlace = (fila_catalogo.get("datos") or {}).get("enlace", "")
            if enlace:
                resultado = comprobar(enlace, datos.get("titulo", ""))
                if resultado.get("estado") == "verificada":
                    nuevos = dict(fila_catalogo.get("datos") or {})
                    nuevos["verificacion"] = {"estado": "verificada", "motivo": resultado.get("motivo", ""),
                                              "enlaces": [resultado]}
                    repo.actualizar_catalogo_datos(rev["vacante_id"], nuevos)
    return len(nuevas)


def aplicar_confirmacion(actual, explicacion):
    """Para `servicio.resultados`: una asignación confirmada se evalúa con los países decididos."""
    for e in explicacion or []:
        if isinstance(e, dict) and isinstance(e.get("confirmada"), dict):
            return con_paises(actual, e["confirmada"].get("paises") or [], e["confirmada"].get("por", "operador"))
    return actual



# ── Contrato v17: revisión masiva por CSV (sin IA) y lista de reglas ───────────────────────────────────────────────
COLUMNAS_CSV = ["vacante_id", "cargo", "empresa", "ubicacion", "pista", "le_serviria_a", "pais_sugerido", "decision",
                "pais", "aplicar_a_iguales", "comentario"]
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
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(COLUMNAS_CSV)
    for r in sorted(repo.revisiones(estado="pendiente"), key=lambda x: -x.get("prioridad", 0)):
        datos = _datos(r.get("catalogo_vacantes"))
        nombres = sorted({clientes.get(p["cliente_id"], "") for p in r.get("perfiles") or []} - {""})
        escritor.writerow([r["vacante_id"], datos.get("titulo", ""), datos.get("empresa", ""), datos.get("ubicacion", ""),
                           r.get("pista", ""), ", ".join(nombres), " ".join(r.get("sugerencia") or []), "", "", "", ""])
    return "﻿" + salida.getvalue()  # BOM: Excel lo abre con tildes correctas


def importar_csv(repo, contenido, fecha=None, comprobar=None):
    """Aplica cada fila llenada como un clic en la bandeja. Devuelve aplicadas, omitidas y errores por fila."""
    import csv
    import io
    texto = (contenido or "").lstrip("﻿")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4000], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.DictReader(io.StringIO(texto), dialect=dialecto))[:500]
    nombres = {normalizar.texto(p["nombre"]): p["codigo"] for p in paises.datos()["cubiertos"]}
    resultado = {"aplicadas": 0, "omitidas": 0, "errores": []}
    for n, fila in enumerate(filas, start=2):
        decision = _DECISIONES_CSV.get(normalizar.texto(fila.get("decision") or ""))
        if not decision:
            if (fila.get("decision") or "").strip():
                resultado["errores"].append({"fila": n, "motivo": "Decisión no reconocida: usa sirve, otro país, no sirve o saltar."})
            else:
                resultado["omitidas"] += 1
            continue
        crudos = [x.strip() for x in re.split(r"[,/;]| y ", fila.get("pais") or "") if x.strip()]
        codigos = [x.upper() if len(x) == 2 else nombres.get(normalizar.texto(x), "?") for x in crudos]
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
