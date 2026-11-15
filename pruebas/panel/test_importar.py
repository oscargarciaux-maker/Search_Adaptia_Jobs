"""Importar clientes desde un CSV (15 nov). Solo datos ficticios."""
import pytest
from fastapi.testclient import TestClient

from panel import importar
from panel.api import crear_app
from panel.modelos import Configuracion
from panel.repositorio import ErrorRepositorio, RepositorioDemo

CSV = """nombre;whatsapp;acepto_whatsapp;cargo;vive_en;modalidades;ciudades;se_mudaria_a;puede_trabajar_en;acepta_horario;idiomas;experiencia_anos;margen_experiencia;ingles_maximo;sectores_preferidos;no_acepta_palabras;salario_minimo;no_acepta_contrato;meta_diaria
Ana Prueba;+57 300 111 2222;sí;Product Designer;Colombia;remoto|híbrido;Bogotá;España|Germany;US;EE. UU. Este;español|inglés;6;4;B2;fintech|salud;call center;2.500 USD mes;prácticas|freelance;12
Ana Prueba;;;UX Writer;CO;remoto;;;;;;;;;;;;;
Luis Prueba;;;QA;méxico;presencial;;;;;inglés;2;;nativo;;;;;
"""


def _repo():
    return RepositorioDemo()


def test_lee_columnas_listas_paises_y_restricciones():
    r = importar.previa(_repo().config()["borrador"], CSV, "mantener")
    assert r["errores"] == 0 and r["clientes"] == 2 and r["perfiles"] == 3
    cfg = r["configuracion"]
    ana = next(c for c in cfg["clientes"] if c["nombre"] == "Ana Prueba")
    pd, writer = [p for p in cfg["perfiles"] if p["cliente_id"] == ana["id"]]
    assert pd["vive_en"] == "CO" and pd["modalidades"] == ["remoto", "hibrido"]
    assert pd["paises_presenciales_extra"] == ["ES", "DE"] and pd["puede_trabajar_en"] == ["US"]
    assert pd["acepta_horario"] == ["us_este"] and pd["ciudades"] == ["Bogotá"]
    assert pd["experiencia_anos"] == 6 and (pd["experiencia_min"], pd["experiencia_max"]) == (2, 10)
    assert pd["ingles_maximo"] == "B2" and pd["meta_diaria"] == 12 and pd["sectores_preferidos"] == ["fintech", "salud"]
    assert {"tipo": "salario_minimo", "monto": 2500.0, "moneda": "USD", "periodo": "month"} in pd["restricciones"]
    assert {"tipo": "palabras", "palabras": ["call center"]} in pd["restricciones"]
    assert {"tipo": "contrato", "tipos": ["internship", "freelance"]} in pd["restricciones"]
    # Vacío = lo mismo que un perfil nuevo del panel.
    assert writer["meta_diaria"] == 10 and writer["idiomas"] == ["es", "en"] and writer["antiguedad_dias"] == 14
    assert writer["ingles_maximo"] == "sin_filtro" and writer["experiencia_anos"] is None
    luis = next(p for p in cfg["perfiles"] if p["vive_en"] == "MX")
    assert luis["idiomas"] == ["en"] and luis["ingles_maximo"] == "native"
    assert r["cargos_nuevos"] == ["UX Writer"]
    assert r["contactos"][ana["id"]] == {"telefono": "+573001112222", "nombre_saludo": "Ana", "consentimiento": True}
    assert len(r["contactos"]) == 1  # Luis no tiene WhatsApp
    Configuracion.model_validate(cfg)


def test_errores_por_fila_y_no_guarda_nada():
    malo = "nombre;cargo;vive_en;modalidades;ingles_maximo;salario_minimo\n" \
           "Ana;Product Designer;Narnia;teletransporte;muy bueno;mucho dinero\n;QA;CO;remoto;;\n"
    repo = _repo()
    antes = repo.config()
    r = importar.previa(antes["borrador"], malo, "borrar")
    textos = " ".join(e for f in r["filas"] for e in f["errores"])
    assert "Narnia" in textos and "teletransporte" in textos and "ingles_maximo" in textos
    assert "salario_minimo" in textos and "Falta el nombre" in textos
    assert r["configuracion"] is None
    with pytest.raises(ErrorRepositorio):
        importar.importar(repo, antes["revision"], malo, "borrar")
    assert repo.config()["borrador"] == antes["borrador"]


