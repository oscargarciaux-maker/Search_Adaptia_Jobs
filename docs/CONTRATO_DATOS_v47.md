# Contrato de datos v47 — «Buscar ahora» para quien falta: corta y sin repetir (18 nov 2026)

Decisión de Oscar: «Me gustaría que sea corta. Sin embargo, lo más prioritario es que lleguen las vacantes necesarias
para el perfil. Pero que no haga reprocesos si las condiciones del perfil no han cambiado.» Corrige partes de v45.
Sin IA y sin SQL. La búsqueda completa del día no cambia.

## Por qué tardaba lo mismo (búsqueda #34, 81 min)
- LinkedIn tardó 50 min y los portales de empresas otros 50, en paralelo. Los portales leyeron 33.941 avisos.
- Comprobar enlaces tardó 11 min y el refuerzo 14.
- La de faltantes (v45) no bajaba el tope de 50 min, duplicaba los presupuestos y, al terminar con quien faltaba,
  seguía con los demás.
- Nada evitaba repetir una búsqueda hecha hoy, y v45 forzaba 30 días en sus lugares.

## Reglas (`enfoque=faltantes`)
1. **Solo quienes faltan.**
   - Las personas de búsqueda son solo ellas (como en v45).
   - `cobertura.repartir` ya no añade el «resto» de combinaciones de otros perfiles
     (`cobertura.configurar_faltantes`).
   - El mapa de cargos no cambia: la limpieza y la clasificación siguen viendo todos los cargos, así que el lote del
     día no se toca.
2. **Sin repetir lo ya buscado hoy** (`cobertura.siguiente_busqueda`):
   - Cada búsqueda queda anotada por fuente + cargo + lugar + nombres (`clave_consulta`). Ahora también lo hacen
     Computrabajo, Elempleo y Get on Board.
   - Si esa clave ya se buscó hoy, se usan los nombres siguientes del cargo.
   - Si ya se usaron todos, se sigue en la página donde quedó, con los mismos días (`~paginas` en el estado de la
     fuente; LinkedIn con `start`, Indeed con `offset`, Computrabajo con `?p=`), hasta 10 páginas al día.
   - Si no se sabe dónde quedó, o ya no hay más páginas, no se repite.
   - Si cambian las condiciones del perfil (nombres del cargo, países o ciudades, modalidad, idioma), cambian las
     claves y esas búsquedas sí corren.
   - Se quita la regla de v45 de pedir siempre 30 días. Se piden 30 días solo si la combinación nunca se buscó o la
     última vez no trajo nada.
3. **Pasos que no corren:**
   - los portales de empresas (ya se leyeron hoy y cuentan como comprobados 24 h, v42);
   - Open Seat y los tableros LATAM, los tableros remotos, los sitemaps de Hireline y Magneto, y el descubrimiento de
     portales. Todos recorren todos los cargos.
4. **Tiempos:**
   - 12 min por fuente, con los presupuestos de siempre (no el doble);
   - comprobar enlaces 240 s y confirmar ubicaciones 150 s, primero lo de quien va corto (como siempre);
   - una sola ronda de refuerzo.
   - Objetivo: unos 30 min.
5. **Prioridad, que lleguen las vacantes.** El reparto (`registrar`: lote, reutilización, rescate sobre toda la
   bodega y posts) no cambia: primero lo que ya hay guardado, luego lo nuevo, y nunca dos veces a la misma persona.
6. **El panel** dice «Tarda unos 30 minutos».
