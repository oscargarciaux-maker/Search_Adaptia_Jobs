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
