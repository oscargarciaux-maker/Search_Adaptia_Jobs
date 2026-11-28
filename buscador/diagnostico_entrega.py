"""P-16.1 (Oscar, 28 nov, prioridad 1): medidor de entrega estable, en SOLO LECTURA.

Objetivo del sistema: a cada persona le llega cada día una cantidad estable de vacantes (su meta, mínimo 5). Este
medidor no cambia la selección: dice, por perfil, cuánto recibió en los últimos 14 días y dónde se le caen las
vacantes de la bodega de hoy (el catálogo activo de Supabase):

    cargo → lugar/remoto → idioma → requisitos del sistema (30 días, fecha) → enlace comprobado → no recibida antes
    → asignada hoy

Además: cuántas esperan en «Por confirmar» para ese perfil (y por qué duda), la causa principal de lo que le falta
(«mercado»: pocas por su cargo; «mercado_flujo»: las candidatas ya le llegaron otros días y las nuevas del día no
alcanzan su meta (P-16.4); «capacidad»: le servirían pero no se comprobó su enlace por turno o tiempo; «sistema»: hay
candidatas y se caen en un paso, que se nombra), cuántas «nuevas de hoy» tiene (vistas por primera vez en la última
búsqueda y que pasan todo el embudo hasta «no recibida») y el conteo de repeticiones de la 12.15: pares
(perfil, vacante) asignados más de una vez, por camino y por fecha.

Usa las mismas reglas que la selección (`panel.afinidad.lugar` y `evaluar`, `panel.terminos.grado` con el cargo
operativo de `panel.ejecutor.cargos_operativos`) y las lecturas de `panel/repositorio.py` (`paginar`, `recibidas`,
`asignaciones_por_perfil`…), sin cambiarlas. No escribe nada.

PRIVACIDAD: el repositorio es público y el resumen, el registro y el artefacto de Actions también. Todo lo que sale
pasa antes por `lista_blanca`: solo cifras, fechas, un índice anónimo por perfil (P01, P02…, ordenado de quien menos
recibe a quien más, no por cliente ni por id, así que cambia de una corrida a otra) y textos fijos de este archivo
(pasos, causas, familias de fuente). Nunca nombres, ids, ciudades, países, cargos, términos ni metas por perfil.
Los avisos internos del repositorio (que podrían traer una dirección con ids) no se imprimen: solo se cuentan.

Uso: python -m buscador.diagnostico_entrega --salida <carpeta>   (escribe entrega.json y entrega.md)
"""
import argparse
from collections import Counter, defaultdict
import contextlib
from datetime import date, datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import sys

from panel.afinidad import (MINIMO_POR_PERFIL as MINIMO, MOTIVO_CIUDAD_SIN_CONFIRMAR, MOTIVO_OTRO_PAIS,
                            MOTIVO_SIN_CIUDAD, evaluar, ligera, lugar)
from panel.repositorio import paginar
from panel.servicio import DIAS_COBERTURA as DIAS, DIAS_PARA_MEDIR
from panel.terminos import grado

PASOS = ("cargo", "lugar", "idioma", "requisitos", "enlace", "no_recibida", "asignada")
HORAS_VIGENCIA = 24  # una comprobación vale 24 h para seleccionar y compartir (contrato §8)

CAUSA_CUMPLE, CAUSA_MERCADO, CAUSA_MERCADO_FLUJO, CAUSA_CAPACIDAD, CAUSA_SISTEMA, CAUSA_SIN_DATOS = (
    "cumple", "mercado", "mercado_flujo", "capacidad", "sistema", "sin_datos")
CAUSAS = (CAUSA_CUMPLE, CAUSA_MERCADO, CAUSA_MERCADO_FLUJO, CAUSA_CAPACIDAD, CAUSA_SISTEMA, CAUSA_SIN_DATOS)

# Enlace sin comprobar: por qué (de `datos.verificacion.motivo`, textos fijos de buscador/verificar_enlaces.py).
# «sin_turno» y «vencida» (comprobada hace más de 24 h) son de capacidad: más turnos o tiempo las comprobarían.
# «solo_vista» (Indeed y otros que solo valen por verse hoy: «sin comprobación directa») no se arregla con turnos.
ENLACE_SIN_TURNO, ENLACE_VENCIDA, ENLACE_SOLO_VISTA, ENLACE_BLOQUEO, ENLACE_NO_COMPROBABLE, ENLACE_RECHAZADA = (
    "sin_turno", "vencida", "solo_vista", "bloqueo", "no_comprobable", "rechazada")
ENLACES = (ENLACE_SIN_TURNO, ENLACE_VENCIDA, ENLACE_SOLO_VISTA, ENLACE_BLOQUEO, ENLACE_NO_COMPROBABLE,
           ENLACE_RECHAZADA)
