# Contrato de datos v45 — «Buscar ahora» que decide solo (18 nov 2026)

Decisión de Oscar: un solo botón «Buscar ahora», sin más botones. Al pulsarlo, el servidor revisa qué hace falta y lanza
eso. Sin IA y sin SQL.

## Reglas
1. **El servidor decide** (`panel/servicio.plan_busqueda`, `POST /api/busqueda`), con datos frescos y sin fiarse del
   navegador:
   - **Hoy no hay búsqueda terminada** (no existe o la de hoy quedó «fallida»): lanza la **búsqueda completa** del día
     (`bodega.yml`, modo diario, `enfoque=completo`).
   - **La de hoy ya corrió y hay perfiles bajo su meta diaria** (lo asignado hoy frente a `meta_diaria`): lanza
     `enfoque=faltantes`.
   - **Todos llegan a su meta:** no lanza nada y lo dice («Hoy todos llegaron a su meta»).
2. **El diálogo muestra el plan antes de lanzar:** qué hará y la lista de quienes no llegan (cliente · cargo · «3 de
   17»).
3. **`enfoque=faltantes`** (`panel/ejecutor.preparar(..., enfocar)` y `--enfoque` en `bodega.yml`):
   - solo esas personas tienen turnos de búsqueda en todas las fuentes, y sus lugares van primero;
   - sus lugares piden los 30 días completos (`cobertura.configurar_a_fondo`), aunque se hayan buscado ayer;
   - el presupuesto de LinkedIn, Indeed, Get on Board, Computrabajo, Elempleo, Hireline y Magneto se duplica
     (`FACTOR_A_FONDO`);
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
