# Contrato de datos v51 — la búsqueda arranca a su hora sin depender del horario de GitHub (27 nov 2026)

Decisión de Oscar (27 nov): la hora la marca algo **dentro de GitHub**, sin servicios externos. Sin IA, sin SQL nuevo y
sin claves nuevas. Amplía v50 y el arranque del 18 nov (`buscador/arranque.py`).

## Evidencia

**Primera búsqueda real con v49 y v50 (26 nov, corrida 45890342501, 97,6 min):**

| | 25 nov (código anterior) | 26 nov |
|---|---|---|
| En español con cargo reconocido | 1.128 | 1.503 |
| De esas, con enlace comprobado | 67 (6 %) | 407 (27 %) |
| En español entre las 130 elegidas del día | 21 | 32 |
| En inglés con cargo / comprobadas | 4.025 / 1.124 | 4.867 / 2.279 |
| Cargos bajo su meta (vacantes que faltaron) | 23 | 7 |

LinkedIn leyó 450 fichas, todas de un cargo buscado (antes 75 de cualquier aviso); Indeed pasó de 769 a 8.503 avisos
vistos; InfoJobs trajo 51 sin captcha; fugas de ubicación en 0. No apareció el error «selección canónica».

**Horarios de GitHub (corridas programadas de `bodega.yml` e `incremental.yml`, 29 oct a 26 nov):**

| Fechas | Captura «de cada hora» | Primera búsqueda del día (pedida a las 11:30 UTC) |
|---|---|---|
| 14 y 15 nov | 22 y 21 corridas al día | 31 y 34 minutos tarde |
| 16 nov | 13, con huecos de 2 a 4 horas | 1 h 08 tarde |
| 17 a 26 nov | 2 a 4 al día, cada 8 a 12 horas | de 6 h 37 a 11 h 17 tarde, todos los días |

- Los cinco horarios de la mañana llegan desplazados las mismas horas y en su orden: los respaldos del 18 nov no ayudan
  porque usan el mismo reloj. El «vigía» depende de la captura horaria, que llega igual de tarde.
- GitHub documenta que los flujos programados «pueden retrasarse» con mucha carga y hasta descartarse; no da una hora
  garantizada. La causa de un atraso fijo desde el 17 nov no se pudo ver. No se encontró un cambio nuestro que lo
  explique.
- Lo que se **pide** (`workflow_dispatch`) arranca al momento: el 26 nov la búsqueda pedida por el vigía se creó en
  segundos.

**Otros hallazgos de la corrida del 26 nov:**
- Bumeran: desde GitHub no respondieron los portales de Argentina, Chile y Perú (3 avisos en total); desde otra red
  respondían a la misma hora. Get on Board: ninguna búsqueda respondió (el 25 nov, 123 avisos). El reporte no guardaba
  el motivo.
- El refuerzo de Apify falla el 25 y el 26 nov con «Estado central sin confirmar (apify_reservar)». Es la primera
  reserva de la corrida y llega tras más de una hora sin usar la conexión con Supabase; la reserva siguiente, minutos
  después y por la misma conexión, funciona.
- Computrabajo: 235 vacantes en español con cargo, 7 con enlace comprobado. 233 son presenciales o híbridas. Un enlace
  se comprueba cuando la vacante le sirve a alguien: no es una fuga de la comprobación. El reporte mostraba
  `candidatas_programadas: 1`, que es solo la última de varias llamadas de la corrida.

## 1. El «Reloj» (`.github/workflows/reloj.yml`)

1. **Qué es.** Una cadena de relevos. Cada corrida espera con el temporizador del entorno `reloj` de GitHub (30
   minutos; la espera no ocupa una máquina ni gasta minutos), pide el siguiente relevo y lanza lo que toque. Solo lee
   fechas y estados de corridas y `trabajo/metricas_entrega.json` (fechas y conteos): sin datos de clientes ni claves.
2. **Qué pide** (reglas en `buscador/arranque.py`, con pruebas):
   - **Captura horaria** (`toca_captura`): si no hay una búsqueda diaria ni otra captura en marcha y la última captura
     que no se canceló empezó hace 55 minutos o más. Se pide con `prueba=false` (a mano su valor por defecto es de
     prueba).
   - **Búsqueda diaria** (`toca_diaria`): desde las 6:30 a. m. de Bogotá (11:30 UTC), si hoy no terminó ninguna y en la
     rama principal no hay una de hoy en marcha ni terminada. Una que falló **no** se repite sola: se revisa. Una que
     GitHub canceló en la cola no cuenta, pero no se pide más de 3 veces al día. Es la búsqueda completa de siempre.
   - Si toca la diaria no se pide a la vez la captura: en la cola del grupo `publicar` solo cabe una corrida en espera
     y la segunda cancelaría a la primera.
