"""Genera `datos/lugares_mundo.json.gz` (contratos v19 y v38): municipios y ciudades del mundo a partir de GeoNames
(https://www.geonames.org, licencia CC BY 4.0), para reconocer ubicaciones que las listas hechas a mano no traen
(«Inca», «Camas», «Abrera», «Harrisburg, PA», «Calcuta y alrededores», «Chicago», «Toronto», «Tokio»).

- **Países cubiertos:** todos los lugares de 1.000 habitantes o más (y sus otros nombres desde 5.000), y sus regiones
  de primer nivel.
- **Extranjeros:** ciudades de 15.000 habitantes o más; además, los nombres en otros idiomas (exónimos como «Londres»
  o «Calcuta») de las de 200.000 o más, y las regiones de primer nivel («Bavaria», «Ontario»).
- **País de una ciudad extranjera (v38):** el país que tiene, con ese nombre, al menos 5 veces más habitantes que
  cualquier otro («Chicago» → US, «London» → GB, «Toronto» → CA). Si el nombre también existe en un país cubierto, hacen
  falta 20 veces más («Los Angeles» → US frente a Los Ángeles de Chile). Si no llega, el lugar sigue siendo «de fuera»
  pero sin país («Cambridge», «Richmond», «Vancouver»): **nunca se adivina**.
- Un nombre que está en dos países cubiertos, o en uno cubierto y uno extranjero sin esa diferencia, se descarta: **es
  ambiguo y nunca decide**. Se descartan también los nombres de menos de 4 letras y las palabras corrientes.
- **Coordenadas (v38):** de las ciudades de 15.000 habitantes o más, para saber si un lugar queda cerca de la ciudad
  del perfil («Brooklyn» y «Jersey City» junto a «New York»).

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
DOMINIO_EXTRANJERO = 5   # contrato v38: veces más habitantes que el siguiente país para darle el país a la ciudad
DOMINIO_CUBIERTO = 20    # ... y frente a un lugar de un país cubierto con el mismo nombre
_LATINO = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
# Palabras que también son nombres de lugar en algún país: nunca deciden.
VACIAS = {"remote", "remoto", "remota", "hybrid", "hibrido", "office", "oficina", "central", "centro", "norte", "sur",
          "este", "oeste", "union", "libertad", "progreso", "victoria", "esperanza", "providencia", "independencia",
          "concepcion", "trinidad", "florida", "paraiso", "porvenir", "reforma", "nueva", "nuevo", "santa", "san",
          "lima", "home", "global", "worldwide", "anywhere", "location", "multiple", "various", "varios", "varias",
          "teletrabajo", "presencial", "capital", "distrito", "federal", "provincia", "region", "estado", "state",
          "city", "ciudad", "mexico", "panama", "guatemala", "colon", "cordoba", "valencia", "granada", "merida",
          "santiago", "leon", "trujillo", "barcelona", "toledo", "cartagena", "salamanca", "durango", "guadalupe",
          # contrato v38: regiones extranjeras con nombre de punto cardinal o genérico
          "north", "south", "east", "west", "northern", "southern", "eastern", "western", "northeast", "northwest",
          "southeast", "southwest", "midlands", "metropolitan", "metro", "island", "islands", "coast", "interior",
          # contrato v38: siglas de regiones de trabajo («Remote, APAC»: Apac también es un pueblo de Uganda)
          "apac", "emea", "amer", "americas", "latam", "mena", "dach", "benelux", "nordics", "nordic", "asean",
          "europe", "europa", "africa", "asia", "oceania", "remote only"}
# Islas y regiones (de España y Chile) que los avisos escriben así y GeoNames no trae como lugar.
PROPIOS_EXTRA = {"ES": ["islas baleares", "baleares", "mallorca", "menorca", "ibiza", "eivissa", "formentera",
                        "islas canarias", "canarias", "tenerife", "gran canaria", "lanzarote", "fuerteventura"],
                 # contrato v38: LinkedIn y los portales abrevian la región de Santiago de Chile
                 "CL": ["region metropolitana", "region metropolitana de santiago", "santiago metropolitan region",
                        "santiago metropolitan"]}


def _nombre(texto):
    t = normalizar.texto(texto or "")
    return t if len(t) >= 4 and t not in VACIAS and not t.isdigit() else ""


def generar(ruta_ciudades, ruta_regiones):
    from buscador import paises
    d = paises.datos()
    cubiertos = set(d["codigos"])
    comunes = set(d["palabras_comunes"])
    propios, extranjeros, principales = {}, set(), set()
    poblacion = {}  # nombre → {país: habitantes del lugar más grande con ese nombre}
    coordenadas = {}  # nombre → [(habitantes, país, estado, lat, lon)]

    def contar(n, pais, habitantes):
        por_pais = poblacion.setdefault(n, {})
        por_pais[pais] = max(por_pais.get(pais, 0), habitantes)

    def propio(nombre, codigo, habitantes=0):
        n = _nombre(nombre)
        if n and n not in comunes:
            propios.setdefault(n, set()).add(codigo)
            contar(n, codigo, habitantes)

    def extranjero(nombre, pais, habitantes):
        n = _nombre(nombre)
        if n and n not in comunes:
            extranjeros.add(n)
            contar(n, pais, habitantes)

    def ubicar(nombre, pais, estado, lat, lon, habitantes):
        # Las coordenadas se buscan siempre dentro de los países del perfil: aquí sí valen «Barcelona», «Lima» o
        # «Santiago», que como nombre solo nunca deciden el país.
        n = normalizar.texto(nombre or "")
        if len(n) >= 3 and not n.isdigit():
            coordenadas.setdefault(n, set()).add((habitantes, pais, estado if pais == "US" else "",
                                                  round(float(lat), 2), round(float(lon), 2)))

    with open(ruta_ciudades, encoding="utf-8") as archivo:
        for linea in archivo:
            c = linea.rstrip("\n").split("\t")
            if len(c) < 15:
                continue
            nombre, ascii_, alternos, pais, poblacion_ = c[1], c[2], c[3], c[8], int(c[14] or 0)
            otros = [alt for alt in alternos.split(",") if _LATINO.match(alt)]
            if pais in cubiertos:
                propio(nombre, pais, poblacion_)
                propio(ascii_, pais, poblacion_)
                if poblacion_ >= MINIMO_ALTERNOS_PROPIOS:  # «Ribarroja del Turia», «Montcada»
                    for alt in otros:
                        propio(alt, pais, poblacion_)
            elif poblacion_ >= MINIMO_EXTRANJERO:
                extranjero(nombre, pais, poblacion_)
                extranjero(ascii_, pais, poblacion_)
                principales.update({_nombre(nombre), _nombre(ascii_)})
                if poblacion_ >= MINIMO_EXONIMOS:
                    for alt in otros:
                        extranjero(alt, pais, poblacion_)
            else:  # pueblos extranjeros pequeños: no entran en la lista, pero cuentan como otro país con ese nombre
                for n in {_nombre(nombre), _nombre(ascii_)} - {""}:
                    contar(n, pais, poblacion_)
            if poblacion_ >= MINIMO_EXTRANJERO:
                for n in [nombre, ascii_] + (otros if poblacion_ >= MINIMO_EXONIMOS else []):
                    ubicar(n, pais, c[10], c[4], c[5], poblacion_)
    regiones_fuera = {}
    with open(ruta_regiones, encoding="utf-8") as archivo:
        for linea in archivo:
            c = linea.rstrip("\n").split("\t")
            if len(c) < 3:
                continue
            if c[0][:2] in cubiertos:
                propio(c[1], c[0][:2])
                propio(c[2], c[0][:2])
            else:
                for n in {_nombre(c[1]), _nombre(c[2])} - {""} - comunes:
                    regiones_fuera.setdefault(n, set()).add(c[0][:2])
    for codigo, nombres in PROPIOS_EXTRA.items():
        for n in nombres:
            propios.setdefault(normalizar.texto(n), set()).add(codigo)

    def dominante(n, de_fuera):
        """País con DOMINIO veces más habitantes que cualquier otro con ese nombre, o ""."""
        por_pais = sorted(poblacion.get(n, {}).items(), key=lambda x: -x[1])
        candidatos = [(p, h) for p, h in por_pais if (p not in cubiertos) == de_fuera]
        if not candidatos:
            return ""
        pais, habitantes = candidatos[0]
        for otro, h in por_pais:
            if otro != pais and habitantes < h * (DOMINIO_CUBIERTO if (otro in cubiertos) == de_fuera
                                                  else DOMINIO_EXTRANJERO):
                return ""
        return pais

    unicos, fuera = {}, {}
    for n, codigos in propios.items():
        # Al revés no se aplica: los nombres alternos de los lugares cubiertos traen transliteraciones («Kuito» es
        # Quito y también una ciudad de Angola) y la lista de cubiertos ya decide casi todo.
        if n not in extranjeros and len(codigos) == 1:
            unicos[n] = next(iter(codigos))
    for n in extranjeros:
        if n not in propios:
            fuera[n] = dominante(n, True)
        elif n in principales and n not in d["ciudades"] and dominante(n, True):
            # v38: «Los Angeles», «Berlin»: el de fuera es mucho más grande. Solo con su nombre principal (los
            # exónimos chocan: «Colonia» es Köln y una ciudad de Uruguay) y nunca contra la lista curada de paises.yaml.
            fuera[n] = dominante(n, True)
    for n, codigos in regiones_fuera.items():
        if n in propios or n in unicos or n in d["ciudades"]:
            continue
        de_ciudad = fuera.get(n)
        pais = next(iter(codigos)) if len(codigos) == 1 else ""
        if n not in fuera:
            otros = {p for p, h in poblacion.get(n, {}).items() if h >= MINIMO_EXTRANJERO} - codigos
            fuera[n] = "" if otros else pais
        elif de_ciudad != pais:
            fuera[n] = ""  # «Ontario» es provincia de Canadá y ciudad de EE. UU.: de fuera, sin país
    for n in set(fuera) & set(d["ciudades"]):  # la lista curada de paises.yaml manda («Acre» es el estado de Brasil)
        curados = d["ciudades"][n]
        fuera[n] = curados[0] if len(curados) == 1 and curados[0] not in cubiertos else ""
    ambiguos = sum(1 for n in propios if n not in unicos) + sum(1 for n in extranjeros if n in propios and n not in fuera)
    lugares = {n: [[p, e, la, lo] for _, p, e, la, lo in sorted(v, key=lambda x: -x[0])[:6]]
               for n, v in coordenadas.items()}  # todas: se buscan siempre dentro de los países del perfil
    return {"fuente": "GeoNames (https://www.geonames.org), CC BY 4.0. Generado con buscador/generar_lugares.py.",
            "cubiertos": dict(sorted(unicos.items())), "extranjeros": dict(sorted(fuera.items())),
            "coordenadas": dict(sorted(lugares.items())), "ambiguos_descartados": ambiguos}


if __name__ == "__main__":
    salida = generar(sys.argv[1], sys.argv[2])
    with gzip.open(DESTINO, "wt", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(salida['cubiertos'])} lugares cubiertos, {len(salida['extranjeros'])} extranjeros "
          f"({sum(1 for p in salida['extranjeros'].values() if p)} con país), {len(salida['coordenadas'])} con coordenadas, "
          f"{salida['ambiguos_descartados']} ambiguos descartados → {DESTINO}")
