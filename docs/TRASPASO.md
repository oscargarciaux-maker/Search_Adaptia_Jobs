# Traspaso al cliente sin perder continuidad

Versión vigente: 5 de noviembre de 2026. Acompaña [GUIA_CLIENTE.md](GUIA_CLIENTE.md), [INSTALACION.md](INSTALACION.md),
[OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md) y [ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md).
La preparación preferida del destino está en [INSTALACION_AUTOMATICA.md](INSTALACION_AUTOMATICA.md): el cliente configura
accesos una vez y no copia SQL 002/003 ni crea variables de captura. Continuidad sigue requiriendo un corte coherente.

## 1. Acordar qué se transfiere

Antes de actuar, elegir entre **continuar el servicio existente** o **instalar una instancia nueva e independiente**.
No tienen el mismo resultado. La continuidad conserva lo ya seleccionado, los pendientes y el presupuesto reservado.
Una instancia nueva con memoria vacía puede volver a ofrecer vacantes antiguas y reservar nuevamente crédito.

Acordar por escrito, fuera del repositorio, responsable y recuperación de acceso de cada servicio; fecha de corte;
URL final; historial que se entrega; presupuesto; canal de soporte y quién resuelve un bloqueo de las fuentes.
No transferir cuentas personales ni compartir contraseñas para simular el cambio de propietario.

| Elemento | Qué se entrega o configura | Evidencia |
|---|---|---|
| GitHub | Código `main`, flujos, rama `publicado`, permisos y ramas protegidas | Cliente entra con su cuenta y ve las ejecuciones |
| Supabase | Proyecto conservado o restauración de tablas/permisos; siete tablas y dos secuencias con el instalador | Conteos, referencias, reservas y lectura/escritura reales |
| Apify | Cuenta/organización del cliente, actor y límite | Token nuevo validado, saldo y reservas contrastados |
| Estado de trabajo | Toda la carpeta `trabajo/` de un mismo corte | Lote, colas y presupuesto respaldados juntos |
| Manuales y soporte | Versiones vigentes, incidencias conocidas y responsables | Cliente completa una búsqueda/selección sin ayuda |

GitHub aloja código y procesos; no mueve automáticamente los proyectos de Supabase o Apify.

## 2. Preparar un corte consistente

1. Elegir una ventana en que no se esté enviando una selección a clientes.
2. En Actions, deshabilitar temporalmente los flujos que escriben: **Bodega nocturna**, **Captura horaria** y
   **Búsqueda profunda**. Esperar a que las ejecuciones en curso terminen.
3. Guardar URL, identificador de la última ejecución, commit `main` y commit `publicado` del corte, sin registrar secretos.
4. Respaldar todas las tablas, secuencias y la carpeta de trabajo siguiendo el manual de operación. Conservar los respaldos fuera
   del repositorio y con acceso restringido. Los artefactos de Actions caducan; no son una copia permanente.
5. Guardar los reportes de salud y sus pendientes. No vaciar las colas ni modificar fechas para que el corte parezca limpio.
6. Registrar el saldo/uso de Apify y las reservas del archivo `apify_presupuesto.json` del mismo corte.
   En modo central, contrastar también `apify_reservas`; el archivo es una copia auxiliar.

Para detener operaciones no basta con cambiar `CAPTURA_HORARIA_ACTIVA=false`: la nocturna seguiría y además volvería
al camino v1. Utilizar la deshabilitación de flujos cuando se requiere una pausa completa de mantenimiento.

## 3. Transferir o copiar el repositorio

### Transferir propiedad y continuar la misma instancia

En GitHub: **Settings → General → Danger Zone → Transfer ownership**. El destinatario acepta la transferencia.
Comprobar después ramas, permisos, Actions, secretos, variables, entornos y protección: las condiciones pueden variar entre organizaciones y planes.

