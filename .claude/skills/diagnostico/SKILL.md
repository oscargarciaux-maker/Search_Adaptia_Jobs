---
name: diagnostico
description: Explica en lenguaje sencillo qué pasó en la última búsqueda nocturna (cuántas vacantes, qué fuente falló, por qué salieron pocas de un cargo o un país) y qué hacer. Úsala con "qué pasó anoche", "por qué salieron pocas", "no funciona la página" o "revisa el buscador".
---

# Diagnóstico

1. Lee solo `datos/salud.json` de la rama `publicado`
   (`https://raw.githubusercontent.com/<repo>/publicado/datos/salud.json`). Trae: fecha, minutos, vacantes en la bodega,
   nuevas, cada fuente (avisos, errores, tiempo), descartes y conteos por cargo, país y fuente.
2. Si la fecha no es de anoche: la bodega no corrió o falló. Revisa *Actions → Bodega nocturna* (el último registro) y di
   el error exacto.
3. Si una fuente dice `error`, explica cuál y si las demás compensan. Bloqueos de LinkedIn (429) son normales a ratos:
   la rotación retoma al día siguiente. Si es seguido, sugiere bajar `presupuestos.linkedin_busquedas` o usar Apify.
4. Si preguntan por un cargo o país con pocas vacantes: mira `por_familia` y `por_pais`, y los `descartes`; sugiere
   ampliar el mapa (skill `ampliar-mapa`) o una búsqueda en vivo.
5. Para revisar claves y fuentes desde cero: *Actions → Diagnóstico → Run workflow*.

Responde corto: qué pasó, por qué y qué hacer. Sin leer la bodega completa.
