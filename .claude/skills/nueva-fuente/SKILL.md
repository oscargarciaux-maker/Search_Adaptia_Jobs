---
name: nueva-fuente
description: Agrega una fuente de vacantes nueva (un portal como Computrabajo, Bumeran u OCC, o una API pública) al buscador, con sus pruebas. Úsala con "agrega <portal>", "busca también en …".
---

# Nueva fuente

1. Revisa que el portal sirva: que se postule en el mismo sitio o que lleve al aviso original (no un agregador que cobra
   o redirige), y que se pueda leer sin sesión. Nunca con la cuenta ni la cookie de nadie.
2. Crea `buscador/fuentes/<nombre>.py` con `NOMBRE` y `buscar(cliente, …) -> (vacantes_crudas, estadisticas)`. Cada
   vacante cruda: `titulo, empresa, ubicacion, descripcion, fecha (AAAA-MM-DD), enlace, enlace_directo, remoto, fuente`.
   Usa `buscador.http.Cliente` (pausas y espera ante 429) y respeta un presupuesto de peticiones y de minutos.
3. Si el portal es un sitio donde se postula, agrégalo a `portales` en `datos/dominios.yaml`; si es una copia, a
   `agregadores` y resuelve el original como en `fuentes/remotos.py`.
4. Conéctala en `buscador/bodega.py` (función `recoger`), con su presupuesto en `datos/config.yaml`.
5. Pruebas sin red en `pruebas/test_fuentes.py` con una respuesta guardada. `python -m pytest -q`.
6. Prueba en vivo: `python -m buscador.bodega --salida /tmp/prueba --prueba`. Rama + PR.
7. Si viene de un pedido de «Huecos por país» (sección 8.1, es para el mismo día): en la prueba en vivo cuenta cuántos
   avisos de la fuente nueva son **de ese país** y de las familias pedidas (solo conteos, sin datos de nadie) y ponlo en
   el PR; si son 0, la fuente no resuelve el hueco. Para que `panel/ejecutor.py` `fuentes_en` la muestre en la tabla,
   declara sus países (como `PAISES` o `SITIOS` en las demás) y añádela allí. Si ningún portal pasa la prueba en vivo
   (§9 del contrato), no la fuerces: dilo en el informe; el perfil sigue con las genéricas y Apify (8.2).
