# Entrega al cliente — guía paso a paso

Guía en lenguaje sencillo para (1) probar el sistema antes de entregarlo, (2) pasarlo al Supabase de pago del cliente
el día de la entrega y (3) revisarlo la primera semana. Los detalles técnicos siguen en [TRASPASO.md](TRASPASO.md),
[OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md) y [PANEL_CONTROL.md](PANEL_CONTROL.md).

Todo lo que se hace en GitHub está en la pestaña **Actions** del repositorio: se elige el flujo a la izquierda y se
pulsa **Run workflow**. Las claves se guardan en **Settings → Secrets and variables → Actions → Secrets**. Nunca se
pegan claves en el código, en el chat ni en documentos.

## 0. Qué hace cada pieza

| Pieza | Cuándo corre | Qué hace |
|---|---|---|
| Bodega nocturna | 1:17 a. m. (Colombia) | Busca y elige las 120 vacantes del día |
| Bodega nocturna (pasada de la mañana) | 7:17 a. m. | Solo si a la noche le faltaron vacantes o no corrió: completa el mismo día |
| Captura horaria | Cada hora | Actualiza vacantes y comprueba enlaces; no elige vacantes nuevas |
| Copia de seguridad semanal | Domingos 5:41 a. m. | Copia cifrada de todo; se guarda 90 días en Actions |
| Traspaso a otro Supabase | Solo a mano | Copia todo al Supabase del cliente y comprueba que coincida |
| Preparar Supabase | Al fusionar cambios o a mano | Instala las actualizaciones de la base con copia previa |
| Pruebas | En cada cambio | Revisa el código; no toca datos reales |

Apify tiene un tope del proyecto de USD 5 al mes repartido por día (≈ USD 0,17). La pasada de la mañana no gasta más
de lo que quedó del día. Las capturas horarias, las copias y el traspaso no usan Apify.

## 1. Pruebas manuales que puedes hacer ya

Ninguna de estas pruebas cambia la selección de vacantes ni gasta Apify.

| # | Prueba | Cómo | Resultado esperado |
|---|---|---|---|
| 1 | Prueba corta de la búsqueda | Actions → **Bodega nocturna** → Run workflow → marcar *Corrida corta de prueba* | Termina en verde en unos 5–10 min; no escribe en Supabase |
| 2 | Prueba de captura | Actions → **Captura horaria** → Run workflow → marcar *Solo capturar en temporal* | Verde; no escribe en Supabase |
| 3 | Copia de seguridad | Actions → **Copia de seguridad semanal** → Run workflow | Verde. Abajo, en *Artifacts*, aparece `respaldo-semanal-…`; el resumen muestra cuántas filas tiene cada tabla |
| 4 | Pasada de la mañana | Revisar Actions cualquier día después de las 7:17 a. m. | Aparece una *Bodega nocturna* de la mañana. Si la noche llegó a 120, termina en ~1 min sin hacer nada; si no, completa el día |
| 5 | Ensayo del traspaso | Ver sección 2 | El resumen dice *Ensayo comprobado* y los conteos coinciden; tu base sigue funcionando |
| 6 | Panel en demostración | Ver sección 5 | Puedes crear clientes/cargos, ver la estimación de vacantes y copiar el mensaje de WhatsApp |
| 7 | Avisos por correo | Ver sección 4 | Llega un correo de prueba |

Si algo sale en rojo, abre la ejecución, pulsa el paso en rojo y copia el mensaje que empieza por `Error`.

## 2. Ensayo del traspaso (recomendado antes de la entrega)

Sirve para comprobar, sin riesgo, que todo se copia bien a otro Supabase. **Tu base actual sigue funcionando.**

1. En Supabase, crea un proyecto **nuevo y vacío** de prueba (el plan gratuito permite dos proyectos).
2. En ese proyecto copia dos datos:
   - **Project URL**: Project Settings → Data API (algo como `https://xxxx.supabase.co`).
   - **Cadena de conexión**: botón **Connect** → *Session pooler* (puerto 5432). Sustituye `[YOUR-PASSWORD]` por la
     contraseña de la base de ese proyecto.
3. En GitHub, crea dos secretos: `SUPABASE_URL_DESTINO` (la URL) y `SUPABASE_DB_URL_DESTINO` (la cadena de conexión).
4. Actions → **Traspaso a otro Supabase** → Run workflow → escribe `TRASPASAR` y **deja marcada la casilla Ensayo**.
5. Resultado esperado: verde y un resumen *Ensayo comprobado* con las filas de cada tabla.
6. Al terminar, borra el proyecto de prueba en Supabase (Project Settings → General → Delete project) y los dos
   secretos `…_DESTINO` en GitHub.

Si sale en rojo: tu base no cambió. Los mensajes más comunes son *destino ya tiene tablas* (usar un proyecto vacío)
y errores de conexión (`[DB_…]`, revisar la cadena de conexión y la contraseña).

## 3. Lo que debe tener listo el cliente antes de la entrega

