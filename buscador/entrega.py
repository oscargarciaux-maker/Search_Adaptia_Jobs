"""Entrega diaria: `por_rol` vacantes nuevas por rol, lo más variadas posible, en el formato del contrato de datos v1.

Corre al final de la bodega. Elige de la bodega las vacantes que nunca se han entregado (trabajo/entregadas.json guarda
su huella y sus enlaces), las reparte por rol (datos/entrega.yaml) y, dentro de cada rol, va tomando la que menos se
parece a las ya elegidas: idioma, nivel, país, modalidad, fuente y empresa. Sube las filas a Supabase (supabase.py).
"""
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

from buscador import contrato, familias, normalizar, vacante

RAIZ = Path(__file__).resolve().parent.parent
GRADOS = familias.GRADOS            # exacto, similar, cercano
GRADO_CONTRATO = {"exacto": "exact", "similar": "similar", "cercano": "close"}


_config_operativa = None


def config():
    if _config_operativa is not None:
        return _config_operativa
    return yaml.safe_load((RAIZ / "datos" / "entrega.yaml").read_text(encoding="utf-8"))


def meta_de(rol, cfg):
    return rol.get("cupo", cfg["por_rol"])


def huellas(v):
    """Claves con las que se reconoce una vacante ya entregada: su identidad estable y todos sus enlaces limpios."""
    return [v["id"], *v.get("_ids_fusionados", [])] + [contrato.url_limpia(u) for u in
                        [v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])] if u]


def rol_de(v, roles):
    """(rol, grado) de la vacante: el rol con la coincidencia más fuerte; si empatan, el primero de la lista."""
    empatados, grado = roles_de(v, roles)
    return (empatados[0], grado) if empatados else (None, None)


def roles_de(v, roles):
    """([roles empatados en la mejor coincidencia, en el orden de la lista], grado)."""
    grados = {f["familia"]: f["coincidencia"] for f in v.get("familias", [])}
    titulo = normalizar.texto(v.get("titulo", ""))
    mejor = None
    for orden, rol in enumerate(roles):
        en_rol = [grados[f] for f in rol["familias"] if f in grados]
        if "_perfiles" in rol:
            en_rol = [g for g in en_rol if g != "cercano"]  # oficios vecinos: solo para ampliar (contrato v9)
        if not en_rol:
            continue
        if rol.get("titulo") and not any(normalizar.contiene_frase(titulo, normalizar.texto(p)) for p in rol["titulo"]):
            continue
        if "_perfiles" in rol:
            from panel.afinidad import evaluar
            if not any(evaluar(v, p, rol["_hoy"])["compatible"] for p in rol["_perfiles"]):
                continue
        grado = min(en_rol, key=GRADOS.index)
        if mejor is None or GRADOS.index(grado) < GRADOS.index(mejor[1]):
            mejor = ([rol], grado)
        elif grado == mejor[1]:
            mejor[0].append(rol)
    return mejor if mejor else ([], None)


def _rasgos(v):
    # Calcular diversidad no certifica ni exporta un enlace.
    fila = contrato.filas(v, solo_comprobados=False)[0] if v.get("enlace") or v.get("enlace_directo") else {}
    return {
        "idioma": v.get("idioma", ""),
        "nivel": fila.get("seniority") or "sin nivel",
        "pais": fila.get("office_country") or "|".join(sorted(v.get("paises", []))) or "sin dato",
        "modo": fila.get("work_mode") or "sin dato",
        "fuente": v.get("fuente", ""),
        "empresa": normalizar.empresa(v.get("empresa", "")),
        "con_texto": len(v.get("_descripcion", "")) >= 200,
    }


def prioridad_remota(v):
    if v.get("confianza_pais") == "baja":
        return 3
    if v.get("modalidad") == "remoto":
        return 0 if v.get("confianza_pais") == "alta" and len(v.get("paises", [])) > 1 else 1
    return 2


