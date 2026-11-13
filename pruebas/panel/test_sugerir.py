"""Ampliación v17: sugerencias de la revisión, calculadas por código. Casos tomados de dudosas reales."""
import csv
import io

import pytest

from panel import revision
from panel.sugerir import sugerir


def _s(ubicacion="Remote", descripcion="", titulo="Product Designer", modalidad="remoto"):
    return sugerir({"titulo": titulo, "ubicacion": ubicacion, "modalidad": modalidad, "_descripcion": descripcion})


@pytest.mark.parametrize("ubicacion, descripcion, titulo", [
    ("Remote", "This is a fully remote role with the option to work hybrid if a commutable distance from our Salem, OR, "
     "Pittsburgh, PA, or Fremont, CA offices.", "Marketing Analyst"),
    ("Remote in AMER", "At the moment, we are looking for freelance software testers based in Martinique.",
     "Freelance Software Tester (Remote in Martinique)"),
    ("Rangún, Myanmar", "Ability to communicate effectively with the team.", "QA Tester"),
    ("Remote in America", "This is a 100% remote role open to candidates based in the United States.", "PMM"),
])
def test_solo_extranjeros_sugiere_otro_pais(ubicacion, descripcion, titulo):
    s = _s(ubicacion, descripcion, titulo)
    assert s["decision"] == "otro_pais" and s["motivo"].startswith("Solo menciona")


def test_sin_pistas_sugiere_no_sirve_y_beneficios_o_clientes_no_cuentan():
    texto = ("Annual company retreat in epic locations (past trips: Paris, Morocco, Tulum, Iceland). "
             "At least 2 years in sales development, ideally B2B with US or Canadian clients. "
             "We'd love you to join us.")
    s = _s("Remote Remoto", texto)
    assert s["decision"] == "no_sirve" and "Remote Remoto" in s["motivo"] and not s["frase"]


def test_paises_cubiertos_y_latam():
    s = _s("Remote Remoto", "You must be based in Colombia or Mexico to apply.")
    assert s["decision"] == "sirve" and s["paises"] == ["CO", "MX"] and "Colombia" in s["frase"]
    s = _s("Remote Remoto", "Residir en Latinoamérica, con horario compatible con Chile.")
    assert s["decision"] == "sirve" and len(s["paises"]) == 19 and "ES" not in s["paises"]
    s = _s("Remote Remoto", "Based in LATAM, excluding Brazil and Argentina.")
    assert s["decision"] == "sirve" and "AR" not in s["paises"] and "excepto Argentina" in s["motivo"]
    s = _s("Granada", "Trabajarás en nuestra oficina de Granada, España, dos días por semana.", modalidad="hibrido")
    assert s["decision"] == "sirve" and s["paises"] == ["ES"]


def test_mezcla_o_europa_hay_que_leerla():
    s = _s("Remote in AMER", "This is a 100% remote role open to those who reside in the US, UK, or EMEA region.")
    assert s["decision"] == "" and s["motivo"].startswith("Léela")
    s = _s("Remote", "Sr. Customer Success Manager covering the EMEA region, based in Europe.")
    assert s["decision"] == "" and "EMEA" in s["motivo"]


def test_csv_trae_la_sugerencia_escrita_y_se_puede_subir_tal_cual():
    from pruebas.panel.test_revision import Repo, _cfg, _fila
    from panel.repositorio import hoy
    cfg, _ = _cfg()
    r = Repo([_fila(1, "Remote Remoto"), _fila(2, "Remote Remoto")])
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles}, completa=True)
    contenido = revision.exportar_csv(r, hoy())
    filas = list(csv.DictReader(io.StringIO(contenido.lstrip("﻿"))))
    assert list(filas[0]) == revision.COLUMNAS_CSV
    assert "¿Puede postularse" in filas[0]["por_que"] and not filas[0]["vacante_id"]  # instrucciones
    datos = filas[1:]
    assert all(f["decision"] == "sí" and f["pais"] == "Colombia, México" and f["enlace"] for f in datos)
    resultado = revision.importar_csv(r, contenido)
    assert resultado["aplicadas"] == 2 and not resultado["errores"]
    assert {x["estado"] for x in r.revisiones()} == {"confirmada"}


def test_leer_paises_entiende_latam_y_todos():
    assert revision.leer_paises("LATAM") == revision.leer_paises("América Latina")
    assert len(revision.leer_paises("LATAM y España")) == 20 and len(revision.leer_paises("todos")) == 20
    assert revision.leer_paises("Colombia, MX") == ["CO", "MX"] and revision.leer_paises("Narnia") == ["?"]
    assert revision.texto_paises(revision.leer_paises("LATAM")) == "LATAM"