| Qué | Detalle |
|---|---|
| **Proyecto Supabase nuevo** en su cuenta de pago | **No usar el proyecto de su página web.** Este sistema necesita su propia base: el traspaso se niega a mezclarse con tablas existentes. En el plan Pro cada proyecto extra tiene un costo de cómputo mensual; confirmarlo en su facturación |
| Datos de ese proyecto | Project URL, **secret key** (Project Settings → API Keys) y cadena *Session pooler* con contraseña |
| Cuenta de Apify propia | Su token de API, con límite de USD 5/mes configurado en Apify (o el que decida) |
| Cuenta de GitHub | Para recibir el repositorio (o un colaborador con permiso de administración) |
| Correo para avisos | El de la persona que atenderá los problemas, no uno personal |
| Alojamiento del panel | Ver sección 5; solo si van a usar el panel de clientes |

## 4. Avisos por correo (Healthchecks)

GitHub no avisa cuando una tarea **no llega a ejecutarse**. Healthchecks.io (plan gratuito) sí: cada tarea le dice
"terminé bien" o "fallé", y si no recibe noticias a tiempo, envía un correo.

1. Crear cuenta en healthchecks.io con el correo de avisos.
2. Crear tres *checks* y anotar la URL de *ping* de cada uno:
   - **Nocturna**: Period 1 day, Grace 3 hours.
   - **Captura horaria**: Period 1 hour, Grace 2 hours.
   - **Copia semanal**: Period 7 days, Grace 1 day.
3. En GitHub, crear los secretos `AVISO_NOCTURNA_URL`, `AVISO_CAPTURA_URL` y `AVISO_RESPALDO_URL` con esas URL.
4. En Healthchecks, en **Integrations**, usar la opción de prueba junto al correo para comprobar que el aviso llega.

Sin esos secretos todo funciona igual, solo que sin avisos.

## 5. Panel de clientes

**Probarlo hoy (demostración con datos ficticios)**, en un computador con Python 3.12 y Node 24:

```bash
pip install -r requirements.txt
```

```bash
npm --prefix web ci && npm --prefix web run build
```

```bash
python -m panel.api --demo --port 8000
```

Abrir http://localhost:8000. Probar: crear un cliente con un perfil, ver la estimación «≈ N vacantes guardadas aún no entregadas», pulsar **Estimar con búsqueda en vivo**,
pulsar **Aplicar** en una sugerencia, añadir un cargo nuevo (por ejemplo «Editor de video») y revisar sus sugerencias,
programar para mañana y copiar el mensaje de WhatsApp.

**Instalarlo con tus datos reales en Render (plan gratuito)** — unos 20 minutos, una sola vez:

1. Entrar en render.com y registrarse con GitHub. Para la entrega definitiva conviene que la cuenta sea del cliente.
2. **New → Blueprint** → elegir el repositorio `Search_Adaptia_Jobs`. Render lee `render.yaml` y pide cuatro valores:
   - `SUPABASE_URL`: el mismo valor del secreto de GitHub (Supabase → Project Settings → Data API → Project URL).
   - `SUPABASE_SECRET_KEY`: la *secret key* del proyecto (Supabase → Project Settings → API Keys), la misma de GitHub.
   - `PANEL_ORIGIN`: `https://adaptia-panel.onrender.com`. Si Render asigna otra dirección (por ejemplo con un sufijo),
     copiar la que muestre y cambiar este valor en *Environment*; el panel se reinicia solo.
   - `PANEL_OPERATOR_EMAILS`: el correo con el que vas a entrar.
3. **Apply** y esperar a que termine (5–10 minutos la primera vez).
4. En Supabase → **Authentication → Users → Add user → Create new user**: el mismo correo, una contraseña y marcar
   **Auto Confirm User**.
5. Recomendado: en Supabase → Authentication → Sign In / Providers, desactivar el registro de usuarios nuevos.
6. Abrir la dirección del panel e iniciar sesión.

El plan gratuito se duerme tras unos minutos sin uso: la primera visita puede tardar ~1 minuto. La primera estimación de
vacantes también tarda unos segundos mientras lee el catálogo. Detalle técnico: [PANEL_CONTROL.md](PANEL_CONTROL.md) §7.

**Cómo cambiar las vacantes que llegan**

1. **Cargos y cupos**: crear los cargos que quieres (revisar sus denominaciones) y repartir exactamente 120.
2. **Clientes**: cada cargo con cupo necesita al menos un perfil de cliente con sus filtros. Mira la estimación
   «≈ N vacantes guardadas aún no entregadas» o **Estimar con búsqueda en vivo** y usa «Aplicar» si un filtro deja muy pocas.
3. **Programar para mañana**. La versión rige desde el día siguiente en Colombia: si programas antes de la 1:17 a. m.,
   la búsqueda de esa madrugada ya la usa.
4. Desde ese momento **los seis cargos fijos actuales dejan de usarse**: si quieres conservar alguno, créalo en el panel.
5. Al día siguiente, en **Vacantes**, revisa lo que llegó para cada cliente; en **Actividad**, si faltó algo.

