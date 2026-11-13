"""Genera `datos/lugares_mundo.json.gz` (contrato v19): municipios y ciudades del mundo a partir de GeoNames
(https://www.geonames.org, licencia CC BY 4.0), para reconocer ubicaciones que las listas hechas a mano no traen
(«Inca», «Camas», «Abrera», «Harrisburg, PA», «Calcuta y alrededores»).

- **Países cubiertos:** todos los lugares de 1.000 habitantes o más (y sus otros nombres desde 5.000), y sus regiones
  de primer nivel.
- **Extranjeros:** ciudades de 15.000 habitantes o más; además, los nombres en otros idiomas (exónimos como «Londres»
  o «Calcuta») de las de 200.000 o más.
- Un nombre que está en dos países cubiertos, o en uno cubierto y uno extranjero, se descarta: **es ambiguo y nunca
  decide**. Se descartan también los nombres de menos de 4 letras y las palabras corrientes.

Se corre a mano solo para actualizar el archivo; el buscador lee el resultado y no depende de GeoNames ni de la red:

    curl -O https://download.geonames.org/export/dump/cities1000.zip && unzip cities1000.zip
    curl -O https://download.geonames.org/export/dump/admin1CodesASCII.txt
    python -m buscador.generar_lugares cities1000.txt admin1CodesASCII.txt
"""
import gzip
import json
import re
import sys
from pathlib import Path

from buscador import normalizar

DESTINO = Path(__file__).resolve().parent.parent / "datos" / "lugares_mundo.json.gz"
MINIMO_EXTRANJERO = 15000
MINIMO_EXONIMOS = 200000
MINIMO_ALTERNOS_PROPIOS = 5000
_LATINO = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
# Palabras que también son nombres de lugar en algún país: nunca deciden.
VACIAS = {"remote", "remoto", "remota", "hybrid", "hibrido", "office", "oficina", "central", "centro", "norte", "sur",
          "este", "oeste", "union", "libertad", "progreso", "victoria", "esperanza", "providencia", "independencia",
          "concepcion", "trinidad", "florida", "paraiso", "porvenir", "reforma", "nueva", "nuevo", "santa", "san",
          "lima", "home", "global", "worldwide", "anywhere", "location", "multiple", "various", "varios", "varias",
          "teletrabajo", "presencial", "capital", "distrito", "federal", "provincia", "region", "estado", "state",
          "city", "ciudad", "mexico", "panama", "guatemala", "colon", "cordoba", "valencia", "granada", "merida",
          "santiago", "leon", "trujillo", "barcelona", "toledo", "cartagena", "salamanca", "durango", "guadalupe"}
# Islas y regiones de España que los avisos escriben en español y GeoNames no trae como lugar.
PROPIOS_EXTRA = {"ES": ["islas baleares", "baleares", "mallorca", "menorca", "ibiza", "eivissa", "formentera",
                        "islas canarias", "canarias", "tenerife", "gran canaria", "lanzarote", "fuerteventura"]}


def _nombre(texto):
    t = normalizar.texto(texto or "")
    return t if len(t) >= 4 and t not in VACIAS and not t.isdigit() else ""


def generar(ruta_ciudades, ruta_regiones):
    from buscador import paises
    d = paises.datos()
    cubiertos = set(d["codigos"])
    comunes = set(d["palabras_comunes"])
    propios, extranjeros = {}, set()

    def propio(nombre, codigo):
        n = _nombre(nombre)
        if n and n not in comunes:
            propios.setdefault(n, set()).add(codigo)

    def extranjero(nombre):
        n = _nombre(nombre)
        if n and n not in comunes:
            extranjeros.add(n)

    with open(ruta_ciudades, encoding="utf-8") as archivo:
        for linea in archivo:
            c = linea.rstrip("\n").split("\t")
            if len(c) < 15:
                continue
            nombre, ascii_, alternos, pais, poblacion = c[1], c[2], c[3], c[8], int(c[14] or 0)
            if pais in cubiertos:
                propio(nombre, pais)
                propio(ascii_, pais)
                if poblacion >= MINIMO_ALTERNOS_PROPIOS:  # «Ribarroja del Turia», «Montcada»
                    for alt in alternos.split(","):
                        if _LATINO.match(alt):
                            propio(alt, pais)
            elif poblacion >= MINIMO_EXTRANJERO:
                extranjero(nombre)
                extranjero(ascii_)
                if poblacion >= MINIMO_EXONIMOS:
                    for alt in alternos.split(","):
                        if _LATINO.match(alt):
                            extranjero(alt)
    with open(ruta_regiones, encoding="utf-8") as archivo:
        for linea in archivo:
            c = linea.rstrip("\n").split("\t")
            if len(c) >= 3 and c[0][:2] in cubiertos:
                propio(c[1], c[0][:2])
                propio(c[2], c[0][:2])
    for codigo, nombres in PROPIOS_EXTRA.items():
        for n in nombres:
            propios.setdefault(normalizar.texto(n), set()).add(codigo)
    unicos = {n: next(iter(cs)) for n, cs in propios.items() if len(cs) == 1 and n not in extranjeros}
    solo_fuera = sorted(n for n in extranjeros if n not in propios)
    ambiguos = sum(1 for n in propios if n not in unicos) + sum(1 for n in extranjeros if n in propios)
    return {"fuente": "GeoNames (https://www.geonames.org), CC BY 4.0. Generado con buscador/generar_lugares.py.",
            "cubiertos": dict(sorted(unicos.items())), "extranjeros": solo_fuera, "ambiguos_descartados": ambiguos}


if __name__ == "__main__":
    salida = generar(sys.argv[1], sys.argv[2])
    with gzip.open(DESTINO, "wt", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(salida['cubiertos'])} lugares cubiertos, {len(salida['extranjeros'])} extranjeros, "
          f"{salida['ambiguos_descartados']} ambiguos descartados → {DESTINO}")
