"""Vistas y texto para copiar; nunca se envía WhatsApp."""
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import logging
import re
import threading
import time

from buscador import contrato, enlaces, familias, normalizar, paises, registro, vacante
from buscador.normalizar import titulo_base
from panel.afinidad import (AMPLIACIONES, AVISO_BAJO, ETIQUETAS_AMPLIACION, MINIMO_POR_PERFIL, MOTIVO_OTRO_PAIS,
                            encaja_asignada, enlace_utilizable,
                            evaluar, evaluar_ampliada, evaluar_asignada, post_ubicacion,
                            titulo_del_cargo)
from panel.modelos import Perfil
from panel.repositorio import ErrorRepositorio, hoy, numeros
from panel.terminos import grado, sugerir

# Qué puede hacer el operador cuando un filtro, por sí solo, deja fuera vacantes. Sin sugerencia si no depende de él.
# Desde v27 solo descartan la ubicación, el idioma y las reglas del sistema: años, inglés y restricciones solo ordenan.
SUGERENCIAS = {
    "publicación fuera del plazo": "Ampliar la antigüedad de publicación",
    MOTIVO_OTRO_PAIS: "Añadir una ubicación donde trabajaría",
    "oficina en otra ciudad": "Añadir la ciudad a sus ubicaciones",
    # Contrato v49 (decisión de Oscar): sin ciudad no llegan presenciales ni híbridas.
    "falta la ciudad en el perfil": "Escribir la ciudad donde trabajaría (sin ciudad no llegan presenciales ni híbridas)",
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


ORDEN_GRADO = {"exact": 0, "similar": 1, "close": 2}


def calidad(ficha):
    """Contrato v49: orden de la lista de un cliente y del mensaje de WhatsApp. Primero las vacantes formales, sin
    ampliación, con mejor coincidencia del cargo y que encajan en todo (cada etiqueta de lo que no cumple pesa como un
    grado menos, también «Funciones por confirmar»); a igualdad, la más reciente."""
    return (ficha.get("tipo") == "post", bool(ficha.get("ampliacion")),
            ORDEN_GRADO.get(ficha.get("match_grade"), 1) + len(ficha.get("avisos") or ()),
            -int((ficha.get("publicada") or "0000-00-00").replace("-", "")[:8] or 0))


# 7.G (decisión de Oscar, 27 nov): marca de la vacante de hoy que ya no encaja; no se comparte.
NO_ENCAJA_PERFIL = "ya no encaja con el cargo: se editó el perfil después de asignarla"
NO_ENCAJA_CARGO = "ya no encaja con el cargo: se editó el cargo después de asignarla"


class _ConfiguracionVigente:
    """7.G: cada asignación guarda la copia del perfil y del cargo con que se hizo. Si el operador los edita después,
    la vacante de hoy se vuelve a evaluar con los de la versión vigente de la búsqueda del día; si ya no encaja, no se
    comparte (ni lista, ni WhatsApp) y queda marcada para el operador. No se borra nada: la asignación sigue guardada.
    Un perfil o cargo que salió de la configuración no se toca (lo entregado se conserva, v49)."""

    def __init__(self, repo, r):
        self.repo = repo
        self.perfiles = {str(p.get("id")): p for p in r.get("perfiles") or [] if isinstance(p, dict)}
        self.cargos = {str(c.get("id")): c for c in r.get("cargos") or [] if isinstance(c, dict)}
        self._perfil, self._cargo, self._aprendidos, self._ampliados = {}, {}, None, {}

    def perfil(self, perfil_id):
        if perfil_id not in self._perfil:
            crudo = self.perfiles.get(perfil_id)
            try:
                self._perfil[perfil_id] = Perfil.model_validate(crudo).model_dump(mode="json") if crudo else None
            except ValueError as e:  # un perfil vigente que no valida no retira nada: queda el aviso
                registro.aviso("servicio:perfil-vigente", e)
                self._perfil[perfil_id] = None
        return self._perfil[perfil_id]

    def cargo(self, cargo_id):
        if cargo_id not in self._cargo:
            from panel import contenido
            crudo = self.cargos.get(cargo_id)
            if crudo and self._aprendidos is None:
                try:  # los títulos aprendidos (v25) también cuentan: sin ellos se retiraría lo aprobado a mano
                    self._aprendidos = (self.repo.ajuste("titulos_aprendidos", {}) or {}) if hasattr(self.repo, "ajuste") else {}
                    # P-14.2: y los términos ampliados por el LLM (con el interruptor encendido), los mismos que usó la
                    # búsqueda: sin ellos se retiraría como «ya no encaja» lo que entró por uno de ellos.
                    from panel import ampliados
                    self._ampliados = ampliados.leer(self.repo, self.cargos)
                except Exception as e:  # noqa: BLE001 — sin el dato no se mira el cargo (no se retira de más)
                    registro.aviso("servicio:aprendidos", e)
                    self._aprendidos = False
            self._cargo[cargo_id] = contenido.cargo_operativo(crudo, self._aprendidos.get(cargo_id),
                                                              ampliados=self._ampliados.get(cargo_id)) \
                if crudo and self._aprendidos is not False else None
        return self._cargo[cargo_id]

    def motivo(self, row, actual, ampliacion, aprobada):
        """El motivo si la vacante ya no encaja con el perfil o el cargo vigentes; "" si encaja o no hay con qué mirar."""
        perfil = self.perfil(str(row.get("perfil_id")))
        # Solo si el perfil cambió: sin cambios da lo mismo que la copia y se ahorra evaluar dos veces.
        # Una ampliada vale también si el perfil editado ya la acepta sin ampliar (p. ej. ahora admite remoto).
        dia = hoy()
        if perfil and perfil != row.get("filtros") \
                and not evaluar_asignada(actual, perfil, dia, ampliacion)["compatible"] \
                and not (ampliacion and evaluar_asignada(actual, perfil, dia)["compatible"]):
            return NO_ENCAJA_PERFIL
        cargo = None if aprobada else self.cargo(str(row.get("cargo_id")))
        if cargo and _cargo_editado(cargo, row.get("cargo_configuracion") or {}) \
                and not titulo_del_cargo(actual, cargo):
            return NO_ENCAJA_CARGO
        return ""


# Lo del cargo que decide si un título le corresponde (`grado`); la huella y las funciones solo ordenan.
_CAMPOS_DEL_TITULO = ("nombre", "terminos_exactos", "terminos_similares", "terminos_excluidos", "terminos_cercanos",
                      "excluir_mapa", "terminos_ampliados")


def _cargo_editado(vigente, guardado):
    """¿Cambió lo que decide el título entre el cargo operativo de ahora y la copia de la asignación?"""
    return any(sorted(map(str, vigente.get(k) or [])) != sorted(map(str, guardado.get(k) or []))
               if isinstance(vigente.get(k), list) else vigente.get(k) != guardado.get(k)
               for k in _CAMPOS_DEL_TITULO)


# P-12.10 (velocidad de «Vacantes», mismo resultado): cada carga volvía a leer la descripción entera de cada asignación
# para el idioma, el inglés, los años, el salario y las familias (`vacante.reetiquetar`, 58 % del procesador) y para
# las funciones del cargo (`contenido.evidencia`, 25 %). Las dos son funciones puras del título, la descripción y el
# cargo (más el mapa de cargos y los archivos de `datos/`, fijos mientras corre el servidor): se recuerdan en una
# memoria acotada del proceso. La clave lleva una huella de la descripción (no el texto) para ocupar poco. Solo se
# usa con el mapa de cargos de siempre: con otro (`familias.configurar`, que solo hace la búsqueda) se calcula.
MAX_REETIQUETADAS = 4096
MAX_EVIDENCIAS = 4096


class _Memoria:
    """Memoria LRU con tope de entradas, segura entre hilos (el panel atiende varias peticiones a la vez)."""

    def __init__(self, maximo):
        self.maximo, self._datos, self._cerrojo = maximo, OrderedDict(), threading.Lock()

    def obtener(self, clave, calcular):
        with self._cerrojo:
            if clave in self._datos:
                self._datos.move_to_end(clave)
                return self._datos[clave]
        valor = calcular()  # fuera del cerrojo: dos hilos pueden calcular lo mismo, el resultado es idéntico
        with self._cerrojo:
            self._datos[clave] = valor
            self._datos.move_to_end(clave)
            while len(self._datos) > self.maximo:
                self._datos.popitem(last=False)
        return valor

    def __len__(self):
        return len(self._datos)

    def vaciar(self):
        with self._cerrojo:
            self._datos.clear()


_REETIQUETADAS = _Memoria(MAX_REETIQUETADAS)
_EVIDENCIAS = _Memoria(MAX_EVIDENCIAS)


def _huella(texto):
    return hashlib.blake2b(texto.encode("utf-8", "surrogatepass"), digest_size=16).digest()


def _reetiquetar_publicada(base):
    """Lo mismo que `vacante.reetiquetar(base, publicada=True)`. Con `publicada=True` solo lee el título y la
    descripción y solo escribe las etiquetas que salen de ellos, así que se recuerdan esas etiquetas y se ponen sobre
    `base` (cada llamada recibe sus propias copias: nada de la memoria se comparte con quien las usa)."""
    if "titulo" not in base:
        return vacante.reetiquetar(base, publicada=True)  # mismo error de siempre
    titulo, descripcion = base["titulo"], base.get("_descripcion", "")
    if not isinstance(titulo, str) or not isinstance(descripcion, str) or not _mapa_de_siempre():
        return vacante.reetiquetar(base, publicada=True)

    def calcular():
        sola = vacante.reetiquetar({"titulo": titulo, "_descripcion": descripcion}, publicada=True)
        return {k: x for k, x in sola.items() if k not in ("titulo", "_descripcion")}
    etiquetas = _REETIQUETADAS.obtener((titulo, _huella(descripcion)), calcular)
    base.update(deepcopy(etiquetas))
    return base


def _mapa_de_siempre():
    return familias.mapa() is familias.mapa_base()


def _avisos_de_funciones(titulo, descripcion, cargo, clave_cargo):
    """`contenido.avisos(contenido.evidencia(…))`, recordado por (título, descripción, cargo). `clave_cargo` es la copia
    del cargo de la asignación en JSON: `cargo` sale de ella con `cargo_operativo`, que también es pura."""
    from panel import contenido

    def calcular():
        return tuple(contenido.avisos(contenido.evidencia(titulo, descripcion, cargo)))
    if not isinstance(titulo, str) or not isinstance(descripcion, (str, type(None))) or not _mapa_de_siempre():
        return list(calcular())
    return list(_EVIDENCIAS.obtener((titulo, _huella(descripcion or ""), descripcion is None, clave_cargo), calcular))


def resultados(repo, cliente_id=None, fecha=None):
    # P-12.10: dentro de una carga la misma descripción se normaliza varias veces (idioma, inglés, años, funciones); la
    # memoria de P-12.2 vale mientras dura la carga y se vacía al terminar.
    with normalizar.con_memoria():
        return _calcular_resultados(repo, cliente_id, fecha)


def _calcular_resultados(repo, cliente_id, fecha):
    from panel import contenido
    r = repo.resultados(cliente_id, fecha)
    salida, vistas = [], {}
    operativos = {}  # el cargo de cada asignación, rellenado una sola vez (contrato v49)
    # Una búsqueda de un día anterior ya se entregó: sus enlaces dejan de recomprobarse y caducan a las 6 h (contrato
    # v9). Sus vacantes compatibles se muestran «Entregada el …», no «por confirmar» (13 nov).
    dia = ((r.get("ejecucion") or {}).get("fecha") or "")[:10]
    pasada = _es_dia_anterior(r)
    vigentes = _ConfiguracionVigente(repo, r)
    for row in r["filas"]:
        v = row.get("catalogo_vacantes") or {}
        datos = v.get("datos") or {}
        # Los datos públicos no traen las observaciones de ubicación ni el origen de la fecha: conservar lo que calculó
        # la bodega en vez de rehacerlo con menos evidencia.
        actual = _reetiquetar_publicada(dict(datos, _descripcion=v.get("description_full") or datos.get("_descripcion", "")))
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
        # Contrato v49: el cargo operativo (con los nombres sugeridos y la huella heredada), también para asignaciones
        # anteriores: antes una vacante que entró por un nombre sugerido quedaba «no corresponde al cargo».
        clave_cargo = json.dumps(row["cargo_configuracion"], sort_keys=True, ensure_ascii=False, default=str)
        if clave_cargo not in operativos:
            operativos[clave_cargo] = contenido.cargo_operativo(row["cargo_configuracion"])
        cargo = operativos[clave_cargo]
        # Aprobada por el operador en «Por confirmar» (v25/v49): el título ya se decidió a mano. La marca es
        # `{"aprobada_por": …}`; las asignaciones anteriores a v49 traen `{"funciones": True}`.
        aprobada = any(isinstance(e, dict) and (e.get("aprobada_por") or e.get("funciones") is True)
                       for e in row.get("explicacion") or [])
        # 7.H: la misma regla que usa la Bodega para «ya no encaja» (perfil + título del cargo, con cercanos; v27).
        filtros = encaja_asignada(actual, row["filtros"], cargo, hoy(), ampliacion, aprobada)
        no_encaja = ""
        if filtros["compatible"] and not pasada:
            no_encaja = vigentes.motivo(row, actual, ampliacion, aprobada)
            if no_encaja:
                filtros["compatible"] = False
                filtros["motivos"].append(no_encaja)
        if not aprobada and actual.get("tipo") != "post":  # un post no trae funciones que comparar
            filtros["avisos"] = [*filtros.get("avisos", []), *_avisos_de_funciones(
                actual["titulo"], actual.get("_descripcion"), cargo, clave_cargo)]
        es_post = actual.get("tipo") == "post"  # contrato v11: post de LinkedIn sin ficha formal, con su etiqueta
        no_apta = contrato.entregable_post(actual) if es_post else contrato.entregable(actual, panel=True)
        enlace = enlace_utilizable(row) if filtros["compatible"] and not no_apta else ""
        clave = row["vacante_id"]
        if clave in vistas and (vistas[clave]["estado"] == "lista" or not enlace):
            continue
        lugar, lugar_portal = paises.ubicacion_a_mostrar(datos.get("ubicacion"))  # P-7.F: el cliente ve la corregida
        ficha = {"id": clave, "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": lugar, "ubicacion_portal": lugar_portal, "modalidad": datos.get("modalidad", ""),
            "idioma": datos.get("idioma", ""), "publicada": datos.get("fecha_publicacion", ""),
            "experiencia": datos.get("anos_min"), "match_grade": row["match_grade"],
            "explicacion": row["explicacion"], "cargo_id": row["cargo_id"], "enlace": enlace,
            "enlace_directo": datos.get("enlace_directo", ""),
            "cargo_nombre": (row.get("cargo_configuracion") or {}).get("nombre", ""),
            "estado": "lista" if enlace else "retirada" if v.get("status") != "active" else
                      "no_encaja" if no_encaja else
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
    por_id = numeros(repo, [v["id"] for v in salida])
    for v in salida:
        v["numero"] = por_id.get(v["id"])
    salida.sort(key=calidad)  # estable: a igualdad se conserva el orden en que se asignaron
    # Contrato v48: de un día anterior también se pueden copiar las ya entregadas (se comprueban al copiar).
    return {**{k: r[k] for k in ("ejecucion", "clientes")}, "vacantes": salida,
            "listas": sum(v["estado"] == "lista" for v in salida), "dia_anterior": pasada,
            "para_copiar": sum(v["estado"] in copiables(pasada) for v in salida)}


def copiables(dia_anterior):
    """Contrato v48: los estados que entran en «Copiar WhatsApp»: de hoy, las listas; de un día anterior, también las
    ya entregadas que siguen siendo compatibles (nunca las retiradas ni las por confirmar)."""
    return ("lista", "entregada") if dia_anterior else ("lista",)


def _es_dia_anterior(r):
    dia = ((r.get("ejecucion") or {}).get("fecha") or "")[:10]
    return bool(dia) and dia < hoy()



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
    lugar, lugar_portal = paises.ubicacion_a_mostrar(datos.get("ubicacion"))  # P-7.F
    return {"id": vacante_id, "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": lugar, "ubicacion_portal": lugar_portal, "modalidad": datos.get("modalidad", ""),
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


# ── Contrato v45: qué hará «Buscar ahora» ────────────────────────────────────────────────────────────────────────
PLAN_COMPLETO = {"tipo": "completa", "faltan": [],
                 "motivo": "Hoy todavía no hay una búsqueda terminada: se hará la búsqueda completa del día.",
                 "detalle": "Empieza en unos minutos y tarda alrededor de una hora y media. Puedes cerrar el panel: "
                            "sigue sola."}


def plan_busqueda(repo, fecha=None, ejecuciones=None, cliente_id=None):
    """Un solo botón, tres casos: hoy no hay búsqueda que haya armado su lote (o falló) → la completa del día; ya corrió
    y hay perfiles que no llegan a su meta y pueden recibir más → solo para ellos, corta y sin repetir («faltantes», v47); si no →
    nada. Solo nombres de clientes del panel privado. Nunca falla: sin datos, la completa.
    Con `cliente_id` (contrato v49), el plan de ese cliente: ver `plan_cliente`."""
    from panel.ejecutor import faltan_hoy, validar_version
    fecha = fecha or hoy()
    if cliente_id:
        return plan_cliente(repo, str(cliente_id), fecha, ejecuciones)
    try:
        version = repo.operativa(fecha)
        if not version:
            return {**PLAN_COMPLETO, "motivo": "Aún no hay configuración confirmada: se hará la búsqueda de siempre."}
        avance = faltan_hoy(repo, version, fecha, ejecuciones)
        if avance is None:
            return dict(PLAN_COMPLETO)
        cfg = validar_version(version)
    except Exception as e:  # noqa: BLE001 — sin el dato, el botón hace la búsqueda completa de siempre
        registro.aviso("servicio:plan_busqueda", e)
        return dict(PLAN_COMPLETO)
    clientes = {str(c.id): c.nombre for c in cfg.clientes}
    cargos = {str(c.id): c.nombre for c in cfg.cargos}
    faltan = sorted(({"perfil_id": str(p.id), "cliente": clientes.get(str(p.cliente_id), ""),
                      "cargo": cargos.get(str(p.cargo_id), ""), "hoy": n, "meta": meta} for p, n, meta in avance),
                    key=lambda f: (f["hoy"] / max(1, f["meta"]), f["cliente"]))
    if not faltan:
        return {"tipo": "nada", "faltan": [],
                "motivo": "Hoy todos llegaron a su meta o ya recibieron todo lo que cabe en el día: no hace falta "
                          "buscar más."}
    return {"tipo": "faltantes", "faltan": faltan,
            "motivo": f"La búsqueda de hoy ya corrió y {len(faltan)} "
                      f"{'perfil no llega' if len(faltan) == 1 else 'perfiles no llegan'} a su meta: se buscará solo "
                      "para ellos, en sus cargos y lugares, sin repetir lo que ya se buscó hoy.",
            "detalle": "Primero les reparte lo que ya hay guardado y luego busca nombres y páginas nuevas. Tarda unos 30 "
                       "minutos; puedes cerrar el panel."}


def plan_cliente(repo, cliente_id, fecha=None, ejecuciones=None):
    """Contrato v49: «Buscar ahora» desde el detalle de un cliente. Lee la configuración EN USO (la aplicada), no la que
    se está editando. Tres casos: hoy aún no hay lote → la completa del día, con los perfiles del cliente primero; ya hay
    lote → `pedido`: solo los perfiles activos del cliente que no llegan a su meta (uno nuevo cuenta 0); todos en su
    meta → nada. `perfiles` son los ids que el servidor guarda para la búsqueda (nunca van al flujo de GitHub).
    Un cliente que no está activo en la configuración en uso es un error 409 que dice qué hacer."""
    from panel.ejecutor import LOTE_ARMADO, validar_version
    fecha = fecha or hoy()
    version = repo.operativa(fecha)
    cfg = validar_version(version) if version else None
    cliente = next((c for c in cfg.clientes if str(c.id) == cliente_id), None) if cfg else None
    if not cliente or not cliente.activo:
        raise ErrorRepositorio("Este cliente todavía no está en la configuración en uso. Pulsa «Aplicar cambios» y "
                               "vuelve a intentarlo.", 409)
    perfiles = [p for p in cfg.perfiles_activos() if str(p.cliente_id) == cliente_id]
    if not perfiles:
        raise ErrorRepositorio(f"{cliente.nombre} no tiene perfiles activos con meta en la configuración en uso: "
                               "activa o añade un perfil y pulsa «Aplicar cambios».", 409)
    filas = ejecuciones if ejecuciones is not None else (repo.ejecuciones() or [])
    de_hoy = [e for e in filas if str(e.get("fecha", "")) == fecha]
    if (not de_hoy or de_hoy[0].get("estado") not in LOTE_ARMADO
            or (de_hoy[0].get("resumen") or {}).get("revision_del_lote") is None):
        return {**PLAN_COMPLETO, "cliente": cliente.nombre, "perfiles": [str(p.id) for p in perfiles],
                "motivo": "Hoy todavía no hay una búsqueda terminada: se hará la búsqueda completa del día, con los "
                          f"perfiles de {cliente.nombre} primero."}
    eid = str(de_hoy[0]["id"])
    conteo = repo.asignaciones_por_perfil([eid])
    cargos = {str(c.id): c.nombre for c in cfg.cargos}
    faltan = [{"perfil_id": str(p.id), "cliente": cliente.nombre, "cargo": cargos.get(str(p.cargo_id), ""),
               "hoy": conteo.get((eid, str(p.id)), 0), "meta": int(p.meta_diaria or 0)} for p in perfiles]
    faltan = sorted((f for f in faltan if f["hoy"] < f["meta"]), key=lambda f: (f["hoy"] / max(1, f["meta"]), f["cargo"]))
    if not faltan:
        return {"tipo": "nada", "faltan": [], "cliente": cliente.nombre, "perfiles": [],
                "motivo": f"Hoy {cliente.nombre} ya llegó a su meta en todos sus perfiles: no hace falta buscar más."}
    uno = len(faltan) == 1
    return {"tipo": "pedido", "faltan": faltan, "cliente": cliente.nombre, "perfiles": [f["perfil_id"] for f in faltan],
            "motivo": f"La búsqueda de hoy ya corrió y {len(faltan)} {'perfil' if uno else 'perfiles'} de "
                      f"{cliente.nombre} no {'llega' if uno else 'llegan'} a su meta: se buscará solo para "
                      f"{'ese perfil' if uno else 'esos perfiles'}, en sus cargos y lugares, sin repetir lo que ya se "
                      "buscó hoy.",
            "detalle": "Primero le reparte lo que ya hay guardado y luego busca nombres y páginas nuevas. Tarda unos 30 "
                       "minutos; puedes cerrar el panel."}


# ── Contrato v44: «Qué hacer» por persona, con cifras ──────────────────────────────────────────────────────────────
def _ampliaciones_del_cargo(cargo, raw, base):
    """Contrato v44: por cargo (una vez, no por persona), las listas de nombres que se podrían añadir y las vacantes que
    sumarían: los nombres en español sugeridos y el oficio general. Solo sugerencias."""
    propios = {titulo_base(x) for x in [cargo.nombre, *raw["terminos_exactos"], *raw["terminos_similares"]]}
    sug = sugerir(cargo.nombre, consultar_esco=False, definicion=raw)  # v50: sin los nombres que ya usa solos
    salida = []
    for clave, accion, terminos in (("nombres_es", "Añadir al cargo estos nombres en español", sug.get("terminos_es") or []),
                                     ("oficio_base", "Aceptar también el oficio general", sug.get("terminos_base") or [])):
        extra = [x for x in terminos if titulo_base(x) not in propios]
        if extra:
            ampliado = dict(raw, terminos_similares=[*raw["terminos_similares"], *extra])
            salida.append((clave, accion, extra, _del_cargo(base, ampliado)))
    return salida


def _con_presencial(p):
    """El mismo perfil aceptando también híbrido y presencial donde vive (su primera fila), o None si ya los acepta."""
    filas = p.filas
    if not filas or {"hibrido", "presencial"} & set(filas[0].modalidades):
        return None
    datos = p.model_dump(mode="json")
    primera = filas[0].model_dump(mode="json")
    datos["ubicaciones"] = [dict(primera, modalidades=sorted(set(primera["modalidades"]) | {"hibrido", "presencial"})),
                            *[f.model_dump(mode="json") for f in filas[1:]]]
    try:
        return Perfil.model_validate(datos), primera
    except ValueError:
        return None


def que_hacer(p, ampliaciones, del_cargo, compatibles, ya, fecha, nombres_pais, recibidas_dias):
    """Contrato v44: para una persona bajo su meta, cuántas vacantes más del catálogo le servirían con cada ajuste. Solo
    los que suman algo; nada se aplica solo. `compatibles`: ids que ya le sirven (calculados en `cobertura`);
    `recibidas_dias`: lo que recibió en cada uno de sus últimos días medidos."""
    def nuevas(vacantes, perfil):
        return sum(1 for v in vacantes if v["id"] not in ya and v["id"] not in compatibles
                   and evaluar(v, perfil, fecha)["compatible"])

    salida = []
    for clave, accion, extra, vacantes in ampliaciones:
        mas = nuevas(vacantes, p)
        if mas:
            salida.append({"clave": clave, "accion": accion, "mas": mas,
                           "detalle": ", ".join(extra[:4]) + ("…" if len(extra) > 4 else "")})
    ampliado = _con_presencial(p)
    if ampliado:
        perfil, primera = ampliado
        mas = nuevas(del_cargo, perfil)
        lugar = ", ".join(primera.get("ciudades") or []) or ", ".join(
            nombres_pais.get(x, x) for x in primera.get("paises") or [p.vive_en])
        if mas:
            salida.append({"clave": "modalidad", "accion": f"Aceptar híbrido o presencial en {lugar}",
                           "detalle": "Hoy solo acepta remoto donde vive.", "mas": mas})
    salida.sort(key=lambda x: -x["mas"])
    # Meta realista: con lo que de verdad recibió en sus últimos días (al menos 3 medidos), nunca por debajo de 5.
    meta = int(p.meta_diaria or 0)
    if len(recibidas_dias) >= 3 and meta > MINIMO_POR_PERFIL:
        promedio = sum(recibidas_dias) / len(recibidas_dias)
        sugerida = max(MINIMO_POR_PERFIL, int(promedio + 0.5))
        if sugerida < meta and max(recibidas_dias) < meta:
            salida.append({"clave": "meta", "accion": f"Bajar su meta diaria de {meta} a {sugerida}", "mas": 0,
                           "detalle": f"En sus últimos {len(recibidas_dias)} días recibió en promedio {promedio:.1f} "
                                      "y ninguno llegó a la meta."})
    return salida


# ── Contrato v37: cobertura por persona ──────────────────────────────────────────────────────────────────────────────
DIAS_COBERTURA = 14
DIAS_PARA_MEDIR = 3  # con menos búsquedas medidas, «aún sin datos»

# 8.1b: código estable de la causa de `cobertura()` (la lógica decide con él; el texto es solo para el operador y puede
# cambiar). Vacío cuando no hay causa (llegó al mínimo).
CAUSA_SIN_VACANTES_CARGO = "sin_vacantes_cargo"    # el cargo no tiene vacantes en nada de lo buscado
CAUSA_LISTAS_SIN_RECIBIR = "listas_sin_recibir"    # hay vacantes listas que aún no recibió
CAUSA_AJUSTE_PERFIL = "ajuste_perfil"              # las del cargo no le sirven por un rasgo de su perfil
CAUSA_OTRO_PAIS = "otro_pais"                      # las del cargo no le sirven por «oficina en otro país»
CAUSA_POR_COMPROBAR = "por_comprobar"              # le servirían, pero falta comprobar el enlace
CAUSA_POCAS_EN_FUENTES = "pocas_en_fuentes"        # pocas vacantes nuevas en las fuentes revisadas


def cobertura(repo, fecha=None):
    """Por cada perfil activo: si hoy llegó al umbral de aviso (`AVISO_BAJO`, `cobertura.aviso_bajo` = 10, la meta;
    P-11.3), cuántos de sus últimos días lo logró (con su denominador), cuántas
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
    nombres = {x["codigo"]: x["nombre"] for x in paises.mundo()["lista"]}
    ampliaciones = {}  # por cargo: se calculan una vez
    filas = []
    for cargo, p in perfiles:
        pid = str(p.id)
        dias = [e for e in ejecuciones if pid in presentes.get(e.get("revision"), set())]
        con_minimo = sum(1 for e in dias if conteo.get((str(e["id"]), pid), 0) >= AVISO_BAJO)
        hoy_n = conteo.get((str(ejecuciones[0]["id"]), pid), 0) if ejecuciones else 0
        raw = cargo.model_dump(mode="json")
        if not raw["terminos_exactos"]:
            raw["terminos_exactos"] = sugerir(cargo.nombre, consultar_esco=False)["terminos_exactos"]
        base = {"actualizado": catalogo["actualizado"] + "#todas", "vacantes": todas}
        del_cargo = _del_cargo(base, raw) + _del_cargo(base, raw, cercanas=True)
        ya = recibidas.get(pid, set())
        listas = pendientes = 0
        motivos = Counter()
        compatibles = set()
        for v in del_cargo:
            if v["id"] in ya:
                continue
            r = evaluar(v, p, fecha)
            if not r["compatible"]:
                if len(r["motivos"]) == 1:
                    motivos[r["motivos"][0]] += 1
                continue
            compatibles.add(v["id"])
            if v.get("_verificacion") == "verificada":
                listas += 1
            else:
                pendientes += 1
        if hoy_n >= AVISO_BAJO:
            estado = "cubierto"
        elif len(dias) < DIAS_PARA_MEDIR:
            estado = "sin_datos"
        else:
            estado = "pendiente"
        causa = codigo = ""
        from panel.ejecutor import fuentes_locales, lugares_perfil, paises_de_lugares
        # 8.1b: «Cobertura limitada» con la misma definición de fuente local que la tabla de huecos (Indeed cuenta).
        pocas_fuentes = not any(fuentes_locales(c) for c in (paises_de_lugares(lugares_perfil(p)) or [p.vive_en]))
        if estado != "cubierto" and hoy_n < AVISO_BAJO:
            if not del_cargo:
                codigo = CAUSA_SIN_VACANTES_CARGO
                causa = "Aún no hay vacantes de este cargo en lo buscado: la próxima búsqueda lo incluye."
            elif listas:
                codigo = CAUSA_LISTAS_SIN_RECIBIR
                causa = (f"Hay {listas} {'lista' if listas == 1 else 'listas'} que aún no recibió: la próxima búsqueda "
                         "completa su mínimo con ellas.")
            elif listas + pendientes == 0 and motivos:
                m, n = motivos.most_common(1)[0]
                codigo = CAUSA_OTRO_PAIS if m == MOTIVO_OTRO_PAIS else CAUSA_AJUSTE_PERFIL
                causa = f"{n} vacantes del cargo no le sirven por «{m}»" + (
                    f": {SUGERENCIAS[m].lower()} daría más." if m in SUGERENCIAS else ".")
            elif pendientes:
                codigo = CAUSA_POR_COMPROBAR
                causa = f"{pendientes} le servirían pero aún no tienen el enlace comprobado; se comprueban en la próxima búsqueda."
            else:
                codigo = CAUSA_POCAS_EN_FUENTES
                causa = "Pocas vacantes nuevas en las fuentes revisadas para su ubicación e idioma."
            if pocas_fuentes and not listas:
                from panel.ejecutor import fuentes_en
                causa += (f" Cobertura limitada donde vive: se busca con {', '.join(fuentes_en(p.vive_en))}; recibe sobre "
                          "todo remotas abiertas a su país. Tiene el doble de turnos en la búsqueda.")
        seguidos = 0
        for e in dias:
            if conteo.get((str(e["id"]), pid), 0) >= AVISO_BAJO:
                break
            seguidos += 1
        # Contrato v44: qué hacer, con cifras, para quien no llega a su meta.
        ajustes = []
        if hoy_n < max(MINIMO_POR_PERFIL, int(p.meta_diaria or 0)):
            if cargo.id not in ampliaciones:
                ampliaciones[cargo.id] = _ampliaciones_del_cargo(cargo, raw, base)
            ajustes = que_hacer(p, ampliaciones[cargo.id], del_cargo, compatibles, ya, fecha, nombres,
                                [conteo.get((str(e["id"]), pid), 0) for e in dias])
        filas.append({"perfil_id": pid, "cliente_id": str(p.cliente_id), "cliente": clientes[p.cliente_id].nombre,
                      "que_hacer": ajustes,
                      "cargo": cargo.nombre, "vive_en": p.vive_en, "idiomas": list(p.idiomas), "estado": estado,
                      "hoy": hoy_n, "dias_con_minimo": con_minimo, "dias_medidos": len(dias),
                      "dias_seguidos_bajo": seguidos if len(dias) >= DIAS_PARA_MEDIR else 0,
                      "listas": listas, "por_comprobar": pendientes, "causa": causa, "causa_codigo": codigo,
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
                       f"seguidos con menos de {AVISO_BAJO}: revisa su cargo y su ubicación.")
    return {"fecha": fecha, "minimo": AVISO_BAJO, "dias_ventana": DIAS_COBERTURA, "perfiles": filas,
            "grupos": {"cargo": agrupar("cargo"), "pais": agrupar("vive_en"), "idioma": agrupar("idiomas")},
            "alertas": alertas,
            "nota": "Cuenta solo lo medido en las búsquedas de cada día. «Listas» son vacantes guardadas, con enlace "
                    "comprobado, que esa persona nunca recibió; no es una promesa para los próximos días."}


SEGUNDOS_DIA_ANTERIOR = 30  # contrato v48: tope para comprobar al momento los enlaces de un día anterior


def whatsapp(repo, cliente_id, fecha=None, resultados=None, contactos=None, cuantas=10, comprobar=None,
             segundos=SEGUNDOS_DIA_ANTERIOR):
    """El mensaje para copiar. El servidor pasa los `resultados` y `contactos` que ya tiene en memoria (18 nov).
    Contrato v43 (regla 7): el operador elige `cuantas` (10 por defecto, como el borrador diario), con 2 por empresa;
    las que quedan fuera van en «Tengo N más…». Con más de 10, el texto se entrega también en `partes` de 10.
    Contrato v48: de un día anterior entran también las ya entregadas; las que no tienen el enlace comprobado en 24 h se
    comprueban al momento (`comprobar`, con tope de `segundos`) y las cerradas o sin comprobar se quitan."""
    r = resultados if resultados is not None else globals()["resultados"](repo, cliente_id, fecha)
    from panel import borradores
    anterior = _es_dia_anterior(r)
    dia = ((r.get("ejecucion") or {}).get("fecha") or "")[:10]
    candidatas = [v for v in r["vacantes"] if v["estado"] in copiables(anterior)]
    quitadas = {"cerradas": 0, "sin_comprobar": 0}
    if anterior:
        candidatas, quitadas = _comprobar_anteriores(repo, candidatas, cuantas, comprobar, segundos)
    elegidas, empresas, sobran = [], {}, 0
    for v in candidatas:
        empresa = borradores._empresa(v)
        if len(elegidas) < cuantas and (borradores.es_post(v) or empresas.get(empresa, 0) < borradores.POR_EMPRESA):
            empresas[empresa] = empresas.get(empresa, 0) + 1
            elegidas.append(v)
        else:
            sobran += 1
    listas = borradores.con_posts(elegidas, maximo=cuantas)
    sobran += len(elegidas) - len(listas)
    nota = _nota_dia_anterior(quitadas) if anterior else ""
    if not listas:
        nota = ("Ninguna vacante de ese día sigue con el enlace abierto y comprobado." if anterior else
                "No hay vacantes con filtros y enlace vigentes para copiar.")
        return {"texto": "", "partes": [], "vacantes": 0, "nota": nota}
    # Misma plantilla humana que los borradores diarios (contrato v10): cargo y lista, sin enumerar filtros.
    grupos = {}
    for v in listas:
        grupos.setdefault(v.get("cargo_nombre") or "tu perfil", []).append(v)
    if contactos is None:
        contactos = repo.contactos() if hasattr(repo, "contactos") else []
    contacto = next((c for c in contactos
                     if c.get("cliente_id") == cliente_id), {})
    nombre = contacto.get("nombre_saludo", "")
    texto = borradores.texto(nombre, list(grupos.items()), dia or hoy(), str(cliente_id or ""), mas=sobran,
                             todas_de_hoy=not anterior)
    return {"texto": texto, "partes": partir_mensaje(texto), "vacantes": len(listas), "sobran": sobran, "nota": nota}


def _nota_dia_anterior(quitadas):
    nota = "Son de un día anterior: sus enlaces se comprobaron ahora."
    if quitadas["cerradas"]:
        nota += f" Se quitaron {quitadas['cerradas']} que ya cerraron."
    if quitadas["sin_comprobar"]:
        nota += f" {quitadas['sin_comprobar']} no se pudieron comprobar y no van."
    return nota


VENTANA_DIA_ANTERIOR = 60  # contrato v48: como mucho tantas ya entregadas se comprueban al copiar


def _comprobar_anteriores(repo, candidatas, cuantas, comprobar, segundos):
    """Contrato v48: de un día anterior, las «entregada» (sin comprobación de 24 h; si la tuvieran ya serían «lista»)
    se comprueban ahora, en orden y solo las que podrían entrar (`cuantas`·2 + 5, por los 2 por empresa). Nunca se
    manda un enlace cerrado ni uno sin comprobar. Sin `comprobar` (demostración) se toman como vienen.
    Devuelve (candidatas utilizables, {"cerradas", "sin_comprobar"})."""
    quitadas = {"cerradas": 0, "sin_comprobar": 0}
    if comprobar is None:
        return candidatas, quitadas
    from buscador import verificar_enlaces
    ventana = [v for v in candidatas if v["estado"] == "entregada"][:min(VENTANA_DIA_ANTERIOR, cuantas * 2 + 5)]
    # Copias propias: `candidatas` son la copia en memoria de los resultados y no se tocan.
    revisar = [{"id": v["id"], "titulo": v["titulo"], "enlace": v.get("enlace", ""),
                "enlace_directo": v.get("enlace_directo", "")} for v in ventana]
    cache = {}
    if revisar:
        verificar_enlaces.auditar(revisar, cache, maximo=len(revisar), segundos=segundos, comprobar_url=comprobar)
    resultado = {w["id"]: verificar_enlaces.anotar(w, cache) for w in revisar}
    for vid, ver in resultado.items():
        if ver["estado"] == "verificada":
            _guardar_comprobacion(repo, vid, ver)
    salida = []
    for v in candidatas:
        ver = resultado.get(v["id"])
        if ver is None:
            if v["estado"] == "lista":
                salida.append(v)
        elif ver["estado"] == "verificada":
            salida.append(dict(v, enlace=ver.get("url_utilizable") or v["enlace"]))
        else:
            quitadas["cerradas" if ver["estado"] == "rechazada" else "sin_comprobar"] += 1
    return salida, quitadas


def _guardar_comprobacion(repo, vacante_id, verificacion):
    """Que la próxima vez ya cuente como comprobada (como al confirmar en «Por confirmar»)."""
    try:
        fila = repo.vacante(vacante_id) or {}
        if fila.get("datos"):
            repo.actualizar_catalogo_datos(vacante_id, dict(fila["datos"], verificacion=verificacion))
    except ErrorRepositorio as e:
        registro.aviso("servicio:whatsapp-anterior", e)


def partir_mensaje(texto, por_parte=10):
    """Parte el mensaje en trozos de hasta `por_parte` vacantes, sin cortar ninguna: el saludo va con la primera y el
    cierre con la última. La numeración sigue de una parte a la otra. Con varios cargos (`*Cargo*`), el título nunca
    queda suelto al final de una parte y se repite al empezar la siguiente (revisión Thermos del 18 nov)."""
    partes, actual, n, titulo = [], [], 0, ""
    for parrafo in texto.split("\n\n"):
        es_vacante = bool(re.match(r"^\d+\. ", parrafo))
        es_titulo = bool(re.fullmatch(r"\*[^*\n]+\*", parrafo))
        if es_vacante and n == por_parte:
            arrastre = []
            if actual and re.fullmatch(r"\*[^*\n]+\*", actual[-1]):
                arrastre = [actual.pop()]
            elif titulo:
                arrastre = [titulo]
            partes.append("\n\n".join(actual))
            actual, n = arrastre, 0
        if es_titulo:
            titulo = parrafo
        actual.append(parrafo)
        n += es_vacante
    partes.append("\n\n".join(actual))
    return partes


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
