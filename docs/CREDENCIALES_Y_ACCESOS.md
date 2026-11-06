# Dónde guardar los accesos y qué significa cada clave

Para Oscar y el propietario que recibe el proyecto. **Este documento es un índice: no se rellena con contraseñas.**
Los valores privados se guardan en un gestor de contraseñas y se copian a la configuración del programa cuando corresponda.

## Un lugar para consultarlos después

Recomendación: [Bitwarden](https://bitwarden.com/), con una organización y una colección compartida llamada **Adaptia Jobs**.
Si el cliente ya utiliza un gestor con bóvedas compartidas, puede conservarlo; la organización de entradas siguiente sirve igual.

1. Crear la colección compartida con el propietario del proyecto. Revisar las opciones/condiciones del plan del gestor.
2. Cada persona entra con su propia cuenta. Invitar al cliente a la colección mediante el gestor; no compartir la contraseña
   maestra de una cuenta. El propietario del programa debe poder administrar y recuperar los accesos que recibe.
3. Crear las entradas indicadas abajo, con nombres claros y los valores en los campos privados del gestor.
4. Copiar desde el gestor al secreto de GitHub correspondiente. Guardar primero en el gestor: GitHub no devuelve el valor
   después de guardarlo, solo permite sustituirlo o eliminarlo.
5. Comprobar que el cliente puede abrir las entradas, identificar su función y consultar los valores necesarios antes de
   terminar el traspaso. Al cerrar el soporte, revisar los accesos que continúan vigentes según lo acordado.

El gestor es para consultar/compartir accesos entre administradores. GitHub Secrets es para que el programa los use.
El repositorio, la página pública, las tablas de vacantes y este chat no son almacenes de contraseñas.

## Mapa de credenciales

| Nombre de entrada sugerido en el gestor | Qué contiene / para qué sirve | Dónde lo usa el programa |
|---|---|---|
| **Supabase — contraseña de la base** | Contraseña PostgreSQL elegida al crear el proyecto o al restablecerla en Database Settings. Permite construir la conexión administrativa | Está dentro de `SUPABASE_DB_URL`; no tiene un secreto separado en la versión actual |
| **SUPABASE_DB_URL — conexión completa** | URI de Session pooler: incluye usuario, contraseña codificada, servidor, puerto 5432 y nombre de base. Es privada porque contiene la contraseña anterior | GitHub Actions → Repository secrets → `SUPABASE_DB_URL` |
| **SUPABASE_BACKUP_KEY — respaldos** | Clave aleatoria generada de 32 bytes, representada normalmente por 43 caracteres. Cifra/descifra los cortes | Repository secrets → `SUPABASE_BACKUP_KEY` |
| **SUPABASE_SECRET_KEY — API** | Secret key o service_role proporcionada por Supabase. El programa guarda vacantes por REST con ella | Repository secrets → `SUPABASE_SECRET_KEY` |
| **SUPABASE_URL — dirección API** | Dirección del proyecto; no es una contraseña ni una conexión PostgreSQL | Repository secrets → `SUPABASE_URL` |
| **APIFY_TOKEN — LinkedIn** | Token de la cuenta Apify, con permisos para el refuerzo de ofertas formales y su presupuesto | Repository secrets → `APIFY_TOKEN` |
| **BRAVE_API_KEY — opcional** | Clave de Brave si esa fuente está contratada/configurada | Repository secrets → `BRAVE_API_KEY`; no crearla solo para completar el inventario |

La contraseña de acceso a la cuenta Supabase (o su inicio de sesión con Google/GitHub) es otro acceso personal. No se pega
en `[YOUR-PASSWORD]`. Las cuentas personales GitHub/Supabase/Apify se mantienen con usuarios propios e invitaciones al
proyecto. El cliente recibe propiedad/permisos y credenciales del servicio, sin utilizar la cuenta personal de Oscar.

GitHub genera `GITHUB_TOKEN` para los flujos: no hace falta inventar esa contraseña ni guardarla como secreto del repositorio.
Si se utiliza Cloudflare, sus cuentas y el token `GITHUB_TOKEN_FLUJOS` se registran por separado en el gestor siguiendo
[Instalación](INSTALACION.md); ese token opcional no es el `GITHUB_TOKEN` automático de Actions.

**La contraseña PostgreSQL y `SUPABASE_DB_URL` no son dos contraseñas diferentes:** la segunda es una dirección que lleva
la primera dentro. `SUPABASE_SECRET_KEY` y `SUPABASE_BACKUP_KEY` sí son claves diferentes, con funciones independientes.

## Recuperar los valores que ya se configuraron

GitHub Secrets no permite mostrar el valor guardado. Si todavía no existe una entrada en el gestor, buscar el original
en los registros privados del propietario o en el panel del proveedor. Si ese proveedor ya no permite consultarlo,
hay que sustituirlo coordinadamente y actualizar las configuraciones que lo utilizan; no se obtiene desde el repositorio.

La contraseña PostgreSQL desconocida se restablece desde Supabase. La clave de respaldo requiere atención especial:
si solo quedó en GitHub y no se conservó una copia, no se puede consultar allí después. Antes de regenerarla, revisar
qué cortes existentes dependen de ella y conservar las claves anteriores disponibles. Registrar desde ahora las claves
nuevas en el gestor evita repetir esa pérdida. Este documento no cambia ni recupera los valores de Secrets.

## Cómo completar `[YOUR-PASSWORD]`

En la conexión final, **se sustituye el bloque completo `[YOUR-PASSWORD]`, incluidos sus corchetes**, por la contraseña
PostgreSQL codificada para URI. No dejar corchetes alrededor de la contraseña ni pegar solo la contraseña en `SUPABASE_DB_URL`.
Se conservan el resto de la URI original: usuario, servidor, puerto y base.

En el método de PowerShell de [Instalación automática](INSTALACION_AUTOMATICA.md#contraseña-de-la-base-dentro-de-la-uri):

1. En el primer aviso se pega la URI original de Session pooler **todavía con `[YOUR-PASSWORD]`**.
2. En el segundo aviso se escribe la contraseña vigente de la base, sin añadir corchetes. Ese campo oculta lo escrito.
3. El comando reemplaza el marcador completo, codifica los caracteres especiales y copia la **URI final completa**.
4. Guardar esa URI en la entrada `SUPABASE_DB_URL — conexión completa` del gestor y copiarla al secreto homónimo de GitHub.
   Evitar copiar otro texto entre generar y pegar, porque reemplazaría el portapapeles.

La contraseña guardada en el campo de contraseña de la base del gestor permanece en su forma original. La codificación
solo cambia su representación dentro de la URI, no la contraseña del servidor. La URI completa sigue siendo privada.

## Ficha de cada entrada del gestor

Crear estos campos en el gestor, no en este archivo:

- Nombre claro de la entrada y propósito.
- Valor privado en su campo de contraseña/secreto.
- Servicio y proyecto al que pertenece; enlace del panel para encontrarlo.
- Nombre exacto de secreto de GitHub donde se copia, si corresponde.
- Responsable y personas que deben tener acceso.
- Fecha de cambio y última comprobación válida, con enlace a la ejecución.

Para `Supabase — contraseña de la base`, guardar también como campo de referencia la URI **original** de Session pooler
que contiene el marcador, y distinguirla claramente de la URI **final** de `SUPABASE_DB_URL`. Así no hay que reconstruir
el servidor o el usuario de memoria. Comprobar siempre que corresponda al mismo proyecto que `SUPABASE_URL`.

## Cuando cambia una clave

- **Contraseña PostgreSQL:** actualizar la entrada de contraseña del gestor, regenerar la URI final con el método anterior,
  guardarla en el gestor y reemplazar `SUPABASE_DB_URL` en GitHub. Actualizar también otros consumidores de esa conexión.
- **Clave de API Supabase:** actualizar su entrada y `SUPABASE_SECRET_KEY`; no reemplazar con ella la contraseña de la base.
- **Clave de respaldo:** conservar en el gestor la clave anterior identificada por fecha/cortes mientras existan copias
  cifradas con ella. Cambiarla en GitHub no vuelve descifrables esos cortes con la nueva clave.
- **Token Apify:** actualizar su entrada y `APIFY_TOKEN`, conservando el historial y las reservas de presupuesto.

Después de corregir `SUPABASE_DB_URL`, ejecutar **Diagnóstico → solo_conexion_db=true**. El éxito confirma la autenticación
y una consulta de solo lectura, sin migraciones. La preparación automática es otra comprobación: importa el corte,
aplica lo pendiente y activa el estado central. Ninguna de ellas se acredita solo por guardar un secreto o fusionar un PR.

## Alcance de esta guía

Esta guía no configura una bóveda ni modifica secretos o bases de datos. El propietario prepara el gestor, la invitación
y los permisos desde sus cuentas. El proyecto conserva esta referencia sin valores privados para
que el cliente entienda qué buscar y dónde actualizarlo. No es necesario fusionar documentación para utilizar un gestor.
