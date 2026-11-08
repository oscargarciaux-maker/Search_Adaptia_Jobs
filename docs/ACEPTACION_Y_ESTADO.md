# Aceptación del proyecto y estado comprobado

Este documento distingue código probado, operación observada y aceptación en las cuentas del cliente. No certifica
ausencia total de fallos. Actualizar el corte y adjuntar evidencia después de una prueba real; no cambiar pendientes a
aprobados por haber fusionado otro PR. Instrucciones de uso: [GUIA_CLIENTE.md](GUIA_CLIENTE.md).

## 1. Corte de evidencia

### Fallo recurrente tras 008 — SQL 010 ensayada, instalación pendiente

Las capturas [42446101328](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42446101328)
y [42449938233](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42449938233) fallaron en
validación por SQLSTATE 57014. En el reporte de la segunda se confirmaron 16.908 filas sincronizadas, sin pendientes
centrales; falló la consolidación posterior. No significa 16.908 ofertas nuevas ni acreditación de toda su vigencia.

El [diagnóstico 42453546438](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42453546438)
confirmó 20.251 registros de catálogo, 360 selecciones históricas, 359 ofertas operativas y 44 filas archivadas.
Con la función 008 instalada se agotaron tres segundos en resolución de identidades. El patrón de aliases recíprocos
reprodujo el fallo local; las pruebas anteriores de volumen sin esas relaciones no bastaban para este caso.

SQL 010 extrae metadatos una vez, resuelve las relaciones por clave y evita actualizar ofertas sin cambios. No amplía
el timeout, añade tablas ni elimina las verificaciones. El [ensayo 42454009812](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42454009812)
ejecutó 010 en la base real dentro de una transacción revertida: la función anterior volvió a agotar el límite;
la corregida completó en 360 ms como service_role, con 359 filas operativas y cuatro sin identidad confirmada.
Esas cuatro no se eliminan ni se asocian sin evidencia. El ensayo revirtió tanto SQL como datos y registro de versión.

Validación local: 697 pruebas Python, PostgreSQL con 24.000 registros y 6.000 aliases recíprocos bajo tres segundos,
ciclos explícitos rechazados, prefijos explícitos válidos, principales ausentes, límites de cadenas, conservación de
snapshots/archivo, concurrencia y repetición sin nuevas versiones físicas de filas. Instalación, rollback de migración
y respaldo/restauración de once tablas/dos secuencias aprobados. CI comprueba también el panel sin modificarlo.

La corrección aún requiere fusión y Preparar Supabase con respaldo. Después, comprobar una reconciliación y captura
real posteriores a la instalación antes de acreditar recuperación; el ensayo revertido no la instala ni silencia alertas.

### Control por clientes v6 — preparado para revisión, no desplegado

Por petición del propietario, se implementa una nueva interfaz privada de clientes/perfiles, cargos abiertos, cupos
por cargo que suman 120, filtros independientes, versiones desde mañana y copia manual de WhatsApp. La decisión
anterior de retirar una web no prohíbe esta nueva plataforma. Inicio de sesión y alojamiento real diferidos por el
propietario; la demostración usa exclusivamente datos ficticios y el servidor real permanece cerrado sin autorización.

Evidencia local: 696 pruebas Python, compilación TypeScript/Vite, dos recorridos Playwright en Chromium (gestión,
programación, copia real al portapapeles y móvil); PostgreSQL 17 prueba permisos, revisiones concurrentes, vigencia,
referencias y copia/restauración de once tablas/dos secuencias. SQL 008 conserva el ensayo de 18.000 registros/300
ofertas y límite de tres segundos. La imagen Docker se comprueba en modo ficticio y cerrada sin configuración real.