def test_columnas_obligatorias_y_archivo_vacio():
    with pytest.raises(ErrorRepositorio, match="cargo"):
        importar.previa(_repo().config()["borrador"], "nombre;vive_en\nAna;CO\n")
    with pytest.raises(ErrorRepositorio, match="vacío"):
        importar.previa(_repo().config()["borrador"], "﻿  ")


def test_quien_ya_existe_se_actualiza_y_conserva_su_identidad():
    """16 nov: importar no debe hacer desaparecer lo que alguien ya recibió. Mismo nombre = mismo cliente y, en el
    mismo cargo, mismo perfil."""
    repo = _repo()
    antes = repo.config()["borrador"]
    cliente = antes["clientes"][1]  # «Cliente de ejemplo 02», Product Designer
    perfil = next(p for p in antes["perfiles"] if p["cliente_id"] == cliente["id"])
    texto = (f"nombre;cargo;vive_en;meta_diaria\n{cliente['nombre'].upper()};Product Designer;Perú;7\n"
             f"{cliente['nombre']};QA;Perú;3\nPersona Nueva;QA;CO;5\n")
    r = importar.previa(antes, texto, "mantener")
    assert r["errores"] == 0 and r["actualizados"] == [cliente["nombre"].upper()] and r["nuevos"] == ["Persona Nueva"]
    assert [f["estado"] for f in r["filas"]] == ["actualiza", "actualiza", "nuevo"]
    cfg = r["configuracion"]
    assert len(cfg["clientes"]) == 6  # nadie se borra con «mantener»
    suyos = [p for p in cfg["perfiles"] if p["cliente_id"] == cliente["id"]]
    pd = next(p for p in suyos if p["cargo_id"] == perfil["cargo_id"])
    assert pd["id"] == perfil["id"] and pd["vive_en"] == "PE" and pd["meta_diaria"] == 7
    assert len(suyos) == 2  # sus perfiles son los del archivo
    # Archivar o borrar solo afecta a quienes no están en el archivo.
    r = importar.previa(antes, texto, "archivar")
    assert len(r["archivar"]) == 4 and cliente["nombre"] not in r["archivar"]
    assert next(c for c in r["configuracion"]["clientes"] if c["id"] == cliente["id"])["activo"]
    r = importar.previa(antes, texto, "borrar")
    assert len(r["borrar"]) == 4 and cliente["id"] not in r["_borrados"]


def test_nombre_anterior_renombra_sin_perder_la_identidad():
    repo = _repo()
    antes = repo.config()["borrador"]
    cliente = antes["clientes"][0]
    texto = f"nombre;nombre_anterior;cargo\nCamila Prueba;{cliente['nombre']};Product Designer\n"
    r = importar.previa(antes, texto, "mantener")
    nuevo = next(c for c in r["configuracion"]["clientes"] if c["id"] == cliente["id"])
    assert r["errores"] == 0 and nuevo["nombre"] == "Camila Prueba" and r["nuevos"] == []
    malo = importar.previa(antes, "nombre;nombre_anterior;cargo\nX;No Existe;QA\n", "mantener")
    assert "nombre_anterior" in " ".join(malo["filas"][0]["errores"])


def test_actualizar_conserva_el_whatsapp_si_la_fila_no_lo_trae_y_sigue_viendose_lo_de_hoy():
    repo = _repo()
    cliente = repo.config()["borrador"]["clientes"][1]
    repo.guardar_contacto(cliente["id"], {"telefono": "+573001112222", "nombre_saludo": "Ana", "consentimiento": True})
    antes = TestClient(crear_app(demo=True, repositorio=repo)).get("/api/resumen-clientes").json()
    hoy_antes = antes["dias"][-1]["clientes"][cliente["id"]]
    importar.importar(repo, repo.config()["revision"], f"nombre;cargo\n{cliente['nombre']};Product Designer\n", "borrar",
                      "BORRAR")
    assert {c["cliente_id"] for c in repo.contactos()} == {cliente["id"]}
    despues = TestClient(crear_app(demo=True, repositorio=repo)).get("/api/resumen-clientes").json()
    assert despues["dias"][-1]["clientes"][cliente["id"]] == hoy_antes
    assert [c["id"] for c in repo.config()["borrador"]["clientes"]] == [cliente["id"]]

