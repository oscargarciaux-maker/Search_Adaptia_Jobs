# Operación, mantenimiento y recuperación

Manual del administrador, actualizado el 5 de noviembre de 2026. Complementa la [guía del operador](GUIA_CLIENTE.md).
No modifica la instalación por leerlo. Registrar incidentes y respaldos fuera del repositorio, sin incluir secretos.

## 1. Qué comprobar cada día

1. **Pruebas**: comprobar las del commit de `main` que se desplegó. Un test verde prueba ese código con sus fixtures;
   no prueba que la captura de hoy se haya ejecutado.
2. **Bodega nocturna**: abrir la ejecución real, leer resumen y comprobar selección por los seis roles, faltantes,
   sincronización histórica, catálogo y registro de selección. `prueba=true` no acredita escritura.
3. **Captura horaria**: comprobar que hubo un trabajo ejecutado, no omitido, y que el paso final de catálogo terminó.
4. **Actualizar página** o despliegue Cloudflare: comparar la hora real del dato con la rama `publicado`.
5. **Calidad**: revisar estados y hora de enlaces de la selección del día. La selección histórica puede seguir en 120
   mientras una parte cerró después o está pendiente; no compartir por esa cifra sin mirar el estado actual.
6. Abrir al menos una muestra de cada rol y revisar cargo afín, residencia, idioma y acceso a postulación.
7. Revisar avisos/notificaciones GitHub y saldo Apify. Configurar las notificaciones con el responsable; este proyecto
   no incluye un monitor externo, guardia ni un SLA de respuesta automático.

La captura solicita ejecución horaria, no entrega una garantía de latencia de una hora. En el diagnóstico de preparación,
una captura/ofertas sin observación reciente en dos horas no pasan el criterio; es un umbral de revisión del piloto,
no una garantía contractual del proveedor. Abrir una incidencia si hay retrasos repetidos y conservar evidencia.

## 2. Inventario y significado de los datos

| Almacenamiento | Qué contiene | Cómo se utiliza |
|---|---|---|
| `catalogo_vacantes` | Vacante canónica, descripción, tiempos, estado y JSON público | Referencia actual e historial; puede estar activa, cerrada o archivada |
| `entregas_diarias` | ID, día, rol, grado y snapshot de selección | Reconstrucción de lote/no repetición; no representa envío a una persona |
| `ofertas` | Filas v1 por enlace seleccionado | Compatibilidad e histórico; `active` no certifica vigencia actual |
| `entrega_de_hoy` | Vista de la fecha máxima existente en `ofertas` | Puede mostrar un día anterior; no tiene almacenamiento propio |
| `publicado/trabajo/` | Estado de búsqueda, memoria, colas, presupuesto y caché | Continuar ejecuciones y recuperar pendientes |
| `publicado/datos/` | Datos públicos de la página y reporte de salud | Consulta de la interfaz; no sustituye a Supabase |
| Navegador o Cloudflare KV | Marcas manuales de enviadas | Historial del operador, sin destinatario ni comprobante WhatsApp |

Cerrar significa evidencia de cierre; archivar puede deberse a antigüedad, fusión o enlace rechazado. Retirar del
buscador no elimina registros en Supabase. Los 30 días son ventana activa, no retención máxima de la base.

No repetición: el archivo local tiene ventana de 180 días; con v2 activo también se recuperan identidades y URLs del
registro Supabase y del histórico v1. Conservar la memoria y las tablas. No describir un reinicio vacío como si fuera
una continuación sin duplicados.

## 3. Qué significa un resultado verde o rojo

- **Verde en Pruebas:** pasaron Python/JavaScript/SQL de ese commit; SQL se prueba en PostgreSQL temporal.
- **Verde en captura real:** revisar que no se hayan omitido los pasos y leer sus métricas. No equivale a verificación
  de todas las fuentes, de cada enlace del inventario ni de autenticidad de empresas.
- **Rojo en validación al final:** puede haberse guardado ya catálogo/colas. Averiguar qué falta antes de repetir.
  Un fallo por déficit no significa que deban borrarse las ofertas válidas.
- **Verde en despliegue:** se sirvieron archivos disponibles; pueden ser los datos anteriores si la captura falló antes.
- **Pendiente/queued:** espera un runner o el grupo de publicación. No lanzar copias para forzar otra cola.

Los trabajos comparten un grupo de publicación para evitar escrituras simultáneas. GitHub puede reemplazar trabajos
pendientes, retrasar o perder horarios; no se utiliza como una cola con conservación garantizada de todos los disparos.

## 4. Resolver incidentes por síntoma

