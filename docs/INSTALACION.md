# Instalación y configuración del administrador

Actualizado el 5 de noviembre de 2026. Este procedimiento corresponde al catálogo v2 y la verificación pública v3.
Para utilizar una instalación ya operativa, empezar en [GUIA_CLIENTE.md](GUIA_CLIENTE.md): no reemplazar cuentas,
recrear tablas ni repetir la primera carga solo por recibir este manual.

## 1. Elegir instalación nueva o continuidad

- **Instalación nueva:** cuentas/base vacías, nueva memoria de selección y presupuesto propio. Seguir este documento.
- **Continuidad de un negocio existente:** conservar historial, lote, reintentos, memoria de no repetición y reservas Apify.
  Seguir primero [TRASPASO.md](TRASPASO.md). Copiar solo el código no conserva esos datos.
- **Actualización desde la versión anterior:** aplicar `002_catalogo.sql` si falta y revisar
  [ACTIVAR_CAPTURA_HORARIA.md](ACTIVAR_CAPTURA_HORARIA.md). La verificación v3 no añade SQL ni secretos nuevos.
- **Estado operativo duradero:** SQL 003 es una extensión separada de v3. Seguir
  [ACTIVAR_ESTADO_OPERATIVO.md](ACTIVAR_ESTADO_OPERATIVO.md) para conservar reservas/pendientes en Supabase.

No se promete una instalación de treinta minutos ni costo total cero. Los tiempos dependen de las cuentas y permisos;
los límites gratuitos y precios se comprueban en cada proveedor.

## 2. Cuentas y responsables

| Servicio | Necesidad | Qué debe controlar el cliente |
|---|---|---|
| GitHub | Obligatorio para la automatización actual | Propiedad del repositorio, Actions, variables, secretos y recuperación de acceso |
| Supabase | Obligatorio para persistencia/entrega | Organización/proyecto, SQL Editor administrativo, claves y respaldos |
| Apify | Necesario si se quiere el refuerzo formal LinkedIn | Cuenta, crédito/ciclo, actor y límite global de consumo |
| GitHub Pages o Cloudflare Pages | Elegir alojamiento | URL del sitio, acceso y despliegue |
| Brave Search | Opcional | Clave, condiciones y presupuesto independiente |

Cada responsable debe tener acceso con su propia cuenta y los permisos mínimos necesarios. Una invitación al
repositorio no concede automáticamente administración de Supabase o Apify. Activar recuperación y segundo factor
según las opciones de las cuentas. No poner claves en archivos, tickets, capturas de pantalla o conversaciones.

## 3. Preparar GitHub sin activar procesos a medias

1. Transferir o crear el repositorio siguiendo el procedimiento elegido. Si se copia una plantilla, comprobar qué ramas
   se incluyeron; no asumir que `publicado` y su memoria viajaron.
2. En **Actions**, habilitar el servicio si aparece la solicitud. En una instalación nueva, dejar temporalmente
   deshabilitados **Bodega nocturna** y **Captura horaria** mientras se preparan base y secretos: abrir el flujo,
   menú `… → Disable workflow`. No hace falta deshabilitar **Pruebas**.
3. Confirmar que `main` contiene el código aprobado. Las pruebas de Python, JavaScript y SQL deben estar aprobadas.
4. Determinar si el repositorio será público o privado. GitHub Pages es público salvo capacidades específicas del plan;
   proteger una página de Cloudflare no hace privados los archivos de un repositorio público.
5. No cambiar permisos generales a escritura si un flujo ya declara sus permisos. Si existe una restricción de
   organización que bloquea `contents`, `pages` o Actions, el administrador debe resolverla explícitamente.

## 4. Crear o preparar Supabase

