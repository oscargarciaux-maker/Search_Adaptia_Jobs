"""Comprobar el resultado real después de conservar el estado y la cola de reintentos."""
import argparse
import json
from pathlib import Path


def errores(reporte):
    e = reporte.get("entrega") or {}
    sb = e.get("supabase") or {}
    fallos = []
    if not e or not e.get("meta_cumplida"):
        fallos.append("La meta de selección diaria está incompleta.")
    if not sb or sb.get("omitida") or sb.get("errores") or sb.get("pendientes") or \
            sb.get("enviadas") is None or sb.get("enviadas") != sb.get("filas"):
        fallos.append("La sincronización con Supabase no está confirmada o tiene filas pendientes.")
    if not reporte.get("vacantes_en_bodega"):
        fallos.append("No hay catálogo válido.")
    return fallos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()
    reporte = json.loads((Path(args.salida) / "datos/salud.json").read_text(encoding="utf-8"))
    fallos = errores(reporte)
    for mensaje in fallos:
        print("::error::" + mensaje)
    if fallos:
        raise SystemExit(1)
    print("Meta de selección y sincronización confirmadas. Esto no certifica autenticidad de cada empresa.")


if __name__ == "__main__":
    main()
