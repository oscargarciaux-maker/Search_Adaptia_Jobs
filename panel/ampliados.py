"""P-14.2 (IA acotada, decisión de Oscar del 28 nov): términos de búsqueda ampliados por un LLM, por CARGO.

- `prompt(cargo)`: lo único que se envía al LLM: el nombre del cargo y sus términos exactos y similares (nunca datos de
  personas, ni los aprendidos, ni los excluidos).
- `actualizar(repo, cfg)`: en la búsqueda del día, pide los términos de cada cargo activo nuevo o cambiado (`huella`)
  y los guarda en `panel_ajustes.terminos_ampliados` ({cargo_id: {huella, es, en, fecha, modelo}}). Lo ya pedido no
  se vuelve a pedir. Un fallo guarda la huella con `fallo` y se reintenta al día siguiente.
- `por_cargo(guardados, cargos)`: los que siguen valiendo para el cargo vigente (misma huella, filtrados con
  `terminos.filtrar_ampliados`). Entran al cargo operativo en `terminos_ampliados` (`contenido.cargo_operativo`): se
  buscan y `grado` los reconoce solo si el título los CONTIENE (sin similitud textual: un término nuevo no debe atraer
  por parecido títulos de otro oficio). Los usan la búsqueda, el lote y el panel, para que todos vean el mismo cargo
  (si el panel no los viera, retiraría como «ya no encaja» lo que entró por ellos).
- `preparar(repo, cfg, pedir)`: lo que llama la búsqueda (actualiza si toca y devuelve lo vigente); `leer`, el panel.

Interruptor: `llm.terminos_activo` en `datos/config.yaml` (apagado por defecto). Apagado no se pide nada y nadie usa
lo guardado: todo queda como antes. En el registro solo salen cifras (nunca cargos ni términos: el repo es público).
"""
from datetime import datetime, timezone
import hashlib
import json

from buscador import registro

CLAVE = "terminos_ampliados"
HORAS_REINTENTO = 20  # un fallo se reintenta en la búsqueda del día siguiente, no en cada pasada
VERSION = 1  # cambiarla vuelve a pedir los términos de todos los cargos (cambió el prompt)
SISTEMA = "Eres un experto en títulos de ofertas de empleo. Respondes solo con JSON, sin texto alrededor."


def activo(cfg=None):
    from buscador import llm
    return llm.opciones(cfg).get("terminos_activo") is True


def es_valida(dato):
    """La respuesta esperada: {"es": [texto, …], "en": [texto, …]} y nada más. Cuántos y de qué largo lo decide
    después `terminos.filtrar_ampliados`."""
    return isinstance(dato, dict) and set(dato) == {"es", "en"} \
        and all(isinstance(dato[k], list) and all(isinstance(x, str) for x in dato[k]) for k in ("es", "en"))


def _enviado(cargo):
    """(nombre, términos) que se envían: lo que escribió el operador en exactos y similares, sin repetir el nombre."""
    from panel.terminos import _base
    nombre = " ".join(str(cargo.get("nombre") or "").split())
    propios = [" ".join(x.split()) for k in ("terminos_exactos", "terminos_similares")
               for x in cargo.get(k) or [] if isinstance(x, str)]
    return nombre, [x for x in dict.fromkeys(propios) if x and _base(x) != _base(nombre)][:20]


def huella(cargo):
    """Huella de lo que se envía: si no cambia, no se vuelve a pedir."""
    from panel.terminos import _base
    nombre, propios = _enviado(cargo)
    datos = [VERSION, _base(nombre), sorted(_base(x) for x in propios)]
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def prompt(cargo):
    from panel.terminos import MAX_AMPLIADOS
    nombre, propios = _enviado(cargo)
    ya = "; ".join(propios) if propios else "(ninguno)"
    return (
        f"Cargo: {nombre}\nTérminos que ya usamos: {ya}\n\n"
        "Propón títulos de ofertas de empleo que las empresas publican para ESTE MISMO trabajo con otro nombre: "
        "sinónimos, variantes regionales (España y Latinoamérica) y la forma habitual en inglés. Reglas:\n"
        "- El mismo oficio y las mismas funciones. NO oficios vecinos ni más amplios (para «Diseñador UX» no vale "
        "«Diseñador gráfico» ni «Desarrollador frontend»).\n"
        "- Sin nivel ni seniority (nada de junior, senior, lead), sin empresa, lugar, modalidad ni herramientas.\n"
        "- Cada título con al menos dos palabras, como aparece en un aviso real. Sin repetir los que ya usamos.\n"
        f"- Hasta {MAX_AMPLIADOS} en español y hasta {MAX_AMPLIADOS} en inglés. Si no hay más, devuelve menos.\n"
        'Responde solo con este JSON: {"es": ["…"], "en": ["…"]}')


def _id(c):
    return str(c.id if hasattr(c, "id") else c.get("id"))


def _cargo(c):
    return c.model_dump(mode="json") if hasattr(c, "model_dump") else dict(c)


def _vencido(entrada, ahora):
    try:
        return (ahora - datetime.fromisoformat(entrada["fecha"])).total_seconds() >= HORAS_REINTENTO * 3600
    except (KeyError, TypeError, ValueError):
        return True


def pendientes(cargos, guardados, ahora=None):
    """Los cargos activos sin términos para su huella actual (o con un fallo viejo), en orden estable."""
    ahora = ahora or datetime.now(timezone.utc)
    salida = []
    for c in cargos:
        if not c.get("activo", True) or not (c.get("nombre") or "").strip():
            continue
        e = guardados.get(str(c.get("id"))) or {}
        if e.get("huella") != huella(c) or (e.get("fallo") and _vencido(e, ahora)):
            salida.append(c)
    return salida


