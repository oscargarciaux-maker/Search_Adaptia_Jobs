# Dónde guardar los accesos y qué significa cada clave

Actualizada el 16 nov 2026 (escrita el 6 nov; se añadió el panel en Render y se quitaron Brave y Cloudflare).

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
| **InfoJobs — API oficial (optativa)** | Client ID y Client secret de la aplicación registrada en developer.infojobs.net (`docs/ACTIVAR_INFOJOBS_API.md`). Sin ellos InfoJobs se lee por su página | Repository secrets → `INFOJOBS_CLIENT_ID` e `INFOJOBS_CLIENT_SECRET` |
| **Panel — operadores** | Correos que pueden entrar al panel, separados por comas. No es una clave, pero conviene registrarlo | Render → servicio del panel → Environment → `PANEL_OPERATOR_EMAILS` |
| **Panel — dirección** | Dirección HTTPS del panel (por ejemplo, la de Render). No es una clave | Render → Environment → `PANEL_ORIGIN` |
| **Panel — conexión a Supabase** | Las mismas `SUPABASE_URL` y `SUPABASE_SECRET_KEY` de arriba; el panel las usa en el servidor, nunca en el navegador | Render → Environment → `SUPABASE_URL` y `SUPABASE_SECRET_KEY` |
| **Usuarios del panel** | Cada operador entra con su correo y contraseña de Supabase Auth (Authentication → Users). Cada persona guarda la suya | Supabase → Authentication; no va en GitHub ni en Render |

La contraseña de acceso a la cuenta Supabase (o su inicio de sesión con Google/GitHub) es otro acceso personal. No se pega
en `[YOUR-PASSWORD]`. Las cuentas personales GitHub/Supabase/Apify se mantienen con usuarios propios e invitaciones al
proyecto. El cliente recibe propiedad/permisos y credenciales del servicio, sin utilizar la cuenta personal de Oscar.

GitHub genera `GITHUB_TOKEN` para los flujos: no hace falta inventar esa contraseña ni guardarla como secreto del repositorio.
La web antigua de Cloudflare y la búsqueda con Brave se retiraron: sus claves ya no se usan y no hace falta crearlas.

**La contraseña PostgreSQL y `SUPABASE_DB_URL` no son dos contraseñas diferentes:** la segunda es una dirección que lleva
la primera dentro. `SUPABASE_SECRET_KEY` y `SUPABASE_BACKUP_KEY` sí son claves diferentes, con funciones independientes.

## Tabla de secretos: quién los crea, si caducan y qué falla (28 nov 2026)

**Nunca se escriben valores aquí.** «Dónde» es donde el programa los lee. «Renovar» es el único paso para sustituirlo
(guardar primero en el gestor y después pegar en GitHub o Render).