def variadas(candidatas, cuantas, max_por_empresa, hoy, preferir_remotas=False, iniciales=(), perfiles=()):
    """Toma `cuantas` candidatas [(vacante, grado)] una por una: en cada paso la de menor costo, donde el costo sube con
    lo que ya se repite (idioma, nivel, país, modalidad, fuente), con un grado más débil, sin descripción o más vieja."""
    elegidas, conteo = list(iniciales), {k: Counter() for k in ("idioma", "nivel", "pais", "modo", "fuente", "empresa")}
    for v, _ in iniciales:
        rasgos = _rasgos(v)
        for k in conteo:
            conteo[k][rasgos[k]] += 1
    def destinatarios(v):
        if not perfiles: return set()
        from panel.afinidad import evaluar
        return {p["cliente_id"] for p in perfiles if evaluar(v,p,hoy)["compatible"]}
    atendidos = Counter(k for v,_ in iniciales for k in destinatarios(v))
    resto = [(v, g, dict(_rasgos(v),_destinatarios=destinatarios(v))) for v, g in candidatas]
    hoy_d = date.fromisoformat(hoy)
    while resto and len(elegidas) < cuantas:
        def costo(item):
            v, g, r = item
            dias = (hoy_d - date.fromisoformat((v.get("fecha_publicacion") or v.get("visto_primera_vez") or hoy)[:10])).days
            return (3.0 * conteo["idioma"][r["idioma"]] + 2.0 * conteo["nivel"][r["nivel"]] +
                    1.5 * conteo["pais"][r["pais"]] + 1.0 * conteo["modo"][r["modo"]] +
                    1.0 * conteo["fuente"][r["fuente"]] + 4.0 * GRADOS.index(g) +
                    (0 if r["con_texto"] else 4.0) + 0.3 * max(0, dias))
        resto = [x for x in resto if conteo["empresa"][x[2]["empresa"]] < max_por_empresa]
        if not resto:
            break
        mejor = min(resto, key=lambda item: (GRADOS.index(item[1]),
                    prioridad_remota(item[0]) if preferir_remotas else 0,
                    min((atendidos[k] for k in item[2]["_destinatarios"]),default=0),costo(item)))
        resto.remove(mejor)
        v, g, r = mejor
        elegidas.append((v, g))
        atendidos.update(r["_destinatarios"])
        for k in conteo:
            conteo[k][r[k]] += 1
    return elegidas


def _repartir_por_turnos(compartidas, por_rol, roles, cfg, iniciales):
    """Cargos que aceptan la misma vacante con igual coincidencia (p. ej. «Product Designer» y «Diseñador UX/UI»): en vez
    de llevárselas todas el primero de la lista, cada una va al cargo con mayor fracción de cupo pendiente."""
    orden = {r["id"]: i for i, r in enumerate(roles)}
    meta = {r["id"]: meta_de(r, cfg) for r in roles}
    tienen = {r["id"]: len(por_rol[r["id"]]) + len(iniciales.get(r["id"], [])) for r in roles}
    compartidas.sort(key=lambda x: x[0].get("fecha_publicacion") or "", reverse=True)  # recientes primero
    compartidas.sort(key=lambda x: GRADOS.index(x[1]))  # estable: mejor coincidencia primero
    for v, grado, ids in compartidas:
        def clave(rid):
            m = meta[rid] or 0
            pendiente = max(0, m - tienen[rid]) / m if m else -1
            return (-pendiente, tienen[rid] / m if m else float("inf"), orden[rid])
        elegido = min(ids, key=clave)
        por_rol[elegido].append((v, grado))
        tienen[elegido] += 1


def _motivo_general(v, entregadas, desde, cfg, omitir_verificacion=False):
    """Reglas que nunca se amplían: no entregada antes, frescura, enlace comprobado y contrato (idioma, país, texto)."""
    if any(h in entregadas for h in huellas(v)):
        return "ya entregada"
    if (v.get("visto_primera_vez") or "") < desde:
        return "fuera de frescura"
    revision = v.get("verificacion")
    if not omitir_verificacion and revision is not None and revision.get("estado") != "verificada":
        return "enlaces sin comprobar o rechazados"
    return contrato.entregable(v, tuple(cfg.get("idiomas", ["es", "en"])))


