# Contrato de datos v43: «Confirmar y aplicar», búsquedas que no se caen, Comunidad hasta su meta y vacantes compartidas

**Fecha:** 18 de noviembre de 2026. **SQL 019.** Sin IA. Decisiones de Oscar del 18 nov.

## Por qué
- **«Aplicar hoy» y «Programar para mañana» confundían.** Oscar pidió que confirmar la configuración sirva desde la
  próxima búsqueda, aunque sea minutos después.
- **La búsqueda #33 (17 nov) se cayó en el último paso.** Tardó 88 minutos, alguien aplicó una configuración para
  hoy mientras corría, y al terminar se detuvo con «La captura de hoy conserva otra versión». No se publicó nada y se
  perdió lo encontrado.
- **«196 de 20» en Comunidad.** Comunidad recibía todas las vacantes que le servían, sin tope, aunque el cupo diario
  le dejaba 0.
- **Una vacante que sirve a dos cargos** solo llegaba a los perfiles del cargo al que entró en el lote.

## Reglas
1. **Confirmar y aplicar** (`panel_publicar`, SQL 019): la versión confirmada rige desde **hoy** en Bogotá.
   - Si la búsqueda de hoy ya existe, pasa a la versión nueva y anota la anterior en
     `panel_ejecuciones.resumen.revisiones_anteriores`.
   - Lo ya entregado hoy no cambia: `entregas_diarias` y SQL 017 no se tocan.
   - `panel_publicar_hoy` queda como el mismo botón.
   - Ya no se rechaza con una búsqueda en curso (regla 2).
2. **Una búsqueda no se cae por un cambio de configuración** (`panel/ejecutor.py`):
   - antes de asignar, vuelve a leer la versión confirmada más nueva (`vigente`) y asigna con ella;
   - `iniciar` lleva la fila del día a la versión más nueva y nunca la regresa a una más vieja.
3. **La próxima búsqueda completa lo que falta** (sin botón «buscar ahora», decisión de Oscar; el mismo 18 nov, tras un día sin horarios de GitHub, pidió «Buscar ahora» en el Resumen: lanza esta misma búsqueda diaria y no cambia ninguna regla de este contrato, ver `docs/GUIA_CLIENTE.md`):
   - la búsqueda que arma el lote guarda `resumen.revision_del_lote`;
   - si una captura horaria encuentra una versión más nueva que la del lote, arma lote solo para lo que falta, con el
     lote del día como punto de partida. Antes lee lo ya entregado en Supabase y no repite nada;
   - es la **única excepción** a «la captura horaria no crea entregas»: solo cuando la configuración cambió después
     del lote del día. No usa Apify.
4. **Comunidad hasta su meta:**
   - recibe después de los clientes reales;
   - primero recibe las vacantes que no le llegaron a ningún cliente real;
   - se corta en la `meta_diaria` de su perfil;
   - puede recibir vacantes que también le llegaron a clientes.
5. **Vacantes compartidas entre cargos:** una vacante del lote llega también a los perfiles de otro cargo activo
   cuando ese cargo la reconoce como exacta o similar (`terminos.grado`, nunca solo «cercano») y cumple sus filtros
   (`afinidad.evaluar`).
   - La asignación lleva el cargo de ese perfil y cuenta para su meta.
   - No ocupa cupo del lote.
   - Nunca llega dos veces a la misma persona.
6. **Cifras del día** (`panel_ejecuciones.resumen`):
   - `vacantes_vigentes`: del lote, de cargos activos en la versión vigente;
   - `vacantes_anteriores`: de cargos que ya no están;
   - `asignaciones_comunidad`;
   - `revision_del_lote` y `revisiones_anteriores`.
7. **WhatsApp manual desde «Vacantes»** (PR 4): el operador elige cuántas copiar, de 1 a todas las listas (10 por
   defecto). Se mantienen 2 por empresa y se copia en partes si hace falta. Amplía el tope de 10 de v31 solo para
   esta acción manual; los borradores diarios siguen en 10.

## Lo que no cambia
- Lo ya entregado no se mueve ni se borra.
- Nada se envía solo.
- Sin comprobación vigente no se entrega ni se comparte.
- Sin IA.