ENLACES_CAPACIDAD = frozenset({ENLACE_SIN_TURNO, ENLACE_VENCIDA})
_SIN_TURNO = ("presupuesto", "sin comprobación vigente", "sin comprobacion vigente")
_SOLO_VISTA = ("sin comprobación directa", "sin comprobacion directa")
_BLOQUEO = ("bloque", "sesión", "sesion", "fallo", "conexión", "conexion", "captcha", "403", "429")

# Lugar: el primer motivo de `panel.afinidad.lugar`, en grupos fijos.
LUGARES = {"modalidad diferente": "modalidad", "país sin elegibilidad confirmada": "pais_sin_confirmar",
           "no admite postular desde su país": "no_abierta_a_su_pais", MOTIVO_OTRO_PAIS: "oficina_otro_pais",
           MOTIVO_SIN_CIUDAD: "sin_ciudad", MOTIVO_CIUDAD_SIN_CONFIRMAR: "ciudad_sin_confirmar",
           "oficina en otra ciudad": "otra_ciudad"}
LUGAR_OTRO = "otro"

# Familias de fuente (texto fijo; el nombre de cada portal se reduce a una de estas). El orden importa: Apify antes
# que LinkedIn.
APIFY = "LinkedIn (Apify)"
_FUENTES = (("apify", APIFY), ("publicaci", "LinkedIn (publicación)"), ("linkedin", "LinkedIn"),
            ("indeed", "Indeed"), ("computrabajo", "Computrabajo"), ("get on board", "Get on Board"),
            ("getonbrd", "Get on Board"), ("bumeran", "Bumeran y hermanos"), ("laborum", "Bumeran y hermanos"),
            ("multitrabajos", "Bumeran y hermanos"), ("konzerta", "Bumeran y hermanos"),
            ("zonajobs", "Bumeran y hermanos"), ("infojobs", "InfoJobs"), ("tecnoempleo", "Tecnoempleo"),
            ("elempleo", "Elempleo"), ("hireline", "Hireline"), ("magneto", "Magneto"),
            ("greenhouse", "Portales de empresas"), ("lever", "Portales de empresas"),
            ("ashby", "Portales de empresas"), ("workable", "Portales de empresas"),
            ("smartrecruiters", "Portales de empresas"), ("recruitee", "Portales de empresas"),
            ("portales de empresas", "Portales de empresas"), ("remotive", "Tableros remotos"),
            ("working nomads", "Tableros remotos"), ("tableros", "Tableros remotos"))
FUENTE_OTRA = "Otras"
FUENTES = tuple(dict.fromkeys([f for _, f in _FUENTES] + [FUENTE_OTRA]))

# Grupos de perfil (solo para totales): idiomas que acepta × si acepta remoto.
GRUPOS = tuple(f"{i}+{r}" for i in ("solo_es", "solo_en", "es_en") for r in ("remoto", "sin_remoto"))
TIPOS = ("cliente", "comunidad")
DUDAS = ("ubicacion", "funciones", "otro_oficio")
CAMINOS = ("lote", "lote_ampliada", "rescate", "reutilizada", "post", "sirve")

# Solo lo que usan los filtros; a diferencia de la estimación del panel, también los campos del alcance (mundial,
# países nombrados, zona, nota), para que una remota mundial cuente como la cuenta la selección.
CAMPOS_CATALOGO = (
    "id,titulo:datos->>titulo,paises:datos->paises,paises_mundo:datos->paises_mundo,"
    "alcance_mundial:datos->alcance_mundial,zona_utc:datos->zona_utc,ubicacion:datos->>ubicacion,"
    "nota_pais:datos->>nota_pais,confianza_pais:datos->>confianza_pais,modalidad:datos->>modalidad,"
    "idioma:datos->>idioma,publicada_en:datos->>publicada_en,fecha_publicacion:datos->>fecha_publicacion,"
    "fecha_estimada:datos->fecha_estimada,ids_agrupados:datos->ids_agrupados,anos_min:datos->anos_min,"
    "ingles:datos->>ingles,requisito_ingles:datos->requisito_ingles,salario:datos->>salario,"
    "duplicada_de:datos->>duplicada_de,tipo:datos->>tipo,verificacion:datos->verificacion->>estado,"
    "verificacion_motivo:datos->verificacion->>motivo,comprobada_en:datos->verificacion->>comprobada_en,fuente:datos->>fuente,fuentes:datos->fuentes,"
    "visto_primera_vez:datos->>visto_primera_vez")


def familia_fuente(texto):
    t = str(texto or "").lower()
    return next((familia for clave, familia in _FUENTES if clave in t), FUENTE_OTRA)


