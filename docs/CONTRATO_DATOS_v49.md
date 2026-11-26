# Contrato de datos v49 — ubicación sin fugas, afinidad por funciones, más vacantes para quien va corto y panel simple (26 nov 2026)

Pedido de Oscar tras el reporte del cliente: hay personas que piden vacantes en español y no reciben ninguna; llegan
vacantes cuyo título coincide pero cuyas funciones no sirven; y llegan vacantes de una ubicación que la persona no
habilitó. Además, un solo botón «Aplicar cambios» y «Buscar ahora» por cliente. Sin IA y sin SQL nuevo.

## Evidencia (bodega pública del 25 nov, 11.375 vacantes; perfiles y cargos ficticios)

Se mide con `python -m buscador.medicion --bodega trabajo/bodega.json.gz` (solo conteos y títulos públicos).

- **Ubicación.** De 988 remotas «compatibles» para un perfil remoto de Colombia, 128 no eran suyas: 102 nombraban otro
  país («Desde casa, Mexico», «Remote, Peru») y entraban porque el aviso mencionaba un horario parecido (EST, GMT-5).
  Otras 102 oficinas le llegaban fuera de su ciudad.
- **Funciones.** El cargo se decidía solo con el título. Con la huella del mapa, no tienen ninguna evidencia del oficio
  el 6 % de Product Designer («Product Designer – Kids' Drinkware»), el 29 % de Product Manager («LCL Product Manager
  – Ocean Freight») y el 25 % de QA («Battery Test Engineer», «QA Manufacturing Analyst»).
- **Español.** Para quien solo acepta español y solo remoto (Colombia, Product Manager): 2.047 del cargo → 1.657 con
  descripción → 241 en español → 21 abiertas a su país → 1 con enlace comprobado. Computrabajo dejaba 554 de 739
  avisos sin descripción.

## Decisiones de Oscar (26 nov)

1. Título sin respaldo en las funciones: llega **al final, con la etiqueta «Funciones por confirmar»**; si además parece
   otro oficio, **no se entrega sola: va a «Por confirmar»**.
2. A quien va corto se le completa **hasta su meta diaria** (antes, hasta 5), sin pasar el techo del día.
3. Presencial e híbrida **exigen ciudad**: sin ciudad en el perfil no llegan.
4. Una remota que solo dice horario (sin país) llega **solo a quien marcó ese horario**; las demás siguen «por
   confirmar».

## 1. Ubicación: si el aviso nombra un país, manda ese país

Reglas de `panel/afinidad.py::lugar` (las usan todas las vías: lote, ampliación, cruce entre cargos, reutilización,
rescate, bandeja y lo que muestra el panel). Valen también para lo ya guardado.

- **Países abiertos de un aviso.** Un país cubierto (LATAM hispanohablante y España) solo cuenta si está en `paises`.
  Un país de fuera cuenta si el aviso lo nombra (`paises_mundo`).
- **Horario.** La franja horaria solo abre un aviso remoto que no nombra país (`nota_pais` = «por zona horaria» y
  `paises_mundo` vacío) y solo para las zonas de `acepta_horario` (±1 h). La zona del país donde vive deja de contar
  sola (cambia v23 y v35). Sin horario marcado, el aviso sigue «por confirmar» y entra a la bandeja.
- **Alcance mundial.** «Anywhere in France, Belgium, Spain» o «en cualquier parte de México» no es alcance mundial
  (`paises.mundo_acotado`): manda el lugar nombrado. `alcance_mundial` vale si el aviso no nombra países o si `paises`
  trae todos los cubiertos.
- **Residencia obligatoria.** En una remota con frase de residencia, `paises_mundo` son solo los países de esa frase
  (antes se sumaba el de la ubicación: «Colombia» + «must reside in Argentina» llegaba a Colombia).
- **«US-based».** Solo restringe si habla de la persona («must be US-based», «US-based candidates»). «A leading
  US-based company» describe a la empresa (243 vacantes quedaban fuera de LATAM solo por eso).
- **La ciudad no anula el país.** El nombre de una ciudad solo cuenta si el país del aviso es uno de la fila (o el de
  la ciudad, en una fila sin países). «Santiago» de Chile no acepta «Santiago de Cali»; «Valencia» de España no acepta
  «Valencia, CA» ni sus alrededores.
- **Presencial e híbrida exigen ciudad.** La fila necesita ciudades y el aviso debe nombrar una o quedar a 50 km
  (v38). Motivos nuevos: «falta la ciudad en el perfil» y «oficina sin ciudad confirmada» (el aviso solo dice el país).
  La región como ubicación (v19) deja de servir a presenciales. Si la fila no acepta la modalidad, el motivo es el de
  siempre («modalidad diferente»).
- **País desde la ciudad.** Una fila solo con ciudades toma el país de esas ciudades si todas apuntan al mismo; de ahí
  sale «donde vive». En un perfil anterior (sin filas), cada ciudad queda en las filas de su país y una ciudad de otro
  país tiene su propia fila (v24: la ciudad implica su país).
- **Posts.** El tope de 2 por perfil al día cuenta todo post al que se le perdonó el país o la modalidad (también los
  «deducidos»).
- **Admisión.** `bodega._sirve_a_perfiles` conserva por horario solo lo que no nombra país.

Efecto: lo ya asignado que era una fuga deja de salir como «lista» en Vacantes y en WhatsApp (el panel reevalúa). No se
reescriben asignaciones.

