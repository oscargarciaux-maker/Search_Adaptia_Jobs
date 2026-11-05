# Instalación

Lo que hace el sistema cada noche (1:17, hora de Bogotá), solo, en GitHub:

1. **Busca** vacantes en LinkedIn (buscador público, sin cuenta), Indeed, los portales de empleo de cientos de empresas,
   Get on Board, tableros remotos y **publicaciones «contratando» de LinkedIn** (con Apify).
2. **Arma la entrega del día:** 20 vacantes **nuevas** (nunca entregadas antes) por cada rol —Product designer, UX/UI
   designer, Product Owner, Product manager, AI Engineer y QA—, variadas en idioma, nivel, país y modalidad, de LATAM y
   España, con las columnas del contrato de datos (`docs/CONTRATO_DATOS_v1.md`).
3. **La guarda** en Supabase, la base de datos obligatoria. El Excel de la entrega anterior ya no se genera automáticamente.
   Las publicaciones del feed de Apify son indicios pendientes de verificar y no se incluyen en la entrega.

Ninguna clave se escribe en el repositorio ni en un chat: todas van en los **secretos** de GitHub
(*Settings → Secrets and variables → Actions → New repository secret*).

Tiempo total de la instalación: unos 30 minutos. Costo: USD 0 (Supabase gratis, Apify gratis con USD 5 al mes de uso).

---

## 1. GitHub (obligatorio)

1. **Cuenta y repositorio.** Este repositorio vive en la cuenta de GitHub de quien lo usa (ver `docs/TRASPASO.md` para
   pasarlo a otra cuenta).
2. **Activar Actions** si GitHub lo pide: pestaña *Actions → I understand my workflows, enable them*.
3. **Activar la página.** *Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `publicado` /
   `(root)` → Save*. La rama `publicado` aparece después de la primera búsqueda (paso 4). En uno o dos minutos la página
   queda en `https://<usuario>.github.io/<repositorio>/` (GitHub muestra el enlace en esa misma pantalla).

## 2. Supabase: la base de datos de la entrega (gratis, 10 minutos)

Supabase guarda cada día las vacantes entregadas en una tabla llamada `ofertas`, con las columnas del contrato. Desde ahí
se consultan las entregas, y ahí las leerá después el bot de WhatsApp. CSV/Excel ya no son la base de datos.

1. **Crear la cuenta:** entra a https://supabase.com → *Start your project* → regístrate (con GitHub o con correo).
2. **Crear el proyecto:** *New project*.
   - *Organization*: la que crea Supabase por defecto (plan *Free*).
   - *Project name*: por ejemplo `vacantes`.
   - *Database password*: toca *Generate a password* y guárdala en un lugar seguro (no se usa en este sistema, pero la
     pide Supabase si algún día necesitas entrar a la base directamente).
   - *Region*: la más cercana, por ejemplo *East US (North Virginia)* o *South America (São Paulo)*.
   - *Create new project*. Tarda uno o dos minutos.
3. **Crear la tabla:** menú izquierdo → *SQL Editor* → *New query*. Abre en GitHub el archivo `supabase/esquema.sql`,
   copia **todo** su contenido, pégalo en el editor y toca *Run*. Debe decir *Success. No rows returned*.
   En *Table Editor* aparece la tabla `ofertas` (vacía) y la vista `entrega_de_hoy`.
4. **Copiar la dirección y la clave secreta:** *Project Settings* (engranaje) →
   - *Data API* (o *API*): copia la **Project URL** (`https://xxxxxxxx.supabase.co`).
   - *API Keys*: en *Secret keys* copia la clave **secreta** (`sb_secret_…`). Si tu proyecto solo muestra las claves
     antiguas, usa la **`service_role`** (no la `anon`). **Nunca** la pegues en un chat, un correo ni en el repositorio.
5. **Guardarlas en GitHub** como dos secretos:
   - `SUPABASE_URL` = la Project URL.
   - `SUPABASE_SECRET_KEY` = la clave secreta.

La tabla tiene la seguridad de filas activada y sin permisos públicos: solo entra quien tenga la clave secreta.

**Capacidad de Supabase:** el plan gratuito anunciado incluye 500 MB; verifica las condiciones vigentes. No se puede
prometer que alcance para años: las descripciones completas y una fila por enlace pueden ocupar bastante espacio.
Revisa el tamaño real y configura copias de seguridad según el plan contratado. La limpieza de 30 días del buscador
no elimina filas de Supabase. Ver `COBERTURA_HISTORICO.md`.

