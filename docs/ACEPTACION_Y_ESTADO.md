# Aceptación del proyecto y estado comprobado

Este documento distingue código probado, operación observada y aceptación en las cuentas del cliente. No certifica
ausencia total de fallos. Actualizar el corte y adjuntar evidencia después de una prueba real; no cambiar pendientes a
aprobados por haber fusionado otro PR. Instrucciones de uso: [GUIA_CLIENTE.md](GUIA_CLIENTE.md).

## 1. Corte de evidencia

**Extensión preparada después de ese corte:** SQL 003 y `ESTADO_SUPABASE_ACTIVO` permiten reservas/pendientes duraderos.
Se ensayaron concurrencia y restauración de cinco tablas/dos secuencias en PostgreSQL 17 ficticio, además de pruebas
Python de cortes/recuperación. No se migró ni activó la base real durante el desarrollo. Para aceptarla falta seguir
[la guía](ACTIVAR_ESTADO_OPERATIVO.md) y registrar importación real, siguiente reserva, entrega y página con su SHA.
La rama del [PR #14](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/pull/14) pasó 479 pruebas Python y la
suite JavaScript. Una captura pública `--prueba` terminó en 6,5 minutos: 1.594 vacantes en temporal y 11 enlaces
comprobados de 12 programados; el resto siguió pendiente. No creó entrega productiva, escribió en Supabase ni usó
Apify pagado. Es evidencia acotada de fuentes/integración, no de activación central ni calidad de todo el catálogo.

Consulta del **5 de noviembre de 2026, 12:32 p. m. de Colombia**:

| Comprobación | Resultado observado | Límite de la evidencia |
|---|---|---|
| PR #11 | Fusionado en `main`, commit `6767075bc693dc9785e93e4da396351f7a02e057` | Fusionar no ejecuta ni despliega una captura |
| Pruebas de `main` | Aprobadas: [ejecución 42072570083](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42072570083); referencia del cambio: 456 Python, Node y SQL | No demuestra siete días reales ni una cuenta nueva del cliente |
| Nocturna del 5 de noviembre | [Ejecución 41987125129](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/41987125129), éxito; 120 ofertas, 162 filas, sin pendientes, 120 registros de selección | Anterior al control v3; la cantidad no acredita vigencia de todos los enlaces |
| Captura y web al consultar | Datos de 11:35:21 a. m. Colombia; catálogo 15.061 filas aceptadas, cero pendientes; página y rama coincidían | El número incluye actualizaciones/archivos, no 15.061 ofertas nuevas |
| Pages | `build_type=workflow`, sitio construido; [despliegue 42066022677](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42066022677) | Ese despliegue todavía correspondía al código previo al PR #11 |
| Auditoría de enlaces | 120 ofertas revisadas: 108 con al menos un enlace comprobable, 5 pendientes y 7 apartadas | Foto de 11:25–11:32; no cambia retroactivamente snapshots ni acredita cobros ocultos |
| Primera captura productiva con v3 | Todavía no figuraba una ejecución con el commit nuevo; `verificacion_enlaces` no aparecía en el reporte público | Pendiente, no asumir activa por estar fusionada |
| Continuidad diaria | Solo una fecha en `historico_entregas`; sin evidencia histórica de enlaces comprobados | No cumple siete días del criterio de preparación |
| Restauración del manual | Ensayo con datos ficticios en PostgreSQL 17: tres tablas, FK, cierre, permisos y secuencia conservados | No es una recuperación de la cuenta real del cliente |
| Capacidad/costos/respaldos reales del cliente | No comprobados administrativamente en este corte | Requieren revisión del propietario en sus servicios |

La herramienta de preparación devolvía **`apto_para_piloto_whatsapp=false`**: faltaba continuidad de siete días y
comprobación vigente de toda la selección. Captura reciente, observación reciente, catálogo y v2 sí cumplían en ese corte.
El [informe de los doce casos](../reportes/auditoria_enlaces_2026-11-05.md) y el
[control de enlaces](CONTROL_CALIDAD_ENLACES.md) detallan los hallazgos. Un enlace fallido no prueba fraude de la empresa.

Este estado fechado es histórico; utilizar los pasos siguientes para evaluar la situación actual.

### Actualización observada el 5 de noviembre, 1:10 p. m. Colombia

La [captura 42080482444](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42080482444) terminó
correctamente con `7a131022e02410639f6896e4e0ca81cd73e01482`: ya se acreditó la primera captura productiva con v3.
Su catálogo confirmó 13.959 filas, sin errores ni pendientes; la página coincidía con el dato de **1:09:43 p. m.** después
del [despliegue 42081595465](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42081595465).

La comprobación programó 40 ofertas. Del lote histórico de 120: **32 comprobadas, 86 pendientes y 2 rechazadas por cierre**.
De las 86 pendientes, 80 no habían sido revisadas por el límite del ciclo y seis quedaron sin confirmar. Es la revisión
gradual prevista, no una prueba de que las 120 estén listas para compartir ni de siete días de continuidad. Las dos
cerradas se retiraron del catálogo activo sin reescribir la selección histórica.

Esta actualización resuelve el pendiente del primer ciclo v3 del corte anterior; permanecen las pruebas de continuidad,
respaldo real/capacidad de las cuentas del cliente, alertas y aceptación con sus propios accesos.

## 2. Condiciones para una entrega operativa

Registrar resultado, fecha, responsable y enlace de evidencia para cada fila. «No probado» no equivale a «aprobado».

| Prueba | Criterio observable | Evidencia que se conserva |
|---|---|---|
| Propiedad y acceso | Cliente administra repo, base, Apify y alojamiento con sus cuentas | Inventario privado de cuentas/permisos, sin secretos en acta pública |
| Código aprobado | Pruebas del commit utilizado pasan Python/Node/SQL | Commit y ejecución de Pruebas |
| Captura con el código nuevo | Trabajo real usa commit con v3 y no omite captura/sincronización | Ejecución, SHA y reporte de salud |
| Persistencia v2 | Catálogo, ofertas y registro sin errores/colas pendientes | Reporte y conteos por rol/fecha en Supabase |
| Web actualizada | Hora del dato en web coincide con rama y despliegue esperado | URL, horas y ejecución; captura de pantalla sin claves si hace falta |
| Calidad por caso | Una URL 200 genérica no se aprueba; cierres/404/ciclos/pagos se apartan; 403 queda pendiente | Tests + revisión por muestra en la instalación |
| Enlace alternativo | Si falla el principal y hay uno bueno, se comparte el comprobado | Caso revisado y texto resultante |
| País y afinidad | UX/UI incluye afines pertinentes; remoto restringido no se anuncia mundial | Muestra LATAM/España/mundial y casos restringidos |
| Frescura | 2/6/24 horas solo incluyen publicación con hora confirmada | Ejemplos con hora, solo fecha y primera detección |
| Selección y repetición | Máximo configurado por rol; completar/reintentar el mismo lote no escoge otro completo | IDs/fechas antes y después de repetición controlada |
| Reintento | Fallo no pierde colas y reintento no duplica registros ni cambia fecha | Tests de regresión + ensayo aislado si se cambia infraestructura |
| Conservación | Oferta retirada permanece cerrada/archivada en catálogo y referenciada en selección | Consulta por ID y snapshot |
| Presupuesto | Cuenta/ciclo/límite confirmados y reservas conservadas | Uso real Apify y archivo del corte, sin tokens |
| Capacidad | Tamaño/uso de base y minutos/plan soportan la frecuencia prevista | Paneles del proveedor revisados por propietario |
| Respaldo y recuperación | Cliente puede restaurar un corte aislado conservando tipos, IDs, FK, secuencia y memoria | Acta del ensayo en cuentas/entorno acordado |
| Acceso de página | Se cumple la decisión pública/privada y, si corresponde, APIs/dominios Access | Prueba autorizada e incógnita; configuración revisada |
| Alertas y soporte | Responsable recibe avisos y sabe leer/atender un fallo | Incidencia de prueba y procedimiento acordado |
| Uso sin asistencia | Cliente busca, interpreta estados, copia y marca sin ayuda del desarrollador | Recorrido de aceptación |

No provocar pagos, cierres ni fallos de la base productiva para ensayar. Los casos artificiales se prueban en fixtures
y destinos aislados. Las escrituras reales de aceptación se coordinan para no repetir selección ni consumir crédito extra
innecesariamente. Los comandos y recuperación están en [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md).

## 3. Siete días para evaluar continuidad

Durante **siete fechas distintas**, con memoria y cuentas conservadas:

1. Registrar cantidades nuevas por cada rol y faltantes. La meta es veinte por rol, no un total compensado entre cargos.
2. Confirmar cero pendientes en selección/catálogo/registro. No considerar prueba de escritura una corrida `prueba=true`.
3. Registrar evidencia de enlaces comprobados al seleccionar y revisar una muestra de los seis roles.
4. Medir fechas reales y desconocidas, primera detección y retrasos de ejecución/despliegue. No llamar «nuevas de hoy»
   a ofertas publicadas hoy sin el dato que lo respalde.
5. Contrastar costos reservados con el consumo global y capacidad. No hacer varias cargas vacías para simular días.
6. Revisar no repetición, máximo por empresa, afinidad y elegibilidad desde el país de los destinatarios.
7. Anotar incidentes y su resolución. Si el mercado/fuentes no sostienen la cuota, decidir alcance/fuentes/presupuesto
   con los resultados; no ocultar déficit para marcar un objetivo comercial como cumplido.

`python -m buscador.preparacion --salida <directorio>` comprueba siete días con meta, registro, no pendientes y evidencia
de enlaces; también exige captura/observaciones recientes y selección actual comprobada. No mide por sí solo pertinencia
para cada persona, cumplimiento de costos de toda la cuenta ni recepción WhatsApp. Tampoco es una prueba completa de seguridad.

La aceptación técnica del programa puede registrarse separada de la validación de la meta comercial. La continuidad de
120 nuevas útiles no se garantiza porque un día haya alcanzado la cifra ni porque el test unitario lo permita.

## 4. Qué falta antes de WhatsApp

- Completar la evidencia de operación y calidad; atender los casos pendientes, sin reescribir el histórico.
- Definir destinatarios, consentimiento/bajas, países, roles, idiomas y frecuencia por cliente.
- Elegir proveedor/costos de WhatsApp y registrar confirmación de envío por destinatario para evitar duplicados.
- Revalidar enlaces al enviar y usar estado actual del catálogo; no usar `ofertas.status=active` como prueba de vigencia.
- Decidir cómo se conocerá el progreso de una candidatura. La ficha pública no revela rechazo/entrevista de una persona.

Estas funciones no están construidas ni deben presentarse al cliente como incluidas en la entrega actual.

## 5. Modelo de registro de aceptación

Guardar una copia privada que contenga: instancia/URL; fecha/hora Colombia; commits de código y datos; responsables;
IDs de ejecuciones; filas verificadas de la tabla anterior; incidencias; ubicación protegida del respaldo y resultado
de restauración; costos/capacidad aprobados; límites aceptados; y fecha del siguiente control. Las claves se guardan en
un gestor seguro, nunca en ese acta ni en este repositorio.

Declaración sugerida: «Se acepta la versión y alcance indicados con las evidencias y pendientes registrados. Se conoce
que fuentes externas, disponibilidad de ofertas y planes de proveedores pueden cambiar; los incidentes se atenderán
mediante el procedimiento acordado». No declarar «sin fallos» ni firmar pruebas todavía no realizadas.
