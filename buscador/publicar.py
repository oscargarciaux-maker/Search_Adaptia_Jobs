"""Conserva reporte técnico y estado de captura en la rama histórica `publicado`, sin sitio web."""
import csv
import json
from pathlib import Path

# Archivos generados por la interfaz retirada. No eliminar trabajo/, colas ni respaldos.
INTERFAZ_RETIRADA = ("index.html", "estilos.css", "app.js", "motor.js", "config.js", ".nojekyll",
    "datos/vacantes.json.gz", "datos/mapa.json", "datos/paises.json",
    "functions/api/enviadas.js", "functions/api/profunda.js", "functions/api/.gitkeep")
CARPETAS_RETIRADAS = ("functions/api", "functions")  # se quitan solo si quedaron vacías


def publicar(salida, vacantes, reporte, sin_familia):
    salida = Path(salida)
    datos = salida / "datos"
    datos.mkdir(parents=True, exist_ok=True)
    for nombre in INTERFAZ_RETIRADA:
        (salida / nombre).unlink(missing_ok=True)
    for carpeta in CARPETAS_RETIRADAS:
        ruta = salida / carpeta
        if ruta.is_dir() and not any(ruta.iterdir()):
            ruta.rmdir()
    (datos / "salud.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")
    if (reporte or {}).get("modo") != "incremental":
        # 14 nov: la captura de cada hora pisaba el informe de la búsqueda completa (rescate, posts, embudo). Se guarda
        # aparte para poder revisarlo durante el día; solo conteos, como salud.json.
        (datos / "salud_bodega.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(datos / "titulos_sin_familia.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["titulo", "veces"])
        for titulo, veces in sin_familia.most_common(300):
            w.writerow([titulo, veces])
