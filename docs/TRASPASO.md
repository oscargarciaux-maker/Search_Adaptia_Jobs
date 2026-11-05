# Traspaso a otra persona

Todo vive en este repositorio y en cuentas que la otra persona crea a su nombre: GitHub, Supabase y Apify (y, si los usa,
Brave y Cloudflare). No hay nada que dependa del Google, el Drive, el Apps Script ni otros repositorios de quien lo
construyó. Al cambiar los secretos, todo funciona igual con las cuentas nuevas.

## Lo que la otra persona necesita

| Cuenta | Para qué | Costo |
|---|---|---|
| GitHub | El código, la búsqueda nocturna y la página | Gratis (repositorio público; privado también sirve, pero GitHub Pages en privado pide plan pago: usar Cloudflare) |
| Supabase | La base de datos con la entrega diaria | Gratis |
| Apify | Publicaciones «contratando» de LinkedIn | Gratis hasta USD 5 al mes |
| Brave, Cloudflare | Opcionales (ver `docs/INSTALACION.md`) | Gratis o casi |

## Pasos

1. **Pasar el repositorio.** Dos opciones:
   - *Transferir* (conserva historial y flujos; el enlace de la página cambia de usuario): *Settings → General → Danger
     Zone → Transfer ownership* → usuario de la otra persona. Ella acepta desde el correo de GitHub.
   - *Copiar como plantilla* (cada uno conserva el suyo): *Settings → General → Template repository*; la otra persona toca
     *Use this template → Create a new repository*. Con esta opción la rama `publicado` no viaja: la primera búsqueda
     empieza de cero (y la memoria de "ya entregadas" también; ver el paso 6).
2. **La otra persona crea su Supabase y su Apify** siguiendo `docs/INSTALACION.md` (secciones 2 y 3). Su base de datos
   empieza vacía; si quiere el histórico, quien entrega exporta la tabla `ofertas` a CSV (*Table Editor → ofertas →
   Export → Export to CSV*) y ella la importa en la suya (*Table Editor → ofertas → Insert → Import data from CSV*).
3. **Poner los secretos nuevos** en *Settings → Secrets and variables → Actions*: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
   `APIFY_TOKEN` (y `BRAVE_API_KEY` si lo usa). Los secretos **no** viajan con el repositorio: si se transfirió, borra los
   viejos y crea los nuevos con los mismos nombres.
4. **Activar Actions** si GitHub lo pide (*Actions → I understand my workflows, enable them*) y **la página** (GitHub
   Pages con la rama `publicado`, o Cloudflare), igual que en `docs/INSTALACION.md`.
5. **Diagnóstico:** *Actions → Diagnóstico → Run workflow*. Debe salir ✅ en Supabase y Apify con las cuentas nuevas.
6. **Primera búsqueda:** *Actions → Bodega nocturna → Run workflow → modo `inicial`* (40–60 minutos). Si el repositorio
   se transfirió, sigue sin repetir lo ya entregado; si se copió como plantilla, empieza una memoria nueva.
7. **Cerrar lo viejo (quien entrega):** revoca sus claves —Supabase (*Project Settings → API Keys → borrar la clave
   secreta* o pausar/borrar su proyecto), Apify (*Settings → API & Integrations → borrar el token*), Brave y Cloudflare—
   y sale como colaborador del repositorio. Desde ese momento nada usa sus cuentas.

## Qué revisar después

- La página abre y la búsqueda de un cargo trae vacantes.
- *Estado → Entrega del día*: fecha de hoy, 20 por rol (o cuántas faltaron) y "Supabase: N filas guardadas".
- En Supabase, *Table Editor → entrega_de_hoy* tiene filas con la fecha de hoy.
- Si algo falla, el *Diagnóstico* dice qué; con Claude, la skill `diagnostico` lo explica.