def categoria_enlace(v, ahora=None):
    """'' si el enlace está comprobado en las últimas 24 h (lo que exige la selección); si no, por qué."""
    estado = v.get("_verificacion") or ""
    if estado == "verificada":
        ahora = ahora or datetime.now(timezone.utc)
        try:
            cuando = datetime.fromisoformat(str(v.get("_comprobada_en") or "").replace("Z", "+00:00"))
            if cuando.tzinfo is None:
                cuando = cuando.replace(tzinfo=timezone.utc)
            vigente = 0 <= (ahora - cuando).total_seconds() < HORAS_VIGENCIA * 3600
        except ValueError:
            vigente = False
        return "" if vigente else ENLACE_VENCIDA
    if estado == "rechazada":
        return ENLACE_RECHAZADA
    motivo = str(v.get("_motivo_enlace") or "").lower()
    if any(x in motivo for x in _SOLO_VISTA):
        return ENLACE_SOLO_VISTA
    if not motivo or any(x in motivo for x in _SIN_TURNO):
        return ENLACE_SIN_TURNO
    if any(x in motivo for x in _BLOQUEO):
        return ENLACE_BLOQUEO
    return ENLACE_NO_COMPROBABLE


def camino(explicacion):
    """Por qué camino se asignó una fila de `panel_asignaciones` (la misma regla que el conteo SQL de la 12.15)."""
    partes = [e for e in explicacion if isinstance(e, dict)] if isinstance(explicacion, list) else []
    if any(e.get("rescatada") == "bodega" for e in partes):
        return "rescate"
    if any(e.get("tipo") == "post" for e in partes):
        return "post"
    if any("reutilizada" in e for e in partes):
        return "reutilizada"
    # «Sirve» de «Por confirmar»: `aprobada_por` desde v49; antes, `{"funciones": True}` (no el nivel de evidencia).
    if any("confirmada" in e or "aprobada_por" in e or e.get("funciones") is True for e in partes):
        return "sirve"
    if any("ampliacion" in e for e in partes):
        return "lote_ampliada"
    return "lote"


def grupo_de(p):
    idiomas = set(p.idiomas)
    i = "solo_es" if idiomas == {"es"} else "solo_en" if idiomas == {"en"} else "es_en"
    return i + ("+remoto" if any("remoto" in f.modalidades for f in p.filas) else "+sin_remoto")


def _vacante(d):
    v = ligera(d)
    v["_motivo_enlace"] = d.get("verificacion_motivo") or ""
    v["_comprobada_en"] = d.get("comprobada_en") or ""
    v["_fuente"] = familia_fuente(d.get("fuente"))
    fuentes = d.get("fuentes") if isinstance(d.get("fuentes"), list) else []
    v["_apify"] = v["_fuente"] == APIFY or any(familia_fuente(f) == APIFY for f in fuentes)
    v["_ids"] = {str(d["id"]), *(str(x) for x in (d.get("ids_agrupados") or []) if x)}
    v["_visto"] = str(d.get("visto_primera_vez") or "")[:10]
    return v


def leer_catalogo(pedir):
    """Vacantes activas del catálogo (sin copias ni posts), reducidas a lo que usan los filtros. Incluye las de enlace
    rechazado para contarlas en el paso «enlace»."""
    return [_vacante(d) for d in paginar(pedir, "catalogo_vacantes", "id",
                                         {"status": "eq.active", "select": CAMPOS_CATALOGO}, 1000)
            if not d.get("duplicada_de") and d.get("tipo") != "post"]


def embudo(del_cargo, p, fecha, recibidas_antes, asignadas_hoy, por_fuente=None, ahora=None, dia_busqueda=""):
    """Cuántas vacantes del cargo pasan cada paso para el perfil `p`. `por_fuente` (opcional) acumula lo mismo por
    familia de fuente y para las que trajo Apify. El cuarto valor son las «nuevas de hoy»: llegan hasta «no recibida»
    y se vieron por primera vez el `dia_busqueda` (la fecha de la última búsqueda): el flujo diario del perfil."""
    n, enlace, motivos_lugar = Counter(), Counter(), Counter()
    nuevas = 0

    def paso(v, nombre):
        n[nombre] += 1
        if por_fuente is not None:
            por_fuente[v["_fuente"]][nombre] += 1
            if v["_apify"]:
                por_fuente["_apify"][nombre] += 1

    for v in del_cargo:
        paso(v, "cargo")
        fallos, _ = lugar(v, p)
        if fallos:
            motivos_lugar[LUGARES.get(fallos[0], LUGAR_OTRO)] += 1
            continue
        paso(v, "lugar")
        if v.get("idioma") not in p.idiomas:
            continue
        paso(v, "idioma")
        if not evaluar(v, p, fecha)["compatible"]:
            continue
        paso(v, "requisitos")
        categoria = categoria_enlace(v, ahora)
        if categoria:
            enlace[categoria] += 1
            continue
        paso(v, "enlace")
        if v["_ids"] & recibidas_antes:
            continue
        paso(v, "no_recibida")
        nuevas += bool(dia_busqueda) and v.get("_visto") == dia_busqueda
        if v["_ids"] & asignadas_hoy:
            paso(v, "asignada")
    return {k: n.get(k, 0) for k in PASOS}, dict(enlace), dict(motivos_lugar), nuevas


