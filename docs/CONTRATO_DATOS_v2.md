# Contrato de catálogo y frescura v2

Extensión compatible del contrato v1. La entrega histórica `ofertas` conserva sus columnas v1. El catálogo persistente
se guarda por separado en `catalogo_vacantes`; las capturas frecuentes no crean entregas ni marcan ofertas como enviadas.
No hay tablas de clientes, postulaciones ni mensajes WhatsApp en esta versión.

## Campos de frescura

| Campo de la vacante | Formato | Regla |
|---|---|---|
| `publicada_en` | ISO 8601 UTC o vacío | Hora real de publicación, solo si la fuente la proporciona con zona horaria. Nunca usar modificación como publicación. |
| `detectada_en` | ISO 8601 UTC o vacío | Primera detección con hora registrada por el sistema. No convertir una fecha histórica sin hora en medianoche. |
| `vista_en` | ISO 8601 UTC o vacío | Última observación efectiva en una fuente. No renovar al releer la bodega. |

`fecha_publicacion` sigue siendo la fecha real conocida; `fecha_estimada` marca ausencia de fecha. Si solo existe fecha,
se muestra esa precisión y no se afirma «hace 40 minutos». `visto_primera_vez` y `visto_ultima_vez` se conservan por
compatibilidad. Una fecha de actualización de un aviso no demuestra publicación nueva.

## Persistencia del catálogo

`catalogo_vacantes`: `id` (identidad estable), `datos` (campos públicos de la vacante definidos por el catálogo v1/v2),
`description_full` (texto, máximo 30.000 caracteres), `published_at`, `first_seen_at`, `last_seen_at`, `observed_at`,
`status`, `closed_at`, `reason` y `contract_version` (`v2`). Los tiempos son timestamptz UTC, opcionales salvo
`observed_at` (momento de la sincronización).

Estados: `active` = presente en el catálogo activo; `closed` = cierre observado en un listado completo;
`archived` = retirado por antigüedad, calidad o fusión de duplicados. Antigüedad no equivale a cierre. No se borra el
registro histórico por salir del buscador. Un estado activo no certifica que cada fuente haya sido revisada recientemente:
hay que mostrar `last_seen_at` y la salud de la captura. La tabla tiene RLS y acceso exclusivo service_role.

La actualización conserva la primera detección conocida, no acepta observaciones anteriores a las ya guardadas y no
reabre un cierre con una vacante que no se volvió a ver después de ese cierre. La entrega v1 no sobrescribe su contenido.

Ritmo de escritura (9 nov 2026): cada captura envía las filas nuevas o cuyo contenido cambió (datos, estado, fechas
de publicación, verificación de enlaces, descripción). Volver a ver una vacante sin cambios solo actualiza
`last_seen_at`/`observed_at` por rotación: cada fila se renueva aproximadamente cada 6 horas y como máximo a las 12.
Por eso `observed_at` es el momento del último envío de esa fila, no de cada captura. Ningún filtro ni vista usa esas
marcas para decidir vigencia; los enlaces siguen exigiendo comprobación de menos de seis horas en `verificacion`.
La memoria de huellas vive en `trabajo/catalogo_sincronizado.json.gz` (sin datos de clientes); si se pierde, la
siguiente captura vuelve a enviar todo el catálogo.

## Entrega diaria e idempotencia

Cada fecha de Bogotá tiene un lote por rol. Una repetición puede reintentar pendientes y completar plazas faltantes,
pero nunca añadir otras 20 a un rol que ya tiene 20. El lote conserva las ofertas seleccionadas y se registra antes de
enviar. La captura horaria no modifica ese lote. Una futura entrega WhatsApp necesitará su propia confirmación de envío
y no debe interpretar «seleccionada» o «sincronizada» como «enviada a una persona».

`entregas_diarias`: `vacante_id` (clave única y referencia al catálogo, sin borrado en cascada), `delivery_date`, `role_id`,
`match_grade` (`exact`, `similar`, `close`), `selected_at` y `snapshot` (vacante tal como se seleccionó, incluida descripción).
No se sobrescribe una selección confirmada. La clave única impide volver a seleccionar la misma identidad aunque se pierda
el archivo de memoria; el lote del día puede reconstruirse leyendo los snapshots. No representa un envío WhatsApp.

## Activación

Aplicar primero `supabase/migraciones/002_catalogo.sql`. Después activar `CAPTURA_HORARIA_ACTIVA=true` en variables de
GitHub. El flujo horario queda desactivado hasta ese paso; la entrega nocturna v1 sigue funcionando sin esta migración.
La migración es aditiva y no elimina ni reescribe ofertas históricas. La aplicación del SQL requiere acceso al SQL Editor
o a una conexión administrativa; la clave REST del scraper no proporciona un endpoint de migraciones SQL.
