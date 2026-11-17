"""Contrato v38 (17 nov, pedido de Oscar): reconocer bien cualquier parte del mundo. La ciudad dice el país («Chicago» →
EE. UU., «Toronto» → Canadá), con o sin código postal o sigla de estado o provincia, y los alrededores de la ciudad del
perfil cuentan como la misma ciudad. Lo de verdad ambiguo («Cambridge», «Richmond») sigue sin decidirse: nunca se
adivina."""
import pytest

from buscador import paises
from panel.afinidad import evaluar
from panel.modelos import Perfil
from panel.repositorio import hoy

BASE = {"id": "00000000-0000-0000-0000-000000000001", "cliente_id": "00000000-0000-0000-0000-000000000002",
        "cargo_id": "00000000-0000-0000-0000-000000000003", "idiomas": ["es", "en"]}


def _mundo(ubicacion, titulo="Product Designer"):
    return paises.elegibles(titulo, ubicacion)["paises_mundo"]


@pytest.mark.parametrize("ubicacion,pais", [
    # EE. UU. sin decir «United States»
    ("New York", "US"), ("New York, NY 10001", "US"), ("NYC", "US"), ("Manhattan, NY", "US"), ("Chicago", "US"),
    ("Seattle", "US"), ("Boston", "US"), ("Los Angeles, CA 90001", "US"), ("Austin, TX 78701", "US"),
    ("Hybrid - Chicago", "US"), ("Remote - New York, NY", "US"), ("Washington, DC", "US"), ("Paris, TX", "US"),
    ("London, KY", "US"), ("Indianapolis, IN", "US"), ("Springfield, IL", "US"), ("Seattle y alrededores", "US"),
    # «US» con guion, barra o al final
    ("US-Remote", "US"), ("Remote/USA", "US"), ("USA - Remote", "US"), ("Remote (US)", "US"),
    # Canadá, Australia y el resto del mundo
    ("Toronto", "CA"), ("Toronto, ON", "CA"), ("Toronto, ON M5V 3L9", "CA"), ("Montreal, QC", "CA"),
    ("Vancouver, BC", "CA"), ("London, ON", "CA"), ("Toronto, CA", "CA"), ("Greater Toronto Area", "CA"),
    ("Yellowknife, NT", "CA"), ("Sydney, NSW", "AU"), ("Melbourne VIC", "AU"), ("Perth, WA", "AU"),
    ("Darwin, NT", "AU"), ("Adelaide, SA", "AU"), ("London", "GB"), ("Munich, Bavaria", "DE"), ("München", "DE"),
    ("Berlin, DE", "DE"), ("Amsterdam", "NL"), ("Amsterdam, NL", "NL"), ("Lisbon", "PT"), ("Milan", "IT"),
    ("Zurich", "CH"), ("Auckland", "NZ"), ("Tokyo", "JP"), ("Bangalore", "IN"), ("Mumbai, IN", "IN"),
    ("Dubai", "AE"), ("Tel Aviv, IL", "IL"), ("Warsaw", "PL"), ("São Paulo", "BR"), ("Prague, cz", "CZ"),
])
def test_la_ciudad_dice_el_pais(ubicacion, pais):
    assert _mundo(ubicacion) == [pais]


def test_norteamerica_es_eeuu_y_canada():
    assert _mundo("Remote, North America") == ["CA", "US"]
    assert _mundo("América del Norte") == ["CA", "US"]


@pytest.mark.parametrize("ubicacion", ["Cambridge", "Richmond", "Vancouver", "Hamilton", "Remote, APAC", "EMEA"])
def test_lo_ambiguo_no_se_adivina(ubicacion):
    assert not set(_mundo(ubicacion)) - set(paises.datos()["codigos"])


def test_la_sigla_del_estado_no_pisa_otro_pais_nombrado_ni_una_ciudad_cubierta():
    assert _mundo("Barcelona, CT, Spain") == ["ES"]  # CT es Cataluña
    assert "US" not in _mundo("Sabadell, CT") and "US" not in _mundo("La Moraleja, MD, Spain")
    assert _mundo("Atlanta, GA, US") == ["US"]


