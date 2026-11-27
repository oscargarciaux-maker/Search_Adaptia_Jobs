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
