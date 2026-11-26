# Ceder el proyecto al nuevo dueño, sin copiar nada

Guía en lenguaje sencillo para pasar **el mismo** proyecto a las cuentas del nuevo dueño: la base de datos, el
repositorio con sus búsquedas programadas y el panel. Nada se copia: se cambia de dueño. Como la dirección y las claves
de la base no cambian, no se pierde información y nada se rompe.

Es distinto del traspaso con copia de [ENTREGA_AL_CLIENTE.md](ENTREGA_AL_CLIENTE.md) (flujo `traspaso.yml`). Ese camino
copia todo a un Supabase nuevo y detiene el anterior. Aquí no hace falta.

Los nombres de los menús de Supabase, GitHub y Render pueden variar un poco con el tiempo.

## Mientras tanto: darle acceso antes de ceder

**Para usar la plataforma no necesita Render.** Basta con dos pasos:

1. Supabase → Authentication → Users → *Invite user* (o *Add user*) con su correo.
2. Render → el servicio del panel → Environment → `PANEL_OPERATOR_EMAILS`: añadir su correo después del tuyo,
   separado por coma, y guardar. Render reinicia el panel solo.

Con eso trabaja en el panel y descarga sus datos en CSV, y tú conservas todo lo técnico.

Para quitarle el acceso, borra su correo de esa variable.

**Si además quieres que entre a Render,** por ejemplo para ver los registros o reiniciar el panel: Render → *Workspace
Settings* → *Members* → *Invite* con su correo y el rol que corresponda.

- Invitar miembros puede requerir un plan de Render que lo permita.
- Si el tuyo no lo permite, no hace falta: puede usar todo desde el panel.

## Lo que usa el sistema

