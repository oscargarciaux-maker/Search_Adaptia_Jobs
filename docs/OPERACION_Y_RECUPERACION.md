# Operación, mantenimiento y recuperación

Manual del administrador, actualizado para la revisión v6 del 6 de noviembre de 2026. Complementa la [guía del operador](GUIA_CLIENTE.md).
No modifica la instalación por leerlo. Registrar incidentes y respaldos fuera del repositorio, sin incluir secretos.
La extensión de [estado operativo](ACTIVAR_ESTADO_OPERATIVO.md) centraliza reservas/pendientes solo tras SQL 003 y
`ESTADO_SUPABASE_ACTIVO=true`. Los procedimientos distinguen modo legado y central; no asumir activación por tener código.
El camino preferido es [instalación automática](INSTALACION_AUTOMATICA.md): aplica SQL e importa/activa mediante una
marca privada, sin esa variable manual. Incluye respaldo cifrado subido antes de cambios y diario `adaptia_migraciones`.
La preparación comparte la exclusión de las capturas; en este camino no hay que pausar y copiar SQL en cada actualización.

El control privado se opera según [PANEL_CONTROL.md](PANEL_CONTROL.md). Vigilar revisión efectiva, estado de ejecución y
faltantes por cargo. No copiar clientes/perfiles a la rama publicado. Las asignaciones mantienen filtros/cargo de su
versión; la interfaz revalida contra el catálogo actual. Los respaldos con SQL 009 incluyen las cuatro tablas del panel,
además de las siete anteriores. Auth del proveedor se gestiona aparte. No abrir el servidor real mientras login esté pendiente.

## 1. Qué comprobar cada día

**Desde el 28 nov (P-13.1) lo diario lo hace el «Vigía de avisos»** (`vigia.yml`, `buscador/vigia.py`): si no te llega
un correo, no hay nada que hacer. Una vez al día (lo pide el Reloj desde las 10:30 de Bogotá; el horario de las 10:40
es su respaldo) mira, sin buscar nada ni escribir en la base:

| Qué mira | Cuándo avisa |
|---|---|
| Bodega nocturna, Captura horaria, Reloj y Copia semanal en `main` | La última terminó en rojo (Captura: 2 seguidas; Reloj: 3), lleva demasiado sin terminar bien (Bodega 30 h, Captura 6 h, Reloj 3 h, Copia 8 días) o el flujo está desactivado (p. ej. por los 60 días sin actividad) |
| Tamaño de la base (`pg_database_size`) | 80 % de 500 MB (aviso) y 95 % (urgente) |
| Copias en el bucket `respaldos` | 80 % y 95 % de 1 GB |
| Archivo más grande de la rama `publicado` | 80 % y 95 % de los 100 MB por archivo de GitHub |
| Días sin commits en `main` | 30 días (urgente a los 50): GitHub apaga los horarios de un repo público a los 60 |
| `datos/caducidades.yaml` | Fin de soporte 180 días antes; claves 30 días antes; urgente si ya caducó |
| Algo que no pudo medir | Siempre («No se pudo comprobar…»): sin medir nadie vigila |

Cada aviso es una frase fija con **un solo paso** («Entra en X y pulsa Y» o «Reenvía este correo a soporte técnico»).
El texto sale a Healthchecks, un servicio externo: solo lleva frases de la lista blanca de `buscador/vigia.py`, cifras
enteras, fechas y el texto revisado de `datos/caducidades.yaml`; nunca clientes, lugares, cargos, mensajes de error ni
claves. El mismo texto queda en el resumen de la corrida (Actions → Vigía de avisos).

### Activar el Vigía (una vez, unos 10 minutos)

1. Entra en healthchecks.io con la cuenta de avisos (la del correo de la persona que atenderá los problemas; ver
   [ENTREGA_AL_CLIENTE.md](ENTREGA_AL_CLIENTE.md) §4). Si no existe, créala: el plan gratuito basta.
2. Pulsa **Add Check**. Nombre: `Atención`. En **Schedule** pon *Period* `1 day` y *Grace Time* `12 hours` (GitHub
   puede retrasar el horario de respaldo). Guarda.
3. Copia la **Ping URL** del check (empieza por `https://hc-ping.com/`).
4. En GitHub: Settings → Secrets and variables → Actions → **New repository secret**. Nombre `AVISO_ATENCION_URL`,
   valor la URL del paso 3. Guarda.
5. En GitHub: Actions → **Vigía de avisos** → **Run workflow**. En Healthchecks el check pasa a verde («up») o a rojo
   («down») con el texto de los avisos en **Events**.
6. En Healthchecks → **Integrations**, comprueba que el correo está activo y pulsa **Test** para ver que llega.

