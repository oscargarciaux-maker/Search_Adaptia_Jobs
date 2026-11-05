"""Colas con revisión y reservas Apify duraderas. Un error nunca habilita gasto local alternativo."""
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
import json
import threading
from uuid import uuid4

import requests

from buscador import supabase, tiempos


def micro(valor, redondeo=ROUND_DOWN):
    return int((Decimal(str(valor)) * 1_000_000).to_integral_value(rounding=redondeo))


class Central:
    def __init__(self, presupuesto_local, guardar_presupuesto, sesion=None):
        self.url, clave = supabase.credenciales()
        if not self.url or not clave:
            raise RuntimeError("El estado central requiere credenciales Supabase; no se usará estado local alternativo.")
        self.sesion = sesion or requests.Session()
        self.cabeceras = {"apikey": clave}
        if clave.startswith("eyJ"):
            self.cabeceras["Authorization"] = f"Bearer {clave}"
        self.ejecucion = str(uuid4())
        self.guardar_presupuesto = guardar_presupuesto
        self.presupuesto = self.rpc("operacion_inicializar", {"p_importar": presupuesto_local})
        self._validar_presupuesto(self.presupuesto)
        guardar_presupuesto(self.presupuesto)
        self.lote = Cola(self, "lote")

    @staticmethod
    def _validar_presupuesto(datos):
        if not isinstance(datos, dict) or not isinstance(datos.get("reservas"), dict) or not datos.get("mes"):
            raise RuntimeError("Supabase no confirmó el presupuesto central; no se autorizó gasto.")

    def rpc(self, nombre, cuerpo):
        try:
            r = self.sesion.post(f"{self.url}/rest/v1/rpc/{nombre}", json=cuerpo, headers=self.cabeceras, timeout=45)
            datos = r.json()
        except (requests.RequestException, ValueError) as e:
            raise RuntimeError(f"Estado central sin confirmar ({nombre}); conservar copia y releer, sin reintento automático.") from e
        if not 200 <= r.status_code < 300:
            detalle = datos.get("message", "") if isinstance(datos, dict) and datos.get("code") == "P0001" else ""
            raise RuntimeError(f"Estado central: {nombre} HTTP {r.status_code}. {detalle} Revisar migración 003/permisos.")
        return datos

    def leer(self, cola, identificador=None):
        filas, ultimo = [], None
        while True:
            params = {"cola": "eq." + cola, "select": "identificador,payload,revision", "order": "identificador", "limit": 100}
            if identificador is not None:
                params["identificador"] = "eq." + identificador
            elif ultimo is not None:
                params["identificador"] = "gt." + ultimo
            try:
                r = self.sesion.get(f"{self.url}/rest/v1/estado_operativo", params=params, headers=self.cabeceras, timeout=45)
                datos = r.json()
            except (requests.RequestException, ValueError) as e:
                raise RuntimeError("No se pudo recuperar el estado central; no continuar con una copia vacía.") from e
            if r.status_code != 200 or not isinstance(datos, list):
                raise RuntimeError("No se pudo leer estado_operativo; comprobar SQL 003 y permisos.")
            filas.extend(datos)
            if len(datos) < 100 or identificador is not None:
                return filas
            nuevo = datos[-1]["identificador"]
            if ultimo is not None and nuevo <= ultimo:
                raise RuntimeError("Paginación central inconsistente; detener para no omitir pendientes.")
            ultimo = nuevo

    def cola(self, nombre, local, guardar_local):
        cola = Cola(self, nombre, guardar_local)
        cola.cargar()
        fusionadas = deepcopy(cola.valores)
        for k, v in local.items():
            if k not in fusionadas or nombre == "catalogo" and v.get("observed_at", "") > fusionadas[k].get("observed_at", ""):
                fusionadas[k] = v
        cola.guardar(fusionadas)
        return fusionadas, cola.guardar

    @staticmethod
    def normalizar_lote(lote):
        copia = json.loads(json.dumps({"fecha": lote["fecha"], "elegidas": lote.get("elegidas", {})}))
        for lista in copia["elegidas"].values():
            for v, _ in lista:
                if v.get("_capturada_entrega"):
                    v["_capturada_entrega"] = tiempos.instante(v["_capturada_entrega"])
        return copia

    def cargar_lote(self, hoy, local):
        self.lote.cargar()
        remoto = deepcopy(self.lote.valores.get(hoy, {"fecha": hoy, "elegidas": {}}))
        if local.get("fecha") == hoy:
            for rol, lista in local.get("elegidas", {}).items():
                ids = {v["id"] for filas in remoto["elegidas"].values() for v, _ in filas}
                remoto["elegidas"].setdefault(rol, []).extend((v, g) for v, g in lista if v["id"] not in ids)
        if remoto["elegidas"]:
            self.guardar_lote(remoto)
        return remoto

    def guardar_lote(self, lote):
        normalizado = self.normalizar_lote(lote)
        valores = deepcopy(self.lote.valores)
        valores[normalizado["fecha"]] = normalizado
        self.lote.guardar(valores)

    def limpiar_lotes_confirmados(self):
        self.lote.guardar(deepcopy(self.lote.valores))

    def recuperar_pendientes(self, ofertas, guardar_ofertas, registro, guardar_registro):
        """Reconstruir también días anteriores si se perdió el proceso antes de crear sus colas."""
        from buscador import catalogo, entrega
        memoria = {}
        for lote in self.lote.valores.values():
            for fila in entrega.filas_de(lote["elegidas"], entrega.config()["roles"], lote["fecha"], ""):
                ofertas.setdefault(fila["external_id"], fila)
            for fila in catalogo.filas_seleccion(lote):
                registro.setdefault(fila["vacante_id"], fila)
            for lista in lote["elegidas"].values():
                for v, _ in lista:
                    memoria.update({h: lote["fecha"] for h in entrega.huellas(v)})
        guardar_ofertas(ofertas)
        guardar_registro(registro)
        return memoria

    def control_apify(self, hoy, mensual=5, corrida=3):
        return PresupuestoCentral(self, hoy, mensual, corrida)


