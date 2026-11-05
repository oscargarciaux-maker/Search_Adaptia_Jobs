# Aprender y activar el estado operativo en Supabase

**Camino preferido actual:** [INSTALACION_AUTOMATICA.md](INSTALACION_AUTOMATICA.md). Con dos accesos iniciales adicionales,
GitHub respalda, aplica 001/002/003 e importa/activa sin copiar SQL ni crear variables. Las secciones 3–4 y 7 de esta
guía describen la alternativa manual anterior. Los conceptos y límites siguientes siguen siendo útiles para aprender.
El instalador añade `adaptia_migraciones`: sus cortes incluyen seis tablas y dos secuencias.

Preparado el 5 de noviembre de 2026. **Código preparado no significa activación productiva.** Esta extensión requiere
SQL 003 y la variable indicada más abajo. No se aplicó a la base real durante su desarrollo.
Contrato técnico: [CONTRATO_ESTADO_OPERATIVO.md](CONTRATO_ESTADO_OPERATIVO.md).

## 1. Por qué GitHub y Supabase cumplen funciones diferentes

GitHub guarda el código, su historial y los manuales. Un PR es una propuesta revisable de cambios; fusionarlo incorpora
el código a `main`. GitHub Actions ejecuta ese código en una máquina temporal de la nube. Cuando antes se dijo «local»,
se hablaba de los archivos de esa máquina, no necesariamente de tu computador. La máquina se descarta al terminar.

La rama `publicado` conserva una página estática y copias de trabajo entre ejecuciones. Esa rama se reemplaza al publicar:
es útil para servir resultados y cachés, pero una copia perdida o atrasada puede perder un contador o una tarea.
Supabase conserva datos y permite una **transacción**: comprobar una condición y guardar un cambio como una sola operación.
Eso importa cuando dos procesos consultan el mismo saldo o intentan confirmar la misma tarea.

| Elemento | Dónde queda | Qué aprende el operador |
|---|---|---|
| Código, configuración y manuales | GitHub | Se revisan en PR y tienen historial |
| Catálogo e historial de vacantes | Supabase, tablas existentes | Archivar una vacante no borra su historial |
| Reservas del crédito Apify | Nueva tabla `apify_reservas` | Se reserva antes de iniciar el actor; no es una factura |
| Tareas pendientes y selección todavía sin confirmar | Nueva tabla `estado_operativo` | Si se corta el proceso, se retoma el trabajo guardado |
| Página, rotación de búsquedas y cachés | `publicado`, carpeta `trabajo/` | Se siguen conservando; aún no todo vive en la base |

Ejemplo del presupuesto: quedan USD 0,03 y dos procesos piden USD 0,025. La base atiende las reservas en orden bajo un
bloqueo: el segundo solo puede obtener el remanente que permitan los topes. No se concede a ambos el mismo saldo.
Una reserva cuya respuesta se pierde no se libera automáticamente: se prefiere dejar crédito sin usar a gastarlo dos veces.

Ejemplo de pendientes: la tarea de guardar una vacante tiene revisión 41; otra captura la actualiza a revisión 42.
Una confirmación de la 41 no puede borrar la 42. Esa revisión funciona como un recibo de la versión que se está confirmando.

## 2. Qué cambia al activarlo

1. Antes de buscar, se comprueban Supabase y el catálogo, se importan las reservas antiguas y se recuperan las colas.
2. Cada actor Apify necesita una reserva confirmada en la base. Se mantienen USD 5/mes, reparto diario y límite por corrida.
3. La selección se guarda antes de enviar sus filas. Si falta su cola por un corte, se reconstruye desde ese snapshot,
   también para días anteriores, manteniendo fecha e identidades originales.
4. El proceso confirma y retira únicamente las tareas terminadas. La vacante y su selección histórica permanecen.
5. La captura horaria y la profunda reintentan pendientes existentes. No crean otra selección diaria. La horaria sigue
   sin ejecutar Apify; la profunda puede ejecutarlo y comparte el mismo presupuesto.
