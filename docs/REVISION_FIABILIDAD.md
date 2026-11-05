# Revisión de producto, arquitectura y mantenimiento

Revisión del 5 de noviembre de 2026, sobre `main` tras el PR #12. Considera el producto vendido a un operador con
clientes hispanohablantes, LATAM/España/remotas mundiales y máximo USD 5/mes para Apify. No sustituye las evidencias de
[ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md) ni certifica que los servicios externos nunca fallen.

## 1. Diagnóstico de producto

La base tiene controles útiles: múltiples fuentes, aliases, elegibilidad, presupuesto Apify, reintentos, catálogo
histórico, idempotencia del lote y comprobación de enlaces. Hay pruebas Python/JavaScript y SQL. El crecimiento del
producto exige ahora hacer observable y recuperable la operación, además de añadir funcionalidades.

Mantener la meta de veinte nuevas por rol, acompañada de cuatro medidas de valor:

1. Vacantes únicas con enlace comprobado y elegibilidad útil por rol/país.
2. Publicadas en 24 horas con hora confirmada, y proporción sin fecha/hora conocida.
3. Pertinencia de los cargos exactos/similares/cercanos, evaluada por muestra humana.
4. Tiempo entre publicación conocida, detección y disponibilidad real en la página.

Contar diez mil registros, alcanzar 120 en un día o tener muchas pruebas no acredita esas cuatro medidas. Una oferta
válida y reciente puede no encajar con un perfil. No convertir todos los «cercanos» en equivalentes para completar cuota.
El mapa permite, por ejemplo, backend como cercano de IA/ML: es una ampliación de búsqueda, no evidencia de que ese
backend trabaje con IA. Muestrear las seis familias evita que recall alto o una palabra ambigua oculten ruido.

Excel se retiró por decisión del usuario: botón, carga de librería externa, generación backend y dependencia directa.
Supabase es el destino operativo. Los CSV de empresas/configuración y reportes técnicos siguen siendo archivos de
trabajo; la exportación JSON de marcas del navegador no es una base alternativa ni historial de candidaturas.

## 2. Evidencia y límites de acceso

En la consulta de las **12:49 p. m. de Colombia**:

- El PR #12 estaba fusionado y las pruebas de `main` aprobadas.
- La página seguía mostrando la captura de las 11:35:21 a. m., anterior a los controles v3; el reporte público aún no
  tenía verificación de enlaces. No se había acreditado un primer ciclo productivo con ese cambio.
- El criterio de piloto WhatsApp era falso por falta de siete días/evidencia de enlaces; catálogo y frescura sí cumplían.
- La sincronización reportaba 15.061 filas aceptadas, cero pendientes. No son 15.061 vacantes nuevas.
- El repositorio era público. No se pudo verificar protección de `main`: la API devolvió 403 al permiso de administración.
  Eso no demuestra que carezca de protección; el propietario debe revisarla en Settings.
- No se verificó administrativamente el tamaño/plan real de Supabase, facturación global Apify o respaldo real del cliente.

La auditoría previa de 120 seleccionadas encontró 108 con enlace comprobable, cinco pendientes y siete apartadas. Es
evidencia de que hay que mirar calidad después de una carga exitosa; no afirma que los enlaces conserven ese estado hoy.

## 3. Prioridades basadas en el código

P0: resolver/acreditar antes de automatizar WhatsApp. P1: siguiente trabajo de estabilidad/capacidad. P2: evolución.

