"""P-14.2 (IA acotada, decisión de Oscar del 28 nov): términos de búsqueda ampliados por un LLM, por CARGO.

- `actualizar(repo, cfg)`: en la búsqueda del día, pide al LLM los términos de cada cargo activo que es nuevo o cambió
  (huella de `terminos.huella_ampliados`) y los guarda en `panel_ajustes.terminos_ampliados`
  ({cargo_id: {huella, es, en, fecha, modelo}}). Lo ya pedido no se vuelve a pedir. Un fallo guarda la huella con
  `fallo` y se reintenta al día siguiente. Con el interruptor apagado o sin proveedor no hace nada.
- `leer(repo, cargos)`: los ampliados que siguen valiendo para el cargo vigente (misma huella, filtrados con
  `terminos.filtrar_ampliados`). Entran al cargo operativo en `terminos_ampliados` (`contenido.cargo_operativo`): se
  buscan y `grado` los reconoce solo si el título los CONTIENE (como los nombres hermanos, sin similitud textual: un
  término nuevo no debe atraer por parecido títulos de otro oficio). Lo usan la búsqueda, el lote y el panel, para que
  todos vean el mismo cargo (si el panel no los viera, retiraría como «ya no encaja» lo que entró por ellos).

Interruptor: `llm.terminos_activo` en `datos/config.yaml` (apagado por defecto). Apagado, nadie usa los términos
guardados: todo queda como antes. En el registro solo salen cifras (nunca cargos ni términos: el repo es público).
"""
from datetime import datetime, timezone

from buscador import registro

CLAVE = "terminos_ampliados"
HORAS_REINTENTO = 20  # un fallo se reintenta en la búsqueda del día siguiente, no en cada pasada


def activo(cfg=None):
    from buscador import llm
    return llm.opciones(cfg).get("terminos_activo") is True


def _cargo(c):
    return c.model_dump(mode="json") if hasattr(c, "model_dump") else dict(c)


def _vencido(entrada, ahora):
    try:
        return (ahora - datetime.fromisoformat(entrada["fecha"])).total_seconds() >= HORAS_REINTENTO * 3600
    except (KeyError, TypeError, ValueError):
        return True


def pendientes(cargos, guardados, ahora=None):
    """Los cargos activos sin términos para su huella actual (o con un fallo viejo), en orden estable."""
    from panel.terminos import huella_ampliados
    ahora = ahora or datetime.now(timezone.utc)
    salida = []
    for c in cargos:
        if not c.get("activo", True) or not (c.get("nombre") or "").strip():
            continue
        e = guardados.get(str(c.get("id"))) or {}
        if e.get("huella") != huella_ampliados(c) or (e.get("fallo") and _vencido(e, ahora)):
            salida.append(c)
    return salida


def actualizar(repo, cfg, cliente=None, ahora=None, opciones=None):
    """Pide los términos que faltan, hasta el tope de llamadas. Devuelve cifras: {pedidos, nuevos, fallidos,
    pendientes}. Nunca lanza: sin LLM, la búsqueda sigue con lo guardado."""
    from buscador import llm
    from panel.terminos import ESQUEMA_AMPLIADOS, SISTEMA_AMPLIADOS, huella_ampliados, prompt_ampliados
    cifras = {"pedidos": 0, "nuevos": 0, "fallidos": 0, "pendientes": 0}
    if not activo(opciones) or not hasattr(repo, "guardar_ajuste"):
        return cifras
    try:
        guardados = dict(repo.ajuste(CLAVE, {}) or {})
        faltan = pendientes([_cargo(c) for c in cfg.cargos], guardados, ahora)
        cifras["pendientes"] = len(faltan)
        cliente = cliente or llm.cliente(opciones)
        if faltan and cliente is None:
            registro.aviso("ampliados:sin-proveedor", RuntimeError("interruptor encendido sin proveedor o sin clave"))
            return cifras
        fecha = (ahora or datetime.now(timezone.utc)).isoformat()
        for c in faltan:
            if cliente.agotado:
                break
            cifras["pedidos"] += 1
            dato = cliente.pedir_json(prompt_ampliados(c), ESQUEMA_AMPLIADOS, SISTEMA_AMPLIADOS)
            entrada = {"huella": huella_ampliados(c), "fecha": fecha, "modelo": cliente.proveedor.modelo}
            if dato is None:
                cifras["fallidos"] += 1
                anterior = guardados.get(str(c["id"])) or {}
                # Si el cargo no cambió (solo se reintenta un fallo), se conservan sus términos: un fallo pasajero no
                # los quita. Si cambió, los anteriores ya no valen.
                igual = anterior.get("huella") == entrada["huella"]
                guardados[str(c["id"])] = {**entrada, "fallo": True, "es": anterior.get("es") or [] if igual else [],
                                           "en": anterior.get("en") or [] if igual else []}
            else:
                cifras["nuevos"] += 1
                guardados[str(c["id"])] = {**entrada, "es": dato["es"], "en": dato["en"]}
        if cifras["pedidos"]:
            vigentes = {str(_cargo(c).get("id")) for c in cfg.cargos}
            repo.guardar_ajuste(CLAVE, {k: v for k, v in guardados.items() if k in vigentes})
    except Exception as e:  # noqa: BLE001 — nunca tumba la búsqueda
        registro.aviso("ampliados:actualizar", e)
    return cifras


def por_cargo(ampliados, cargos):
    """{cargo_id: términos ampliados que siguen valiendo}: los guardados para la huella actual del cargo, filtrados con
    `terminos.filtrar_ampliados` y el cargo vigente. `cargos`: {id: cargo crudo vigente}."""
    from panel.contenido import cargo_operativo
    from panel.terminos import filtrar_ampliados, huella_ampliados
    salida = {}
    for cargo_id, c in (cargos or {}).items() if ampliados else ():
        e = ampliados.get(str(cargo_id)) or {}
        if not (e.get("es") or e.get("en")) or e.get("huella") != huella_ampliados(c):
            continue
        extra = filtrar_ampliados(e, cargo_operativo(c))  # con los excluidos del mapa (`excluir_mapa`)
        if extra:
            salida[str(cargo_id)] = extra
    return salida


def leer(repo, cargos):
    """Los términos ampliados vigentes por cargo si el interruptor está encendido; {} si no (o si no se pueden leer:
    la búsqueda y el panel siguen como antes)."""
    if not activo() or not hasattr(repo, "ajuste"):
        return {}
    try:
        return por_cargo(repo.ajuste(CLAVE, {}) or {}, cargos)
    except Exception as e:  # noqa: BLE001
        registro.aviso("ampliados:leer", e)
        return {}
