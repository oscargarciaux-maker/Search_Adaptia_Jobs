"""La evidencia más fuerte conocida de una vacante no se pierde al volver a verla con menos información.

Reproduce lo observado el 9 nov 2026 entre capturas horarias consecutivas: países que pasaban de 1 a 21 (o de 2 a 1) y
fechas de Greenhouse que alternaban entre reales y «estimadas» según qué copia se vio esa hora.
"""
from copy import deepcopy
from itertools import permutations

import pytest

from buscador import bodega, paises, vacante
from panel import servicio
from panel.repositorio import RepositorioDemo

HOY = "2026-11-09"
TEXTO = ("We are hiring a Product Designer to own user research, prototyping and design systems for our "
         "payments product. You will work with engineering and product management every day. ") * 3
LUGAR = ("paises", "confianza_pais", "nota_pais", "modalidad")
FECHA = ("fecha_publicacion", "fecha_estimada", "publicada_en")
GH = "Portales de empresas (greenhouse)"


def crudo(enlace, fuente, ubicacion, **op):
    return dict({"titulo": "Product Designer", "empresa": "Acme", "enlace": enlace, "fuente": fuente,
                 "ubicacion": ubicacion, "descripcion": TEXTO, "fecha": "2026-11-01"}, **op)


def capturas(*horas, previas=()):
    """Corre una captura por hora (cada una con las copias vistas esa hora) y devuelve el inventario de cada hora."""
    estado, resultado = list(previas), []
    for crudas in horas:
        estado, _, _ = bodega.limpiar(estado, list(crudas), HOY, 30, set(), set())
        resultado.append(deepcopy(estado))
    return resultado


def unica(inventario):
    assert len(inventario) == 1
    return inventario[0]


def campos(v, nombres):
    return {k: v.get(k) for k in nombres}


LINKEDIN = crudo("https://www.linkedin.com/jobs/view/111", "LinkedIn", "Bogotá, Distrito Capital, Colombia",
                 enlace_directo="https://jobs.lever.co/acme/1")
# El portal trae la descripción más larga y una ubicación sin país: "Remote".
LEVER = crudo("https://jobs.lever.co/acme/1", "Lever", "Remote", remoto=True, descripcion=TEXTO + " Apply now.")


def test_ubicacion_confirmada_no_se_degrada_por_una_copia_incierta_en_ninguna_hora():
    horas = capturas([LINKEDIN, LEVER], [], [LEVER], [LINKEDIN], [])
    estados = [campos(unica(h), LUGAR) for h in horas]
    assert estados[0]["paises"] == ["CO"] and estados[0]["confianza_pais"] == "alta"
    assert all(e == estados[0] for e in estados)


def test_copia_incierta_sola_sigue_incierta_y_no_inventa_pais():
    v = unica(capturas([LEVER])[0])
    assert v["confianza_pais"] == "baja" and v["paises"] == paises.datos()["codigos"]


def test_volver_a_ver_la_misma_copia_no_cambia_nota_ni_orden():
    # Código ambiguo (PA: Panamá o Pensilvania) con una ciudad desconocida: sin confirmar, siempre la misma.
    # («Valbonne, fr» ya se reconoce como Francia desde el contrato v13.)
    sr = crudo("https://jobs.smartrecruiters.com/acme/1", "Portales de empresas (smartrecruiters)", "Conshohocken, PA")
    horas = capturas([sr], [], [sr], [sr], [])
    estados = [campos(unica(h), LUGAR) for h in horas]
    assert estados[0]["nota_pais"] == "confirmar ubicación"
    assert estados[0]["paises"] == paises.datos()["codigos"]
    assert all(e == estados[0] for e in estados)


def test_dos_ubicaciones_confirmadas_se_conservan_aunque_solo_se_vea_una():
    mexico = crudo("https://www.linkedin.com/jobs/view/222", "LinkedIn", "Ciudad de México, México",
                   enlace_directo="https://job-boards.greenhouse.io/acme/jobs/2")
    brasil = crudo("https://job-boards.greenhouse.io/acme/jobs/2", GH, "São Paulo, Brazil",
                   fecha_origen="first_published")
    horas = capturas([mexico, brasil], [], [brasil], [mexico], [])
    estados = [campos(unica(h), LUGAR) for h in horas]
    assert estados[0]["paises"] == ["MX"] and estados[0]["confianza_pais"] == "alta"  # v12: Brasil no se cubre
    assert all(e == estados[0] for e in estados)


