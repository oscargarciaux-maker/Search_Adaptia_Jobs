"""Regla de países: ubicaciones como las publican LinkedIn, Indeed y los sistemas de postulación."""
import pytest

from buscador import paises

TODOS = paises.datos()["codigos"]
LATAM = paises.datos()["latam"]

# (título, ubicación, descripción, remoto, países esperados, confianza esperada o None)
CASOS = [
    # Presencial o híbrido en un país
    ("Product Designer", "Bogota, D.C., Capital District, Colombia", "", None, ["CO"], "alta"),
    ("Diseñador UX", "Medellín, Antioquia, Colombia", "", None, ["CO"], "alta"),
    ("UX Designer", "São Paulo, State of São Paulo, Brazil", "", None, [], "alta"),  # v12: Brasil fuera de la cobertura
    ("Desarrollador Backend", "Ciudad de México, CDMX, México", "", None, ["MX"], "alta"),
    ("Frontend Developer", "Lima, Peru", "", None, ["PE"], "alta"),
    ("Editor de video", "Caracas, Distrito Capital, Venezuela", "", None, ["VE"], "alta"),
    ("QA Analyst", "San José, San José, Costa Rica", "", None, ["CR"], "alta"),
    ("Data Analyst", "Santiago, Santiago Metropolitan Region, Chile", "", None, ["CL"], "alta"),
    ("Diseñador UI (Híbrido)", "Guadalajara, Jalisco, México", "", None, ["MX"], "alta"),
    ("Analista de datos", "Quito, Pichincha, Ecuador", "", None, ["EC"], "alta"),
    ("Desarrollador", "Montevideo, Uruguay", "", None, ["UY"], "alta"),
    ("Product Designer", "Buenos Aires, Argentina", "", None, ["AR"], "alta"),
    ("Diseñador gráfico", "Santo Domingo, República Dominicana", "", None, ["DO"], "alta"),
    ("Developer", "Ciudad de Panamá, Panamá", "", None, ["PA"], "alta"),
    ("Motion designer", "Asunción, Paraguay", "", None, ["PY"], "alta"),
    ("Soporte TI", "Tegucigalpa, Honduras", "", None, ["HN"], "alta"),
    ("UX Researcher", "Ciudad de Guatemala, Guatemala", "", None, ["GT"], "alta"),
    ("Desarrollador web", "San Salvador, El Salvador", "", None, ["SV"], "alta"),
    ("Ilustrador", "La Paz, Bolivia", "", None, ["BO"], "alta"),
    ("Programador", "Managua, Nicaragua", "", None, ["NI"], "alta"),
    # Presencial fuera de LATAM
    ("Product Designer", "New York, NY, United States", "", None, [], "alta"),
    ("UX Designer", "Madrid, Comunidad de Madrid, España", "", None, ["ES"], "alta"),
    ("UX Designer", "Lisbon, Portugal", "", None, [], "alta"),
    ("Video Editor", "London, England, United Kingdom", "", None, [], "alta"),
    ("Test Engineer", "Santa Ana, California, United States", "", None, [], "alta"),
    # Remoto en un país
    ("Product Designer", "Colombia", "", True, ["CO"], "media"),
    ("UX/UI Designer - Remote", "Mexico", "", None, ["MX"], "media"),
    ("Desarrollador Full Stack (Remoto)", "Venezuela", "", None, ["VE"], "media"),
    ("Senior Designer", "Remote, Brazil", "", None, [], "media"),  # v12: remota solo para Brasil
    # Remoto en una lista de países
    ("Backend Engineer", "Remote - Mexico, Colombia, Argentina", "", None, ["MX", "CO", "AR"], "alta"),
    # Remoto para toda LATAM o el mundo
    ("Product Designer", "Latin America", "", True, LATAM, "alta"),
    ("UX Designer (Remote LATAM)", "", "", None, LATAM, "alta"),
    ("Video Editor", "Remote - Worldwide", "", None, TODOS, "alta"),
    ("Frontend Developer", "Anywhere", "", None, TODOS, "alta"),
    ("QA Engineer", "Remote (Americas)", "", None, LATAM, "alta"),
    ("Designer", "Remote - South America", "", None, ["AR", "BO", "CL", "CO", "EC", "PE", "PY", "UY", "VE"], "alta"),
    # Remoto fuera de LATAM
    ("Product Designer", "Remote - US", "", None, [], "alta"),
    ("UX Designer", "United States (Remote)", "", None, [], "alta"),
    ("Developer", "Remote - Europe", "", None, ["ES"], "alta"),
    ("Developer", "Remote - Spain", "", None, ["ES"], "media"),
    ("Senior Product Designer", "Remote", "This role is US-only. You must reside in the United States.", None, [], "alta"),
    ("Product Designer", "Remote", "Candidates must be based in Canada.", None, [], "alta"),
    # Restricción en la descripción hacia LATAM
    ("Designer", "Remote", "You must be based in Latin America to apply.", None, LATAM, "alta"),
    ("Developer", "Remote", "Only candidates from Colombia or Mexico.", None, ["CO", "MX"], "alta"),
    # Zona horaria
    ("Product Designer", "Remote", "We work in UTC-3 to UTC-5 hours.", None, ["AR", "BO", "CL", "CO", "CU", "DO", "EC", "PA", "PE", "PR", "PY", "UY", "VE"], "baja"),
    ("UX Designer", "Remote", "You need at least 4 hours overlap with EST.", None, None, "baja"),
    # Remoto sin región
    ("Video Editor", "Remote", "Edit short videos for social media.", None, TODOS, "baja"),
    # Remoto con LATAM solo en la descripción
    ("Developer", "Remote", "We are a fully remote team hiring across LATAM.", None, LATAM, "alta"),
]


