# Contrato de datos v41: Indeed comprobado por su búsqueda y comprobación repartida entre fuentes

**Fecha:** 17 de noviembre de 2026. **Sin SQL ni IA.** Aprobado por Oscar tras la auditoría de los 21 perfiles.

## Por qué
- **Indeed:** la bodega tenía 487 vacantes de Indeed de los cargos del panel y solo 17 comprobadas. Indeed responde 401
  a cualquier comprobación de su página. Su «enlace directo» casi siempre es otra página de Indeed (co.indeed.com,
  mx.indeed.com…), así que tampoco se podía comprobar.
- **Computrabajo y Get on Board:** se dejan comprobar, pero casi no tenían turno. Las comprobaciones salían en el orden
  de la lista, casi toda de LinkedIn, que va de una en una con pausa. Mientras esperaban su turno, ocupaban 5 de los
  6 hilos de trabajo. Computrabajo tenía 6 comprobadas de 280 y Get on Board 1 de 74.

## Reglas
1. **Indeed visto hoy = abierto 24 h.** Un aviso que la búsqueda de Indeed (JobSpy) mostró en esta corrida cuenta como
   comprobado, con el motivo «vista hoy en la búsqueda de Indeed» (`indeed.VISTAS` → `verificar_enlaces.incorporar`).
   - Indeed solo lista avisos activos.
   - Vale las mismas 24 h de siempre (v9, v31); si al día siguiente no aparece, vuelve a quedar sin comprobar.
   - No se consulta Indeed de otra forma ni se usa la clave de su app fuera de JobSpy.
2. **LinkedIn en su propia fila** (un hilo, 1,5 s de pausa) y los demás sitios en otra fila, con todos los hilos.
   - A LinkedIn no se le asignan más enlaces de los que alcanza en el tiempo (segundos ÷ pausa); el resto del cupo
     queda para los demás.
3. **Primero lo de quien va corto:** dentro de cada ronda, la comprobación empieza por las vacantes de un cargo y un
   país de alguien que va corto o es nuevo (`cobertura.sirve_a_corta`).
4. Se informa cuántas se incorporaron en `verificacion_enlaces.vistas_indeed_incorporadas`.

## Lo que no cambia
- Sin comprobación vigente no se entrega ni se comparte.
- Un bloqueo nunca cuenta como cierre.
- La comprobación no inicia sesión ni envía formularios.