## 3. Apify: fichas formales de LinkedIn, hasta USD 5 al mes

1. Crear una cuenta gratuita en https://console.apify.com/sign-up y comprobar el crédito vigente del plan.
2. Copiar el token desde Settings → API & Integrations → Personal API tokens y guardarlo como secreto `APIFY_TOKEN`
   en GitHub. Nunca pegarlo en un chat ni en el código.
3. El actor configurado es `curious_coder/linkedin-jobs-scraper`, versión `1.7.18`, con permisos limitados y sin sesión personal. Se envían consultas
   de cargos exactos y afines, filtros de ubicación/remoto y límites de resultados y cargo. No se envían cookies.
4. `tope_mensual_usd: 5` reparte reservas entre los días del mes; cada ejecución tiene su propio `maxTotalChargeUsd`.
   Mantener el plan gratuito y los límites de la cuenta. La tarifa pública consultada es aproximadamente USD 2 por
   1.000 ofertas en el plan gratuito más inicio; no significa que todas las ofertas obtenidas sean nuevas, elegibles o entregables.
5. La búsqueda pagada del feed está desactivada (`publicaciones_por_dia: 0`) para dedicar este crédito a ofertas formales.
   Si se habilita, comparte el mismo presupuesto y solo aporta ofertas al poder recuperar sus fichas originales.
6. Diagnóstico → `probar_apify: true` ejecuta una prueba explícita de una sola oferta, con tope USD 0,01 del crédito,
   sin guardar en Supabase. No repetirla innecesariamente: también consume crédito de la cuenta.

Sin token, las otras fuentes continúan; el reporte indica que Apify no pudo usarse. Los detalles del control de gasto
están en `APIFY_LINKEDIN.md`. El presupuesto interno cubre este proyecto, no otros actores ejecutados por fuera.

## 4. Primera corrida y revisión

1. **Antes de la primera corrida:** *Actions → Diagnóstico → Run workflow → solo_supabase: true*. Comprueba
   credenciales y columnas mediante lectura; no crea ofertas de prueba. Esto no demuestra aún permisos de escritura.
2. **Primera búsqueda completa** (para no esperar a la noche): *Actions → Bodega nocturna → Run workflow → modo
   `inicial`*. Tarda entre 40 y 60 minutos. Al terminar, el resumen de la corrida dice cuántas vacantes entregó por rol y
   cuántas filas guardó en Supabase.
3. **Diagnóstico:** *Actions → Diagnóstico → Run workflow*. Debe salir ✅ en *Supabase (entrega diaria)* y en *Apify*.
   ➖ significa "opcional sin configurar"; ❌ dice qué arreglar (por ejemplo, "usa la clave secreta, no la pública").
4. **Ver la entrega:**
   - En la página: pestaña *Estado → Entrega del día*: selección por rol, déficits y estado de sincronización.
     No hay descarga automática de Excel de la entrega con la configuración actual.
   - En Supabase: *Table Editor → entrega_de_hoy* (la más reciente) o *ofertas* (todas). Para Excel: botón *Export →
     Export to CSV*.
   - En GitHub: el resumen debe confirmar la meta y cero pendientes. Un fallo de sincronización o cuota marca la corrida
     como fallida; el estado se conserva para reintentos y en un artefacto de recuperación durante 14 días.

## Cómo funciona la entrega (y qué se puede ajustar sin tocar código)

`datos/entrega.yaml`:
- `exportar_archivos` (false): generación automática del antiguo Excel/CSV desactivada. No es alternativa a Supabase.
- `preferir_remotas` (true): primero remotas de alcance amplio identificado, luego de un país, locales y dudosas.
- `por_rol` (20), `idiomas` (`es` y `en`: el contrato no acepta otros), `max_por_empresa` (2 por rol y día),
  `dias_frescura` (14: solo vacantes vistas por primera vez en esos días).
- `roles`: cada rol junta familias del mapa de cargos (`datos/mapa_cargos.yaml`), con sus cargos exactos, similares y
  cercanos. Para agregar un rol: un bloque nuevo aquí (y la familia en el mapa si no existe).
