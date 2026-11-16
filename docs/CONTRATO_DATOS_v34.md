# Contrato de datos v34: «Por confirmar» rápido y con los datos del aviso

**Fecha:** 16 de noviembre de 2026. **SQL:** 018, aditiva (una columna). **Sin IA.**

Pedido de Oscar: «Por confirmar» tarda en cambiar de página, no muestra lo que ya dice el aviso, el filtro «Para» se
mueve, los avisos pierden sus saltos de línea y negritas, y «Cargar todas las dudosas de la base» no funciona.

## 1. Resumen guardado de noche (SQL 018)
- `panel_revisiones.resumen jsonb not null default '{}'` (objeto). No cambia filas, permisos ni funciones existentes.
- Al armar la cola (`panel/revision.preparar_cola`) cada fila nueva guarda: `titulo`, `empresa`, `ubicacion`,
  `modalidad`, `salario` (texto del aviso), `idioma`, `publicada`, `enlace`, `paises` (los que leyó el sistema, sin
  confirmar; hasta 8), `sugerida`, `paises_sugeridos`, `por_que` y `frase` (la sugerencia por código de v17).
- Las pendientes de noches anteriores sin resumen lo reciben una vez (como mucho 300 por noche).
- El panel lista las pendientes leyendo solo la bandeja (sin el catálogo ni descripciones). Una fila sin resumen se
  calcula al mostrarla, como antes. Sin SQL 018 (antes de «Preparar Supabase») todo funciona como en v29.

## 2. Carga completa sin agotar la memoria
- «Cargar todas las dudosas de la base» recorre el catálogo por páginas de 100 sin guardarlas todas; la bandeja se
  lee sin descripciones y solo pide las que necesita, de 100 en 100; se guarda en grupos de 200. Antes traía miles de
  descripciones a la vez y el alojamiento gratuito (512 MB) se quedaba sin memoria. El avance muestra «N de total».

## 3. Formato del aviso
- LinkedIn conserva saltos de línea, viñetas y negritas (`**texto**`), igual que el `JobPosting` de las fichas. Una
  línea toda en negrita es un subtítulo. La búsqueda ignora los `**` al normalizar. El panel los pinta en negrita como
  texto, nunca como HTML. Los avisos ya guardados mantienen su texto hasta que se vuelvan a leer.

## 4. Pantalla
- Los mismos datos que en «Vacantes» (ubicación, modalidad, salario, publicación, idioma) en la lista y en el detalle.
- Los países que leyó el sistema van como etiquetas («Países que leyó el sistema: Italia»).
- «Para» va primero, con cuántas tiene cada cliente; las páginas siempre ocupan su lugar.
- El selector de país tiene el estilo de los demás campos.

Pruebas: `pruebas/panel/test_resumen_v34.py` y el recorrido «bandeja Por confirmar» en `web/tests/control.spec.ts`.
