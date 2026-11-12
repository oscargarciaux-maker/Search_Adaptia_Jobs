"""Contrato v13: reglas de la revisión de vacantes fuera del objetivo (sin base de datos; con SQL: probar_limpieza.py)."""
import pytest

from buscador import catalogo, limpiar_fuera_objetivo as limpieza, paises
from pruebas.probar_limpieza import CASOS


@pytest.mark.parametrize("caso", list(CASOS))
def test_decision_por_caso(caso):
    fabrica, esperado = CASOS[caso]
    fila = catalogo.fila(fabrica(), "2026-11-07T00:00:00Z")
    assert limpieza.decidir(fila["datos"], fila["description_full"])[0] == esperado


@pytest.mark.parametrize("ubicacion, modo, esperado", [
    ("Varsovia, Mazovia, Polonia", "onsite", ("borrar", "presencial o híbrida fuera de LATAM y España")),
    ("São Paulo, SP, Brazil", "hybrid", ("borrar", "presencial o híbrida en Brasil")),
    ("Remote, United Kingdom", "remote", ("borrar", "remota solo para otros países")),
    ("Remote - LATAM", "remote", ("", "")),
    ("Ciudad de México, México", "onsite", ("", "")),
])
def test_fila_sin_catalogo_se_juzga_por_sus_columnas(ubicacion, modo, esperado):
    oferta = {"job_title": "QA Engineer", "location": ubicacion, "work_mode": modo, "posting_language": "en"}
    assert limpieza.decidir(None, "", oferta) == esperado


def test_elegir_exige_huella_y_numeros_validos(tmp_path):
    filas = [{"numero": 1, "decision": "borrar"}, {"numero": 2, "decision": "borrar"}, {"numero": 3, "decision": "revisar"}]
    h = limpieza.huella(filas)
    assert limpieza.elegir(filas, h) == {1, 2}
    assert limpieza.elegir(filas, h, conservar="2", borrar_tambien="3") == {1, 3}
    for args in (("otra",), (h, "3"), (h, "", "1")):
        with pytest.raises(SystemExit):
            limpieza.elegir(filas, *args)


def test_listado_solo_con_datos_publicos(tmp_path):
    filas = [{"numero": 7, "decision": "borrar", "motivo": "escrita en francés", "titulo": "<b>Designer</b>",
              "empresa": "A", "ubicacion": "Paris", "modalidad": "remoto", "entregada": "2026-11-06",
              "enlace": "javascript:alert(1)", "vacante_id": "x"}]
    limpieza.escribir_listado(filas, limpieza.resumen(filas, 10), tmp_path)
    pagina = (tmp_path / "revision.html").read_text(encoding="utf-8")
    assert "&lt;b&gt;Designer" in pagina and "javascript:" not in pagina  # escapa el texto y no enlaza lo que no es web
    assert "Designer" in (tmp_path / "revision.csv").read_text(encoding="utf-8-sig")


def test_codigos_finales_y_nombres_en_espanol():
    assert paises.elegibles("QA", "Bucharest, ro")["paises"] == []
    assert paises.elegibles("QA", "Barcelona, es")["paises"] == ["ES"]
    assert paises.elegibles("QA", "San Jose, CA")["paises"] == []
    assert paises.elegibles("QA", "Bogotá, CO")["paises"] == ["CO"]
    assert paises.elegibles("QA", "Conshohocken, PA")["confianza"] == "baja"  # PA: Panamá o Pensilvania
    assert paises.elegibles("QA", "Watford, Inglaterra, Reino Unido")["paises"] == []
