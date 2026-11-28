"""P-11.3 (decisión de Oscar, 28 nov): los avisos al operador saltan bajo 10 (la meta) y el rescate pagado sigue bajo 5.
Las dos cifras viven en `datos/config.yaml` → `cobertura` y son independientes. Perfiles ficticios."""
from collections import Counter
from pathlib import Path

import pytest
import yaml

from buscador import entrega, familias, refuerzo
from panel import afinidad, ejecutor, huecos, servicio
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy

from pruebas.panel.test_rescate import CON_DATO, _oferta

TITULOS = {"Product Designer": "Product Designer", "Frontend": "Frontend Developer", "QA": "QA Engineer"}


def test_las_dos_cifras_salen_de_config_yaml():
    datos = yaml.safe_load((Path(__file__).resolve().parents[2] / "datos" / "config.yaml").read_text(encoding="utf-8"))
    assert datos["cobertura"] == {"aviso_bajo": 10, "rescate_bajo": 5}
    assert (afinidad.AVISO_BAJO, afinidad.RESCATE_BAJO) == (10, 5)
    assert afinidad.MINIMO_POR_PERFIL == 5  # el mínimo de la selección (7.A) no se toca aquí


@pytest.mark.parametrize("cobertura, esperado", [
    ({"aviso_bajo": 12}, (12, 5)),                     # cambiar el aviso no mueve el rescate
    ({"rescate_bajo": 10}, (10, 10)),                  # subir el rescate (Starter) no mueve el aviso
    ({"aviso_bajo": 8, "rescate_bajo": 3}, (8, 3)),
    ({"aviso_bajo": "diez", "rescate_bajo": 0}, (10, 5)),  # lo inválido vuelve al valor del contrato
    ({"aviso_bajo": True}, (10, 5)),
    (None, (10, 5)),
    ("texto", (10, 5)),
])
def test_cambiar_una_cifra_no_mueve_la_otra(monkeypatch, cobertura, esperado):
    monkeypatch.setattr(afinidad, "_config_yaml", lambda: {"cobertura": cobertura})
    assert afinidad._umbrales_cobertura() == esperado


def test_sin_config_vuelve_a_los_valores_del_contrato(monkeypatch):
    monkeypatch.setattr(afinidad, "_config_yaml", lambda: {})
    assert afinidad._umbrales_cobertura() == (10, 5)


@pytest.fixture
def cfg():
    c = configuracion_demo()
    for p in c["perfiles"][1:3]:
        p["activo"] = False  # un solo perfil en Product Designer
    return c


def _ofertas(cfg, n):
    ofertas = [_oferta(TITULOS[c["nombre"]], f"{c['nombre']}{i}", CON_DATO) for c in cfg["cargos"] for i in range(n)]
    with ejecutor.activar({"configuracion": cfg}, hoy()):  # se clasifica con los cargos del panel
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
    return ofertas


def _rescate(cfg, ofertas):
    """(perfiles bajo el umbral del rescate en el resumen, llamadas a Apify, llamadas a posts)."""
    apify, posts = [], []
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        _, resumen = entrega.elegir(ofertas, {}, hoy())
        refuerzo.rescate_apify(ofertas, {}, hoy(), entrega.config(), familias.mapa(),
                               lambda c: apify.append(c) or ([], {}), lambda a, b: a + b)
        refuerzo.rescate_posts(ofertas, {}, hoy(), entrega.config(), familias.mapa(),
                               lambda c, f, e: posts.append(c) or ([], [], {}), lambda a, b: a + b)
    return sum(r.get("perfiles_bajo_minimo", 0) for r in resumen["roles"].values()), apify, posts


def test_con_7_de_10_no_se_gasta_rescate_pero_se_avisa(cfg):
    """Quien tiene 7 está bajo la meta (aviso) pero sobre 5: ni refuerzo por perfil, ni Apify, ni posts (como antes)."""
    bajo, apify, posts = _rescate(cfg, _ofertas(cfg, 7))
    assert bajo == 0 and not apify and not posts
    pid = next(p["id"] for p in cfg["perfiles"] if p.get("activo", True))
    repo = RepositorioDemo()
    repo.operativa = lambda fecha: {"revision": 1, "configuracion": cfg}
    repo.versiones = lambda revisiones: {int(r): cfg for r in revisiones}
    repo.ejecuciones = lambda: [{"id": f"e{i}", "fecha": "2026-11-1" + str(7 - i), "revision": 1} for i in range(4)]
    repo.asignaciones_por_perfil = lambda ids: Counter({(e, pid): 7 for e in ids})
    fila = next(f for f in servicio.cobertura(repo, "2026-11-17")["perfiles"] if f["perfil_id"] == pid)
    assert fila["estado"] == "pendiente" and fila["dias_con_minimo"] == 0 and fila["dias_seguidos_bajo"] == 4


def test_con_menos_de_5_el_rescate_sigue_igual(cfg):
    bajo, apify, posts = _rescate(cfg, _ofertas(cfg, 2))
    assert bajo >= 1 and apify and posts


def test_el_rescate_lo_decide_rescate_bajo_y_no_aviso_bajo(cfg, monkeypatch):
    ofertas = _ofertas(cfg, 7)
    monkeypatch.setattr(afinidad, "AVISO_BAJO", 20)
    assert _rescate(cfg, ofertas)[1] == []  # subir el aviso no gasta Apify
    monkeypatch.setattr(afinidad, "RESCATE_BAJO", 10)  # lo que hará la 8.2b al comprar Starter
    bajo, apify, posts = _rescate(cfg, ofertas)
    assert bajo >= 1 and apify and posts


def test_el_aviso_al_guardar_dice_la_cifra_en_uso(monkeypatch):
    cfg = configuracion_demo()
    cfg["perfiles"] = [{**cfg["perfiles"][0], "vive_en": "GH", "ubicaciones": []}]
    assert huecos.aviso_al_guardar(None, cfg) == ["Ghana: sin fuente local; riesgo de quedar bajo 10."]
    monkeypatch.setattr(huecos, "AVISO_BAJO", 12)
    assert huecos.aviso_al_guardar(None, cfg) == ["Ghana: sin fuente local; riesgo de quedar bajo 12."]
