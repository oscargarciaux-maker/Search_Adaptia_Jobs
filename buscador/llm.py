"""IA acotada (P-14.2, 28 nov): un LLM solo PROPONE términos de búsqueda de un cargo; nunca decide qué vacante sirve.

- `Cliente.pedir_json(prompt, esquema)`: una petición que debe devolver un objeto JSON que cumpla `esquema` (una
  función que dice si el objeto vale). Con tiempo máximo, reintento con espera (solo para fallos pasajeros: red, 429,
  5xx), tope de llamadas por corrida y validación. Si algo falla devuelve None y deja un `registro.aviso`: sin LLM
  todo sigue igual que antes.
- El proveedor va detrás de una interfaz (`Proveedor.completar`). Hoy hay uno: `openai_compatible` (el formato
  `/chat/completions` que ofrecen casi todos los servicios). Cuál se usa, su URL, el modelo y el NOMBRE de la variable
  de entorno con la clave se eligen en `datos/config.yaml` → `llm`; la clave es un secreto, nunca va en el repo.
- GitHub Models, la opción pensada al principio, se retiró el 30 jul 2026 (docs.github.com/en/github-models): no hay
  proveedor por defecto (`proveedor: ninguno`).

Lo que se envía lo arma quien llama (`panel/ampliados.py::prompt`): nombre del cargo, sus términos y el
idioma. Nunca datos de personas. Este módulo no registra el texto enviado ni el recibido, solo cifras y tipos de error.
"""
import json
import os
import re
import time

import requests

from buscador import registro

PROVEEDOR_NINGUNO = "ninguno"
PROVEEDOR_COMPATIBLE = "openai_compatible"
SEGUNDOS = 30          # tiempo máximo de cada petición
REINTENTOS = 2         # reintentos tras un fallo pasajero (3 intentos en total)
ESPERA = 2.0           # segundos de la primera espera; se dobla en cada reintento
ESPERA_MAXIMA = 30.0   # un Retry-After más largo no se espera: se deja para la próxima corrida
TOPE_POR_CORRIDA = 20  # llamadas por corrida (cada cargo nuevo o cambiado pide una)
SEGUNDOS_POR_CORRIDA = 300  # tiempo total del LLM por corrida: la búsqueda nocturna no se alarga más que esto


class FalloPasajero(Exception):
    """Red, tiempo agotado, 429 o 5xx: puede reintentarse."""

    def __init__(self, mensaje, espera=None):
        super().__init__(mensaje)
        self.espera = espera


class FalloDefinitivo(Exception):
    """Clave inválida, modelo que no existe, petición rechazada: no se reintenta."""


class Proveedor:
    """Interfaz: `completar(mensajes, segundos)` devuelve el texto de la respuesta o lanza Fallo*; `modelo` se guarda
    junto a los términos para saber de dónde salieron."""
    modelo = ""

    def completar(self, mensajes, segundos):  # pragma: no cover — interfaz
        raise NotImplementedError


class Compatible(Proveedor):
    """`POST {url}/chat/completions` con `Authorization: Bearer <clave>` (formato de OpenAI)."""

    def __init__(self, url, modelo, clave, sesion=None):
        self.url = url.rstrip("/") + "/chat/completions"
        self.modelo = modelo
        self._clave = clave
        self._sesion = sesion or requests.Session()

    def completar(self, mensajes, segundos):
        try:
            r = self._sesion.post(self.url, timeout=segundos, json={
                "model": self.modelo, "messages": mensajes, "temperature": 0, "max_tokens": 800},
                headers={"Authorization": "Bearer " + self._clave, "Content-Type": "application/json"})
        except (requests.Timeout, requests.ConnectionError) as e:
            raise FalloPasajero(type(e).__name__) from e
        except requests.RequestException as e:
            raise FalloDefinitivo(type(e).__name__) from e
        if r.status_code == 429 or r.status_code >= 500:
            raise FalloPasajero(f"HTTP {r.status_code}", _retry_after(r.headers.get("Retry-After")))
        if r.status_code >= 400:
            raise FalloDefinitivo(f"HTTP {r.status_code}")
        try:
            return r.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise FalloDefinitivo("respuesta sin texto") from e


def _retry_after(valor):
    try:
        return max(0.0, float(valor))
    except (TypeError, ValueError):
        return None


