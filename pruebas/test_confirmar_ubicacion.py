"""Contrato v16: confirmar la ubicación leyendo los datos estructurados de la ficha, antes de preguntar a nadie."""
import json

from buscador import confirmar_ubicacion as c, vacante

HOY = "2026-11-13"
TEXTO = "We are looking for a product designer to join our team and work with users every week. " * 5


def _ficha(*trabajos):
    return "<html>" + "".join('<script type="application/ld+json">' + json.dumps(t) + "</script>" for t in trabajos) + "</html>"


def _vacante(n=1):
    return vacante.crear("Product Designer", "A", f"https://jobs.lever.co/a/{n}", "Lever", ubicacion="Remote Remoto",
                         descripcion=TEXTO, fecha="2026-11-12", hoy=HOY, remoto=True)


def test_lee_pais_ciudad_y_remoto_con_requisitos():
    oficina = {"@type": "JobPosting", "title": "Product Designer", "jobLocation": {"address": {
        "addressLocality": "Quito", "addressRegion": "Pichincha", "addressCountry": "EC"}}}
    remota = {"@type": "JobPosting", "title": "Product Designer", "jobLocationType": "TELECOMMUTE",
              "applicantLocationRequirements": [{"@type": "Country", "name": "Mexico"}, {"@type": "Country", "name": "Colombia"}]}
    assert c.observacion(_ficha(oficina), "Product Designer") == ("Quito, Pichincha, EC", None)
    assert c.observacion(_ficha(remota), "Product Designer") == ("Remote - Mexico; Remote - Colombia", True)
    assert c.observacion("<html>sin datos</html>", "Product Designer") is None
    otra = dict(oficina, title="Chef de cocina")
    assert c.observacion(_ficha(otra, dict(remota, title="Analista")), "Product Designer") is None  # no es esta ficha


def test_confirma_descarta_o_deja_por_confirmar():
    casos = [({"@type": "JobPosting", "title": "Product Designer", "jobLocationType": "TELECOMMUTE",
               "applicantLocationRequirements": {"@type": "Country", "name": "Colombia"}}, ["CO"], "confirmadas"),
             ({"@type": "JobPosting", "title": "Product Designer", "jobLocation": {"address": {
                 "addressLocality": "Austin", "addressRegion": "TX", "addressCountry": "US"}}}, [], "extranjeras")]
    for n, (jp, paises, contador) in enumerate(casos):
        v = _vacante(n)
        assert v["confianza_pais"] == "baja"
        stats = c.confirmar([v], {}, HOY, obtener=lambda url, jp=jp: _ficha(jp))
        assert v["paises"] == paises and v["confianza_pais"] in ("alta", "media") and stats[contador] == 1
    v = _vacante(9)
    stats = c.confirmar([v], {}, HOY, obtener=lambda url: None)  # 403, error o página sin datos: no prueba nada
    assert v["confianza_pais"] == "baja" and stats["sin_datos"] == 1


def test_memoria_y_presupuesto():
    jp = {"@type": "JobPosting", "title": "Product Designer", "jobLocationType": "TELECOMMUTE",
          "applicantLocationRequirements": {"@type": "Country", "name": "Peru"}}
    leidas, memoria = [], {}
    obtener = lambda url: leidas.append(url) or _ficha(jp)  # noqa: E731
    vacantes = [_vacante(n) for n in range(5)]
    stats = c.confirmar(vacantes, memoria, HOY, maximo=2, obtener=obtener)
    assert stats["leidas"] == 2 and len(leidas) == 2 and len(memoria) == 2
    otra = [_vacante(n) for n in range(2)]  # al día siguiente se usa lo leído, sin volver a pedir la ficha
    stats = c.confirmar(otra, memoria, HOY, maximo=0, obtener=obtener)
    assert stats["desde_memoria"] == 2 and len(leidas) == 2 and all(v["paises"] == ["PE"] for v in otra)


def test_solo_cargos_de_los_roles_e_idioma_valido():
    v = _vacante(1)
    v["familias"] = [{"familia": "qa", "coincidencia": "exacto"}]
    assert c.candidatas([v], {"diseno-producto-ux"}, HOY) == []
    v2 = dict(_vacante(2), idioma="")
    assert c.candidatas([v2], set(), HOY) == []


def test_v17_decisiones_del_operador_valen_en_cada_busqueda():
    from buscador import contrato
    a, b, d = _vacante(1), _vacante(2), _vacante(3)
    for v in (a, b, d):
        v.update(paises=["CO", "MX"], confianza_pais="baja")
    tocadas = c.aplicar_operador([a, b, d], {a["id"]: {"paises": ["EC"]}, b["id"]: {"extranjero": True},
                                             d["id"]: {"descartada": True}})
    assert tocadas == 3
    assert a["paises"] == ["EC"] and a["confianza_pais"] in ("alta", "media")
    assert b["paises"] == [] and b["confianza_pais"] == "alta"
    assert d["descartada_operador"] and contrato.entregable(d, HOY) == "descartada por el operador"


def test_v18_politica_remota_de_get_on_board_en_la_ficha():
    mundo_en = "<html><h3>Remote work policy</h3><p>Fully remote</p><p>Candidates can reside anywhere in the world.</p></html>"
    mundo_es = "<p>Política de trabajo remoto</p><p>Totalmente remoto</p><p>El trabajo es 100% remoto desde cualquier país.</p>"
    local_es = ("<p>Remoto sólo localmente</p><p>El trabajo es 100% remoto, pero los candidatos deben residir en "
                "Sudamérica, Centroamérica o México para postular.</p>")
    local_en = "<p>Locally remote only</p><p>Position is 100% remote, but candidates must reside in United States.</p>"
    assert c.observacion(mundo_en, "X") == c.observacion(mundo_es, "X") == ("Remote - Worldwide", True)
    assert c.observacion(local_es, "X") == ("Remote - Sudamérica, Centroamérica o México", True)
    assert c.observacion(local_en, "X") == ("Remote - United States", True)
    v = _vacante(9)
    v.update(enlace="https://www.linkedin.com/jobs/view/1", enlace_directo="https://www.getonbrd.com/jobs/design/x",
             confianza_pais="baja")
    assert c.enlace_ficha(v) == "https://www.getonbrd.com/jobs/design/x"
    leidas = []
    stats = c.confirmar([v], {}, HOY, obtener=lambda url: leidas.append(url) or local_es)
    assert leidas == ["https://www.getonbrd.com/jobs/design/x"] and stats["confirmadas"] == 1
    assert set(v["paises"]) >= {"AR", "CR", "MX"} and "ES" not in v["paises"]


def test_v18_varias_subregiones_y_paises_juntos():
    from buscador import paises
    r = paises.elegibles("X", "Remote - Sudamérica, Centroamérica o México", "", True)
    assert {"AR", "CR", "MX"} <= set(r["paises"]) and "ES" not in r["paises"]
    r = paises.elegibles("X", "Remote", "Candidates must reside in Central America, Chile or Mexico.", True)
    assert {"CR", "CL", "MX"} <= set(r["paises"]) and "AR" not in r["paises"]
