# Contrato público v3: verificación de enlaces

Extensión compatible de los campos públicos v2. No cambia las columnas de `ofertas` ni la selección histórica.
El sobre SQL de `catalogo_vacantes` sigue siendo `contract_version=v2`: el nuevo objeto se guarda dentro de `datos`
(JSON), sin migración de tablas. No se implementan postulaciones ni envíos WhatsApp.

## Campo `verificacion`

Objeto opcional: `estado` (`verificada`, `pendiente`, `rechazada`), `comprobada_en` (ISO UTC o vacío), `motivo`,
`url_utilizable` (un enlace comprobado o vacío) y `enlaces` (lista de resultados por URL).
Cada resultado contiene `url`, `destino`, `estado`, `motivo`, `comprobada_en`, `http` (número o null),
`saltos` (número) y `ruta` (URLs recorridas, limitada). Los fragmentos y parámetros originales se preservan al consultar.

`verificada` significa que se pudo consultar una ficha específica compatible con el título anunciado, sin detectar
las causas de rechazo descritas abajo. No certifica a la empresa, no promete que siga abierta después de la revisión
y no afirma que se haya recorrido una postulación completa. No se envían formularios, credenciales ni pagos.
Una ruta de aplicación visible se comprueba por GET cuando puede identificarse sin iniciar sesión.

Se rechazan HTTP 404/410, ciclos o exceso de redirecciones, destinos agregadores/de pago conocidos, señales explícitas
de cobro para postular, cierres en la ficha, expiración estructurada y páginas generales sin oferta específica.
Timeout, 403/429, login/CAPTCHA, sitio que requiere JavaScript o contenido insuficiente quedan `pendiente`.
Un bloqueo no es evidencia de cierre. Una mención de salario, beneficios, formación paga u otra advertencia contra
estafas no demuestra que se cobre al aspirante.

Un enlace rechazado no invalida otro enlace comprobado de la misma oferta. La selección de enlaces para compartir y
las filas de nuevas entregas usan únicamente los comprobados. Si no hay ninguno, la oferta permanece por verificar o
se retira del catálogo activo según la evidencia; nunca se borra del histórico. Un lote ya seleccionado no se reescribe
para ocultar errores posteriores. Su estado actual debe comprobarse aparte antes de un futuro envío WhatsApp.

## Caducidad y límites

Las comprobaciones positivas se reutilizan un máximo de seis horas; rechazos, seis horas; estados pendientes,
treinta minutos. No se renueva su hora por leer caché. Cambiar el título de referencia obliga a comparar de nuevo.
Se limita el número de ofertas, concurrencia, saltos, bytes, tiempo por solicitud y tiempo total. Lo que no alcanza a
comprobarse queda pendiente, no aprobado. La captura horaria rota comprobaciones y prioriza la selección del día;
la nocturna comprueba candidatas y puede completar con otras verificadas, conservando las reglas de variedad.

El reporte de salud incluye cantidades comprobadas, pendientes/rechazadas y motivos; la página muestra estado y hora.
`codigo_commit` y `ejecucion_id` identifican el código y ejecución que generaron ese reporte. Son metadatos opcionales
de salud, vacíos fuera de Actions; no exponen claves ni sustituyen las comprobaciones del dato y del despliegue.
Las vacantes históricas sin este objeto se muestran sin comprobar. No se interpretan automáticamente como verificadas.
La verificación se aplica antes de nuevas selecciones en el flujo de producción; utilidades offline compatibles v1/v2
pueden seguir operando sin acceso a red. No se usa crédito de Apify para estas comprobaciones.

## Recuperación conservadora de una selección parcial

Si existen filas v1 de la fecha de negocio actual sin correspondencia en el registro canónico ni en un lote local
recuperable, el arranque normal se detiene antes de recoger o consumir Apify. La memoria de URLs evita duplicar una
oferta, pero por sí sola no reconstruye cuántas plazas ya ocupaba el lote perdido. Se debe recuperar el estado del
corte/artefacto y completar el registro; no crear otras veinte para aparentar una reanudación correcta. Las filas y
los snapshots se conservan. Este control no convierte las escrituras de tablas y GitHub en una única transacción.