Cómo se comporta: Healthchecks manda un correo cuando el check pasa a rojo (hay avisos, o el Vigía no corrió en
36 horas) y otro cuando vuelve a verde. Si los mismos avisos siguen al día siguiente (aunque cambie la cifra) no se
repite el correo; si aparece uno **nuevo** mientras el check ya estaba en rojo, el Vigía lo pone un instante en verde y
otra vez en rojo para que llegue otro correo (guarda solo una huella de qué avisos había, en la caché de Actions). Por
eso pueden llegar dos correos seguidos («up» y «down»): el que importa es el último, con la lista completa. El texto del
día está también en el check (**Events**) y en el resumen de la corrida. Sin el secreto el Vigía corre igual y lo dice
en el registro, pero no avisa a nadie. Entra en Healthchecks al menos una vez al año: según su FAQ, las cuentas
inactivas se pueden borrar.

Requisitos para que no avise en falso: el Reloj activado (`docs/ACTIVAR_RELOJ.md`) y la copia semanal funcionando
(`SUPABASE_BACKUP_KEY`); si no, el Vigía avisará de que llevan días sin terminar bien, que es cierto. En la Bodega, los
horarios de respaldo terminan en verde sin trabajar cuando la de la mañana ya publicó: por eso un rojo de las últimas
24 horas solo se da por resuelto con una búsqueda pedida que terminó bien después («Buscar ahora» o la del Reloj).

Para añadir una fecha que caduca (otra clave, otra versión) se edita `datos/caducidades.yaml` (solo nombre, fecha y
un paso; nunca el valor de una clave). Para quitar el aviso de los días sin commits basta un commit en `main`: el
propio aviso explica cómo hacerlo desde la web cambiando la fecha `revisado` de ese archivo.

### Revisión a mano (si hace falta mirar más a fondo)

1. **Pruebas**: comprobar las del commit de `main` que se desplegó. Un test verde prueba ese código con sus fixtures;
   no prueba que la captura de hoy se haya ejecutado.
2. **Bodega nocturna**: abrir la ejecución real, leer resumen y comprobar selección por los cargos de la versión activa (seis en legado), faltantes,
   sincronización histórica, catálogo y registro de selección. `prueba=true` no acredita escritura.
3. **Captura horaria**: comprobar que hubo un trabajo ejecutado, no omitido, y que el paso final de catálogo terminó.
4. **Reporte y base**: comparar la hora de `publicado/datos/salud.json` con la última captura y las vistas de Supabase.
5. **Calidad**: revisar estados y hora de enlaces de la selección del día. La selección histórica puede seguir en 120
   mientras una parte cerró después o está pendiente; no compartir por esa cifra sin mirar el estado actual.
6. Abrir al menos una muestra de cada rol y revisar cargo afín, residencia, idioma y acceso a postulación.
7. Revisar el saldo de Apify. El monitor es el Vigía de arriba más los tres checks de Healthchecks de cada tarea; no
   hay guardia ni un SLA de respuesta automático.

La captura solicita ejecución horaria, no entrega una garantía de latencia de una hora. En el diagnóstico de preparación,
una captura/ofertas sin observación reciente en dos horas no pasan el criterio; es un umbral de revisión del piloto,
no una garantía contractual del proveedor. Abrir una incidencia si hay retrasos repetidos y conservar evidencia.

## 2. Inventario y significado de los datos

| Almacenamiento | Qué contiene | Cómo se utiliza |
|---|---|---|
| `catalogo_vacantes` | Vacante canónica, descripción, tiempos, estado y JSON público | Referencia actual e historial; puede estar activa, cerrada o archivada |
| `entregas_diarias` | ID, día, rol, grado y snapshot de selección | Reconstrucción de lote/no repetición; no representa envío a una persona |
| `ofertas` | Una fila por vacante reconocida tras SQL 005 | Compatible con v1 y extras v5; `active` no certifica vigencia actual |
| `ofertas_enlaces_historicos` | Copias por URL archivadas con fila original completa e ID principal | Conservación, auditoría y recuperación; no cuentan como otras vacantes |
| `entrega_de_hoy` | Vista de la fecha máxima existente en `ofertas` | Puede mostrar un día anterior; no tiene almacenamiento propio |
| `seleccion_estado_actual` | Vista privada que cruza selección con catálogo, rol vigente y enlaces | `estado_actual=lista` exige enlace de la ficha con menos de seis horas; no usar `ofertas.active` para enviar |
| `resumen_entregas_actual` | Vista privada por fecha/rol | Distingue seleccionadas, listas ahora, pendientes, retiradas y afinidad por revisar; no cuenta filas v1 como ofertas |
| `publicado/trabajo/` | Bodega, caché de enlaces, presupuesto y métricas del día **sin detalle por cargo** (27 nov) | Continuar ejecuciones; `estado_privado.json` dice qué parte está en Supabase |
| `estado_trabajo` (SQL 022) | Privada: lote del día, vacantes ya entregadas, rotación con claves cargo@país, colas, métricas por cargo, reporte completo y a qué cargo va cada vacante de la bodega (`buscador/estado_privado.py`) | La siguiente corrida la repone tras clonar `publicado`; si la marca existe y falta, no arranca. Grupo `fallida`: copia de la última corrida que falló, solo para diagnóstico |
| Supabase con SQL 003 | `estado_operativo` y `apify_reservas` privados | Autoridad de pendientes/reservas en modo central; archivos de trabajo auxiliares |
| `adaptia_migraciones` | Versión, nombre, hash y fecha; acceso administrativo | Evita repetir o modificar migraciones ya aplicadas; incluir en respaldos automáticos |
| `publicado/datos/` | Reporte técnico de salud, solo cifras agregadas (totales, por fuente, por idioma, COMPLETA/CORTA/AVERÍA) | Foto de la captura; el reporte completo está en `estado_trabajo` |