El ensayo dirigido de fuentes públicas, sin Supabase/Apify, obtuvo 29 registros de inventario en 0,7 minutos con
presupuestos mínimos. No seleccionó oportunidades para los filtros estrictos de la muestra; **no acredita 120 reales**.
Se comprobaron cargos/lugares dirigidos y ausencia de nombres/identificadores de clientes en archivos de captura.
La aceptación productiva requiere instalar 008/009, configurar alojamiento/login, programar criterios y observar una
captura dirigida real. No se modifica el historial anterior para aparentar resultados nuevos. Manual: [PANEL_CONTROL.md](PANEL_CONTROL.md).

### Alertas de captura y consulta de consolidación — 6 de noviembre de 2026

La captura [42278586716](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42278586716)
terminó correctamente a las 2:32 p. m. Colombia con el commit posterior al PR 23. La siguiente,
[42285642036](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42285642036), terminó en fallo a las
3:18 p. m.: preparación, captura, respaldo de estado y actualización del reporte completados; falló la validación final.
El reporte confirmó 15.646 filas de catálogo enviadas sin errores ni pendientes, cero pendientes centrales, y error
HTTP 500 / 57014 al reconciliar ofertas únicas. Esto acredita el guardado del catálogo de ese corte, no la consolidación.

SQL 008 prepara consulta indexada de URLs sin modificar migraciones registradas. La prueba aislada PostgreSQL 17
comprueba 18.000 registros con enlaces alternativos y 300 ofertas, uso real del índice y reconciliación bajo límite de
tres segundos con service_role, además de archivo, ambigüedad, referencias y recuperación. El arreglo requiere revisión,
fusión, instalación y comprobación real antes de afirmar recuperación productiva. No se silencian las alertas.

### Admisión geográfica reforzada — 6 de noviembre de 2026

La preparación [42270700157](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42270700157)
terminó correctamente a la 1:27 p. m. Colombia: siete migraciones vigentes; aplicadas 006 y 007 después de fusionarse
el PR 22. Esto acredita instalación del esquema, no una captura posterior ni corrección de toda ficha externa.

La revisión siguiente refuerza la admisión por evidencia positiva: oficinas presenciales/híbridas dentro de cobertura,
remotas con alcance pertinente, todas las restricciones de residencia reconocidas y exclusión de horarios como única
prueba. Tampoco se promociona «Global» a ubicación física ni se toma un país del título para cambiar una oficina
extranjera. Los metadatos sin confianza geográfica quedan fuera. Requiere fusionar este nuevo ajuste y observar una
captura con su commit para acreditar el efecto productivo; los snapshots históricos no se reescriben.

### Estonia y preparación posterior al PR 21 — 6 de noviembre de 2026

El PR 21 se fusionó a las 12:34 p. m. Colombia. La preparación
[42262920061](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42262920061) conservó el respaldo,
pero no instaló 006: ocho ciclos de aliases inferidos bloquearon la reconciliación. La reparación preparada conserva
SQL 001–006, ordena esos aliases dentro de la transacción respaldada antes de 006 e incorpora 007 para resolver
futuros ciclos implícitos. Las referencias explícitas contradictorias siguen abortando.

La auditoría de solo lectura [42264805543](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42264805543)
confirmó el caso LinkedIn 4487752612: Product Owner de Playtech, Tartu/Estonia, fila 222 de `ofertas`, ID
`99af2b8a2f2e8824`, seleccionado el 6 de noviembre. El catálogo lo tenía activo con todos los países y confianza
baja. El filtro anterior desconocía Estonia y la entrega admitía ubicaciones de confianza baja.
Las reglas corregidas excluyen ese país y apartan las ubicaciones sin confirmar de nuevas entregas. Al revisar
6.555 fichas activas con esas reglas, 206 quedan fuera de cobertura y 1.039 pendientes de región; son cifras del
catálogo, no de las 120 seleccionadas ni una certificación individual de las demás.