def ampliar(rol, elegidas, libres, cuantas, max_por_empresa, hoy):
    """Contrato v9: si un perfil del cargo tiene menos del mínimo diario de vacantes que cumplen sus filtros, se completa
    por niveles (sin dato → cargo cercano → remota abierta a su país) con vacantes que nadie tomó, dentro del cupo.
    Cada añadida lleva `_ampliacion` con su nivel; `libres` pierde las que se usan."""
    perfiles = rol.get("_perfiles") or []
    if not perfiles or len(elegidas) >= cuantas:
        return elegidas
    from panel.afinidad import AMPLIACIONES, MINIMO_POR_PERFIL, TOPE_EMPRESA_AMPLIADO, evaluar, evaluar_ampliada
    elegidas = list(elegidas)
    empresas = Counter(normalizar.empresa(v["empresa"]) for v, _ in elegidas)
    def estrictas(p):
        return sum(1 for v, _ in elegidas if evaluar(v, p, hoy)["compatible"] or
                   (v.get("_ampliacion") and evaluar_ampliada(v, p, hoy, v["_ampliacion"])["compatible"]))
    def grado_en_rol(v):
        grados = {f["familia"]: f["coincidencia"] for f in v.get("familias", [])}
        return min((grados[f] for f in rol["familias"] if f in grados), key=GRADOS.index, default=None)
    for nivel in AMPLIACIONES:
        permitidos = ("exacto", "similar", "cercano") if nivel != "sin_dato" else ("exacto", "similar")
        tope = TOPE_EMPRESA_AMPLIADO if nivel == "empresa_4" else max_por_empresa
        for p in perfiles:
            falta = MINIMO_POR_PERFIL - estrictas(p)
            while falta > 0 and len(elegidas) < cuantas:
                opciones = [(GRADOS.index(g), -(int((v.get("fecha_publicacion") or "0000-00-00").replace("-", "") or 0)), i, v, g)
                            for i, v in enumerate(libres) if (g := grado_en_rol(v)) in permitidos
                            and empresas[normalizar.empresa(v["empresa"])] < tope
                            and evaluar_ampliada(v, p, hoy, nivel)["compatible"]]
                if not opciones:
                    break
                *_, i, v, g = min(opciones, key=lambda x: x[:3])
                libres.pop(i)
                elegidas.append((dict(v, _ampliacion=nivel), g))
                empresas[normalizar.empresa(v["empresa"])] += 1
                falta -= 1
    return elegidas


def completar_cupo_por_empresa(elegidas, candidatas, cuantas):
    """Contrato v11 (último recurso): si el cargo no llega a su cupo solo porque sus candidatas son de pocas empresas,
    admite hasta 4 por empresa (en vez de 2) con vacantes que ya cumplen los filtros de algún perfil."""
    from panel.afinidad import TOPE_EMPRESA_AMPLIADO
    if len(elegidas) >= cuantas:
        return elegidas
    elegidas = list(elegidas)
    tomadas = {v["id"] for v, _ in elegidas}
    empresas = Counter(normalizar.empresa(v["empresa"]) for v, _ in elegidas)
    resto = [x for x in candidatas if x[0]["id"] not in tomadas]
    resto.sort(key=lambda x: x[0].get("fecha_publicacion") or "", reverse=True)
    resto.sort(key=lambda x: GRADOS.index(x[1]))
    for v, g in resto:
        if len(elegidas) >= cuantas:
            break
        empresa = normalizar.empresa(v["empresa"])
        if empresas[empresa] < TOPE_EMPRESA_AMPLIADO:
            elegidas.append((dict(v, _ampliacion="empresa_4"), g))
            empresas[empresa] += 1
    return elegidas


def deficit_por_perfil(elegidas, roles, hoy):
    """{perfil_id: cuántas le faltan para el mínimo diario} con lo elegido (estricto o ampliado). Uso interno: nunca
    se escribe en reportes públicos; ahí solo van conteos por cargo."""
    from panel.afinidad import MINIMO_POR_PERFIL, evaluar, evaluar_ampliada
    salida = {}
    for rol in roles:
        lista = elegidas.get(rol["id"], [])
        for p in rol.get("_perfiles") or []:
            n = sum(1 for v, _ in lista if evaluar(v, p, hoy)["compatible"] or
                    (v.get("_ampliacion") and evaluar_ampliada(v, p, hoy, v["_ampliacion"])["compatible"]))
            if n < MINIMO_POR_PERFIL:
                salida[p["id"]] = MINIMO_POR_PERFIL - n
    return salida


