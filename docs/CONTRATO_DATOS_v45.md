# Contrato de datos v45 — «Buscar ahora» que decide solo (18 nov 2026)

> Desde v47 la búsqueda para quien falta es corta y no repite lo ya buscado hoy: ya no duplica los presupuestos ni
> fuerza 30 días (regla 3). Ver `CONTRATO_DATOS_v47.md`.

Decisión de Oscar: un solo botón «Buscar ahora», sin más botones. Al pulsarlo, el servidor revisa qué hace falta y lanza
eso. Sin IA y sin SQL.

## Reglas
1. **El servidor decide** (`panel/servicio.plan_busqueda`, `POST /api/busqueda`), con datos frescos y sin fiarse del
   navegador:
   - **Hoy no hay búsqueda que haya armado su lote**: no hay fila del día, quedó «fallida», o solo corrió la captura
     horaria (la fila no tiene `resumen.revision_del_lote` o su estado no es «parcial»/«completa»). Lanza la
     **búsqueda completa** del día (`bodega.yml`, modo diario; sin la entrada `enfoque`).
   - **La de hoy ya corrió y hay perfiles que no llegan a su meta y pueden recibir más** (`panel/ejecutor.faltan_hoy`,
     una sola regla para el botón y para la búsqueda): lo asignado hoy es menor que `meta_diaria` y además está bajo
     el mínimo de 5 (rescate y reutilización lo completan) o su cargo tiene cupo libre en el lote del día
     (`resumen.faltantes`). Comunidad no cuenta: recibe lo que sobra. Lanza `enfoque=faltantes`.
   - **Si no:** no lanza nada y lo dice (todos llegaron a su meta o ya recibieron todo lo que cabe en el día).
   - Si el servidor no puede leer los datos, hace la completa (el plan nunca falla).
2. **El diálogo muestra el plan antes de lanzar:** qué hará y la lista de quienes no llegan (cliente · cargo · «3 de
   17»).
3. **`enfoque=faltantes`** (`panel/ejecutor.preparar(..., enfocar)` y `--enfoque` en `bodega.yml`):
   - solo esas personas tienen turnos de búsqueda en todas las fuentes, y sus lugares van primero;
   - solo sus lugares (no los «cortos» de la última búsqueda que ya cumplen) piden los 30 días completos (`cobertura.configurar_a_fondo`), aunque se hayan buscado ayer;
   - el presupuesto de LinkedIn, Indeed, Get on Board, Computrabajo, Elempleo, Hireline y Magneto se duplica
     (`FACTOR_A_FONDO`);
   - la medición de rendimiento (`cobertura.medir`) solo cuenta lo buscado en esa pasada, y «Búsquedas hoy» por
     persona suma las pasadas del día;
   - el mapa de cargos y el lote del día no cambian: se clasifica igual, se completa el mismo lote, nada entregado se
     repite y el reparto (`registrar`, rescate, posts) completa a quien falta;
   - si al empezar resulta que ya todos cumplen, se hace la búsqueda normal del día (el flujo necesita su reporte).
4. **Sigue igual:**
   - no lanza si hay una búsqueda u otra tarea larga del grupo en cola o corriendo (v44, «Buscar ahora» del 18 nov);
   - la llave de GitHub vive solo en el servidor;
   - las búsquedas programadas siempre usan `enfoque=completo`.

## Ajustes del cargo (mismo PR)
- Al abrir «Editar cargo» se cargan solos los grupos «En español», «Sugeridos» y «Más amplio» (solo el mapa y el
  glosario, sin ESCO). No cambian los nombres del cargo.
- Las sugerencias ya no incluyen títulos en portugués (`terminos.en_portugues`).
- Lo escrito y las fichas de nombres van en el color más fuerte (`--contenido`: blanco en modo oscuro). Solo el texto de
  ejemplo queda gris.