- `consultas_publicaciones`: búsquedas de Apify.

Reglas fijas (`buscador/entrega.py`, `buscador/contrato.py`):
- **Reintentos a Supabase:** `trabajo/pendientes_supabase.json` conserva las filas aún no confirmadas, incluso si
  falló la conexión durante el envío. Se reintentan sin volver a seleccionarlas otro día y conservando su fecha original.
  Si las credenciales faltan antes de empezar, la ejecución normal se detiene sin iniciar la entrega.
- **Nunca repetidas:** `trabajo/entregadas.json` (en la rama `publicado`) guarda la huella y los enlaces de todo lo
  entregado en los últimos 180 días. Una vacante que ya salió no vuelve a salir aunque siga abierta.
- **Variadas:** dentro de cada rol se toma una por una la que menos se parece a las ya elegidas (idioma, nivel, país,
  modalidad, fuente), prefiriendo las de cargo exacto, con descripción completa y más nuevas.
- **Solo con descripción completa** (el contrato la necesita para detectar copias) y con empresa conocida.
- **Nada inventado:** lo que el aviso no dice queda vacío (moneda de un "$" solo, modalidad si no la dice, sector,
  palabras clave de rol y blandas, resumen: los completa la plataforma con IA).
- Si un día no hay 20 nuevas de un rol, se entregan las que haya y el resumen dice cuántas faltaron.

## Opcional: descubrir más empresas con Brave Search

Brave busca empresas que publican vacantes en Greenhouse, Lever, Ashby o Workable; la bodega las lee gratis cada noche.

1. Crea una cuenta en https://api-dashboard.search.brave.com (pide tarjeta; trae USD 5 de crédito al mes, unas 1.000
   búsquedas) y crea una clave del plan *Search*. Pon un límite de gasto.
2. En GitHub, secreto `BRAVE_API_KEY` con esa clave.

## Opcional: página privada y compartida con Cloudflare (gratis)

Con Cloudflare la página pide iniciar sesión con un correo autorizado, "Marcar enviadas" se comparte entre el computador y
el celular, y "Buscar en vivo" lanza la búsqueda directamente.

1. Crea una cuenta gratis en https://dash.cloudflare.com.
2. *Workers & Pages → Create → Pages → Connect to Git*, elige este repositorio. En la configuración:
   *Production branch: `publicado`*, *Build command:* vacío, *Build output directory:* `/`. Guarda y despliega.
3. **Enviadas compartidas:** *Workers & Pages → KV → Create namespace* llamado `ENVIADAS`. Luego en el proyecto de Pages:
   *Settings → Functions → KV namespace bindings → Add binding*: nombre de variable `ENVIADAS`, namespace `ENVIADAS`.
4. **Buscar en vivo:** en GitHub crea un token (*Settings de tu cuenta → Developer settings → Fine-grained tokens*) con
   acceso solo a este repositorio y permiso **Actions: Read and write**. En el proyecto de Pages: *Settings → Variables and
   Secrets*: `GITHUB_REPO` = `usuario/repositorio` (texto) y `GITHUB_TOKEN_FLUJOS` = el token (secreto).
5. **Privada:** *Zero Trust → Access → Applications → Add an application → Self-hosted*, dominio de la página
   (`<proyecto>.pages.dev`), y una política *Allow* con los correos autorizados (código de un solo uso por correo).
6. Vuelve a desplegar (*Deployments → Retry deployment*) y entra desde el computador y el celular.
7. Si usas Cloudflare, puedes apagar GitHub Pages (*Settings → Pages → Unpublish*) para que solo quede la versión privada.

## Otros ajustes sin tocar código

- `datos/config.yaml`: países (LATAM y España), días, presupuestos por fuente, actor y tope de Apify.
- `datos/mapa_cargos.yaml`: cargos y sus parecidos (o la skill `nueva-familia`).
- `datos/paises.yaml`: países, ciudades y las palabras que abren una vacante remota a LATAM, al mundo o a Europa.
- `datos/dominios.yaml`: qué sitios cuentan como original, portal o agregador.
- `datos/empresas_ats.csv`: empresas cuyo portal se lee cada noche (crece sola en `trabajo/empresas_ats.csv`).
- Hora de la búsqueda: `cron` en `.github/workflows/bodega.yml` (está en UTC: Bogotá + 5 horas).
