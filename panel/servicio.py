"""Vistas y texto para copiar; nunca se envía WhatsApp."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from buscador import contrato, vacante
from panel.afinidad import (AMPLIACIONES, ETIQUETAS_AMPLIACION, MINIMO_POR_PERFIL, enlace_utilizable, evaluar,
                            evaluar_ampliada)
from panel.repositorio import hoy
from panel.terminos import grado, sugerir

# Qué puede hacer el operador cuando un filtro, por sí solo, deja fuera vacantes. Sin sugerencia si no depende de él.
SUGERENCIAS = {
    "experiencia no informada": "Admitir experiencia no informada",
    "inglés requerido sin confirmar": "Admitir inglés no informado",
    "publicación fuera del plazo": "Ampliar la antigüedad de publicación",
    "oficina en otro país": "Añadir países a los que se mudaría",
    "modalidad diferente": "Aceptar otra modalidad",
    "idioma del aviso diferente": "Aceptar avisos en español e inglés",
    "experiencia fuera del rango": "Ampliar el rango de experiencia",
    "inglés requerido superior al indicado": "Subir el nivel de inglés admitido",
}
SIN_DATO = {"experiencia no informada", "inglés requerido sin confirmar"}
_POR_CARGO = {}


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
        for v in (del_cargo if nivel == "sin_dato" else del_cargo + cercanas):
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
        elif set(r["motivos"]) == SIN_DATO:  # muchos avisos no dicen ni años ni nivel de inglés
            solo["ambos sin dato"] += 1
    limitantes = [{"motivo": m, "vacantes": n, "sugerencia": SUGERENCIAS[m]} for m, n in solo.items() if m in SUGERENCIAS]
    if solo["ambos sin dato"]:
        limitantes.append({"motivo": "experiencia e inglés no informados",
                           "vacantes": sum(solo[m] for m in (*SIN_DATO, "ambos sin dato")),
                           "sugerencia": "Admitir experiencia e inglés no informados"})
    return ids, sorted(limitantes, key=lambda x: -x["vacantes"])[:3]


def vista_previa(repo, cfg, fecha=None):
    """Cuántas vacantes ya guardadas y aún no entregadas cumplirían hoy cada perfil y cargo del borrador.
    Es una estimación con las mismas reglas de la selección; no busca, no guarda y no devuelve vacantes ni clientes."""
    fecha = fecha or hoy()
    catalogo = repo.catalogo_vigente()
    clientes = {c.id for c in cfg.clientes if c.activo}
    perfiles, cargos = {}, {}
    for c in cfg.cargos:
        if not c.activo:
            continue
        raw = c.model_dump(mode="json")
        if not raw["terminos_exactos"]:  # igual que la captura dirigida
            raw["terminos_exactos"] = sugerir(c.nombre, consultar_esco=False)["terminos_exactos"]
        del_cargo = _del_cargo(catalogo, raw)
        disponibles = set()
        for p in cfg.perfiles:
            if not p.activo or p.cargo_id != c.id or p.cliente_id not in clientes:
                continue
            ids, limitantes = _contar(del_cargo, p, fecha)
            disponibles |= ids
            perfiles[str(p.id)] = {"compatibles": len(ids), "del_cargo": len(del_cargo), "limitantes": limitantes,
                                   "ampliables": _ampliables(del_cargo, _del_cargo(catalogo, raw, cercanas=True), p, fecha, ids)}
        n = len(disponibles)
        estado = ("sin_cupo" if not c.cupo else "alcanza" if n >= c.cupo else "justo" if n * 2 >= c.cupo
                  else "insuficiente")
        cargos[str(c.id)] = {"disponibles": n, "del_cargo": len(del_cargo), "cupo": c.cupo, "estado": estado}
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
    with ThreadPoolExecutor(2) as hilos:
        for nombre, futuro in (("LinkedIn", hilos.submit(linkedin)), ("Get on Board", hilos.submit(getonboard))):
            try:
                filas, stats = futuro.result(timeout=limite_segundos + 5)
                crudas += filas
                fuentes[nombre] = {k: stats.get(k, 0) for k in ("busquedas", "fallidas", "avisos")}
            except Exception:  # noqa: BLE001 - una fuente caída no impide estimar con la otra
                fuentes[nombre] = {"error": True}
    return crudas, fuentes


def estimacion_en_vivo(repo, cfg, perfil_id, fecha=None, fuentes=None, reloj=time.monotonic):
    """Cuántos avisos encontrados ahora en las fuentes públicas cumplen el perfil. No guarda nada ni devuelve vacantes."""
    fecha = fecha or hoy()
    p = next((x for x in cfg.perfiles if str(x.id) == str(perfil_id)), None)
    c = p and next((x for x in cfg.cargos if x.id == p.cargo_id), None)
    if not c:
        return {"error": "Perfil o cargo no encontrado en la configuración."}
    if not _EN_CURSO.acquire(blocking=False):
        return {"ocupado": True, "nota": "Ya hay una búsqueda en vivo en curso. Inténtalo en un minuto."}
    try:
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
    finally:
        _EN_CURSO.release()


def resultados(repo, cliente_id=None, fecha=None):
    r = repo.resultados(cliente_id, fecha)
    salida, vistas = [], {}
    for row in r["filas"]:
        v = row.get("catalogo_vacantes") or {}
        datos = v.get("datos") or {}
        # Los datos públicos no traen las observaciones de ubicación ni el origen de la fecha: conservar lo que calculó
        # la bodega en vez de rehacerlo con menos evidencia.
        actual = vacante.reetiquetar(dict(datos, _descripcion=v.get("description_full") or datos.get("_descripcion", "")),
                                     publicada=True)
        ampliacion = next((e["ampliacion"] for e in row.get("explicacion") or [] if isinstance(e, dict) and e.get("ampliacion")), "")
        filtros = evaluar_ampliada(actual, row["filtros"], hoy(), ampliacion) if ampliacion else evaluar(actual, row["filtros"], hoy())
        afinidad_cargo,_ = grado(actual["titulo"],row["cargo_configuracion"], cercanos=ampliacion == "cargo_cercano")
        if not afinidad_cargo:
            filtros["compatible"] = False
            filtros["motivos"].append("el título actual no corresponde al cargo configurado")
        enlace = enlace_utilizable(row) if filtros["compatible"] and not contrato.entregable(actual) else ""
        clave = row["vacante_id"]
        if clave in vistas and (vistas[clave]["estado"] == "lista" or not enlace):
            continue
        ficha = {"id": clave, "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": datos.get("ubicacion", ""), "modalidad": datos.get("modalidad", ""),
            "idioma": datos.get("idioma", ""), "publicada": datos.get("fecha_publicacion", ""),
            "experiencia": datos.get("anos_min"), "match_grade": row["match_grade"],
            "explicacion": row["explicacion"], "cargo_id": row["cargo_id"], "enlace": enlace,
            "estado": "lista" if enlace else "retirada" if v.get("status") != "active" else "por_confirmar",
            "motivos": filtros["motivos"], "ampliacion": ETIQUETAS_AMPLIACION.get(ampliacion, "")}
        if clave in vistas:
            salida[salida.index(vistas[clave])] = ficha
        else:
            salida.append(ficha)
        vistas[clave] = ficha
    return {**{k: r[k] for k in ("ejecucion", "clientes")}, "vacantes": salida,
            "listas": sum(v["estado"] == "lista" for v in salida)}


def whatsapp(repo, cliente_id, fecha=None):
    r = resultados(repo, cliente_id, fecha)
    listas = [v for v in r["vacantes"] if v["estado"] == "lista"]
    if not listas:
        return {"texto": "", "vacantes": 0, "nota": "No hay vacantes con filtros y enlace vigentes para copiar."}
    texto = "Hola, el día de hoy te traigo estas vacantes que pueden ser de tu interés. Te las comparto para que puedas aplicar lo más pronto posible:\n\n"
    texto += "\n\n".join(f"{i}. {' '.join(v['titulo'].split())} · {' '.join(v['empresa'].split())}\n{v['enlace']}"
                          for i, v in enumerate(listas, 1))
    texto += "\n\nRevisa los requisitos y postúlate directamente en cada enlace. ¡Mucho éxito!"
    return {"texto": texto, "vacantes": len(listas)}
