"""P-7.F (27 nov): las dos decisiones de Oscar que el PR #165 (7.E) dejó abiertas.

1. Ubicación: el cliente ve la ubicación corregida («California, Pará, Brasil» → «California, United States») en todo
   lo que recibe o ve; el operador ve además el texto del portal en el detalle. `ofertas` v1 no se reescribe.
2. Cargo: «Technical Security Tester», «Analista de Pruebas de Seguridad» y sus equivalentes son Ciberseguridad, no QA.
"""
import csv
import io

import pytest

from buscador import paises
from buscador.medicion import cargo_crudo
from panel import revision
from panel.contenido import cargo_operativo
from panel.terminos import grado

PORTAL = "California, Pará, Brasil"
CORREGIDA = "California, United States"


# ── 1. Ubicación ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_el_cliente_ve_la_ubicacion_corregida_y_el_operador_la_del_portal():
    assert paises.ubicacion_a_mostrar(PORTAL) == (CORREGIDA, PORTAL)
    assert paises.ubicacion_a_mostrar("california, para, brasil") == (CORREGIDA, "california, para, brasil")


@pytest.mark.parametrize("ubicacion", ["Califórnia, Paraná, Brasil", "Bogotá, Colombia", "Remote - Worldwide", "", None])
def test_sin_correccion_sale_igual_que_hoy(ubicacion):
    assert paises.ubicacion_a_mostrar(ubicacion) == (ubicacion or "", "")


def test_la_bandeja_por_confirmar_muestra_la_corregida():
    # El resumen se guarda de noche con el texto del portal: se corrige al mostrar.
    todas = [{"vacante_id": "v1", "estado": "pendiente", "motivo": "", "ubicacion": "x", "perfiles": [],
              "resumen": {"titulo": "Product Manager", "empresa": "Adobe", "ubicacion": PORTAL}},
             {"vacante_id": "v2", "estado": "pendiente", "motivo": "", "ubicacion": "y", "perfiles": [],
              "resumen": {"titulo": "Product Manager", "empresa": "Nexo", "ubicacion": "Bogotá, Colombia"}}]

    class Repo:
        def ajuste(self, _clave, defecto=None):
            return defecto

    filas = {r["vacante_id"]: r for r in revision.listar(Repo(), "2026-11-27", todas=todas, version={})["pendientes"]}
    assert (filas["v1"]["ubicacion"], filas["v1"]["ubicacion_portal"]) == (CORREGIDA, PORTAL)
    assert (filas["v2"]["ubicacion"], filas["v2"]["ubicacion_portal"]) == ("Bogotá, Colombia", "")


def test_el_csv_de_la_base_lleva_la_corregida_sin_tocar_la_fila_guardada():
    guardada = {"vacante_id": "v1", "external_id": "e1", "job_title": "Product Manager", "location": PORTAL,
                "catalogo_vacantes": {"confianza": "alta"}}
    otra = {"vacante_id": "v2", "external_id": "e2", "job_title": "Product Manager", "location": "Bogotá, Colombia",
            "catalogo_vacantes": {"confianza": "alta"}}

    class Repo:
        def base_ofertas(self):
            return [guardada, otra]

    texto, incluidas, *_ = revision.exportar_base(Repo(), todo=True)
    filas = {f["vacante_id"]: f for f in csv.DictReader(io.StringIO(texto.lstrip("﻿")))}
    assert incluidas == 2
    assert filas["v1"]["location"] == CORREGIDA
    assert filas["v2"]["location"] == "Bogotá, Colombia"
    assert guardada["location"] == PORTAL  # `ofertas` v1 no se reescribe


# ── 2. Cargo ─────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def qa():
    return cargo_operativo(cargo_crudo("QA"))


@pytest.fixture(scope="module")
def ciber():
    return cargo_operativo(cargo_crudo("Cybersecurity Analyst"))


SEGURIDAD = ["Technical Security Tester", "Analista de Pruebas de Seguridad", "Security Tester",
             "Senior Security Tester", "Security Testing Engineer", "Tester de Seguridad",
             "Ingeniero de Pruebas de Seguridad"]


@pytest.mark.parametrize("titulo", SEGURIDAD)
def test_las_pruebas_de_seguridad_no_son_qa(qa, titulo):
    assert grado(titulo, qa)[0] is None


@pytest.mark.parametrize("titulo", SEGURIDAD)
def test_las_pruebas_de_seguridad_son_ciberseguridad(ciber, titulo):
    assert grado(titulo, ciber)[0] in {"exacto", "similar"}


@pytest.mark.parametrize("titulo", ["QA Tester", "Software Tester", "Test Engineer", "Analista de Pruebas",
                                    "Analista QA Funcional", "Tester Funcional", "Analista de Pruebas de Software",
                                    "Performance Tester"])
def test_qa_conserva_sus_tester_de_verdad(qa, ciber, titulo):
    assert grado(titulo, qa)[0] in {"exacto", "similar"}
    assert grado(titulo, ciber)[0] is None