def test_cambio_real_de_ubicacion_en_el_mismo_enlace_se_refleja():
    url = "https://job-boards.greenhouse.io/acme/jobs/3"
    antes = crudo(url, GH, "Buenos Aires, Argentina", fecha_origen="first_published")
    despues = crudo(url, GH, "Santiago, Chile", fecha_origen="first_published")
    h1, h2, h3 = capturas([antes], [despues], [])
    assert unica(h1)["paises"] == ["AR"]
    for h in (h2, h3):
        assert unica(h)["paises"] == ["CL"] and unica(h)["ubicacion"] == "Santiago, Chile"


def test_enlace_conocido_que_pasa_fuera_de_cobertura_se_retira():
    url = "https://job-boards.greenhouse.io/acme/jobs/4"
    previas = capturas([crudo(url, GH, "Buenos Aires, Argentina", fecha_origen="first_published")])[0]
    retiradas = []
    salida, _, descartes = bodega.limpiar(previas, [crudo(url, GH, "New York, NY, United States")], HOY, 30,
                                          set(), set(), retiradas=retiradas)
    assert salida == []
    assert [(v["id"], estado, razon) for v, estado, razon in retiradas] == [
        (previas[0]["id"], "archived", "sin elegibilidad regional")]
    assert not descartes["no se puede aplicar desde LATAM"]


def test_copia_nueva_fuera_de_cobertura_se_sigue_descartando_sin_retiro():
    retiradas = []
    salida, _, descartes = bodega.limpiar([], [crudo("https://job-boards.greenhouse.io/acme/jobs/5", GH,
                                                     "New York, NY, United States")], HOY, 30, set(), set(),
                                          retiradas=retiradas)
    assert salida == [] and retiradas == [] and descartes["no se puede aplicar desde LATAM"] == 1


def test_otra_fuente_con_ubicacion_confirmada_mantiene_la_vacante_si_el_portal_sale_de_cobertura():
    url = "https://job-boards.greenhouse.io/acme/jobs/6"
    linkedin = crudo("https://www.linkedin.com/jobs/view/666", "LinkedIn", "Lima, Perú", enlace_directo=url)
    portal = crudo(url, GH, "Buenos Aires, Argentina", fecha_origen="first_published")
    previas = capturas([linkedin, portal])[0]
    assert unica(previas)["paises"] == ["AR", "PE"]
    v = unica(capturas([crudo(url, GH, "New York, NY, United States", fecha_origen="first_published")],
                       previas=previas)[0])
    assert v["paises"] == ["PE"] and v["confianza_pais"] == "alta"


# ── Fechas ─────────────────────────────────────────────────────────────────────────────────────────────────────


def legado_greenhouse():
    """Vacante de Greenhouse guardada antes de registrar el origen de la fecha (podía ser updated_at)."""
    v = vacante.crear("Product Designer", "Acme", "https://job-boards.greenhouse.io/acme/jobs/7", GH,
                      ubicacion="Bogotá, Colombia", descripcion=TEXTO, fecha="2026-10-25", hoy=HOY)
    v.pop("_fecha_publicacion_origen", None)
    v.pop("_lugares", None)
    return v


def test_fecha_historica_sin_origen_de_greenhouse_sigue_sin_certificarse():
    v = unica(capturas([], previas=[legado_greenhouse()])[0])
    assert v["fecha_estimada"] is True and v["fecha_publicacion"] == "" and v["publicada_en"] == ""


def test_fecha_real_de_greenhouse_no_vuelve_a_estimada_cuando_no_se_ve():
    portal = crudo("https://job-boards.greenhouse.io/acme/jobs/7", GH, "Bogotá, Colombia", fecha="2026-10-28T10:00:00Z",
                   publicada_en="2026-10-28T10:00:00Z", fecha_origen="first_published")
    horas = capturas([portal], [], [portal], [], previas=[legado_greenhouse()])
    estados = [campos(unica(h), FECHA) for h in horas]
    assert estados[0] == {"fecha_publicacion": "2026-10-28", "fecha_estimada": False,
                          "publicada_en": "2026-10-28T10:00:00Z"}
    assert all(e == estados[0] for e in estados)


def test_fecha_real_aportada_por_otra_fuente_no_se_borra_por_la_regla_de_greenhouse():
    linkedin = crudo("https://www.linkedin.com/jobs/view/777", "LinkedIn", "Bogotá, Colombia", fecha="2026-10-27",
                     enlace_directo="https://job-boards.greenhouse.io/acme/jobs/7", descripcion="Ver detalle")
    horas = capturas([linkedin], [], [], previas=[legado_greenhouse()])
    for h in horas:
        v = unica(h)
        assert "greenhouse" in v["fuente"].lower()  # la copia con la descripción más larga
        assert (v["fecha_publicacion"], v["fecha_estimada"]) == ("2026-10-27", False)