| Síntoma | Revisar primero | Acción segura |
|---|---|---|
| No apareció la captura a la hora solicitada | Actions, habilitación del workflow, cola y avisos de GitHub | Esperar si está en curso; investigar retraso; reejecutar una sola vez si procede |
| Falta catálogo v2 / `002_catalogo.sql` | Tablas, Project URL y permisos de servicio del mismo proyecto | Aplicar el SQL administrativo correcto; no desactivar integridad ni crear tablas con nombres aproximados |
| Error 401/403 Supabase | Tipo de clave, vigencia y proyecto | Sustituir secreto por secret/service_role de la cuenta correcta; no publicarlo |
| Tablas existen pero API no accede | Grants, RLS y recarga de esquema | Revisar scripts completos; no abrir permisos anon para hacer funcionar el scraper |
| Pendientes de sincronización | Tipo de cola y último HTTP/permiso | Corregir causa y reintentar con memoria intacta; conservar fecha e ID |
| Hay menos de 20 en un rol | Motivos, descripción, enlaces, país, no repetición y máximo por empresa | Revisar refuerzos/fuentes/alias; no rellenar con pendientes, repeticiones o cargos ajenos |
| La selección histórica contiene enlaces fallidos | Reporte actual de verificación | No reenviar esas ofertas; conservar snapshot, revisar casos y esperar nuevas oportunidades |
| Muchos 403/429/CAPTCHA de un portal | Salud de esa fuente, otros orígenes y frecuencia | Dejarlos pendientes; no declararlos cerrados, aumentar agresividad ni pedir una cookie personal |
| Se detectó cobro o página general | URL y destino final, motivo y hora | Apartar, revisar original y documentar; no pagar para comprobar ni enviar formularios |
| Apify aparece omitido | Cuota reservada, token, actor y crédito real | Si es por límite, esperar el período o usar fuentes gratuitas; no borrar reservas |
| Dice «Publicaciones LinkedIn omitida» pero formal funciona | `publicaciones_por_dia=0` y bloque LinkedIn Apify | Es lo esperado: presupuesto reservado a fichas formales |
| Web antigua con captura nueva | Despliegue, Source de Pages, variable y hora de salud | Ejecutar/reparar despliegue con datos existentes; no repetir toda la búsqueda para arreglar solo la web |
| Pages no despliega | Source=GitHub Actions, `PAGES_POR_ACTIONS`, entorno/ramas | Corregir configuración; no volver a publicación desde rama |
| Cloudflare tiene marcas/búsqueda distintas | Access, KV, repositorio/token y dominios | Revisar esa instalación; Functions no funcionan en GitHub Pages |
| «Enviadas» desapareció en otro equipo | Historial local vs KV | Importar exportación o revisar KV; no borrar entregas de Supabase |
| Capacidad Supabase o minutos Actions agotados | Uso/tamaño real y plan | Respaldar, acordar capacidad/frecuencia; archivar no libera automáticamente espacio |

Para soporte guardar: enlace/ID de ejecución, commit, fecha/hora Colombia, rol afectado, URL problemática, último paso,
cantidad de pendientes y mensaje de error sanitizado. No copiar variables de entorno ni cabeceras de autorización.

## 5. Diagnósticos y acciones manuales

En **Actions → Diagnóstico → Run workflow**, rama `main`:

- `solo_supabase=true`, `probar_apify=false`: lee conexión/esquema v1, sin crear ofertas. No prueba escritura ni todo v2.
- Ambos `false`: diagnóstico de configuración/fuentes, consulta de cuenta Apify y, si está, una consulta Brave.
  No ejecuta el actor Apify. Que aparezca una fuente opcional omitida no es un fallo de Supabase.
- `probar_apify=true`: una ejecución explícita de una oferta con límite USD 0,01, sin guardado Supabase. Sí consume
  crédito de la cuenta; no se incluye como una reserva normal del programa.

En una captura, `prueba=true` no guarda ofertas ni actualiza la rama; no sirve para probar cuota/escritura productiva.
**Búsqueda profunda** no tiene ese parámetro de prueba y puede consumir Apify. No repetirla para arreglar un despliegue.

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

Ejecutar en **Supabase → SQL Editor**, en el proyecto correcto. Son lecturas; no reemplazan la comprobación de la página.

