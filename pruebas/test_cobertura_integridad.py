"""Casos de negocio: cobertura regional, afines, reintentos e identidad de las ofertas."""
from datetime import date, timedelta

import pandas as pd

from buscador import cobertura, entrega, familias, paises, supabase, vacante
from buscador.fuentes import ats, indeed, linkedin_publico

HOY = "2026-11-04"
TEXTO = "We are hiring a designer to improve our product with user research and prototyping. " * 6


def oferta(numero, titulo="Product Designer", lugar="Remote - Worldwide", texto=TEXTO):
    return vacante.crear(titulo, "Acme", f"https://jobs.lever.co/acme/{numero}", "Lever",
                         ubicacion=lugar, descripcion=texto, hoy=HOY)


def test_no_fusionar_otro_nivel_pais_o_requisicion():
    ofertas = [oferta(1, "Junior Product Designer", "Bogotá, Colombia"),
               oferta(2, "Senior Product Designer", "Madrid, España"),
               oferta(3, lugar="Lima, Peru"), oferta(4, texto=TEXTO + "Different responsibilities.")]
    assert len({v["id"] for v in ofertas}) == len(vacante.juntar(ofertas)) == 4


def test_copias_con_enlace_compartido_conservan_id_y_aliases():
    a = oferta(1)
    b = dict(a, id="otro-id", enlace="https://www.linkedin.com/jobs/view/12345678", enlace_directo=a["enlace"])
    unida, = vacante.juntar([a, b])
    assert unida["id"] == a["id"]
    assert set(entrega.huellas(unida)) >= {a["id"], a["enlace"], b["enlace"] + "/"}


def test_contenido_igual_solo_une_si_titulo_empresa_y_lugar_coinciden():
    a, b = oferta(1), oferta(2)
    assert len(vacante.juntar([a, b])) == 1
    b["ubicacion"] = "Remote - Colombia"
    assert len(vacante.juntar([a, b])) == 2


def test_union_no_convierte_paises_dudosos_en_confirmados():
    a = oferta(1, lugar="Colombia")
    b = oferta(1, lugar="Remote", texto="Design screens for our app. " * 20)
    unida = vacante.unir(a, b)
    assert unida["confianza_pais"] == "baja"
    assert "confirmar" in unida["nota_pais"]


def test_prioridad_remota_y_variedad_regional():
    ofertas = [oferta(1, lugar="Bogotá, Colombia"), oferta(2, lugar="Madrid, España"),
               oferta(3, lugar="Remote - Colombia, Mexico"), oferta(4),
               oferta(5, lugar="Remote", texto="Design screens for our app. " * 20)]
    for i, v in enumerate(ofertas):
        v["empresa"] = f"Empresa {i}"
    elegidas, _ = entrega.elegir(ofertas, {}, HOY, dict(entrega.config(), por_rol=2))
    seleccion = [v for v, _ in elegidas["product-designer"]]
    assert len(seleccion) == 2
    assert all(v["modalidad"] == "remoto" and v["confianza_pais"] == "alta" for v in seleccion)
    assert any("ES" in v["paises"] for v in seleccion)
    assert all(len(v["paises"]) > 1 for v in seleccion)


def test_remoto_no_significa_mundial_y_restriccion_manda():
    assert paises.elegibles("UX Designer", "Remote - Colombia")["paises"] == ["CO"]
    assert paises.elegibles("UX Designer", "Remote - Worldwide", "This role is US-only.")["paises"] == []
    assert paises.elegibles("UX Designer", "Remote")["confianza"] == "baja"


def test_consultas_rotan_por_todos_los_aliases_no_solo_el_primero():
    familia = next(f for f in familias.mapa() if f["id"] == "diseno-producto-ux")
    terminos = cobertura.consultas(familia)
    assert {"interaction designer", "design systems designer", "ux researcher", "ux writer"} <= set(terminos)
    vistos = set()
    for dia in range(len(terminos)):
        hoy = (date.fromisoformat(HOY) + timedelta(days=dia)).isoformat()
        vistos.update(cobertura.rotar(terminos, hoy, 4))
    assert vistos == set(terminos)
    for titulo in ("Interaction Designer", "Design Systems Designer", "UX Researcher", "UX Engineer"):
        assert any(f["familia"] == familia["id"] for f in familias.clasificar(titulo))
    assert not any(f["familia"] == familia["id"] for f in familias.clasificar("UI Artist Unreal"))


def test_presupuesto_repartido_entre_familias_y_paises_sin_favoritismo_fijo():
    combos = [(f, [], p) for f in ("ux", "qa", "po") for p in ("CO", "MX", "ES", "REMOTO_MUNDO")]
    turnos = cobertura.repartir(combos, {}, HOY, {"ux", "qa", "po"})
    assert {c[0] for c in turnos[:3]} == {"ux", "qa", "po"}
    assert all(c[2] == "REMOTO_MUNDO" for c in turnos[:3])
    estado = {f"{f}@REMOTO_MUNDO": HOY for f in ("ux", "qa", "po")}
    assert all(c[2] != "REMOTO_MUNDO" for c in cobertura.repartir(combos, estado, HOY)[:3])


