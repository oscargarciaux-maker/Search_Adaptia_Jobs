"""Contrato v11: rescate por persona hasta 5 — Apify sin fallos silenciosos, nuevos niveles, reutilizar y Apify dirigido."""
from datetime import date, timedelta

import pytest

from buscador import alertas, apify, entrega, familias, refuerzo, vacante
from buscador.fuentes import linkedin_apify
from panel import afinidad, ejecutor
from panel.modelos import Perfil
from panel.repositorio import configuracion_demo, hoy

CON_DATO = ("We require 3 years of experience. English B2 required. We design digital products, "
            "test software and work with engineering and user research. ") * 4
SIN_DATO = "We design digital products with a collaborative team and research users every week. " * 4


def _oferta(titulo, n, texto, empresa=None, ubicacion="Remote - Worldwide"):
    v = vacante.crear(titulo, empresa or f"Empresa {n}", f"https://jobs.lever.co/empresa/r-{n}", "Lever",
                      ubicacion=ubicacion, descripcion=texto, fecha=hoy(), hoy=hoy(), remoto=True)
    v["verificacion"] = {"estado": "verificada"}
    return v


@pytest.fixture
def cfg():
    c = configuracion_demo()
    for p in c["perfiles"][1:3]:
        p["activo"] = False  # Product Designer con un solo perfil: Colombia, remoto, 0–5 años, inglés ≤B2
    return c


def _elegir(cfg, ofertas, entregadas=None):
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        elegidas, resumen = entrega.elegir(ofertas, entregadas or {}, hoy())
        roles = entrega.config()["roles"]
    rid = "cargo:" + cfg["cargos"][0]["id"]
    return elegidas, resumen["roles"][rid], roles, rid


# ── Apify nunca falla en silencio ──────────────────────────────────────────────────────────────────────────────────

class ClienteRechazado:
    def __init__(self):
        self.ultimo_error, self.posts = None, 0

    def post_json(self, url, cuerpo, headers=None, timeout=None):
        self.posts += 1
        self.ultimo_error = {"http": 401, "tipo": "user-or-token-not-found", "mensaje": "Token is not valid"}
        return None


def test_clave_de_apify_rechazada_se_marca_se_detiene_y_alerta():
    cliente = ClienteRechazado()
    combos = [("qa", ["QA Engineer"], f"P{i}", {"location": "Colombia"}) for i in range(5)]
    crudas, stats = linkedin_apify.buscar(cliente, "curious_coder/linkedin-jobs-scraper", combos, {}, hoy(),
                                          token="token-ficticio", control_gasto=apify.Presupuesto({}, hoy()))
    assert crudas == [] and stats["clave_invalida"] and cliente.posts == 1 and "APIFY_TOKEN" in stats["error"]
    salud = {"fecha": hoy(), "fuentes": {"LinkedIn (Apify) rescate": stats},
             "entrega": {"vacantes": 120, "meta_cumplida": True, "roles": {}}}
    assert alertas.decidir("diario", "success", salud) == "fallo"
    _, _, texto = alertas.contenido("fallo", "diario", salud)
    assert "APIFY_TOKEN" in texto and "token-ficticio" not in texto


# ── Déficit por persona y niveles nuevos ───────────────────────────────────────────────────────────────────────────

def test_deficit_por_perfil_y_conteos_sin_datos_de_clientes(cfg):
    _, resumen, roles, _ = _elegir(cfg, [_oferta("Product Designer", n, CON_DATO) for n in range(2)])
    assert resumen["perfiles_bajo_minimo"] == 1 and resumen["faltan_para_minimo"] == 3
    assert cfg["perfiles"][0]["id"] not in str(resumen) and cfg["clientes"][0]["id"] not in str(resumen)  # solo conteos


def test_experiencia_cercana_solo_cuando_faltan(cfg):
    pide_7 = CON_DATO.replace("3 years", "7 years")  # el perfil admite 0–5: 7 está a 2 años
    pide_9 = CON_DATO.replace("3 years", "9 years")
    elegidas, resumen, _, rid = _elegir(cfg, [_oferta("Product Designer", 1, pide_7), _oferta("Product Designer", 2, pide_9)])
    marcas = [v.get("_ampliacion") for v, _ in elegidas[rid]]
    assert marcas == ["experiencia_cercana"] and resumen["ampliadas"] == {"experiencia_cercana": 1}
    p = Perfil.model_validate(cfg["perfiles"][0])
    assert afinidad.relajado(p, "experiencia_cercana").experiencia_max == 7


def test_hasta_cuatro_por_empresa_si_el_cargo_no_llega_al_cupo(cfg):
    misma = [_oferta(f"Product Designer {'Sr' if n % 2 else 'Jr'} {n}", n, CON_DATO + f" Equipo {n}, sede {n * 7}.",
                     empresa="Única S.A.") for n in range(6)]
    elegidas, resumen, _, rid = _elegir(cfg, misma)
    assert len(elegidas[rid]) == 4  # 2 normales + 2 por el último recurso, nunca más de 4
    assert sum(v.get("_ampliacion") == "empresa_4" for v, _ in elegidas[rid]) == 2