3. **Seguros** (`relevo`):
   - Un relevo que esperó menos de 20 minutos está en un entorno sin temporizador: no hace nada y **no pide otro**
     (sin esto la cadena giraría sin pausa). Se marca en rojo solo si lo arrancó una persona.
   - Nunca dos cadenas: si hay otro relevo vivo, este cumple con lo que toque y no pide el siguiente; de dos que corren
     a la vez, sigue el más antiguo.
   - Sin su propio registro, sin la lista de corridas o fuera de la rama principal, no hace nada a ciegas.
   - El relevo se pide **antes** que la captura o la búsqueda: si algo falla después, la cadena ya sigue.
4. **Si la cadena se corta** la reanudan: el horario propio del Reloj y la captura horaria programada (cuando GitHub
   los dispare) y cualquier búsqueda real, incluida «Buscar ahora» (trabajo `reloj` de `bodega.yml`, aparte y con
   permiso solo de `actions: write`; la búsqueda no recibe ese permiso). `hace_falta_revivir`: solo si no queda ningún
   relevo vivo.
5. **Lo que no cambia.** Los horarios de `bodega.yml`, sus respaldos y el vigía siguen; `hace_falta_pasada` ya evita
   repetir la búsqueda del día. La segunda pasada (8:30) sigue con el horario de GitHub. «Buscar ahora» no cambia.
   El Reloj no usa el grupo `publicar`: no cancela búsquedas ni capturas en espera.
6. **Activación (una vez, a mano):** crear el entorno `reloj` con «Wait timer» 30 y arrancar el flujo
   (`docs/ACTIVAR_RELOJ.md`). Para detenerlo: desactivar el flujo «Reloj».
7. **Límites conocidos.**
   - Si GitHub retrasara también lo pedido (hasta el 26 nov no lo hace), el Reloj se atrasaría igual.
   - Un cruce exacto entre el vigía y el Reloj en el mismo minuto podría pedir dos búsquedas; la segunda esperaría a
     la primera. No se ha visto; el vigía solo corre cuando GitHub dispara su horario.
   - Deja unas 48 corridas cortas al día en Actions y en «Deployments».

## 2. Motivo de los fallos de las fuentes

- `buscador/http.py::motivo_del_fallo(cliente)`: por qué falló la última petición, corto y sin direcciones ni claves
  («HTTP 403», «HTTP 200 (respuesta no JSON)», «ConnectTimeout»). `Cliente.get` y `Cliente.json` ahora lo anotan.
- **Bumeran y portales hermanos** (`jobint.py`): el reporte añade `motivos` por país y `reintentados`, y el registro
  nombra el portal que no respondió. Un portal en descanso (3 fallos seguidos) recibe **una** oportunidad más al final
  de la corrida: si responde, siguen sus turnos; si vuelve a fallar, descansa hasta la siguiente. No se insiste contra
  un bloqueo ni se cambia la forma de pedir.
- **Get on Board** (`getonbrd.py`): `fallidas` y `motivos`.
- Con el motivo a la vista se decide. Un bloqueo a las direcciones de GitHub se respeta.

## 3. Reserva de Apify

- `estado_operativo.Central.rpc`: tras 120 segundos sin usar la conexión con Supabase se abre una nueva **antes** de
  pedir. No es un reintento: la regla «sin reintento automático» de una reserva ambigua no cambia.
- El código de respuesta se mira antes de leer el cuerpo, y el mensaje dice la causa
  («apify_reservar: ReadTimeout», «apify_reservar: HTTP 502 sin datos»), nunca la dirección ni la clave.
- La causa (conexión vieja) es la hipótesis más probable, no un hecho comprobado: si fuera otra, el reporte siguiente
  la dirá.

## 4. Medición

- `verificacion_enlaces.en_la_corrida`: `llamadas`, `programadas` (suma de todas las llamadas), `enlaces` (resultados
  guardados desde que empezó la corrida), `vistas_en_busqueda` y `por_sitio` con sus estados
  (`verificar_enlaces.resumen_corrida`). No incluye lo que comprueba «completar a quien va corto» en el panel, que
  guarda sus resultados en el catálogo.
- `entrega.embudo[cargo].por_idioma`: por idioma del aviso, `nuevas`, `cumplen_filtros`, `enlace_comprobado` y
  `entregadas`. Solo cuentas por cargo, sin datos de clientes.
- No se añade una cola para comprobar vacantes que no le sirven a nadie: no entregaría más.

## Sin comprobar
- El Reloj en GitHub real: necesita el entorno `reloj` y estar en la rama principal.
- Por qué GitHub retrasa los horarios desde el 17 nov.
- El motivo real de los fallos de Bumeran y Get on Board desde GitHub (lo dirá la primera corrida con este código).
