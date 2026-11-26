"""Contrato v50: más vacantes en español. No perder lo que ya se encuentra (fichas de LinkedIn al cargo, relectura por
necesidad, repaso de Indeed, comprobación por carril) y buscar y reconocer más en español (bilingües, nombres hermanos
con control, letra pequeña en español)."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from buscador import cobertura, familias, medicion, normalizar, paises, vacante, verificar_enlaces
from buscador.fuentes import indeed, linkedin_publico
from panel import contenido, ejecutor, terminos
from panel.afinidad import evaluar
from panel.modelos import Cargo
from panel.repositorio import configuracion_demo, hoy

PM = ("Buscamos una persona de producto digital. Vas a definir el roadmap, hacer discovery con usuarios, priorizar el "
      "backlog y medir con OKRs junto a diseño e ingeniería. Trabajo remoto. ") * 2


@pytest.fixture
def cfg():
    return configuracion_demo()


# ── 1.1 LinkedIn: primero las fichas de los avisos del cargo ───────────────────────────────────────────────────────
def _tarjeta(n, titulo):
    return (f'<li><div class="base-card" data-entity-urn="urn:li:jobPosting:{n}">'
            f'<h3 class="base-search-card__title">{titulo}</h3><h4 class="base-search-card__subtitle">Empresa {n}</h4>'
            '<span class="job-search-card__location">Bogotá, Colombia</span>'
            '<time class="job-search-card__listdate" datetime="2026-11-20">hace 1 día</time></div></li>')


class _Respuesta:
    def __init__(self, texto, status=200):
        self.text, self.status_code, self.url = texto, status, "https://www.linkedin.com"


class _LinkedIn:
    def __init__(self, listado):
        self.listado, self.fichas = listado, []

    def get(self, url, params=None, **_):
        if "jobPosting/" in url:
            self.fichas.append(url.rsplit("/", 1)[1])
            return _Respuesta('<div class="show-more-less-html__markup">' + PM + "</div>")
        return _Respuesta(self.listado if (params or {}).get("start") == "0" else "")


def test_linkedin_lee_primero_las_fichas_de_los_titulos_del_cargo():
    # LinkedIn devuelve muchos avisos que no son del cargo; antes se leían en el orden en que llegaban.
    titulos = ["Asesor comercial", "Auxiliar de bodega", "Product Designer", "Vendedor de mostrador", "Diseñador UX/UI",
               "Conductor", "Senior Product Designer"]
    cliente = _LinkedIn("".join(_tarjeta(100 + i, t) for i, t in enumerate(titulos)))
    mapa = [{"id": "diseno-producto-ux", "consultas": ["product designer"]}]
    crudas, stats = linkedin_publico.buscar(cliente, mapa, [("CO", "Colombia")], {}, presupuesto=1, hoy="2026-11-26",
                                            max_fichas=3)
    assert set(cliente.fichas) == {"102", "104", "106"}  # las tres del cargo; ninguna de las otras cuatro
    assert stats["del_cargo"] == 3 and stats["fichas_del_cargo"] == 3 and stats["con_descripcion"] == 3
    assert len(crudas) == 7 and sum(bool(c["descripcion"]) for c in crudas) == 3  # las demás se guardan sin texto
    # Si sobra cupo, también las demás (un título genérico puede coincidir por su descripción, v25).
    cliente = _LinkedIn("".join(_tarjeta(100 + i, t) for i, t in enumerate(titulos)))
    _, stats = linkedin_publico.buscar(cliente, mapa, [("CO", "Colombia")], {}, presupuesto=1, hoy="2026-11-26",
                                       max_fichas=5)
    assert cliente.fichas[:3] == ["102", "104", "106"] and len(cliente.fichas) == 5 and stats["fichas_del_cargo"] == 3


# ── 1.2 Releer primero lo que le sirve a quien tiene menos ──────────────────────────────────────────────────────────
def test_la_relectura_va_por_turnos_entre_personas_y_primero_quien_va_corta():
    def v(n, familia, pais):
        return {"id": f"{familia}-{pais}-{n}", "familias": [{"familia": familia, "coincidencia": "exacto"}] if familia else [],
                "paises": [pais], "paises_mundo": [pais], "idioma": ""}
    de_ana = [v(n, "cargo:qa", "CO") for n in range(4)]       # Ana (QA, Colombia) tiene muchas
    de_luis = [v(n, "cargo:pm", "PE") for n in range(2)]      # Luis (PM, Perú) va corto y tiene pocas
    sin_persona = [v(0, "cargo:qa", "MX")]                    # de un cargo buscado, pero hoy no le sirve a nadie
    sin_cargo = [v(0, "", "CO")]
    personas = [{"familia": "cargo:qa", "perfil": "ana", "lugares": ["CO"], "peso": 5, "corto": False, "idiomas": ["es"]},
                {"familia": "cargo:pm", "perfil": "luis", "lugares": ["PE"], "peso": 5, "corto": True, "idiomas": ["es"]}]
    anterior = cobertura._PERSONAS
    cobertura._PERSONAS = [dict(p, lugares=set(p["lugares"])) for p in personas]
    try:
        orden = [x["id"] for x in cobertura.por_necesidad(sin_cargo + sin_persona + de_ana + de_luis)]
    finally:
        cobertura._PERSONAS = anterior
    assert orden[:4] == ["cargo:pm-PE-0", "cargo:qa-CO-0", "cargo:pm-PE-1", "cargo:qa-CO-1"]  # por turnos, Luis primero
    assert orden[-2:] == ["cargo:qa-MX-0", "-CO-0"]  # al final lo que no sirve a nadie y lo que no es de ningún cargo
    # Sin personas (modo heredado): el mismo orden de llegada, con lo que no es de ningún cargo al final.
    assert [x["id"] for x in cobertura.por_necesidad(sin_cargo + de_luis)] == ["cargo:pm-PE-0", "cargo:pm-PE-1", "-CO-0"]


def test_una_busqueda_en_espanol_no_es_turno_de_quien_solo_acepta_ingles():
    personas = [{"familia": "cargo:qa", "perfil": "es", "lugares": ["CO"], "peso": 5, "corto": False, "idiomas": ["es", "en"]},
                {"familia": "cargo:qa", "perfil": "en", "lugares": ["CO"], "peso": 5, "corto": False, "idiomas": ["en"]}]
    anterior = cobertura._PERSONAS
    cobertura._PERSONAS = [dict(p, lugares=set(p["lugares"])) for p in personas]
    try:
        suyas = cobertura.de_personas([("cargo:qa", ["analista qa"], "CO:ES", {}), ("cargo:qa", ["qa"], "CO", {})])
    finally:
        cobertura._PERSONAS = anterior
    assert [c[2] for c in suyas[0]] == ["CO:ES", "CO"] and [c[2] for c in suyas[1]] == ["CO"]


# ── 1.3 Indeed repasa cada noche los 30 días completos ─────────────────────────────────────────────────────────────
def _indeed(mapa, **opciones):
    pedidas = []

    def scrape(**kw):
        pedidas.append(kw)
        return pd.DataFrame([{"title": "Analista QA", "company": "Empresa", "location": "Bogotá, Colombia",
                              "description": "Pruebas de software.", "date_posted": None,
                              "job_url": "https://co.indeed.com/viewjob?jk=abc", "job_url_direct": "", "is_remote": False}])
    crudas, stats = indeed.buscar(mapa, [], {}, hoy="2026-11-26", scrape=scrape, **opciones)
    return pedidas, crudas, stats


MAPA_INDEED = [{"id": "cargo:qa", "consultas": ["qa", "qa engineer", "tester", "qa analyst", "sdet"],
                "consultas_es": ["analista qa", "analista de pruebas", "ingeniero de pruebas"],
                "paises_busqueda": ["CO"], "paises_es": ["CO"]}]


def test_el_repaso_de_indeed_pide_la_ventana_completa_con_varios_nombres_y_primero_en_espanol():
    indeed.VISTAS.clear()
    pedidas, crudas, stats = _indeed(MAPA_INDEED, presupuesto=50, max_dias=30, repaso=4)
    assert stats["repaso"] and all(p["hours_old"] == 30 * 24 and p["results_wanted"] == 100 for p in pedidas)
    es = MAPA_INDEED[0]["consultas_es"]
    en_espanol = [p for p in pedidas if p["search_term"] in es]
    assert {p["search_term"] for p in en_espanol if not p.get("is_remote")} == set(es)  # todos sus nombres en español…
    assert pedidas[:len(en_espanol)] == en_espanol                                      # …y antes que los demás
    generales = {p["search_term"] for p in pedidas if not p.get("is_remote")} - set(MAPA_INDEED[0]["consultas_es"])
    assert len(generales) == 4  # cuatro nombres de la combinación general, no uno por día
    # Con el filtro remoto no se repasa (la búsqueda sin filtro ya trae esos avisos): un solo nombre.
    assert sum(1 for p in pedidas if p.get("is_remote") and p["search_term"] in MAPA_INDEED[0]["consultas"]) == 1
    # El mismo aviso con varios nombres de una combinación se guarda una vez, y cuenta como visto hoy (v41).
    assert len([c for c in crudas if c["_busqueda"] == "cargo:qa@CO:ES"]) == 1
    assert indeed.VISTAS["https://co.indeed.com/viewjob?jk=abc"]["estado"] == "verificada"


def test_sin_repaso_indeed_busca_como_antes_y_la_busqueda_para_quien_falta_no_repasa():
    pedidas, _, stats = _indeed(MAPA_INDEED, presupuesto=50, max_dias=30)
    assert not stats["repaso"] and len(pedidas) == 4 and all(p["results_wanted"] == 30 for p in pedidas)
    anterior = cobertura._FALTANTES
    cobertura._FALTANTES = True
    try:
        pedidas, _, stats = _indeed(MAPA_INDEED, presupuesto=50, max_dias=30, repaso=4)
    finally:
        cobertura._FALTANTES = anterior
    assert not stats["repaso"] and all(p["results_wanted"] == 30 for p in pedidas)


def test_el_repaso_de_indeed_respeta_el_presupuesto_y_el_panel_lo_pide_solo_en_la_busqueda_completa(cfg):
    pedidas, _, stats = _indeed(MAPA_INDEED, presupuesto=5, max_dias=30, repaso=4)
    assert len(pedidas) == stats["busquedas"] == 5
    _, _, motor = ejecutor.preparar({"configuracion": cfg}, hoy())
    assert motor["presupuestos"]["indeed_repaso"] == 4 and motor["presupuestos"]["indeed_busquedas"] > 72
    perfil = cfg["perfiles"][0]["id"]
    _, _, motor = ejecutor.preparar({"configuracion": cfg}, hoy(), enfocar=[perfil])
    assert motor["presupuestos"]["indeed_repaso"] == 0 and motor["presupuestos"]["indeed_busquedas"] <= 72


# ── 1.4 Comprobación por carril ────────────────────────────────────────────────────────────────────────────────────
def test_en_la_cola_por_persona_linkedin_no_le_quita_el_turno_a_los_demas_sitios():
    ahora = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)

    def v(n, sitio):
        url = f"https://www.linkedin.com/jobs/view/{1000 + n}" if sitio == "linkedin" else f"https://co.computrabajo.com/o/{n}"
        return {"id": f"{sitio}-{n}", "titulo": "Analista QA", "enlace": url, "enlace_directo": "", "_enlaces": [url]}
    cola = [v(n, "linkedin") for n in range(3)] + [v(n, "computrabajo") for n in range(3)]
    pedidas = []

    def comprobar(u, titulo, ahora=None, **_):
        pedidas.append(u)
        return {"url": u, "destino": u, "estado": "verificada", "motivo": "ficha específica accesible",
                "comprobada_en": ahora.isoformat(), "http": 200, "saltos": 0, "ruta": [u]}
    original = verificar_enlaces.PAUSA_LINKEDIN
    verificar_enlaces.PAUSA_LINKEDIN = 0.01
    try:
        # Como antes: el máximo es de todos, y las tres de LinkedIn (que van primero) se lo gastan.
        assert verificar_enlaces.auditar(cola, {}, maximo=3, segundos=5, ahora=ahora, comprobar_url=comprobar) == 3
        assert all("linkedin" in u for u in pedidas)
        pedidas.clear()
        # Por carril: el máximo cuenta solo los sitios en paralelo; LinkedIn va aparte, por su tiempo.
        assert verificar_enlaces.auditar(cola, {}, maximo=3, segundos=5, ahora=ahora, comprobar_url=comprobar,
                                         por_carril=True) == 6
        assert sum("computrabajo" in u for u in pedidas) == 3 and sum("linkedin" in u for u in pedidas) == 3
    finally:
        verificar_enlaces.PAUSA_LINKEDIN = original


# ── 0. Medición ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_el_embudo_por_idioma_cuenta_solo_avisos_de_un_cargo_y_sin_datos_de_clientes():
    def v(idioma, fuente, comprobada, descripcion="x" * 300, cargo=True):
        return {"idioma": idioma, "fuente": fuente, "_descripcion": descripcion,
                "familias": [{"familia": "qa", "coincidencia": "exacto"}] if cargo else [],
                "verificacion": {"estado": "verificada" if comprobada else "pendiente"}}
    vacantes = [v("es", "LinkedIn", True), v("es", "LinkedIn", False), v("es", "Computrabajo", False),
                v("en", "Portales de empresas (lever)", True), v("", "LinkedIn", False, descripcion=""),
                v("fr", "Indeed", False), v("es", "LinkedIn", True, cargo=False)]
    e = medicion.embudo_idioma(vacantes)
    assert e["es"] == {"con_cargo": 3, "comprobadas": 1, "fuentes": {"LinkedIn": {"con_cargo": 2, "comprobadas": 1},
                                                                     "Computrabajo": {"con_cargo": 1, "comprobadas": 0}}}
    assert e["en"]["fuentes"] == {"Portales de empresas": {"con_cargo": 1, "comprobadas": 1}}
    assert e["sin_descripcion"]["con_cargo"] == 1 and e["otro"]["con_cargo"] == 1
    por_idioma = verificar_enlaces.resumen(vacantes)["por_idioma"]
    assert por_idioma["es"] == {"vacantes": 4, "comprobadas": 2} and por_idioma["en"] == {"vacantes": 1, "comprobadas": 1}


# ── 2.1 Bilingües ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_quien_acepta_espanol_e_ingles_busca_tambien_con_nombres_en_espanol(cfg):
    for p in cfg["perfiles"]:
        p["idiomas"] = ["es", "en"]
    mapa, _, motor = ejecutor.preparar({"configuracion": cfg}, hoy())
    con = [f for f in mapa if f["consultas_es"]]
    assert con and all(f["lugares_es"] for f in con)
    # El peso doble en los turnos sigue siendo solo de quien solo acepta español.
    solo = configuracion_demo()
    solo["perfiles"][0]["idiomas"] = ["es"]
    for p in solo["perfiles"][1:]:
        p["idiomas"] = ["es", "en"]
    _, _, motor_solo = ejecutor.preparar({"configuracion": solo}, hoy())
    peso = {p["perfil"]: p["peso"] for p in motor["personas_busqueda"]}
    peso_solo = {p["perfil"]: p["peso"] for p in motor_solo["personas_busqueda"]}
    primero = str(solo["perfiles"][0]["id"])
    assert peso_solo[primero] == peso[primero] * ejecutor.PESO_SOLO_ESPANOL
    assert all(peso_solo[k] == peso[k] for k in peso if k != primero)


# ── 2.2 Nombres hermanos en español, solos y con control ───────────────────────────────────────────────────────────
def test_los_nombres_hermanos_en_espanol_se_buscan_y_se_reconocen_sin_anadirlos():
    cargo = {"nombre": "Product Manager", "terminos_exactos": [], "terminos_similares": [], "terminos_excluidos": []}
    hermanos = dict(terminos.hermanos_es("Product Manager"))
    assert hermanos["jefe de producto"] == "mapa" and hermanos["líder de producto"] == "mapa"
    assert hermanos["director de producto"] == "similar"  # antes los similares del mapa solo se sugerían
    assert terminos.grado("Jefe de Producto Digital", cargo) == (
        "similar", {"regla": "título en español del mapa", "termino": "jefe de producto", "grado": "similar"})
    assert terminos.grado("Director de Producto", cargo)[1]["regla"] == "nombre hermano en español"
    assert terminos.grado("Jefe de bodega", cargo) == (None, None)
    # Un cargo compuesto usa los nombres que arma el glosario (v44: antes solo sugerencias).
    ia = {"nombre": "AI Product Manager", "terminos_exactos": [], "terminos_similares": [], "terminos_excluidos": []}
    assert ("Gerente de Producto de IA", "glosario") in terminos.hermanos_es("AI Product Manager")
    assert terminos.grado("Gerente de Producto de IA", ia)[1]["regla"] == "nombre hermano en español"
    # Un cargo que no está en el mapa no hereda nada.
    assert terminos.hermanos_es("Bodeguero") == ()


def test_lo_que_el_operador_excluye_no_se_usa_y_lo_que_ya_tiene_no_se_repite():
    cargo = {"nombre": "Product Manager", "terminos_exactos": ["Gerente de producto"], "terminos_similares": [],
             "terminos_excluidos": ["jefe de producto"]}
    usados = [x for x, _ in terminos.hermanos_del_cargo(cargo)]
    assert "jefe de producto" not in usados and "jefe de producto digital" not in usados  # contiene lo excluido
    assert "gerente de producto" not in usados and "líder de producto" in usados
    assert terminos.grado("Jefe de Producto", cargo) == (None, None)


def test_las_busquedas_en_espanol_usan_los_hermanos_y_todo_lo_buscado_se_reconoce(cfg):
    c = cfg["cargos"][0]
    raw = contenido.cargo_operativo(c)
    consultas = ejecutor.consultas_espanol(Cargo.model_validate(c), raw)
    assert consultas and all(terminos.en_espanol(t) and terminos.grado(t, raw)[0] for t in consultas)
    bases = {normalizar.titulo_base(x) for x in consultas}
    assert bases & {normalizar.titulo_base(x) for x, _ in terminos.hermanos_del_cargo(raw)}
    assert terminos.sugerir(c["nombre"], consultar_esco=False)["hermanos_es"]  # el panel los muestra


def test_un_nombre_hermano_sin_las_funciones_del_cargo_no_pasa_como_si_nada():
    # Un cargo con sus propios nombres: «Jefe de producto» no está entre ellos y entra solo, como hermano.
    cargo = contenido.cargo_operativo({"id": "x", "nombre": "Product Manager", "terminos_exactos": ["Product Manager"],
                                       "terminos_similares": [], "terminos_excluidos": [], "funciones": []})
    assert terminos.grado("Jefe de Producto", cargo)[0] == "similar"
    con_funciones = contenido.evidencia("Jefe de Producto", PM, cargo)
    assert con_funciones["nivel"] in ("fuerte", "debil") and not con_funciones["otro_oficio"]
    retail = ("Buscamos jefe de producto para la categoría de alimentos congelados. Negociación con proveedores, "
              "surtido en tiendas, márgenes y promociones en el punto de venta. Experiencia en retail. ") * 2
    sin_funciones = contenido.evidencia("Jefe de Producto Alimentos", retail, cargo)
    assert sin_funciones["nivel"] == "ninguna" and sin_funciones["otro_oficio"]  # va a «Por confirmar» (v49)
    familias.configurar([{"id": "cargo:x", "nombre": "Product Manager", "_control_cargo": cargo, "consultas": [],
                          "exactos": [], "similares": [], "cercanos": [], "excluir": []}])
    try:
        assert familias.clasificar("Jefe de Producto Alimentos", retail)[0]["coincidencia"] == familias.GRADO_OTRO_OFICIO
        assert familias.clasificar("Jefe de Producto", PM)[0]["coincidencia"] == "similar"
    finally:
        familias.configurar(None)


# ── 2.3 Letra pequeña en español ───────────────────────────────────────────────────────────────────────────────────
def _remota_de_chile(letra):
    return vacante.crear("Product Manager", "Empresa", "https://www.linkedin.com/jobs/view/555", "LinkedIn",
                         ubicacion="Santiago, Chile (Remoto)", descripcion=PM + letra, fecha="2026-11-20", remoto=True,
                         hoy="2026-11-26")


@pytest.mark.parametrize("letra,esperados", [
    ("Abierto a candidatos de Colombia y Perú. Ofrecemos seguro de salud en Chile.", ["CL", "CO", "PE"]),
    ("Contratamos en México, Colombia y Argentina.", ["AR", "CL", "CO", "MX"]),
    ("Vacante remota disponible para Colombia, Ecuador o Perú.", ["CL", "CO", "EC", "PE"]),
    ("Puedes postular desde Uruguay.", ["CL", "UY"]),
])
def test_la_letra_pequena_que_nombra_desde_donde_postular_suma_esos_paises(letra, esperados):
    v = _remota_de_chile(letra)
    assert sorted(v["paises"]) == esperados and v["nota_pais"] == paises.NOTA_APERTURA
    for pais in ("CO", "MX", "CL"):
        sirve = evaluar(v, medicion.perfil(pais, idiomas=("es",)), "2026-11-26")["compatible"]
        assert sirve == (pais in esperados)


@pytest.mark.parametrize("letra", [
    "Somos una empresa con presencia en 6 países: México, Colombia, Perú y Argentina. Líder en Latinoamérica.",
    "Nuestros clientes en Colombia, México y España confían en nosotros.",
    "Trabaja desde tu casa o donde quieras. Compensación en USD o en tu moneda local.",
    "No contratamos en Colombia ni en Perú por ahora.",
    "Tenemos equipos en Colombia y oficinas en México.",
])
def test_las_frases_de_la_empresa_las_vagas_y_las_negadas_no_abren_el_aviso(letra):
    v = _remota_de_chile(letra)
    assert v["paises"] == ["CL"] and v["nota_pais"] != paises.NOTA_APERTURA


def test_la_letra_pequena_no_convierte_una_oficina_en_remota_ni_pisa_una_restriccion():
    oficina = vacante.crear("Product Manager", "Empresa", "https://www.linkedin.com/jobs/view/556", "LinkedIn",
                            ubicacion="Santiago, Chile", descripcion=PM.replace("Trabajo remoto. ", "") +
                            "Trabajo presencial en nuestras oficinas. Contratamos en México y Colombia.",
                            fecha="2026-11-20", hoy="2026-11-26")
    assert oficina["paises"] == ["CL"] and oficina["modalidad"] != "remoto"
    restringida = _remota_de_chile("Debes residir en Chile para este cargo. Además, contratamos en México y Colombia.")
    assert restringida["paises"] == ["CL"]
