"""Contrato v16: antes de preguntarle a nadie, el sistema intenta confirmar solo la ubicación de las vacantes «por
confirmar» leyendo los datos estructurados de su ficha pública (schema.org JobPosting): `jobLocation.address`,
`applicantLocationRequirements` y `jobLocationType: TELECOMMUTE`, que publican LinkedIn, Greenhouse, Ashby y otros.

Sin IA, sin Apify, sin formularios y con presupuesto. Una evidencia positiva queda como una observación más de
ubicación (`_lugares`, fuente «ficha estructurada»): con un país cubierto se confirma, solo con extranjeros se descarta.
Un 403 o una página sin datos no prueban nada: la vacante sigue por confirmar. El resultado se recuerda unos días en
`trabajo/ubicacion_fichas.json` (solo enlace y ubicación pública del aviso; ningún dato de clientes).
"""
import json
import time
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from buscador import tiempos, vacante
from buscador.verificar_enlaces import NAVEGADOR, _coincide, _jobs, publica

VIGENCIA_DIAS = 7


def _texto(valor):
    if isinstance(valor, dict):
        return str(valor.get("name") or valor.get("addressCountry") or "").strip()
    return str(valor or "").strip()


def _lista(valor):
    return valor if isinstance(valor, list) else [valor] if valor else []


def observacion(html, titulo):
    """(ubicación como texto, remoto) a partir del JobPosting de la ficha, o None si no trae datos de lugar."""
    sopa = BeautifulSoup(html or "", "html.parser")
    trabajos = []
    for s in sopa.find_all("script", type="application/ld+json"):
        try:
            trabajos.extend(_jobs(json.loads(s.string or s.get_text())))
        except (ValueError, RecursionError):
            pass
    propios = [j for j in trabajos if _coincide(titulo, j.get("title", ""))] or (trabajos if len(trabajos) == 1 else [])
    if not propios:
        return None
    j = propios[0]
    remoto = "TELECOMMUTE" in str(j.get("jobLocationType", "")).upper()
    requisitos = [_texto(r) for r in _lista(j.get("applicantLocationRequirements")) if _texto(r)]
    lugares = []
    for lugar in _lista(j.get("jobLocation")):
        direccion = lugar.get("address", {}) if isinstance(lugar, dict) else {}
        if isinstance(direccion, dict):
            partes = [_texto(direccion.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry")]
            if any(partes):
                lugares.append(", ".join(p for p in partes if p))
    if remoto and requisitos:
        return "; ".join("Remote - " + r for r in requisitos), True
    if lugares:
        return "; ".join(lugares), True if remoto else None
    if requisitos:
        return "; ".join(requisitos), None
    return None


def _obtener(url, sesion, plazo):
    """HTML de la ficha o None. Solo GET, solo destinos públicos, sin seguir más de 3 redirecciones."""
    destino = url
    for _ in range(4):
        if not publica(destino) or time.monotonic() >= plazo:
            return None
        r = sesion.get(destino, headers=NAVEGADOR, allow_redirects=False, timeout=12)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            from urllib.parse import urljoin
            destino = urljoin(destino, r.headers["Location"])
            continue
        return r.text[:1_000_000] if r.status_code == 200 else None
    return None


def candidatas(vacantes, familias, hoy, dias=30):
    """Por confirmar, en español o inglés, recientes y del cargo de algún rol de la entrega; las más nuevas primero."""
    desde = (date.fromisoformat(hoy) - timedelta(days=dias)).isoformat()
    lista = [v for v in vacantes if v.get("confianza_pais") == "baja" and v.get("idioma") in ("es", "en")
             and (v.get("fecha_publicacion") or v.get("visto_primera_vez") or "") >= desde
             and (not familias or {f["familia"] for f in v.get("familias", [])} & set(familias))]
    return sorted(lista, key=lambda v: v.get("fecha_publicacion") or "", reverse=True)


def confirmar(vacantes, cache, hoy, familias=(), maximo=60, segundos=180, sesion=None, obtener=None, ahora=None):
    """Añade la observación de la ficha a las candidatas (hasta `maximo` lecturas nuevas). Devuelve conteos."""
    ahora = ahora or datetime.now(timezone.utc)
    plazo = time.monotonic() + segundos
    propia = sesion is None and obtener is None
    sesion = sesion or (requests.Session() if obtener is None else None)
    obtener = obtener or (lambda url: _obtener(url, sesion, plazo))
    vigente_desde = (ahora - timedelta(days=VIGENCIA_DIAS)).isoformat()
    stats = {"candidatas": 0, "leidas": 0, "confirmadas": 0, "extranjeras": 0, "sin_datos": 0, "desde_memoria": 0}
    try:
        for v in candidatas(vacantes, familias, hoy):
            stats["candidatas"] += 1
            url = v.get("enlace") or v.get("enlace_directo") or ""
            if not url:
                continue
            previo = cache.get(url)
            if previo and previo.get("fecha", "") >= vigente_desde:
                stats["desde_memoria"] += 1
                obs = (previo["ubicacion"], previo.get("remoto")) if previo.get("ubicacion") else None
            else:
                if stats["leidas"] >= maximo or time.monotonic() >= plazo:
                    continue
                stats["leidas"] += 1
                try:
                    html = obtener(url)
                except (requests.RequestException, OSError, ValueError):
                    html = None
                obs = observacion(html, v.get("titulo", "")) if html else None
                cache[url] = {"fecha": ahora.isoformat(timespec="seconds"),
                              **({"ubicacion": obs[0], "remoto": obs[1]} if obs else {})}
            if not obs:
                stats["sin_datos"] += 1
                continue
            v.setdefault("_lugares", vacante._lugares(v))
            v["_lugares"][url + "#ficha"] = {"titulo": v.get("titulo", ""), "ubicacion": obs[0], "remoto": obs[1],
                                            "vista_en": tiempos.instante(ahora.isoformat()), "fuente": "ficha estructurada"}
            vacante._aplicar_lugar(v, vacante._evaluar_lugares(v["_lugares"], v.get("_descripcion", "")))
            if v.get("confianza_pais") in ("alta", "media"):
                stats["confirmadas" if v.get("paises") else "extranjeras"] += 1
    finally:
        if propia and sesion is not None:
            sesion.close()
    return stats


def aplicar_operador(vacantes, decisiones):
    """Contrato v17: lo que el operador decidió en la bandeja vale en cada búsqueda (noche, mañana y cada hora).
    `decisiones`: {vacante_id: {"paises": [...]} | {"extranjero": True} | {"descartada": True}}. Devuelve cuántas tocó."""
    from buscador import paises
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    tocadas = 0
    for v in vacantes:
        ids = [v.get("id"), *v.get("_ids_fusionados", [])]
        decision = next((decisiones[i] for i in ids if i in decisiones), None)
        if not decision:
            continue
        tocadas += 1
        if decision.get("descartada"):
            v["descartada_operador"] = True
            continue
        ubicacion = "; ".join(nombres.get(c, c) for c in decision.get("paises") or []) or "pais extranjero"
        v.setdefault("_lugares", vacante._lugares(v))
        v["_lugares"][str(v.get("id")) + "#operador"] = {
            "titulo": v.get("titulo", ""), "ubicacion": ubicacion, "fuente": "operador",
            "remoto": True if v.get("modalidad") == "remoto" else None, "vista_en": v.get("vista_en", "")}
        vacante._aplicar_lugar(v, vacante._evaluar_lugares(v["_lugares"], v.get("_descripcion", "")))
    return tocadas