Cerrar significa evidencia de cierre; archivar puede deberse a antigüedad, fusión o enlace rechazado. Retirar del
buscador no elimina registros en Supabase. Los 30 días son ventana activa, no retención máxima de la base.

No repetición: el archivo local tiene ventana de 180 días; con v2 activo también se recuperan identidades y URLs del
registro Supabase y del histórico v1. Conservar la memoria y las tablas. No describir un reinicio vacío como si fuera
una continuación sin duplicados.

## 3. Qué significa un resultado verde o rojo

- **Verde en Pruebas:** pasaron Python/SQL de ese commit; SQL se prueba en PostgreSQL temporal.
- **Verde en captura real:** revisar que no se hayan omitido los pasos y leer sus métricas. No equivale a verificación
  de todas las fuentes, de cada enlace del inventario ni de autenticidad de empresas.
- **Rojo en validación al final:** puede haberse guardado ya catálogo/colas. Averiguar qué falta antes de repetir.
  Desde el contrato v52 el déficit ya no pone la corrida en rojo (estado CORTA: verde con avisos); el rojo es una
  avería. Un día corto tampoco significa que deban borrarse las ofertas válidas.
- **Pendiente/queued:** espera un runner o el grupo de publicación. No lanzar copias para forzar otra cola.

Los trabajos comparten un grupo de publicación para evitar escrituras simultáneas. GitHub puede reemplazar trabajos
pendientes, retrasar o perder horarios; no se utiliza como una cola con conservación garantizada de todos los disparos.

## 4. Resolver incidentes por síntoma

| Síntoma | Revisar primero | Acción segura |
|---|---|---|
| No apareció la captura a la hora solicitada | Actions, habilitación del workflow, cola y avisos de GitHub | Esperar si está en curso; investigar retraso; reejecutar una sola vez si procede |
| La búsqueda arranca por la tarde o la captura no corre cada hora (desde el 17 nov GitHub dispara los horarios cada 8 a 12 horas) | Actions > Reloj: ¿hay una corrida esperando («Waiting»)? | Si no está activado, seguir [ACTIVAR_RELOJ.md](ACTIVAR_RELOJ.md) (contrato v51). Si la cadena se cortó, se reanuda sola con la siguiente búsqueda o con «Buscar ahora»; para no esperar, Actions > Reloj > Run workflow. El Reloj no repite una búsqueda que falló: revisar el fallo y usar «Buscar ahora» |
| No corrió la búsqueda de las 6:30 (GitHub no lanzó el horario; pasó el 18 nov) | Actions > Bodega nocturna: ¿hay una corrida de hoy? | Nada en la mayoría de los casos: la hace el primero que arranque entre el respaldo de las 7:15, la «Captura horaria» desde las 7:23 (trabajo «vigia», una vez al día) y el respaldo de las 7:50; los demás terminan sin hacer nada y sin aviso. Si no corrió ninguna captura horaria, GitHub no está lanzando nada: pulsar «Buscar ahora» en el Resumen del panel (o en GitHub: Run workflow, modo diario). Para no buscar un día, desactivar el flujo: cancelar una corrida no basta, porque los respaldos la vuelven a hacer |
| Falta catálogo v2 / vistas actuales | Tablas, Project URL y permisos del mismo proyecto | Revisar Preparar Supabase y su respaldo; el instalador aplica migraciones pendientes. No desactivar integridad ni crear tablas aproximadas |
| Error 401/403 Supabase | Tipo de clave, vigencia y proyecto | Sustituir secreto por secret/service_role de la cuenta correcta; no publicarlo |
| Tablas existen pero API no accede | Grants, RLS y recarga de esquema | Revisar scripts completos; no abrir permisos anon para hacer funcionar el scraper |
| Pendientes de sincronización | Tipo de cola y último HTTP/permiso | Corregir causa y reintentar con memoria intacta; conservar fecha e ID |
| Filas v1 de hoy sin registro ni lote recuperable | Artefacto/estado del mismo corte y `entregas_diarias` | Recuperar el lote y completar su registro; el arranque se detiene antes de buscar para no escoger otra entrega |
| Un cargo no alcanza su cupo | Motivos, descripción, enlaces, país, no repetición y máximo por empresa | Revisar refuerzos/fuentes/alias; no rellenar con pendientes, repeticiones o cargos ajenos |
| La selección histórica contiene enlaces fallidos | Reporte actual de verificación | No reenviar esas ofertas; conservar snapshot, revisar casos y esperar nuevas oportunidades |
| Muchos 403/429/CAPTCHA de un portal | Salud de esa fuente, otros orígenes y frecuencia | Dejarlos pendientes; no declararlos cerrados, aumentar agresividad ni pedir una cookie personal |
| Se detectó cobro o página general | URL y destino final, motivo y hora | Apartar, revisar original y documentar; no pagar para comprobar ni enviar formularios |
| Apify aparece omitido | Cuota reservada, token, actor y crédito real | Si es por límite, esperar el período o usar fuentes gratuitas; no borrar reservas |
| Dice «Publicaciones LinkedIn omitida» pero formal funciona | `publicaciones_por_dia=0` y bloque LinkedIn Apify | Es lo esperado: presupuesto reservado a fichas formales |
| Capacidad Supabase o minutos Actions agotados | Uso/tamaño real y plan | Respaldar, acordar capacidad/frecuencia; archivar no libera automáticamente espacio |

