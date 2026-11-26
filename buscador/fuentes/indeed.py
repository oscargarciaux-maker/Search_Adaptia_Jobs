"""Indeed por país con JobSpy (su API móvil; la página web responde 403 a los servidores). Sin sesión.

Como LinkedIn, rota las combinaciones (familia, país) y cada corrida toma las que hace más tiempo no se revisan.
"""
import time
from datetime import datetime, timezone

from buscador import cobertura

NOMBRE = "Indeed"
# Países que Indeed tiene en JobSpy (código ISO → nombre en JobSpy). Contrato v40: todos los que JobSpy admite (62), así
# cualquier persona del panel tiene Indeed donde vive o trabajaría; solo se busca en los países de sus lugares.
PAISES = {"AR": "argentina", "AU": "australia", "AT": "austria", "BH": "bahrain", "BE": "belgium", "BR": "brazil",
          "CA": "canada", "CL": "chile", "CN": "china", "CO": "colombia", "CR": "costa rica", "CZ": "czech republic",
          "DK": "denmark", "EC": "ecuador", "EG": "egypt", "FI": "finland", "FR": "france", "DE": "germany",
          "GR": "greece", "HK": "hong kong", "HU": "hungary", "IN": "india", "ID": "indonesia", "IE": "ireland",
          "IL": "israel", "IT": "italy", "JP": "japan", "KW": "kuwait", "LU": "luxembourg", "MY": "malaysia",
          "MX": "mexico", "MA": "morocco", "NL": "netherlands", "NZ": "new zealand", "NG": "nigeria", "NO": "norway",
          "OM": "oman", "PK": "pakistan", "PA": "panama", "PE": "peru", "PH": "philippines", "PL": "poland",
          "PT": "portugal", "QA": "qatar", "RO": "romania", "SA": "saudi arabia", "SG": "singapore",
          "ZA": "south africa", "KR": "south korea", "ES": "spain", "SE": "sweden", "CH": "switzerland",
          "TW": "taiwan", "TH": "thailand", "TR": "türkiye", "UA": "ukraine", "AE": "united arab emirates",
          "GB": "uk", "US": "usa", "UY": "uruguay", "VE": "venezuela", "VN": "vietnam"}


# Contrato v41: avisos que la búsqueda de Indeed mostró en esta corrida (enlace → comprobación). Indeed solo lista avisos
# activos y responde 401 a cualquier comprobación directa: verse hoy en su búsqueda cuenta como abierta 24 h.
VISTAS = {}


def _anotar_vista(*enlaces_aviso):
    hora = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    from buscador import verificar_enlaces
    for enlace in enlaces_aviso:
        # Solo páginas de Indeed (por el dominio real, no por el texto): el enlace de la empresa se comprueba como siempre.
        if enlace and verificar_enlaces.sin_comprobacion_directa(enlace):
            VISTAS[enlace] = {"estado": "verificada", "motivo": "vista hoy en la búsqueda de Indeed",
                              "comprobada_en": hora, "destino": enlace}


def _nombre_en(pais):
    """Nombre en inglés del país de un Indeed de fuera de LATAM y España, o "" (los de la tabla propia no se completan)."""
    from buscador import paises
    if pais in paises.datos()["codigos"] or pais == "BR":
        return ""
    return next((x["nombre_en"] for x in paises.mundo()["lista"] if x["codigo"] == pais), "")


def ubicacion(texto, pais):
    """La ubicación del aviso; si no nombra ningún país (p. ej. «Remote») y el Indeed es de fuera de LATAM, se añade el
    país de ese Indeed, igual que cuando el aviso viene sin ubicación."""
    texto = _limpio(texto)
    nombre_en = _nombre_en(pais)
    if not texto:
        return nombre_en or PAISES[pais].title()
    if nombre_en:
        from buscador import paises
        if not paises.alcance("", texto).get("paises_mundo"):
            return f"{texto}, {nombre_en}"
    return texto


def _limpio(valor):
    if valor is None:
        return ""
    try:
        import math
        if isinstance(valor, float) and math.isnan(valor):
            return ""
    except Exception:  # noqa: BLE001
        pass
    return str(valor).strip()


# Contrato v50: en el repaso de cada noche, cuántos resultados se piden por búsqueda y cuántos nombres de una
# combinación en español se buscan (las demás, `repaso` nombres).
RESULTADOS_REPASO = 100
NOMBRES_REPASO_ES = 8