| Dónde | Qué |
|---|---|
| Secretos de GitHub (Settings → Secrets and variables → Actions) | `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_DB_URL`, `SUPABASE_BACKUP_KEY` y `APIFY_TOKEN`. Opcionales: `AVISO_NOCTURNA_URL`, `AVISO_CAPTURA_URL`, `AVISO_RESPALDO_URL` y, si se activó la API de InfoJobs, `INFOJOBS_CLIENT_ID` e `INFOJOBS_CLIENT_SECRET`. `GITHUB_TOKEN` lo pone GitHub solo |
| Variables de GitHub | `CAPTURA_HORARIA_ACTIVA` y `ESTADO_SUPABASE_ACTIVO` |
| Render (panel) | `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `PANEL_ORIGIN`, `PANEL_OPERATOR_EMAILS`, `GITHUB_ACCIONES_TOKEN` y `GITHUB_REPOSITORIO` |
| Usuarios del panel | Supabase → Authentication → Users, más su correo en `PANEL_OPERATOR_EMAILS` |

## Fase 0 · Preparar (antes del día)

1. **Guarda el valor de cada llave** en un gestor de contraseñas. GitHub no deja volver a verlas y puede hacer falta
   crearlas de nuevo. La más importante es `SUPABASE_BACKUP_KEY`: sin ella no se pueden abrir las copias de seguridad
   cifradas.
2. **El nuevo dueño crea sus cuentas:**
   - GitHub;
   - Supabase, con una **organización** propia en un plan con sitio para un proyecto más;
   - Render;
   - Apify (esta puede esperar).
3. **El nuevo dueño te invita como *Owner*** a su organización de Supabase. Hace falta para poder moverle el proyecto.
4. **Elige una hora tranquila,** lejos de las búsquedas de las 6:30 y las 8:30 a. m. (hora de Bogotá).

## Fase 1 · Ceder la base de datos (Supabase)

1. En tu proyecto: Project Settings → General → **Transfer project** → la organización del nuevo dueño.
2. Los datos, los usuarios, la dirección y las claves no cambian, así que GitHub y el panel siguen funcionando igual.
3. Comprueba que el panel abre y muestra los datos.

## Fase 2 · Ceder el repositorio (GitHub)

1. Repositorio → Settings → General → Danger Zone → **Transfer ownership** → la cuenta del nuevo dueño.
   - Se van el código, el historial, las ramas y las búsquedas programadas.
   - También se va la rama `publicado`, que guarda la memoria de las búsquedas.
   - Los enlaces viejos redirigen solos.
2. En el repositorio ya transferido, revisa Settings → Secrets and variables → Actions:
   - que estén todos los secretos y las dos variables de la tabla de arriba;
   - si falta alguno, créalo con el valor que guardaste en la Fase 0.
3. En la pestaña **Actions**, comprueba que los flujos estén activados.
4. El nuevo dueño te agrega como **colaborador** del repositorio para que puedas seguir corrigiendo.

## Fase 3 · El panel (Render)

**Dónde queda el panel.** Hay dos opciones:

- **La más simple:** invitar al nuevo dueño a tu espacio de Render como dueño. El panel sigue en la misma dirección.
- **Cuenta propia:** el nuevo dueño crea el servicio con **New → Blueprint** (lee `render.yaml`) y las mismas
  variables. Si la dirección cambia, se actualiza `PANEL_ORIGIN` y se le pasa la nueva.

**Variables que cambian, en cualquiera de las dos:**

- `GITHUB_REPOSITORIO`: el nuevo, `cuenta-del-nuevo-dueño/Search_Adaptia_Jobs`.
- `GITHUB_ACCIONES_TOKEN`: lo crea el nuevo dueño desde su cuenta. Es un token fino, solo de ese repositorio, con
  permiso «Actions: lectura y escritura». El anterior deja de servir porque el repositorio ya no es tuyo. Sin este
  token, el botón «Buscar ahora» no aparece.
- `PANEL_OPERATOR_EMAILS`: su correo y el tuyo, separados por coma.

Crea también su usuario del panel en Supabase → Authentication → Users, y conserva el tuyo.

## Fase 4 · Llaves que pasan a ser del nuevo dueño

| Llave | Dónde | Qué hacer |
|---|---|---|
| `APIFY_TOKEN` | Secretos de GitHub | Poner el de su cuenta de Apify, con su límite mensual (el proyecto usa USD 5/mes) |
| `INFOJOBS_CLIENT_ID` e `INFOJOBS_CLIENT_SECRET` (optativos) | Secretos de GitHub | Registrar su propia aplicación en InfoJobs y poner sus dos datos (`docs/ACTIVAR_INFOJOBS_API.md`); sin ellos InfoJobs se lee por su página |
| `GITHUB_ACCIONES_TOKEN` | Render | El que él crea (Fase 3) |
| `SUPABASE_SECRET_KEY` | GitHub y Render | Recomendado, al final: él crea una nueva en Supabase (API Keys), se pone en los dos sitios y se borra la vieja. Así solo él la conoce |
| Contraseña de la base (va dentro de `SUPABASE_DB_URL`) | GitHub | Igual: él la cambia en Supabase (Database → Reset password) y se actualiza el secreto |
| `SUPABASE_BACKUP_KEY` | GitHub | **No cambiarla**: es la que abre las copias ya hechas. Dársela para que la guarde |
| Avisos (`AVISO_*`) | GitHub | Si existen, que apunten a un correo suyo |

## Fase 5 · Comprobar (unos 10 minutos)

1. GitHub → Actions → **Preparar Supabase** → *Run workflow*: termina en verde.
2. **Captura horaria** → *Run workflow*, sin marcar nada: termina en verde.
3. El nuevo dueño entra al panel y ve sus clientes, vacantes y mensajes, y aparece «Buscar ahora».
4. Al día siguiente, revisa que la búsqueda de las 6:30 corrió en su repositorio.

Si algo sale en rojo: abre la ejecución, pulsa el paso en rojo y lee el mensaje que empieza por `Error`. Para qué
hacer después, ver [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md).

## Qué se le entrega al nuevo dueño

- La dirección del panel y su usuario.
- `SUPABASE_BACKUP_KEY`, por un canal seguro: nunca por chat ni por correo sin cifrar.
- Las guías:
  - [GUIA_CLIENTE.md](GUIA_CLIENTE.md): cómo usar el panel;
  - [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md): qué hacer si algo falla;
  - [ENTREGA_AL_CLIENTE.md](ENTREGA_AL_CLIENTE.md), sección 0: qué hace cada pieza.
- La tabla de llaves de la Fase 4, para que sepa qué es suyo.

## Tu acceso después

Quedas como colaborador del repositorio en GitHub, miembro de su organización en Supabase y, si aplica, miembro de su
espacio en Render. Él es el dueño y te quita el acceso cuando quiera.
