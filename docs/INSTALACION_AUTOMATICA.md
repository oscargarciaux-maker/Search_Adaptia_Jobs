# Instalación y actualizaciones automáticas

Este es el camino preferido para entregar el proyecto. Sustituye copiar los SQL 001/002/003 y activar variables a mano.
La configuración inicial de cuentas/secretos sigue correspondiendo al propietario; las siguientes actualizaciones las
ejecuta GitHub. Un PR incorpora código; la ejecución **Preparar Supabase** acredita la instalación de esa versión.

## Contrato de automatización

- Conexión administrativa privada `SUPABASE_DB_URL`, dirigida al mismo proyecto que `SUPABASE_URL`. Se usa el pooler
  **Session** de Supabase para disponer de IPv4 y bloqueos de sesión; no el pooler Transaction de puerto 6543.
  TLS verifica certificado y nombre. La contraseña va en Secrets, nunca en argumentos, artefactos ni logs.
  El programa incluye la raíz pública oficial de Supabase y la combina con las del sistema; no hace falta añadir
  otro secreto de certificado. Referencia y huella en [certificados](../supabase/certificados/README.md).
- Clave de respaldo `SUPABASE_BACKUP_KEY`: 32 bytes aleatorios codificados en base64 URL segura. Se conserva también
  fuera de GitHub en el gestor del cliente: sin ella no se pueden recuperar las copias cifradas.
- Las migraciones se descubren en orden: `esquema.sql` como 001 y archivos `NNN_nombre.sql` posteriores. Se registra
  nombre/hash SHA-256/fecha en `adaptia_migraciones`, tabla privada adicional. No modificar un SQL ya registrado:
  añadir otro. Una versión desconocida o un hash distinto detiene el proceso antes de cambiar datos.
- Un bloqueo impide dos migradores simultáneos. Las migraciones pendientes y su registro se confirman en una sola
  transacción, retirando solo los BEGIN/COMMIT externos de los archivos existentes. Un fallo revierte ese lote.
- Antes de cualquier migración pendiente o primera activación automática, se crea una copia cifrada del estado de las
  tablas del proyecto, sus secuencias y `trabajo/`. Si falla la copia, no se cambia el esquema. No incluye Auth, Storage,
  otros esquemas ni configuraciones de proveedor: no equivale a un backup completo de toda la plataforma Supabase.
- Se importa el presupuesto actual, sin asumir cero. Solo el botón inicial **Instancia nueva** permite inicializar
  expresamente una base sin historial ni reservas. No reinicia una instalación usada; si hay historia y falta contador, se bloquea.
- La marca privada `estado_operativo/control/instalacion_automatica` se guarda tras validar el esquema y presupuesto.
  Contiene los hashes requeridos. Las capturas la detectan sin modificar variables GitHub; catálogo y estado central
  quedan activados para esa ejecución. La captura horaria sigue sin consumir Apify ni crear entregas diarias.
- Configurar, migrar y capturar comparten el grupo de exclusión `publicar` de Actions. Otras copias del servicio deben
  permanecer detenidas. No hay transacción entre base, artefactos de GitHub y servicios externos.

Las pruebas `--prueba` nunca migran ni activan. Una instalación manual existente sigue funcionando cuando no se ha
configurado la conexión administrativa. Si ya hay marca automática, una credencial ausente o migración nueva no se
resuelve volviendo a modo local: debe corregirse la configuración. Las claves administrativas solo se entregan al paso
de preparación; la captura usa la clave REST de servicio existente.

## Configuración inicial del propietario

1. Conservar `SUPABASE_URL` y `SUPABASE_SECRET_KEY` del proyecto. En Supabase, **Connect → Session pooler → URI**, obtener
   la conexión PostgreSQL con la contraseña de la base. En GitHub → **Settings → Secrets and variables → Actions → Secrets**,
   guardarla como `SUPABASE_DB_URL`. No pegarla en el chat. El usuario suele ser `postgres.<referencia>` y el puerto 5432.
2. Crear `SUPABASE_BACKUP_KEY` con un generador seguro de 32 bytes/base64 URL segura. Un administrador puede ejecutar
   `python -c "import secrets; print(secrets.token_urlsafe(32))"` en su equipo privado y guardar el resultado como secreto
   y en el gestor del cliente. No ejecutar ese comando en un log compartido ni perder las claves de copias anteriores.
3. En **Actions → Preparar Supabase → Run workflow → main**, ejecutar. Para continuar este proyecto dejar **Instancia
   nueva** apagada: se importa el contador existente de `publicado/trabajo/`. Solo un negocio nuevo, con base vacía,
   marca esa opción una vez. La preparación no busca vacantes ni ejecuta Apify.

Después, las migraciones se comprueban antes de cada captura real y al fusionar cambios de instalación/SQL. No es
necesario copiar SQL ni crear `ESTADO_SUPABASE_ACTIVO`/`CAPTURA_HORARIA_ACTIVA` para el modo automático. El alojamiento
Pages/Cloudflare conserva su configuración propia. Si se añaden secretos después de una fusión, el botón anterior permite
instalar sin esperar al siguiente horario.

## Comprobación y recuperación

Si falla la conexión, ejecutar **Actions → Diagnóstico → solo_conexion_db=true**, dejando las otras opciones apagadas.
Comprueba autenticación con `SELECT 1` dentro de una transacción de solo lectura: no aplica SQL de migración, consulta
vacantes, ejecuta Apify ni publica. Distingue URI inválida, proyecto/puerto incorrecto, contraseña ausente, autenticación
rechazada, DNS, ruta IPv6 de conexión directa, tiempo agotado y certificado TLS. Solo imprime categorías/mensajes
controlados; nunca DSN, contraseña, usuario/proyecto ni el error original de libpq. No desactivar TLS para corregir un fallo.
Si no hay categoría concluyente, el resultado no prueba que la contraseña sea incorrecta. Este diagnóstico puede
ejecutarse sobre una rama de revisión; la preparación con migraciones continúa limitada a main.

El resumen de Actions indica migraciones aplicadas o ya vigentes, respaldo generado y preparación confirmada. La siguiente
captura debe mostrar `estado_operativo.activo: true`, cero pendientes y su SHA. Eso no acredita calidad de todos los enlaces.
No se ha configurado ni ejecutado esta instalación en la base real durante el desarrollo del cambio.

Las copias se suben como artefactos **respaldo-instalacion-…**, cifrados, con retención de 14 días. Descargarlas a almacenamiento
privado duradero según la política acordada. Una copia previa a migración no sustituye backups periódicos ni un monitor
independiente. El respaldo se comprime y cifra en flujo; los originales de trabajo se conservan en su ubicación habitual.

La restauración se ensaya en una base vacía y aislada: preparar el esquema, descifrar/verificar la copia, restaurar tablas
en orden, identidades/secuencias y trabajo. Nunca ejecutar una restauración sobre producción para probar si funciona.
El historial de migraciones también viaja en el corte; tras este cambio son seis tablas de proyecto y dos secuencias.
Conservar las versiones SQL originales y la clave que corresponde al artefacto. Una copia vieja no repone crédito Apify:
contrastar consumo posterior al corte antes de volver a abrir el servicio.