def test_copia_sin_fecha_no_reemplaza_una_fecha_real():
    con_fecha = crudo("https://jobs.lever.co/acme/8", "Lever", "Bogotá, Colombia", fecha="2026-10-30")
    sin_fecha = dict(con_fecha, fecha="", descripcion=TEXTO + " Más texto.")
    for h in capturas([con_fecha], [sin_fecha], []):
        assert (unica(h)["fecha_publicacion"], unica(h)["fecha_estimada"]) == ("2026-10-30", False)


# ── Reglas de combinación ──────────────────────────────────────────────────────────────────────────────────────


def r(lista, confianza, nota="", modalidad="presencial"):
    return {"paises": lista, "confianza": confianza, "nota": nota, "modalidad": modalidad}


TODOS = paises.datos()["codigos"]


@pytest.mark.parametrize("resultados,esperado", [
    ([r(["CO"], "alta"), r(TODOS, "baja", "remoto: confirmar región", "remoto")], (["CO"], "alta", "")),
    ([r(["CO"], "alta"), r(["CO"], "media")], (["CO"], "alta", "")),
    ([r(["AR"], "alta"), r(["MX"], "media")], (["AR", "MX"], "media", "")),
    ([r([], "alta", "fuera de LATAM y España"), r(["CO"], "media")], (["CO"], "media", "")),
    ([r(TODOS, "baja", "confirmar ubicación"), r(TODOS, "baja", "confirmar ubicación")],
     (TODOS, "baja", "confirmar ubicación")),
    ([r(TODOS, "baja", "confirmar ubicación"), r(TODOS[:20], "baja", "por zona horaria")],
     (TODOS, "baja", paises.NOTA_INCIERTA)),
    ([r(["MX", "PE"], "alta", "restricción explícita de residencia")],
     (["MX", "PE"], "alta", "restricción explícita de residencia")),
])
def test_combinar_no_depende_del_orden_y_conserva_la_evidencia_mas_fuerte(resultados, esperado):
    for orden in permutations(resultados):
        combinado = paises.combinar(list(orden))
        assert (combinado["paises"], combinado["confianza"], combinado["nota"]) == esperado


def test_combinar_prefiere_modalidad_explicita_a_presencial_por_defecto():
    assert paises.combinar([r(["CO"], "alta"), r(TODOS, "baja", "", "remoto")])["modalidad"] == "remoto"
    assert paises.combinar([r(["CO"], "alta", "", "hibrido"), r(TODOS, "baja", "", "remoto")])["modalidad"] == "hibrido"


UBICACIONES = [("Bogotá, Colombia", None), ("Remote", True), ("Remote - LATAM", True), ("Ciudad de México, México", None),
               ("Valbonne, fr", None), ("Remote - Mexico", True), ("Hybrid - São Paulo, Brazil", None)]


@pytest.mark.parametrize("primera", UBICACIONES)
@pytest.mark.parametrize("segunda", UBICACIONES)
def test_unir_es_estable_al_volver_a_etiquetar_y_no_depende_del_orden(primera, segunda):
    a = vacante.crear("Product Designer", "Acme", "https://www.linkedin.com/jobs/view/9", "LinkedIn",
                      ubicacion=primera[0], remoto=primera[1], descripcion=TEXTO,
                      enlace_directo="https://jobs.lever.co/acme/9", hoy=HOY)
    b = vacante.crear("Product Designer", "Acme", "https://jobs.lever.co/acme/9", "Lever",
                      ubicacion=segunda[0], remoto=segunda[1], descripcion=TEXTO + " Apply now.", hoy=HOY)
    unida = vacante.unir(a, b)
    assert campos(unida, LUGAR) == campos(vacante.unir(b, a), LUGAR)
    assert campos(vacante.reetiquetar(deepcopy(unida)), LUGAR) == campos(unida, LUGAR)
    assert campos(vacante.unir(unida, deepcopy(b)), LUGAR) == campos(unida, LUGAR)
    assert "_lugares" not in vacante.publica(unida)


# ── Panel ──────────────────────────────────────────────────────────────────────────────────────────────────────


def test_panel_no_rehace_pais_ni_fecha_con_los_datos_publicos():
    """Los datos públicos no traen las observaciones ni el origen de la fecha; el panel conserva lo de la bodega."""
    repo = RepositorioDemo()
    r_demo = repo.resultados(None)
    fila = deepcopy(r_demo["filas"][0])
    datos = fila["catalogo_vacantes"]["datos"]
    datos.update(fuente=GH, ubicacion="Remote")  # fecha real de Greenhouse; ubicación mostrada sin país
    repo.resultados = lambda *a: {**r_demo, "filas": [fila]}
    resultado = servicio.resultados(repo, r_demo["clientes"][0]["id"])
    assert resultado["vacantes"][0]["motivos"] == [] and resultado["listas"] == 1
    assert servicio.whatsapp(repo, r_demo["clientes"][0]["id"])["vacantes"] == 1
