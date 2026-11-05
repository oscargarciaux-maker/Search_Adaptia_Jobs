"""Catálogo persistente independiente de la cuota diaria. No elimina ofertas históricas."""
from buscador import contrato, tiempos, vacante


def fila(v, observado, estado="active", razon=""):
    return {"id": v["id"], "contract_version": "v2", "datos": vacante.publica(v),
            "description_full": v.get("_descripcion", "")[:30000],
            "published_at": v.get("publicada_en") or None,
            "first_seen_at": v.get("detectada_en") or None, "last_seen_at": v.get("vista_en") or None,
            "observed_at": observado, "status": estado,
            "closed_at": observado if estado == "closed" else None, "reason": razon or None}


def sincronizar(vacantes, retiradas, pendientes, subir, persistir, observado=None):
    observado = tiempos.instante(observado) or tiempos.ahora()
    validas = {v["id"]: v for v in vacantes if not contrato.entregable(v)}
    def encolar(row):
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
    resultado = dict(subir(list(pendientes.values())))
    for identificador in resultado.pop("confirmadas", []):
        pendientes.pop(identificador, None)
    persistir(pendientes)
    return dict(resultado, pendientes=len(pendientes), activas_elegibles=len(validas))


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