def test_borrar_quita_clientes_perfiles_contactos_y_mensajes_y_conserva_cargos():
    repo = _repo()
    viejo = repo.config()["borrador"]["clientes"][0]["id"]
    repo.guardar_contacto(viejo, {"telefono": "+573000000000", "nombre_saludo": "X", "consentimiento": True})
    repo.guardar_borrador({"fecha": "2026-11-15", "cliente_id": viejo, "texto": "hola", "vacantes": [], "cargos": [],
                           "estado": "pendiente"})
    cargos_antes = {c["id"] for c in repo.config()["borrador"]["cargos"]}
    r = importar.importar(repo, repo.config()["revision"], CSV, "borrar", "BORRAR")
    assert r["importados"] == 2 and r["borrados"] == 5 and r["cargos_nuevos"] == ["UX Writer"]
    cfg = repo.config()["borrador"]
    assert {c["nombre"] for c in cfg["clientes"]} == {"Ana Prueba", "Luis Prueba"}
    assert all(p["cliente_id"] in {c["id"] for c in cfg["clientes"]} for p in cfg["perfiles"])
    assert cargos_antes <= {c["id"] for c in cfg["cargos"]}  # los cargos se conservan
    assert viejo not in {c["cliente_id"] for c in repo.contactos()}
    assert not repo.borradores(cliente_id=viejo)
    assert len(repo.contactos()) == 1


def test_techo_excedido_se_avisa_sin_impedir_el_borrador():
    filas = "\n".join(f"Persona {i};QA;120" for i in range(2))
    r = importar.previa(_repo().config()["borrador"], "nombre;cargo;meta_diaria\n" + filas, "borrar")
    assert r["errores"] == 0 and r["excede_techo"] and r["metas"]["reales"] == 240


def test_borrar_cliente_individual():
    repo = _repo()
    cliente = repo.config()["borrador"]["clientes"][1]["id"]
    importar.borrar_cliente(repo, repo.config()["revision"], cliente)
    cfg = repo.config()["borrador"]
    assert cliente not in {c["id"] for c in cfg["clientes"]}
    assert cliente not in {p["cliente_id"] for p in cfg["perfiles"]}
    with pytest.raises(ErrorRepositorio):
        importar.borrar_cliente(repo, repo.config()["revision"], cliente)


def test_api_previa_importar_y_confirmacion():
    repo = _repo()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    origen = {"origin": "http://testserver"}
    plantilla = api.get("/api/clientes/plantilla.csv")
    assert plantilla.status_code == 200 and "nombre;comunidad;whatsapp" in plantilla.text
    assert importar.previa(repo.config()["borrador"], plantilla.text)["errores"] == 0  # la plantilla es válida
    previa = api.post("/api/clientes/importar/previa", json={"contenido": CSV, "actuales": "borrar"}, headers=origen)
    assert previa.status_code == 200 and "configuracion" not in previa.json() and "contactos" not in previa.json()
    assert previa.json()["clientes"] == 2
    revision = repo.config()["revision"]
    sin_confirmar = api.post("/api/clientes/importar", headers=origen,
                             json={"contenido": CSV, "actuales": "borrar", "revision": revision})
    assert sin_confirmar.status_code == 422
    hecho = api.post("/api/clientes/importar", headers=origen,
                     json={"contenido": CSV, "actuales": "borrar", "revision": revision, "confirmacion": "BORRAR"})
    assert hecho.status_code == 200 and hecho.json()["importados"] == 2
    assert len(hecho.json()["estado"]["borrador"]["clientes"]) == 2
    otra = api.post("/api/clientes/importar", headers=origen,
                    json={"contenido": CSV, "actuales": "mantener", "revision": revision})
    assert otra.status_code == 409  # revisión vieja
    cliente = hecho.json()["estado"]["borrador"]["clientes"][0]["id"]
    nueva = hecho.json()["estado"]["revision"]
    assert api.post(f"/api/clientes/{cliente}/borrar", headers=origen,
                    json={"revision": nueva, "confirmacion": "no"}).status_code == 422
    assert api.post(f"/api/clientes/{cliente}/borrar", headers=origen,
                    json={"revision": nueva, "confirmacion": "BORRAR"}).status_code == 200


