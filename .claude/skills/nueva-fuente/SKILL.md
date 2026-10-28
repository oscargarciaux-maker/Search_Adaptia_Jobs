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
