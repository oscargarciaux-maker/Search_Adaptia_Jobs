> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

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
  (`paises.mundo_acotado`): manda el lugar nombrado. «Anywhere in LATAM» sigue abierta a LATAM y «cualquier parte del
  mundo» sigue siendo mundial. Lo mismo en la descripción: «work from anywhere in the US» ya no abre el aviso a
  cualquier país (39 vacantes de fuera llegaban así a LATAM), y «work from anywhere in LATAM or Europe» vale para esa
  región. `alcance_mundial` vale si el aviso no nombra países o si `paises`
  trae todos los cubiertos.
- **Residencia obligatoria.** En una remota con frase de residencia, `paises_mundo` son solo los países de esa frase
  (antes se sumaba el de la ubicación: «Colombia» + «must reside in Argentina» llegaba a Colombia).
- **«US-based».** Solo restringe si habla de la persona o del puesto («must be US-based», «US-based candidates»,
  «US-based remote role», o «(USA-based)» en el título). «A leading US-based company» describe a la empresa (243
  vacantes quedaban fuera de LATAM solo por eso).
- **La ciudad no anula el país.** El nombre de una ciudad solo cuenta si el país del aviso es uno de la fila (o el de
  la ciudad, en una fila sin países). «Santiago» de Chile no acepta «Santiago de Cali»; «Valencia» de España no acepta
  «Valencia, CA» ni sus alrededores.
- **Presencial e híbrida exigen ciudad.** La fila necesita ciudades y el aviso debe nombrar una o quedar a 50 km
  (v38). Motivos nuevos: «falta la ciudad en el perfil» y «oficina sin ciudad confirmada» (el aviso solo dice el país).
  La región como ubicación (v19) deja de servir a presenciales. Si la fila no acepta la modalidad, el motivo es el de
  siempre («modalidad diferente»).
- **País desde la ciudad.** Una fila solo con ciudades toma el país de esas ciudades si todas apuntan al mismo; de ahí
  sale «donde vive». En un perfil anterior (sin filas), cada ciudad queda en las filas de los países donde existe una
  ciudad con ese nombre («Mérida» de quien vive en España es la de Extremadura) y, si su país más conocido es otro,
  además tiene su propia fila (v24: la ciudad implica su país). Para los alrededores (50 km) la ciudad se ubica en su
  país más conocido y, si el nombre es de varios, en los de la fila.
- **Posts.** El tope de 2 por perfil al día cuenta todo post al que se le perdonó el país o la modalidad (también los
  «deducidos»).
- **Admisión.** `bodega._sirve_a_perfiles` conserva por horario solo lo que no nombra país.

Efecto: lo ya asignado que era una fuga deja de salir como «lista» en Vacantes y en WhatsApp (el panel reevalúa). No se
reescriben asignaciones.

## 2. Afinidad por funciones

- **Cargo operativo** (`panel/contenido.py::cargo_operativo`): un solo cargo «rellenado» para clasificar, asignar,
  rescatar, revisar y mostrar. Añade a lo que escribió el operador: los nombres sugeridos si no puso ninguno y los
  títulos aprendidos (v25). Si el cargo no tiene funciones propias, su huella son las `herramientas` de su familia del
  mapa más la huella calculada de noche (`huellas_automaticas`: por idioma, de los avisos cuyo título es exactamente un
  nombre del cargo; se guarda en `panel_ajustes.huellas_cargos`). Si es título exacto de una familia, sus `excluir`
  quedan como señales (`excluir_mapa`), no como descartes.
- **Evidencia** (`panel/contenido.py::evidencia(titulo, descripcion, cargo)`), sin IA:
  - `fuerte`: 3 o más términos de la huella, o el nombre del cargo 2 o más veces en la descripción;
  - `debil`: 1 o 2 términos;
  - `ninguna`: hay huella y la descripción no trae ninguno;
  - `sin_huella`: el cargo no tiene huella o el aviso no tiene descripción: no opina.
  - `otro_oficio`: sin ninguna evidencia y con una señal positiva de otro oficio: el título trae un `excluir` de su
    familia del mapa, una palabra de otro sector (`datos/oficios_ajenos.yaml`, editable) que el cargo no usa, o la
    descripción trae 4 o más herramientas de una familia de otra área. Un título que es exactamente un nombre del
    cargo (o uno aprobado en la bandeja) nunca se retiene.