No afirmar que todos los secretos desaparecen al transferir: una transferencia puede conservar configuración del
repositorio. Revisar y sustituir las credenciales por las del cliente según el plan de continuidad. Eliminar accesos
que ya no correspondan solo después de verificar el relevo.

### Copiar como plantilla o a otro repositorio

Comprobar la opción de incluir ramas; no asumir que la copia contiene `publicado` ni el estado de trabajo.
Los secretos no deben copiarse como archivos ni se leen desde GitHub para compartirlos. Crear configuración y secretos
con los nombres previstos en [INSTALACION.md](INSTALACION.md).

Si se desea continuidad, restaurar explícitamente el estado `trabajo/` y los datos. Los identificadores y referencias
no se regeneran. Una copia de código con `modo=inicial` no es una migración completa de negocio.

## 4. Conservar o mover Supabase

Hay dos caminos; no ejecutarlos ambos a ciegas:

- **Conservar el proyecto:** utilizar la transferencia/propiedad de organización que permita Supabase, con accesos propios
  del cliente. Comprobar permisos y facturación y rotar la clave de servicio coordinadamente.
- **Crear otro proyecto:** preparar su esquema con `esquema.sql` y `002_catalogo.sql`; restaurar los datos en destino
  vacío y validar conteos, identidades, permisos y referencias antes de cambiar la conexión de producción.
  Si el origen tiene SQL 003, aplicar también `003_estado_operativo.sql` antes de restaurar, sin inicializar vacío.

Las tablas necesarias son:

1. `catalogo_vacantes`: identidad, contenido, estados, tiempos y verificación de enlaces.
2. `entregas_diarias`: registro de selección y snapshot; depende del catálogo mediante clave foránea.
3. `ofertas`: filas históricas compatibles con v1, potencialmente varias por vacante.
4. Si se aplicó 003, `estado_operativo`: marcador, colas con revisiones y selecciones sin confirmar.
5. Si se aplicó 003, `apify_reservas`: reservas de crédito anteriores y centrales; nunca reiniciarlas al traspasar.
6. Si se usó el instalador, `adaptia_migraciones`: versiones y hashes de SQL ya aplicado. No omitirlo ni borrar su historia.

Conservar las secuencias `ofertas_id_seq` y, tras 003, `estado_operativo_revision_seq`. La segunda evita reutilizar revisiones.

La vista `entrega_de_hoy` se crea con el esquema y no sustituye las tablas. Exportar/importar únicamente `ofertas` no
conserva el catálogo, el registro inmutable ni toda la capacidad de recuperación. No limitar la copia a registros activos:
los cerrados y archivados también forman parte del historial.

El procedimiento técnico de respaldo/restauración está en [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md).
No usar una exportación CSV simple como prueba suficiente de restauración: puede cambiar tipos, JSON, identidades o
relaciones. Probar la recuperación antes del corte definitivo.

## 5. Conservar el estado de la automatización

Restaurar **toda** la carpeta `trabajo/` de un corte coherente. Sus piezas principales son:

| Archivo | Función y motivo para conservarlo |
|---|---|
| `bodega.json.gz` | Inventario/descripcion para continuar la captura y deduplicación |
| `estado.json` | Rotación de consultas y estado de fuentes |
| `empresas_ats.csv` | Portales descubiertos además de la lista inicial |
| `entregadas.json` | Huellas/URLs ya seleccionadas; no es el historial manual del navegador |
| `lote_entrega.json` | Lote del día para repetir/reintentar sin escoger otro completo |
| `pendientes_supabase.json` | Filas históricas no confirmadas, con fecha original |
| `pendientes_catalogo.json` | Cambios de catálogo no confirmados |
| `pendientes_registro.json` | Selecciones no confirmadas en el registro v2 |
| `apify_presupuesto.json` | Contador en modo legado; copia auxiliar del registro Supabase en modo central |
| `verificacion_enlaces.json` | Caché de evidencias; caduca y no debe rejuvenecerse al copiar |
| `metricas_entrega.json` | Serie de días distintos para continuidad y preparación |

