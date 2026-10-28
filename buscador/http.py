"""Peticiones HTTP con pausas, reintento ante bloqueos (429) y tiempo límite. Sin sesión de nadie."""
import random
import time

import requests

NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8,pt;q=0.6",
}


class Cliente:
    """Cliente con contador de peticiones (para los presupuestos de cada fuente) y una espera larga ante un 429."""

    def __init__(self, pausa=(0.5, 1.5), espera_429=(45, 75), timeout=25):
        self.sesion = requests.Session()
        self.sesion.headers.update(NAVEGADOR)
        self.pausa, self.espera_429, self.timeout = pausa, espera_429, timeout
        self.peticiones = 0
        self.bloqueos = 0

    def get(self, url, params=None, headers=None, reintentar_429=True, pausar=True):
        """Respuesta (requests.Response) o None si falló la conexión."""
        for intento in range(2):
            self.peticiones += 1
            try:
                r = self.sesion.get(url, params=params, headers=headers, timeout=self.timeout, allow_redirects=True)
            except requests.RequestException:
                return None
            finally:
                if pausar:
                    time.sleep(random.uniform(*self.pausa))
            if r.status_code == 429:
                self.bloqueos += 1
                if reintentar_429 and intento == 0:
                    time.sleep(random.uniform(*self.espera_429))
                    continue
            return r
        return r

    def json(self, url, params=None, headers=None, **k):
        r = self.get(url, params=params, headers=headers, **k)
        if r is None or r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None

    def post_json(self, url, cuerpo, headers=None, timeout=None):
        self.peticiones += 1
        try:
            r = self.sesion.post(url, json=cuerpo, headers=headers, timeout=timeout or self.timeout)
        except requests.RequestException:
            return None
        try:
            return r.json() if r.status_code < 300 else None
        except ValueError:
            return None