1. Entrar en [Supabase](https://supabase.com/), con la cuenta del cliente, y crear un proyecto si no existe.
2. Guardar la contraseña administrativa en un gestor seguro. Es distinta de la clave REST del scraper y se necesita
   para ciertas tareas de respaldo/restauración. No se guarda en GitHub como parte de este programa.
3. En **SQL Editor → New query**, ejecutar completo [supabase/esquema.sql](../supabase/esquema.sql).
4. Después ejecutar completo [supabase/migraciones/002_catalogo.sql](../supabase/migraciones/002_catalogo.sql).
5. Comprobar en **Table Editor** las tablas `ofertas`, `catalogo_vacantes`, `entregas_diarias` y la vista `entrega_de_hoy`.
6. En la configuración de API obtener **Project URL** y una **secret key** `sb_secret_…`, o la clave antigua
   `service_role` si es lo disponible. No utilizar `anon`/publishable para estos procesos.
7. En **GitHub → Settings → Secrets and variables → Actions → Secrets**, crear:

   | Nombre exacto | Contenido |
   |---|---|
   | `SUPABASE_URL` | Project URL del proyecto que acaba de prepararse |
   | `SUPABASE_SECRET_KEY` | Secret key o service_role de ese mismo proyecto |

Los scripts SQL son aditivos e idempotentes para el esquema previsto; no son un mecanismo para convertir cualquier
base ajena. Ante tablas preexistentes con columnas diferentes, respaldar y revisar con un técnico antes de ejecutar.
Las tablas quedan con RLS y acceso de servicio, sin acceso público de lectura/escritura para anon/authenticated.

La clave REST no permite ejecutar migraciones SQL arbitrarias. Tenerla configurada no sustituye los pasos del SQL Editor.
La versión pública v3 guarda `verificacion` dentro de `catalogo_vacantes.datos`; su sobre SQL sigue siendo v2.

## 5. Configurar Apify sin superar el presupuesto acordado

1. Crear o elegir la cuenta de [Apify](https://console.apify.com/) que pagará el servicio. Comprobar crédito, ciclo,
   método de cobro y límites reales del plan actual.
2. Obtener un token limitado a lo necesario y guardarlo en GitHub como secreto `APIFY_TOKEN`.
3. Comprobar en `datos/config.yaml`: actor `curious_coder/linkedin-jobs-scraper`, build `1.7.18`,
   `tope_mensual_usd: 5`, `tope_consulta_usd: 0.025`, `publicaciones_por_dia: 0`.
4. No proporcionar sesión/cookies de LinkedIn ni habilitar otro actor por parecido de nombre. Un cambio de actor necesita
   adaptar y probar su esquema, permisos y tarifa.
5. Conservar `trabajo/apify_presupuesto.json`. En modo legado es el contador; con SQL 003/estado central activo es una
   copia auxiliar del registro Supabase. La primera activación importa el corte y no debe asumir saldo vacío.
6. Revisar el uso global en Apify: otros programas y la prueba explícita del actor pueden consumir la misma cuenta.

La nocturna y las búsquedas profundas pueden usar este refuerzo, compartiendo el límite del proyecto. La captura horaria
no ejecuta Apify. El diagnóstico general valida la cuenta sin lanzar el actor; `probar_apify=true` sí puede consumir hasta
USD 0,01 y no forma parte de las reservas normales. No repetir esa prueba sin necesidad.

El máximo de USD 5 corresponde a Apify de este proyecto; no es un precio total garantizado de GitHub, base, alojamiento,
Brave o futuro WhatsApp. Tarifas, reservas y límites: [APIFY_LINKEDIN.md](APIFY_LINKEDIN.md).

## 6. Variables de activación: no son secretos

En **Settings → Secrets and variables → Actions → Variables**, utilizar estos nombres y valores literales:

| Variable | Valor | Efecto |
|---|---|---|
| `CAPTURA_HORARIA_ACTIVA` | `true` | Habilita el horario y el catálogo v2 de la nocturna |
| `ESTADO_SUPABASE_ACTIVO` | `true`, solo tras SQL 003 y corte/importación | Centraliza presupuesto, pendientes y lote sin confirmar; ver guía específica |
| `PAGES_POR_ACTIONS` | `true` para GitHub Pages; `false` o ausente para Cloudflare | Habilita el despliegue explícito de Pages |

Crear `CAPTURA_HORARIA_ACTIVA=true` solo después del SQL. Para el primer arranque mantener el flujo **Captura horaria**
deshabilitado hasta completar la primera carga: así la nocturna puede usar v2 sin intercalar otra captura a medias.
Dejar inicialmente `PAGES_POR_ACTIONS=false` mientras todavía no existe `publicado`; se activa al configurar la página.
`CATALOGO_ACTIVO` es un parámetro interno que la nocturna recibe de la primera variable, no una tercera variable que
el cliente deba crear.
La variable de estado central permanece ausente/apagada hasta seguir su guía. Fusionar su código no migra la base.
Para una instalación nueva que lo use, aplicar también 003 e inicializar expresamente como indica esa guía.

## 7. Diagnóstico y primera captura

1. **Actions → Diagnóstico → Run workflow → main → solo_supabase=true**, dejando `probar_apify=false`.
   Es una lectura de conexión/columnas de `ofertas`; no demuestra escritura ni comprueba por sí sola todo el catálogo v2.
2. Opcionalmente ejecutar Diagnóstico general para comprobar fuentes/cuenta. Un Brave no configurado es opcional;
   un Supabase obligatorio fallido debe resolverse antes de operar. Un resultado de una fuente no acredita todo el mercado.
3. Habilitar **Bodega nocturna** desde su menú si estaba deshabilitada.
4. Ejecutar **Run workflow → main → modo=diario → prueba=true**. No escribe ofertas ni actualiza `publicado`.
   Puede dejar artefactos temporales en el runner; no demuestra persistencia real.
5. Para una instalación nueva, ejecutar una sola primera captura **modo=inicial → prueba=false**. Para continuidad de
   un negocio, usar la memoria restaurada y el modo acordado; no hacer una carga vacía que pierda la historia.
6. Esperar a que termine. El límite del trabajo nocturno es 95 minutos; una corrida observada duró 38,7 minutos, pero
   no es una duración fija. No lanzar varias por impaciencia: pueden ponerse en cola, consumir presupuesto y complicar el diagnóstico.
7. En el resumen comprobar cantidades por rol, faltantes, calidad de enlaces y sincronización. En v2 debe confirmarse
   también el catálogo y `entregas_diarias`, no solo `ofertas`. Si no alcanza la meta, conservar el reporte y revisar motivos.
8. En Supabase, comprobar filas reales en las tres tablas. `entrega_de_hoy` muestra la fecha máxima disponible,
   que puede ser de un día anterior: mirar la fecha, no solo el nombre de la vista.

`modo=inicial` amplía la recolección/reinicia rotación; no es una autorización para borrar presupuesto, no repetición
ni histórico. `prueba=true` tampoco sirve para evaluar la continuidad de siete días reales.

## 8. Elegir y activar la página

### GitHub Pages

1. Cuando exista `publicado`, abrir **Settings → Pages → Build and deployment → Source → GitHub Actions**.
2. Crear/cambiar `PAGES_POR_ACTIONS=true`.
3. Revisar el entorno `github-pages` y sus restricciones: permitir la rama `main`, donde se ejecuta el flujo.
4. **Actions → Actualizar página → Run workflow → main** para la primera publicación explícita.
5. Abrir la URL que muestre Pages y comprobar que la hora de Estado coincide con `publicado/datos/salud.json`.

No elegir «Deploy from a branch»: los commits hechos por el token de Actions no disparan ese mecanismo de reconstrucción.
La publicación nueva empaqueta solo interfaz y datos públicos; no necesita poner una clave Supabase en el navegador.

### Cloudflare Pages y acceso privado (opcional)

1. Conectar el repositorio a Cloudflare Pages, rama de producción `publicado`, sin compilación y directorio de salida `/`.
2. Dejar `PAGES_POR_ACTIONS=false` y comprobar un despliegue de Cloudflare con esa rama.
3. Para acceso restringido, configurar Cloudflare Access con los correos autorizados. Comprobar también los dominios
   alternativos/preview según su configuración; no basta con ocultar la URL principal.
4. Probar en una sesión autorizada y en incógnito que la página y sus rutas `/api/` respetan el acceso previsto.
5. Para marcas compartidas, crear KV y enlazarlo como `ENVIADAS`. Es un historial común de operadores, no por candidato.
6. Para búsqueda profunda desde la página, configurar `GITHUB_REPO` como `usuario/repositorio` y el secreto
   `GITHUB_TOKEN_FLUJOS`, con acceso a ese repositorio y permiso Actions de lectura/escritura. Las funciones asumen
   que Access protege el sitio; no dejarlas abiertas a terceros.
7. Si el negocio requiere privacidad, revisar también la visibilidad del repositorio y la otra URL de Pages. Access no
   protege los archivos de una rama pública de GitHub. No cambiar ni apagar una URL usada por clientes sin coordinarlo.

GitHub Pages no ejecuta las Functions de Cloudflare: allí las marcas son locales al navegador y la búsqueda profunda
se lanza mediante Actions. Elegir alojamiento por necesidad real; no prometer las funciones de Cloudflare en Pages.

## 9. Activar el horario y verificar el ciclo completo

1. Confirmar el SQL y `CAPTURA_HORARIA_ACTIVA=true`; habilitar **Captura horaria** si estaba deshabilitada.
2. Ejecutar una captura con `prueba=true` si se desea comprobar fuentes sin escritura. Para verificar persistencia,
   ejecutar una con `prueba=false` o esperar la programada.
3. Confirmar que sus pasos de captura, sincronización y actualización de la rama se ejecutaron; «skipped» no es una prueba real.
4. Confirmar el despliegue posterior y la hora en la página. Un flujo de página puede correr tras una prueba y volver
   a publicar los datos previos: mirar la hora del dato, no solo que hubo un despliegue verde.
5. En la primera versión con control de enlaces habrá ofertas pendientes mientras se revisa por lotes. No declararlas
   comprobadas ni reenviar el lote antiguo solo porque tenía 20 por rol antes de la auditoría.
6. Completar [ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md) y acordar responsables, alertas y respaldo.

La nocturna solicita inicio a la 1:17 a. m. de Bogotá; la horaria, al minuto 23. GitHub puede retrasar/saltar ejecuciones.
La configuración horaria efectiva es el `cron` de los flujos en UTC; `hora_bodega_bogota` es informativo.

## 10. Opcionales, límites y documentación que se entrega

Brave se habilita únicamente si se necesita búsqueda web adicional, guardando `BRAVE_API_KEY` y revisando su plan y gasto.
No es obligatorio para usar las fuentes existentes. No se garantiza gratuidad de opciones de terceros ni de futuros canales.

Entregar al operador [GUIA_CLIENTE.md](GUIA_CLIENTE.md), al administrador [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md),
y a ambas partes [TRASPASO.md](TRASPASO.md) y [ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md). `PLAN.md` es histórico,
no un instalador vigente. Guardar por separado las referencias de cuentas y los secretos en un gestor seguro.