def test_indeed_pide_remotas_y_rota_titulo_sin_perder_ventana_de_30_dias():
    llamadas = []
    def scrape(**op):
        llamadas.append(op)
        return pd.DataFrame([])
    estado = {"ux@ES:REMOTO": "2026-11-03"}
    indeed.buscar([{"id": "ux", "consultas": ["ux designer"], "similares": ["interaction designer"]}],
                  ["ES"], estado, 2, hoy=HOY, scrape=scrape)
    assert any(c.get("is_remote") for c in llamadas)
    assert all(c["hours_old"] == 30 * 24 for c in llamadas)
    assert all(c["country_indeed"] == "spain" for c in llamadas)


def test_reintentar_supabase_sin_repetir_entrega_y_conservar_fecha_original(tmp_path):
    pendientes, memoria, guardados = {}, {}, []
    def fallo(filas):
        return {"enviadas": 0, "errores": ["503"], "confirmadas": []}
    entrega.correr([oferta(1)], memoria, HOY, HOY + "T12:00:00Z", tmp_path, subir=fallo,
                   pendientes=pendientes, persistir=lambda p: guardados.append(dict(p)))
    assert pendientes and guardados[0]
    recibidas = []
    def exito(filas):
        recibidas.extend(filas)
        return {"enviadas": len(filas), "errores": [], "confirmadas": [f["external_id"] for f in filas]}
    resumen = entrega.correr([oferta(1)], memoria, "2026-11-05", "2026-11-05T12:00:00Z", tmp_path,
                              subir=exito, pendientes=pendientes)
    assert resumen["vacantes"] == 0 and not pendientes
    assert recibidas[0]["delivery_date"] == HOY


def test_lote_parcial_confirmar_solo_las_filas_aceptadas(monkeypatch):
    monkeypatch.setattr(supabase, "LOTE", 1)
    class Sesion:
        def post(self, url, json, **op):
            return type("R", (), {"status_code": 201 if json[0]["external_id"] == "a" else 503, "text": "error"})()
    filas = [{"external_id": "a"}, {"external_id": "b"}]
    resumen = supabase.subir(filas, "https://ejemplo.supabase.co", "clave-ficticia", Sesion())
    assert resumen["confirmadas"] == ["a"] and resumen["enviadas"] == 1
    assert resumen["errores"]


def test_descripcion_larga_conservada_y_requisitos_lever():
    assert len(oferta(1, texto="x" * 35000)["_descripcion"]) == 30000
    datos = [{"text": "UX Designer", "hostedUrl": "https://jobs.lever.co/a/1", "descriptionPlain": "Intro",
              "lists": [{"text": "Requirements", "content": "<p>Figma and user research</p>"}], "additional": "Benefits"}]
    texto = ats.vacantes_de("lever", datos, "A", "a")[0]["descripcion"]
    assert all(s in texto for s in ("Intro", "Requirements", "Figma", "Benefits"))


def test_paginacion_ats_y_detalles_smartrecruiters():
    class Cliente:
        def json(self, url, **op):
            if "/postings/1" in url:
                return {"jobAd": {"sections": {"jobDescription": {"text": TEXTO}}}}
            if "offset=" in url:
                return {"content": [{"id": "2", "name": "UX Designer"}], "totalFound": 2}
            return {"content": [{"id": "1", "name": "UX Designer"}], "totalFound": 2}
    datos = ats._tablero_completo(Cliente(), "smartrecruiters", "acme")
    assert len(datos["content"]) == 2
    v = ats.vacantes_de("smartrecruiters", datos, "Acme", "acme")[0]
    assert ats._completar(Cliente(), "smartrecruiters", "acme", v)
    assert v["descripcion"] == TEXTO.strip()


def test_paginacion_incompleta_no_es_evidencia_de_cierre():
    class Cliente:
        def json(self, url, **op):
            if "offset=" in url:
                return None
            return {"content": [{"id": "1"}], "totalFound": 200}
    assert ats._tablero_completo(Cliente(), "smartrecruiters", "acme") is None


def test_enlaces_puente_unen_grupos_y_se_conservan_aliases():
    a = oferta(1)
    b = oferta(2, texto=TEXTO + "Different responsibilities.")
    puente = dict(b, enlace=a["enlace"], enlace_directo=b["enlace"])
    unida, = vacante.juntar([a, b, puente])
    assert unida["id"] == a["id"]
    assert set(unida["_enlaces"]) == {a["enlace"], b["enlace"]}


def test_presupuesto_no_abandona_familias_fuera_de_entrega():
    combos = [(f, [], p) for f in ("ux", "qa", "video") for p in ("CO", "MX", "ES", "REMOTO")]
    turnos = cobertura.repartir(combos, {}, HOY, {"ux", "qa"})
    assert turnos[4][0] == "video"


def test_no_inferir_cierre_si_falla_otro_tablero_de_la_empresa():
    class Cliente:
        def json(self, url, **op):
            return [] if "lever.co" in url else None
    filas = [{"empresa": "Acme", "sistema": "lever", "slug": "acme"},
             {"empresa": "Acme", "sistema": "greenhouse", "slug": "acme"}]
    _, leidas, _ = ats.buscar(Cliente(), filas)
    assert "Acme" not in leidas