Para soporte guardar: enlace/ID de ejecución, commit, fecha/hora Colombia, rol afectado, URL problemática, último paso,
cantidad de pendientes y mensaje de error sanitizado. No copiar variables de entorno ni cabeceras de autorización.

## 5. Diagnósticos y acciones manuales

SQL 006 conserva la identidad y archivo definidos en 005, pero resuelve las cadenas de IDs una sola vez para todo
el catálogo. Evita miles de consultas internas repetidas que pueden exceder el límite de tiempo de la API.
El preparador la aplica y reconcilia después del respaldo, sin SQL manual. Un código `57014` indica que la base
canceló la consulta por tiempo; conservar el estado, no confundirlo con una captura vacía ni borrar reservas/colas.

SQL 007 permite equivalencias recíprocas de aliases, sin aceptar referencias explícitas contradictorias. Si la
preparación de 006 se detuvo por esos aliases, el instalador los ordena dentro de su transacción respaldada y continúa.
Los registros y snapshots históricos se conservan. Los errores SQL muestran código y categoría, nunca filas o URI.

SQL 008 añade índices de URLs normalizadas para consultar únicamente las fichas relacionadas con las ofertas
operativas. Conserva las reglas de identidad, ambigüedad, archivo y referencias; no desactiva la validación. Los índices
se actualizan con las escrituras del catálogo y selección; no necesitan una tarea de refresco. Se crean sin lista de
inserciones diferidas para que las consultas posteriores a una captura masiva no la recorran repetidamente.

Un fallo final por `57014` puede ocurrir después de guardar el catálogo: consultar `catalogo.filas/enviadas/pendientes`
y el detalle de `identidad` en salud.json. No deducir pérdida de ofertas ni cambiar contraseñas por ese código.
SQL 010 corrige el recorrido de relaciones que todavía podía agotar tiempo con 008: extrae metadatos una vez,
resuelve por clave y evita reescrituras sin cambios. Conserva validación, archivo, referencias y los índices de URLs.
No requiere contraseñas nuevas ni SQL manual; se instala tras respaldo con el mecanismo automático existente.

El diagnóstico mide primero la función instalada bajo un límite de tres segundos en una transacción revertida.
Solo imprime conteos, duración, código y etapa reconocida; nunca el contexto SQL completo ni filas privadas.
Después ensaya las migraciones permitidas y vuelve a medir como service_role. Todo el ensayo se revierte; un
resultado favorable acredita la prueba, no instalación. Comprobar Preparar Supabase y la siguiente captura real.

En **Actions → Diagnóstico → Run workflow**, rama `main`:

- `ensayar_migraciones=true`: ensayo del SQL de identidad pendiente (006/007/008/009/010) con reversión obligatoria de toda la transacción. No instala
  versiones ni conserva reparaciones. Tiene prioridad sobre los demás modos y no consume Apify. No reemplaza al
  preparador con respaldo. Espera como máximo tres segundos por un bloqueo y treinta por consulta.


- `auditar_producto=true`: consulta de solo lectura con conteos de la última fecha por `search_tag`/`role_id`,
  muestra pública acotada de QA y estado de una URL opcional en `vacante_url`. No escribe, migra ni usa Apify.
  Tiene prioridad sobre las otras opciones salvo el ensayo de migraciones y la consolidación. Comparar fechas, no solo el nombre del rol.

- `solo_conexion_db=true`: comprobar específicamente el acceso PostgreSQL administrativo en solo lectura. No aplica
  migraciones ni usa Apify; tiene prioridad sobre las otras opciones. Distingue configuración, autenticación, red y TLS
  con categorías seguras. Una conexión directa sin ruta IPv6 requiere elegir Session pooler 5432; un fallo de certificado
  exige corregir servidor/certificado, conservando su verificación. No cambiar contraseñas sin evidencia del diagnóstico.

- `solo_supabase=true`, `probar_apify=false`: lee conexión/esquema v1, sin crear ofertas. No prueba escritura ni todo v2.
- Ambos `false`: diagnóstico de configuración/fuentes, consulta de cuenta Apify.
  No ejecuta el actor Apify. Que aparezca una fuente opcional omitida no es un fallo de Supabase.
- `probar_apify=true`: una ejecución explícita de una oferta con límite USD 0,01, sin guardado Supabase. Sí consume
  crédito de la cuenta; no se incluye como una reserva normal del programa.