def test_regiones_en_listas_de_paises_para_perfiles_moviles():
    texto = ("nombre;cargo;vive_en;puede_trabajar_en;se_mudaria_a;acepta_horario\n"
             "Persona Móvil;Product Manager;Emiratos Árabes Unidos;Emiratos|Europa;UE;Europa\n"
             "Persona América;Product Designer;CO;Toda América;;\n")
    r = importar.previa(_repo().config()["borrador"], texto, "borrar")
    assert r["errores"] == 0
    movil, america = r["configuracion"]["perfiles"]
    assert movil["vive_en"] == "AE" and movil["puede_trabajar_en"][0] == "AE"
    assert {"DE", "FR", "ES", "GB", "CH"} <= set(movil["puede_trabajar_en"])
    assert set(importar.UE) == set(movil["paises_presenciales_extra"]) and "GB" not in movil["paises_presenciales_extra"]
    assert movil["acepta_horario"] == ["europa"]
    assert {"US", "CA", "MX", "AR"} <= set(america["puede_trabajar_en"])


def test_nombres_y_funciones_solo_para_cargos_nuevos():
    texto = ("nombre;cargo;nombres_del_cargo;funciones_del_cargo\n"
             "Persona IA;AI Product Manager;AI Product Owner|Product Manager IA;agentes de voz|LLM|chatbot\n"
             "Otra IA;AI Product Owner;;\n"
             "Persona QA;QA;QA Lead;pruebas\n")
    repo = _repo()
    r = importar.previa(repo.config()["borrador"], texto, "borrar")
    assert r["errores"] == 0 and r["cargos_nuevos"] == ["AI Product Manager"]
    cargo = next(c for c in r["configuracion"]["cargos"] if c["nombre"] == "AI Product Manager")
    assert cargo["terminos_exactos"] == ["AI Product Manager", "AI Product Owner", "Product Manager IA"]
    assert cargo["funciones"] == ["agentes de voz", "LLM", "chatbot"]
    # «AI Product Owner» es un nombre del cargo nuevo: la segunda persona va al mismo cargo.
    perfiles = r["configuracion"]["perfiles"]
    assert perfiles[0]["cargo_id"] == perfiles[1]["cargo_id"] == cargo["id"]
    qa = next(c for c in r["configuracion"]["cargos"] if c["nombre"] == "QA")
    antes = next(c for c in repo.config()["borrador"]["cargos"] if c["nombre"] == "QA")
    assert qa["terminos_exactos"] == antes["terminos_exactos"]  # un cargo existente no se cambia
    assert any("ya existe" in a for a in r["filas"][2]["avisos"])


def test_admitir_ingles_y_experiencia_no_informados():
    texto = ("nombre;cargo;ingles_maximo;experiencia_anos;admitir_ingles_no_informado;admitir_experiencia_no_informada\n"
             "Persona A;QA;B2;5;sí;sí\nPersona B;QA;B2;5;;\nPersona C;QA;B2;5;quizás;no\n")
    r = importar.previa(_repo().config()["borrador"], texto, "borrar")
    assert "admitir_ingles_no_informado" in " ".join(r["filas"][2]["errores"])
    texto = texto.replace("quizás", "no")
    a, b, c = importar.previa(_repo().config()["borrador"], texto, "borrar")["configuracion"]["perfiles"]
    assert a["aceptar_ingles_sin_dato"] and a["aceptar_experiencia_sin_dato"]
    assert not b["aceptar_ingles_sin_dato"] and not b["aceptar_experiencia_sin_dato"]  # vacío = como un perfil nuevo
    assert not c["aceptar_ingles_sin_dato"]