# ── Reutilizar entre personas ──────────────────────────────────────────────────────────────────────────────────────

def test_reutiliza_vacantes_de_dias_anteriores_sin_repetir_a_la_misma_persona(cfg):
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    rid = "cargo:" + cfg["cargos"][0]["id"]
    p = cfg["perfiles"][0]
    previas = [{"vacante_id": f"v{n:015d}", "delivery_date": ayer, "role_id": rid, "match_grade": "exact",
                "snapshot": dict(_oferta("Product Designer", 50 + n, CON_DATO), id=f"v{n:015d}")} for n in range(8)]
    hoy_rows = [{"vacante_id": "h000000000000001", "delivery_date": hoy(), "role_id": rid, "match_grade": "exact",
                 "snapshot": _oferta("Product Designer", 1, CON_DATO)}]
    asignaciones = []

    class Repo:
        ejecucion = None

        def pedir(self, metodo, ruta, **op):
            params = op.get("params") or {}
            if ruta == "panel_ejecuciones":
                if metodo == "GET":
                    return [self.ejecucion] if self.ejecucion else []
                if metodo == "POST":
                    self.ejecucion = {"id": "e1", **op["json"]}
                if metodo == "PATCH":
                    self.ejecucion.update(op["json"])
            elif ruta == "entregas_diarias":
                if params.get("delivery_date", "").startswith("eq."):
                    return hoy_rows
                return previas if not params.get("offset") else []
            elif ruta == "panel_asignaciones":
                if metodo == "GET":  # ya recibió v000…000 en una asignación anterior
                    return [{"perfil_id": p["id"], "vacante_id": previas[0]["vacante_id"]}] if not params.get("offset") else []
                asignaciones.extend(op["json"])
            elif ruta == "panel_borradores":  # y v000…001 le fue en un mensaje
                return [{"cliente_id": p["cliente_id"], "vacantes": [previas[1]["vacante_id"]]}] if not params.get("offset") else []
            return []
    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    mias = [a for a in asignaciones if a["perfil_id"] == p["id"]]
    ids = [a["vacante_id"] for a in mias]
    assert len(mias) == 5 and "h000000000000001" in ids  # 1 de hoy + 4 reutilizadas
    assert previas[0]["vacante_id"] not in ids and previas[1]["vacante_id"] not in ids
    assert sum(any(isinstance(e, dict) and e.get("reutilizada") == ayer for e in a["explicacion"]) for a in mias) == 4
    assert repo.ejecucion["resumen"]["reutilizadas"] >= 4


# ── Apify dirigido a quien le falta ────────────────────────────────────────────────────────────────────────────────

def test_rescate_apify_busca_solo_para_perfiles_con_deficit(cfg):
    cfg["perfiles"][0].update(vive_en="MX", modalidades=["remoto"])
    llamadas = []

    def buscar_apify(combinaciones):
        llamadas.append(combinaciones)
        return [], {"busquedas": len(combinaciones)}
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        suficientes = []
        for cargo in cfg["cargos"][1:]:
            titulo = {"Frontend": "Frontend Developer", "QA": "QA Engineer"}[cargo["nombre"]]
            suficientes += [_oferta(titulo, f"{cargo['nombre']}{n}", CON_DATO) for n in range(6)]
        ofertas = [_oferta("Product Designer", 1, CON_DATO)] + suficientes
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        _, stats = refuerzo.rescate_apify(ofertas, {}, hoy(), entrega.config(), familias.mapa(), buscar_apify,
                                          lambda a, b: a + b, max_busquedas=4)
    combos = llamadas[0]
    assert stats["perfiles_con_deficit"] >= 1 and len(combos) <= 4
    pd = "cargo:" + cfg["cargos"][0]["id"]
    assert combos[0][0] == pd and {c[2] for c in combos if c[0] == pd} >= {"REMOTO_MX", "REMOTO"}


def test_sin_deficit_no_gasta_apify(cfg):
    llamadas = []
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        ofertas = []
        for cargo in cfg["cargos"]:
            titulo = {"Product Designer": "Product Designer", "Frontend": "Frontend Developer", "QA": "QA Engineer"}[cargo["nombre"]]
            ofertas += [_oferta(titulo, f"{cargo['nombre']}{n}", CON_DATO) for n in range(6)]
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        _, stats = refuerzo.rescate_apify(ofertas, {}, hoy(), entrega.config(), familias.mapa(),
                                          lambda c: llamadas.append(c) or ([], {}), lambda a, b: a + b)
    assert not llamadas and stats["perfiles_con_deficit"] == 0


def test_en_modo_panel_apify_no_rota_a_ciegas(cfg):
    _, _, motor = ejecutor.preparar({"configuracion": cfg}, hoy())
    assert motor["presupuestos"]["apify_busquedas"] == 0
