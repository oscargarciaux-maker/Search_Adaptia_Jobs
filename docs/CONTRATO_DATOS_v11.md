# Rescate por persona hasta 5 vacantes — v11

Revisión del 12 de noviembre de 2026 (decisiones de Oscar). Amplía v9. Sin SQL nuevo.

## Objetivo

Cada perfil activo (cliente + cargo) debe recibir al menos 5 vacantes al día. Se usa, en este orden, lo que haga falta
y solo para quien le falte; nada de esto rellena con vacantes que no se puedan postular desde su país, en otro idioma
o sin enlace comprobado.

1. Selección normal (filtros del perfil, reparto por turnos entre cargos parecidos).
2. Ampliaciones v9: `sin_dato`, `cargo_cercano`, `remota_cercana`.
3. **Nuevas (último recurso):**
   - `experiencia_cercana`: si el aviso dice años, se admiten hasta 2 de diferencia con el rango del perfil.
   - `empresa_4`: hasta 4 vacantes de la misma empresa (en vez de 2) cuando el cargo no llega a su cupo.
4. **Reutilizar entre personas:** una vacante elegida en los 14 días anteriores (para otro cliente o por el cupo) puede
   asignarse a un perfil que no llega a 5 si cumple sus filtros —con las mismas ampliaciones— y esa persona nunca la
   recibió (ni asignada ni en un mensaje). No cambia `entregas_diarias` ni el cupo de 120: el cupo sigue contando
   vacantes nuevas distintas. Marca en la asignación: `{"reutilizada": "<fecha original>"}`.
5. **Refuerzo gratuito por persona:** las rondas de refuerzo se activan también cuando un cargo cubrió su cupo pero
   algún perfil quedó bajo el mínimo.
6. **Apify dirigido:** en modo panel Apify ya no rota combinaciones a ciegas (`apify_busquedas = 0`). Tras la selección
   provisional, busca solo para los perfiles con déficit —los de más déficit primero— con los términos de su cargo
   (incluidos los cercanos) en su país y en las remotas abiertas a él, hasta `apify.rescate_busquedas` (4) búsquedas
   de 10 resultados. Mismo actor formal, sin cookies, dentro del tope de USD 5/mes (≈60 % del crédito diario; el resto
   queda para publicaciones, segunda parte de v11).

## Apify sin fallos silenciosos

Si Apify responde 401/403 (clave rotada o revocada, como en su incidente de seguridad de noviembre de 2026), la fuente
se detiene, `salud.json` la marca `clave_invalida` y se envía la alerta de **fallo** pidiendo actualizar `APIFY_TOKEN`.

## Reportes

`salud.json` y el resumen del panel solo llevan conteos por cargo: `perfiles_bajo_minimo` y `faltan_para_minimo`, más
`reutilizadas` en la ejecución del panel. Nunca ids de perfil ni datos de clientes.

## Segunda parte: posts de LinkedIn etiquetados «Post»

Decisión de Oscar (12 nov 2026): muchos posts de quien contrata no tienen ficha ni enlace de postulación, pero permiten
contactar directamente a quien publica (mensaje en LinkedIn o correo). Se aceptan como **último recurso**, siempre con la
etiqueta «Post». **Modifica** la regla anterior («un post solo aporta una oferta si se recupera su ficha formal»): esa
regla sigue valiendo para `ofertas` y el cupo; un post sin ficha solo puede llegar como «Post».

### Cuándo se buscan

Solo en modo panel, con `APIFY_TOKEN`, después del rescate formal (punto 6) y solo si algún perfil sigue bajo 5. Actor
`apify.actor_publicaciones` (`harvestapi/linkedin-post-search`, sin cookies ni sesión), hasta `apify.posts_rescate`
(30) posts al día (≈ USD 0,06) con lo que quede del crédito diario. Consultas: `(hiring OR contratando OR vacante OR
buscamos) "<término del cargo>"`, máx. 6, primero los cargos con más déficit. El feed antiguo
(`publicaciones_por_dia`) sigue en 0.

### Filtro estricto, sin IA

Un post entra solo si cumple todo:

1. Anuncia una contratación (`CONTRATA`) y pide hacer algo: postular, enviar el CV, escribir, comentar (`ACCION`) o
   trae un enlace.
2. No es basura (`RUIDO`, `A_FUTURO`): personas que buscan empleo (#OpenToWork, «busco trabajo», «en búsqueda de
   nuevas oportunidades», «open to new opportunities», también en el titular del autor), cursos, webinars y eventos,
   «banco de talento», «base de datos», «talent pool/community», «futuras oportunidades», «te contactaremos», «deja tu
   CV para…», o listas de más de 3 enlaces (vacantes de terceros).
3. Nombra un cargo del mapa (exacto o similar), la empresa (autor empresa o «at/en <Empresa>» en su titular), un país
   activo o trabajo remoto con ubicación positiva, y está en español o inglés.
4. Tiene fecha dentro del plazo (`dias_maximos`) y forma de contacto: el perfil de LinkedIn del autor (`/in/` o
   `/company/`) o un correo del texto.

Si el post enlaza una ficha formal de LinkedIn que se puede leer, se entrega **esa ficha** como vacante normal (sin
etiqueta). Si no, queda como post.

### Campos

- Catálogo (`catalogo_vacantes`, sin SQL nuevo): id `post-<huella>`, `datos.tipo = "post"`, `datos.contacto =
  {perfil, correo}` (solo lo que el post muestra), fuente `LinkedIn (post)`, enlace al post, cargo nombrado, ubicación,
  fecha y `verificacion` con la hora en que Apify lo leyó. Solo los posts llevan `tipo` y `contacto`: el resto del
  catálogo no cambia.
- `contrato.entregable` rechaza siempre un post («no es una oferta formal»): nunca va a `ofertas`, a
  `entregas_diarias` ni al cupo de 120. `contrato.entregable_post` aplica las reglas de arriba.
- Asignación (`panel_asignaciones.explicacion`): `{"tipo": "post"}` (y `{"ampliacion": "sin_dato"}` si el post no dice
  años o inglés). Se asigna solo a perfiles bajo 5 y solo hasta completar 5, nunca dos veces a la misma persona.
- Vigencia: un post no tiene estado de cierre; su lectura vale **24 h** para compartir (las fichas siguen con 6 h). El
  panel solo considera posts leídos en los 2 últimos días.
- Privacidad: los posts traen el perfil o correo de quien publica; viven solo en Supabase privado, nunca en `trabajo/`,
  `salud.json` ni la rama `publicado` (allí solo conteos por motivo de descarte).

### Cómo se muestra

- Panel, «Vacantes»: etiqueta azul «Post» y botón «Contactar a quien publicó» (abre el post); el correo, si existe,
  en «Por qué coincide». No cuenta en la vista previa de «Estimar».
- WhatsApp (borrador y «Copiar WhatsApp»): primero las vacantes formales; los posts van al final, solo completan hasta 5
  y se escriben así: `📣 Post · <Cargo> · <Empresa>` / `Escríbele por mensaje a quien publicó: <enlace>` / `O al
  correo: <correo>`, con una frase que explica qué significa 📣 Post.
