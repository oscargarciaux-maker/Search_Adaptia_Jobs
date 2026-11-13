# Contrato de datos v19 — lugares del mundo, regiones y una bandeja sin ruido

Vigente desde el 13 nov 2026. Amplía v18 y versiones anteriores, sin columnas nuevas en `ofertas` ni SQL nuevo. Nace
de la revisión de Oscar en el panel (13 nov), donde encontró:

- avisos híbridos del Reino Unido («Cambridge y alrededores») como dudosos;
- «Inca» (Mallorca) sugerido como «no sirve»;
- avisos con ubicación «LATAM» que no se aceptaban;
- ninguna forma de elegir «LATAM» como país en el panel;
- «EMEA – Remote», que vale para España;
- vacantes ya cerradas (Expel) todavía en la bandeja;
- «anywhere in the US», que es solo EE. UU.

## 1. Municipios y ciudades del mundo (`datos/lugares_mundo.json.gz`)

- **Origen:** generado una vez desde **GeoNames** (https://www.geonames.org, licencia **CC BY 4.0**) con
  `buscador/generar_lugares.py`. El buscador no depende de la red ni de GeoNames.
- **Contenido:**
  - países cubiertos: todos los lugares de 1.000 habitantes o más (con sus otros nombres desde 5.000), sus regiones de
    primer nivel y las islas de España (Baleares, Canarias…). Son 34.650 nombres;
  - extranjeros: ciudades de 15.000 habitantes o más, con exónimos («Calcuta», «Johannesburgo») desde 200.000. Son
    61.098 nombres.
- **Ambigüedad calculada por código:** un nombre que está en dos países cubiertos, o en uno cubierto y uno extranjero, se
  descarta y nunca decide («Camas», «Córdoba», «Madrid» como municipio). También se descartan los nombres de menos de 4
  letras y las palabras corrientes.
- **Uso (`paises.lugar_conocido`): solo como último recurso y solo con la ubicación**, nunca con la descripción.
  - Se aplica cuando ni la tabla de países, ni las ciudades curadas, ni los lugares extranjeros, ni una región
    decidieron.
  - Se lee por tramos separados por comas, quitando «y alrededores», «Área metropolitana de» y el código de estado final
    («Harrisburg, PA»).
  - Tramos contradictorios no deciden.
- **Las listas curadas mandan siempre:** «Madrid» sigue siendo España y «Santiago» sigue siendo Chile, como antes.

## 2. Regiones

- **Una región como ubicación** («LATAM», «Latin America», «América Latina», «Sudamérica») vale como esa región cuando
  el aviso **no** dice que es presencial ni híbrido.
- **Una presencial o híbrida sigue exigiendo un lugar concreto** (contrato v8): «Latin America (Hybrid)» queda por
  confirmar.
- **Región del título:** cuando la ubicación no dice ningún lugar («Remote job», «N/A»), vale la región del título
  («Latam | Code Tutor», «CSM - EMEA»). Con una ubicación concreta, el título no la reemplaza.
- **Panel:** el selector de país trae un grupo «Regiones» con «LATAM (todos los países)», «Sudamérica, Centroamérica y
  México», «Sudamérica», «Centroamérica» y «LATAM y España».
  - El servidor convierte cada región en sus países (`revision.expandir`). Brasil queda fuera (v12).
  - En el CSV, la columna `pais` acepta también «Sudamérica», «Centroamérica» y listas con «o / or».

## 3. Sugerencias (`panel/sugerir.py`)

- **Europa/EMEA sin LATAM** → `sí` España: «EMEA – Remote» exige residir en Europa, Oriente Medio o África, y España
  está dentro.
- **«Anywhere in the US / Canada / UK…»** → no es «cualquier lugar»: cuenta como ese país (otro país).
- **«Remote, Latin America» publicado en un país de LATAM sin cobertura** (Guyana, Belice, Surinam, Brasil…) → `sí` LATAM.

## 4. La bandeja no pregunta lo que no hace falta (`panel/revision.py`)

No se pregunta, y si ya estaba pendiente pasa a `vencida` con su motivo:

- lo que **ninguna fuente lista hace más de 7 días** o se publicó hace más de 30 → «posiblemente cerrada»;
- lo que **las reglas vigentes ya resuelven** (lugares, regiones, Get on Board…) → «resuelta sola», sin esperar a que la
  búsqueda nocturna actualice el catálogo.

## 5. Carga en segundo plano y rápida (ampliación del 13 nov, noche)

- **El problema:** tras el PR #44, «Cargar todas las dudosas» no terminaba en el panel. En una sola petición evaluaba
  cada dudosa dos veces (candidatas y pendientes guardadas), recalculaba todas sus etiquetas y vencía las pendientes
  una por una. Con 264 dudosas reales tardaba 16 s en una máquina rápida y más en el servidor.
- **Ahora:**
  - `POST /api/revisiones/cargar` arranca el trabajo en segundo plano (uno a la vez) y responde al instante;
  - `GET /api/revisiones/cargar` da el avance (`leidas`/`total`) y el resultado, o un error en lenguaje sencillo;
  - el panel muestra «Cargando… N de M» y, si se recarga la página, retoma el avance.
- **Más rápido, con el mismo resultado:**
  - datos guardados por la nocturna sin recalcular etiquetas (`_datos_ligeros`);
  - cada vacante se evalúa una sola vez por carga;
  - las vencidas se actualizan en lotes;
  - `_ciudad_dentro` descarta con una expresión compilada los textos sin ninguna ciudad.
- **Medición:**
  - con las 264 dudosas reales: de 16,3 s a 1,5 s, con el mismo resultado (213 por revisar);
  - las 8.306 vacantes del inventario dan exactamente la misma elegibilidad que antes;
  - toda la suite de pruebas baja de 37 s a 10 s.

## Medición (13 nov, inventario de 8.306 vacantes, solo conteos)

| Resultado | Vacantes |
|---|---|
| Vacantes ya confirmadas que cambian de país | **0** |
| Dudosas que pasan a aceptadas (municipios de España como Inca, Abrera, Esplugues o Palma; «LATAM»/«América Latina») | 76 |
| Dudosas descartadas por ser de otro país (Cambridge, Calcuta, Harrisburg PA, Tel Aviv, Köln, Nicosia…) | 37 |

Se revisaron a mano las listas completas de aceptadas y descartadas.

## Lo que sigue igual

- Sin IA. En caso de duda, no entra.
- Las reglas del operador (v17) siguen resolviendo solo lo que queda por confirmar.
- **Fuera de alcance:**
  - «Remoto (4 ubicaciones)» de LinkedIn es una ventana de su página que no llega en los datos. La lectura de la ficha
    (v16) intenta resolverla.
  - Casos como «50 % presencial y la empresa tiene oficina en México» los decide el operador.
