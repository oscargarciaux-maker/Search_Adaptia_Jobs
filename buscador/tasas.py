"""Contrato v26: tasas de cambio para comparar salarios en otra moneda. Tabla editable `datos/tasas_cambio.yaml`
(unidades de cada moneda por 1 USD). Se actualiza con `python -m buscador.tasas --actualizar` desde una fuente
pública sin clave; si la fuente no responde, la tabla anterior se conserva. Con tasas viejas no se convierte."""
from datetime import date
from functools import lru_cache
from pathlib import Path
import sys

import yaml

RUTA = Path(__file__).resolve().parent.parent / "datos" / "tasas_cambio.yaml"
FUENTE = "https://open.er-api.com/v6/latest/USD"
DIAS_VIGENCIA = 120
MONEDAS = ("USD", "EUR", "COP", "MXN", "ARS", "CLP", "PEN", "BRL", "UYU", "DOP", "GTQ", "CRC", "VES",
           "GBP", "CAD", "AED", "CHF", "BOB", "PYG", "HNL", "NIO")
INESTABLES = ["ARS", "VES"]


@lru_cache(maxsize=1)
def tabla():
    if not RUTA.exists():
        return {"fecha": "", "tasas": {}, "inestables": INESTABLES}
    datos = yaml.safe_load(RUTA.read_text(encoding="utf-8")) or {}
    tasas = {str(k).upper(): float(v) for k, v in (datos.get("tasas") or {}).items() if v}
    tasas["USD"] = 1.0
    return {"fecha": str(datos.get("fecha") or ""), "tasas": tasas,
            "inestables": [str(m).upper() for m in datos.get("inestables", INESTABLES)]}


def vigente(hoy=None):
    """La tabla sirve si tiene menos de 120 días."""
    fecha = tabla()["fecha"]
    try:
        return ((hoy or date.today()) - date.fromisoformat(fecha)).days <= DIAS_VIGENCIA
    except ValueError:
        return False


def convertir(monto, de, a, hoy=None):
    """`monto` en la moneda `de`, expresado en `a`; None si no se puede convertir con seguridad."""
    de, a = str(de or "").upper(), str(a or "").upper()
    if de == a:
        return float(monto)
    t = tabla()
    if not vigente(hoy) or de in t["inestables"] or a in t["inestables"] or de not in t["tasas"] or a not in t["tasas"]:
        return None
    return float(monto) / t["tasas"][de] * t["tasas"][a]


def actualizar(pedir=None):
    """Reescribe la tabla desde la fuente pública. Devuelve la fecha nueva o lanza si la fuente no responde bien."""
    if pedir is None:
        import requests
        pedir = lambda: requests.get(FUENTE, timeout=20).json()  # noqa: E731
    datos = pedir()
    if datos.get("result") != "success" or not isinstance(datos.get("rates"), dict):
        raise RuntimeError("La fuente de tasas no respondió bien; se conserva la tabla anterior.")
    tasas = {m: round(float(datos["rates"][m]), 6) for m in MONEDAS if m in datos["rates"] and m != "USD"}
    fecha = date.today().isoformat()
    texto = ("# Contrato v26: unidades de cada moneda por 1 USD. Se actualiza con `python -m buscador.tasas "
             "--actualizar`.\n# Con más de 120 días no se convierte (nunca se descarta con tasas viejas).\n" +
             yaml.safe_dump({"fecha": fecha, "fuente": "open.er-api.com", "base": "USD", "tasas": tasas,
                             "inestables": INESTABLES}, allow_unicode=True, sort_keys=False))
    RUTA.write_text(texto, encoding="utf-8")
    tabla.cache_clear()
    return fecha


if __name__ == "__main__":
    if "--actualizar" in sys.argv:
        print("Tasas actualizadas:", actualizar())
    else:
        t = tabla()
        print(f"Tabla del {t['fecha'] or '—'} ({'vigente' if vigente() else 'vencida'}): {len(t['tasas'])} monedas.")