| Secreto | Para qué sirve | Dónde | Quién lo crea | Caduca | Qué falla si caduca o falta | Renovar en 1 paso |
|---|---|---|---|---|---|---|
| `SUPABASE_URL` | Dirección de la API del proyecto | Actions y Render | Supabase, al crear el proyecto | No | Todo el programa y el panel quedan sin base | Copiar la URL del proyecto nuevo a Actions y Render |
| `SUPABASE_SECRET_KEY` | Clave de API del servidor (lee y escribe vacantes y estado) | Actions y Render | Supabase → Settings → API Keys (cuenta del cliente) | Las claves *legacy* `service_role` se retiran a principios de 2027; una `sb_secret_…` no caduca | Actions y panel sin base | Crear una clave `sb_secret_…` y pegarla en Actions y en Render (las dos, siempre juntas) |
| `SUPABASE_DB_URL` | Conexión directa a PostgreSQL (migraciones, copias, diagnóstico) | Actions | Quien tiene la contraseña de la base | No, salvo que se cambie la contraseña | Bodega, copias y migraciones en rojo | Restablecer la contraseña en Supabase y regenerar la URI (ver abajo) |
| `SUPABASE_BACKUP_KEY` | Cifra y descifra las copias de seguridad | Actions | Quien entrega, una sola vez (32 bytes aleatorios) | No | Las copias dejan de poder restaurarse; sin la clave guardada fuera de GitHub no se pueden descifrar | No se renueva: se **custodia** en el gestor. Si se cambia, conservar la anterior mientras existan copias con ella |
| `APIFY_TOKEN` | Búsquedas pagadas de refuerzo en LinkedIn (tope mensual) | Actions | Cuenta de Apify del cliente | No (Apify admite caducidad opcional al crearlo) | El rescate con Apify se salta; el programa sigue sin él | Crear un token nuevo en Apify → Settings → Integrations y pegarlo en Actions |
| `INFOJOBS_CLIENT_ID` e `INFOJOBS_CLIENT_SECRET` (optativos) | API oficial de InfoJobs | Actions | developer.infojobs.net | No | InfoJobs se lee por su página, con menos datos | Regenerar el par en InfoJobs y pegar los dos |
| `LLM_API_KEY` (optativo, P-14.2) | Clave del proveedor de LLM que propone términos de búsqueda por cargo (`llm` en `datos/config.yaml`; el nombre del secreto se cambia en `clave_env`) | Actions (Bodega) | El proveedor que se elija (aún ninguno: GitHub Models se retiró el 30 jul 2026) | Según el proveedor | Nada: la búsqueda sigue con los términos guardados (aviso en el registro) | Crear otra clave en el proveedor y pegarla |
| `AVISO_NOCTURNA_URL`, `AVISO_CAPTURA_URL`, `AVISO_RESPALDO_URL` (optativos) | Direcciones de Healthchecks para los avisos | Actions | Healthchecks del cliente | **Sí: Healthchecks borra la cuenta si no se entra al menos 1 vez al año** | Se acaban los avisos y nadie se entera de las caídas | Entrar a Healthchecks 1 vez al año; si se borró, crear los 3 chequeos y pegar las URL nuevas |
| `AVISO_GITHUB_USUARIO` (variable, no secreto) | Usuario de GitHub al que el Vigía de avisos menciona en el issue «Atención: Adaptia» | Actions → Variables | Quien atiende los avisos | No | El issue se abre sin mención: nadie recibe el correo | Poner el usuario de quien atiende los avisos (docs/OPERACION_Y_RECUPERACION.md §1) |
| `CLAUDE_CODE_OAUTH_TOKEN` | Flujos «Claude» y «Claude Code Review» de los PR | Actions | Quien tiene la suscripción (hoy Oscar): `claude setup-token` | **Sí: dura 1 año** (guardado el 27 nov 2026, vence hacia el 27 nov 2027) y va ligado a esa suscripción | Los dos flujos salen en rojo en cada PR y consumen la cuenta de quien lo creó. No afecta a la búsqueda ni al panel | `claude setup-token` y pegar el resultado; o borrar los dos flujos si el cliente no los usa |
| `GITHUB_ACCIONES_TOKEN` | «Buscar ahora» del panel (lanza `bodega.yml`) | Render | El dueño del repositorio: token fino, solo este repositorio, permiso «Actions: lectura y escritura» | Admite «sin caducidad», pero **GitHub lo revoca si pasa 1 año sin usarse**; si se creó con fecha, vence en esa fecha | «Buscar ahora» da error (el panel lo explica); la búsqueda automática sigue | Crear un token fino nuevo y pegarlo en Render → Environment |
| `PANEL_OPERATOR_EMAILS` y `PANEL_ORIGIN` (no son claves) | Quién entra al panel y su dirección HTTPS | Render | El cliente | No | Nadie entra al panel o la sesión se rechaza | Editar el valor en Render |
| `SUPABASE_URL_DESTINO`, `SUPABASE_SECRET_KEY_DESTINO`, `SUPABASE_DB_URL_DESTINO` | Solo al traspasar a otro proyecto de Supabase (`traspaso.yml`) | Actions | El cliente, con su proyecto nuevo | No | Solo falla el traspaso | Se borran al terminar el traspaso |
| `GITHUB_TOKEN` | Lo pone GitHub en cada corrida | Actions | GitHub | Dura lo que la corrida | Nada que hacer | — |

**Dos caducidades de GitHub que no son un secreto pero apagan todo:**

- Un token personal que no se usa durante **1 año** lo revoca GitHub.
- En un repositorio público, GitHub desactiva los horarios (`schedule`) tras **60 días sin actividad** en el repositorio
  (por ejemplo, sin commits). Se desactiva cada flujo programado, también el Reloj. Para reactivarlos: Actions → elegir el
  flujo → **Enable workflow**. Con el Vigía activo se avisa antes; sin él, hacer un commit pequeño al mes lo evita.

**GitHub Pages no se usa.** Si Settings → Pages sigue activo, desactivarlo (Settings → Pages, o con
`gh api -X DELETE repos/<dueño>/<repositorio>/pages`). Ningún flujo ni código lee `PAGES_POR_ACTIONS` ni el entorno
`github-pages`.

**No hacer privado el repositorio en el plan Free:** el Wait timer del Reloj desaparece y los minutos de Actions dejan de
ser gratis (ver [TRASPASO.md](TRASPASO.md) §6).

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
- **Clave de API Supabase en el panel:** si cambia `SUPABASE_SECRET_KEY`, actualizarla también en Render; si no, el
  panel deja de cargar datos.

Después de corregir `SUPABASE_DB_URL`, ejecutar **Diagnóstico → solo_conexion_db=true**. El éxito confirma la autenticación
y una consulta de solo lectura, sin migraciones. La preparación automática es otra comprobación: importa el corte,
aplica lo pendiente y activa el estado central. Ninguna de ellas se acredita solo por guardar un secreto o fusionar un PR.

## Alcance de esta guía

Esta guía no configura una bóveda ni modifica secretos o bases de datos. El propietario prepara el gestor, la invitación
y los permisos desde sus cuentas. El proyecto conserva esta referencia sin valores privados para
que el cliente entienda qué buscar y dónde actualizarlo. No es necesario fusionar documentación para utilizar un gestor.