def elegir(vacantes, entregadas, hoy, cfg=None, iniciales=None, omitir_verificacion=False):
    """{rol_id: [(vacante, grado)]} con las vacantes nuevas de cada rol, y un resumen por rol."""
    cfg = cfg or config()
    roles = cfg["roles"]
    iniciales = iniciales or {}
    incluidas = {h for lista in iniciales.values() for v, _ in lista for h in huellas(v)}
    desde = (date.fromisoformat(hoy) - timedelta(days=cfg.get("dias_frescura", 14))).isoformat()
    por_rol, motivos = {r["id"]: [] for r in roles}, Counter()
    descartes_rol = {r["id"]: Counter() for r in roles}
    panel = any("_perfiles" in r for r in roles)
    libres = []  # pasan las reglas generales pero ningún perfil las acepta tal cual: material para ampliar
    compartidas = []  # sirven igual de bien a varios cargos del panel: se reparten por turnos
    for v in vacante.juntar(vacantes):
        if any(h in incluidas for h in huellas(v)):
            continue
        empatados, grado = roles_de(v, roles)
        rol = empatados[0] if empatados else None
        if not rol:
            if panel and not _motivo_general(v, entregadas, desde, cfg, omitir_verificacion):
                libres.append(v)
            continue
        if any(h in entregadas for h in huellas(v)):
            motivos["ya entregada"] += 1
            descartes_rol[rol["id"]]["ya entregada"] += 1
            continue
        if (v.get("visto_primera_vez") or "") < desde:
            motivos["vista hace más de %d días" % cfg.get("dias_frescura", 14)] += 1
            descartes_rol[rol["id"]]["fuera de frescura"] += 1
            continue
        revision = v.get("verificacion")
        if not omitir_verificacion and revision is not None and revision.get("estado") != "verificada":
            motivos["enlaces sin comprobar o rechazados"] += 1
            descartes_rol[rol["id"]]["enlaces sin comprobar o rechazados"] += 1
            continue
        motivo = contrato.entregable(v, tuple(cfg.get("idiomas", ["es", "en"])))
        if motivo:
            motivos[motivo] += 1
            descartes_rol[rol["id"]][motivo] += 1
            continue
        if panel and len(empatados) > 1:
            compartidas.append((v, grado, [r["id"] for r in empatados]))
        else:
            por_rol[rol["id"]].append((v, grado))
    if compartidas:
        _repartir_por_turnos(compartidas, por_rol, roles, cfg, iniciales)
    salida, resumen = {}, {}
    for rol in roles:
        candidatas = por_rol[rol["id"]]
        salida[rol["id"]] = variadas(candidatas, meta_de(rol, cfg), cfg.get("max_por_empresa", 2), hoy,
                                      cfg.get("preferir_remotas", False), iniciales.get(rol["id"], []), perfiles=rol.get("_perfiles",[]))
    if panel:
        tomadas = {v["id"] for lista in salida.values() for v, _ in lista}
        libres += [v for lista in por_rol.values() for v, _ in lista if v["id"] not in tomadas]
        for rol in roles:
            salida[rol["id"]] = ampliar(rol, salida[rol["id"]], libres, meta_de(rol, cfg),
                                        cfg.get("max_por_empresa", 2), hoy)
            salida[rol["id"]] = completar_cupo_por_empresa(salida[rol["id"]], por_rol[rol["id"]], meta_de(rol, cfg))
        deficit = deficit_por_perfil(salida, roles, hoy)
    for rol in roles:
        candidatas = por_rol[rol["id"]]
        elegidas = [v for v, _ in salida[rol["id"]]]
        unicas = len(vacante.juntar(elegidas))
        empresas = Counter(normalizar.empresa(v["empresa"]) for v, _ in candidatas + list(iniciales.get(rol["id"], [])))
        capacidad = sum(min(n, cfg.get("max_por_empresa", 2)) for n in empresas.values())
        resumen[rol["id"]] = {
            "nombre": rol["nombre"], "candidatas": len(candidatas) + len(iniciales.get(rol["id"], [])), "entregadas": len(elegidas),
            "unicas": unicas, "duplicadas": len(elegidas) - unicas,
            "faltan": max(0, meta_de(rol, cfg) - unicas),
            "idiomas": dict(Counter(v["idioma"] for v in elegidas)),
            "niveles": dict(Counter(contrato.seniority(v["titulo"]) or "sin nivel" for v in elegidas)),
            "paises": dict(Counter((v["paises"][0] if len(v["paises"]) == 1 else "varios") for v in elegidas)),
            "remotas": sum(v["modalidad"] == "remoto" for v in elegidas),
            "remotas_amplias": sum(prioridad_remota(v) == 0 for v in elegidas),
            "descartadas": dict(descartes_rol[rol["id"]]),
            "empresas_disponibles": len(empresas),
            "capacidad_con_tope_empresa": capacidad,
            "limitadas_por_empresa": sum(empresas.values()) - capacidad,
            "reserva_sin_entregar": max(0, len(candidatas) + len(iniciales.get(rol["id"], [])) - len(elegidas)),
            "ampliadas": dict(Counter(v["_ampliacion"] for v in elegidas if v.get("_ampliacion"))),
        }
        if panel:
            perfiles_rol = [p["id"] for p in rol.get("_perfiles") or []]
            resumen[rol["id"]]["perfiles_bajo_minimo"] = sum(1 for pid in perfiles_rol if pid in deficit)
            resumen[rol["id"]]["faltan_para_minimo"] = sum(deficit.get(pid, 0) for pid in perfiles_rol)
    return salida, {"roles": resumen, "descartadas": dict(motivos)}