def causa_de(pasos, enlace, objetivo, hoy_n):
    """(causa, paso) de lo que le falta hoy: el primer paso del embudo que queda por debajo de su meta.
    P-16.4: si frena «no recibida», las candidatas existen pero ya le llegaron otros días y las que aún no recibió no
    alcanzan su meta: es el flujo del mercado, no una pérdida del sistema (ENTREGA.md §6). «nuevas_hoy» (las vistas
    por primera vez en la última búsqueda) es otra cifra: mide el flujo, no decide la causa."""
    if hoy_n >= objetivo:
        return CAUSA_CUMPLE, ""
    freno = next((k for k in PASOS if pasos[k] < objetivo), "asignada")
    if freno == "cargo":
        return CAUSA_MERCADO, freno
    if freno == "no_recibida":
        return CAUSA_MERCADO_FLUJO, freno
    if freno == "enlace" and sum(enlace.get(k, 0) for k in ENLACES_CAPACIDAD) * 2 > sum(enlace.values()):
        return CAUSA_CAPACIDAD, freno
    return CAUSA_SISTEMA, freno


def tipo_duda(motivo):
    from panel.revision import FUNCIONES, OTRO_OFICIO
    return "funciones" if motivo == FUNCIONES else "otro_oficio" if motivo == OTRO_OFICIO else "ubicacion"


def _dias(desde, hasta):
    try:
        return (date.fromisoformat(str(hasta)[:10]) - date.fromisoformat(str(desde)[:10])).days
    except (TypeError, ValueError):
        return None