6. Un esquema ausente, revisión en conflicto o estado sin confirmar detiene la operación afectada. No se vuelve
   silenciosamente al contador de archivos. Una inicialización fallida detiene el arranque antes de buscar.

No existe una transacción única entre Apify, Supabase, GitHub y la red. Puede haber trabajo reservado que no llegó a
ejecutarse; se conserva para revisión. Una base caída tampoco puede guardar su propia cola: queda la copia auxiliar
disponible y el proceso falla. No se promete ausencia total de fallos externos.

## 3. Preparar el corte con el administrador

Estos pasos son de mantenimiento; no hace falta repetirlos cada día:

1. Fusionar el PR aprobado y comprobar que `Pruebas` terminó bien, incluidos los trabajos Python/JavaScript y SQL.
2. Deshabilitar **Bodega nocturna**, **Captura horaria** y **Búsqueda profunda** desde Actions. Esperar las ejecuciones
   en curso y evitar despachos desde Cloudflare. No basta apagar la variable de captura horaria.
3. Guardar un corte de `publicado` completo y el respaldo de las tres tablas existentes. Anotar SHA, ejecución, fecha
   y reservas. Seguir [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md).
4. Comprobar que `trabajo/apify_presupuesto.json` del corte contiene `mes` y `reservas`. Conservar lote y colas.
   Si se perdió el contador de una instalación usada, recuperarlo de un corte coherente y contrastar Apify. **No crear
   un contador vacío para desbloquearla.** La base no puede deducir el gasto antiguo que nunca recibió.
5. Confirmar que ninguna copia anterior sigue gastando en la misma cuenta Apify. La protección central solo cubre
   procesos que usan esta misma base y este mecanismo. Otros actores, diagnósticos y negocios requieren control global.
6. Revisar tamaño/cuota real de Supabase y margen para una cola de catálogo completa, que temporalmente duplica contenido.
   Si no cabe, mantener los flujos pausados y resolver capacidad/sincronización antes de activar. El plan gratis no se
   acredita por tener pocas filas. El SQL de tamaño del manual de operación y el panel del proveedor ayudan a medirlo.

## 4. Aplicar el esquema y activar

1. En el proyecto correcto de Supabase, **SQL Editor → New query**, ejecutar completo
   [003_estado_operativo.sql](../supabase/migraciones/003_estado_operativo.sql). Requiere `esquema.sql` y 002 previos.
   Es aditivo y repetible; no limpia tablas ni reinicia reservas. Revisar el resultado antes de continuar.
2. Comprobar en Table Editor `estado_operativo` y `apify_reservas`. Tras el SQL pueden estar vacías: la primera ejecución
   importa el corte. Nunca desactivar RLS para solucionar un permiso.
3. En GitHub, **Settings → Secrets and variables → Actions → Variables → New repository variable**, crear
   `ESTADO_SUPABASE_ACTIVO` con valor literal `true`. Conservar `CAPTURA_HORARIA_ACTIVA=true` y los secretos Supabase existentes.
4. Habilitar únicamente **Captura horaria**, ejecutar manualmente desde `main` con `prueba=false` y esperar el resultado.
   Esta corrida importa el contador y los pendientes, sincroniza catálogo y reintenta tareas; no consume Apify ni genera
   una nueva selección. `prueba=true` sirve para una captura temporal, pero **no prueba la activación ni importa el estado**.
5. Revisar salud y las consultas del apartado siguiente. Si todo corresponde al corte, habilitar la nocturna y la profunda
   y observar la siguiente corrida diaria. Las reservas nuevas aparecerán cuando se solicite ejecutar un actor.

La clave REST de GitHub permite estas operaciones privadas una vez creadas. No permite instalar funciones/tablas SQL
arbitrarias: el paso del SQL Editor corresponde al administrador. No pegar claves en este manual, el chat o un PR.

Solo para una instalación **genuinamente nueva**, sin gasto previo ni contador que importar, el administrador puede
inicializar explícitamente en SQL Editor después de 003:

