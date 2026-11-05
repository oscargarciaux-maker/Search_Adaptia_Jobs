# Activar el catálogo y la captura horaria

El código debe estar fusionado en `main`. La automatización horaria permanece desactivada hasta completar estos pasos.
No hace falta volver a crear el proyecto de Supabase ni cambiar sus claves existentes.
Para una cuenta nueva seguir [INSTALACION.md](INSTALACION.md); para operar o transferir, [GUIA_CLIENTE.md](GUIA_CLIENTE.md)
y [TRASPASO.md](TRASPASO.md). No repetir la activación si ya está comprobada en esa instancia.

1. En **Supabase → SQL Editor → New query**, ejecutar todo
   [`supabase/migraciones/002_catalogo.sql`](../supabase/migraciones/002_catalogo.sql). Se crean
   `catalogo_vacantes` y `entregas_diarias` con permisos privados. `ofertas` y sus datos existentes permanecen.
   No basta con ejecutar la migración en una base temporal. La clave REST del scraper no permite aplicar SQL.
2. Si se usa GitHub Pages (como el sitio revisado), en **Settings → Pages → Build and deployment → Source** elegir
   **GitHub Actions**. Crear la variable de Actions `PAGES_POR_ACTIONS=true`. El flujo **Actualizar página** despliega
   explícitamente después de las capturas; también se puede ejecutar manualmente. Si el entorno `github-pages` tiene
   restricciones de rama, permitir `main`, donde se ejecuta este flujo. Para Cloudflare Pages, conservar su conexión a
   `publicado` y dejar esta variable desactivada.
3. En **GitHub → Settings → Secrets and variables → Actions → Variables → New repository variable**, crear
   `CAPTURA_HORARIA_ACTIVA` con valor `true`. Es una variable, no una contraseña. También activa el catálogo v2 de la
   captura nocturna. Los secretos Supabase existentes se reutilizan.
4. En **Actions → Captura horaria → Run workflow**, dejar `prueba` activado para comprobar fuentes sin escribir;
   después ejecutar con `prueba` desactivado para verificar persistencia real. Comprobar permisos, cero pendientes en
   `Estado`, filas privadas en las tablas nuevas y actualización de la página que usan los clientes.

La captura automática intenta ejecutarse cada hora al minuto 23, todos los días. La selección nocturna se conserva:
la captura horaria actualiza el catálogo, no elige otras 120 ni envía mensajes. La nocturna y las búsquedas profundas
pueden usar Apify con el tope mensual compartido de USD 5. GitHub puede retrasar ejecuciones; no equivale a recepción
inmediata desde LinkedIn.

La página consulta si hay una nueva captura cada minuto cuando está abierta. Comprobar que **Actualizar página**
termina y que la URL real muestra la misma hora que `publicado/datos/salud.json`. Un push hecho por `GITHUB_TOKEN` no
activa por sí solo el Pages anterior; por eso se añade ese despliegue. No dar por actualizada la web solo porque la
captura terminó. El artefacto Pages contiene solo los archivos de interfaz y sus datos públicos, sin `trabajo/`.

## Comprobación antes de WhatsApp

Dejar correr siete días distintos y revisar los reportes diarios: 20 **nuevas por rol**, no 120 sumadas de cualquier
cargo ni 20 repetidas. Un déficit permanece visible; la antigüedad desconocida se declara y no se rellena con basura.
El filtro de últimas 2/6/24 horas solo incluye publicaciones con hora comprobable. Las ofertas con solo fecha siguen
en el catálogo general.

En un directorio recuperado de `publicado`, ejecutar:

```bash
python -m buscador.validacion --salida salida --catalogo
python -m buscador.preparacion --salida salida
```

Consultar [la revisión y sus límites](REVISION_PRODUCTO.md). No borrar registros antiguos para simular novedades.
Las colas `pendientes_catalogo.json`, `pendientes_registro.json`, `pendientes_supabase.json` y el lote diario quedan en
`trabajo/` y se conservan para reintentar. Los fallos de sincronización marcan la ejecución como fallida después de
guardar el estado recuperable.

Para detener solo el horario automático, cambiar la variable a `false`. Los datos ya guardados no se eliminan.
La entrega nocturna vuelve al camino v1; no desactivar v2 como práctica habitual porque su recuperación desde Supabase
y su registro de selección dependen de que esté activo. Ante errores, conservar colas y corregir la causa.
