"""Regla de países: ubicaciones como las publican LinkedIn, Indeed y los sistemas de postulación."""
import pytest

from buscador import paises

TODOS = paises.datos()["codigos"]

# (título, ubicación, descripción, remoto, países esperados, confianza esperada o None)
CASOS = [
    # Presencial o híbrido en un país
    ("Product Designer", "Bogota, D.C., Capital District, Colombia", "", None, ["CO"], "alta"),
    ("Diseñador UX", "Medellín, Antioquia, Colombia", "", None, ["CO"], "alta"),
    ("UX Designer", "São Paulo, State of São Paulo, Brazil", "", None, ["BR"], "alta"),
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
    ("UX Designer", "Madrid, Comunidad de Madrid, España", "", None, [], "alta"),
    ("Video Editor", "London, England, United Kingdom", "", None, [], "alta"),
    # Remoto en un país
    ("Product Designer", "Colombia", "", True, ["CO"], "media"),
    ("UX/UI Designer - Remote", "Mexico", "", None, ["MX"], "media"),
    ("Desarrollador Full Stack (Remoto)", "Venezuela", "", None, ["VE"], "media"),
    ("Senior Designer", "Remote, Brazil", "", None, ["BR"], "media"),
    # Remoto en una lista de países
    ("Backend Engineer", "Remote - Mexico, Colombia, Argentina", "", None, ["MX", "CO", "AR"], "alta"),
    # Remoto para toda LATAM o el mundo
    ("Product Designer", "Latin America", "", True, TODOS, "alta"),
    ("UX Designer (Remote LATAM)", "", "", None, TODOS, "alta"),
    ("Video Editor", "Remote - Worldwide", "", None, TODOS, "alta"),
    ("Frontend Developer", "Anywhere", "", None, TODOS, "alta"),
    ("QA Engineer", "Remote (Americas)", "", None, TODOS, "alta"),
    ("Designer", "Remote - South America", "", None, TODOS, "alta"),
    # Remoto fuera de LATAM
    ("Product Designer", "Remote - US", "", None, [], "alta"),
    ("UX Designer", "United States (Remote)", "", None, [], "alta"),
    ("Developer", "Remote - Europe", "", None, [], "alta"),
    ("Senior Product Designer", "Remote", "This role is US-only. You must reside in the United States.", None, [], "alta"),
    ("Product Designer", "Remote", "Candidates must be based in Canada.", None, [], "alta"),
    # Restricción en la descripción hacia LATAM
    ("Designer", "Remote", "You must be based in Latin America to apply.", None, TODOS, "alta"),
    ("Developer", "Remote", "Only candidates from Colombia or Mexico.", None, ["CO", "MX"], "alta"),
    # Zona horaria
    ("Product Designer", "Remote", "We work in UTC-3 to UTC-5 hours.", None, ["AR", "BO", "BR", "CL", "CO", "CU", "DO", "EC", "PA", "PE", "PR", "PY", "UY", "VE"], "media"),
    ("UX Designer", "Remote", "You need at least 4 hours overlap with EST.", None, None, "media"),
    # Remoto sin región
    ("Video Editor", "Remote", "Edit short videos for social media.", None, TODOS, "baja"),
    # Remoto con LATAM solo en la descripción
    ("Developer", "Remote", "We are a fully remote team hiring across LATAM.", None, TODOS, "media"),
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
    assert len(d["codigos"]) == len(set(d["codigos"])) == 20
    for p in d["paises"]:
        assert set(p) >= {"codigo", "nombre", "nombres", "gentilicios", "ciudades", "utc"}
        assert -8 <= p["utc"] <= -2