ETAPAS_EMBUDO = ("encontradas", "con_descripcion", "entregables", "nuevas", "enlace_comprobado", "cumplen_filtros")
PERDIDA = {"con_descripcion": "sin descripción completa (no se sabe el idioma)",
           "entregables": "país o idioma sin confirmar",
           "nuevas": "ya entregadas antes o vistas hace demasiado",
           "enlace_comprobado": "enlace sin comprobar a tiempo",
           "cumplen_filtros": "no cumplen los filtros de ningún perfil del cargo"}


def embudo(vacantes, entregadas, hoy, cfg=None, resumen=None):
    """Por cargo: cuántas vacantes sobreviven a cada paso hasta la entrega y dónde se pierden más. Solo cuentas por
    cargo y motivo, sin datos de clientes. `resumen` (de `elegir`/`correr`) aporta entregadas y ampliadas."""
    cfg = cfg or config()
    roles = cfg["roles"]
    desde = (date.fromisoformat(hoy) - timedelta(days=cfg.get("dias_frescura", 14))).isoformat()
    idiomas = tuple(cfg.get("idiomas", ["es", "en"]))
    salida = {r["id"]: {"nombre": r["nombre"], **{e: 0 for e in ETAPAS_EMBUDO}} for r in roles}
    for v in vacantes:
        grados = {f["familia"]: f["coincidencia"] for f in v.get("familias", [])}
        propios = [r for r in roles if any(grados.get(f) in ("exacto", "similar") for f in r["familias"])]
        if not propios:
            continue
        pasos = ["encontradas"]
        if len(v.get("_descripcion") or "") >= 200:
            pasos.append("con_descripcion")
            if not contrato.entregable(dict(v, verificacion=None), idiomas):
                pasos.append("entregables")
                if not any(h in entregadas for h in huellas(v)) and (v.get("visto_primera_vez") or "") >= desde:
                    pasos.append("nuevas")
                    if (v.get("verificacion") or {}).get("estado") == "verificada":
                        pasos.append("enlace_comprobado")
        asignado = rol_de(v, roles)[0] if "enlace_comprobado" in pasos else None
        for r in propios:
            for e in pasos:
                salida[r["id"]][e] += 1
            if asignado is r:
                salida[r["id"]]["cumplen_filtros"] += 1
    for rid, e in salida.items():
        r = ((resumen or {}).get("roles") or {}).get(rid, {})
        e["entregadas"], e["ampliadas"] = r.get("entregadas", 0), sum((r.get("ampliadas") or {}).values())
        caidas = {etapa: e[anterior] - e[etapa] for anterior, etapa in zip(ETAPAS_EMBUDO, ETAPAS_EMBUDO[1:])}
        mayor = max(caidas, key=caidas.get) if any(caidas.values()) else None
        e["principal_perdida"] = PERDIDA[mayor] if mayor else ""
    return salida


def filas_de(elegidas, roles, hoy, capturada):
    nombres = {r["id"]: r["nombre"] for r in roles}
    filas, ids = [], set()
    for rol_id, lista in elegidas.items():
        for v, grado in lista:
            for fila in contrato.filas(v, nombres[rol_id], GRADO_CONTRATO.get(grado, grado), hoy,
                                       v.get("_capturada_entrega", capturada)):
                if fila["external_id"] not in ids:   # dos vacantes con el mismo enlace directo: una sola fila
                    ids.add(fila["external_id"])
                    filas.append(fila)
    return filas


