# Traspaso a otra persona

Todo vive en este repositorio y en cuentas que la otra persona crea a su nombre. No hay nada que dependa del Google, el
Drive ni el Apps Script de quien lo construyó. Los datos se reconstruyen solos en la primera noche.

## Pasos

1. **La otra persona crea sus cuentas:** GitHub (obligatoria) y, si los va a usar, Apify, Brave y Cloudflare, con sus
   propios límites de gasto (ver `docs/INSTALACION.md`).
2. **Pasar el repositorio.** Dos opciones:
   - *Transferir* (conserva historial, flujos y el enlace de GitHub Pages cambia de usuario): *Settings → General → Danger
     Zone → Transfer ownership* → usuario de la otra persona. Ella acepta desde el correo de GitHub.
   - *Copiar como plantilla* (cada uno conserva el suyo): *Settings → General → Template repository*; la otra persona toca
     *Use this template → Create a new repository*.
3. **Poner los secretos de nuevo** en *Settings → Secrets and variables → Actions*: `APIFY_TOKEN` y `BRAVE_API_KEY` (si los
   usa). No des por hecho que viajan con el repositorio.
4. **Activar Actions** si GitHub lo pide (*Actions → I understand my workflows, enable them*).
5. **Activar la página:** GitHub Pages con la rama `publicado` o Cloudflare, igual que en `docs/INSTALACION.md`.
6. **Primera bodega:** *Actions → Bodega nocturna → Run workflow → modo `inicial`* (unos 40 minutos).
7. **Diagnóstico:** *Actions → Diagnóstico → Run workflow*. Todo en ✅ o ➖ (opcional sin configurar).
8. **Historial de enviadas (opcional):** quien lo entrega lo exporta en *Estado → Exportar historial* y la otra persona lo
   importa en su página.
9. **Cerrar lo viejo:** quien lo entrega revoca sus tokens (GitHub, Apify, Brave) y sale como colaborador.

## Qué revisar después

- La página abre y la búsqueda de un cargo trae vacantes.
- La pestaña *Estado* muestra la fecha de la última búsqueda (debe ser de esta noche).
- Si algo falla, el *Diagnóstico* dice qué; con Claude, la skill `diagnostico` lo explica.
