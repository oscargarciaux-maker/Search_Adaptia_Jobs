"""P-7.A (27 nov): lo que el panel ofrece «fuera de lo pedido» a un perfil presencial o híbrido es la ampliación prevista
`remota_cercana` (contratos v9 y v27): solo hasta el mínimo de 5, solo remotas abiertas al país donde vive o mundiales,
marcada en el panel y sin la marca en el texto de WhatsApp (v9). En la línea base (escenarios b y e) eran las 32 «fuera».
La misma comprobación para `sin_dato` está en `test_control.py::test_registro_v27_…`."""
from datetime import datetime, timezone

import pytest

from panel import ejecutor, servicio
from panel.afinidad import ETIQUETAS_AMPLIACION, MINIMO_POR_PERFIL
from panel.repositorio import hoy
from pruebas.panel.test_control import SIN_DATO, _elegir, _oferta, cfg, cfg_un_perfil  # noqa: F401 (fixtures)


@pytest.fixture
def presencial(cfg_un_perfil):  # noqa: F811 (la fixture importada de test_control)
    cfg_un_perfil["perfiles"][0].update(aceptar_experiencia_sin_dato=True, aceptar_ingles_sin_dato=True,
                                       ubicaciones=[{"paises": ["CO"], "ciudades": ["Bogotá"],
                                                     "modalidades": ["presencial"]}])
    return cfg_un_perfil


def _ofertas(*lugares):
    return [_oferta("Product Designer", n, SIN_DATO, ubicacion=u, remoto=r) for n, (u, r) in lugares]


def test_presencial_corto_recibe_remotas_de_su_pais_solo_hasta_el_minimo(presencial):
    ofertas = _ofertas((0, ("Bogotá, Colombia", None)),  # presencial en su ciudad: cumple tal cual
                       *((10 + n, ("Remote - Colombia", True)) for n in range(8)))
    marcas = {v["empresa"]: v.get("_ampliacion") for v, _ in _elegir(presencial, ofertas)[0]}
    assert marcas.pop("Empresa 0") is None  # lo que cumple no se marca
    assert set(marcas.values()) == {"remota_cercana"}
    assert len(marcas) == MINIMO_POR_PERFIL - 1  # en la selección del día completa hasta 5, no hasta la meta


def test_una_remota_cerrada_a_otro_pais_nunca_entra_por_ampliacion(presencial):
    sola = _ofertas((30, ("Remote - Brazil", True)))  # única candidata: si fuera compatible, entraría
    assert _elegir(presencial, sola)[0] == []


class _Registro:
    """Repositorio mínimo para `ejecutor.registrar` con una sola vacante en el lote del día."""
    ejecucion = None

    def __init__(self, rid, v):
        self.rid, self.v, self.asignaciones = rid, v, []

    def pedir(self, metodo, ruta, **op):
        if ruta == "panel_ejecuciones":
            if metodo == "GET":
                return [self.ejecucion] if self.ejecucion else []
            self.ejecucion = {"id": "e1", **(self.ejecucion or {}), **op["json"]}
        elif ruta == "entregas_diarias":
            return [{"role_id": self.rid, "vacante_id": self.v["id"], "match_grade": "exact", "snapshot": self.v}]
        elif ruta == "panel_asignaciones":
            self.asignaciones.extend(op["json"])

    def resultados(self, cliente_id, fecha):
        fila = dict(self.asignaciones[0], catalogo_vacantes={"id": self.v["id"], "status": "active", "datos": self.v,
                                                             "description_full": SIN_DATO})
        return {"ejecucion": self.ejecucion, "clientes": [], "filas": [fila]}


def test_la_ampliada_se_ve_marcada_en_el_panel_y_el_whatsapp_no_lleva_la_marca(presencial):
    ampliada = _elegir(presencial, _ofertas((10, ("Remote - Colombia", True))))[0][0][0]
    assert ampliada["_ampliacion"] == "remota_cercana"
    ampliada["verificacion"]["enlaces"] = [{"url": ampliada["enlace"], "estado": "verificada",
                                            "comprobada_en": datetime.now(timezone.utc).isoformat()}]
    repo = _Registro("cargo:" + presencial["cargos"][0]["id"], ampliada)
    ejecutor.registrar(repo, {"revision": 1, "configuracion": presencial}, hoy())
    assert repo.ejecucion["resumen"]["ampliadas"] == 1
    v = servicio.resultados(repo)["vacantes"][0]
    assert v["estado"] == "lista" and v["ampliacion"] == ETIQUETAS_AMPLIACION["remota_cercana"]
    texto = servicio.whatsapp(repo, None)["texto"]
    # La vacante sí va al mensaje (dice «Remoto»), pero sin la marca técnica (contrato v9).
    assert "Product Designer · Empresa 10 (Remoto)" in texto and "mpliad" not in texto


# ── Decisión de Oscar (27 nov, 7.A): la ampliación solo completa hasta 5, también al reutilizar y al rescatar ──────

def _comprobada(n, ubicacion, remoto):
    from buscador import familias
    v = _oferta("Product Designer", n, SIN_DATO, ubicacion=ubicacion, remoto=remoto)
    v["verificacion"]["enlaces"] = [{"url": v["enlace"], "estado": "verificada",
                                     "comprobada_en": datetime.now(timezone.utc).isoformat()}]
    v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
    return v


