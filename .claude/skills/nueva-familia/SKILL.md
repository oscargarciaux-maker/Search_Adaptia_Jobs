---
name: nueva-familia
description: Agrega un tipo de cargo (familia) al mapa de cargos o amplía una existente con títulos exactos, similares y cercanos en español, inglés y portugués. Úsala cuando pidan "agrega el cargo …", "que también busque …", "no encuentra vacantes de …" o "suma estos títulos a …".
---

# Nueva familia de cargos

Objetivo: que al escribir ese cargo en la página salgan el exacto, los similares y los cercanos, de todos los niveles.

1. Lee solo `datos/mapa_cargos.yaml` (el encabezado explica cada campo) y busca si ya hay una familia parecida: si existe,
   amplíala en vez de crear otra.
2. Escribe la familia: `id` (minúsculas y guiones), `nombre`, `area` (una de las existentes si encaja), `consultas`
   (4 a 6 términos que más se usan en los avisos de LATAM; se mandan a las fuentes), `exactos`, `similares`, `cercanos`
   (en español, inglés y portugués, sin niveles: el programa quita junior/senior/lead), `herramientas` (palabras del
   oficio en la descripción), `genericos` (palabras sueltas del oficio en el título) y `excluir` (oficios con nombre
   parecido que no son este).
3. Agrega a `pruebas/test_familias.py` al menos 5 títulos reales de la familia (y 2 que NO deben entrar).
4. Corre `python -m pytest -q` y `node --test pruebas/*.test.js`. Si una prueba vieja cambia, revisa que no se haya roto
   otra familia (un título de una palabra en `similares` puede atrapar de más).
5. Rama + PR. La familia empieza a buscarse en la siguiente bodega nocturna (o con *Bodega nocturna → modo inicial*).

No inventes cargos: si no estás seguro de un título, déjalo fuera y dilo.
