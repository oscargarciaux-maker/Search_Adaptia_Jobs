"""P-16.4 (28 nov): remotas «no abiertas a su país» que se leían mal.

Auditoría de 212 remotas cerradas de la bodega (muestra por fuente): la letra pequeña en inglés que dice desde dónde
puede trabajar la persona («remote Latin America», «candidates based in…») y la región escrita en la ubicación junto a
países de fuera («Remote, Ireland, Europe, United States») no se leían. Cada caso de abajo fallaba antes del arreglo.
Las restricciones reales siguen descartando (casos sintéticos al final). Sin datos de clientes: textos genéricos.
"""
import pytest

from buscador import paises
from panel.afinidad import lugar
from panel.modelos import Perfil
from buscador.medicion import perfil

LATAM = set(paises.datos()["latam"])
RELLENO = " We build digital products for clients across many industries and care about quality. "


def abiertos(ubicacion, descripcion, titulo="Product Designer"):
    v = paises.elegibles(titulo, ubicacion, RELLENO + descripcion + RELLENO, remoto=True)
    return paises.abiertos(v)[0], v


def remoto(pais):
    return Perfil.model_validate(perfil(pais))


def pasa(ubicacion, descripcion, pais, titulo="Product Designer"):
    """¿El paso del lugar de la selección (`panel.afinidad.lugar`) acepta la remota para quien vive en `pais`?"""
    _, e = abiertos(ubicacion, descripcion, titulo)
    v = {**e, "confianza_pais": e["confianza"], "nota_pais": e["nota"], "ubicacion": ubicacion}
    return not lugar(v, remoto(pais))[0]


# ── Patrones mal leídos: ahora abren lo que el aviso dice ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("ubicacion, descripcion, pais", [
    # «remote <región>» pegado (agencia que publica una copia por ciudad de LATAM)
    ("Costa Rica", "Design. Full-time. Your only job. Remote, Latin America. About the role.", "MX"),
    ("Ecuador", "Marketing. Full-time. Remote: USA, Canada, Latin America or South Africa.", "AR"),
    ("Panama", "Location: 100% remote, LATAM only. Schedule aligned with EST.", "CO"),
    ("Bogotá, Colombia", "Location: Remote (Philippines or Latin America). Schedule: MST.", "MX"),
    ("Buenos Aires, Argentina", "Location: fully remote, based in Colombia, Mexico or Argentina.", "MX"),
    # «candidates/applicants/you are … based/located/residing in <lista>»
    ("Argentina", "We are only able to consider candidates based in Argentina, Brazil and Mexico.", "MX"),
    ("Córdoba, Argentina", "Eligibility: this position is open to candidates residing in Latin America.", "CO"),
    ("Argentina", "This is a remote contractor opportunity for candidates located in LATAM.", "MX"),
    ("Chile", "Location alignment: residing in any Latin American country, with US hours overlap.", "AR"),
    ("Montevideo, Uruguay", "Requirements: you are based in Europe or the Americas or open to relocate.", "ES"),
    ("Montevideo, Uruguay", "Requirements: you are based in Europe or the Americas or open to relocate.", "MX"),
    # «this role will be based remotely in <región>»
    ("Colombia", "Location: this role will be based remotely in the Americas region.", "MX"),
    # «remotely from anywhere in the world» con la sede de fuera
    ("Kyiv", "We offer the opportunity to collaborate remotely from anywhere in the world.", "CO"),
    # sede de fuera + apertura a LATAM
    ("Remote, USA", "This position is open to candidates residing in Latin America.", "MX"),
])
def test_la_letra_pequena_en_ingles_abre_a_su_pais(ubicacion, descripcion, pais):
    assert pasa(ubicacion, descripcion, pais)


