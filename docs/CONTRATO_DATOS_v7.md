# Inglés exigido precalculado en el catálogo — v7

Revisión del 11 de noviembre de 2026. Amplía el catálogo v2 (`catalogo_vacantes.datos`) sin cambiar columnas ni SQL.

`datos.requisito_ingles` (texto): resultado de `contrato.requisitos_idioma(descripción, ingles)` con la misma
descripción que la bodega usa para etiquetar. Formato `en:<nivel>:<obligatorio>` (por ejemplo `en:B2:1`; `0` cuando el
aviso lo presenta como deseable) o vacío si el aviso no pide inglés. No inventa un nivel: si el aviso no lo dice, queda
vacío o con el nivel interpretado de `ingles`.

Uso: la estimación del panel lee solo los campos de filtro de `datos` (unos 2,5 MB para ~6.000 vacantes, frente a ~40 MB
con descripciones) y obtiene el mismo veredicto que la evaluación con descripción completa. Los años mínimos ya estaban
en `anos_min` y no dependen del texto. Mientras una fila antigua no tenga el campo, la estimación usa el nivel guardado
como obligatorio: puede quedar corta, nunca inflada. Al desplegarse, la primera captura reenvía una vez las filas cuyo
`datos` cambió por el campo nuevo; después vuelve el envío por cambios del contrato v2.
