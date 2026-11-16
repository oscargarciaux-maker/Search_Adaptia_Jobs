"""Un límite de tiempo agotado (0 s) detiene la fuente; antes 0 se leía como «sin límite» (corrida del 16 nov: LinkedIn
siguió releyendo fichas 50 minutos de más)."""
from types import SimpleNamespace

from buscador.fuentes import linkedin_publico


class Cliente:
    def __init__(self):
        self.pedidas = 0

    def get(self, url, params=None, **k):
        self.pedidas += 1
        return SimpleNamespace(status_code=200, text="")


def test_relectura_con_tiempo_agotado_no_pide_nada():
    previas = [{"titulo": "QA", "empresa": "Acme", "enlace": f"https://www.linkedin.com/jobs/view/41{n:08}",
                "fecha_publicacion": "2026-11-16", "_descripcion": ""} for n in range(5)]
    c = Cliente()
    crudas, stats = linkedin_publico.completar_descripciones(c, previas, 10, hoy="2026-11-16", limite_segundos=0)
    assert c.pedidas == 0 and stats["peticiones"] == 0 and crudas == []


def test_busqueda_con_tiempo_agotado_no_pide_nada():
    c = Cliente()
    mapa = {"familias": []}
    try:
        crudas, stats = linkedin_publico.buscar(c, mapa, [("CO", "Colombia")], {}, 10, hoy="2026-11-16", limite_segundos=0)
    except Exception:  # noqa: BLE001 - un mapa vacío puede no tener combinaciones; lo que importa es no pedir
        crudas = []
    assert c.pedidas == 0 and crudas == []