def test_pais_dentro_del_nombre_de_una_ciudad_o_de_un_estado():
    assert _mundo("Jersey City, NJ") == ["US"] and _mundo("Kuwait City") == ["KW"]
    assert _mundo("Atlanta, Georgia") == ["US"] and _mundo("Tbilisi, Georgia") == ["GE"]
    florida = paises.elegibles("D", "Panama City, FL")  # antes contaba como Panamá
    assert florida["paises"] == [] and florida["paises_mundo"] == ["US"]
    assert paises.elegibles("D", "Panama City")["paises"] == ["PA"]
    assert _mundo("Toledo, OH") == ["US"] and _mundo("Lima, OH") == ["US"]
    for ubicacion in ("Sabadell, CT", "Vigo, GA", "Madrid, MD"):  # comunidades de España, no estados de EE. UU.
        assert paises.elegibles("D", ubicacion)["paises"] == ["ES"], ubicacion


def test_los_paises_cubiertos_no_cambian():
    assert paises.elegibles("D", "Bogotá")["paises"] == ["CO"]
    assert paises.elegibles("D", "Santiago, Región Metropolitana")["paises"] == ["CL"]
    assert paises.elegibles("D", "Córdoba")["confianza"] == "baja"  # España y Argentina
    assert paises.elegibles("D", "Lima, PE")["paises"] == ["PE"]
    assert _mundo("Madrid") == []  # la tabla curada sigue mandando en los cubiertos
    assert paises.lugar_conocido("Inca") == "ES" and paises.lugar_conocido("NYC") == "fuera"


def _vacante(ubicacion, modalidad=None):
    e = paises.elegibles("Product Designer", ubicacion)
    return {"titulo": "Product Designer", "modalidad": modalidad or e["modalidad"], "paises": e["paises"],
            "paises_mundo": e["paises_mundo"], "alcance_mundial": e["alcance_mundial"],
            "confianza_pais": e["confianza"], "ubicacion": ubicacion, "idioma": "en", "fecha_publicacion": hoy()}


def _perfil(*filas):
    return Perfil.model_validate({**BASE, "ubicaciones": list(filas)})


def _recibe(perfil, ubicacion, modalidad=None):
    return evaluar(_vacante(ubicacion, modalidad), perfil, hoy())["compatible"]


def test_quien_vive_en_eeuu_recibe_las_de_cualquier_ciudad_de_eeuu():
    p = _perfil({"paises": ["US"], "modalidades": ["remoto", "hibrido", "presencial"]})
    for ubicacion in ("New York", "New York, NY 10001", "Chicago", "Seattle", "Brooklyn, NY", "Austin, TX 78701",
                      "San Francisco Bay Area", "Paris, TX"):
        assert _recibe(p, ubicacion, "presencial"), ubicacion
    assert _recibe(p, "US-Remote", "remoto")
    for ubicacion in ("Toronto", "London", "Paris", "Berlin, DE"):
        assert not _recibe(p, ubicacion, "presencial"), ubicacion


def test_los_alrededores_de_su_ciudad_cuentan_como_la_misma():
    nueva_york = _perfil({"paises": ["US"], "ciudades": ["New York"], "modalidades": ["hibrido", "presencial"]})
    for ubicacion in ("Brooklyn, NY", "Jersey City, NJ", "Manhattan, NY", "NYC", "New York, NY 10001",
                      "New York City Metropolitan Area"):
        assert _recibe(nueva_york, ubicacion, "hibrido"), ubicacion
    for ubicacion in ("Boston, MA", "Chicago, IL", "Austin, TX"):
        assert not _recibe(nueva_york, ubicacion, "hibrido"), ubicacion
    chicago = _perfil({"paises": ["US"], "ciudades": ["Chicago"], "modalidades": ["presencial"]})
    assert _recibe(chicago, "Evanston, IL", "presencial") and _recibe(chicago, "Naperville, IL", "presencial")
    bogota = _perfil({"paises": ["CO"], "ciudades": ["Bogotá"], "modalidades": ["presencial"]})
    assert _recibe(bogota, "Chía, Cundinamarca", "presencial") and not _recibe(bogota, "Medellín", "presencial")


def test_la_distancia_nunca_se_adivina():
    assert paises.cerca("Brooklyn", "New York", ("US",)) and paises.cerca("Sabadell", "Barcelona", ("ES",))
    assert not paises.cerca("Toluca", "Ciudad de México", ("MX",))  # unos 60 km: otra ciudad
    assert not paises.cerca("Lugar inventado", "New York", ("US",))
    assert not paises.cerca("Cambridge", "Boston")  # sin país, Cambridge es de varios
