"""Contrato v12: reglas de la limpieza única (sin base de datos; el ensayo con SQL está en probar_limpieza.py)."""
from buscador import catalogo, limpiar_idioma_pais as limpieza, vacante
from pruebas.probar_limpieza import ESPANOL, INGLES, PORTUGUES, _vacante


def _fila(v):
    return catalogo.fila(v, "2026-11-07T00:00:00Z")


def test_motivos_y_plan_solo_con_conteos():
    pt = _vacante(1, "Remote - LATAM", PORTUGUES, True, idioma="es")           # guardada como «es» antes del arreglo
    br = _vacante(2, "Curitiba, PR, Brazil (Hybrid)", INGLES, paises=["BR"])
    varios = _vacante(3, "Remote - Latin America", INGLES, True, paises=["AR", "BR", "CO", "MX"])
    es = _vacante(4, "Bogotá, Colombia (Híbrido)", ESPANOL)
    filas = [_fila(v) for v in (pt, br, varios, es)]
    assert [limpieza.motivo_catalogo(f) for f in filas] == [limpieza.MOTIVO_IDIOMA, limpieza.MOTIVO_PAIS, "", ""]
    ofertas = [{"id": 1, "external_id": "otro-id", "offer_url": pt["enlace"] + "?utm_source=x", "vacante_id": None},
               {"id": 2, "external_id": br["id"], "offer_url": "", "vacante_id": None},
               {"id": 3, "external_id": varios["id"], "offer_url": varios["enlace"], "vacante_id": varios["id"]},
               {"id": 4, "external_id": "viejo", "offer_url": "", "vacante_id": None, "hire_countries": ["BR"]},
               {"id": 5, "external_id": "viejo-2", "offer_url": "", "vacante_id": None, "hire_countries": ["BR", "CO"]}]
    marcadas, borrar, resumen = limpieza.planificar(filas, ofertas)
    assert set(marcadas) == {pt["id"], br["id"]} and set(borrar) == {1, 2, 4}
    assert resumen["ofertas_por_motivo"] == {limpieza.MOTIVO_IDIOMA: 1, limpieza.MOTIVO_PAIS: 2}
    assert "Product Designer" not in str(resumen) and "lever" not in str(resumen)


def test_remota_de_varios_paises_se_conserva_aunque_nombre_brasil():
    v = vacante.crear("Product Designer", "A", "https://jobs.lever.co/a/9", "Lever",
                      ubicacion="Argentina (Remote); Mexico (Remote); São Paulo, Brazil", descripcion=INGLES,
                      fecha="2026-11-06", remoto=True, hoy="2026-11-07")
    v["paises"] = ["AR", "BR", "MX"]  # como quedó guardada antes del contrato v12
    assert limpieza.motivo_catalogo(_fila(v)) == ""