def calcular(fecha, cfg, cargos, catalogo, ejecuciones, conteo, metas, recibidas, asignadas_hoy, revisiones,
             ahora=None):
    """Todo el cálculo, sin leer nada (las pruebas lo llaman con datos sintéticos).
    - cfg: Configuracion vigente · cargos: {cargo_id: cargo operativo} · catalogo: vacantes de `_vacante`
    - ejecuciones: [{id, fecha}] la más reciente primero · conteo: Counter((ejecucion_id, perfil_id))
    - metas: {ejecucion_id: {perfil_id: meta de ese día}} (un perfil ausente no estaba activo ese día)
    - recibidas: {perfil_id: vacantes recibidas alguna vez} · asignadas_hoy: {perfil_id: vacantes de la última}
    - revisiones: filas pendientes de «Por confirmar» ({motivo, perfiles: [{perfil_id}], creada_en})
    - ahora: instante para la vigencia de 24 h de los enlaces (por defecto, ahora)"""
    ahora = ahora or datetime.now(timezone.utc)
    desde = (date.fromisoformat(fecha) - timedelta(days=DIAS - 1)).isoformat()
    ventana = [e for e in ejecuciones if desde <= str(e.get("fecha", ""))[:10] <= fecha]
    ultima = str(ventana[0]["id"]) if ventana else None
    dia_busqueda = str(ventana[0].get("fecha", ""))[:10] if ventana else ""
    comunidades = {c.id for c in cfg.clientes if c.activo and c.comunidad}
    clientes = {c.id for c in cfg.clientes if c.activo}
    dudas = defaultdict(Counter)
    edades = Counter()
    for r in revisiones:
        edad = _dias(r.get("creada_en"), fecha)
        edades["0_2" if edad is None or edad <= 2 else "3_7" if edad <= 7 else "8_o_mas"] += 1
        for info in r.get("perfiles") or []:
            if isinstance(info, dict) and info.get("perfil_id"):
                dudas[str(info["perfil_id"])][tipo_duda(r.get("motivo"))] += 1
    por_fuente = defaultdict(Counter)
    enlace_total, lugar_total = Counter(), Counter()
    filas = []  # (fila pública, datos solo para los totales: dirían la meta del perfil)
    for c in cfg.cargos:
        raw = cargos.get(str(c.id))
        perfiles = [p for p in cfg.perfiles_activos(str(c.id)) if p.cliente_id in clientes] if c.activo else []
        if raw is None or not perfiles:
            continue
        del_cargo = [v for v in catalogo if grado(v.get("titulo") or "", raw, cercanos=True)[0]]
        for p in perfiles:
            pid = str(p.id)
            tipo = "comunidad" if p.cliente_id in comunidades else "cliente"
            meta = int(p.meta_diaria or 0)
            serie = []
            for e in reversed(ventana):
                m = metas.get(str(e["id"]), {})
                if pid in m:
                    serie.append((conteo.get((str(e["id"]), pid), 0), int(m[pid] or meta)))
            hoy_ids = {str(x) for x in asignadas_hoy.get(pid, ())}
            hoy_n = conteo.get((ultima, pid), 0) if ultima else 0
            antes = {str(x) for x in recibidas.get(pid, ())} - hoy_ids
            pasos, enlace, lugares, nuevas = embudo(del_cargo, p, fecha, antes, hoy_ids,
                                                    por_fuente if tipo == "cliente" else None, ahora, dia_busqueda)
            if tipo == "cliente":
                enlace_total.update(enlace)
                lugar_total.update(lugares)
            causa, freno = causa_de(pasos, enlace, meta, hoy_n) if ultima else (CAUSA_SIN_DATOS, "")
            numeros = [n for n, _ in serie]
            filas.append(({
                "tipo": tipo, "dias_medidos": len(serie), "por_dia": numeros,
                "media": round(sum(numeros) / len(numeros), 1) if numeros else None,
                "minimo": min(numeros) if numeros else None,
                "dias_en_0": sum(1 for n in numeros if n == 0),
                "dias_bajo_5": sum(1 for n in numeros if n < MINIMO),
                "dias_bajo_meta": sum(1 for n, m in serie if n < m),
                "hoy": hoy_n, "cumple_meta_hoy": hoy_n >= meta,
                "embudo": pasos, "nuevas_hoy": nuevas, "enlace_sin_comprobar": enlace, "lugar_motivos": lugares,
                "por_confirmar": {"total": sum(dudas[pid].values()), **{k: dudas[pid].get(k, 0) for k in DUDAS}},
                "causa": causa, "paso": freno,
            }, {"grupo": grupo_de(p), "faltan": max(0, meta - hoy_n),
                "deficit": round(sum(max(0, m - n) for n, m in serie) / len(serie), 2) if serie else 0.0}))
    # Índice anónimo: los clientes primero, de quien menos recibe a quien más (sin datos = primero).
    filas.sort(key=lambda x: (x[0]["tipo"] != "cliente", -1 if x[0]["media"] is None else x[0]["media"], x[0]["hoy"]))
    for i, (f, _) in enumerate(filas, 1):
        f["indice"] = f"P{i:02d}"
    con_privado = [(f, privado) for f, privado in filas if f["tipo"] == "cliente"]
    causas = defaultdict(lambda: {"perfiles": 0, "faltan_hoy": 0, "deficit_medio_14d": 0.0})
    grupos = defaultdict(lambda: {"perfiles": 0, "media": 0.0, "en_0_algun_dia": 0, "bajo_5_de_media": 0,
                                  "faltan_hoy": 0})
    con_datos = Counter()
    for f, privado in con_privado:
        if f["causa"] != CAUSA_CUMPLE:
            k = causas[(f["causa"], f["paso"])]
            k["perfiles"] += 1
            k["faltan_hoy"] += privado["faltan"]
            k["deficit_medio_14d"] = round(k["deficit_medio_14d"] + privado["deficit"], 2)
        g = grupos[privado["grupo"]]
        g["perfiles"] += 1
        if f["media"] is not None:  # la media del grupo, solo con quien tiene días medidos
            g["media"] += f["media"]
            con_datos[privado["grupo"]] += 1
        g["en_0_algun_dia"] += f["dias_en_0"] > 0
        g["bajo_5_de_media"] += f["media"] is not None and f["media"] < MINIMO
        g["faltan_hoy"] += privado["faltan"]
    for clave, g in grupos.items():
        g["media"] = round(g["media"] / con_datos[clave], 1) if con_datos[clave] else 0.0
    lista_causas = sorted(({"causa": c, "paso": p, **v} for (c, p), v in causas.items()),
                          key=lambda x: (-x["deficit_medio_14d"], -x["faltan_hoy"], x["causa"], x["paso"]))
    reales = [f for f, _ in con_privado]
    apify = por_fuente.pop("_apify", Counter())
    return {
        "fecha": fecha, "ultima_busqueda": str(ventana[0].get("fecha", ""))[:10] if ventana else "",
        "busquedas_en_ventana": len(ventana), "dias_ventana": DIAS, "catalogo_activo": len(catalogo),
        "totales": {
            "perfiles": len(reales), "comunidad": len(filas) - len(reales),
            "en_0_algun_dia": sum(1 for f in reales if f["dias_en_0"]),
            "bajo_5_de_media": sum(1 for f in reales if f["media"] is not None and f["media"] < MINIMO),
            "estables_en_meta": sum(1 for f in reales if f["dias_medidos"] >= DIAS_PARA_MEDIR
                                    and not f["dias_bajo_meta"]),
            "cumplen_hoy": sum(1 for f in reales if f["cumple_meta_hoy"]),
            "sin_datos": sum(1 for f in reales if f["dias_medidos"] < DIAS_PARA_MEDIR),
            "faltan_hoy": sum(c["faltan_hoy"] for c in lista_causas),
            "nuevas_hoy": sum(f["nuevas_hoy"] for f in reales),
        },
        "causas": lista_causas,
        "grupos": {k: grupos[k] for k in GRUPOS if k in grupos},
        "por_fuente": {k: {p: por_fuente[k].get(p, 0) for p in PASOS} for k in FUENTES if k in por_fuente},
        "apify": {p: apify.get(p, 0) for p in PASOS},
        "enlace_sin_comprobar": {k: enlace_total.get(k, 0) for k in ENLACES},
        "lugar_motivos": dict(sorted(lugar_total.items(), key=lambda x: -x[1])),
        "por_confirmar": {"pendientes": len(revisiones), "por_antiguedad_dias": {k: edades.get(k, 0)
                                                                               for k in ("0_2", "3_7", "8_o_mas")},
                          **{k: sum(d.get(k, 0) for d in dudas.values()) for k in DUDAS}},
        "perfiles": [f for f, _ in filas],
    }