| Prioridad | Hallazgo / evidencia | Consideración y criterio para resolverlo |
|---|---|---|
| P0 | Fusión y pruebas no acreditan ejecución de v3 | Ver un ciclo real con el SHA correcto, reporte de enlaces, persistencia y página; conservar su ID |
| P0 | No hay monitor independiente de ejecuciones; un cron ausente puede no generar fallo/notificación | Supervisar desde otro proceso/proveedor hora del último dato útil, errores/colas y última captura válida; acordar destinatario y respuesta |
| P0 | Solo se ensayó respaldo/restauración ficticio; no hay backup completo programado por el código | Acordar retención y responsable y restaurar un corte del cliente en destino aislado, incluyendo tres tablas, secuencia y trabajo |
| P0 | Supabase, registro de selección y archivos Git no comparten una transacción | La protección nueva detiene arranque si detecta v1 del día sin registro/lote recuperable; documentar recuperación, no repetir a ciegas |
| P1 | `catalogo.sincronizar` vuelve a encolar todas las filas cada captura | Medir tráfico/tiempo y separar cambios de contenido de actualizaciones pequeñas de observación; no reenviar descripción completa sin cambios |
| P1 | Descripciones y snapshots se repiten en catálogo, selección y filas v1; histórico crece | Medir tamaño con índices, filas actualizadas/muertas, cuotas y respaldo. Archivar no libera espacio. Acordar política antes de límites |
| P1 | URLs ya seleccionadas se recuperan por páginas de todo el histórico (`leer_entregas`) | Medir latencia/consultas al crecer. Diseñar índice/identidad de enlaces y consultas acotadas, conservando no repetición |
| P1 | Una fuente puede devolver vacío, bloquear o cambiar formato sin que caiga toda la captura | Contratos de respuesta por adaptador, fixtures y una prueba acotada de fuente; alertar por caída anómala de datos útiles |
| P1 | Directas fijadas en `requirements.txt`; transitivas sin lock completo ni hashes; Actions usan tags | Añadir resolución reproducible, revisión periódica de dependencias y actualizaciones por PR; validar seguridad/compatibilidad antes de fusionar |
| P1 | CI tiene lógica/SQL, sin recorrido automatizado completo del navegador | Prueba de carga, filtros, clipboard, selección, móvil y datos del despliegue en un entorno de ensayo; probar cuentas del cliente |
| P1 | Código/aprobaciones/cuentas y continuidad del servicio necesitan dueño | Revisar reglas de `main`, revisores, cuentas de recuperación, expiración de claves y quién atiende una alerta |
| P2 | Llegarán perfiles personales, mensajes y candidaturas si se amplía alcance | Separar datos por cliente, autenticar, definir permisos y retención antes de guardar información personal o automatizar envíos |

## 4. Arquitectura: qué conviene conservar y qué evolucionar

### Supabase como estado duradero

Actualmente persiste catálogo y selecciones, pero siguen en `publicado/trabajo/` el presupuesto, colas, memoria auxiliar
y caché. La rama se reescribe y los artefactos caducan a 14 días. El respaldo de Supabase por sí solo no reconstruye todo.

La siguiente evolución debería llevar a Supabase un registro de ejecuciones, reservas de presupuesto y operaciones
pendientes críticas. Usar claves únicas, transacciones y bloqueos apropiados; los archivos pueden permanecer como
cachés reconstruibles. Hacerlo con migración aditiva, pruebas de corte/reintento y ensayo previo, sin borrar lo existente.
No hace falta sustituir toda la infraestructura por una plataforma compleja para empezar a medir estos riesgos.

Se encontró un caso concreto: v1 confirma filas, falla el registro v2 y se pierde el estado antes de publicar. Recuperar
solo URLs evita repetir esas ofertas, pero podría permitir seleccionar veinte adicionales en el mismo día. La guardia
añadida comprueba las filas v1 de hoy frente al registro y lote recuperable antes de buscar. Ante inconsistencia se
detiene, conserva datos y requiere recuperación; si el lote local contiene las filas pendientes permite repararlo.
No crea atomicidad entre servicios ni garantiza una recuperación automática de todo fallo posible.

### Sincronización y capacidad

Con lotes de 100, una captura que envía 15.061 filas requiere aproximadamente 151 POST de catálogo, además de lecturas,
estado y otros registros. El algoritmo vuelve a enviar el contenido aunque solo cambie `observed_at`. La carga real
debe medirse en bytes, tiempo, errores, tamaño e índices; no se infiere una factura de esa cuenta sin verla.

Diseño recomendado para la siguiente mejora: hash del contenido estable y escrituras cuando cambie; observaciones por
ID/campos pequeños solo para ofertas realmente vistas; cierres/archivos como eventos idempotentes. Preservar primera
detección, verificación que caduca y rechazo de respuestas viejas. No excluir timestamps del historial para ahorrar
escrituras ni confundir una sincronización con una nueva observación.

### Captura, calidad y selección como etapas medibles

Conservar adaptadores independientes, presupuestos, backoff y falta de cookies. Diferenciar última ejecución,
último éxito por fuente y última observación útil. El control de enlaces es acotado y puede bloquearse: pendiente no
equivale a cierre. Un catálogo con datos anteriores no debe ocultar que hoy fallaron las tres fuentes.

El cron de GitHub solicita horarios; no asegura recepción inmediata de las ofertas. Si el cliente exige un SLA de
frescura, medir primero retrasos reales y acordar un ejecutor/scheduler con capacidad y monitoreo apropiados. Añadir
más cron al mismo sistema no resuelve una cola atrasada ni garantiza alertas de ejecuciones que no ocurrieron.

## 5. Operación que debe quedar acordada