## 6. El día de la entrega — en este orden

Reservar unas 2 horas fuera del horario de la nocturna (entre las 9 a. m. y las 10 p. m. de Colombia).

1. **Secretos del destino**: en GitHub crear `SUPABASE_URL_DESTINO` y `SUPABASE_DB_URL_DESTINO` con los datos del
   proyecto nuevo del cliente.
2. **Traspaso real**: Actions → **Traspaso a otro Supabase** → escribir `TRASPASAR` y **desmarcar Ensayo**.
   Esperar el verde. El resumen muestra las filas copiadas. Desde este momento tu base antigua queda detenida: las
   capturas fallarán con el mensaje *Esta base se trasladó…* hasta el paso 3 (es intencional, para no escribir en dos
   bases).
3. **Cambiar tres secretos** por los del proyecto del cliente: `SUPABASE_URL`, `SUPABASE_SECRET_KEY` y
   `SUPABASE_DB_URL`. **No cambiar `SUPABASE_BACKUP_KEY`**: es la que permite leer las copias cifradas.
4. **Comprobar**: Actions → **Preparar Supabase** → Run workflow (verde). Después **Captura horaria** → Run workflow
   sin marcar nada (verde).
5. **Borrar** los secretos `SUPABASE_URL_DESTINO` y `SUPABASE_DB_URL_DESTINO`.
6. **Apify**: cambiar `APIFY_TOKEN` por el del cliente.
7. **Avisos**: crear los secretos `AVISO_…` con el Healthchecks del cliente (sección 4).
8. **Repositorio**: Settings → General → Danger Zone → *Transfer ownership* a la cuenta del cliente. Después, con la
   cuenta del cliente, revisar que los secretos sigan ahí y que Actions esté habilitado.
9. **Panel** (si aplica): configurar el alojamiento con las claves del proyecto del cliente (sección 5).
10. **Tu Supabase antiguo**: no borrarlo durante 2 semanas, por si hiciera falta volver atrás. Después, borrarlo.

**Si algo falla:**
- Falla el paso 2: no cambió nada; tu base sigue operando. Revisar el mensaje y repetir.
- Falla algo después del paso 3: se puede volver atrás poniendo los tres secretos antiguos y, en el SQL Editor del
  Supabase antiguo, ejecutando
  `delete from public.estado_operativo where cola = 'control' and identificador = 'trasladada';`

## 7. Primera semana después de la entrega

| Día | Revisar en Actions |
|---|---|
| Mismo día | Varias capturas horarias en verde |
| Día siguiente | Bodega nocturna en verde; si no, que la pasada de las 7:17 a. m. la complete |
| Primer domingo | Copia de seguridad semanal en verde con su artefacto |
| Toda la semana | Que no lleguen correos de aviso; si llegan, abrir la ejecución indicada |

En Supabase del cliente: Reports → Database, que CPU y Disk IO no estén al 100 % de forma sostenida. Si lo están, subir
el tamaño de cómputo del proyecto (Project Settings → Compute and Disk).

## 8. Límites conocidos (no son fallos del traspaso)

- **Bloqueos de LinkedIn/Indeed al comprobar enlaces.** Solo se entregan vacantes con enlace comprobado; un día con
  muchos bloqueos puede quedar corto. La pasada de la mañana lo reduce, pero no lo puede garantizar.
- **Fuentes externas cambian sin aviso.** Si una fuente deja de responder, bajan las vacantes de algunos cargos.
- **Mientras sigas en el plan gratuito** de Supabase, alguna captura horaria puede fallar por saturación (unas 2 de
  cada 16 en la última medición). No se pierden datos: la siguiente captura reintenta.
- **El panel** necesita alojamiento e inicio de sesión configurados; sin eso, solo funciona en demostración.


## Avisos por correo (Resend) — una sola vez

1. Crear una cuenta en resend.com (idealmente del cliente) y en **Domains → Add domain** escribir el dominio del cliente
   (p. ej. adaptiajobs.com).
2. Resend muestra 3 registros DNS (SPF, DKIM y MX/Return-Path). Añadirlos donde se administra el dominio y pulsar
   **Verify**. Puede tardar unos minutos.
3. **API Keys → Create API key** con permiso de envío. Copiarla una sola vez:
   - GitHub → Settings → Secrets and variables → Actions → **New repository secret**: `RESEND_API_KEY`.
   - Render → el servicio del panel → Environment: `RESEND_API_KEY` (la misma).
4. Remitente, como **variable** (no secreto) en GitHub y en Render: `ALERTAS_REMITENTE` = `Adaptia <alertas@adaptiajobs.com>`.
   Opcional en GitHub: variable `PANEL_URL` con la dirección del panel, para que el correo enlace a él.
5. En el panel → **Actividad → Avisos por correo**: escribir el correo que recibirá los avisos, elegir los tipos,
   **Guardar avisos** y **Enviar correo de prueba**.