def repeticiones(pedir):
    """12.15: pares (perfil, vacante) asignados más de una vez en todo `panel_asignaciones`, por camino y por fecha, y
    cuántos de esos pares salieron en 2 o más mensajes de WhatsApp. Solo cifras."""
    fechas = {str(r["id"]): str(r.get("fecha") or "")[:10]
              for r in paginar(pedir, "panel_ejecuciones", "id", {"select": "id,fecha"}, 1000)}
    grupos = defaultdict(list)
    total = 0
    for r in paginar(pedir, "panel_asignaciones", "id",
                     {"select": "id,perfil_id,cliente_id,vacante_id,ejecucion_id,creada_en"}, 1000):
        total += 1
        grupos[(str(r["perfil_id"]), str(r["vacante_id"]))].append(r)
    repetidos = {k: v for k, v in grupos.items() if len(v) > 1}
    ids = [str(r["id"]) for filas in repetidos.values() for r in filas]
    explicaciones = {}
    for i in range(0, len(ids), 100):
        for r in pedir("GET", "panel_asignaciones", params={"id": "in.(" + ",".join(ids[i:i + 100]) + ")",
                                                             "select": "id,explicacion"}) or []:
            explicaciones[str(r["id"])] = r.get("explicacion")
    transiciones, por_fecha, perfiles, clientes = Counter(), Counter(), set(), set()
    for (perfil, _), filas in repetidos.items():
        filas.sort(key=lambda r: (fechas.get(str(r.get("ejecucion_id")), ""), str(r.get("creada_en") or "")))
        primero = camino(explicaciones.get(str(filas[0]["id"])))
        for r in filas[1:]:
            transiciones[f"{primero} -> {camino(explicaciones.get(str(r['id'])))}"] += 1
            por_fecha[fechas.get(str(r.get("ejecucion_id"))) or "sin_fecha"] += 1
        perfiles.add(perfil)
        clientes.add(str(filas[0].get("cliente_id")))
    en_borradores, enviados = Counter(), Counter()
    for b in paginar(pedir, "panel_borradores", "id", {"select": "id,cliente_id,estado,vacantes"}, 500):
        for vacante in b.get("vacantes") or []:
            clave = (str(b.get("cliente_id")), str(vacante))
            en_borradores[clave] += 1
            enviados[clave] += b.get("estado") == "enviado"
    cliente_de = {k: str(v[0].get("cliente_id")) for k, v in repetidos.items()}
    return {
        "asignaciones_total": total, "pares_distintos": len(grupos), "pares_repetidos": len(repetidos),
        "filas_de_mas": sum(transiciones.values()), "perfiles_afectados": len(perfiles),
        "clientes_afectados": len(clientes),
        "primer_camino_y_repeticion": dict(sorted(transiciones.items(), key=lambda x: -x[1])),
        "repeticiones_por_fecha": dict(sorted(por_fecha.items())),
        "whatsapp": {
            "pares_repetidos_en_2_o_mas_borradores": sum(en_borradores[(cliente_de[k], k[1])] >= 2 for k in repetidos),
            "pares_repetidos_enviados_2_o_mas_veces": sum(enviados[(cliente_de[k], k[1])] >= 2 for k in repetidos),
        },
    }


def leer(repo, fecha=None):
    """Las lecturas (solo GET) que necesita `calcular`, con las funciones de panel/repositorio.py."""
    from panel.ejecutor import cargos_operativos, validar_version
    from panel.repositorio import hoy
    fecha = fecha or hoy()
    version = repo.operativa(fecha)
    if not version:
        raise RuntimeError("sin configuración vigente")
    cfg = validar_version(version)
    ejecuciones = [e for e in repo.ejecuciones() or [] if str(e.get("fecha", ""))[:10] <= fecha][:DIAS]
    ids = [str(e["id"]) for e in ejecuciones]
    configs = repo.versiones([e["revision"] for e in ejecuciones if e.get("revision") is not None])
    metas = {}
    for e in ejecuciones:
        c = configs.get(int(e["revision"])) if e.get("revision") is not None else None
        metas[str(e["id"])] = {str(p["id"]): p.get("meta_diaria") for p in (c or {}).get("perfiles", [])
                               if p.get("activo", True)}
    perfiles = [str(p.id) for p in cfg.perfiles_activos()]
    return {
        "fecha": fecha, "cfg": cfg, "cargos": cargos_operativos(repo, cfg),
        "catalogo": leer_catalogo(repo.pedir), "ejecuciones": ejecuciones,
        "conteo": repo.asignaciones_por_perfil(ids), "metas": metas,
        "recibidas": repo.recibidas(perfiles) if perfiles else {},
        "asignadas_hoy": repo.asignadas_de(ids[0]) if ids else {},
        "revisiones": list(paginar(repo.pedir, "panel_revisiones", "vacante_id",
                                   {"estado": "eq.pendiente", "select": "vacante_id,motivo,perfiles,creada_en"}, 1000)),
    }


