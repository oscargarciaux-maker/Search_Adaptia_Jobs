"""Ficha de una vacante para el panel (lista grande, PR 3, contrato v29).

La descripción se muestra en bloques de texto (párrafo, viñeta, subtítulo): nunca HTML crudo en el navegador. Si el
catálogo no la tiene, se lee una sola vez del `JobPosting` de la ficha original, con la misma lectura acotada que los
posts (contrato v28): solo dominios de la lista fija `datos/dominios.yaml`, 1 MB, 12 s, solo GET, sin cookies ni
formularios y sin redirecciones fuera de la lista.
"""
import json
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from buscador import enlaces

MAX_BYTES_FICHA = 1_000_000
MAX_DESCRIPCION = 30000  # el mismo tope de `catalogo_vacantes.description_full`
_VINETA = re.compile(r"^\s*(?:[-•*·▪●◦–]|\d{1,2}[.)])\s+")
_NEGRITA_ENTERA = re.compile(r"\*\*([^*]+?)\*\*\s*:?")
_BLOQUES_HTML = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "br")


def dominio_conocido(url):
    """Solo sistemas de postulación y portales de la lista fija (`datos/dominios.yaml`): quien escribe un post o un aviso
    no elige a qué servidor se conecta el sistema (evita SSRF y descargas de sitios arbitrarios)."""
    d = enlaces.dominios()
    h = enlaces.host(url)
    return bool(h) and not enlaces._en(h, d["agregadores"]) and (enlaces._en(h, d["originales"]) or
                                                                  enlaces._en(h, d["portales"]))


def leer_acotado(url, sesion, segundos=12):
    """HTML de una ficha con tope de 1 MB y de tiempo, sin seguir redirecciones fuera de la lista fija."""
    from buscador.verificar_enlaces import NAVEGADOR, publica
    plazo = time.monotonic() + segundos
    destino = url
    for _ in range(4):
        if not dominio_conocido(destino) or not publica(destino) or time.monotonic() >= plazo:
            return None
        with sesion.get(destino, headers=NAVEGADOR, allow_redirects=False, stream=True, timeout=(5, 8)) as r:
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                destino = urljoin(destino, r.headers["Location"])
                continue
            if r.status_code != 200:
                return None
            partes, total = [], 0
            for trozo in r.iter_content(65536):
                total += len(trozo)
                if total > MAX_BYTES_FICHA or time.monotonic() >= plazo:
                    return None
                partes.append(trozo)
            return b"".join(partes).decode(r.encoding or "utf-8", errors="replace")
    return None


def descripcion_jobposting(html, titulo=""):
    """El texto de `JobPosting.description` de la ficha (con saltos de línea y viñetas), o "" si no lo trae."""
    from buscador.verificar_enlaces import _coincide, _jobs
    sopa = BeautifulSoup(html or "", "html.parser")
    trabajos = []
    for s in sopa.find_all("script", type="application/ld+json"):
        try:
            trabajos.extend(_jobs(json.loads(s.string or s.get_text())))
        except (ValueError, RecursionError):
            continue
    propios = [j for j in trabajos if titulo and _coincide(titulo, j.get("title", ""))]
    propios = propios or (trabajos if len(trabajos) == 1 else [])
    descripcion = next((j.get("description") for j in propios if isinstance(j.get("description"), str)), "")
    return a_texto(descripcion)[:MAX_DESCRIPCION]


def a_texto(html):
    """HTML de una descripción → texto plano con una línea por bloque, «- » delante de cada viñeta y las negritas entre
    «**» (contrato v34: el panel las pinta en negrita; la búsqueda las ignora al normalizar)."""
    if "<" not in (html or ""):
        return (html or "").strip()
    sopa = BeautifulSoup(html, "html.parser")
    for oculto in sopa.find_all(("script", "style", "noscript", "template")):
        oculto.decompose()
    for negrita in sopa.find_all(("strong", "b")):
        contenido = negrita.get_text()
        if contenido.strip():
            negrita.replace_with(contenido.replace(contenido.strip(), "**" + contenido.strip() + "**", 1))
    for li in sopa.find_all("li"):
        li.insert(0, "\n- ")
    for titulo in sopa.find_all(("h1", "h2", "h3", "h4", "h5", "h6")):
        titulo.insert(0, "\n## ")
    for etiqueta in sopa.find_all(_BLOQUES_HTML):
        etiqueta.insert_before("\n")
        etiqueta.insert_after("\n")
    lineas = [re.sub(r"[ \t\xa0]+", " ", x).strip() for x in sopa.get_text().splitlines()]
    texto = "\n".join(lineas)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def bloques(texto, maximo=400):
    """Texto plano → [{tipo: "p"|"li"|"h", texto}] para pintarlo con su formato y sin HTML."""
    salida = []
    for linea in a_texto(texto or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        entera = _NEGRITA_ENTERA.fullmatch(linea)
        if entera and len(entera.group(1)) <= 80:  # una línea toda en negrita es un subtítulo
            salida.append({"tipo": "h", "texto": entera.group(1).strip().rstrip(":")})
        elif linea.startswith("#"):
            salida.append({"tipo": "h", "texto": linea.lstrip("#").strip().rstrip(":")})
        elif _VINETA.match(linea):
            salida.append({"tipo": "li", "texto": _VINETA.sub("", linea)})
        elif len(linea) <= 60 and linea.endswith(":") or (len(linea) <= 40 and linea.isupper() and len(linea) > 3):
            salida.append({"tipo": "h", "texto": linea.rstrip(":")})
        else:
            salida.append({"tipo": "p", "texto": linea})
        if len(salida) >= maximo:
            break
    return salida


def traer_descripcion(urls, titulo="", obtener=None, sesion=None):
    """Lee la descripción de la primera ficha de la lista fija que la traiga. `obtener(url)` se puede sustituir en las
    pruebas; por defecto es la lectura acotada."""
    if obtener is None:
        import requests
        sesion = sesion or requests.Session()
        def obtener(url):
            return leer_acotado(url, sesion)
    for url in [u for u in urls if u and dominio_conocido(u)][:2]:
        html = obtener(url)
        texto = descripcion_jobposting(html, titulo) if html else ""
        if texto:
            return texto
    return ""
