"""Contrato v49: afinidad por funciones. El título dice que la vacante es del cargo; la descripción lo respalda o no.
Sin evidencia va al final con su etiqueta; con una señal de otro oficio no se entrega sola (decisiones de Oscar)."""
from copy import deepcopy
from uuid import uuid4

import pytest

from buscador import entrega, familias
from panel import contenido, ejecutor, revision, servicio
from panel.repositorio import RepositorioDemo, configuracion_demo, hoy
from pruebas.panel.test_confirmar_v43 import Repo
from pruebas.panel.test_control import trabajo

RELLENO = "We are a growing company with great benefits, flexible hours and a friendly team that values people. " * 3
DISENO = RELLENO + "You will design in Figma, build wireframes and prototyping flows and keep our design system."
QA = RELLENO + "Escribirás casos de prueba, automatizarás con Cypress y Playwright y reportarás defectos en Jira."
FABRICA = RELLENO + "You will inspect parts on the production line and keep the plant audit records up to date."


def cargo(nombre, **extra):
    return contenido.cargo_operativo({"id": "c1", "nombre": nombre, "terminos_exactos": [nombre], "terminos_similares": [],
                                      "terminos_excluidos": [], "terminos_cercanos": [], "funciones": [], **extra})


# ── El cargo operativo ─────────────────────────────────────────────────────────────────────────────────────────────
def test_el_cargo_hereda_del_mapa_la_huella_y_las_senales_de_otro_oficio():
    c = cargo("Product Designer")
    assert "figma" in c["funciones"] and "wireframes" in c["funciones"]
    assert "diseñador industrial" in c["excluir_mapa"]
    assert c["terminos_excluidos"] == []  # lo heredado señala; no descarta por su cuenta
    assert contenido.cargo_operativo(c) == c  # aplicarlo dos veces da lo mismo


def test_lo_que_escribio_el_operador_manda():
    propio = cargo("Product Designer", funciones=["tokens", "accesibilidad", "handoff", "research"])
    assert propio["funciones"] == ["tokens", "accesibilidad", "handoff", "research"]
    # Un excluido del mapa que el cargo usa como nombre propio deja de ser señal («UX Engineer»).
    con_ingeniero = cargo("Product Designer", terminos_similares=["UX Engineer"])
    assert "engineer" not in con_ingeniero["excluir_mapa"] and "engineer" in cargo("Product Designer")["excluir_mapa"]


def test_titulos_aprendidos_y_huella_de_la_noche():
    base = {"id": "c1", "nombre": "Asesor comercial", "terminos_exactos": ["Asesor comercial"], "terminos_similares": []}
    c = contenido.cargo_operativo(base, aprendidos=["Ejecutivo de ventas"], huella_auto=["prospectar", "cierre de ventas"])
    assert c["terminos_similares"] == ["Ejecutivo de ventas"] and c["funciones"] == ["prospectar", "cierre de ventas"]
    assert c["excluir_mapa"] == [] and c["distintivo"] == []


def test_un_cargo_compuesto_tiene_distintivo_y_la_huella_de_su_oficio_base():
    c = cargo("AI Product Manager")
    assert c["distintivo"][0] == "IA" and "ai" in c["distintivo"]
    assert "roadmap" in c["funciones"]
    assert cargo("Product Manager")["distintivo"] == []


# ── La evidencia ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_niveles_de_evidencia():
    c = cargo("Product Designer")
    fuerte = contenido.evidencia("Senior Product Designer", DISENO, c)
    assert fuerte["nivel"] == "fuerte" and "figma" in fuerte["halladas"] and not fuerte["otro_oficio"]
    assert contenido.evidencia("Product Designer", RELLENO + "Figma is a plus.", c)["nivel"] == "debil"
    ninguna = contenido.evidencia("Product Designer", RELLENO, c)
    assert ninguna["nivel"] == "ninguna" and contenido.avisos(ninguna) == ["Funciones por confirmar"]
    assert contenido.penalizacion(ninguna) == 1 and contenido.penalizacion(fuerte) == 0
    # Sin descripción o sin huella suficiente, no opina.
    assert contenido.evidencia("Product Designer", "", c)["nivel"] == "sin_huella"
    assert contenido.evidencia("Contador", RELLENO, cargo("Contador"))["nivel"] == "sin_huella"


