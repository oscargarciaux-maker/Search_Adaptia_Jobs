"""Política de negocio: la ausencia de un país en la lista de exclusión nunca acredita cobertura."""
import pytest

from buscador import contrato, entrega, paises, vacante

TEXTO = "We are hiring a Product Designer to design digital products, research user needs and collaborate with engineering. " * 4


def oferta(ubicacion, titulo="Product Designer", descripcion=TEXTO, remoto=None):
    return vacante.crear(titulo,"Empresa", "https://jobs.lever.co/acme/regional", "Lever",
                        ubicacion=ubicacion, descripcion=descripcion, remoto=remoto, hoy="2026-11-06")


@pytest.mark.parametrize("lugar", ["Estonia", "Japan", "Ghana", "Bangladesh", "Morocco", "Saudi Arabia", "Atlantis"])
@pytest.mark.parametrize("modo", ["On-site", "Hybrid", "Remote"])
def test_ubicacion_extranjera_incluso_desconocida_no_se_entrega(lugar, modo):
    v = oferta(f"{lugar} ({modo})",remoto=True)
    assert contrato.entregable(v)
    elegidas,_ = entrega.elegir([v],{},"2026-11-06")
    assert not any(elegidas.values())


@pytest.mark.parametrize("lugar", ["Bogotá, Colombia", "Madrid, España", "Lima, Perú", "Mexico"])
@pytest.mark.parametrize("modo", ["On-site", "Hybrid", "Remote"])
def test_ubicacion_permitida_se_conserva_con_su_modalidad(lugar,modo):
    v = oferta(f"{lugar} ({modo})",remoto=True)
    assert not contrato.entregable(v)
    assert v["modalidad"] == {"On-site":"presencial","Hybrid":"hibrido","Remote":"remoto"}[modo]


@pytest.mark.parametrize("lugar", ["Global", "Worldwide", "Latin America", "EMEA", "Remote"])
@pytest.mark.parametrize("modo", ["On-site", "Hybrid"])
def test_modalidad_local_necesita_ubicacion_local_identificada(lugar, modo):
    assert contrato.entregable(oferta(f"{lugar} ({modo})",remoto=True))


@pytest.mark.parametrize("lugar", ["Ghana", "Madrid, Ghana", "Tartu, Estonia"])
def test_titulo_con_pais_o_ciudad_no_cambia_una_oficina_extranjera(lugar):
    assert contrato.entregable(oferta(lugar, titulo="Product Designer - Spain Madrid LATAM"))


@pytest.mark.parametrize("descripcion", ["We work in UTC-3 to UTC-5.", "Overlap with EST is required.", "Our clients are in LATAM.", "Work with our global team."])
def test_horario_clientes_y_texto_comercial_no_acreditan_elegibilidad(descripcion):
    assert contrato.entregable(oferta("Remote",descripcion=descripcion+" "+TEXTO))


def test_restricciones_sucesivas_no_se_ocultan_con_una_primera_permitida():
    v = oferta("Remote Worldwide",descripcion="You must be based in Colombia. You must be located in the United States. "+TEXTO)
    assert not v["paises"] and contrato.entregable(v)


def test_residencia_extranjera_tambien_restringe_un_anuncio_hibrido():
    v = oferta("Madrid, Spain (Hybrid)",descripcion="You must be based in Estonia. "+TEXTO)
    assert not v["paises"] and contrato.entregable(v)


@pytest.mark.parametrize("ubicacion", ["Tartu, Estonia", "Ghana", "Remote Worldwide"])
def test_empresa_extranjera_puede_contratar_remoto_mundial(ubicacion):
    v = oferta(ubicacion, titulo="Product Designer - Remote Worldwide")
    assert not contrato.entregable(v) and v["paises"] == paises.datos()["codigos"]


def test_presencialidad_obligatoria_prevalece_sobre_bandera_remota_de_la_fuente():
    v = oferta("Global",descripcion="This position is onsite. "+TEXTO,remoto=True)
    assert v["modalidad"] == "presencial" and contrato.entregable(v)


def test_bandera_hibrida_en_texto_prevalece_sobre_consulta_remota():
    v = oferta("Ghana",descripcion="This is a hybrid role. "+TEXTO,remoto=True)
    assert v["modalidad"] == "hibrido" and contrato.entregable(v)


def test_metadatos_sin_confianza_no_se_dan_por_confirmados():
    v = oferta("Remote Worldwide")
    v.pop("confianza_pais")
    assert contrato.entregable(v) == "elegibilidad regional por confirmar"


@pytest.mark.parametrize("descripcion", ["We are hiring worldwide.", "You can work from anywhere."])
def test_alcance_mundial_explicito_tambien_se_lee_en_descripcion(descripcion):
    v = oferta("Remote", descripcion=descripcion+" "+TEXTO)
    assert not contrato.entregable(v) and v["paises"] == paises.datos()["codigos"]


@pytest.mark.parametrize("descripcion", ["We are not hiring worldwide.", "You cannot work from anywhere."])
def test_negacion_no_se_convierte_en_invitacion_mundial(descripcion):
    assert contrato.entregable(oferta("Remote",descripcion=descripcion+" "+TEXTO))


@pytest.mark.parametrize("descripcion", ["Candidates must be legally authorized to work in the United States.", "Debes residir en Estonia.", "Es necesario vivir en un territorio sin identificar."])
def test_requisito_local_prevalece_sobre_la_etiqueta_mundial(descripcion):
    assert contrato.entregable(oferta("Remote Worldwide",descripcion=descripcion+" "+TEXTO))


@pytest.mark.parametrize("ubicacion,codigo", [("Madrid y alrededores","ES"),("Barcelona y alrededores","ES"),("Recife y alrededores","BR"),("Belo Horizonte y alrededores","BR"),("Área metropolitana de Lima","PE"),("Pamplona/Iruña","ES")])
def test_formatos_metropolitanos_conocidos_no_se_pierden(ubicacion,codigo):
    v = oferta(ubicacion)
    assert v["paises"] == [codigo] and not contrato.entregable(v)
