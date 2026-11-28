"""P-11.1 (28 nov): la comprobación de enlaces empieza por quien va corta, también en español, y usa el presupuesto.
La Bodega del 27 abrió 213 enlaces con cupo de 800 y 600 s; en español solo el 24 % de las vacantes de un cargo
buscado tenía el enlace comprobado (inglés: 39 %)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from buscador import verificar_enlaces
from panel import ejecutor
from panel.repositorio import configuracion_demo, hoy
from pruebas.panel.test_espanol_v49 import EN, _vacante


@pytest.fixture
def cfg():
    """Dos personas del mismo cargo en Colombia, remoto: una solo en español y otra solo en inglés."""
    c = configuracion_demo()
    for p in c["perfiles"][2:]:
        p["activo"] = False
    base = dict(vive_en="CO", modalidades=["remoto"], ciudades=[], ubicaciones=[], meta_diaria=5, activo=True)
    c["perfiles"][0].update(base, idiomas=["es"])
    c["perfiles"][1].update(base, idiomas=["en"], cargo_id=c["perfiles"][0]["cargo_id"])
    return c


def _comprobador(comprobadas):
    def comprobar(url, titulo, ahora=None, **_):
        comprobadas.append(url)
        return {"url": url, "destino": url, "estado": "verificada", "motivo": "ficha específica accesible",
                "comprobada_en": ahora.isoformat(), "http": 200, "saltos": 0, "ruta": []}
    return comprobar


def _correr(monkeypatch, vacantes, cfg_enlaces):
    comprobadas = []
    monkeypatch.setattr(verificar_enlaces, "comprobar", _comprobador(comprobadas))
    cache = {}
    ahora = datetime.now(timezone.utc).isoformat()
    for v in vacantes:  # lo que ya llega comprobado (por ejemplo, visto hoy en Indeed)
        if v["verificacion"]["estado"] == "verificada":
            cache[v["enlace"]] = {"url": v["enlace"], "estado": "verificada", "motivo": "vista hoy",
                                  "comprobada_en": ahora, "_titulo": v["titulo"]}
    r = verificar_enlaces.preparar(vacantes, set(), hoy(), cache, cfg=cfg_enlaces)
    return r, comprobadas


def test_primero_la_de_espanol_de_quien_va_corta_que_la_de_ingles_de_quien_ya_tiene(cfg, monkeypatch):
    # La persona en inglés ya tiene 5 candidatas comprobadas (su mínimo) y una más reciente por comprobar; la de español
    # tiene 8 candidatas y ninguna comprobada. Antes iba primero quien tenía menos candidatas en total (la de inglés).
    with ejecutor.activar({"revision": 1, "configuracion": cfg}, hoy()):
        ingles = [_vacante(n, EN) for n in range(1, 6)] + [_vacante(6, EN, verificada=False)]
        espanol = [_vacante(n, verificada=False) for n in range(10, 18)]
        for v in espanol:  # la de inglés por comprobar es la más reciente
            v["fecha_publicacion"] = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
        cola = verificar_enlaces.cola_por_necesidad(ingles + espanol, hoy())
        assert cola[0]["id"] in {v["id"] for v in espanol}
        r, comprobadas = _correr(monkeypatch, ingles + espanol, {"vacantes_por_corrida": 2, "segundos_corrida": 30})
    assert comprobadas[0] in {v["enlace"] for v in espanol}
    assert r["por_necesidad"] >= 1


def test_las_ya_comprobadas_no_ocupan_el_tope_de_quien_va_corta(cfg):
    # Meta 5 → tope de 10 candidatas. Las 9 más recientes de la persona en español ya están comprobadas: antes solo
    # quedaba 1 por abrir en su turno; ahora el tope cuenta las comprobadas y la cola trae lo que falta por abrir.
    with ejecutor.activar({"revision": 1, "configuracion": cfg}, hoy()):
        listas = [_vacante(n) for n in range(1, 10)]
        por_abrir = [_vacante(n, verificada=False) for n in range(10, 20)]
        for v in por_abrir:  # más antiguas: antes quedaban detrás de las ya comprobadas
            v["fecha_publicacion"] = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
        cola = verificar_enlaces.cola_por_necesidad(listas + por_abrir, hoy())
    assert {v["id"] for v in cola} <= {v["id"] for v in por_abrir}
    assert len(cola) == 1  # 10 del tope − 9 comprobadas


def test_lo_que_sobra_del_presupuesto_comprueba_las_demas_candidatas(cfg, monkeypatch):
    # 30 candidatas en español sin comprobar, tope de 10 y cupo de 100: antes quedaban sin abrir las que pasaban del
    # tope aunque sobrara presupuesto.
    with ejecutor.activar({"revision": 1, "configuracion": cfg}, hoy()):
        espanol = [_vacante(n, verificada=False) for n in range(1, 31)]
        _, comprobadas = _correr(monkeypatch, espanol, {"vacantes_por_corrida": 100, "segundos_corrida": 30})
    assert set(comprobadas) == {v["enlace"] for v in espanol}
    assert all(v["verificacion"]["estado"] == "verificada" for v in espanol)


def test_el_resto_respeta_el_cupo(cfg, monkeypatch):
    with ejecutor.activar({"revision": 1, "configuracion": cfg}, hoy()):
        espanol = [_vacante(n, verificada=False) for n in range(1, 31)]
        r, comprobadas = _correr(monkeypatch, espanol, {"vacantes_por_corrida": 12, "segundos_corrida": 30})
    assert len(comprobadas) <= 12 and r["candidatas_programadas"] <= 12
