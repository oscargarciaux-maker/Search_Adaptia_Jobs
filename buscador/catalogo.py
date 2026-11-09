"""Catálogo persistente independiente de la cuota diaria. No elimina ofertas históricas."""
from datetime import datetime
import hashlib
import json

from buscador import contrato, tiempos, vacante

# Marcas que cambian cada vez que una fuente vuelve a listar la vacante. No alteran filtros, afinidad ni enlaces
# (la comprobación de enlaces vive en `verificacion` y sí cuenta como cambio); se renuevan por rotación.
VOLATILES_FILA = ("observed_at", "last_seen_at")
VOLATILES_DATOS = ("vista_en", "visto_ultima_vez")
ROTACION_HORAS = 6
MAXIMO_SIN_RENOVAR_HORAS = 12


def huella(row):
    """Contenido que importa a consultas y filtros, sin marcas de observación."""
    datos = {k: v for k, v in (row.get("datos") or {}).items() if k not in VOLATILES_DATOS}
    resto = {k: v for k, v in row.items() if k not in VOLATILES_FILA and k != "datos"}
    texto = json.dumps([resto, datos], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode()).hexdigest()[:24]


def _hora(instante):
    return int(datetime.fromisoformat(instante.replace("Z", "+00:00")).timestamp() // 3600)


def hay_que_enviar(row, sincronizado, observado):
    """Enviar contenido nuevo; lo que no cambió se renueva por turnos para no reescribir todo el catálogo cada hora."""
    previo = sincronizado.get(row["id"])
    if not previo or previo[0] != huella(row):
        return True
    try:
        hora, enviada = _hora(observado), _hora(previo[1])
    except (ValueError, TypeError, AttributeError, IndexError):
        return True
    turno = int(row["id"][:8], 16) % ROTACION_HORAS == hora % ROTACION_HORAS
    return (turno and hora > enviada) or hora - enviada >= MAXIMO_SIN_RENOVAR_HORAS


def fila(v, observado, estado="active", razon=""):
    return {"id": v["id"], "contract_version": "v2", "datos": vacante.publica(v),
            "description_full": v.get("_descripcion", "")[:30000],
            "published_at": v.get("publicada_en") or None,
            "first_seen_at": v.get("detectada_en") or None, "last_seen_at": v.get("vista_en") or None,
            "observed_at": observado, "status": estado,
            "closed_at": observado if estado == "closed" else None, "reason": razon or None}


def sincronizar(vacantes, retiradas, pendientes, subir, persistir, observado=None, sincronizado=None):
    """`sincronizado` ({id: [huella, enviada_en]}) recuerda lo confirmado en Supabase. Sin él se envía todo, como antes.
    Perderlo solo provoca un envío completo; un pendiente anterior siempre se reintenta."""
    observado = tiempos.instante(observado) or tiempos.ahora()
    validas = {v["id"]: v for v in vacantes if not contrato.entregable(v)}
    vistas, sin_cambios = set(), 0
    def encolar(row):
        nonlocal sin_cambios
        vistas.add(row["id"])
        if sincronizado is not None and row["id"] not in pendientes and not hay_que_enviar(row, sincronizado, observado):
            sin_cambios += 1
            return
        anterior = pendientes.get(row["id"])
        if not anterior or row["observed_at"] >= anterior["observed_at"]:
            pendientes[row["id"]] = row
    for v in validas.values():
        encolar(fila(v, observado))
    for v in vacantes:
        if v["id"] not in validas:
            encolar(fila(v, observado, "archived", contrato.entregable(v)))
    for v, estado, razon in retiradas:
        if v["id"] not in validas:
            encolar(fila(v, observado, estado, razon))
    persistir(pendientes)
    enviadas = list(pendientes.values())
    huellas = {row["id"]: [huella(row), row["observed_at"]] for row in enviadas}
    resultado = dict(subir(enviadas))
    for identificador in resultado.pop("confirmadas", []):
        pendientes.pop(identificador, None)
        if sincronizado is not None and identificador in huellas:
            sincronizado[identificador] = huellas[identificador]
    persistir(pendientes)
    if sincronizado is not None:
        for identificador in [k for k in sincronizado if k not in vistas and k not in pendientes]:
            del sincronizado[identificador]  # salió del inventario; si vuelve, se envía completa
    return dict(resultado, pendientes=len(pendientes), activas_elegibles=len(validas), sin_cambios=sin_cambios)


def filas_seleccion(lote):
    from buscador.entrega import GRADO_CONTRATO
    filas = []
    for rol, lista in lote["elegidas"].items():
        for v, grado in lista:
            filas.append({"vacante_id": v["id"], "delivery_date": lote["fecha"], "role_id": rol,
                "match_grade": GRADO_CONTRATO[grado], "selected_at": v["_capturada_entrega"], "snapshot": v})
    return filas


def registrar_seleccion(lote, pendientes, subir, persistir):
    for fila in filas_seleccion(lote):
        pendientes.setdefault(fila["vacante_id"], fila)
    persistir(pendientes)
    resultado = dict(subir(list(pendientes.values())))
    for identificador in resultado.pop("confirmadas", []):
        pendientes.pop(identificador, None)
    persistir(pendientes)
    return dict(resultado, pendientes=len(pendientes))