def buscar(mapa, paises_activos, estado, presupuesto, hoy=None, max_dias=30, por_busqueda=30, reloj=time.monotonic,
           limite_segundos=None, scrape=None, prioritarias=(), desfase_terminos=0, repaso=0):
    """Vacantes crudas de Indeed y estadísticas. `scrape` permite probar sin red (por defecto jobspy.scrape_jobs).
    `repaso` (contrato v50, la búsqueda de cada noche): cuántos nombres de cada combinación se buscan con la ventana
    completa de `max_dias`. Indeed no deja comprobar un aviso directamente (v41): solo cuenta como abierto el día que
    su búsqueda lo muestra. Pidiendo cada noche solo lo publicado desde la vez anterior, y con un nombre por día, un
    aviso de hace tres días no volvía a verse: el 26 nov había 259 en español con cargo sin comprobar por eso. Una
    búsqueda de 30 días tarda 1 segundo. Con 0 (capturas horarias, refuerzo y «Buscar ahora» para quien falta), como
    antes: un nombre y solo lo nuevo."""
    if scrape is None:
        from jobspy import scrape_jobs as scrape
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    repaso = 0 if cobertura._FALTANTES else int(repaso or 0)  # v47: la búsqueda para quien falta no repite
    # Contrato v47: cada combinación lleva la lista de nombres; el término lo elige `siguiente_busqueda`.
    combinaciones = [(f["id"], cobertura.consultas(f), p + sufijo)
                     for f in mapa for p in f.get("paises_busqueda") or f.get("paises_objetivo", paises_activos)
                     if p in PAISES
                     # El filtro remoto de Indeed casi nunca marca avisos de LATAM (11 nov: 0 frente a 4 sin filtro):
                     # también se busca sin él y la ubicación del aviso decide la modalidad.
                     for sufijo in (":REMOTO", "")]
    # Contrato v44: para quien solo habla español, también con un título en español en sus países (remoto y no).
    combinaciones += [(f["id"], f["consultas_es"], p + sufijo)
                      for f in mapa if f.get("consultas_es") for p in f.get("paises_es") or [] if p in PAISES
                      for sufijo in (":ES:REMOTO", ":ES")]
    combinaciones = cobertura.repartir(combinaciones, estado, hoy, prioritarias)
    if repaso:  # primero las combinaciones en español: son las que menos avisos tienen y más se pierden
        combinaciones.sort(key=lambda c: ":ES" not in c[2])  # estable
    crudas, hechas, fallidas, seguidas = [], 0, 0, 0
    por_familia, por_pais = {}, {}
    bloqueada = False

    def agotada():
        return hechas >= presupuesto or seguidas >= 3 or bloqueada or (
            limite_segundos is not None and reloj() - inicio >= limite_segundos)
    for familia, lista, pais in combinaciones:
        if agotada():
            break
        lugar = pais
        pais = lugar.split(":")[0]
        solo_remoto = lugar.endswith(":REMOTO")
        # En el repaso, el filtro remoto no añade avisos (la búsqueda sin filtro ya los trae): un solo nombre.
        cantidad = 1 if not repaso or solo_remoto else NOMBRES_REPASO_ES if ":ES" in lugar else repaso
        b = cobertura.siguiente_busqueda(lista, hoy, cantidad, f"{familia}@{lugar}", estado, desfase=desfase_terminos,
                                         max_dias=max_dias)
        if b is None:  # contrato v47: ya se buscó hoy y no queda nada nuevo ahí
            continue
        dias = max_dias if repaso else b.dias
        pedir = RESULTADOS_REPASO if repaso else por_busqueda
        vistos, hecha = set(), False
        for consulta in b.terminos:
            if agotada():
                break
            hechas += 1
            por_familia[familia] = por_familia.get(familia, 0) + 1
            por_pais[lugar] = por_pais.get(lugar, 0) + 1
            cobertura.anotar_busqueda("indeed", familia, lugar)
            try:
                df = scrape(site_name=["indeed"], search_term=consulta, hours_old=dias * 24, results_wanted=pedir,
                            country_indeed=PAISES[pais], description_format="markdown", verbose=0,
                            **({"is_remote": True} if solo_remoto else {}),
                            **({"offset": b.desde * pedir} if b.desde else {}))
            except Exception as e:  # noqa: BLE001 — un bloqueo no detiene a las demás fuentes
                fallidas += 1
                seguidas += 1
                bloqueada = "429" in str(e) or "block" in str(e).lower()
                continue
            seguidas = 0
            hecha = True
            if not repaso:
                cobertura.anotar_paginas(estado, b, hoy, b.desde + 1, len(df) < pedir)
            for r in df.to_dict("records"):
                fecha = r.get("date_posted")
                enlace = _limpio(r.get("job_url"))
                _anotar_vista(enlace, _limpio(r.get("job_url_direct")))
                if enlace in vistos:  # el mismo aviso con otro nombre de la misma combinación
                    continue
                vistos.add(enlace)
                crudas.append({
                    "titulo": _limpio(r.get("title")), "empresa": _limpio(r.get("company")),
                    "ubicacion": ubicacion(r.get("location"), pais),
                    "descripcion": _limpio(r.get("description"))[:30000],
                    "fecha": fecha.isoformat()[:10] if hasattr(fecha, "isoformat") else _limpio(fecha)[:10],
                    "enlace": enlace, "enlace_directo": _limpio(r.get("job_url_direct")),
                    "remoto": bool(r.get("is_remote")) or None, "fuente": NOMBRE,
                    "_busqueda": b.clave,  # contrato v40: de qué búsqueda salió
                })
        if hecha:
            cobertura.anotar_hecha(estado, b, hoy)
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(crudas), "repaso": bool(repaso),
                    "combinaciones_total": len(combinaciones), "por_familia": por_familia, "por_lugar": por_pais}
