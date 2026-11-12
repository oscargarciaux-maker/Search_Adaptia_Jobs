# Ubicaciones extranjeras reconocidas y limpieza revisada de `ofertas` — v13

Revisión del 12 de noviembre de 2026 (pedido de Oscar). Amplía v12. Sin SQL nuevo.

## Objetivo de la base

Vacantes que una persona de LATAM o España puede aprovechar:
- presenciales o híbridas en un país cubierto;
- remotas abiertas a algún país cubierto;
- escritas en español o inglés.

No sirven:
- presenciales o híbridas fuera de LATAM y España (por ejemplo, Rumania o Francia);
- remotas solo para otros países;
- avisos en otros idiomas.

## Lo que se encontró

Del inventario del 12 nov, 3.817 vacantes tenían la ubicación «por confirmar» aunque muchas eran claramente extranjeras.
LinkedIn y los portales las escriben de tres formas que no se reconocían:
- en español: «Reino Unido», «Francia», «Rumania», «Singapur»;
- con un código de país al final: «Bucharest, ro», «Bristol, gb»;
- con un estado de EE. UU.: «San Jose, CA».

Con estas reglas, 1.462 se resuelven, sin que ninguna vacante válida de LATAM o España cambie de país. También había
avisos en francés que se tomaban como español o inglés.

## Reglas nuevas

1. **`datos/paises.yaml → fuera_de_latam`.** Añade nombres en español de países, regiones y ciudades frecuentes, y el
   marcador `pais extranjero`. Se dejaron fuera los nombres que también existen en LATAM: El Cairo (Colombia),
   Casablanca (Chile), Roma (Ciudad de México), Valencia y Granada.
2. **Código final** (`paises._expandir_codigos`), en cada tramo separado por `;` o `|`:
   - En minúsculas es un código de país: el de un país cubierto se lee como ese país («Barcelona, es» → España); uno
     extranjero, como «pais extranjero».
   - En mayúsculas, un estado de EE. UU. es extranjero. Si el código también es de un país cubierto (CO, AR, PA), solo
     se lee como ese país cuando la ciudad es de allí («Bogotá, CO» → Colombia); si no, queda «por confirmar»
     («Conshohocken, PA»).
3. **Idioma** (`etiquetas.idioma`): también reconoce francés, alemán e italiano (`fr`, `de`, `it`) por sus palabras
   propias. Siguen sin poder entregarse: solo `es` y `en`.

## Revisión y limpieza de `ofertas`

Flujo manual **«Revisar y limpiar vacantes fuera del objetivo»** (`.github/workflows/limpiar_fuera_objetivo.yml`,
`buscador/limpiar_fuera_objetivo.py`). Reemplaza al flujo de v12, cuyas reglas incluye.

Cada fila de `ofertas` se juzga con las reglas vigentes. Se usa la vacante completa del catálogo (descripción
incluida) o, si no hay catálogo, las propias columnas de la fila (`location`, `work_mode`, `posting_language`). Cada
fila queda en uno de tres grupos:

| Grupo | Motivo | Al aplicar |
|---|---|---|
| **Propuestas para borrar** | escrita en portugués, francés, alemán o italiano; presencial o híbrida fuera de LATAM y España; presencial o híbrida en Brasil; remota solo para otros países; solo para Brasil | Se borran, salvo los números en «conservar» |
| **Para revisar a mano** | ubicación sin confirmar | No se borran, salvo los números en «borrar_tambien» |
| (no aparece) | cumple el objetivo | Se conserva |

1. **Revisar** (sin marcar «aplicar»): no cambia nada.
   - Deja `revision.html` (con enlaces a cada aviso) y `revision.csv` en el artefacto `listado-para-revisar`, que se
     guarda 30 días.
   - El resumen muestra los conteos y una **huella**, un código de la lista propuesta.
   - El listado solo trae datos públicos de los avisos: número, motivo, cargo, empresa, ubicación, modalidad, fecha de
     entrega y enlace. Nunca datos de clientes.
2. **Aplicar** («aplicar» + huella + `BORRAR`, y si hace falta «conservar» y «borrar_tambien»):
   - Si la huella no coincide, porque los datos cambiaron desde la revisión, se detiene sin cambiar nada.
   - Guarda una copia cifrada (90 días).
   - En una sola transacción, borra de `ofertas` los números elegidos y pasa a `archived` sus vacantes activas del
     catálogo, con `reason = "contrato v13: fuera del objetivo (idioma o país)"`.
   - `entregas_diarias` y `panel_asignaciones` no se tocan.

Esta limpieza está autorizada por Oscar para que la base cumpla su objetivo, no para ocultar déficit. Las noches
siguientes esas vacantes no vuelven a entrar: con las reglas nuevas dejan de ser entregables, y el catálogo archiva por
sí solo las que siguen en el inventario.