En una captura, `prueba=true` no guarda ofertas ni actualiza la rama; no sirve para probar cuota/escritura productiva.
**Búsqueda profunda** no tiene ese parámetro de prueba y puede consumir Apify. No repetirla sin revisar el estado del presupuesto.

Un técnico, desde el código aprobado con Python 3.12 y dependencias instaladas, puede revisar solo reportes:

```bash
# Elegir una carpeta nueva, fuera del repositorio de código. La lectura de un repo privado requiere acceso propio.
git clone --depth 1 --branch publicado https://github.com/CLIENTE/REPOSITORIO.git /tmp/adaptia-estado
python -m buscador.validacion --salida /tmp/adaptia-estado --catalogo
python -m buscador.validacion --salida /tmp/adaptia-estado
python -m buscador.preparacion --salida /tmp/adaptia-estado
```

El primer comando de validación comprueba sincronización de catálogo; el segundo también selección/sincronización diaria;
el tercero combina siete fechas distintas, registro, comprobación de enlaces y frescura. No inicia una captura ni
certifica pagos ocultos, autenticidad o recepción de mensajes. Si el lote es de ayer, no interpretarlo como el de hoy.

Auditoría de enlaces del lote, solo lectura y sin Apify:

```bash
python -m buscador.verificar_enlaces --lote /tmp/adaptia-estado/trabajo/lote_entrega.json --salida /tmp/adaptia-auditoria.json --maximo 120
```

Revisar una URL puede bloquearse aunque abra en el navegador. El resultado JSON puede incluir parámetros temporales
del portal; compartir solo los motivos y URLs originales necesarios. No subir el volcado completo a soporte público.

## 6. Consultas administrativas de comprobación

Ejecutar en **Supabase → SQL Editor**, en el proyecto correcto. Son lecturas; no certifican que todos los enlaces sigan abiertos.

```sql
-- Las tres tablas base; aparecen también las dos nuevas si se aplicó 003.
select table_name from information_schema.tables
where table_schema='public' and table_name in ('ofertas','catalogo_vacantes','entregas_diarias','estado_operativo','apify_reservas');

-- Selecciones distintas por rol y día. Elegir después la fecha de negocio que se está revisando.
select delivery_date, role_id, count(*) as seleccionadas
from public.entregas_diarias group by 1,2 order by 1 desc,2;

-- Estado actual; no confundirlo con el active histórico de ofertas.
select status, coalesce(datos->'verificacion'->>'estado','sin evidencia') as verificacion, count(*)
from public.catalogo_vacantes group by 1,2 order by 1,2;

-- Pendientes/retiradas de la selección del día de Bogotá. Incluye comprobaciones positivas caducadas.
select d.role_id, d.vacante_id, c.status, c.datos->>'titulo' as titulo,
       c.datos->'verificacion'->>'estado' as verificacion,
       c.datos->'verificacion'->>'motivo' as motivo
from public.entregas_diarias d join public.catalogo_vacantes c on c.id=d.vacante_id
where d.delivery_date=(now() at time zone 'America/Bogota')::date
  and (c.status<>'active' or coalesce(c.datos->'verificacion'->>'estado','')<>'verificada'
       or nullif(c.datos->'verificacion'->>'comprobada_en','')::timestamptz is null
       or nullif(c.datos->'verificacion'->>'comprobada_en','')::timestamptz < now()-interval '6 hours');

-- Referencias: el resultado debe ser cero.
select count(*) as referencias_huerfanas from public.entregas_diarias d
left join public.catalogo_vacantes c on c.id=d.vacante_id where c.id is null;

-- Tamaños orientativos. Contrastar con el panel/límites reales del proveedor.
select pg_size_pretty(pg_database_size(current_database())) as base_completa;
select relname, pg_size_pretty(pg_total_relation_size(oid)) as total_con_indices
from pg_class where oid in ('public.ofertas'::regclass,'public.catalogo_vacantes'::regclass,'public.entregas_diarias'::regclass);

-- Seguridad pública prevista: RLS activo y permisos anon/authenticated ausentes.
select relname, relrowsecurity from pg_class
where oid in ('public.ofertas'::regclass,'public.catalogo_vacantes'::regclass,'public.entregas_diarias'::regclass);
select has_table_privilege('anon','public.catalogo_vacantes','SELECT') as anon_catalogo,
       has_table_privilege('authenticated','public.entregas_diarias','SELECT') as usuario_entregas;
```

Un nombre/JSON alterado manualmente puede requerir diagnóstico técnico. No arreglar un cast o permiso borrando tablas.

## 7. Mantenimiento y costos

**Semanal:** revisar déficit por rol, calidad por muestra, fuentes con fallos, colas, retrasos y consumo. Revisar el tamaño
de todas las tablas con índices (cinco tras 003) y las condiciones del plan Supabase. Si procede, acordar más capacidad o una estrategia
explícita de archivo/respaldos; cambiar un estado a archived no reduce espacio por sí solo.

