"""«Buscar ahora» (18 nov, pedido de Oscar): el panel lanza la búsqueda diaria (bodega.yml) sin entrar a GitHub, por
ejemplo el día que GitHub no lanza su horario.

GitHub solo deja lanzar un flujo a quien tiene permiso sobre el repositorio, así que el servidor del panel necesita un
token fino de GitHub de ESTE repositorio con permiso «Actions: lectura y escritura» y nada más (GITHUB_ACCIONES_TOKEN),
y el repositorio en GITHUB_REPOSITORIO (dueño/nombre). Ambos viven solo en el alojamiento del panel: nunca en el
repositorio, el navegador, las respuestas ni los registros. Sin ellos el botón no aparece. Al traspasar, el cliente pone
los suyos.

Siempre lanza una búsqueda diaria normal (modo diario, sin prueba): si hoy ya hubo una, completa el mismo lote y no
repite lo entregado. GitHub deja una sola tarea esperando por grupo de concurrencia («publicar») y la que llega después
cancela a la que esperaba; por eso no lanza si otra tarea del grupo espera turno o si una larga (no la captura horaria,
que dura minutos) está corriendo, ni dos veces seguidas en pocos minutos."""
import os
import threading
import time
from datetime import datetime, timezone

import requests

from buscador import registro
from buscador.arranque import hoy_bogota
from panel.repositorio import ErrorRepositorio

API = "https://api.github.com"
FLUJO = "bodega.yml"
# Flujos con `concurrency: group: publicar` (pruebas/panel/test_buscar_ahora.py lo compara con .github/workflows).
GRUPO_PUBLICAR = {"bodega.yml", "incremental.yml", "limpiar_fuera_objetivo.yml", "preparar.yml", "profunda.yml",
                  "respaldo.yml", "traspaso.yml"}
CORTO = "incremental.yml"  # corre unos minutos: se puede esperar detrás de ella sin riesgo
EN_COLA = {"queued", "waiting", "requested", "pending"}
EN_CURSO = EN_COLA | {"in_progress"}
ESPERA_ENTRE_LANZAMIENTOS = 180  # s: la corrida tarda unos segundos en aparecer en la lista de GitHub
VIGENCIA_ESTADO = 15  # s
YA_HAY = "Ya hay una búsqueda en cola o corriendo: espera a que termine."
NOMBRES = {"bodega.yml": "la búsqueda diaria", "incremental.yml": "la captura horaria",
           "profunda.yml": "una búsqueda profunda", "preparar.yml": "la preparación de Supabase",
           "respaldo.yml": "la copia de seguridad", "traspaso.yml": "un traspaso",
           "limpiar_fuera_objetivo.yml": "una limpieza de la base"}


def _flujo(c):
    return str(c.get("path") or "").rsplit("/", 1)[-1]


def _corrida(c):
    if c.get("status") in EN_COLA:
        estado = "en_cola"
    elif c.get("status") == "in_progress":
        estado = "corriendo"
    else:
        estado = c.get("conclusion") or "terminada"
    return {"estado": estado, "creada": c.get("created_at") or ""}


def _de_hoy(c):
    try:
        return hoy_bogota(datetime.fromisoformat(str(c.get("created_at", "")))) == hoy_bogota()
    except ValueError:
        return False


def resumir(corridas, rama):
    """De las corridas recientes del repositorio (todas las del grupo):
    - en_curso: la búsqueda diaria de la rama principal en cola o corriendo (el botón dice desde cuándo);
    - ocupado: otra tarea del grupo que impide lanzar sin cancelar nada (o None);
    - ultima_pedida: la última búsqueda diaria pedida a mano hoy, para avisar si GitHub la canceló."""
    corridas = [c for c in corridas if isinstance(c, dict) and _flujo(c) in GRUPO_PUBLICAR]
    diarias = [c for c in corridas if _flujo(c) == FLUJO and c.get("head_branch") == rama]
    en_curso = next((c for c in diarias if c.get("status") in EN_CURSO), None)
    ocupa = None if en_curso else next(
        (c for c in corridas if c.get("status") in EN_COLA or
         (c.get("status") == "in_progress" and _flujo(c) != CORTO)), None)
    pedida = next((c for c in diarias if c.get("event") == "workflow_dispatch" and _de_hoy(c)), None)
    return {"en_curso": _corrida(en_curso) if en_curso else None,
            "ocupado": (f"Espera: {NOMBRES.get(_flujo(ocupa), 'otra tarea')} está "
                        f"{'esperando turno' if ocupa.get('status') in EN_COLA else 'corriendo'}; "
                        "si pides ahora, una de las dos se cancelaría.") if ocupa else None,
            "ultima_pedida": _corrida(pedida) if pedida else None}