El ensayo [42264625952](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42264625952)
ejecutó 006/007 sobre los datos reales y revirtió toda la transacción correctamente. No instaló migraciones ni retiró
ofertas productivas. Las pruebas PostgreSQL aisladas también comprueban la reversión del ensayo, el archivo de copias,
la conservación de snapshots y el rechazo de ciclos explícitos. La activación efectiva requiere fusionar el arreglo,
verificar Preparar Supabase y comprobar una captura; no se acredita solo con estos ensayos.

### Corrida del 6 de noviembre de 2026: revisión posterior

La [nocturna 42180442019](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42180442019)
terminó a las 2:58 a. m. Colombia con 120 seleccionadas, 121 filas y veinte por cada rol. Se comprobó al menos un
enlace de cada seleccionada en ese corte. Usó cuatro migraciones y fue anterior a la fusión del PR 20.

La preparación [42247389682](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42247389682)
aplicó 005 a las 10:55 a. m. La [auditoría 42248248084](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42248248084)
posterior detectó 119 oportunidades distintas entre 120 selecciones: dos QA de OfferUp eran una misma oportunidad.
Otras dos QA exigían residencia en Alemania/Países Bajos y Réunion/Mónaco pese a la etiqueta general EMEA. La revisión
de ese lote deja 17 QA distintas dentro de la cobertura según las reglas corregidas, no veinte certificadas.

La [captura 42248658081](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42248658081)
guardó catálogo y estado sin pendientes, pero falló al validar reconciliación. Una comprobación específica obtuvo
HTTP 500 / SQLSTATE 57014: la API canceló la consulta por tiempo. SQL 006 prepara resolución por lotes; el ajuste de
residencia reconoce requisitos físicos y alcance específico del título. Ambos requieren fusión/preparación/captura
para acreditar su resultado productivo. Los snapshots históricos se conservan y no se usan para aparentar reposición.

### Corrección de identidad preparada el 6 de noviembre de 2026

La auditoría de solo lectura [42181448612](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42181448612)
revisó la entrega completa: 162 filas operativas, 120 selecciones y 120 oportunidades reconocidas. Encontró 42 grupos
con dos filas por enlace y 42 filas adicionales; no quedaron vínculos ambiguos en esa entrega. El catálogo QA
contenía 219 registros clasificados y 210 sin seleccionar; esto no certifica enlaces comprobados de todas ellas.

SQL 005 y el contrato v5 convierten `ofertas` a una fila por vacante reconocida y conservan las copias en
`ofertas_enlaces_historicos`. En PostgreSQL 17 aislado, un corte de las 120 seleccionadas reprodujo 162 filas;
la migración dejó 120 y archivó 42, con cero sin identificar y sin cambiar las selecciones. También se ensayaron
reintentos antiguos, inserciones concurrentes, enlaces ambiguos y aplicación repetida. Es evidencia de la reparación
ensayada; todavía requiere fusión y preparación real para acreditar que Supabase productivo quedó consolidado.

La captura pública `--prueba` del cambio terminó en 8,7 minutos con 1.483 registros temporales y doce comprobaciones
positivas de doce programadas. No escribió en Supabase ni usó el actor Apify; no generó archivos de interfaz.
GitHub rechazó la baja del sitio alojado con HTTP 403 tanto en esta sesión como desde Actions; el despliegue futuro
está deshabilitado. La baja definitiva requiere los permisos administrativos del propietario. No declararla realizada.

Alcance vigente: scraper, automatización y Supabase. La interfaz web y sus despliegues se retiran por decisión
del propietario. Las referencias a web/Pages de cortes anteriores son evidencia histórica, no requisitos de entrega
actual. Los criterios de interfaz, despliegue y envío manual desde la página quedan fuera de alcance. La retirada
local del código no acredita por sí sola que el sitio alojado se haya dado de baja.

### Actualización de la noche del 5 de noviembre de 2026, Colombia

- **Preparación automática confirmada:** [42155588984](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42155588984)
  terminó con respaldo cifrado y SQL 001–003; los fallos de contraseña/TLS documentados más abajo quedaron superados.