**Mensual y al cambiar cuentas:** comprobar ciclo de crédito Apify, reservas, otros proyectos de la cuenta, permisos,
expiración de tokens, facturación de alojamiento y restauración de un respaldo. Revisar que el repositorio no quede
sin actividad de mantenimiento: GitHub puede deshabilitar cron en repositorios públicos inactivos según su política
(el Vigía avisa a los 30 días sin commits en `main` y si un flujo clave queda desactivado).

Los USD 5 limitan Apify del proyecto, no todos los servicios. En repositorio público las condiciones de Actions difieren
de uno privado; verificar plan actual. Como orden de magnitud, 24 capturas/día de 4,7 min son 3.384 min/mes, más unas
1.161 min por 30 nocturnas de 38,7 min, instalaciones y verificaciones. No asumir que cabe en 2.000 minutos privados.
Estos son cálculos con duraciones observadas, no una factura ni una duración garantizada.

No hay tarea implementada que elimine automáticamente el histórico Supabase ni una política de backup completo de la
base incluida en el código. Acordar con el cliente frecuencia, retención y responsable de respaldos. Propuesta inicial
para evaluar: copia diaria y antes de cambios, con recuperación probada; el administrador debe aprobar capacidad y ventana.

## 8. Respaldo completo y restauración comprobable

El instalador produce antes de cambios un corte cifrado de las tablas del proyecto, secuencias y `trabajo/`; la acción
debe guardarlo en Storage privado (tipo `instalacion`, ver abajo) antes de aplicar SQL: si no se puede guardar, no se
migra. Guardar la clave de cifrado fuera de GitHub. No incluye Auth, Storage ni otros
esquemas de Supabase. No sustituye una copia periódica ni la supervisión independiente del servicio.

El módulo `buscador.respaldo.restaurar` verifica AES-GCM antes de insertar; solo acepta tablas de negocio vacías y una
carpeta de trabajo nueva. Se prepara el esquema de la versión del corte antes de llamarlo. Se ensaya en CI con seis
tablas, dos secuencias, decimales exactos, permisos y trabajo; rechaza un cifrado alterado. El rescate real sigue siendo
una operación administrativa en destino aislado, con posterior contraste del consumo Apify.