def test_las_funciones_en_espanol_cuentan_igual():
    assert contenido.evidencia("Analista QA", QA, cargo("QA"))["nivel"] == "fuerte"


@pytest.mark.parametrize("nombre,titulo,descripcion,senal", [
    ("QA", "QA Manufacturing Analyst", FABRICA, "manufacturing"),
    ("Product Designer", "Outerwear Design Manager", FABRICA, None),   # no coincide con el cargo: no se evalúa aquí
    ("Product Designer", "Product Designer – Kids' Drinkware", FABRICA, "drinkware"),
    ("Product Designer", "Industrial Designer / Product Designer", FABRICA, "industrial designer"),
    ("Product Manager", "LCL Product Manager - Ocean Freight", FABRICA, "freight"),
])
def test_senales_de_otro_oficio(nombre, titulo, descripcion, senal):
    e = contenido.evidencia(titulo, descripcion, cargo(nombre))
    if senal is None:
        assert e["nivel"] == "ninguna"
    else:
        assert e["otro_oficio"] and e["senal"] == senal


def test_con_funciones_del_cargo_la_palabra_de_otro_sector_no_retiene():
    e = contenido.evidencia("QA Manufacturing Analyst", QA, cargo("QA"))
    assert e["nivel"] == "fuerte" and not e["otro_oficio"]


def test_el_titulo_exacto_del_cargo_nunca_se_retiene():
    e = contenido.evidencia("Senior Product Designer", FABRICA, cargo("Product Designer"))
    assert e["nivel"] == "ninguna" and not e["otro_oficio"]
    # Tampoco un título que el operador aprobó en «Por confirmar» (v25).
    aprobado = contenido.cargo_operativo(cargo("QA"), aprendidos=["QA Manufacturing Analyst"])
    assert not contenido.evidencia("QA Manufacturing Analyst", FABRICA, aprobado)["otro_oficio"]


def test_la_palabra_de_otro_sector_no_cuenta_si_es_del_cargo():
    c = cargo("QA", terminos_similares=["QA de manufactura"], funciones=["plan de control", "manufactura", "ppap", "amef"])
    assert not contenido.evidencia("Analista QA de Manufactura Senior II", FABRICA, c)["otro_oficio"]


def test_cargo_compuesto_sin_su_distintivo():
    c = cargo("AI Product Manager", terminos_similares=["Product Manager"])
    pm = RELLENO + "You own the roadmap and the backlog, write user stories and align stakeholders on OKRs."
    sin_ia = contenido.evidencia("Product Manager - Pharmacy E-Commerce", pm, c)
    assert sin_ia["falta_distintivo"] == "IA" and contenido.avisos(sin_ia) == ["No menciona IA"]
    assert contenido.penalizacion(sin_ia) == 1 and not sin_ia["otro_oficio"]
    con_ia = contenido.evidencia("Product Manager", pm + " You will ship LLM features with our AI team.", c)
    assert not con_ia["falta_distintivo"] and contenido.penalizacion(con_ia) == 0
    assert not contenido.evidencia("Senior AI Product Manager", pm, c)["falta_distintivo"]  # lo dice el título


def test_la_huella_de_la_noche_sale_por_idioma():
    def aviso(i, idioma, titulo, texto):
        return {"id": f"{idioma}{titulo}{i}", "titulo": titulo, "idioma": idioma, "_descripcion": RELLENO + texto}
    vacantes = [aviso(i, "es", "Asesor comercial", f"Prospectar clientes y cierre de ventas en la zona {i}. Manejo de CRM.")
                for i in range(20)]
    vacantes += [aviso(i, "en", "Asesor comercial", f"Prospecting and closing deals in territory {i}. Pipeline reviews.")
                 for i in range(20)]
    vacantes += [aviso(i, idioma, "Contador", f"Conciliaciones bancarias y cierre contable del mes {i}.")
                 for i in range(40) for idioma in ("es", "en")]
    c = {"id": "c9", "nombre": "Asesor comercial", "terminos_exactos": ["Asesor comercial"], "terminos_similares": []}
    huella = contenido.huellas_automaticas(vacantes, [c])["c9"]
    assert any("prospectar" in t for t in huella) and any("prospecting" in t for t in huella)
    assert not any("contable" in t for t in huella)
    assert contenido.huellas_automaticas(vacantes[:5], [c]) == {}  # con pocos avisos no hay huella


