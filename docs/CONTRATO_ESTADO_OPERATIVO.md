# Estado operativo duradero — contrato y activación

Extensión aditiva al catálogo v2/verificación v3. Se documenta antes del código. No altera columnas de `ofertas`,
vacantes históricas ni registro de selección. No añade clientes, mensajes o candidaturas. GitHub conserva código,
manuales, capturas y cachés; Supabase pasa a ser autoridad del estado crítico al activar esta extensión.

## Datos nuevos

`estado_operativo`: clave compuesta `cola`/`identificador`, `payload` JSON, `revision` bigint de secuencia global y
`actualizado_en`. Colas: `catalogo`, `ofertas`, `registro`, `lote`; control de inicialización privado en `control`.
Las tres primeras contienen únicamente tareas sin confirmar; un lote conserva el snapshot del día hasta que sus
elementos están registrados canónicamente. Confirmar una tarea elimina el pendiente, no la vacante ni su histórico.

Las escrituras y confirmaciones pasan por funciones SQL: comparación de revisión, bloqueo y cambio en una transacción.
Una confirmación antigua no elimina un pendiente nuevo. Un conflicto detiene el proceso y exige releer estado. Los
lotes solo pueden crecer hasta veinte por rol y no permiten modificar una selección ya guardada. Un lote completo
confirmado se puede retirar del área temporal porque permanece en `entregas_diarias`.
La comprobación contra el registro canónico permanece incluso tras retirar ese temporal: un proceso atrasado no puede
usar revisión cero para reemplazar/comenzar otro lote del mismo día. Los lotes sin confirmar de días anteriores permiten
reconstruir sus colas de filas/registro con fecha original, aunque el proceso se cortara antes de crearlas.

`apify_reservas`: `solicitud` text, `fecha`, `ejecucion` UUID opcional, `micro_usd` bigint y `origen` (`legado`/`central`).
Un micro-USD es 0,000001 USD: se usan enteros para no liberar crédito por redondeos de coma flotante. Un bloqueo por mes
protege el cálculo concurrente. Tope de proyecto hasta USD 5/mes, reparto diario por días del mes y máximo solicitado
por corrida (hasta USD 3). La fecha debe coincidir con el día de Bogotá de la base; discrepancia detiene la reserva.
La reserva se confirma antes de ejecutar el actor. No se devuelve si Apify o la respuesta de red no confirman resultado.
Repetir el identificador de solicitud no autoriza otro cargo. Un timeout no se reintenta automáticamente.

La importación de reservas antiguas es monotónica: preserva el mayor total conocido sin sumar otra vez las reservas
centrales ya reflejadas en la copia local. Solo se importa un corte coherente de la instancia; no se puede inferir la
suma de dos negocios independientes a partir de contadores antiguos agregados. El gasto global del proveedor prevalece.

## Seguridad y errores

RLS, sin permisos públicos. `service_role` puede leer; modificaciones solo mediante RPC privadas concedidas a ese rol.
Si falta esquema, falla RPC, hay conflicto o no puede importarse el estado inicial, no se usa un contador local como
alternativa silenciosa. Antes de persistir a la base se conserva la copia local para diagnóstico/artefactos. No se
declara confirmada una operación porque únicamente se haya escrito el archivo.

Una base caída no puede guardar su propia cola: el proceso se detiene y conserva la copia disponible. Esto reduce la
dependencia de `publicado`, pero no sustituye respaldos de Supabase ni hace atómicas una llamada Apify y la base.

## Activación controlada

El camino preferido está en [INSTALACION_AUTOMATICA.md](INSTALACION_AUTOMATICA.md): respaldo cifrado subido antes del SQL,
versiones/hashes privados en `adaptia_migraciones` y marca `control/instalacion_automatica` con las versiones esperadas.
Las capturas la detectan sin crear variables GitHub. El esquema y las reservas se preparan con conexión administrativa;
la captura conserva clave REST. Los pasos siguientes se mantienen como alternativa manual.

1. Fusionar código y pausar flujos que escriben; esperar los que estén en curso. Guardar corte/respaldos y reservas.
2. Aplicar `supabase/migraciones/003_estado_operativo.sql` con SQL Editor administrativo, después de esquema y 002.
3. Asegurar que el corte contiene `apify_presupuesto.json`, lote y colas actuales. La primera lectura importa ese
   estado; si la base no está inicializada y falta presupuesto local, falla en vez de asumir saldo cero.
4. Para una instalación genuinamente nueva, un administrador puede inicializar explícitamente con un JSON de mes y
   reservas vacío, usando `operacion_inicializar`. No hacerlo para reemplazar reservas perdidas de una instancia usada.
5. Crear variable GitHub `ESTADO_SUPABASE_ACTIVO=true`, manteniendo `CAPTURA_HORARIA_ACTIVA=true`. Se reutilizan secretos
   Supabase. La búsqueda profunda también recibe las credenciales para reservar centralmente si utiliza Apify.
6. Habilitar un flujo y comprobar importación, reservas, recuperación de pendientes y lote; después reanudar horarios.
   `--prueba` no migra, no escribe estado central ni ejecuta Apify.

La variable permanece apagada hasta completar esos pasos. No desactivarla como arreglo de un fallo: volver al contador
local requiere corte y exportación actualizados. Las copias locales son auxiliares; la caché de verificaciones,
rotaciones y bodega de descripciones continúa en archivos y puede requerir recolección si se pierde.
