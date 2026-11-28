"""Contrato v37: más vacantes para quien va corto y cobertura por persona medida, sin promesas. Incluye la matriz de
oficios que no están en el mapa (contador, enfermero, docente, ejecutivo de ventas, ingeniero industrial, coordinador
logístico)."""
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from buscador import cobertura
from buscador.fuentes import linkedin_publico
from panel import ejecutor, servicio
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy
from panel.terminos import grado, sugerir


@pytest.fixture(autouse=True)
def _limpio():
    cobertura.configurar_primero()
    yield
    cobertura.configurar_primero()


def test_los_lugares_de_quien_va_corto_van_primero():
    combos = [("f", ["x"], "REMOTO", {}), ("f", ["x"], "CO", {}), ("f", ["x"], "CIUDAD_CHICAGO", {}),
              ("f", ["x"], "US:REMOTO", {})]
    estado = {"f@CIUDAD_CHICAGO": "2026-11-16", "f@US:REMOTO": "2026-11-16"}  # recién buscados
    assert [c[2] for c in cobertura.repartir(combos, estado, "2026-11-17")][:2] == ["REMOTO", "CO"]
    cobertura.configurar_primero({"f": ["CIUDAD_CHICAGO", "US"]})
    orden = [c[2] for c in cobertura.repartir(combos, estado, "2026-11-17")]
    assert set(orden[:2]) == {"CIUDAD_CHICAGO", "US:REMOTO"}  # «US» también cubre «US:REMOTO» (Indeed)


def test_preparar_marca_los_lugares_de_los_perfiles_cortos():
    cfg = configuracion_demo()
    p = cfg["perfiles"][0]
    p.update(vive_en="US", modalidades=["remoto", "hibrido"], ciudades=["Chicago"], ubicaciones=[])
    _, _, motor = ejecutor.preparar({"revision": 1, "configuracion": cfg}, hoy(), cortos={p["id"]})
    lugares = motor["lugares_primero"]["cargo:" + p["cargo_id"]]
    assert {"CIUDAD_CHICAGO", "US", "REMOTO_US"} <= set(lugares)
    _, _, motor = ejecutor.preparar({"revision": 1, "configuracion": cfg}, hoy())
    assert motor["lugares_primero"] == {}


def test_perfiles_cortos_con_la_ultima_busqueda():
    cfg = configuracion_demo()
    ids = [p["id"] for p in cfg["perfiles"] if p.get("activo", True)]

    class Repo:
        def ejecuciones(self):
            return [{"id": "e2", "fecha": hoy()}, {"id": "e1", "fecha": "2026-01-01"}]

        def conteo_asignaciones(self, ejecucion, perfiles):
            assert ejecucion == "e2"
            return Counter({ids[0]: 7, ids[1]: 2})
    cortos = ejecutor.perfiles_cortos(Repo(), {"revision": 1, "configuracion": cfg}, hoy())
    assert ids[0] not in cortos and ids[1] in cortos and set(ids[2:]) <= cortos  # sin nada = corto (nuevo)

    class Roto:
        def ejecuciones(self):
            raise RuntimeError("sin red")
    assert ejecutor.perfiles_cortos(Roto(), {"revision": 1, "configuracion": cfg}, hoy()) == set()


class _R:
    def __init__(self, texto):
        self.text, self.status_code = texto, 200


def test_linkedin_deja_la_mitad_del_tiempo_para_leer_fichas():
    reloj = [0.0]

    class Cliente:
        fichas = 0

        def get(self, url, params=None):
            reloj[0] += 10
            if "jobPosting/" in url:
                Cliente.fichas += 1
                return _R('<div class="show-more-less-html__markup">' + "Texto del aviso. " * 30 + "</div>")
            n = int(reloj[0])
            return _R("".join(f'<li><div data-entity-urn="urn:li:jobPosting:{n}{i}"><h3 class="base-search-card__title">'
                              f'Product Designer</h3></div></li>' for i in range(10)))
    mapa = [{"id": "f", "consultas": ["Product Designer"],
             "lugares": [(f"L{i}", {"location": f"L{i}"}) for i in range(30)]}]
    _, stats = linkedin_publico.buscar(Cliente(), mapa, [], {}, 500, max_fichas=500, max_paginas=1,
                                       reloj=lambda: reloj[0], limite_segundos=200)
    assert stats["busquedas"] == 10 and Cliente.fichas >= 9  # 100 s buscando y el resto leyendo fichas


