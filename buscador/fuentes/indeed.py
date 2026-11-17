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


def buscar(mapa, paises_activos, estado, presupuesto, hoy=None, max_dias=30, por_busqueda=30, reloj=time.monotonic,
           limite_segundos=None, scrape=None, prioritarias=(), desfase_terminos=0):
    """Vacantes crudas de Indeed y estadísticas. `scrape` permite probar sin red (por defecto jobspy.scrape_jobs)."""
    if scrape is None:
        from jobspy import scrape_jobs as scrape
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    combinaciones = [(f["id"], cobertura.rotar(cobertura.consultas(f), hoy, 1, desfase=desfase_terminos)[0], p + sufijo)
                     for f in mapa for p in f.get("paises_busqueda") or f.get("paises_objetivo", paises_activos)
                     if p in PAISES
                     # El filtro remoto de Indeed casi nunca marca avisos de LATAM (11 nov: 0 frente a 4 sin filtro):
                     # también se busca sin él y la ubicación del aviso decide la modalidad.
                     for sufijo in (":REMOTO", "")]
    combinaciones = cobertura.repartir(combinaciones, estado, hoy, prioritarias)
    crudas, hechas, fallidas, seguidas = [], 0, 0, 0
    por_familia, por_pais = {}, {}
    for familia, consulta, pais in combinaciones:
        if hechas >= presupuesto or seguidas >= 3 or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        lugar = pais
        pais = lugar.split(":")[0]
        solo_remoto = lugar.endswith(":REMOTO")
        clave = f"{familia}@{lugar}"
        clave_terminos = cobertura.clave_consulta(clave, [consulta])
        ultima = estado.get(clave_terminos)
        dias = cobertura.dias_busqueda(clave, ultima, hoy, max_dias)  # completo si la vez anterior no dejó nada útil
        hechas += 1
        por_familia[familia] = por_familia.get(familia, 0) + 1
        por_pais[lugar] = por_pais.get(lugar, 0) + 1
        cobertura.anotar_busqueda("indeed", familia, lugar)
        try:
            df = scrape(site_name=["indeed"], search_term=consulta, hours_old=dias * 24, results_wanted=por_busqueda,
                        country_indeed=PAISES[pais], description_format="markdown", verbose=0,
                        **({"is_remote": True} if solo_remoto else {}))
        except Exception as e:  # noqa: BLE001 — un bloqueo no detiene a las demás fuentes
            fallidas += 1
            seguidas += 1
            if "429" in str(e) or "block" in str(e).lower():
                break
            continue
        seguidas = 0
        estado[clave] = hoy
        estado[clave_terminos] = hoy
        for r in df.to_dict("records"):
            fecha = r.get("date_posted")
            crudas.append({
                "titulo": _limpio(r.get("title")), "empresa": _limpio(r.get("company")),
                "ubicacion": ubicacion(r.get("location"), pais),
                "descripcion": _limpio(r.get("description"))[:30000],
                "fecha": fecha.isoformat()[:10] if hasattr(fecha, "isoformat") else _limpio(fecha)[:10],
                "enlace": _limpio(r.get("job_url")), "enlace_directo": _limpio(r.get("job_url_direct")),
                "remoto": bool(r.get("is_remote")) or None, "fuente": NOMBRE,
                "_busqueda": clave,  # contrato v40: de qué búsqueda salió
            })
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(crudas),
                    "combinaciones_total": len(combinaciones), "por_familia": por_familia, "por_lugar": por_pais}