- **Distintivo** (aparte del nivel): en un cargo compuesto («AI Product Manager» = IA + Product Manager, según
  `datos/glosario_cargos.yaml`), si ni el título ni la descripción nombran el modificador, `falta_distintivo` trae la
  forma que falta («IA»). Ordena igual que `ninguna` y deja la etiqueta «No menciona IA».
- **Qué hace.** `ninguna` solo ordena: pesa como una cosa más que no cumple y deja la etiqueta «Funciones por
  confirmar»; en el mensaje de WhatsApp entra después de las que sí tienen evidencia. `otro_oficio` no se entrega sola:
  en `familias` queda con la coincidencia `otro_oficio` (grado nuevo, fuera de exacto/similar/cercano y distinto de
  `funciones`, que es lo contrario: v25) y va a «Por confirmar» con el motivo «Título coincide; funciones de otro
  oficio». «Sirve» la asigna y aprende el título; «No sirve» la retira solo para ese cargo (motivo «no sirve para ese
  cargo»; antes, «No sirve» en una duda de cargo la descartaba para todos los cargos).
- **Dónde queda.** La evidencia no se guarda en el catálogo (depende del cargo, que es configuración privada). Va en
  `panel_asignaciones.explicacion` como `{"funciones": nivel, "halladas": [...], "falta": "IA"}` (`falta` solo si
  aplica). Una asignación aprobada a mano en la bandeja lleva `{"aprobada_por": …}` (antes `{"funciones": true}`, que
  se sigue leyendo). `panel_asignaciones.cargo_configuracion` guarda el cargo operativo: el del operador más
  `funciones` rellenadas, `excluir_mapa` y `distintivo`.
- **Orden por calidad.** Vacantes y WhatsApp ordenan por: coincidencia del cargo, lo que no cumple, evidencia y fecha.
- `match_grade` de una asignación es el del cargo que la recibe (antes, en el cruce entre cargos y al reutilizar, era
  el del cargo de origen).

## 3. Más vacantes para quien va corto

- **Completar hasta la meta** (`panel/ejecutor.py::Completar`). Reutilización (v11) y rescate con toda la bodega (v36)
  completan hasta la meta diaria del perfil (mínimo 5). Comunidad y los posts siguen en el mínimo. Hasta el mínimo
  siempre cabe; del mínimo a la meta, una vacante que hoy aún no usa nadie solo entra mientras lote + añadidas no pasen
  del techo del día. El rescate comprueba hasta 200 enlaces en 5 minutos (antes 80 en 150 s), por turnos y primero para
  quien tiene menos candidatas. «Buscar ahora» cuenta como «le falta» a todo el que está bajo su meta. Lo asignado
  en las pasadas anteriores del mismo día (8:30, cada hora, «Buscar ahora») cuenta para la meta y para el techo
  (`repo.asignadas_de`): cada pasada completa solo lo que falta. Si ese dato no se puede leer, se completa solo hasta
  el mínimo. «Sirve» en la bandeja asigna también hasta la meta.
- **Comprobar enlaces por necesidad** (`buscador/verificar_enlaces.py::cola_por_necesidad`, solo modo panel). Antes de
  la cola del lote se comprueban las candidatas de cada persona: las de su cargo que cumplen su idioma y su ubicación,
  aunque otro cliente ya las haya recibido; por turnos, primero quien tiene menos, hasta 2 por cada vacante de su meta
  y con la mitad del presupuesto como mucho (un tercio en la captura horaria).
- **Descripciones por necesidad.** Computrabajo lee solo fichas cuyo título es de un cargo buscado, primero las de
  cargos con personas cortas en ese país (300 por noche), y relee hasta 200 guardadas sin descripción
  (`computrabajo_relectura`). La relectura de LinkedIn y esta ordenan por lo que sirve a quien va corto, con su idioma
  cuando ya se conoce.