- **Responsable:** quién revisa diariamente y quién sustituye a esa persona. Canal y tiempo de respuesta acordados.
- **Señales:** edad del dato, observaciones recientes, sincronización pendiente, fuentes fallidas, verificación vigente,
  déficit por rol y gasto. No monitorizar solo que la web responde 200.
- **Umbrales:** el piloto usa dos horas de frescura; acordar si ese umbral representa la necesidad comercial. Los avisos
  de capacidad pueden anticiparse, por ejemplo al 70/85 % del límite real, tras medir base y cuotas.
- **Recuperación:** definir pérdida máxima tolerable de datos (RPO) y tiempo de recuperación (RTO), y probarlo. Una copia
  diaria puede ser punto de partida a acordar; no se promete RPO/RTO sin automatización y ensayo con las cuentas reales.
- **Costos:** USD 5 es Apify, no un presupuesto total de infraestructura ni de un futuro WhatsApp. Revisar reservas,
  uso de toda la cuenta, minutos GitHub y capacidad Supabase; no reiniciar memoria para liberar saldo aparente.
- **Cambios:** usar rama/PR, revisar diff/contratos, pruebas y rollback; reservar una ventana de observación entre cambios
  relevantes. Preferir versiones identificables a fusionar mejoras continuas sin mirar la siguiente captura.

El reporte ahora registra `codigo_commit` y `ejecucion_id`, tomados de Actions. Permite distinguir el código fusionado
del que generó los datos visibles. Fuera de Actions quedan vacíos; no son credenciales ni prueba de calidad por sí solos.
No se ha configurado ni enviado ninguna alerta externa en esta revisión.

## 6. Seguridad y mantenimiento de cambios asistidos por IA

La búsqueda productiva actual **no usa un modelo de IA**; desarrollar el código con asistencia de IA no la convierte
en una dependencia del pipeline. Mantener esa separación evita sumar costo y comportamiento variable a cada captura.

Para código asistido: exigir diff pequeño, pruebas del comportamiento afectado, revisión de migraciones y secretos,
y evidencia del despliegue. Un test generado puede repetir el mismo error que el código; complementarlo con fixtures
independientes, fuentes reales acotadas y aceptación del operador. No usar autoconfirmación de un agente como evidencia.

Se amplió el detector de credenciales para secret keys Supabase y tokens de instalación GitHub que no contemplaba.
Es un control básico: no reemplaza escaneo de secretos del proveedor, revisión de accesos ni rotación si una clave se
expone. Para `main`, comprobar revisión por PR, checks `pruebas` y `sql` y restricción de push directo/forzado. Las reglas
de esa rama no deben bloquear sin planificación la escritura automática de `publicado`, que hoy se reescribe.

Si se incorpora IA más adelante:

1. Mantener la ficha original y evidencias como fuente; la IA no inventa salario, empresa, elegibilidad, fechas o vacantes.
2. Tratar descripciones/enlaces como datos no confiables. Sus instrucciones no autorizan ejecutar código, revelar claves,
   pagar, postular o contactar terceros. Validar URLs y salida estructurada fuera del modelo.
3. Separar permisos de lectura de acciones; limitar herramientas y presupuesto por cliente y registrar decisiones.
4. Versionar modelo, prompt, esquema y conjunto de evaluación; comparar calidad por rol/país, no solo texto convincente.
5. Prever timeout, proveedor caído, salida inválida y vuelta al flujo determinista. No depender del plan de este chat.
6. Mantener perfiles/CV, contactos y mensajes fuera de la rama pública. Antes de multicliente, diseñar autorización y
   permisos por cliente; service_role del scraper no se entrega al navegador ni a usuarios finales.

## 7. Orden de trabajo recomendado

1. Fusionar correcciones acotadas y observar un ciclo completo con su SHA; confirmar en web y base.
2. Acreditar backup real, avisos independientes y responsables. Completar aceptación con las cuentas del cliente.
3. Observar siete fechas distintas y muestras útiles por rol. Atender déficit/ruido con fuentes y aliases medidos.
4. Con métricas, priorizar sincronización incremental y estado crítico duradero en Supabase. Ensayar interrupciones.
5. Añadir WhatsApp después: registro por destinatario, clave única cliente/vacante/canal, pendientes de envío y confirmación
   del proveedor. Distinguir aceptado por API, entregado y leído. Copiar una selección no prueba ninguno de esos estados.

La revisión no mueve automáticamente estado a Supabase, configura alertas, cambia planes, habilita protección de ramas
ni construye WhatsApp. Esas decisiones tienen costo/credenciales y necesitan un cambio concreto con validación. Los
controles ya implementados en esta revisión y los riesgos todavía abiertos quedan separados en las secciones anteriores.