## 2. Afinidad por funciones

- **Cargo efectivo** (`panel/contenido.py::cargo_operativo`): un solo cargo «rellenado» para clasificar, asignar,
  rescatar, revisar y mostrar. Añade a lo que escribió el operador: los nombres sugeridos si no puso ninguno, los
  títulos aprendidos (v25) y, cuando el cargo es título exacto de una familia del mapa, sus `excluir` y, si no tiene
  funciones propias, sus `herramientas` como huella.
- **Evidencia** (`panel/contenido.py::evidencia(titulo, descripcion, cargo)`), sin IA:
  - `fuerte`: 3 o más términos de la huella, o el nombre del cargo 2 o más veces en la descripción;
  - `debil`: 1 o 2 términos;
  - `ninguna`: hay huella y la descripción no trae ninguno, o el cargo es compuesto («AI Product Manager», «Growth
    Marketing») y ni el título ni la descripción nombran su distintivo (`datos/glosario_cargos.yaml`);
  - `sin_huella`: el cargo no tiene huella o el aviso no tiene descripción: no opina.
  - `otro_oficio`: sin evidencia y con una señal positiva de otro oficio (el título es también de otra familia del mapa
    o la descripción trae 3 o más herramientas de otra familia y ninguna de la suya).
- **Qué hace.** `ninguna` solo ordena: pesa como una cosa más que no cumple y deja la etiqueta «Funciones por
  confirmar»; en el mensaje de WhatsApp entra después de las que sí tienen evidencia. `otro_oficio` no se entrega sola:
  va a «Por confirmar» con el motivo «Título coincide; funciones de otro oficio». «Sirve» la asigna; «No sirve» la
  retira solo para ese cargo.
- **Dónde queda.** No se guarda en el catálogo (depende del cargo, que es configuración privada). Va en
  `panel_asignaciones.explicacion` como `{"funciones": nivel, "halladas": [...]}`.
- **Orden por calidad.** Vacantes y WhatsApp ordenan por: coincidencia del cargo, lo que no cumple, evidencia y fecha.
- `match_grade` de una asignación es el del cargo que la recibe (antes, en el cruce entre cargos y al reutilizar, era
  el del cargo de origen).

## 3. Más vacantes para quien va corto

- **Completar hasta la meta.** Reutilización (v11) y rescate con toda la bodega (v36) completan hasta la meta diaria
  del perfil (mínimo 5). Los posts y Comunidad siguen como estaban. Las vacantes añadidas así no pasan, sumadas al lote,
  del techo del día.
- **Comprobar enlaces por necesidad.** Antes de la cola del lote se comprueban, por turnos y primero para quien tiene
  menos, las candidatas de cada persona bajo su meta que cumplen su idioma y su ubicación (aunque otro cliente ya las
  haya recibido).
- **Descripciones por necesidad.** Computrabajo lee solo fichas cuyo título es de un cargo buscado, primero las de
  cargos con personas cortas, y relee las guardadas sin descripción.
- **Reconocer lo que se busca.** Todo título de `consultas_es` se reconoce al clasificar; los plurales cuentan
  («Desarrolladores»); `en_espanol` usa listas editables en `datos/titulos_idioma.yaml`; quien solo acepta español
  recibe el doble de turnos de búsqueda.
- **Modalidad y alcance en español.** «Modalidad: 100% remoto», «remoto desde Latinoamérica/LATAM/cualquier país» se
  leen como remota y con su alcance. «Empresa líder en Latinoamérica» no cuenta.
- **«Buscar ahora» para quien falta** incluye Hireline y Magneto (ajusta v47) y el español en Get on Board.
- **Diagnóstico por persona** (solo en el panel privado): candidatas → con descripción → idioma → ubicación → enlace
  comprobado → asignadas.

## 4. Panel

- **Un solo «Aplicar cambios».** Guarda y deja vigente la configuración (los mismos pasos de «Confirmar y aplicar»,
  v43: `PUT /api/config` y `POST /api/config/publicar`). Se retira «Guardar borrador». El botón de los formularios de
  cliente y de cargo aplica de verdad. Si no se puede publicar (por ejemplo, metas por encima del techo), los cambios
  quedan guardados y el panel dice por qué.
- **«Buscar ahora» por cliente**, en el detalle del cliente. `POST /api/busqueda {"cliente_id": …}`:
  - hoy no hay lote → la búsqueda completa del día, con sus perfiles primero;
  - ya hay lote → `enfoque=pedido`: solo para los perfiles activos de ese cliente que no llegan a su meta;
  - todos en su meta → no lanza.
  Los perfiles pedidos se guardan en `panel_ajustes` (clave `busqueda_pedida`, con su fecha); el flujo de GitHub solo
  recibe la opción cerrada `pedido`. Nunca van identificadores de perfiles en las entradas del flujo ni en sus registros.
- **Formulario.** Una fila con presencial o híbrido pide la ciudad; el panel lista los perfiles a los que les falta.

## Lo que no cambia

- Solo español e inglés; el idioma del perfil sigue siendo un filtro.
- Solo la ubicación, el idioma y las reglas del sistema descartan (v27). La evidencia de funciones ordena; lo único
  nuevo que no se entrega solo es lo que parece otro oficio, y eso se pregunta.
- Sin agregadores, sin envío automático, sin SQL nuevo. `ofertas` v1 no cambia.
- Los compuestos del glosario siguen siendo sugerencias (v44).