def registrar_medicion(historial, resumen, hoy, dias=30):
    """Serie corta para medir continuidad real; no predice ofertas futuras ni almacena descripciones."""
    historial[hoy] = {
        "fecha": hoy, "meta_cumplida": resumen["meta_cumplida"],
        "pendientes_supabase": (resumen.get("supabase") or {}).get("pendientes", 0),
        "registro_confirmado": bool(resumen.get("registro_seleccion")) and not any(
            resumen["registro_seleccion"].get(k) for k in ("errores", "pendientes", "omitida")),
        "enlaces_comprobados": bool(resumen.get("enlaces_comprobados")),
        "roles": {rid: {k: r[k] for k in ("candidatas", "entregadas", "faltan", "reserva_sin_entregar")}
                  for rid, r in resumen["roles"].items()},
    }
    desde = (date.fromisoformat(hoy) - timedelta(days=dias - 1)).isoformat()
    for dia in [dia for dia in historial if dia < desde]:
        del historial[dia]
    return [historial[dia] for dia in sorted(historial) if dia <= hoy][-7:]


def correr(vacantes, entregadas, hoy, capturada, carpeta, subir=None, pendientes=None, persistir=None,
           lote=None, persistir_lote=None, registrar_seleccion=None):
    """Elige y sube a Supabase. `carpeta` conserva compatibilidad de llamadas, sin generar archivos.
    `entregadas` (dict huella → fecha) se actualiza con lo entregado hoy.
    Devuelve el resumen para salud.json."""
    cfg = config()
    iniciales = (lote or {}).get("elegidas", {}) if (lote or {}).get("fecha") == hoy else {}
    elegidas, resumen = elegir(vacantes, entregadas, hoy, cfg, iniciales=iniciales)
    elegidas = {rol: [(dict(v, _capturada_entrega=v.get("_capturada_entrega", capturada)), g) for v, g in lista]
                for rol, lista in elegidas.items()}
    if persistir_lote:
        persistir_lote({"fecha": hoy, "elegidas": elegidas})  # permite reconstruir cola si se interrumpe el siguiente paso
    filas = filas_de(elegidas, cfg["roles"], hoy, capturada)
    pendientes = pendientes if pendientes is not None else {}
    for fila in filas:
        pendientes.setdefault(fila["external_id"], fila)
    if persistir:
        persistir(pendientes)  # diario durable antes de cualquier petición
    for lista in elegidas.values():
        for v, _ in lista:
            for h in huellas(v):
                entregadas[h] = hoy
    # Se olvida lo entregado hace más de 180 días (para entonces la vacante ya se borró de la bodega)
    limite = (date.fromisoformat(hoy) - timedelta(days=180)).isoformat()
    for h in [h for h, f in entregadas.items() if f < limite]:
        del entregadas[h]
    resumen["vacantes"] = sum(len(x) for x in elegidas.values())
    resumen["vacantes_unicas"] = len(vacante.juntar([v for lista in elegidas.values() for v,_ in lista]))
    resumen["copias_en_lote"] = resumen["vacantes"] - resumen["vacantes_unicas"]
    resumen["enlaces_comprobados"] = bool(resumen["vacantes"]) and all(
        (v.get("verificacion") or {}).get("estado") == "verificada" for lista in elegidas.values() for v, _ in lista)
    resumen["filas"] = len(filas)
    resumen["archivos"] = False  # compatibilidad con reportes históricos; Supabase es el destino operativo
    resumen["meta_por_rol"] = cfg["por_rol"] if all(meta_de(r,cfg)==cfg["por_rol"] for r in cfg["roles"]) else None
    resumen["metas_por_rol"] = {r["id"]:meta_de(r,cfg) for r in cfg["roles"]}
    resumen["meta_cumplida"] = all(r["faltan"] == 0 for r in resumen["roles"].values()) and not resumen["copias_en_lote"]
    if subir is not None:
        resultado = dict(subir(list(pendientes.values())))
        for external_id in resultado.pop("confirmadas", []):
            pendientes.pop(external_id, None)
        resultado["pendientes"] = len(pendientes)
        resumen["supabase"] = resultado
        if persistir:
            persistir(pendientes)
    if registrar_seleccion:
        resumen["registro_seleccion"] = registrar_seleccion({"fecha": hoy, "elegidas": elegidas})
    return resumen