class Cola:
    def __init__(self, central, nombre, guardar_local=lambda datos: None):
        self.central, self.nombre, self.guardar_local = central, nombre, guardar_local
        self.valores, self.revisiones = {}, {}

    def cargar(self, identificador=None):
        for r in self.central.leer(self.nombre, identificador):
            self.valores[r["identificador"]] = r["payload"]
            self.revisiones[r["identificador"]] = r["revision"]

    def guardar(self, valores):
        self.guardar_local(valores)  # copia recuperable antes de la red; no equivale a confirmación
        cambios = [{"identificador": k, "payload": v, "revision": self.revisiones.get(k, 0)}
                   for k, v in valores.items() if self.nombre == "lote" or k not in self.valores or v != self.valores[k]]
        for i in range(0, len(cambios), 100):
            lote = cambios[i:i + 100]
            respuesta = self.central.rpc("estado_guardar", {"p_cola": self.nombre, "p_elementos": lote})
            if not isinstance(respuesta, list) or {r.get("identificador") for r in respuesta} != {r["identificador"] for r in lote}:
                raise RuntimeError("Supabase no confirmó todas las revisiones; conservar copia y releer.")
            por_id = {r["identificador"]: r["payload"] for r in lote}
            for r in respuesta:
                k, revision = r["identificador"], r.get("revision")
                if not isinstance(revision, int) or revision < 0 or revision == 0 and self.nombre != "lote":
                    raise RuntimeError("Revisión central inválida; detener y releer estado.")
                if revision:
                    self.revisiones[k], self.valores[k] = revision, deepcopy(por_id[k])
                else:  # lote ya confirmado en registro canónico
                    self.revisiones.pop(k, None)
                    self.valores.pop(k, None)
        borradas = [{"identificador": k, "revision": r} for k, r in self.revisiones.items() if k not in valores]
        for i in range(0, len(borradas), 100):
            lote = borradas[i:i + 100]
            respuesta = self.central.rpc("estado_confirmar", {"p_cola": self.nombre, "p_elementos": lote})
            if not isinstance(respuesta, list) or set(respuesta) != {r["identificador"] for r in lote}:
                raise RuntimeError("Confirmación central incompleta; releer antes de continuar.")
            for k in respuesta:
                self.revisiones.pop(k, None)
                self.valores.pop(k, None)


class PresupuestoCentral:
    def __init__(self, central, hoy, mensual, corrida):
        import calendar
        from datetime import date
        self.central, self.hoy = central, hoy
        self.mensual, self.corrida = float(mensual), float(corrida)
        d = date.fromisoformat(hoy)
        self.diario = self.mensual / calendar.monthrange(d.year, d.month)[1]
        self.reservado = 0.0
        self.lock = threading.Lock()

    def reservar(self, monto):
        with self.lock:
            r = self.central.rpc("apify_reservar", {"p_solicitud": str(uuid4()), "p_ejecucion": self.central.ejecucion,
                "p_fecha": self.hoy, "p_mensual": micro(self.mensual), "p_corrida": micro(self.corrida), "p_monto": micro(monto)})
            n = r.get("monto_micro") if isinstance(r, dict) else None
            if not isinstance(n, int) or n < 0 or n > micro(monto):
                raise RuntimeError("Reserva central no confirmada; no ejecutar Apify.")
            self.central._validar_presupuesto(r.get("estado"))
            self.central.presupuesto = r["estado"]
            self.central.guardar_presupuesto(r["estado"])
            self.reservado = round(self.reservado + n / 1_000_000, 6)
            return n / 1_000_000