def extraer_json(texto):
    """El objeto JSON de la respuesta, aunque venga entre ```json … ``` o con una frase antes. None si no hay."""
    if not isinstance(texto, str):
        return None
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, flags=re.S)
    candidato = bloque.group(1) if bloque else texto
    inicio, fin = candidato.find("{"), candidato.rfind("}")
    if inicio < 0 or fin <= inicio:
        return None
    try:
        return json.loads(candidato[inicio:fin + 1])
    except ValueError:
        return None


class Cliente:
    """Un proveedor con su tope de llamadas por corrida. `dormir` se cambia en las pruebas."""

    def __init__(self, proveedor, tope=TOPE_POR_CORRIDA, segundos=SEGUNDOS, reintentos=REINTENTOS, espera=ESPERA,
                 dormir=time.sleep, total=SEGUNDOS_POR_CORRIDA, reloj=time.monotonic):
        self.proveedor, self.tope, self.segundos = proveedor, int(tope), float(segundos)
        self.reintentos, self.espera, self._dormir = int(reintentos), float(espera), dormir
        self.total, self._reloj, self._inicio = float(total), reloj, None
        self.llamadas = 0     # peticiones hechas (cada intento cuenta: es lo que limita el proveedor)
        self.fallos = 0       # pedidos que terminaron sin un JSON válido
        self._avisado_tope = False

    @property
    def agotado(self):
        """Llegó al tope de llamadas o al tiempo total de la corrida (contado desde la primera llamada)."""
        return self.llamadas >= self.tope or (self._inicio is not None and self._reloj() - self._inicio >= self.total)

    def pedir_json(self, prompt, esquema, sistema=None):
        """El objeto JSON si `esquema(objeto)` es verdadero; si no, None (tope, fallo o respuesta inválida). Nunca
        lanza."""
        mensajes = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": prompt}]
        espera = self.espera
        for intento in range(self.reintentos + 1):
            if self.agotado:
                if not self._avisado_tope:
                    self._avisado_tope = True
                    registro.aviso("llm:tope", RuntimeError(f"tope de {self.tope} llamadas o {self.total:.0f} s"))
                self.fallos += 1
                return None
            self.llamadas += 1
            if self._inicio is None:
                self._inicio = self._reloj()
            try:
                texto = self.proveedor.completar(mensajes, self.segundos)
            except FalloPasajero as e:
                if intento == self.reintentos or (e.espera or 0) > ESPERA_MAXIMA:
                    registro.aviso("llm:pasajero", e)
                    break
                self._dormir(e.espera if e.espera is not None else espera)
                espera *= 2
                continue
            except FalloDefinitivo as e:
                registro.aviso("llm:definitivo", e)
                break
            except Exception as e:  # noqa: BLE001 — un proveedor nunca tumba la corrida
                registro.aviso("llm:inesperado", e)
                break
            dato = extraer_json(texto)
            if dato is not None and esquema(dato):
                return dato
            # Una respuesta mal formada no se reintenta: con temperatura 0 saldría igual y gastaría el cupo del día.
            registro.aviso("llm:json", ValueError("no es JSON" if dato is None else "no cumple el esquema"))
            break
        self.fallos += 1
        return None


def opciones(cfg=None):
    """La sección `llm` de la configuración (vacía si no hay)."""
    if cfg is None:
        from buscador import bodega
        cfg = bodega.config()
    llm = (cfg or {}).get("llm")
    return llm if isinstance(llm, dict) else {}


def cliente(cfg=None, entorno=None, sesion=None, dormir=time.sleep):
    """El cliente configurado, o None si no hay proveedor, falta la URL o el modelo, o la variable de la clave está
    vacía. Sin cliente, quien llama sigue sin LLM."""
    o = opciones(cfg)
    entorno = os.environ if entorno is None else entorno
    proveedor = str(o.get("proveedor") or PROVEEDOR_NINGUNO)
    if proveedor == PROVEEDOR_NINGUNO:
        return None
    if proveedor != PROVEEDOR_COMPATIBLE:
        registro.aviso("llm:proveedor", ValueError("proveedor desconocido en datos/config.yaml"))
        return None
    clave = entorno.get(str(o.get("clave_env") or "LLM_API_KEY"), "")
    if not (o.get("url") and o.get("modelo") and clave):
        return None
    return Cliente(Compatible(str(o["url"]), str(o["modelo"]), clave, sesion),
                   tope=o.get("llamadas_por_corrida", TOPE_POR_CORRIDA),
                   segundos=o.get("segundos_por_llamada", SEGUNDOS), reintentos=o.get("reintentos", REINTENTOS),
                   total=o.get("segundos_por_corrida", SEGUNDOS_POR_CORRIDA), dormir=dormir)
