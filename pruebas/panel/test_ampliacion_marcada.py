"""P-7.A (27 nov): lo que el panel ofrece «fuera de lo pedido» a un perfil presencial o híbrido es la ampliación prevista
`remota_cercana` (contratos v9 y v27): solo hasta el mínimo de 5, solo remotas abiertas al país donde vive, marcada en
el panel y sin la marca en el texto de WhatsApp (v9). En la línea base (escenarios b y e) eran las 32 «fuera»."""
from datetime import datetime, timezone

import pytest

from buscador import entrega, familias, vacante
from panel import ejecutor, servicio
from panel.afinidad import ETIQUETAS_AMPLIACION, MINIMO_POR_PERFIL
from panel.repositorio import configuracion_demo, hoy

TEXTO = "We design digital products with a collaborative team and research users every week. " * 4


def _oferta(n, ubicacion, remoto):
    v = vacante.crear("Product Designer", f"Empresa {n}", f"https://jobs.lever.co/empresa/marca-{n}", "Lever",
                      ubicacion=ubicacion, descripcion=TEXTO, fecha=hoy(), hoy=hoy(), remoto=remoto)
    v["verificacion"] = {"estado": "verificada", "enlaces": [{"url": v["enlace"], "estado": "verificada",
                                                              "comprobada_en": datetime.now(timezone.utc).isoformat()}]}
    return v


@pytest.fixture
def cfg():
    cfg = configuracion_demo()
    for p in cfg["perfiles"][1:3]:
        p["activo"] = False  # Product Designer queda con un solo perfil: el de Colombia
    p = cfg["perfiles"][0]
    p.update(aceptar_experiencia_sin_dato=True, aceptar_ingles_sin_dato=True,
             ubicaciones=[{"paises": ["CO"], "ciudades": ["Bogotá"], "modalidades": ["presencial"]}])
    return cfg


def _elegir(cfg, ofertas):
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for v in ofertas:  # como hace la bodega al reetiquetar con el mapa del panel
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        elegidas, _ = entrega.elegir(ofertas, {}, hoy())
    return elegidas["cargo:" + cfg["cargos"][0]["id"]]


def test_presencial_corto_recibe_remotas_de_su_pais_solo_hasta_el_minimo_y_marcadas(cfg):
    en_su_ciudad = _oferta(0, "Bogotá, Colombia", None)  # presencial en Bogotá: cumple tal cual
    remotas = [_oferta(10 + n, "Remote - Colombia", True) for n in range(8)]
    de_otro_pais = _oferta(30, "Remote - Brazil", True)  # remota cerrada a Colombia: nunca entra
    elegidas = _elegir(cfg, [en_su_ciudad, *remotas, de_otro_pais])
    marcas = {v["empresa"]: v.get("_ampliacion") for v, _ in elegidas}
    assert marcas.pop("Empresa 0") is None  # lo que cumple no se marca
    assert set(marcas.values()) == {"remota_cercana"}
    assert len(marcas) == MINIMO_POR_PERFIL - 1  # completa hasta 5, no hasta la meta (10)
    assert "Empresa 30" not in marcas


def test_la_ampliada_se_ve_marcada_en_el_panel_y_el_whatsapp_no_lleva_la_marca(cfg):
    rid = "cargo:" + cfg["cargos"][0]["id"]
    ampliada = [v for v, _ in _elegir(cfg, [_oferta(10, "Remote - Colombia", True)])][0]
    assert ampliada["_ampliacion"] == "remota_cercana"
    asignaciones = []

    class Repo:
        ejecucion = None

        def pedir(self, metodo, ruta, **op):
            if ruta == "panel_ejecuciones":
                if metodo == "GET":
                    return [self.ejecucion] if self.ejecucion else []
                if metodo == "POST":
                    self.ejecucion = {"id": "e1", **op["json"]}
                if metodo == "PATCH":
                    self.ejecucion.update(op["json"])
            elif ruta == "entregas_diarias":
                return [{"role_id": rid, "vacante_id": ampliada["id"], "match_grade": "exact", "snapshot": ampliada}]
            elif ruta == "panel_asignaciones":
                asignaciones.extend(op["json"])

    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    assert any({"ampliacion": "remota_cercana"} in a["explicacion"] for a in asignaciones)
    assert repo.ejecucion["resumen"]["ampliadas"] == 1
    fila = dict(asignaciones[0], catalogo_vacantes={"id": ampliada["id"], "status": "active", "datos": ampliada,
                                                    "description_full": TEXTO})

    class Resultados:
        def resultados(self, cliente_id, fecha):
            return {"ejecucion": repo.ejecucion, "clientes": [], "filas": [fila]}

    v = servicio.resultados(Resultados())["vacantes"][0]
    assert v["estado"] == "lista" and v["ampliacion"] == ETIQUETAS_AMPLIACION["remota_cercana"]
    texto = servicio.whatsapp(Resultados(), None)["texto"]
    # La vacante sí va al mensaje (dice «Remoto»), pero sin la marca técnica (contrato v9).
    assert "Product Designer · Empresa 10 (Remoto)" in texto and "mpliad" not in texto
