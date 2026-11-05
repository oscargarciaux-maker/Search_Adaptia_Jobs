"""Fechas con precisión explícita: una fecha no se convierte en una hora inventada."""
from datetime import datetime, timezone
from math import ceil


def instante(valor):
    if not valor:
        return ""
    try:
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            dt = datetime.fromtimestamp(valor / 1000 if valor > 1e11 else valor, timezone.utc)
        else:
            texto = str(valor).strip()
            if "T" not in texto:
                return ""
            dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return ""
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError, OSError):
        return ""


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def medir(vacantes, momento=None):
    momento = momento or ahora()
    fin = datetime.fromisoformat(momento.replace("Z", "+00:00"))
    precisas = observadas = recientes = 0
    retardos = []
    for v in vacantes:
        pub, vista, detectada = (instante(v.get(k)) for k in ("publicada_en", "vista_en", "detectada_en"))
        if vista:
            edad = (fin - datetime.fromisoformat(vista.replace("Z", "+00:00"))).total_seconds()
            observadas += 0 <= edad <= 7200
        if pub:
            precisas += 1
            publicacion = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            recientes += 0 <= (fin - publicacion).total_seconds() <= 86400
            if detectada:
                minutos = (datetime.fromisoformat(detectada.replace("Z", "+00:00")) - publicacion).total_seconds() / 60
                if minutos >= 0:
                    retardos.append(minutos)
    retardos.sort()
    return {"con_hora_publicacion": precisas, "sin_hora_publicacion": len(vacantes) - precisas,
            "publicadas_24h_confirmadas": recientes, "observadas_2h": observadas,
            "muestras_retardo": len(retardos),
            "retardo_publicacion_deteccion_p90_min": round(retardos[ceil(len(retardos) * 0.9) - 1], 1) if retardos else None}