@pytest.mark.parametrize("ubicacion, pais", [
    ("Remote, Ireland, Europe, United States, Poland, United Kingdom", "ES"),
    ("Remote, Canada, EMEA, United States", "ES"),
    ("Remote - Americas, Remote EU", "ES"),
    ("Remote - US or EU", "ES"),
])
def test_la_region_escrita_en_la_ubicacion_junto_a_paises_de_fuera(ubicacion, pais):
    assert pasa(ubicacion, "Fully remote team.", pais)


def test_la_apertura_suma_sin_quitar_el_pais_del_aviso():
    abre, v = abiertos("Argentina", "We are only able to consider candidates based in Argentina, Brazil and Mexico.")
    assert {"AR", "MX"} <= abre and "CO" not in abre and v["nota"] == paises.NOTA_APERTURA


# ── Lo que NO abre: restricciones reales y frases de la empresa ────────────────────────────────────────────────────
@pytest.mark.parametrize("ubicacion, descripcion, pais", [
    ("Remote, USA", "US only. Must be authorized to work in the United States. Open to candidates residing in "
                    "Latin America.", "MX"),
    ("Remote, USA", "Candidates must reside in the United States.", "MX"),
    ("Remote, USA", "This role is for US residents only.", "CO"),
    ("Remote, UK", "You must have the right to work in the UK.", "ES"),
    ("Germany", "This role is remote but candidates must be based in Germany.", "ES"),
    ("Mexico", "This position is fully remote, however candidates must be currently residing in Mexico.", "CO"),
    ("Remote, USA", "You can work remotely from anywhere in the US.", "MX"),
    ("Remote, USA", "Our team based in Latin America builds great things for clients worldwide.", "MX"),
    ("Remote, USA", "We are a US-based company with clients in Latin America.", "MX"),
    ("Remote, USA", "We are not hiring candidates based in Latin America for this role.", "MX"),
    ("Eu, N, France", "Fully remote team.", "ES"),  # «Eu» es un pueblo de Normandía, no la Unión Europea
    ("Estonia (Remote, EMEA)", "Fully remote team.", "ES"),  # la región precisa el país; no es una lista de opciones
    ("Colombia", "Location: remote Latin America or Eastern Europe preferred.", "ES"),
    ("Alemania", "Markt Deutschland, remote Europa, deutscher Arbeitsvertrag.", "ES"),
    # Thermos: la negación después de la lista y las frases de la empresa
    ("Remote, USA", "Candidates located in Canada or Mexico are not eligible.", "MX"),
    ("Remote, USA", "Candidates based in Mexico or Brazil will not be considered.", "MX"),
    ("Remote, USA", "Remote US position. Candidates located in Brazil or Mexico should not apply.", "MX"),
    ("Remote, USA", "Applicants located in Mexico must apply via our MX entity page instead.", "MX"),
    ("Remote, USA", "We are a fully remote Latin American startup.", "MX"),
    ("Remote, USA", "Our 100% remote Latin American team builds payments.", "MX"),
    ("Remote, USA", "We have been remote in LATAM since 2015.", "MX"),
    ("Remote, USA", "We work remote across Latin America and the US with distributed teams.", "MX"),
    ("Remote, USA", "We support customers remotely worldwide.", "MX"),
    ("Remote, USA", "We are remote for Mexico City clients.", "MX"),
])

def test_la_restriccion_real_o_la_frase_de_empresa_no_abren(ubicacion, descripcion, pais):
    assert not pasa(ubicacion, descripcion, pais)


def test_una_lista_cerrada_sigue_cerrada_para_los_demas():
    """«candidates based in Colombia, Mexico or Argentina» no abre Chile."""
    assert not pasa("Buenos Aires, Argentina", "Location: fully remote, based in Colombia, Mexico or Argentina.", "CL")


@pytest.mark.parametrize("ubicacion", ["Remote, LATAM / EU timezone overlap", "Remote - Latin America (EU hours)"])
def test_eu_como_horario_no_abre_europa(ubicacion):
    assert pasa(ubicacion, "Fully remote team.", "MX") and not pasa(ubicacion, "Fully remote team.", "ES")