@pytest.mark.parametrize("titulo,ubicacion,descripcion,remoto,esperado,confianza", CASOS)
def test_paises_elegibles(titulo, ubicacion, descripcion, remoto, esperado, confianza):
    r = paises.elegibles(titulo, ubicacion, descripcion, remoto)
    if esperado is not None:
        assert sorted(r["paises"]) == sorted(esperado), r
    if confianza:
        assert r["confianza"] == confianza, r


def test_franja_est_incluye_colombia_y_mexico_pero_no_argentina_lejos():
    r = paises.elegibles("UX Designer", "Remote", "You need at least 4 hours overlap with EST.")
    assert {"CO", "MX", "PE", "VE"} <= set(r["paises"])


def test_modalidad():
    assert paises.modalidad("Diseñador UX (Híbrido)", "Bogotá") == "hibrido"
    assert paises.modalidad("Designer", "Colombia", remoto=True) == "remoto"
    assert paises.modalidad("Designer", "Bogotá", "This is a fully remote position") == "remoto"
    assert paises.modalidad("Designer", "Bogotá") == "presencial"
    assert paises.modalidad("", "") == "sin dato"


def test_datos_de_paises_bien_formados():
    d = paises.datos()
    assert len(d["codigos"]) == len(set(d["codigos"])) == 20  # v12: Brasil se reconoce pero no se cubre
    assert d["europa"] == ["ES"] and len(d["latam"]) == 19 and "BR" in d["reconocidos"] and "BR" not in d["codigos"]
    for p in d["paises"]:
        assert set(p) >= {"codigo", "nombre", "nombres", "gentilicios", "ciudades", "utc"}
        assert -8 <= p["utc"] <= -2 or p.get("region") == "europa"


@pytest.mark.parametrize("titulo,descripcion", [
    ("Freelance Software Tester (Remote in Réunion, Monaco)", "Location: Must be physically located in Réunion or Monaco."),
    ("Freelance Software Tester (Remote in Germany & the Netherlands)", "Location: Must be physically located in Germany or the Netherlands."),
    ("QA Engineer", "Candidates must be physically located in Germany."),
    ("QA Engineer (Remote in Germany)", "We welcome candidates across Europe."),
    ("QA Engineer (Remote in Monaco)", "Work on a global project."),
    ("QA Engineer (Remote in Germany)", "You must be based in Europe."),
])
def test_residencia_especifica_prevalece_sobre_region_general(titulo, descripcion):
    r = paises.elegibles(titulo, "Remote in EMEA", descripcion)
    assert r["paises"] == [] and r["confianza"] == "alta"


def test_lista_mixta_y_espana_siguen_permitidas():
    r = paises.elegibles("QA Engineer (Remote in Spain or Germany)", "Remote in EMEA",
                         "Candidates must be physically located in Spain or Germany.")
    assert r["paises"] == ["ES"]


def test_oficinas_y_clientes_extranjeros_no_son_restriccion_de_residencia():
    r = paises.elegibles("QA Engineer", "Remote Worldwide",
                        "Our offices are in Germany and Monaco. You will test software used in the Netherlands.")
    assert r["paises"] == TODOS and r["confianza"] == "alta"


@pytest.mark.parametrize("ubicacion", ["Tartu, Condado de Tartu, Estonia", "Tallinn, Estonia", "Riga, Latvia", "Vilnius, Lithuania", "Helsinki, Finland", "Oslo, Norway", "Estonia (Remote, EMEA)"])
@pytest.mark.parametrize("remoto", [None, True])
def test_pais_extranjero_no_se_convierte_en_todo_el_mundo(ubicacion, remoto):
    r = paises.elegibles("Product Owner", ubicacion, "Work with distributed teams across time zones. Global scope and inclusive working environment.", remoto)
    assert r["paises"] == [] and r["confianza"] == "alta"


def test_restriccion_estonia_prevalece_sobre_remoto_mundial():
    assert paises.elegibles("Product Owner", "Remote Worldwide", "Candidates must be physically located in Estonia.")["paises"] == []


def test_sede_estonia_no_restringe_una_remota_mundial_confirmada():
    r = paises.elegibles("Product Owner", "Remote Worldwide", "Our headquarters are in Tallinn, Estonia. Work from anywhere.")
    assert r["paises"] == TODOS and r["confianza"] == "alta"


def test_residencia_desconocida_no_hereda_espana_de_emea():
    r = paises.elegibles("Product Owner (Remote in Atlantis)", "Remote in EMEA")
    assert r["confianza"] == "baja"


def test_herramienta_exclusiva_no_es_restriccion_geografica():
    r = paises.elegibles("Staff Product Designer (AI Track)", "RS, Brazil",
                         "You design exclusively in Figma and hand off static specs. Our team works remotely.", True)
    assert r["paises"] == [] and r["confianza"] == "media" and r["nota"] == "país fuera de la cobertura"