# ── Lista blanca de lo que sale ────────────────────────────────────────────────────────────────────────────────────
CLAVES = frozenset({
    *PASOS, *ENLACES, *FUENTES, *GRUPOS, *DUDAS, *set(LUGARES.values()), LUGAR_OTRO,
    "fecha", "ultima_busqueda", "busquedas_en_ventana", "dias_ventana", "catalogo_activo", "totales", "perfiles",
    "comunidad", "en_0_algun_dia", "bajo_5_de_media", "estables_en_meta", "cumplen_hoy", "sin_datos", "faltan_hoy",
    "causas", "causa", "paso", "deficit_medio_14d", "grupos", "media", "por_fuente", "apify",
    "enlace_sin_comprobar", "lugar_motivos", "por_confirmar", "pendientes", "por_antiguedad_dias", "0_2", "3_7",
    "8_o_mas", "indice", "tipo", "dias_medidos", "por_dia", "minimo", "dias_en_0", "dias_bajo_5", "dias_bajo_meta",
    "hoy", "cumple_meta_hoy", "embudo", "total", "repeticiones", "disponible", "asignaciones_total",
    "pares_distintos", "pares_repetidos", "filas_de_mas", "perfiles_afectados", "clientes_afectados",
    "primer_camino_y_repeticion", "repeticiones_por_fecha", "whatsapp", "pares_repetidos_en_2_o_mas_borradores",
    "pares_repetidos_enviados_2_o_mas_veces", "avisos_internos", "nuevas_hoy"})
VALORES = frozenset({*PASOS, *CAUSAS, *TIPOS, ""})
_CAMINO = "(?:" + "|".join(CAMINOS) + ")"
_LIBRES = re.compile(r"P\d{2,3}|\d{4}-\d{2}-\d{2}|sin_fecha|" + _CAMINO + " -> " + _CAMINO)


