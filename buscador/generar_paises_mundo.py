"""Genera `datos/paises_mundo.yaml` (contrato v15): la tabla ISO 3166 completa con siglas de 2 y 3 letras, nombres en
inglés, español y portugués, y subdivisiones (ISO 3166-2) de los países cubiertos y de los extranjeros más frecuentes.

Se corre a mano solo para actualizar la tabla; el buscador lee el archivo generado y no depende de `pycountry`:

    pip install pycountry && python -m buscador.generar_paises_mundo
"""
import gettext
from pathlib import Path

import yaml

from buscador import normalizar

DESTINO = Path(__file__).resolve().parent.parent / "datos" / "paises_mundo.yaml"
# Extranjeros que aparecen a menudo en los avisos: sus estados o regiones también se reconocen.
SUBDIVISIONES_EXTRANJERAS = ("US", "CA", "GB", "IN", "DE", "FR", "IT", "PL", "AU", "NL", "PT", "IE", "RO", "PH", "CN")
# Nombres de uso común que la norma no trae.
ALIAS = {
    "US": ["usa", "u.s.a", "united states of america", "estados unidos", "eeuu", "ee uu", "ee.uu"],
    "GB": ["uk", "u.k", "great britain", "britain", "england", "scotland", "wales", "northern ireland", "inglaterra",
           "escocia", "gales", "irlanda del norte", "reino unido"],
    "NL": ["holland", "holanda", "paises bajos", "the netherlands"], "KR": ["south korea", "corea del sur"],
    "KP": ["north korea", "corea del norte"], "AE": ["uae", "u.a.e", "emiratos", "emiratos arabes unidos"],
    "CZ": ["czechia", "chequia"], "RU": ["russia", "rusia"], "VN": ["vietnam"], "TW": ["taiwan"], "IR": ["iran"],
    "SY": ["syria", "siria"], "TZ": ["tanzania"], "BO": ["bolivia"], "VE": ["venezuela"], "MD": ["moldova"],
    "LA": ["laos"], "CD": ["congo"], "CI": ["ivory coast", "costa de marfil"], "TR": ["turkey", "turquia", "turkiye"],
}


def generar():
    import pycountry  # solo para generar; el buscador no lo necesita

    es = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["es"])
    pt = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["pt_BR"])
    sub_es = gettext.translation("iso3166-2", pycountry.LOCALES_DIR, languages=["es"], fallback=True)
    cubiertos = {p["codigo"] for p in yaml.safe_load((DESTINO.parent / "paises.yaml").read_text(encoding="utf-8"))["paises"]}
    salida = []
    for c in sorted(pycountry.countries, key=lambda c: c.alpha_2):
        crudos = [c.name, getattr(c, "common_name", ""), getattr(c, "official_name", ""), es.gettext(c.name),
                  pt.gettext(c.name), *ALIAS.get(c.alpha_2, [])]
        nombres = sorted({normalizar.texto(n) for n in crudos if n and len(normalizar.texto(n)) > 2})
        fila = {"iso2": c.alpha_2, "iso3": c.alpha_3, "nombres": nombres}
        if c.alpha_2 in cubiertos or c.alpha_2 in SUBDIVISIONES_EXTRANJERAS:
            subs = {normalizar.texto(n) for s in pycountry.subdivisions.get(country_code=c.alpha_2) or []
                    for n in (s.name, sub_es.gettext(s.name)) if n}
            fila["subdivisiones"] = sorted(s for s in subs if len(s) > 2)
        salida.append(fila)
    cabecera = ("# Generado por `python -m buscador.generar_paises_mundo` (ISO 3166-1 y 3166-2 de pycountry). No editar a\n"
                "# mano: para nombres o lugares adicionales usar datos/paises.yaml. Contrato v15.\n")
    DESTINO.write_text(cabecera + yaml.safe_dump({"paises": salida}, allow_unicode=True, sort_keys=False, width=120),
                       encoding="utf-8")
    return len(salida)


if __name__ == "__main__":
    print(f"{generar()} países escritos en {DESTINO}")