# ── Clasificación: lo que parece otro oficio no se entrega solo ────────────────────────────────────────────────────
@pytest.fixture
def modo_panel():
    version = {"revision": 1, "configuracion": configuracion_demo()}
    with ejecutor.activar(version, hoy()):
        yield version["configuracion"]


def test_clasificar_retiene_el_titulo_con_funciones_de_otro_oficio(modo_panel):
    qa = next(c for c in modo_panel["cargos"] if c["nombre"] == "QA")
    normal = familias.clasificar("QA Engineer", QA)
    assert normal == [{"familia": "cargo:" + qa["id"], "coincidencia": "exacto"}]
    dudosa = familias.clasificar("QA Manufacturing Analyst", FABRICA)
    assert dudosa == [{"familia": "cargo:" + qa["id"], "coincidencia": "funciones", "duda": "otro_oficio"}]
    # Sin descripción todavía no se puede saber: se clasifica por el título, como siempre.
    assert familias.clasificar("QA Manufacturing Analyst")[0]["coincidencia"] == "exacto"
    # Y lo que es de otro oficio no entra al lote del cargo.
    v = trabajo(titulo="QA Manufacturing Analyst", _descripcion=FABRICA, familias=dudosa)
    assert entrega.roles_de(v, entrega.config()["roles"]) == ([], None)


def test_el_lote_pone_al_final_lo_que_no_tiene_funciones():
    c = cargo("Product Designer")
    con = trabajo(id="con", empresa="A", _descripcion=DISENO)
    sin = trabajo(id="sin", empresa="B", _descripcion=FABRICA)
    orden = entrega.variadas([(sin, "exacto"), (con, "exacto")], 2, 2, hoy(), cargo=c)
    assert [v["id"] for v, _ in orden] == ["con", "sin"]
    # Sin cargo (modo heredado) no cambia nada: el orden de siempre.
    assert [v["id"] for v, _ in entrega.variadas([(sin, "exacto"), (con, "exacto")], 2, 2, hoy())] == ["sin", "con"]


# ── Asignación: explicación, coincidencia del cargo que recibe y cruce entre cargos ────────────────────────────────
def _lote(cargo_cfg, titulo, descripcion, n=1):
    v = trabajo(id=f"v{n:02d}", titulo=titulo, empresa=f"Empresa {n}", enlace=f"https://jobs.lever.co/e/{n}",
                _descripcion=descripcion)
    return {"role_id": "cargo:" + cargo_cfg["id"], "vacante_id": v["id"], "match_grade": "exact", "snapshot": v}


def _dos_cargos():
    cfg = configuracion_demo()
    diseno = cfg["cargos"][0]
    otro = dict(deepcopy(diseno), id=str(uuid4()), nombre="Diseñador UX/UI", cupo=5, terminos_exactos=["Diseñador UX/UI"],
                terminos_similares=["Product Designer"])
    perfil = dict(deepcopy(cfg["perfiles"][3]), id=str(uuid4()), cargo_id=otro["id"], meta_diaria=5)
    cfg["cargos"].append(otro)
    cfg["perfiles"].append(perfil)
    cfg["techo_diario"] = 200
    return cfg, diseno, otro, perfil


def test_la_asignacion_guarda_las_funciones_y_la_coincidencia_del_cargo_que_recibe():
    cfg, diseno, otro, perfil = _dos_cargos()
    repo = Repo([_lote(diseno, "Product Designer", DISENO)], version_nueva={"revision": 1, "configuracion": cfg})
    ejecutor.registrar(repo, repo.version_nueva, hoy())
    propia = next(f for (p, _), f in repo.asignaciones.items() if p != perfil["id"])
    assert propia["match_grade"] == "exact"
    assert {"funciones": "fuerte", "halladas": ["figma", "prototyping", "wireframes", "design system"]} in propia["explicacion"]
    assert "figma" in propia["cargo_configuracion"]["funciones"]  # el cargo operativo, no el que quedó sin rellenar
    cruzada = repo.asignaciones[(perfil["id"], "v01")]
    assert cruzada["cargo_id"] == otro["id"] and cruzada["match_grade"] == "similar"  # antes quedaba «exact»


