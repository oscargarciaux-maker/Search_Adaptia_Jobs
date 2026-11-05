"""Ejecuciones acotadas de Apify y reservas conservadoras del crédito mensual."""
import calendar
import threading
import time
from datetime import date
from urllib.parse import urlencode

API = "https://api.apify.com/v2"


class Presupuesto:
    def __init__(self, estado, hoy, mensual=5, corrida=3, guardar=None):
        self.estado, self.hoy, self.guardar = estado, hoy, guardar
        self.mensual, self.corrida = float(mensual), float(corrida)
        dia = date.fromisoformat(hoy)
        self.diario = self.mensual / calendar.monthrange(dia.year, dia.month)[1]
        self.reservado = 0.0
        self.lock = threading.Lock()
        if estado.get("mes") != hoy[:7]:
            estado.clear()
            estado.update(mes=hoy[:7], reservas={})

    def reservar(self, monto):
        with self.lock:
            reservas = self.estado["reservas"]
            disponible = min(self.mensual - sum(reservas.values()), self.corrida - self.reservado,
                             self.diario - reservas.get(self.hoy, 0), float(monto))
            monto = int(max(0, disponible) * 1_000_000) / 1_000_000
            if monto < 0.002:
                return 0.0
            reservas[self.hoy] = round(reservas.get(self.hoy, 0) + monto, 6)
            self.reservado = round(self.reservado + monto, 6)
            if self.guardar:
                self.guardar(self.estado)  # antes del POST: un timeout no habilita otro cargo con el mismo crédito
            return monto


def ejecutar(cliente, actor, entrada, token, max_usd, max_items=20, build=None, limite_segundos=180,
             reloj=time.monotonic, esperar=time.sleep):
    inicio = reloj()
    cabeceras = {"Authorization": f"Bearer {token}"}
    params = {"maxTotalChargeUsd": max_usd, "waitForFinish": 30, "timeout": max(1, int(limite_segundos))}
    if build:
        params["build"] = build
    url = f"{API}/acts/{actor.replace('/', '~')}/runs?{urlencode(params)}"
    respuesta = cliente.post_json(url, entrada, headers=cabeceras, timeout=45)
    run = (respuesta or {}).get("data") if isinstance(respuesta, dict) else None
    stats = {"tope_reservado_usd": max_usd}
    if not isinstance(run, dict) or not run.get("id"):
        return [], dict(stats, error="Apify no confirmó el inicio; se conserva la reserva para evitar doble gasto")
    stats["run_id"] = run["id"]
    while run.get("status") in ("READY", "RUNNING", "TIMING-OUT", "ABORTING"):
        if reloj() - inicio >= limite_segundos:
            cliente.post_json(f"{API}/actor-runs/{run['id']}/abort", {}, headers=cabeceras, timeout=20)
            return [], dict(stats, error="Apify agotó el tiempo; se solicitó detener la ejecución", estado="TIMEOUT")
        esperar(2)
        nueva = cliente.json(f"{API}/actor-runs/{run['id']}", headers=cabeceras, pausar=False)
        if not isinstance(nueva, dict) or not isinstance(nueva.get("data"), dict):
            return [], dict(stats, error="No se pudo consultar el estado de Apify; no se relanza la búsqueda")
        run = nueva["data"]
    stats["estado"] = run.get("status")
    if run.get("usageTotalUsd") is not None:
        stats["costo_uso_reportado_usd"] = run["usageTotalUsd"]
    if run.get("status") != "SUCCEEDED":
        return [], dict(stats, error="Apify no completó la ejecución")
    dataset = run.get("defaultDatasetId")
    if not dataset:
        return [], dict(stats, error="Apify terminó sin dataset")
    items = cliente.json(f"{API}/datasets/{dataset}/items?clean=true&format=json&limit={max_items}",
                         headers=cabeceras, pausar=False)
    if not isinstance(items, list):
        return [], dict(stats, error="No se pudo leer el dataset; se conserva la reserva")
    return items, stats
