"""Conserva reporte técnico y estado de captura en la rama histórica `publicado`, sin sitio web."""
import csv
import json
from pathlib import Path

# Archivos generados por la interfaz retirada. No eliminar trabajo/, colas ni respaldos.
INTERFAZ_RETIRADA = ("index.html", "estilos.css", "app.js", "motor.js", "config.js", ".nojekyll",
    "datos/vacantes.json.gz", "datos/mapa.json", "datos/paises.json",
    "functions/api/enviadas.js", "functions/api/profunda.js")


def publicar(salida, vacantes, reporte, sin_familia):
    salida = Path(salida)
    datos = salida / "datos"
    datos.mkdir(parents=True, exist_ok=True)
    for nombre in INTERFAZ_RETIRADA:
        (salida / nombre).unlink(missing_ok=True)
    (datos / "salud.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(datos / "titulos_sin_familia.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["titulo", "veces"])
        for titulo, veces in sin_familia.most_common(300):
            w.writerow([titulo, veces])
