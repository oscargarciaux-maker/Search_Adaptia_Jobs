"""Expansión abierta sin IA: variantes, mapa opcional y vocabulario público ESCO."""
from functools import lru_cache
import re

import requests
from rapidfuzz import fuzz

from buscador import familias, normalizar

ESCO = "https://ec.europa.eu/esco/api"


def variantes(cargo):
    base = " ".join(cargo.split())
    compacto = re.sub(r"\bfront[\s-]*end\b", "frontend", base, flags=re.I)
    compacto = re.sub(r"\bback[\s-]*end\b", "backend", compacto, flags=re.I)
    salida = [base, compacto]
    for termino in ("frontend", "backend", "fullstack"):
        if termino in compacto.lower():
            salida += [f"{termino} developer", f"{termino} engineer", f"desarrollador {termino}"]
    return list(dict.fromkeys(salida))


def sugerir(cargo, sesion=None, consultar_esco=True):
    base = normalizar.titulo_base(cargo)
    exactos, similares, evidencia = variantes(cargo), [], []
    # El mapa existente es una ayuda, nunca un requisito para aceptar un cargo nuevo. Solo aportan las familias donde
    # el cargo es título exacto o similar; «cercano» señala un oficio vecino (motion designer para editor de video),
    # no un equivalente. Se usa el grado más fuerte encontrado para no mezclar oficios distintos.
    coincidencias = []
    for orden, f in enumerate(familias.mapa_base()):
        nivel = 0 if base == normalizar.texto(f["id"]) else next(
            (i for i, g in enumerate(("exacto", "similar")) if base in f["_titulos"][g]), None)
        if nivel is not None:
            coincidencias.append((nivel, orden, f))
    mejor = min((n for n, _, _ in coincidencias), default=None)
    for nivel, _, f in sorted(coincidencias, key=lambda x: x[:2]):
        if nivel == mejor:
            (exactos if nivel == 0 else similares).extend(f.get("exactos", []))
            similares.extend(f.get("similares", []))
    if coincidencias:
        evidencia.append("Equivalentes del mapa existente")
    if consultar_esco:
        try:
            cli = sesion or requests.Session()
            r = cli.get(ESCO + "/search", params={"text": cargo, "type": "occupation", "language": "es", "limit": 5}, timeout=8)
            r.raise_for_status()
            resultados = r.json().get("_embedded", {}).get("results", [])
            for resultado in resultados:
                titulo = resultado.get("title") or resultado.get("label") or ""
                if not isinstance(titulo, str) or fuzz.token_sort_ratio(base, normalizar.titulo_base(titulo)) < 86:
                    continue
                uri = resultado.get("uri", "")
                if not uri.startswith(("http://data.europa.eu/esco/occupation/", "https://data.europa.eu/esco/occupation/")):
                    continue
                for idioma in ("es", "en"):
                    detalle = cli.get(ESCO + "/resource/occupation", params={"uri": uri, "language": idioma}, timeout=8)
                    detalle.raise_for_status()
                    d = detalle.json()
                    for campo in ("preferredLabel", "alternativeLabel"):
                        labels = d.get(campo, {})
                        labels = labels.get(idioma, []) if isinstance(labels, dict) else labels
                        similares += [labels] if isinstance(labels, str) else labels if isinstance(labels, list) else []
                evidencia.append("ESCO, vocabulario ocupacional público")
                break
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            evidencia.append("ESCO no disponible; puedes completar términos desde la interfaz")
    claves, principales, limpios = set(), [], []
    for destino, terminos in ((principales, exactos), (limpios, similares)):
        for x in terminos:
            if isinstance(x, str) and 2 <= len(x) <= 120 and normalizar.titulo_base(x) not in claves:
                claves.add(normalizar.titulo_base(x))
                destino.append(x)
    return {"terminos_exactos": principales[:30], "terminos_similares": limpios[:30],
            "fuentes": list(dict.fromkeys(evidencia)) or ["Variantes de escritura"],
            "requiere_revision": not limpios,
            "nota": "Revisa los términos antes de guardar; un equivalente no garantiza pertinencia de cada anuncio."}


# Los términos de un cargo se comparan contra miles de títulos: normalizarlos una sola vez (funciones puras).
_base = lru_cache(maxsize=32768)(normalizar.titulo_base)
_texto = lru_cache(maxsize=32768)(normalizar.texto)


def grado(titulo, cargo):
    base = _base(titulo)
    if not base:
        return None, None
    completo = _texto(titulo)
    if any(normalizar.contiene_frase(completo, _texto(x)) for x in cargo.get("terminos_excluidos", [])):
        return None, None
    for campo, valor in (("terminos_exactos", "exacto"), ("terminos_similares", "similar")):
        terminos = [cargo["nombre"], *cargo.get(campo, [])] if campo == "terminos_exactos" else cargo.get(campo, [])
        for t in terminos:
            canon = _base(t)
            if canon and normalizar.contiene_frase(base, canon):
                return valor, {"regla": "término de cargo", "termino": t, "grado": valor}
    if len(base) >= 6:
        opciones = [cargo["nombre"], *cargo.get("terminos_exactos", []), *cargo.get("terminos_similares", [])]
        for t in opciones:
            puntaje = fuzz.token_sort_ratio(base, _base(t))
            if puntaje >= 90:
                return "similar", {"regla":"similitud textual", "termino":t, "grado":"similar", "similitud_textual":round(puntaje)}
    return None, None