def actualizar(repo, cfg, cliente=None, ahora=None, opciones=None):
    """Pide los términos que faltan, hasta el tope de llamadas. Devuelve (cifras, guardados): cifras = {pedidos,
    nuevos, fallidos, pendientes}; guardados = el ajuste tal como queda (o como estaba). Nunca lanza: sin LLM, la
    búsqueda sigue con lo guardado. Con el interruptor apagado no lee ni pide nada."""
    from buscador import llm
    cifras, guardados = {"pedidos": 0, "nuevos": 0, "fallidos": 0, "pendientes": 0}, {}
    if not activo(opciones) or not hasattr(repo, "guardar_ajuste"):
        return cifras, guardados
    try:
        guardados = dict(repo.ajuste(CLAVE, {}) or {})
        # Solo los cargos que se buscan (con algún perfil activo): los demás no gastan el tope.
        buscados = [c for c in cfg.cargos if not hasattr(cfg, "perfiles_activos") or cfg.perfiles_activos(_id(c))]
        faltan = pendientes([_cargo(c) for c in buscados], guardados, ahora)
        cifras["pendientes"] = len(faltan)
        cliente = cliente or llm.cliente(opciones)
        if faltan and cliente is None:
            registro.aviso("ampliados:sin-proveedor", RuntimeError("interruptor encendido sin proveedor o sin clave"))
            return cifras, guardados
        fecha = (ahora or datetime.now(timezone.utc)).isoformat()
        for c in faltan:
            if cliente.agotado:
                break
            cifras["pedidos"] += 1
            dato = cliente.pedir_json(prompt(c), es_valida, SISTEMA)
            entrada = {"huella": huella(c), "fecha": fecha, "modelo": cliente.proveedor.modelo}
            if dato is None:
                cifras["fallidos"] += 1
                # Si el cargo no cambió (solo se reintenta un fallo), sus términos se conservan: un fallo pasajero no
                # los quita. Si cambió, los anteriores ya no valen.
                anterior = guardados.get(str(c["id"])) or {}
                previos = anterior if anterior.get("huella") == entrada["huella"] else {}
                guardados[str(c["id"])] = {**entrada, "fallo": True, "es": previos.get("es") or [],
                                           "en": previos.get("en") or []}
            else:
                cifras["nuevos"] += 1
                guardados[str(c["id"])] = {**entrada, "es": dato["es"], "en": dato["en"]}
        if cifras["pedidos"]:
            vigentes = {str(_cargo(c).get("id")) for c in cfg.cargos}
            guardados = {k: v for k, v in guardados.items() if k in vigentes}
            repo.guardar_ajuste(CLAVE, guardados)
    except Exception as e:  # noqa: BLE001 — nunca tumba la búsqueda
        registro.aviso("ampliados:actualizar", RuntimeError(type(e).__name__))  # solo el tipo: el texto podría traer un cargo
    return cifras, guardados


def por_cargo(guardados, cargos):
    """{cargo_id: términos ampliados que siguen valiendo}: los guardados para la huella actual del cargo, filtrados con
    `terminos.filtrar_ampliados` y el cargo vigente. `cargos`: {id: cargo crudo vigente}."""
    from panel.contenido import cargo_operativo
    from panel.terminos import filtrar_ampliados
    salida = {}
    for cargo_id, c in (cargos or {}).items() if guardados else ():
        e = guardados.get(str(cargo_id)) or {}
        if not (e.get("es") or e.get("en")) or e.get("huella") != huella(c):
            continue
        extra = filtrar_ampliados(e, cargo_operativo(c))  # con los excluidos del mapa (`excluir_mapa`)
        if extra:
            salida[str(cargo_id)] = extra
    return salida


def leer(repo, cargos, opciones=None):
    """Los términos ampliados vigentes por cargo si el interruptor está encendido; {} si no, o si no se pueden leer
    (todo sigue como antes)."""
    if not activo(opciones) or not hasattr(repo, "ajuste"):
        return {}
    try:
        return por_cargo(repo.ajuste(CLAVE, {}) or {}, cargos)
    except Exception as e:  # noqa: BLE001
        registro.aviso("ampliados:leer", RuntimeError(type(e).__name__))  # solo el tipo: el texto podría traer un cargo
        return {}


def preparar(repo, cfg, pedir=True, cliente=None, ahora=None, opciones=None):
    """Para la búsqueda: con `pedir` (la del día, no la captura horaria) pide los que faltan y deja una línea con las
    cifras; devuelve {cargo_id: términos vigentes}. Apagado: {} sin leer nada."""
    if not activo(opciones):
        return {}
    cargos = {str(_cargo(c).get("id")): _cargo(c) for c in cfg.cargos}
    if not pedir:
        return leer(repo, cargos, opciones)
    cifras, guardados = actualizar(repo, cfg, cliente, ahora, opciones)
    from buscador import bodega
    bodega.etapa("Términos ampliados (LLM): {pendientes} cargos sin términos, {pedidos} pedidos, {nuevos} nuevos, "
                 "{fallidos} fallidos".format(**cifras))
    try:
        return por_cargo(guardados, cargos)
    except Exception as e:  # noqa: BLE001
        registro.aviso("ampliados:preparar", RuntimeError(type(e).__name__))  # solo el tipo: el texto podría traer un cargo
        return {}