- **Captura central posterior confirmada:** [42159000280](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42159000280)
  terminó a las 11:00 p. m. y confirmó catálogo/estado central, sin pendientes de sincronización. Programó 40 revisiones;
  el lote histórico mostró 32 verificadas, 86 pendientes y 2 rechazadas. Este resultado no acredita 120 listas actuales.
- **Auditoría real de Supabase en solo lectura:** [42160286445](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42160286445),
  11:04 p. m. Confirmó 20 selecciones por cada uno de seis roles y 162 filas v1. QA tiene 20 selecciones/27 filas,
  pero diez seleccionadas eran desarrollo genérico demasiado cercano; otro título corresponde a calidad de Customer
  Success. No afirmar veinte ofertas pertinentes de QA. La muestra es de títulos públicos y estados, sin imprimir secretos.
- **Corrección incluida con estos documentos, todavía requiere fusión/captura:** afinidad QA/IA, reclasificación del
  inventario previo, prioridad de afinidad, vista SQL 004 y disponibilidad por rol. No modifica ni repone snapshots
  históricos. El aumento horario a 120 revisiones/180 segundos es un límite, no prueba de haberlas realizado.
- Faltan continuidad de siete días, calidad y capacidad/recuperación aceptadas por el cliente; no se declara producto
  perfecto ni listo para envío WhatsApp automático.

Validación del cambio propuesto: 539 pruebas Python y suite Node; SQL 004 aplicada dos veces en PostgreSQL 17
aislado, con permisos, caducidad, fechas inválidas, enlaces ajenos, cierres y preservación del histórico. Se ensayaron
instalación/migraciones, respaldo cifrado y restauración. Una captura pública `--prueba` de seis minutos obtuvo 1.336
vacantes temporales y 11 enlaces comprobados de 12 programados; sin escritura en Supabase ni actor Apify. No acredita
una nueva selección productiva de 120 con el cambio ni comprobación exhaustiva de la calidad de esas 1.336 fichas.

Las secciones siguientes conservan evidencia histórica; sus pendientes antiguos no sustituyen esta actualización.

**Diagnóstico histórico del 5 de noviembre, superado por la preparación indicada arriba:** el intento
[42147221329](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42147221329) superó el formato de
la clave de respaldo y falló al conectar. Una comprobación de solo lectura en la rama de corrección aisló un error TLS
([42147821931](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42147821931)). Al añadir la raíz
pública oficial Supabase manteniendo `verify-full`, la siguiente comprobación superó TLS y recibió rechazo de autenticación
([42148436056](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42148436056)). Falta corregir la contraseña
o su codificación en el secreto privado. No se aplicaron migraciones ni se escribieron vacantes en esas comprobaciones;
el estado central productivo no queda acreditado por ellas.

**Automatización de instalación preparada posteriormente:** se ensayaron en PostgreSQL 17 aislado la instalación nueva
con autorización explícita, paso de una base manual a automática conservando historia y reservas, rechazo de SQL
reescrito, rollback del lote y dos migradores concurrentes. El respaldo cifrado se debe subir antes de aplicar en Actions.
Se restauraron seis tablas/dos secuencias y trabajo, con decimales exactos, y se rechazó una copia alterada. Estas pruebas
no configuran secretos, migran Supabase real ni acreditan continuidad productiva. Ver [la guía](INSTALACION_AUTOMATICA.md).

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
de restauración; costos/capacidad aprobados; límites aceptados; y fecha del siguiente control. Las claves se conservan
en una ubicación privada acordada por propietario y cliente, nunca en ese acta ni en este repositorio.

Declaración sugerida: «Se acepta la versión y alcance indicados con las evidencias y pendientes registrados. Se conoce
que fuentes externas, disponibilidad de ofertas y planes de proveedores pueden cambiar; los incidentes se atenderán
mediante el procedimiento acordado». No declarar «sin fallos» ni firmar pruebas todavía no realizadas.
