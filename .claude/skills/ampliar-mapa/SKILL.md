---
name: ampliar-mapa
description: Revisa los títulos de vacantes que llegaron y no encajaron en ningún cargo del mapa, propone dónde va cada uno y aplica lo que se apruebe. Úsala con "revisa los títulos sin familia", "amplía el mapa" o cuando una búsqueda trae pocas vacantes.
---

# Ampliar el mapa con los títulos sin familia

Para gastar pocos tokens se lee **solo** el reporte corto, nunca la bodega completa.

1. Descarga el reporte de la última bodega: `https://raw.githubusercontent.com/<repo>/publicado/datos/titulos_sin_familia.csv`
   (o `datos/titulos_sin_familia.csv` de la rama `publicado`). Toma los 100 más frecuentes.
2. Clasifícalos en una tabla corta: título · veces · familia propuesta y grado (exacto/similar/cercano) · o "no es de
   tecnología ni áreas creativas" (se ignora). No propongas títulos de oficios fuera del alcance (cajero, conductor…).
3. Muéstrale la tabla a quien lo pidió y espera su aprobación.
4. Aplica lo aprobado en `datos/mapa_cargos.yaml` siguiendo la skill `nueva-familia` (pruebas incluidas) y abre un PR.