No editar las fechas de estos archivos, regenerar IDs ni mezclar colas de una base con otro catálogo independiente.
La memoria v2 puede reconstruir lote y no repetición desde Supabase, pero no reconstruye por sí sola presupuesto Apify,
consultas, pendientes locales aún no confirmados del inventario. Esa recuperación no reemplaza el respaldo.
Con SQL 003 y estado central activo, la base sí conserva reservas/colas y lotes sin confirmar; la carpeta sigue siendo
necesaria para los demás auxiliares. Mantener `ESTADO_SUPABASE_ACTIVO=true` en el destino restaurado; no volver a una
copia local antigua. Si aún no estaba activo, seguir [ACTIVAR_ESTADO_OPERATIVO.md](ACTIVAR_ESTADO_OPERATIVO.md).

## 6. Reconfigurar cuentas

1. Crear claves del cliente y actualizar los secretos `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `APIFY_TOKEN` y los opcionales.
   En modo automático, incluir `SUPABASE_DB_URL` del destino y `SUPABASE_BACKUP_KEY`. Conservar también, en su gestor,
   las claves de cifrado anteriores mientras se retengan copias; cambiar el secreto no vuelve legibles los cortes viejos.
2. Confirmar las variables `CAPTURA_HORARIA_ACTIVA=true` y `PAGES_POR_ACTIONS` según el alojamiento.
   Conservar además `ESTADO_SUPABASE_ACTIVO=true` si se traspasa una instancia central con SQL 003 restaurado.
   Las variables de captura/estado anteriores son del camino manual; el automático usa su marca privada. El alojamiento
   sí conserva configuración propia. Ejecutar Preparar Supabase tras restaurar en destino, dejando Instancia nueva apagada.
3. Si cambia el repositorio/propietario, revisar enlaces a Actions y permisos del nuevo propietario.
4. No se transfiere un sitio web ni marcas del navegador: la operación utiliza Supabase y Actions.

Los secretos antiguos se revocan en el proveedor cuando ya no hagan falta. Cambiar solo el valor en GitHub no invalida
un token que siga existiendo en Apify/Supabase. No borrar o pausar el proyecto de origen antes de validar destino y respaldo.

## 7. Validar el relevo y reanudar

1. Mantener la instancia antigua detenida: no operar dos copias como si fueran una sola memoria/presupuesto.
2. Ejecutar diagnóstico de Supabase de lectura con la conexión nueva. Después comprobar catálogo y permisos con la
   captura real y las consultas del manual; el diagnóstico de v1 por sí solo no acredita v2.
3. Habilitar solo el flujo que se va a probar y realizar una prueba acotada sin escritura.
4. Ejecutar una captura real con memoria restaurada. Si se repite el mismo día, debe reintentar/completar el lote,
   no crear otros veinte por rol. Verificar catálogo/registro/colas y que el presupuesto no reinició sus reservas.
5. Confirmar las vistas de Supabase, una selección y la conservación de una oferta cerrada/archivada. Las comprobaciones de
   enlaces caducadas se vuelven a revisar; no forzarlas a positivas para aprobar el traspaso.
6. Si se verifica continuidad en el mismo día, comparar IDs de `entregas_diarias`, no solo el número de filas de `ofertas`.
7. Rehabilitar la programación y retirar la posibilidad de ejecutar la instancia antigua.
8. Completar la lista de aceptación, registrar limitaciones pendientes y entregar responsables/canales de soporte.
9. Solo después, revocar credenciales/accesos anteriores, cerrar los recursos acordados y confirmar cargos pendientes.

La fecha y los resultados de una instalación de demostración no sustituyen la aceptación con las cuentas del cliente.
El manual no autoriza a borrar datos ni a superar el presupuesto para lograr una captura de 120 a cualquier costo.
