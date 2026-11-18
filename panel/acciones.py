"""«Buscar ahora» (18 nov, pedido de Oscar): el panel lanza la búsqueda diaria (bodega.yml) sin entrar a GitHub, por
ejemplo el día que GitHub no lanza su horario.

GitHub solo deja lanzar un flujo a quien tiene permiso sobre el repositorio, así que el servidor del panel necesita un
token fino de GitHub de ESTE repositorio, con permiso «Actions: lectura y escritura» y nada más (GITHUB_ACCIONES_TOKEN),
y el repositorio en GITHUB_REPOSITORIO (dueño/nombre). Ambos viven solo en el alojamiento del panel: nunca en el
repositorio, el navegador ni los registros. Sin ellos el botón no aparece. Al traspasar, el cliente pone los suyos.

Siempre lanza una búsqueda diaria normal (modo diario, sin prueba): si hoy ya hubo una, completa el mismo lote y no
repite lo entregado. Nunca lanza si ya hay una en cola o corriendo, ni dos veces seguidas en pocos minutos."""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from panel.repositorio import ErrorRepositorio

API = "https://api.github.com"
FLUJO = "bodega.yml"
EN_CURSO = {"queued", "in_progress", "waiting", "requested", "pending"}
ESPERA_ENTRE_LANZAMIENTOS = 180  # s: la corrida tarda unos segundos en aparecer en la lista de GitHub
VIGENCIA_ESTADO = 15  # s
BOGOTA = timezone(timedelta(hours=-5))


def _corrida(c):
    return {"estado": "en_cola" if c.get("status") in {"queued", "waiting", "requested", "pending"} else
            "corriendo" if c.get("status") == "in_progress" else (c.get("conclusion") or "terminada"),
            "creada": c.get("created_at") or "", "manual": c.get("event") == "workflow_dispatch",
            "enlace": c.get("html_url") or ""}


def resumir(corridas, rama):
    """De la lista de corridas de bodega.yml: la que está en cola o corriendo y la última de hoy (Bogotá)."""
    propias = [c for c in corridas if isinstance(c, dict) and c.get("head_branch") == rama]
    en_curso = next((c for c in propias if c.get("status") in EN_CURSO), None)
    hoy = datetime.now(BOGOTA).date().isoformat()

    def de_hoy(c):
        try:
            creada = datetime.fromisoformat(str(c.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            return False
        return creada.astimezone(BOGOTA).date().isoformat() == hoy
    ultima = next((c for c in propias if de_hoy(c)), None)
    return {"disponible": True, "en_curso": _corrida(en_curso) if en_curso else None,
            "ultima_hoy": _corrida(ultima) if ultima else None}


class AccionesGitHub:
    def __init__(self, token, repositorio, sesion=None):
        if not token or repositorio.count("/") != 1:
            raise ValueError("Falta GITHUB_ACCIONES_TOKEN o GITHUB_REPOSITORIO (dueño/nombre).")
        self._cabeceras = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                           "X-GitHub-Api-Version": "2022-11-28"}
        self.repositorio, self.sesion = repositorio, sesion or requests.Session()
        self._rama, self._copia, self._ultimo = None, None, 0.0
        self._cerrojo = threading.Lock()

    def _pedir(self, metodo, ruta, **kw):
        try:
            r = self.sesion.request(metodo, f"{API}/repos/{self.repositorio}{ruta}", headers=self._cabeceras,
                                    timeout=15, **kw)
        except requests.RequestException as e:
            raise ErrorRepositorio("GitHub no respondió. Vuelve a intentarlo en un momento.") from e
        if r.status_code in (401, 403):
            raise ErrorRepositorio("GitHub rechazó la llave del panel (GITHUB_ACCIONES_TOKEN): revisa que exista, "
                                   "sea de este repositorio y tenga permiso «Actions».", 502)
        if r.status_code == 404:
            raise ErrorRepositorio("GitHub no encuentra el repositorio o la búsqueda: revisa GITHUB_REPOSITORIO.", 502)
        if r.status_code >= 400:
            raise ErrorRepositorio(f"GitHub respondió {r.status_code}. Vuelve a intentarlo en un momento.", 502)
        return r

    def rama(self):
        if not self._rama:
            self._rama = self._pedir("GET", "").json().get("default_branch") or "main"
        return self._rama

    def estado(self, fresco=False):
        if not fresco and self._copia and time.monotonic() - self._copia[0] < VIGENCIA_ESTADO:
            return self._copia[1]
        corridas = self._pedir("GET", f"/actions/workflows/{FLUJO}/runs", params={"per_page": 20}).json()
        valor = resumir(corridas.get("workflow_runs") or [], self.rama())
        self._copia = (time.monotonic(), valor)
        return valor

    def lanzar(self):
        with self._cerrojo:
            if time.monotonic() - self._ultimo < ESPERA_ENTRE_LANZAMIENTOS:
                raise ErrorRepositorio("La búsqueda ya se pidió hace un momento; aparecerá en unos segundos.", 409)
            if self.estado(fresco=True)["en_curso"]:
                raise ErrorRepositorio("Ya hay una búsqueda en cola o corriendo: espera a que termine.", 409)
            self._pedir("POST", f"/actions/workflows/{FLUJO}/dispatches",
                        json={"ref": self.rama(), "inputs": {"modo": "diario", "prueba": "false"}})
            self._ultimo, self._copia = time.monotonic(), None
            return {"lanzada": True}


class AccionesDemo:
    """Modo --demo: simula la búsqueda (no toca GitHub). Queda «corriendo» 20 s y luego termina bien."""
    DURACION = 20

    def __init__(self):
        self._desde = None

    def estado(self, fresco=False):
        if self._desde is None:
            return {"disponible": True, "en_curso": None, "ultima_hoy": None}
        creada = self._desde[1]
        corriendo = time.monotonic() - self._desde[0] < self.DURACION
        c = {"estado": "corriendo" if corriendo else "success", "creada": creada, "manual": True, "enlace": ""}
        return {"disponible": True, "en_curso": c if corriendo else None, "ultima_hoy": c}

    def lanzar(self):
        if self.estado()["en_curso"]:
            raise ErrorRepositorio("Ya hay una búsqueda en cola o corriendo: espera a que termine.", 409)
        self._desde = (time.monotonic(), datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return {"lanzada": True}


def desde_entorno(demo=False):
    """La conexión con GitHub, o None si el alojamiento no tiene la llave (el botón no aparece)."""
    if demo:
        return AccionesDemo()
    token, repositorio = os.environ.get("GITHUB_ACCIONES_TOKEN", ""), os.environ.get("GITHUB_REPOSITORIO", "")
    if not token or not repositorio:
        return None
    return AccionesGitHub(token, repositorio)
