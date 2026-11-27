# Línea base del objetivo mundial (sección 7)

**Para qué sirve.** El objetivo ya es mundial (`docs/CONTRATO_VIGENTE.md`, inicio), pero el código todavía aplica
restricciones LATAM/España/Brasil. Antes de cambiar esas reglas (sub-tareas 7.1–7.4) se midió cómo se comporta **hoy**
el modo panel. Después de cada sub-tarea se vuelve a medir con la misma bodega y se compara.

No cambia ninguna regla. Solo usa perfiles y cargos **ficticios**, la bodega pública ya publicada y guarda **conteos y
segundos** (nunca títulos, empresas ni enlaces).

## La bodega fijada

| Dato | Valor |
|---|---|
| Commit de la rama `publicado` | `774a1e39208bad12fe52879c6e0d36b0648b98a3` («Bodega 2026-11-27T15:14Z») |
| Archivo | `trabajo/bodega.json.gz` (17.829.098 bytes, 12.606 vacantes) |
| sha256 | `96b57d8a745fd40faa9cacc8289609e1946b8bb2fb971cfbc39810c735378fd2` |

La bodega **no** se sube al repositorio. Importante: la rama `publicado` se reescribe en cada búsqueda (un solo commit
con push forzado), así que ese commit deja de estar en la rama con la siguiente corrida. Por eso:

1. **Guarda una copia fuera del repositorio** mientras el commit exista:
   ```
   git fetch origin publicado
   git show 774a1e39208bad12fe52879c6e0d36b0648b98a3:trabajo/bodega.json.gz > ../adaptia-bodegas/bodega-774a1e3.json.gz
   ```
   (Desde Windows usa Git Bash: en PowerShell 5.1 el `>` cambia los bytes del archivo).
2. Si el commit ya no está en la rama, GitHub suele servirlo un tiempo por su SHA:
   `git fetch origin 774a1e39208bad12fe52879c6e0d36b0648b98a3` y después el mismo `git show`. No está garantizado.
3. Comprueba la huella: `sha256sum bodega-774a1e3.json.gz` debe dar el sha256 de arriba. El modo comparar lo revisa
   solo y se niega a comparar con otra bodega (sale con código 2).

## Cómo se usa

```
# comparar después de un cambio (unos 35 min: cada escenario pasa la bodega entera por `limpiar`)
python -m buscador.medicion --bodega ../adaptia-bodegas/bodega-774a1e3.json.gz --comparar pruebas/datos/linea_base_mundial.json

# volver a crear la línea base (solo si se decide cambiar de bodega)
python -m buscador.medicion --bodega <ruta> --mundial --commit <sha del commit> --guardar pruebas/datos/linea_base_mundial.json
```

El modo comparar imprime una tabla antes → después por escenario y etapa. **Falla (código 1) si cambia lo que recibe
el escenario de control (h)**: sus cinco etapas y `panel_fuera_del_objetivo`. `admitidas` (volumen de toda la bodega)
y los segundos se muestran pero no deciden nada: 7.2 puede subirlos a propósito, y los segundos dependen de la máquina.
Se niega a comparar (código 2) con otra bodega o con otro `--hoy`. Si cambiaron los términos de los cargos ficticios
(por ejemplo, porque se amplió el mapa de cargos), avisa antes de la tabla: entonces una diferencia puede no venir de
la sección 7.

## Escenarios (perfiles ficticios, modo panel)

Cada escenario es un cliente ficticio con un perfil en cada uno de los 5 cargos ficticios de `medicion.CARGOS`, con
meta 100 (alta a propósito, para que la meta del día no esconda dónde se pierden vacantes).

| | Vive en | Idioma | Busca |
|---|---|---|---|
| a | Brasil | inglés | remoto mundial |
| b | Brasil | inglés | presencial en São Paulo |
| c | EE. UU. | solo español | remoto mundial |
| d | Colombia | solo inglés | remoto mundial |
| e | Alemania | inglés | híbrido en Berlín |
| f | Kenia | inglés | remoto mundial (país sin fuentes locales) |
| g | India | inglés | remoto en su país |
| h | Colombia | español | remoto LATAM — **control: debe quedar igual** |

## Etapas

- **objetivo**: vacantes de la bodega del cargo, en un idioma del perfil y con un lugar que el objetivo mundial acepta.
  Es una regla propia y simple sobre las etiquetas ya guardadas, que no usa el código que se va a cambiar: remota que
  nombra el país de la persona o de alcance mundial; oficina cuya ubicación nombra la ciudad del perfil.
- **limpiar**: de esas, las que siguen tras `bodega.limpiar` con la configuración del escenario.
- **entregable**: y pasan `contrato.entregable` en modo panel.
- **afinidad**: y `panel.afinidad.evaluar` las da por compatibles con el perfil.
- **panel**: y `entrega.elegir` las ofrece (sin exigir enlace comprobado: eso depende de lo que pidieron los clientes
  reales cada noche y sería ruido).
- Aparte: `panel_fuera_del_objetivo` (lo que el panel ofrece y la regla del objetivo no reconoce, sobre todo
  ampliaciones), `admitidas` (volumen total que deja `limpiar`) y segundos de `limpiar` y de la selección. «Todos juntos»
  mide los 8 escenarios a la vez (meta 15), como un panel con todos esos clientes.

## Qué es `panel_fuera_del_objetivo` (revisado el 27 nov, sección 7.A)

En la línea base, las 20 de b (São Paulo) y las 12 de e (Berlín) son **todas** la ampliación prevista `remota_cercana`:
el perfil no acepta remoto, no llega a 5 en su ciudad y se completa con remotas abiertas a su país o mundiales, solo
hasta 5 por perfil (`docs/CONTRATO_VIGENTE.md` §7; desde el 27 nov el rescate y la reutilización también paran en 5). La regla «objetivo» no las cuenta porque mira solo la modalidad
pedida. No es un error de lugar; `pruebas/panel/test_ampliacion_marcada.py` fija ese comportamiento.

## Límite importante

La bodega solo guarda lo que **sobrevivió** a la admisión de esa noche, que usó los países de los clientes reales. Lo
que se descartó al capturar («no se puede aplicar desde LATAM»: 1.168 avisos en esa corrida, según
`datos/salud.json` de `publicado`) no está en la bodega, y lo que nunca se buscó (por ejemplo en Kenia o India) tampoco.
Esta medición ve las pérdidas **dentro** de lo guardado; las de antes se verán como más vacantes en la etapa
«objetivo» cuando 7.x cambie la búsqueda y se use una bodega nueva.

Además, la regla «objetivo» lee las etiquetas de país que puso el código de hoy, que tiene sesgo LATAM: por ejemplo,
una remota «Americas» queda con países de LATAM y sin EE. UU., así que no cuenta como objetivo para el escenario c.
Así la etapa queda fija (es lo que se busca), pero el objetivo mundial se ve más chico de lo que es.