class AccionesGitHub:
    def __init__(self, token, repositorio, sesion=None):
        token, repositorio = (token or "").strip(), (repositorio or "").strip()
        if not token or repositorio.count("/") != 1 or any(c.isspace() for c in token):
            raise ValueError("GITHUB_ACCIONES_TOKEN o GITHUB_REPOSITORIO (dueño/nombre) no son válidos.")
        self._cabeceras = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                           "X-GitHub-Api-Version": "2022-11-28"}
        self.repositorio, self.sesion = repositorio, sesion or requests.Session()
        # None = aún no se lanzó nada (no 0.0: el reloj monotónico de una máquina recién encendida vale menos de 180).
        self._rama, self._copia, self._ultimo = None, None, None
        self._cerrojo = threading.Lock()

    def _pedir(self, metodo, ruta, **kw):
        try:
            r = self.sesion.request(metodo, f"{API}/repos/{self.repositorio}{ruta}", headers=self._cabeceras,
                                    timeout=15, **kw)
        except requests.RequestException:
            # Sin encadenar la excepción: algunas (cabecera inválida) llevan el token en su texto.
            raise ErrorRepositorio("GitHub no respondió. Vuelve a intentarlo en un momento.") from None
        if r.status_code == 429 or (r.status_code == 403 and getattr(r, "headers", {}).get("x-ratelimit-remaining") == "0"):
            raise ErrorRepositorio("GitHub pide esperar unos minutos antes de volver a preguntar.", 503)
        if r.status_code in (401, 403):
            raise ErrorRepositorio("GitHub rechazó la llave del panel (GITHUB_ACCIONES_TOKEN): revisa que exista, "
                                   "sea de este repositorio y tenga permiso «Actions».", 502)
        if r.status_code == 404:
            raise ErrorRepositorio("GitHub no encuentra el repositorio o la búsqueda: revisa GITHUB_REPOSITORIO.", 502)
        if r.status_code == 422:
            raise ErrorRepositorio("GitHub no aceptó el pedido: revisa que bodega.yml se pueda lanzar a mano "
                                   "(workflow_dispatch) en la rama principal.", 502)
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
        corridas = self._pedir("GET", "/actions/runs", params={"per_page": 50}).json()
        valor = resumir(corridas.get("workflow_runs") or [], self.rama())
        self._copia = (time.monotonic(), valor)
        return valor

    def lanzar(self, enfoque="completo"):
        with self._cerrojo:
            if self._ultimo is not None and time.monotonic() - self._ultimo < ESPERA_ENTRE_LANZAMIENTOS:
                raise ErrorRepositorio("La búsqueda ya se pidió hace un momento; aparecerá en unos segundos.", 409)
            actual = self.estado(fresco=True)
            if actual["en_curso"]:
                raise ErrorRepositorio(YA_HAY, 409)
            if actual["ocupado"]:
                raise ErrorRepositorio(actual["ocupado"], 409)
            self._pedir("POST", f"/actions/workflows/{FLUJO}/dispatches",
                        json={"ref": self.rama(), "inputs": {"modo": "diario", "prueba": "false", "enfoque": enfoque}})
            self._ultimo, self._copia = time.monotonic(), None
            return {"lanzada": True}


class AccionesDemo:
    """Modo --demo: simula corridas de GitHub (no lo toca) y pasa por el mismo `resumir`. Una búsqueda pedida queda
    en curso 20 s y luego termina bien."""
    DURACION = 20

    def __init__(self):
        self._pedida = None  # (monotonic, created_at)

    def estado(self, fresco=False):
        corridas = []
        if self._pedida:
            corriendo = time.monotonic() - self._pedida[0] < self.DURACION
            corridas.append({"path": ".github/workflows/bodega.yml", "head_branch": "main",
                             "event": "workflow_dispatch", "created_at": self._pedida[1],
                             "status": "in_progress" if corriendo else "completed",
                             "conclusion": None if corriendo else "success"})
        return resumir(corridas, "main")

    def lanzar(self, enfoque="completo"):
        if self.estado()["en_curso"]:
            raise ErrorRepositorio(YA_HAY, 409)
        self._pedida = (time.monotonic(), datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return {"lanzada": True}


def desde_entorno(demo=False):
    """La conexión con GitHub, o None si el alojamiento no tiene la llave o está mal escrita (el botón no aparece)."""
    if demo:
        return AccionesDemo()
    token, repositorio = os.environ.get("GITHUB_ACCIONES_TOKEN", ""), os.environ.get("GITHUB_REPOSITORIO", "")
    if not token.strip() and not repositorio.strip():
        return None
    try:
        return AccionesGitHub(token, repositorio)
    except ValueError as e:  # el mensaje no lleva el token
        registro.aviso("panel:acciones", e)
        return None
