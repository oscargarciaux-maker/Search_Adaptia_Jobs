"""Criterios verificables antes de conectar envíos WhatsApp. No envía mensajes."""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from buscador.validacion import errores_catalogo


def evaluar(reporte, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    criterios = {}
    try:
        captura = datetime.fromisoformat(reporte.get("capturada_en", "").replace("Z", "+00:00"))
        criterios["captura_reciente"] = 0 <= (ahora - captura).total_seconds() <= 7200
    except (TypeError, ValueError):
        criterios["captura_reciente"] = False
    criterios["catalogo_sin_pendientes"] = not errores_catalogo(reporte)
    historial = {r["fecha"]: r for r in reporte.get("historico_entregas", [])}
    fechas = sorted(historial)
    continuidad = False
    if fechas:
        try:
            ultima = date.fromisoformat(fechas[-1])
            requeridas = [(ultima - timedelta(days=i)).isoformat() for i in range(7)]
            continuidad = all(d in historial and historial[d].get("meta_cumplida") and
                               not historial[d].get("pendientes_supabase") and
                               historial[d].get("registro_confirmado") and historial[d].get("enlaces_comprobados")
                               for d in requeridas)
            continuidad = continuidad and 0 <= (ahora.date() - ultima).days <= 1
        except ValueError:
            pass
    criterios["siete_dias_con_meta_y_registro"] = bool(continuidad)
    criterios["v2_activo"] = reporte.get("catalogo") is not None
    criterios["ofertas_observadas_recientemente"] = (reporte.get("frescura") or {}).get("observadas_2h", 0) > 0
    seleccion = (reporte.get("verificacion_enlaces") or {}).get("seleccion_del_dia") or {}
    n = (reporte.get("entrega") or {}).get("vacantes", 0)
    criterios["seleccion_con_enlaces_comprobados"] = bool(n and seleccion.get("vacantes") == n and
        seleccion.get("estados", {}).get("verificada") == n)
    return {"apto_para_piloto_whatsapp": all(criterios.values()), "criterios": criterios,
            "nota": "Esto no sustituye revisar enlaces ni definir consentimiento, destinatarios y confirmación de envíos."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", required=True)
    args = parser.parse_args()
    reporte = json.loads((Path(args.salida) / "datos/salud.json").read_text(encoding="utf-8"))
    print(json.dumps(evaluar(reporte), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