Un respaldo de `trabajo/` no contiene la base. Una exportación de `ofertas` no contiene catálogo/selecciones ni reservas.
Necesita **ambas piezas del mismo corte** y, si se usa, KV/historial del operador. Consultar también las opciones vigentes
[de respaldo de Supabase](https://supabase.com/docs/guides/platform/backups); no asumir que el plan gratis conserva una
copia recuperable para el cliente.

### Respaldos guardados en Supabase Storage (desde el 27 nov)

Todas las copias cifradas de la base están en el bucket **privado** `respaldos` de Supabase Storage, en una carpeta
por tipo: `<tipo>/AAAA-MM-DD_<ejecución>/`, cada una con trozos `parte-000`, `parte-001`… y un `manifiesto.json`. Una
carpeta sin manifiesto es una subida a medias: no sirve. También se ven en el panel de Supabase: Storage > Buckets >
`respaldos` (no hacer público nunca ese bucket).

| Tipo | Cuándo se crea | En qué proyecto buscarlo | Quedan | Cuándo usarlo |
|---|---|---|---|---|
| `semanal` | domingos (`respaldo.yml`) | el actual | las 2 últimas | recuperar la base de una fecha |
| `instalacion` | antes de aplicar una migración (acción «Preparar Supabase») | el actual | la última | una migración dejó mal la base: volver a justo antes |
| `antes-de-limpiar` | antes de `limpiar_fuera_objetivo.yml` | el actual | todas | deshacer una limpieza |
| `traspaso` | al traspasar (`traspaso.yml`), antes de restaurar | el **destino** del traspaso | todas | el destino quedó mal después del traspaso y el Supabase antiguo ya no existe |

Si el traspaso falla, el origen no se toca ni se marca: sigue operando y no hace falta ninguna copia. Mientras el
Supabase antiguo exista, volver atrás es más simple con él que con la copia.

Para recuperar, en un equipo de confianza (no en Actions) con `SUPABASE_URL` y `SUPABASE_SECRET_KEY` del proyecto en el
entorno, sin escribirlos en la línea de órdenes ni en archivos del repositorio:

```bash
python -m buscador.almacen_respaldos listar --tipo semanal          # o instalacion, antes-de-limpiar, traspaso
python -m buscador.almacen_respaldos bajar --respaldo semanal/2026-11-30_123456789-respaldo-1 --salida /ruta/privada/copia.enc
```

Para `traspaso`, usar la URL y la Secret key del **destino** (después del traspaso ya son los `SUPABASE_URL` y
`SUPABASE_SECRET_KEY` de siempre).

`bajar` reúne los trozos y comprueba el sha256 de cada uno y del total. El `.enc` resultante es el mismo que crea
`buscador.respaldo.crear`: se restaura con la función `buscador.respaldo.restaurar` (no tiene línea de órdenes;
`traspaso.yml` NO sirve: hace un corte nuevo de la base actual) en un destino aislado vacío con el esquema ya preparado
y `SUPABASE_BACKUP_KEY`, siguiendo el ensayo de abajo. Si el resumen de la copia semanal avisa de que la
próxima copia podría no caber (el bucket más una copia nueva pasa de 800 MB), decidir esa misma semana entre pasar a
Pro o guardar menos copias (`CONSERVAR` en `buscador/almacen_respaldos.py`). Si se llega al 1 GB, la subida falla y
la poda no corre: borrar a mano en Storage la carpeta semanal más vieja con manifiesto (nunca la más nueva de cada
tipo) y relanzar. Si la que falla es la de «Preparar Supabase», la migración no se aplica y la captura queda en rojo
hasta liberar espacio y relanzar.

### Corte y respaldo

1. Deshabilitar los tres flujos que escriben y esperar los que estén en curso. Guardar los commits del corte.
2. Descargar/guardar completa la rama `publicado`, en especial `trabajo/` y `datos/salud.json`, fuera del repositorio.
   La rama se reescribe y no es por sí misma un histórico de recuperación. Actions guarda artefactos de estado 14 días,
   no una copia permanente ni el contenido de Supabase. Desde el 27 nov el detalle por cargo de `trabajo/` está en la
   tabla `estado_trabajo` (va en los respaldos cifrados): la rama sola ya no basta para recuperar el estado.
3. Si se aplicó 003, exportar cinco tablas y dos secuencias, aunque la variable aún no esté activa. Sin 003 hay tres
   tablas y una secuencia: omitir los argumentos de `estado_operativo`, `apify_reservas` y su secuencia en esta receta.
   Un técnico puede usar la receta siguiente, con cliente
   PostgreSQL compatible y acceso administrativo. Los servicios son perfiles de conexión seguros propios; no pegar
   contraseñas en argumentos ni en este manual. Ver [pg_service](https://www.postgresql.org/docs/current/libpq-pgservice.html).
   Con SQL 009 y el instalador hay once tablas. La receta siguiente incluye todas; para un esquema anterior omitir solo las inexistentes. Conservar sus
   hashes/fechas; no reinicializar el diario durante una restauración. La receta pg_dump es una alternativa técnica
   al corte cifrado, no una tarea diaria del operador.

```bash
# Directorio privado fuera del repositorio. Crear uno nuevo por corte y proteger sus archivos.
ADAPTIA_RESPALDO=/ruta/privada/al/respaldo-del-corte
pg_dump --dbname="service=adaptia_origen" --format=custom --data-only --no-owner --no-privileges \
  --table=public.catalogo_vacantes --table=public.entregas_diarias --table=public.ofertas \
  --table=public.estado_operativo --table=public.apify_reservas --table=public.estado_operativo_revision_seq \
  --table=public.ofertas_id_seq --table=public.ofertas_enlaces_historicos --table=public.adaptia_migraciones \
  --table=public.panel_configuracion --table=public.panel_versiones --table=public.panel_ejecuciones \
  --table=public.panel_asignaciones --file="$ADAPTIA_RESPALDO/datos.dump"
```

`adaptia_origen` referencia la conexión administrativa, TLS y credenciales fuera del código; el técnico prepara esos
perfiles según Supabase y su red. Verificar `pg_get_serial_sequence('public.ofertas','id')` si el esquema tiene un
nombre distinto al creado por el SQL del proyecto. Revisar la salida/exit code y un inventario con conteos, fechas,
estados, reservas, pendientes y ambas secuencias. Sin la secuencia de revisiones se puede reutilizar un recibo antiguo
tras restaurar. El respaldo puede contener descripciones/URLs; almacenarlo con acceso restringido, no en GitHub.

### Ensayo de restauración

4. Crear un destino aislado **vacío**, que no reciba clientes ni automatizaciones. Aplicar `esquema.sql` y
   `002_catalogo.sql` con sus permisos y `003_estado_operativo.sql` si el corte incluye esa extensión.
   No inicializar un marcador/presupuesto vacío antes de restaurar. No crear roles nuevos en Supabase: son roles del proveedor.
   Para un corte con diario de migraciones, preparar también esa tabla mediante `buscador.migraciones.DIARIO`, con
   conexión administrativa, sin ejecutar el paso de activación. El esquema debe corresponder a los SQL del corte.
5. Restaurar sin apuntar jamás al proyecto productivo por accidente:

```bash
pg_restore --dbname="service=adaptia_destino" --data-only --no-owner --no-privileges \
  --single-transaction --exit-on-error "$ADAPTIA_RESPALDO/datos.dump"
```

6. Comparar conteos/IDs/fechas/snapshots, estados cerrados/archivados, referencias, reservas, pendientes y secuencias. Confirmar
   RLS/grants después de aplicar el esquema. Probar una inserción ficticia en ese destino y retirarlo al terminar el ensayo.
7. Verificar también que la copia de `trabajo/` conserva colas, lote, memoria y presupuesto del corte. No rejuvenecer
   fechas de verificación al copiar. Registrar quién ensayó, fecha, resultados y ubicación del respaldo.

La receta de cinco tablas/dos secuencias se ensayó con datos ficticios en PostgreSQL 17: contenido, clave foránea, cierre,
presupuesto, pendiente, permisos, siguiente identidad y revisión se conservaron. Se repite en CI. No equivale a restaurar el proyecto real del cliente ni certifica sus
credenciales/red. Si hay otras tablas de negocio, extensiones o un esquema modificado, ajustar y ensayar su respaldo.

### Recuperar producción después de un incidente

8. Elegir el corte que corresponde al estado de negocio. Mantener los flujos detenidos mientras se restaura o cambia
   el proyecto. No mezclar pendientes de una base con una restauración vacía de otra fecha.
9. Si se recupera `trabajo/`, un técnico hace una copia de la rama `publicado` fuera de `main`, respalda su carpeta de
   trabajo actual y sustituye **la carpeta completa** por la del corte, sin mezclar archivos sueltos. Revisa el diff,
   registra un commit solo con el estado previsto y actualiza `publicado` durante la ventana acordada.
10. Configurar las credenciales del destino correcto, validar la lectura y hacer una prueba aislada. Después realizar
    una captura real con memoria conservada, verificar pendientes y desplegar. No ejecutar dos instancias simultáneas.
11. Reabrir el servicio cuando se haya completado la aceptación mínima. Conservar evidencia del incidente y el corte.

### Estado privado en Supabase (`estado_trabajo`, 27 nov)

- **Una corrida se detiene con «el estado privado está en Supabase, pero no se puede leer» o «incompleto o mezclado».**
  No se busca ni se elige nada, a propósito: seguir sin el lote ni lo ya entregado repetiría vacantes. Revisar que
  `SUPABASE_URL` y `SUPABASE_SECRET_KEY` sean del mismo proyecto que guardó el estado y que exista la tabla
  `estado_trabajo` (la instala «Preparar Supabase», SQL 022). Si el proyecto se restauró de un respaldo cifrado, la
  tabla viene en él. Si el estado se perdió de verdad, un técnico reconstruye `trabajo/` desde el último artefacto o
  respaldo y quita `trabajo/estado_privado.json` de la rama `publicado` en la ventana acordada (entonces la corrida usa
  lo que trae la rama); el lote del día se recupera además desde `entregas_diarias`.
- **«Aviso: el estado privado es de una corrida posterior a la rama publicado».** Falló la publicación después de
  guardar el estado: se usa el de Supabase, que es el más reciente. No requiere acción si la siguiente publica.
- **Una corrida que falló** guarda su estado aparte (grupo `fallida`), solo para diagnóstico; la siguiente sigue con
  el estado vigente anterior, como antes de este cambio.
- **Revertir este cambio (volver a publicar todo en la rama).** El código anterior no sabe leer Supabase: antes de
  revertir, en una copia de la rama `publicado`, ejecutar `python -m buscador.estado_privado traer --salida <copia>`
  con los secretos del proyecto, borrar `trabajo/estado_privado.json` y publicar esa carpeta completa. Sin ese paso,
  la primera corrida arrancaría sin lote ni entregadas y elegiría otra entrega del día.
- **Instalaciones en modo manual** (sin `SUPABASE_DB_URL`): hay que aplicar `supabase/migraciones/022_estado_trabajo.sql`
  a mano antes de la primera corrida con este cambio; sin la tabla, `guardar` falla y la rama no se publica.

La recuperación puede necesitar decisión humana si Supabase confirmó filas y se perdió una cola antes de publicarla.
V2 ayuda a reconstruir selección/no repetición, pero no restaura saldo ni reservas del proveedor. No garantizar que todo
se recupera automáticamente ni borrar filas para forzar otro resultado.
Con modo central activo, SQL 003 conserva las reservas y los pendientes confirmados en esa base y permite reconstruir
colas desde los lotes interrumpidos, también de días anteriores. Todavía se necesita el respaldo de `trabajo/` (la
rama) y de `estado_trabajo` (la base) para rotación, inventario, caché de enlaces y métricas: deben ser del mismo corte. Una restauración vieja puede omitir consumo posterior al corte:
contrastar Apify antes de reanudar; un backup viejo no repone crédito real. No apagar la variable como recuperación rápida.

## 9. Actualizaciones y regreso de versión

Trabajar en rama y PR, ejecutar pruebas, revisar contrato y migraciones y respaldar antes de cambios de datos.
Después de fusionar verificar la siguiente captura y las vistas de Supabase, no solo el CI. Para regresar código, un técnico prepara
un revert revisable y pasa pruebas; no borrar tablas v2/v3 ni historia por regresar interfaz. Una versión anterior puede
carecer de controles nuevos: no usarla como una solución permanente que vuelva a compartir enlaces sin comprobar.

## 10. Evidencia de preparación

Completar [ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md). Una captura o los tests no garantizan ausencia total de fallos.
La operación estable se demuestra con días distintos, calidad revisada, recuperación realista, costos observados y un
responsable que pueda resolver incidencias. WhatsApp sigue siendo una etapa posterior con su propio registro por destinatario.
