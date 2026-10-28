"""Indeed por país con JobSpy (su API móvil; la página web responde 403 a los servidores). Sin sesión.

Como LinkedIn, rota las combinaciones (familia, país) y cada corrida toma las que hace más tiempo no se revisan.
"""
import time
from datetime import datetime, timezone

NOMBRE = "Indeed"
# Países de LATAM que Indeed tiene en JobSpy (código ISO → nombre en JobSpy)
PAISES = {"AR": "argentina", "BR": "brazil", "CL": "chile", "CO": "colombia", "CR": "costa rica", "EC": "ecuador",
          "MX": "mexico", "PA": "panama", "PE": "peru", "UY": "uruguay", "VE": "venezuela"}


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
           limite_segundos=None, scrape=None):
    """Vacantes crudas de Indeed y estadísticas. `scrape` permite probar sin red (por defecto jobspy.scrape_jobs)."""
    if scrape is None:
        from jobspy import scrape_jobs as scrape
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    combinaciones = [(f["id"], f["consultas"][0], p) for f in mapa for p in paises_activos if p in PAISES]
    combinaciones.sort(key=lambda c: estado.get(f"{c[0]}@{c[2]}", ""))
    crudas, hechas, fallidas, seguidas = [], 0, 0, 0
    for familia, consulta, pais in combinaciones:
        if hechas >= presupuesto or seguidas >= 3 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        clave = f"{familia}@{pais}"
        ultima = estado.get(clave)
        dias = max_dias if not ultima else min(max_dias, max(1, (datetime.fromisoformat(hoy) - datetime.fromisoformat(ultima)).days + 1))
        hechas += 1
        try:
            df = scrape(site_name=["indeed"], search_term=consulta, hours_old=dias * 24, results_wanted=por_busqueda,
                        country_indeed=PAISES[pais], description_format="markdown", verbose=0)
        except Exception as e:  # noqa: BLE001 — un bloqueo no detiene a las demás fuentes
            fallidas += 1
            seguidas += 1
            if "429" in str(e) or "block" in str(e).lower():
                break
            continue
        seguidas = 0
        estado[clave] = hoy
        for r in df.to_dict("records"):
            fecha = r.get("date_posted")
            crudas.append({
                "titulo": _limpio(r.get("title")), "empresa": _limpio(r.get("company")),
                "ubicacion": _limpio(r.get("location")) or PAISES[pais].title(),
                "descripcion": _limpio(r.get("description"))[:8000],
                "fecha": fecha.isoformat()[:10] if hasattr(fecha, "isoformat") else _limpio(fecha)[:10],
                "enlace": _limpio(r.get("job_url")), "enlace_directo": _limpio(r.get("job_url_direct")),
                "remoto": bool(r.get("is_remote")) or None, "fuente": NOMBRE,
            })
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(crudas),
                    "combinaciones_total": len(combinaciones)}