```sql
select public.operacion_inicializar(jsonb_build_object(
  'mes', to_char(now() at time zone 'America/Bogota','YYYY-MM'),
  'reservas', '{}'::jsonb
));
```

No usar esta excepción para sustituir memoria perdida de una instalación existente. En continuidad se importa el archivo
del corte automáticamente. Las importaciones posteriores preservan el mayor total conocido sin duplicar las reservas
centrales ya reflejadas en la copia de trabajo.

## 5. Cómo comprobarlo sin conocer programación

En Actions, el flujo debe terminar bien. En `datos/salud.json` del resultado buscar `estado_operativo.activo: true` y
`pendientes` en cero. En la pestaña **Estado** de la página se muestra la confirmación o el trabajo por recuperar.
Un reporte anterior o una página sin desplegar no acredita activación; comparar SHA/ejecución/hora del dato.

En SQL Editor, estas lecturas no modifican datos:

```sql
-- La marca debe existir después de importar/inicializar.
select cola, identificador, revision from public.estado_operativo where cola='control';
-- Las tareas se retiran solo al confirmarse; no confundir esto con borrar vacantes.
select cola, count(*) as pendientes from public.estado_operativo where cola<>'control' group by cola;
-- Reservas conservadoras del proyecto, no costos facturados por el proveedor.
select fecha, origen, sum(micro_usd)/1000000.0 as reservado_usd
from public.apify_reservas group by fecha, origen order by fecha desc, origen;
select public.apify_estado();
```

Si hay pendientes, revisar el error y reintentar tras corregir la causa; no vaciar tablas/archivos. Si hay conflicto,
la siguiente ejecución debe releer las revisiones. No reintentar automáticamente una llamada pagada de resultado dudoso.
Si falla el arranque por presupuesto inicial ausente, recuperar el corte: no asumir que hay USD 5 disponibles.

## 6. Qué se probó y qué falta observar en la cuenta real

Se prueban cortes de red, respuestas incompletas, conservación de copias, recuperación del lote y colas, esquema ausente
y captura horaria sin nueva entrega ni Apify. En PostgreSQL 17 aislado se aplica 003 dos veces, se comprueban permisos,
importación sin reiniciar/doblar crédito, topes, lotes inmutables, confirmaciones antiguas y rollback de un lote conflictivo.
Se lanzan reservas y actualizaciones concurrentes desde procesos independientes. Se respalda/restaura en otra base vacía
con cinco tablas y dos secuencias, comparando contenido, presupuesto, pendientes, permisos y nuevas identidades.

Estas pruebas no ejecutan actores pagados ni usan la base del cliente. La aceptación productiva requiere observar la
importación real, siguiente reserva y entrega, página y ausencia de pendientes. No acredita siete días de continuidad.

La cola de catálogo contiene descripciones y puede crecer temporalmente durante una carga completa. Medir bytes/tamaño
de las cinco tablas con índices, latencia y cuotas reales antes y después de activar; no inferir capacidad por contar filas.
La sincronización que reenvía todo el catálogo sigue pendiente de optimización. Este cambio añade persistencia, no un
monitor externo ni respaldos automáticos. Acordar esos dos controles antes de WhatsApp.

## 7. Recuperar o regresar de versión

Una vez aplicado 003, el respaldo completo incluye **cinco tablas y dos secuencias**, aunque la variable esté apagada.
Conservar también `trabajo/`: quedan allí rotación, inventario, verificaciones y métricas. Restaurar un mismo corte,
con flujos detenidos y las tres migraciones preparadas en destino vacío; seguir el manual de operación.

No apagar la variable ni regresar a código antiguo como arreglo rápido: ese código puede reservar desde una copia
local atrasada. Primero pausar escritores, guardar respaldo y exportar/comprobar reservas, lotes y colas actuales.
Un técnico prepara el regreso y valida equivalencia del corte antes de reabrir. No borrar 003 ni su historial para volver.
