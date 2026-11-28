"""Ejecuciones acotadas de Apify y reservas conservadoras del crédito mensual."""
import calendar
import threading
import time
from datetime import date
from urllib.parse import urlencode

API = "https://api.apify.com/v2"


# 8.2 (28 nov): tipos de error con que la API de Apify rechaza iniciar una ejecución porque el plan no tiene crédito
# (enumerados en https://docs.apify.com/api/v2/actors-runs-post), además de un HTTP 402. En la cuenta gratis Apify
# BLOQUEA hasta el ciclo siguiente. No es una avería: se avisa y la fuente queda detenida el resto del mes. No se
# incluye «limit-reached»: es genérico (otros límites pasajeros) y bloquearía el mes por un fallo que no es de crédito.
ERRORES_CREDITO = ("not-enough-usage-to-run-paid-actor", "monthly-usage-limit-too-low",
                   "monthly-usage-hard-limit-exceeded", "x402-payment-required")
AVISO_SIN_CREDITO = "Apify sin crédito en el plan: la fuente se detiene hasta el mes siguiente"
AVISO_GASTO = 0.8  # aviso cuando lo reservado en el mes pasa del 80 % del tope


def credito_agotado(detalle):
    detalle = detalle if isinstance(detalle, dict) else {}
    return detalle.get("http") == 402 or str(detalle.get("tipo") or "") in ERRORES_CREDITO


def ritmo(mensual, diario, hoy):
    """Lo que se puede reservar por día: `diario` (P-16.2: 0,16 = 5/31 con la cuenta gratis; 0,61 con Starter) o, sin
    él, el tope del mes repartido entre sus días (lo de antes). Nunca más que el tope del mes."""
    if diario is None:
        dia = date.fromisoformat(hoy)
        return float(mensual) / calendar.monthrange(dia.year, dia.month)[1]
    return min(float(diario), float(mensual))


def bloqueado(estado, mensual):
    """El mes está bloqueado si Apify dijo «sin crédito» con este tope o uno mayor. Al comprar un plan mayor (subir
    `tope_mensual_usd`) se vuelve a reservar sin borrar nada (8.2)."""
    tope = (estado or {}).get("bloqueado_tope")
    return tope is not None and float(mensual) <= float(tope) + 1e-9


def gasto(ejecuciones):
    """8.2: lo reservado por estas ejecuciones y lo que Apify informó que costaron (`usageTotalUsd`), en USD."""
    return {"usd_reservado": round(sum(e.get("tope_reservado_usd") or 0 for e in ejecuciones), 6),
            "usd_reportado": round(sum(e.get("costo_uso_reportado_usd") or 0 for e in ejecuciones), 6)}


def detener_por_credito(control):
    """Apify dijo que el plan no tiene crédito: el mes queda bloqueado para las corridas siguientes. Si no se puede
    anotar (p. ej. Supabase no responde), se avisa y la fuente se detiene igual en esta corrida; no gasta de más,
    porque Apify sigue rechazando y la reserva ya quedó contada."""
    try:
        control.marcar_agotado()
    except Exception as e:  # noqa: BLE001 — anotar el bloqueo es una ayuda; nunca tumba la corrida
        from buscador import registro
        registro.aviso("apify:bloqueo", e)
    return {"credito_agotado": True, "aviso": AVISO_SIN_CREDITO}


class Control:
    """Lo común del presupuesto local y del central: topes, ritmo y bloqueo. `estado` = {mes, reservas,
    bloqueado_tope}."""

    def __init__(self, hoy, mensual=5, corrida=3, diario=None):
        self.hoy = hoy
        self.mensual, self.corrida = float(mensual), float(corrida)
        self.diario = ritmo(self.mensual, diario, hoy)
        self.reservado = 0.0
        self.lock = threading.Lock()

    @property
    def bloqueado(self):
        return bloqueado(self.estado, self.mensual)


class Presupuesto(Control):
    def __init__(self, estado, hoy, mensual=5, corrida=3, guardar=None, diario=None):
        super().__init__(hoy, mensual, corrida, diario)
        self.estado, self.guardar = estado, guardar
        if estado.get("mes") != hoy[:7]:
            estado.clear()  # mes nuevo: reservas y bloqueo empiezan de cero
            estado.update(mes=hoy[:7], reservas={})

    def marcar_agotado(self):
        """Nada más se reserva este mes con este tope (también en las corridas siguientes)."""
        with self.lock:
            self.estado["bloqueado_tope"] = max(self.mensual, float(self.estado.get("bloqueado_tope") or 0))
            if self.guardar:
                self.guardar(self.estado)

    def reservar(self, monto):
        with self.lock:
            if self.bloqueado:
                return 0.0
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
        detalle = getattr(cliente, "ultimo_error", None)
        if detalle:
            stats["detalle"] = {k: v.replace(token, "[oculto]") if isinstance(v, str) else v for k, v in detalle.items()}
        if credito_agotado(detalle):
            return [], dict(stats, credito_agotado=True, aviso=AVISO_SIN_CREDITO)
        if (detalle or {}).get("http") in (401, 403):
            # Clave revocada o rotada (p. ej. incidente de seguridad de Apify, nov 2026): no insistir y avisar.
            return [], dict(stats, clave_invalida=True,
                            error="Apify rechazó la clave (APIFY_TOKEN): reemplazarla por la vigente en los secretos")
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
