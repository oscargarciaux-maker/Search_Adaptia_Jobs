"""Arma la carpeta que se publica en la rama `publicado`: la página (web/) y sus datos (datos/), más el trabajo de la
bodega (trabajo/) para la noche siguiente."""
import csv
import gzip
import json
import shutil
from pathlib import Path

from buscador import familias, paises, vacante

RAIZ = Path(__file__).resolve().parent.parent


def publicar(salida, vacantes, reporte, sin_familia):
    salida = Path(salida)
    datos = salida / "datos"
    datos.mkdir(parents=True, exist_ok=True)
    # La página: se copia web/ completa a la raíz de la rama publicada
    web = RAIZ / "web"
    for archivo in web.rglob("*"):
        if archivo.is_file() and archivo.name != ".gitkeep":
            destino = salida / archivo.relative_to(web)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archivo, destino)
    funciones = RAIZ / "functions"
    if funciones.exists():
        shutil.copytree(funciones, salida / "functions", dirs_exist_ok=True)
    # Vacantes ordenadas de la más nueva a la más vieja, sin la descripción completa
    publicas = [vacante.publica(v) for v in sorted(vacantes, key=lambda v: v.get("fecha_publicacion") or v.get("visto_primera_vez") or "",
                                                     reverse=True)]
    with gzip.open(datos / "vacantes.json.gz", "wt", encoding="utf-8") as f:
        json.dump(publicas, f, ensure_ascii=False, separators=(",", ":"))
    (datos / "mapa.json").write_text(json.dumps(familias.para_la_pagina(), ensure_ascii=False), encoding="utf-8")
    (datos / "paises.json").write_text(json.dumps([{"codigo": p["codigo"], "nombre": p["nombre"]} for p in paises.datos()["paises"]],
                                                  ensure_ascii=False), encoding="utf-8")
    (datos / "salud.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(datos / "titulos_sin_familia.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["titulo", "veces"])
        for titulo, veces in sin_familia.most_common(300):
            w.writerow([titulo, veces])
    # Configuración de la página: el repositorio (para el enlace a la búsqueda profunda en GitHub Actions)
    import os
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    (salida / "config.js").write_text("window.BUSCADOR_CONFIG = " + json.dumps({"repo": repo}) + ";\n", encoding="utf-8")
    # GitHub Pages: sin Jekyll, para que sirva los archivos tal cual
    (salida / ".nojekyll").write_text("", encoding="utf-8")