def lista_blanca(obj, donde="resultado"):
    """Falla si algo de lo que va a salir no es una cifra, una fecha, el índice anónimo o un texto fijo de aquí."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str) or (k not in CLAVES and not _LIBRES.fullmatch(k)):
                raise ValueError(f"Clave fuera de la lista blanca en {donde}")
            lista_blanca(v, donde + "." + (k if k in CLAVES else "*"))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            lista_blanca(v, donde + "[]")
    elif isinstance(obj, str):
        if obj not in VALORES and not _LIBRES.fullmatch(obj):
            raise ValueError(f"Texto fuera de la lista blanca en {donde}")
    elif obj is not None and not isinstance(obj, (bool, int, float)):
        raise ValueError(f"Tipo fuera de la lista blanca en {donde}")
    return obj


def _tabla(encabezado, filas):
    return "\n".join(["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado),
                      *("| " + " | ".join(str(x) for x in f) + " |" for f in filas)])


def resumen_md(r):
    """El resumen para Actions, armado solo con lo que ya pasó la lista blanca."""
    t = r["totales"]
    partes = [
        "## P-16.1: entrega por perfil (solo lectura, perfiles anónimos)",
        f"Fecha {r['fecha']} · última búsqueda {r['ultima_busqueda'] or '—'} · {r['busquedas_en_ventana']} búsquedas en "
        f"{r['dias_ventana']} días · catálogo activo {r['catalogo_activo']} · «hoy» = la última búsqueda",
        "",
        f"**Perfiles: {t['perfiles']} · en 0 algún día: {t['en_0_algun_dia']} · bajo 5 de media: {t['bajo_5_de_media']}"
        f" · estables en su meta: {t['estables_en_meta']}** · cumplen hoy: {t['cumplen_hoy']} · sin datos: "
        f"{t['sin_datos']} · Comunidad: {t['comunidad']} · faltan hoy: {t['faltan_hoy']} · nuevas de hoy "
        f"(pares perfil-vacante de clientes): {t['nuevas_hoy']}",
        "",
        "### Causas (vacantes/día que faltan)",
        _tabla(["causa", "paso", "perfiles", "faltan hoy", "déficit medio 14 d"],
               [(c["causa"], c["paso"] or "—", c["perfiles"], c["faltan_hoy"], c["deficit_medio_14d"])
                for c in r["causas"]]),
        "",
        "### Por perfil",
        _tabla(["perfil", "tipo", "días", "media", "mín", "en 0", "<5", "<meta", "hoy", *PASOS, "nuevas hoy",
                "sin comprobar", "por confirmar", "causa", "paso"],
               [(f["indice"], f["tipo"], f["dias_medidos"], "—" if f["media"] is None else f["media"],
                 "—" if f["minimo"] is None else f["minimo"], f["dias_en_0"], f["dias_bajo_5"], f["dias_bajo_meta"],
                 f["hoy"], *(f["embudo"][p] for p in PASOS), f["nuevas_hoy"],
                 " ".join(f"{k}:{v}" for k, v in f["enlace_sin_comprobar"].items()) or "—",
                 f["por_confirmar"]["total"], f["causa"], f["paso"] or "—") for f in r["perfiles"]]),
        "",
        "### Grupos (idioma + remoto)",
        _tabla(["grupo", "perfiles", "media", "en 0 algún día", "bajo 5 de media", "faltan hoy"],
               [(k, g["perfiles"], g["media"], g["en_0_algun_dia"], g["bajo_5_de_media"], g["faltan_hoy"])
                for k, g in r["grupos"].items()]),
        "",
        "### Embudo por fuente (pares perfil-vacante de clientes)",
        _tabla(["fuente", *PASOS], [(k, *(v[p] for p in PASOS)) for k, v in r["por_fuente"].items()]
               + [("con Apify", *(r["apify"][p] for p in PASOS))]),
        "",
        "Enlace sin comprobar: " + ", ".join(f"{k} {v}" for k, v in r["enlace_sin_comprobar"].items())
        + " · Lugar (primer motivo): " + (", ".join(f"{k} {v}" for k, v in r["lugar_motivos"].items()) or "—"),
        "",
        "«Por confirmar» pendientes: " + str(r["por_confirmar"]["pendientes"]) + " · por antigüedad (días): "
        + ", ".join(f"{k} {v}" for k, v in r["por_confirmar"]["por_antiguedad_dias"].items())
        + " · por duda (pares con perfil): " + ", ".join(f"{k} {r['por_confirmar'][k]}" for k in DUDAS),
    ]
    rep = r.get("repeticiones") or {}
    partes += ["", "### Repeticiones (12.15)"]
    if rep.get("disponible") is False:
        partes.append("No se pudo leer (ver el aviso de la corrida).")
    else:
        partes += [f"Asignaciones {rep['asignaciones_total']} · pares distintos {rep['pares_distintos']} · **pares "
                   f"repetidos {rep['pares_repetidos']}** · filas de más {rep['filas_de_mas']} · perfiles "
                   f"{rep['perfiles_afectados']} · clientes {rep['clientes_afectados']} · en 2+ WhatsApp "
                   f"{rep['whatsapp']['pares_repetidos_en_2_o_mas_borradores']} · enviados 2+ veces "
                   f"{rep['whatsapp']['pares_repetidos_enviados_2_o_mas_veces']}",
                   "Camino (primero -> repetición): " + (", ".join(
                       f"{k} {v}" for k, v in rep["primer_camino_y_repeticion"].items()) or "—"),
                   "Por fecha: " + (", ".join(f"{k} {v}" for k, v in rep["repeticiones_por_fecha"].items()) or "—")]
    return "\n".join(partes) + "\n"


def medir(repo, fecha=None, ahora=None):
    """Lee y calcula; los avisos internos del repositorio no se imprimen (podrían traer una dirección con ids)."""
    avisos = io.StringIO()
    with contextlib.redirect_stderr(avisos):
        datos = leer(repo, fecha)
        resultado = calcular(**datos, ahora=ahora)
        try:
            resultado["repeticiones"] = repeticiones(repo.pedir)
        except Exception:  # noqa: BLE001 - el embudo vale igual sin el conteo
            resultado["repeticiones"] = {"disponible": False}
    resultado["avisos_internos"] = sum(1 for linea in avisos.getvalue().splitlines() if linea.startswith("[aviso]"))
    return lista_blanca(resultado)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--salida", default="diagnostico_entrega")
    args.add_argument("--fecha", default=None, help="Fecha de Bogotá (AAAA-MM-DD); por defecto, hoy")
    a = args.parse_args(argv)
    try:
        from panel.repositorio import RepositorioSupabase
        resultado = medir(RepositorioSupabase(), a.fecha)
    except Exception as e:  # noqa: BLE001 - solo el tipo: el mensaje podría traer datos
        print("::error::No se pudo medir la entrega (" + type(e).__name__ + ").")
        return 1
    if resultado["repeticiones"].get("disponible") is False:
        print("::warning::No se pudo contar las repeticiones; el embudo sí se midió.")
    texto, md = json.dumps(resultado, ensure_ascii=False, indent=1), resumen_md(resultado)
    carpeta = Path(a.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "entrega.json").write_text(texto, encoding="utf-8")
    (carpeta / "entrega.md").write_text(md, encoding="utf-8")
    print(md)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    print(f"Medido el {datetime.now(timezone.utc).isoformat(timespec='minutes')} (UTC).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
