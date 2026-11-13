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