```sql
-- Existencia de las tres tablas.
select table_name from information_schema.tables
where table_schema='public' and table_name in ('ofertas','catalogo_vacantes','entregas_diarias');

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
de las tres tablas con índices y las condiciones del plan Supabase. Si procede, acordar más capacidad o una estrategia
explícita de archivo/respaldos; cambiar un estado a archived no reduce espacio por sí solo.

**Mensual y al cambiar cuentas:** comprobar ciclo de crédito Apify, reservas, otros proyectos de la cuenta, permisos,
expiración de tokens, facturación de alojamiento y restauración de un respaldo. Revisar que el repositorio no quede
sin actividad de mantenimiento: GitHub puede deshabilitar cron en repositorios públicos inactivos según su política.

Los USD 5 limitan Apify del proyecto, no todos los servicios. En repositorio público las condiciones de Actions difieren
de uno privado; verificar plan actual. Como orden de magnitud, 24 capturas/día de 4,7 min son 3.384 min/mes, más unas
1.161 min por 30 nocturnas de 38,7 min, instalaciones y verificaciones. No asumir que cabe en 2.000 minutos privados.
Estos son cálculos con duraciones observadas, no una factura ni una duración garantizada.

No hay tarea implementada que elimine automáticamente el histórico Supabase ni una política de backup completo de la
base incluida en el código. Acordar con el cliente frecuencia, retención y responsable de respaldos. Propuesta inicial
para evaluar: copia diaria y antes de cambios, con recuperación probada; el administrador debe aprobar capacidad y ventana.

## 8. Respaldo completo y restauración comprobable

Un respaldo de `trabajo/` no contiene la base. Una exportación de `ofertas` no contiene catálogo/selecciones ni reservas.
Necesita **ambas piezas del mismo corte** y, si se usa, KV/historial del operador. Consultar también las opciones vigentes
[de respaldo de Supabase](https://supabase.com/docs/guides/platform/backups); no asumir que el plan gratis conserva una
copia recuperable para el cliente.

### Corte y respaldo

1. Deshabilitar los tres flujos que escriben y esperar los que estén en curso. Guardar los commits del corte.
2. Descargar/guardar completa la rama `publicado`, en especial `trabajo/` y `datos/salud.json`, fuera del repositorio.
   La rama se reescribe y no es por sí misma un histórico de recuperación. Actions guarda artefactos de estado 14 días,
   no una copia permanente ni el contenido de Supabase.
3. Exportar las tres tablas con tipos/JSON y la secuencia identity. Un técnico puede usar la receta siguiente, con cliente
   PostgreSQL compatible y acceso administrativo. Los servicios son perfiles de conexión seguros propios; no pegar
   contraseñas en argumentos ni en este manual. Ver [pg_service](https://www.postgresql.org/docs/current/libpq-pgservice.html).

```bash
# Directorio privado fuera del repositorio. Crear uno nuevo por corte y proteger sus archivos.
ADAPTIA_RESPALDO=/ruta/privada/al/respaldo-del-corte
pg_dump --dbname="service=adaptia_origen" --format=custom --data-only --no-owner --no-privileges \
  --table=public.catalogo_vacantes --table=public.entregas_diarias --table=public.ofertas \
  --table=public.ofertas_id_seq --file="$ADAPTIA_RESPALDO/datos.dump"
```

`adaptia_origen` referencia la conexión administrativa, TLS y credenciales fuera del código; el técnico prepara esos
perfiles según Supabase y su red. Verificar `pg_get_serial_sequence('public.ofertas','id')` si el esquema tiene un
nombre distinto al creado por el SQL del proyecto. Revisar la salida/exit code y un inventario con conteos, fechas,
estados y secuencia. El respaldo puede contener descripciones/URLs; almacenarlo con acceso restringido, no en GitHub.

### Ensayo de restauración

4. Crear un destino aislado **vacío**, que no reciba clientes ni automatizaciones. Aplicar `esquema.sql` y
   `002_catalogo.sql` con sus permisos. No crear roles nuevos en Supabase: son roles del proveedor.
5. Restaurar sin apuntar jamás al proyecto productivo por accidente:

```bash
pg_restore --dbname="service=adaptia_destino" --data-only --no-owner --no-privileges \
  --single-transaction --exit-on-error "$ADAPTIA_RESPALDO/datos.dump"
```

6. Comparar conteos/IDs/fechas/snapshots, estados cerrados/archivados, referencias y valor de la secuencia. Confirmar
   RLS/grants después de aplicar el esquema. Probar una inserción ficticia en ese destino y retirarlo al terminar el ensayo.
7. Verificar también que la copia de `trabajo/` conserva colas, lote, memoria y presupuesto del corte. No rejuvenecer
   fechas de verificación al copiar. Registrar quién ensayó, fecha, resultados y ubicación del respaldo.

La receta de tres tablas/secuencia se ensayó con datos ficticios en PostgreSQL 17: conteos, clave foránea, cierre,
permisos y siguiente identidad se conservaron. No equivale a restaurar el proyecto real del cliente ni certifica sus
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

La recuperación puede necesitar decisión humana si Supabase confirmó filas y se perdió una cola antes de publicarla.
V2 ayuda a reconstruir selección/no repetición, pero no restaura saldo ni reservas del proveedor. No garantizar que todo
se recupera automáticamente ni borrar filas para forzar otro resultado.

## 9. Actualizaciones y regreso de versión

Trabajar en rama y PR, ejecutar pruebas, revisar contrato y migraciones y respaldar antes de cambios de datos.
Después de fusionar verificar la siguiente captura y la página, no solo el CI. Para regresar código, un técnico prepara
un revert revisable y pasa pruebas; no borrar tablas v2/v3 ni historia por regresar interfaz. Una versión anterior puede
carecer de controles nuevos: no usarla como una solución permanente que vuelva a compartir enlaces sin comprobar.

## 10. Evidencia de preparación

Completar [ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md). Una captura o los tests no garantizan ausencia total de fallos.
La operación estable se demuestra con días distintos, calidad revisada, recuperación realista, costos observados y un
responsable que pueda resolver incidencias. WhatsApp sigue siendo una etapa posterior con su propio registro por destinatario.