- **Buscar solo lo que se reconoce.** `consultas_es` son los nombres en español del cargo y los títulos exactos en
  español de su familia del mapa (`espanol_del_mapa`). Ya no se buscan los «similares» del mapa, que no se reconocían
  al clasificar (v44: solo se sugieren): esos turnos se gastaban.
- **Plurales.** «Desarrolladores Full Stack» cuenta como «Desarrollador Full Stack» (`normalizar.singular`, como
  segunda oportunidad al comparar; no cambia identificadores ni claves).
- **Títulos en español.** `en_espanol` usa `datos/titulos_idioma.yaml` (editable), con oficios generales («Contador»,
  «Vendedor», «Asesor comercial»). «Director of Engineering» no cuenta como español.
- **Turnos.** Quien solo acepta avisos en español recibe el doble de turnos de búsqueda (`PESO_SOLO_ESPANOL`).
- **Modalidad y alcance en español.** «Modalidad: 100% remoto», «100% remoto | Latinoamérica», «remoto desde cualquier
  país de Latinoamérica» y «remoto para LATAM» se leen como remota y con su alcance (antes quedaban presenciales en la
  ciudad de la empresa: el patrón buscaba el signo «%», que la normalización quita). «Empresa líder en Latinoamérica»
  y «no es 100% remoto» no cuentan.
- **«Buscar ahora» para quien falta** incluye Hireline y Magneto (ajusta v47) y un título en español por cargo en el
  refuerzo de Get on Board.
- **Diagnóstico por persona.** Es la «Cobertura por persona» que ya existe (v37): del cargo, compatibles, listas, por
  comprobar y por qué le faltan. Suma los motivos nuevos de ciudad; «falta la ciudad en el perfil» trae su sugerencia
  en «Qué hacer» («Escribir la ciudad…»). «Oficina sin ciudad confirmada» no tiene sugerencia: depende del aviso.

Lo que una bodega guardada no puede demostrar: cuántos enlaces más se comprueban y cuántas descripciones más se leen.
Eso se ve en la primera búsqueda real (`por_necesidad` en la comprobación de enlaces, `del_cargo` y `relectura` en
Computrabajo, `rescatadas` en el resumen).

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
  recibe la opción cerrada `pedido`. Si la búsqueda no se puede lanzar (ya hay una en curso), el pedido que estaba en
  cola se conserva. Nunca van identificadores de perfiles en las entradas del flujo ni en sus registros.
- **Formulario.** Una fila con presencial o híbrido pide la ciudad; el panel lista los perfiles a los que les falta.

## 5. Quitar un cargo el mismo día no tumba la búsqueda

El 25 nov fallaron tres corridas seguidas (la segunda pasada, su respaldo y una captura horaria) con «No se puede
reemplazar una selección canónica»: el lote de la primera búsqueda tenía 5 vacantes de un cargo que después dejó de
estar en la configuración (archivado, sin perfiles activos o sin meta). `entrega.elegir` armaba el lote solo con los
cargos vigentes y la base, que exige que todo lo registrado hoy siga en el lote, lo rechazaba.

- Lo ya entregado hoy de un cargo que salió de la configuración se conserva tal cual en el lote del día (mismo
  snapshot y coincidencia). No recibe vacantes nuevas ni entra al resumen por cargo; cuenta al calcular lo que sobra del techo para Comunidad.
- `entrega.filas_de` no arma filas de `ofertas` para ese cargo: ya salieron cuando se eligieron.
- La regla de la base no cambia (protege lo entregado). Importa más desde v49, porque «Aplicar cambios» rige al
  instante.

## Lo que no cambia

- Solo español e inglés; el idioma del perfil sigue siendo un filtro.
- Solo la ubicación, el idioma y las reglas del sistema descartan (v27). La evidencia de funciones ordena; lo único
  nuevo que no se entrega solo es lo que parece otro oficio, y eso se pregunta.
- Sin agregadores, sin envío automático, sin SQL nuevo. `ofertas` v1 no cambia.
- Los compuestos del glosario siguen siendo sugerencias (v44).