class _Supabase:
    """Lote de hoy vacío; `previas` son las entregas de días anteriores (para reutilizar)."""
    ejecucion = None

    def __init__(self, previas=()):
        self.previas, self.asignaciones = list(previas), []

    def pedir(self, metodo, ruta, **op):
        params = op.get("params") or {}
        if ruta == "panel_ejecuciones":
            if metodo == "GET":
                return [self.ejecucion] if self.ejecucion else []
            self.ejecucion = {"id": "e1", **(self.ejecucion or {}), **op["json"]}
        elif ruta == "entregas_diarias" and str(params.get("delivery_date", "")).startswith("gte.") \
                and not params.get("offset"):
            return self.previas
        elif ruta == "panel_asignaciones" and metodo == "POST":
            self.asignaciones.extend(op["json"])
        return []


@pytest.fixture
def meta_diez(presencial):
    presencial["perfiles"][0]["meta_diaria"] = 10
    return presencial


def _recibidas(repo, configuracion):
    p = configuracion["perfiles"][0]["id"]
    return [a for a in repo.asignaciones if a["perfil_id"] == p]


def _ampliadas(filas):
    return sum(any(isinstance(e, dict) and e.get("ampliacion") for e in f["explicacion"]) for f in filas)


def test_el_rescate_no_pasa_de_5_con_remotas_para_un_perfil_presencial(meta_diez):
    bodega = [_comprobada(n, "Bogotá, Colombia", None) for n in range(2)] + \
             [_comprobada(10 + n, "Remote - Colombia", True) for n in range(8)]
    repo = _Supabase()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": meta_diez}, hoy(), vacantes=bodega, cache_enlaces={})
    filas = _recibidas(repo, meta_diez)
    # Las 2 presenciales de su ciudad y 3 remotas hasta llegar a 5; antes llegaba a 10 con 8 remotas.
    assert len(filas) == MINIMO_POR_PERFIL and _ampliadas(filas) == MINIMO_POR_PERFIL - 2


def test_reutilizar_no_pasa_de_5_con_remotas_para_un_perfil_presencial(meta_diez):
    from datetime import date, timedelta
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    previas = [{"delivery_date": ayer, "role_id": "otro", "vacante_id": v["id"], "match_grade": "exact", "snapshot": v}
               for v in [_comprobada(10 + n, "Remote - Colombia", True) for n in range(8)]]
    repo = _Supabase(previas)
    ejecutor.registrar(repo, {"revision": 1, "configuracion": meta_diez}, hoy())
    filas = _recibidas(repo, meta_diez)
    assert len(filas) == MINIMO_POR_PERFIL and _ampliadas(filas) == MINIMO_POR_PERFIL


def test_de_5_a_la_meta_sigue_entrando_lo_que_cumple_el_perfil(meta_diez):
    from datetime import date, timedelta
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    previas = [{"delivery_date": ayer, "role_id": "otro", "vacante_id": v["id"], "match_grade": "exact", "snapshot": v}
               for v in [_comprobada(10 + n, "Remote - Colombia", True) for n in range(8)]]
    en_su_ciudad = [_comprobada(n, "Bogotá, Colombia", None) for n in range(3)]
    repo = _Supabase(previas)  # reutilizar da primero 5 remotas; el rescate, después, las 3 de su ciudad
    ejecutor.registrar(repo, {"revision": 1, "configuracion": meta_diez}, hoy(), vacantes=en_su_ciudad,
                       cache_enlaces={})
    filas = _recibidas(repo, meta_diez)
    assert _ampliadas(filas) == MINIMO_POR_PERFIL and len(filas) == MINIMO_POR_PERFIL + 3


class _ConPasadaAnterior(_Supabase):
    """Lote de hoy con una ampliada nueva y 5 vacantes que la persona ya recibió en una pasada anterior de hoy."""
    def __init__(self, lote, perfil_id, ya):
        super().__init__()
        self.lote, self.ya = lote, {perfil_id: set(ya)}

    def asignadas_de(self, ejecucion_id):
        return self.ya

    def pedir(self, metodo, ruta, **op):
        if ruta == "entregas_diarias" and (op.get("params") or {}).get("delivery_date") == "eq." + hoy():
            return self.lote
        return super().pedir(metodo, ruta, **op)


def test_lo_de_una_pasada_anterior_de_hoy_cuenta_para_el_tope_de_5(meta_diez):
    rid = "cargo:" + meta_diez["cargos"][0]["id"]
    nueva = dict(_comprobada(10, "Remote - Colombia", True), _ampliacion="remota_cercana")
    lote = [{"role_id": rid, "vacante_id": nueva["id"], "match_grade": "exact", "snapshot": nueva}]
    repo = _ConPasadaAnterior(lote, meta_diez["perfiles"][0]["id"], [f"antes-{n}" for n in range(5)])
    ejecutor.registrar(repo, {"revision": 1, "configuracion": meta_diez}, hoy())
    assert _recibidas(repo, meta_diez) == []  # ya tenía 5 hoy: la ampliada no entra
    repo = _ConPasadaAnterior(lote, meta_diez["perfiles"][0]["id"], [f"antes-{n}" for n in range(4)])
    ejecutor.registrar(repo, {"revision": 1, "configuracion": meta_diez}, hoy())
    assert len(_recibidas(repo, meta_diez)) == 1  # con 4, sí completa la quinta