def test_cobertura_por_persona_en_la_demostracion():
    r = servicio.cobertura(RepositorioDemo())
    assert r["perfiles"] and {f["estado"] for f in r["perfiles"]} <= {"cubierto", "pendiente", "sin_datos"}
    corto = next(f for f in r["perfiles"] if f["hoy"] < r["minimo"])
    assert corto["estado"] == "sin_datos" and corto["causa"]  # la demo solo tiene una búsqueda
    assert all(f["listas"] >= 0 and f["por_comprobar"] >= 0 for f in r["perfiles"])
    assert set(r["grupos"]) == {"cargo", "pais", "idioma"} and "no es una promesa" in r["nota"]


def test_cobertura_avisa_a_quien_lleva_3_dias_bajo_el_minimo():
    repo = RepositorioDemo()
    cfg = configuracion_demo()
    pid = next(p["id"] for p in cfg["perfiles"] if p.get("activo", True))
    repo.ejecuciones = lambda: [{"id": f"e{i}", "fecha": "2026-11-1" + str(7 - i), "revision": 1} for i in range(4)]
    repo.asignaciones_por_perfil = lambda ids: Counter({(e, pid): 2 for e in ids})
    r = servicio.cobertura(repo, "2026-11-17")
    fila = next(f for f in r["perfiles"] if f["perfil_id"] == pid)
    assert fila["estado"] == "pendiente" and fila["dias_seguidos_bajo"] == 4 and fila["dias_con_minimo"] == 0
    assert fila["dias_medidos"] == 4 and any("3 o más días" in a for a in r["alertas"])


def test_api_de_cobertura():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    r = api.get("/api/cobertura")
    assert r.status_code == 200 and r.json()["minimo"] == servicio.AVISO_BAJO == 10  # P-11.3: la meta, no el rescate


# ── Matriz de oficios que no están en el mapa ───────────────────────────────────────────────────────────────────────
def _cargo(nombre):
    s = sugerir(nombre, consultar_esco=False)  # ESCO caído: el cargo sigue con su nombre
    return {"nombre": nombre, "terminos_exactos": s["terminos_exactos"] or [nombre],
            "terminos_similares": s["terminos_similares"], "terminos_excluidos": [],
            "terminos_cercanos": s.get("terminos_cercanos", [])}


@pytest.mark.parametrize("nombre,sirven,no_sirven", [
    ("Contador", ["Contador Público", "Contadora senior"], ["Auxiliar contable", "Analista de cuentas por pagar"]),
    ("Enfermero", ["Enfermera", "Enfermero jefe de piso"], ["Auxiliar de enfermería"]),
    ("Docente", ["Docente de matemáticas", "Docente universitaria"], ["Coordinador académico"]),
    ("Ejecutivo de ventas", ["Ejecutiva de ventas", "Sales Executive"], ["Gerente de ventas"]),
    ("Ingeniero industrial", ["Ingeniera industrial"], ["Ingeniero civil", "Ingeniero de procesos"]),
    ("Coordinador logístico", ["Coordinadora logística"], ["Coordinador de marketing", "Jefe de bodega"]),
])
def test_oficios_nuevos_coinciden_sin_mezclar_otros(nombre, sirven, no_sirven):
    cargo = _cargo(nombre)
    for t in sirven:
        assert grado(t, cargo, cercanos=True)[0] in ("exacto", "similar"), t
    for t in no_sirven:  # una función parecida no convierte otro oficio en equivalente
        assert grado(t, cargo, cercanos=True)[0] is None, t


def test_sin_esco_el_cargo_nuevo_busca_por_su_nombre_y_pide_revision():
    s = sugerir("Coordinador logístico", consultar_esco=False)
    assert s["terminos_exactos"] == ["Coordinador logístico"] and s["requiere_revision"]
