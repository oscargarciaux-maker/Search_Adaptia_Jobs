# Auditoría de exposición — qué ve cualquiera porque el repo es público

Fecha: 27 nov 2026. Solo lectura: no se cambió código, workflows ni configuración. Este informe **no copia ningún
dato real**: solo dice qué tipo de dato hay y dónde.

## Resumen

- **No se encontraron datos de clientes** (nombres, teléfonos, correos, perfiles, salarios, texto de mensajes) **ni
  claves expuestas** en logs, rama `publicado`, artefactos, sitio de Pages ni historial de git.
- Lo que sí queda a la vista: **lo que busca el negocio por cargo** (nombre del cargo, meta diaria, países y la lista
  exacta de vacantes elegidas hoy), **copias cifradas de toda la base** descargables 90 días, y **el sitio viejo de
  GitHub Pages sigue publicado** (el contrato lo prohíbe).
- Hallazgos de gravedad **alta: ninguno**. Recomendación: **público pero limpio** (detalle al final).

## Tabla de superficies

| # | Superficie | Qué se expone | Gravedad | Arreglo propuesto |
|---|---|---|---|---|
| 1 | Artefactos `respaldo-semanal`, `respaldo-antes-de-limpiar`, `respaldo-traspaso` (90 días) y `respaldo-instalacion-*` (14 días) | **Copia de toda la base, incluidos clientes**, pero cifrada (AES-256-GCM; se comprobó cabecera propia y entropía 8,0 bits/byte en una copia). Cualquiera con cuenta de GitHub puede bajar el archivo cifrado. Si `SUPABASE_BACKUP_KEY` se filtrara un día, todas las copias vigentes quedarían legibles. Hoy hay 11 copias vivas (~510 MB). | Media | Guardar las copias fuera de Actions (bucket privado o Storage de Supabase) o bajar la retención; rotar la clave si alguna vez se sospecha fuga; documentar dónde vive la clave. |
| 2 | Rama `publicado` → `datos/salud.json` (`seleccion_actual`, `entrega`, `historico_entregas`) y `trabajo/lote_entrega.json`, `metricas_entrega.json` | Por cada cargo del panel: ID interno (UUID de Supabase), nombre del cargo, meta diaria, reparto por país/idioma/nivel, número de perfiles bajo su meta y **la lista exacta de vacantes elegidas hoy**. No hay nombres ni contactos, pero un cargo con meta muy baja y un solo país permite deducir qué recibe un cliente concreto. | Media | Publicar solo cifras agregadas (sin nombre de cargo ni lista de vacantes por cargo) o reemplazar el nombre por un alias; mover `seleccion_actual` y el lote a un lugar privado (Supabase). |
| 3 | GitHub Pages (`pages-build-deployment`, fuente: rama `publicado`) | El sitio web viejo **sigue en línea** y sirve una foto del 4–5 nov (modo heredado, seis cargos fijos) con `datos/salud.json`. Sin datos de clientes, pero es una superficie que el contrato prohíbe reintroducir y cualquier archivo nuevo en `publicado` con ruta servible podría quedar publicado si Pages vuelve a construir. | Media | Desactivar Pages en Settings → Pages (decisión de Oscar; no se tocó). |
| 4 | Artefactos `estado-bodega-*` y `estado-captura-*` (14 días, ~1,2 GB vivos) | Lo mismo que `publicado/trabajo/` más claves de caché del tipo `cargo:<UUID>@<país o modalidad>`: qué cargo se busca en qué país o con qué modalidad. Más la bodega completa (unas 12 000 vacantes con descripción). | Media (mismo dato que #2) | Igual que #2: quitar el nombre/UUID del cargo de las claves públicas o subir el estado cifrado como ya se hace con los respaldos. |
| 5 | Bodega (`trabajo/bodega.json.gz`, `verificacion_enlaces.json`, en `publicado` y artefactos) | Correos y teléfonos **de reclutadores**, copiados de la descripción pública de los avisos (cientos de correos, unas 30 cifras con forma de teléfono). No son clientes. | Baja | Aceptable (ya son públicos en el portal); opcional: recortar correos/teléfonos de `_descripcion` antes de publicar. |
| 6 | Logs de Actions (revisadas: bodega 46001755920, 45941716018, 45909439317; «Buscar ahora» con enfoque `faltantes` 44571863208 y 44367042934 — en las últimas 40 corridas manuales no hubo enfoque `pedido`; captura 46001732054, 45931389597, 45890014494; reloj 46004553053, la única que existe; mensajes 45913333211, 45722749367, 45513788190) | Secretos siempre como `***`. Sin correos, teléfonos, URLs de Supabase, JWT ni tokens parciales; los únicos UUID son del runner de GitHub. Sí se ve: el número de perfiles bajo su meta y el de borradores de WhatsApp generados (cifras), tiempos y volumen por fuente. El paso «Comprobar meta» imprime nombre del cargo y cuántas faltaron. | Baja | Aceptable. Opcional: no imprimir el nombre del cargo en el paso de meta. |
| 7 | Resúmenes de corrida (`GITHUB_STEP_SUMMARY`) | Revisado el código que los escribe (`inventario`, `diagnostico`, `limpiar_fuera_objetivo`, `validacion`, `preparar`, `traspaso`): solo cifras, nombres de objetos de la base y tablas por cargo; ninguna fila de clientes. | Baja | Ninguno. |
| 8 | Artefacto `listado-para-revisar` (30 días) | Vacantes propuestas para borrar: título, empresa, ubicación, enlace, si se entregó. Sin clientes. | Baja | Ninguno. |
| 9 | Historial de git (396 commits, todas las ramas) | Sin claves (JWT, `sb_secret_`, URL de Postgres con contraseña, tokens de GitHub/Apify, `li_at`, claves privadas). Solo teléfonos y `wa.me` **ficticios** de pruebas (`pruebas/panel/`, `web/tests/`, ejemplos en `panel/`). `panel/.env.example` siempre vacío. Los correos encontrados están solo en el commit único de `publicado` y son de reclutadores (#5). | Baja | Ninguno. |
| 10 | `claude.yml` (se dispara con «@claude» en issues/comentarios) y `claude-code-review.yml` (PR) | En repo público cualquiera puede abrir un issue con «@claude». La acción de Claude por defecto rechaza a quien no tiene permiso de escritura y los PR de forks no reciben secretos, así que el riesgo es de abuso o ruido, no de fuga. No se comprobó en una corrida. | Baja | Opcional: añadir en el `if:` un filtro por `author_association` (OWNER/MEMBER/COLLABORATOR). |
| 11 | Código y `datos/` (estrategia) | Fuentes usadas, actores de Apify, reglas de afinidad y ubicación, `empresas_ats.csv` (empresas y su sistema de postulación), mapa de cargos, contrato completo. Alguien podría copiar el método. | Baja | Riesgo aceptable: el valor está en la operación y los clientes, no en la lista de fuentes, que son portales públicos. |

## Artefactos: qué se sube y cuánto dura

| Artefacto | Contenido | Retención | Vivos hoy |
|---|---|---|---|
| `estado-bodega-*`, `estado-captura-*`, `estado-profunda-*` | `salida/trabajo/` en claro | 14 días | 127, ~1,2 GB |
| `respaldo-semanal-*`, `respaldo-antes-de-limpiar-*`, `respaldo-traspaso-*` | `.enc` cifrado | 90 días | 5, ~223 MB |
| `respaldo-instalacion-*` | `.enc` cifrado (acción `preparar-supabase`) | 14 días | 6, ~287 MB |
| `listado-para-revisar` | `revision.csv` / `revision.html` | 30 días | 5, <1 MB |
| `panel-navegador` | capturas de Playwright si fallan las pruebas (datos `--demo`) | 7 días | 5, ~9 MB |

Total vivo: unos 1,7 GB.

## Costo de pasar a privado

Datos medidos con la API de Actions, del 20 al 27 nov (170 corridas, 415 trabajos, cada trabajo redondeado al minuto
siguiente, como cobra GitHub):

| Workflow | Corridas en 7 días | Minutos facturables en 7 días |
|---|---|---|
| Bodega nocturna (incluye «Buscar ahora») | 43 | 1 644 |
| Pruebas (CI) | 76 | 642 |
| Captura horaria | 21 | 267 |
| Resto (Claude, mensajes, preparar, respaldo, Dependabot, reloj) | 30 | 33 |
| **Total** | **170** | **2 586** |

- **Como se usó esta semana:** 2 586 × 30/7 ≈ **11 100 min/mes**.
- **Con el reloj funcionando como está diseñado** (la captura cada hora en vez de 2–4 veces al día, ~13 min cada una,
  más un relevo de ~1 min cada 30 min): ~7 050 bodega + ~9 400 captura + ~1 450 reloj + ~2 750 pruebas + ~150 resto ≈
  **20 800 min/mes**.

Precio oficial (docs.github.com, *GitHub Actions billing* y *Actions runner pricing*, consultados el 27 nov 2026):
el plan Free incluye **12 USD de cómputo al mes** (≈ 2 000 min de Linux), Linux 2-core cuesta **0,006 USD/min**, cada
trabajo se redondea al minuto, y el almacenamiento de artefactos incluye 500 MB y cuesta 0,25 USD por GB al mes.
Sin método de pago, al acabarse lo incluido **las corridas se bloquean**.

| Escenario | Minutos extra | USD/mes |
|---|---|---|
| Uso de esta semana | ~9 100 | **≈ 55 USD** |
| Reloj activo | ~18 800 | **≈ 113 USD** |
| Artefactos (~1,2 GB por encima de 500 MB) | — | ≈ 0,3 USD |

**Además, pasar a privado rompe dos cosas que el dinero de los minutos no arregla** (misma documentación):

1. **El reloj deja de funcionar:** «en los planes Free, Pro o Team, los temporizadores de espera solo están
   disponibles en repositorios públicos». `reloj.yml` depende del temporizador de 30 min del entorno `reloj`; en
   privado haría falta GitHub Enterprise (21 USD/usuario/mes según github.com/pricing) o rehacer el reloj de otra forma.
2. Los secretos de entorno tampoco existen en privado con Free, y Pages (que de todas formas debe apagarse) tampoco.

## Recomendación

**Público pero limpio.** No hay datos de clientes ni claves a la vista. Pasar a privado costaría unos 55–113 USD al
mes en minutos y además rompería el reloj (necesitaría Enterprise o rediseño). Para quedar limpio bastan tres
arreglos, en este orden:

1. Apagar GitHub Pages (#3).
2. Dejar de publicar el detalle por cargo — nombre, UUID, meta y lista de vacantes elegidas — en `publicado` y en los
   artefactos de estado (#2, #4): solo cifras agregadas, o subir ese estado cifrado como los respaldos.
3. Sacar las copias cifradas de la base de los artefactos públicos o acortar su retención, y dejar escrita la custodia
   de `SUPABASE_BACKUP_KEY` (#1).

Opcionales: filtrar quién puede disparar `claude.yml` (#10) y recortar contactos de reclutadores de la bodega
publicada (#5).