def test_sin_funciones_no_cruza_a_otro_cargo_pero_si_llega_al_suyo():
    cfg, diseno, _, perfil = _dos_cargos()
    repo = Repo([_lote(diseno, "Product Designer", FABRICA)], version_nueva={"revision": 1, "configuracion": cfg})
    ejecutor.registrar(repo, repo.version_nueva, hoy())
    assert (perfil["id"], "v01") not in repo.asignaciones and repo.asignaciones
    assert all({"funciones": "ninguna", "halladas": []} in f["explicacion"] for f in repo.asignaciones.values())


# ── Lo que ve el operador: etiqueta y orden por calidad ────────────────────────────────────────────────────────────
def test_la_lista_del_cliente_va_por_calidad_y_marca_las_funciones_por_confirmar(tmp_path):
    repo = RepositorioDemo(tmp_path / "demo.json")
    cliente = configuracion_demo()["clientes"][0]["id"]
    vacantes = servicio.resultados(repo, cliente)["vacantes"]
    claves = [servicio.calidad(v) for v in vacantes]
    assert claves == sorted(claves) and len(vacantes) > 10
    marcadas = [v for v in vacantes if "Funciones por confirmar" in v["avisos"]]
    assert marcadas and len(marcadas) < len(vacantes) / 4
    # Las que encajan en todo van antes que cualquiera con una etiqueta.
    primera_con_aviso = next(i for i, v in enumerate(vacantes) if v["avisos"])
    assert all(not v["avisos"] for v in vacantes[:primera_con_aviso])
    assert not any(v["avisos"] for v in vacantes[:5])


def test_calidad_ordena_por_coincidencia_etiquetas_y_fecha():
    def ficha(**k):
        return {"tipo": "", "ampliacion": "", "match_grade": "exact", "avisos": [], "publicada": "2026-11-20", **k}
    orden = sorted([ficha(id=1, avisos=["Funciones por confirmar"]), ficha(id=2, match_grade="close"),
                    ficha(id=3, publicada="2026-11-25"), ficha(id=4), ficha(id=5, tipo="post"),
                    ficha(id=6, ampliacion="más vacantes de la misma empresa")], key=servicio.calidad)
    assert [f["id"] for f in orden] == [3, 4, 1, 2, 6, 5]


# ── La bandeja «Por confirmar» ─────────────────────────────────────────────────────────────────────────────────────
def test_la_bandeja_distingue_la_duda_de_cargo_y_no_la_descarta_para_todos():
    assert revision.resumen_de({"titulo": "QA Manufacturing Analyst"}, revision.OTRO_OFICIO)["sugerida"] == ""
    assert "otro oficio" in revision.resumen_de({"titulo": "x"}, revision.OTRO_OFICIO)["por_que"]
    from panel.aprender import ETIQUETAS
    filas = [{"vacante_id": "a", "estado": "descartada", "motivo": revision.NO_SIRVE_AL_CARGO},
             {"vacante_id": "b", "estado": "descartada", "motivo": ETIQUETAS["no_sirve"]}]
    assert revision.decisiones_para_busqueda(filas) == {"b": {"descartada": True}}


def test_formato_de_oficios_ajenos():
    from pathlib import Path
    import yaml
    from buscador import normalizar
    crudo = yaml.safe_load((Path(__file__).resolve().parents[2] / "datos" / "oficios_ajenos.yaml").read_text("utf-8"))
    palabras = crudo["palabras"]
    assert len(palabras) >= 40 and len(palabras) == len(set(palabras))
    assert all(isinstance(p, str) and p == normalizar.texto(p) for p in palabras)  # minúsculas y sin tildes
    assert tuple(palabras) == contenido.oficios_ajenos()
