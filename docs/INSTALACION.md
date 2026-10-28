# Instalación

Hay dos niveles. El **básico** deja la página funcionando con dos clics y sin cuentas pagas. Los **opcionales** suben el
volumen (Apify, Brave) o vuelven la página privada y compartida entre equipos (Cloudflare). Ninguna clave se escribe en
el repositorio ni en un chat: todas van en los "secretos" de GitHub o de Cloudflare.

## Básico (gratis, unos 5 minutos)

1. **Fusionar el código en `main`.** En GitHub, abre el pull request de la versión 1 y toca *Merge*. Desde ese momento la
   búsqueda corre sola cada noche a la 1:17 (hora de Bogotá).
2. **Activar la página.** En el repositorio: *Settings → Pages → Build and deployment → Source: Deploy from a branch →
   Branch: `publicado` / `(root)` → Save*. En uno o dos minutos la página queda en
   `https://<usuario>.github.io/<repositorio>/` (GitHub muestra el enlace en esa misma pantalla).
3. **Primera búsqueda completa** (opcional, si no quieres esperar a la noche): *Actions → Bodega nocturna → Run workflow →
   modo `inicial`*. Tarda unos 40 minutos.
4. **Revisar que todo esté bien:** *Actions → Diagnóstico → Run workflow*. El resumen dice qué fuente funciona y qué falta.

Con el nivel básico:
- La página es pública para quien tenga el enlace (no aparece en buscadores: lleva `noindex`). Solo muestra vacantes
  públicas; no hay datos de clientes.
- "Marcar enviadas" se guarda en el navegador de cada equipo. Para pasar el historial a otro equipo: pestaña *Estado →
  Exportar historial* y en el otro *Importar historial*.
- "Buscar en vivo" abre GitHub Actions: allí se toca *Run workflow*, se escribe el cargo y el país, y en unos 15 minutos
  aparece en la página.

## Opcional: más volumen de LinkedIn con Apify

Apify recorre el buscador público de LinkedIn sin que lo bloqueen (nunca con una cuenta: no le des tu cookie a ningún
actor; si un actor la pide, no se usa).

1. Crea una cuenta en https://apify.com y, en *Settings → Integrations*, copia tu **API token**.
2. En *Billing → Limits* pon un **límite de gasto mensual** (sugerido para empezar: USD 50).
3. En GitHub: *Settings → Secrets and variables → Actions → New repository secret* → nombre `APIFY_TOKEN`, valor: el token.
4. Elige el actor: busca en la tienda de Apify un "LinkedIn Jobs Scraper" **sin login ni cookies** y escribe su id
   (por ejemplo `usuario/linkedin-jobs-scraper`) en `datos/config.yaml`, campo `apify.actor_linkedin`. Pídele a Claude
   que compare dos actores con las mismas búsquedas antes de dejar uno (paso 6 del plan).
5. Corre el *Diagnóstico*: debe decir "clave válida; actor: …".

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

## Ajustes sin tocar código

- `datos/config.yaml`: países, días, presupuestos por fuente, actor de Apify.
- `datos/mapa_cargos.yaml`: cargos y sus parecidos (o la skill `nueva-familia`).
- `datos/dominios.yaml`: qué sitios cuentan como original, portal o agregador.
- `datos/empresas_ats.csv`: empresas cuyo portal se lee cada noche (crece sola en `trabajo/empresas_ats.csv`).
- Hora de la búsqueda: `cron` en `.github/workflows/bodega.yml` (está en UTC: Bogotá + 5 horas).
