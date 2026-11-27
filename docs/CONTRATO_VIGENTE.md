# Contrato vigente — las reglas de hoy, ya resueltas

**Objetivo del producto (decisión 27 nov):** una persona de cualquier país crea su perfil y recibe vacantes que le
sirven según sus características. Si pide remoto mundial, le llegan de todo el mundo. El idioma lo decide el perfil,
no el país donde vive: si pide español, solo en español aunque viva en un país que no habla español; si pide inglés,
le llegan en inglés aunque viva en un país hispanohablante, en Brasil o en cualquier otro. El origen LATAM/España es
histórico. Los idiomas de aviso aceptados siguen siendo solo español e inglés.

Fuente principal de las reglas del proyecto (estado al 27 nov 2026, hasta v52 y las decisiones del 27 nov). Cada regla dice cómo es **hoy**; entre
paréntesis va el contrato de donde sale, por si hace falta el detalle. Si una versión posterior corrigió a otra, aquí
solo queda la posterior. Los `docs/CONTRATO_DATOS_vNN.md` son históricos: se conservan porque el código y las pruebas
los citan, pero no se editan ni se crean nuevos.

**Cómo se cambia una regla:** se edita este documento y se añade una línea en `docs/HISTORIAL_CAMBIOS.md`, en el mismo
PR que el código, y se actualiza la fecha de arriba. Un campo nuevo se escribe aquí primero y después en el código.

**Palabras que se usan aquí:** *perfil* = un cliente + un cargo con sus condiciones · *meta* = vacantes al día de un
perfil · *techo* = máximo de vacantes nuevas del día · *lote* = las vacantes elegidas del día · *bodega* = todo lo
guardado de los últimos 30 días · *va corto* = está bajo su meta (o bajo 5) · *rescate* = completar con vacantes de
la bodega · *ampliación* = último recurso que relaja algo · *exacto / similar / cercano* = qué tan parecido es el
título al cargo · *Comunidad* = el cliente que es el grupo de WhatsApp.

## 1. Modos de trabajo

- **Modo panel** (hay una versión de configuración vigente en Supabase): clientes con perfiles, cargos y metas; la
  captura busca solo los cargos y lugares de esa versión y asigna por perfil (v6, v21).
- **Modo heredado** (sin versión vigente): seis cargos fijos, veinte vacantes por cargo. Solo filtran el cargo (mapa de cargos), 30
  días, que siga abierta, sin repetir, enlace comprobado y que se pueda postular desde el país elegido. Inglés, nivel y
  años solo se muestran como columnas. Nada de lo que sigue cambia este modo salvo que se diga (v6, v24).
- La captura no guarda perfiles ni datos de clientes en su estado público, reportes ni cachés (v6).

## 2. Ubicación y países

- **Cualquier país:** la residencia de un perfil y los lugares donde trabajaría pueden ser de **cualquier país** del
  mundo; una vacante sirve si cumple el perfil, no por ser de LATAM o España (decisión 27 nov; v23, v40).
- **Brasil es un país como cualquier otro:** quien vive en Brasil recibe remotas mundiales y vacantes de Brasil, en
  español o inglés según su perfil. Deja de valer la restricción de v12 (Brasil solo dentro de remotas para varios
  países) (decisión 27 nov).
- **Dónde trabajaría:** el perfil tiene hasta 10 filas `{países, ciudades, modalidades}`; la primera es donde vive.
  Cada fila necesita un país o una ciudad y al menos una modalidad; las regiones se convierten en sus países al guardar.
  La ubicación cumple si **alguna fila** acepta la vacante; si ninguna, los motivos son los de la primera. Los perfiles
  sin filas se convierten solos con el mismo resultado de antes (`Perfil.filas`); el importador conserva sus columnas
  (v30).
- **Si el aviso nombra un país, manda ese país.** Un país cubierto cuenta solo si está en `paises`; uno de fuera, si el
  aviso lo nombra (`paises_mundo`) (v49).
- **Remota:** sirve si está abierta a un país de la fila, es mundial, o nombra el país de la persona aunque sea en la
  letra pequeña. «Anywhere in <lugar>» o «en cualquier parte de México» no es mundial: manda el lugar nombrado;
  «anywhere in LATAM» sigue siendo LATAM (v49, v50).
- **Horario:** la franja horaria solo abre una remota que **no nombra país**, y solo para las zonas que el perfil marcó
  (`acepta_horario`, hasta 12 zonas `UTC±H`, cada una ±1 h). La zona del país donde vive no cuenta sola. Sin horario
  marcado, la vacante sigue «por confirmar» (v35, v49).
- **Residencia obligatoria:** en una remota con frase de residencia, solo valen los países de esa frase. «US-based»
  solo restringe si habla de la persona o del puesto, no de la empresa (v49).
- **Letra pequeña en español:** frases como «abierto a candidatos de…» o «puedes postular desde…» **suman** países a
  una remota que ya nombra un país concreto; nunca recortan ni pisan una restricción de residencia. Las frases de la
  empresa, de beneficios o vagas no abren nada (v50).
- **Presencial e híbrida exigen ciudad:** la fila necesita ciudades y el aviso debe nombrar una o quedar a 50 km o
  menos. Motivos: «falta la ciudad en el perfil» y «oficina sin ciudad confirmada». Una región no sirve para
  presenciales. La ciudad implica su país (v24, v38, v49).
- **La ciudad no anula el país:** el nombre de una ciudad solo cuenta si el país del aviso es uno de la fila
  (o el de la ciudad, en una fila sin países): «Santiago» de Chile no acepta «Santiago de Cali». Una fila solo con
  ciudades toma el país de esas ciudades si todas apuntan al mismo (v49).
- **Vacante sin modalidad declarada:** solo si el perfil acepta las tres modalidades y su país está entre los de la
  vacante; nunca se inventa la modalidad (v8).
- **Lectura de lugares** (`buscador/paises.py`, sin IA): tabla ISO completa de 249 países (`datos/paises_mundo.yaml`)
  con siglas, nombres y subdivisiones; los nombres ambiguos nunca deciden solos; AR, CO y PA tras una ciudad solo
  cuentan si la ciudad es de ese país; PA es Panamá y PY Paraguay (v13, v14, v15). GeoNames (CC BY 4.0) da el país de
  una ciudad de fuera solo si tiene 5× más habitantes que otro país (20× frente a uno cubierto); si no llega, no se
  adivina. La lista curada de `datos/paises.yaml` siempre manda (v19, v38). La sigla de un estado de EE. UU. manda sobre la ciudad homónima («Panama City, FL» es EE. UU.); códigos
  postales, provincias de Canadá y Australia, «US-Remote» y apodos de `datos/alias_lugares.yaml` (v38). Áreas
  metropolitanas de `datos/areas_metropolitanas.yaml` (v32). Una región como ubicación vale solo si el aviso no es
  presencial ni híbrido; vale la región del título si la ubicación no dice ningún lugar (v19).
- **El país escrito al final manda** en una ubicación de un solo lugar («ciudad, región, país», un único país con su
  nombre): el nombre de un estado o región de otro país en los tramos de antes no suma ese país («Califórnia, Paraná,
  Brasil» es solo Brasil; «Birmingham, Alabama, United States», solo EE. UU.). Los errores conocidos de un portal se
  corrigen por texto exacto en `datos/ubicaciones_corregidas.yaml`, con evidencia del aviso («California, Pará,
  Brasil» de LinkedIn es EE. UU.) (7.E, 27 nov).
- «Autorizado para trabajar en el país» se refiere al país del propio aviso (v14). `puede_trabajar_en` admite hasta 60
  países y el importador acepta regiones (v26).
- **Get on Board:** `fully_remote` = cualquier país; `remote_local` = los países de `location_tenants`; sin país,
  «por confirmar» (v18).
- **Admisión y limpieza:** en modo panel se conserva una vacante de fuera si sirve a algún perfil (`_sirve_a_perfiles`;
  por horario, solo si no nombra país). Una vacante se conserva si sirve a algún perfil, sea del país que sea
  (decisión 27 nov; v24, v40, v49).
- **En caso de duda, no entra.** Un país desconocido nunca completa la meta (excepción: los posts, §10) (v17, v23, v28).

## 3. Idioma

- Solo se entregan avisos en **español o inglés**, y solo los idiomas que acepta el perfil: a quien solo acepta
  español nunca le llega un aviso en inglés (v12, v27, v44). **El idioma lo decide el perfil, no el país donde vive**
  (decisión 27 nov).
- `es` o `en` solo con **evidencia positiva**: palabras exclusivas, proporción mínima y ventaja frente a 14 idiomas de
  referencia. Sin evidencia, el idioma queda vacío y no se entrega. Un bilingüe español-inglés pasa (v15).
- Sin descripción no se sabe el idioma y la vacante no se entrega (v40, v50).
- Un título cuenta como español con `datos/titulos_idioma.yaml` (editable); títulos con palabras del portugués no
  cuentan (v44, v49).

## 4. Cargo, afinidad y funciones

- **Grados del cargo:** exacto, similar y cercano; los cercanos entran directo, después de exactos y similares. Los
  grados describen afinidad del cargo, no un puntaje de contratación (v6, v27).
- **Cargo operativo** (`panel/contenido.py::cargo_operativo`): un solo cargo rellenado para clasificar, asignar y
  mostrar: lo que escribió el operador, los sugeridos si no puso ninguno, los títulos aprendidos y, si no tiene
  funciones propias, la huella de su familia del mapa más la calculada de noche (`panel_ajustes.huellas_cargos`) (v49).
- **Evidencia de funciones** (sin IA): `fuerte`, `debil`, `ninguna`, `sin_huella` y `otro_oficio`. `ninguna` y la falta
  del distintivo de un cargo compuesto («No menciona IA») **solo ordenan**: la vacante llega al final con «Funciones por
  confirmar». `otro_oficio` (señal de otro oficio, `datos/oficios_ajenos.yaml`) **no se entrega sola**: va a «Por
  confirmar». Un título que es exactamente un nombre del cargo, o uno aprobado, nunca se retiene (v49).
- **Título genérico + descripción** que nombra el cargo 2 o más veces = similar. **Coincidencia solo por funciones**
  (grado `funciones`) nunca se entrega sola: va a «Por confirmar» (v25).
- **Nombres hermanos en español** (mismo oficio, otro nombre) se usan **solos** para buscar y reconocer (grado
  similar), con el control de funciones: los títulos exactos en español de la familia del mapa y los compuestos del
  glosario (`datos/glosario_cargos.yaml`). Los «similares» del mapa (oficios vecinos) **no** se usan solos: siguen como
  sugerencias. Lo que el operador ponga en «excluidos» no se usa (v50).
- En español solo se busca lo que se reconoce: `consultas_es` = nombres en español del cargo y títulos exactos en
  español de su familia (v49). Plurales cuentan como singular y femenino = masculino (v37, v49).
- Un oficio parecido no se vuelve equivalente solo; no se inventan sinónimos. La expansión usa normalización,
  variantes, ESCO y términos editables; un cargo que solo busca por su nombre lo avisa (v6, v37).
- Una vacante del lote llega también a perfiles de otro cargo que la reconoce exacta o similar (nunca solo cercana);
  cuenta para su meta, no ocupa cupo del lote y nunca llega dos veces a la misma persona (v43). El `match_grade` es el
  del cargo que la recibe (v49).
- El importador añade nombres y funciones a cargos existentes; nunca quita (v27).
- Desarrollo genérico no cuenta como QA ni como IA (v4).
- **El nombre más largo dice el oficio:** un término de una sola palabra del cargo («tester», «qa») no basta si es parte
  del nombre de varias palabras de otro oficio del mapa que trae el título («Penetration Tester» es Ciberseguridad, no
  QA; «QA Tester» o «Software Tester» siguen siendo QA). La similitud textual no cuenta si el título trae un `excluir`
  de la familia del cargo en el mapa («Analista de Pentesting» no es «analista de testing») (7.E, 27 nov).

## 5. Qué descarta y qué solo ordena

- **Descartan solo:** (1) la ubicación (§2); (2) el idioma del aviso (§3); (3) las reglas del sistema: que siga abierta,
  enlace donde se postula comprobado, sin repetir, fecha de publicación confirmada y **máximo 30 días** (v27, v33).
- **Solo ordenan y dejan etiqueta** (nunca descartan): años de experiencia, nivel (junior/prácticas), **nivel de inglés
  exigido** («Pide inglés C1»), salario menor, palabras que el perfil no acepta, tipo de contrato, la antigüedad pedida
  por el perfil, la restricción «otra…» y la evidencia de funciones. Cada cosa que no cumple pesa como un grado menos;
  primero llegan las que encajan en todo (v27, v33, v35, v49).
- Lo **no informado** (años, inglés) no descarta ni avisa (v27).
- **Experiencia:** un solo campo «Años de experiencia»; el rango es de N menos a N más con margen 3 o 4 (por defecto 3).
  Los perfiles antiguos sin ese campo conservan su mínimo y máximo. Con 5 años o más se etiqueta lo junior/prácticas;
  con 2 o menos no se mira la experiencia (v20, v22, v27).
- **Salario:** se compara en cualquier moneda con `datos/tasas_cambio.yaml` y margen del 10 %; no se convierte con
  monedas inestables (ARS, VES), monedas fuera de la tabla ni tasas de más de 120 días. Un «$» solo no es moneda. Solo
  decide si aparece la etiqueta (v26, v27). Las tasas se actualizan con `python -m buscador.tasas --actualizar`.
- **Palabras:** lo pedido como deseable («plus», «nice to have», «se valora»…) no cuenta como mención; en el título
  siempre cuenta (v22).
- **Prioridades** (`sectores_preferidos`, `palabras_preferidas`) solo ordenan (v22).
- Orden por calidad en Vacantes y WhatsApp: coincidencia del cargo, lo que no cumple, evidencia y fecha (v49).

## 6. Metas, techo diario y Comunidad

- **Meta diaria por perfil** (0 a 120; un perfil nuevo empieza con 10; 0 = no busca) y **techo del día** editable (1 a
  600, por defecto 120) que protege los consumos. El cupo por cargo no se edita: lo calcula el servidor con las metas
  (v21).
- Para aplicar, las metas de los clientes reales no pasan el techo y la suma del día va de 1 al techo; cada cargo con
  cupo necesita un perfil activo (v21, SQL 015).
- **Comunidad** (grupo de WhatsApp): recibe **después** de los clientes reales, primero lo que no llegó a ningún
  cliente real, con lo que cabe bajo el techo y **hasta su meta**; puede recibir vacantes que también llegaron a
  clientes (v21, v43).
- Lo ya entregado hoy de un cargo que salió de la configuración se conserva en el lote y cuenta para lo que sobra del
  techo; no recibe vacantes nuevas (v49).

## 7. Selección, completar y entrega

- Una oportunidad cuenta **una vez** aunque esté en varios portales o la reciban varios clientes; `ofertas` tiene una
  fila por vacante reconocida y no se rellenan cupos con copias (v5, v6).
- Variedad en el lote: idioma, nivel, país, modalidad y fuente; **máximo 2 por empresa** (4 solo como último recurso)
  (v11, v27). Nunca dos veces la misma vacante a la misma persona (v11).
- **Completar a quien va corto:** hasta su **meta diaria**. Hasta 5 vacantes siempre cabe; del mínimo a la meta, una
  vacante que hoy aún no usa nadie solo entra mientras lote + añadidas no pasen del techo del día. Orden: lote → reutilización de vacantes de otros días que esa persona nunca recibió → rescate con toda
  la bodega (cargo, ubicación e idioma; 2 por empresa; enlace de 24 h) → ampliación como último recurso y **solo hasta 5**
  (`remota_cercana`, `empresa_4`; también al reutilizar y al rescatar: de 5 a la meta solo entra lo que cumple el
  perfil, decisión de Oscar 27 nov) → posts. Comunidad y los posts se quedan en el mínimo de 5 (v11, v27, v36, v49).
- **Las ampliadas van marcadas:** `remota_cercana` da a un perfil sin «remoto» (presencial o híbrido) las remotas que
  su primera fila (donde vive) aceptaría: abiertas a uno de sus países, mundiales o por su franja horaria; nunca una
  cerrada a otros países. El panel las marca «Ampliada: …» en la lista de Vacantes y en la ficha; el WhatsApp las
  incluye después de las demás vacantes formales (si caben en las 10), con su modalidad y sin la marca (v9, v27, v49).
- Lo asignado en pasadas anteriores del mismo día cuenta para la meta y el techo; si no se puede leer, se completa
  solo hasta el mínimo (v49).
- Las rescatadas no cuentan en el cupo ni van a `ofertas` (marca `rescatada`) (v36).
- Turnos de búsqueda por persona: peso = meta, ×2 si va corta o es nueva, ×2 si su país no tiene fuentes propias, ×2
  si solo acepta español; una búsqueda compartida cuenta para todas; sus lugares principales y los de quien va corto
  van primero (v37, v40, v49). Una búsqueda repetida pide solo lo nuevo desde la vez anterior, salvo que esa vez no
  dejara nada útil: entonces pide los 30 días; una combinación con 3 búsquedas seguidas sin nada útil pasa al final de
  los turnos de su persona hasta que vuelva a traer algo (`estado["rendimiento"]`) (v40). Los lugares salen de todas las filas del perfil y de las regiones de
  `datos/regiones_busqueda.yaml`; «remoto LATAM» solo para quien vive en LATAM (v40).
- La entrega diaria comprueba Supabase antes de recoger (reglas de integridad). Una elegida que después cerró es un
  aviso y no se comparte (v40).
- **Cómo termina la búsqueda diaria: tres estados** (`buscador/validacion.py`, paso «Comprobar meta y
  sincronización» de `bodega.yml`) (v52):
  - **COMPLETA:** todo bien → corrida en verde y ping de éxito a Healthchecks.
  - **CORTA:** meta del día incompleta o vacantes de la selección con el enlace sin comprobar (siguen sin compartirse
    hasta comprobarlas) → corrida en verde con `::warning::` y resumen de qué faltó por cargo (sin datos de clientes);
    ping de éxito. El déficit **no** hace fallar la corrida.
  - **AVERÍA:** sincronización con Supabase o catálogo sin confirmar, reconciliación sin confirmar (incluido el 57014),
    selección no registrada, operaciones centrales pendientes, sin catálogo válido o vacantes de hoy que ya no encajan
    en el perfil → corrida en rojo y aviso `/fail`. **Solo una avería hace fallar la corrida**; si hay avería y falta a
    la vez, manda la avería.
  - La segunda pasada (8:30) y su respaldo completan la meta según `trabajo/metricas_entrega.json`
    (`arranque.falta_completar`), no según el color de la corrida; un día CORTO solo por enlaces sin comprobar (meta
    cumplida) no la pide. En el panel un día corto sigue como «parcial» y «Buscar ahora» ofrece completar (v52).
  - Las demás partes que fallan (búsqueda, publicación) siguen poniendo la corrida en rojo (v52).
- Repetir el día solo completa o reintenta el mismo lote; nunca añade otro lote (v2). Un lote ya elegido no se reescribe
  para ocultar cierres o déficit; el déficit se informa (v3, v4).
- No se borran archivos históricos ni snapshots para ocultar déficit (v5).

## 8. Enlaces y comprobación

- **Solo enlaces donde se postula de verdad:** el sistema de postulación de la empresa, su página de empleo o un portal
  donde se postula ahí mismo. Nunca agregadores ni sitios de pago (lista en `datos/dominios.yaml`); se busca el
  original o la vacante no se guarda. **Enlace principal = LinkedIn** si está ahí; el de la empresa va en
  `enlace_directo` (v3, v5).
- **Vigencia:** para seleccionar vale una comprobación positiva de hace 24 h o menos; un cierre se recuerda 24 h y un
  bloqueo o fallo temporal 30 min antes de volver a comprobar; para compartir (lista, WhatsApp,
  CSV), comprobada en las últimas **24 h** (v9, v31).
- HTTP 200 no prueba que la ficha siga vigente; un 403/429, login, captcha o bloqueo **nunca** es cierre. Se rechazan
  404/410, agregadores, cobro por postular, cierres y expiración (v3, v39).
- La comprobación no inicia sesión, no usa cookies, ni Apify, ni envía formularios (v3, v39).
- **Cuenta como comprobado 24 h:** la ficha pública de LinkedIn leída en la búsqueda si trae título y descripción (v39);
  lo que la búsqueda de Indeed mostró hoy (v41); lo listado hoy por el portal de la propia empresa (Greenhouse, Lever,
  Ashby, Workable, SmartRecruiters, Recruitee) (v42); lo visto hoy en la búsqueda de InfoJobs con descripción de 200+
  caracteres (v50). No cuentan así Computrabajo, Get on Board ni Bumeran y portales hermanos (v42, v50).
- LinkedIn se comprueba con su ficha pública, de una en una, con pausa, en su propia fila; tras 3 bloqueos descansa la
  ronda. Los demás sitios van en paralelo. Primero lo de quien va corto (`cola_por_necesidad`) (v39, v41, v49, v50).
- Presupuestos: 800 enlaces en 10 min por búsqueda diaria; rescate hasta 200 enlaces en 5 min (30 en 60 s en las
  horarias); en «Buscar ahora» para quien falta, 240 s con el tiempo de ordenar incluido y 60 s reservados al refuerzo
  (v36, v39, v48, v49).
- Un enlace rechazado no invalida otro comprobado de la misma oferta; nunca se borra del histórico. Las vistas de SQL
  004 son del modo heredado y conservan su criterio de 6 h (v3, v4).

## 9. Fuentes

Una fuente nueva entra solo si pasa una prueba en vivo: se lista, trae descripción, se postula ahí mismo y su aviso se
puede comprobar (v50). Presupuestos en `datos/config.yaml`.

| Fuente | Regla vigente | Origen |
|---|---|---|
| LinkedIn público | Sin sesión ni cookie de nadie. Busca con los lugares de cada perfil (países de fuera por su nombre en inglés). Busca hasta la mitad de su tiempo y lee fichas el resto; un tiempo restante de 0 la detiene. Lee primero las fichas de avisos cuyo título es de un cargo buscado; reparte fichas entre lugares; la relectura va por turnos entre personas, primero quien va corta | v24, v32, v36, v37, v50 |
| Indeed (JobSpy) | 62 países, solo los de los perfiles. Repasa cada noche los 30 días con varios nombres por combinación (`indeed_repaso`, solo en la búsqueda completa). No se comprueba directo: vale «visto hoy» o que su `enlace_directo` de la empresa esté comprobado. JobSpy no se copia al repo ni se usa su clave fuera de JobSpy | v36, v40, v41, v50 |
| Portales de empresas (`ats.py`) | Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee; la lista crece con las empresas que traen las demás fuentes, Open Seat, RemotosLatam y WeRemoto. Un aviso que desaparece de un portal leído completo cuenta como cerrado | v2, v42, v44 |
| Open Seat, RemotosLatam, WeRemoto | Solo para descubrir empresas; nunca se toman sus avisos | v44 |
| Computrabajo | 18 países de LATAM; fecha de `datePosted`, nunca la de actualización; lee solo fichas de cargos buscados y relee las guardadas sin descripción; turno propio en español | v44, v49 |
| Elempleo (CO) | `ItemList` + `JobPosting`; cierre por `validThrough`; busca con nombres en español y generales | v27, v50 |
| Get on Board | Política remota leída (§2); consulta en español por cargo | v18, v44 |
| Hireline (MX, CO) y Magneto (CO) | Sitemap + `JobPosting`; nunca su búsqueda con parámetros ni su API (robots.txt) | v44 |
| Bumeran, Laborum, Multitrabajos, Konzerta | AR, MX, PE, VE, CL, EC, PA. API pública del portal; comprobación con su ficha (activo y mismo título); verse en la búsqueda **no** comprueba; un portal en descanso recibe una oportunidad más al final | v50, v51 |
| InfoJobs (ES) | Nunca se abre la ficha (captcha). 5 búsquedas por corrida y 15 páginas al día; se detiene al primer captcha. Con `INFOJOBS_CLIENT_ID`/`INFOJOBS_CLIENT_SECRET` usa la API oficial (solo en `bodega.yml` y `profunda.yml`): una ficha de hoy «activo» con descripción comprueba, «archivado» o «borrado» cierra, lo demás —también un 404— no decide; la captura horaria y el panel no reciben las claves y vale la comprobación de la última búsqueda (24 h) | v50 |
| Tecnoempleo (ES) | Portal (no agregador) por decisión de Oscar; ficha con `JobPosting`; comprobación normal | v50 |
| Tableros remotos | Remotive y Working Nomads con el enlace original; Himalayas, We Work Remotely, RemoteOK y Jobicy solo aportan empresas | reglas de integridad |
| Apify | Ver §10 | v11, v28 |
| Descartadas | OCC (bloquea); Brave y avisos por correo retirados el 16 nov | v27, v50 |

- Cualquier país del mundo se busca, como mínimo, con LinkedIn, portales de empresas y remotas de Get on Board (v44).
- Quien acepta español (solo o con inglés) recibe búsquedas con nombres en español; el peso doble es solo para quien
  solo acepta español (v50).
- Cada fuente anota el motivo de su fallo (`http.motivo_del_fallo`), sin direcciones ni claves; un bloqueo a las
  direcciones de GitHub se respeta (v51). Workable con 429 no se insiste en la misma corrida.
- Hallazgos en vivo que siguen valiendo: LinkedIn acepta consultas con OR y su página pública no muestra el enlace
  externo (sale de juntar con el portal de la empresa); Indeed bloquea la web (403) pero JobSpy funciona (estado).
- Las familias de los cargos que se entregan se buscan primero cada noche y sus avisos reciben antes la descripción
  (cobertura).

## 10. Posts y Apify

- **Apify:** actor formal `curious_coder/linkedin-jobs-scraper` (build fijado en `datos/config.yaml`) sin cookies, tope **USD 5 al mes** con reservas
  durables; en modo panel solo busca para perfiles con déficit (primero en español). Una clave rechazada detiene la
  fuente y avisa (v11, v44). El feed pagado de posts sigue desactivado (`publicaciones_por_dia=0`).
- `Central.rpc` abre conexión nueva tras 120 s sin uso; una reserva ambigua no se reintenta sola (v51).
- **Posts** de LinkedIn: solo como último recurso para perfiles bajo 5, etiquetados «Post», después de las vacantes
  formales; filtro estricto contra basura; nunca van a `ofertas`, al cupo ni a `trabajo/`. Si enlazan una ficha formal
  legible, se entrega esa ficha (v11).
- Ubicación de posts por pistas (autor, prefijo, moneda, dominio, empresa, ficha enlazada). Un post sin pistas puede
  completar el mínimo con «ubicación sin confirmar»; máximo 2 posts con país o modalidad perdonados por perfil al día;
  `posts_rescate` 50 (v28, v49).

## 11. «Por confirmar» y aprendizaje

- Entra lo que le serviría a alguien pero tiene una duda que el código no resuelve: el país, «coincide por funciones» u
  «otro oficio». La cola guarda hasta 300; el panel muestra todas por páginas y marca las 10 más útiles; prioridad para
  quien va corto (v16, v17, v29, v49).
- «Sirve» asigna hasta la meta y aprende el título o la ubicación; «No sirve» en una duda de cargo retira solo para ese
  cargo; «Aplicar a las iguales» nunca con ubicaciones genéricas (v16, v25, v49).
- Antes, el sistema intenta confirmar solo con el `JobPosting` de la ficha (300 fichas en 480 s por noche) (v16, v29).
- **Aprendizaje solo con código:** reglas del operador y aprendidas que solo resuelven lo «por confirmar» y nunca
  cambian un país ya reconocido; mínimo de evidencias; un conflicto desactiva y nada se reactiva solo (v17).
- Sugerencias claras se aplican solas de noche sin enseñar al aprendizaje (v32). No se pregunta lo cerrado ni lo ya
  resuelto (v19). Revisión masiva por CSV (v17).

## 12. WhatsApp y mensajes

- **Nada se envía solo.** Botón `wa.me` con el mensaje escrito; el operador revisa y envía. No hay API de WhatsApp ni
  automatización (v10).
- Contacto con teléfono `+código número`, nombre para saludar y **consentimiento**; sin consentimiento no hay mensaje
  (v10).
- Borrador diario por cliente: hasta **10** vacantes, **2 por empresa** (los posts no cuentan para ese tope), «Tengo N
  más…» si sobran; si hoy hay menos de 5, completa con los 3 días anteriores; nunca repite lo que ya fue en otro mensaje;
  regenerar no pisa uno abierto, enviado, descartado o editado. Texto por plantillas, sin IA (v10, v31, v46). Se prepara
  tras las búsquedas y con `mensajes.yml` (10:15 Bogotá).
- Copia manual desde Vacantes: el operador elige cuántas (10 por defecto), 2 por empresa, en partes si hace falta (v43).
- Cada vacante lleva «(ID N)» (v48). Si alguna es de días anteriores, el mensaje no dice «hoy» ni «nuevas» (v46).
- Mensaje de un día anterior: entran las listas y entregadas que siguen compatibles; las que no tienen 24 h se
  comprueban al momento (tope 30 s); las cerradas se quitan (v48).
- **«Mandarme todos a mi WhatsApp»:** un solo mensaje al número del operador (`panel_ajustes.operador`) con un enlace
  corto por cliente `/w/<borrador>.<firma>`: HMAC con llave derivada en el servidor de la credencial de servicio, válido
  solo hoy y mientras el mensaje esté pendiente o abierto, redirige a `wa.me` con el texto actual; sin sesión, sin la
  ficha en los registros, `Cache-Control: no-store` (v46).
- Mensajes dice cuántas vacantes son de hoy y cuántas de días anteriores (v46).

## 13. «Buscar ahora»

- Un solo botón; decide el servidor, nunca el navegador (`plan_busqueda`): sin búsqueda que haya armado lote hoy →
  búsqueda completa; ya corrió y hay perfiles bajo su meta → `enfoque=faltantes`; todos cumplen → no lanza. Si no puede
  leer los datos, hace la completa. No lanza si hay otra tarea larga en cola o corriendo (v45).
- **Para quien falta:** solo esas personas, sin las combinaciones de otros; no repite lo buscado hoy con los mismos
  nombres (usa otros nombres o la página siguiente, hasta 10 páginas); si cambian las condiciones del perfil, sí busca;
  30 días solo si la combinación nunca se buscó o no trajo nada; sin portales de empresas, listas de empresas,
  tableros ni descubrimiento; 12 min por fuente; una ronda de refuerzo; incluye Hireline y Magneto. Objetivo ~30 min
  (v47, v49).
- **Por cliente** (detalle del cliente): hoy sin lote → completa con sus perfiles primero; con lote → `enfoque=pedido`
  solo para sus perfiles bajo la meta. Los perfiles pedidos van en `panel_ajustes.busqueda_pedida`; nunca
  identificadores en las entradas del flujo ni en sus registros (v49).
- El servidor lanza `bodega.yml` con `GITHUB_ACCIONES_TOKEN` (token fino del repositorio, solo «Actions»); sin la llave
  el botón no aparece; nunca va al navegador (18 nov). Las búsquedas programadas usan siempre `enfoque=completo` (v45).
- La búsqueda completa de la mañana no cambia por estas reglas (v47, v48).

## 14. Reloj y horarios (hora de Bogotá)

- `bodega.yml`: principal 6:30, respaldos 7:15 y 7:50 (solo si la anterior no corrió), segunda pasada 8:30 y su
  respaldo 9:30. Captura horaria en el minuto 23. Mensajes 10:15. El horario de Bogotá solo programa: no limita países
  (18 nov; reglas de cobertura).
- Desde el 17 nov GitHub retrasa los horarios 8 a 12 h; lo pedido (`workflow_dispatch`) arranca al momento (v51).
- **Reloj** (`reloj.yml`): cadena de relevos con el temporizador del entorno `reloj` (30 min, se crea a mano:
  `docs/ACTIVAR_RELOJ.md`). Pide el siguiente relevo **antes** de lanzar nada; luego la captura horaria
  (`toca_captura`) o, entre 6:30 a. m. y 7:00 p. m., la búsqueda diaria si hoy no corrió (`toca_diaria`) (v51).
- Seguros: sin temporizador (espera < 20 min) no sigue; de los relevos vivos solo sigue el de número más alto; una
  búsqueda que falló o se cortó **no** se repite sola; una que GitHub quitó de la cola se pide como mucho 3 veces al
  día; no usa el grupo `publicar`; solo lee fechas y estados, sin datos de clientes ni claves (v51).
- El vigía de la captura horaria usa la misma `toca_diaria` desde las 7:00 a. m., una vez al día. Si la cadena se corta,
  la reanudan el horario propio del Reloj y cualquier búsqueda real (`hace_falta_revivir`). Una corrida de prueba en la
  rama principal cuenta como «ya corrió»: las pruebas se lanzan desde otra rama (v51).
- La captura horaria no consume Apify ni crea entregas, salvo cuando la configuración cambió después del lote del día
  (v2, v43).

## 15. Panel

- Privado para el operador; los clientes no entran. Sin autenticación configurada el servidor real queda cerrado;
  `--demo` usa datos ficticios y no toca Supabase (v6).
- **«Aplicar cambios»:** guarda y deja vigente la configuración desde **hoy** en Bogotá; la próxima búsqueda la usa, lo
  entregado no cambia y una búsqueda en curso relee la versión más nueva antes de asignar y no se cae. Si no se puede
  publicar, los cambios quedan guardados y el panel dice por qué (v43, v49).
- Sesión con cookie de acceso de 1 h y de renovación de 30 días (httponly, secure, samesite strict) hasta «Cerrar
  sesión» (v31).
- «Cobertura por persona» solo con lo medido, con «Qué hacer» por persona; nada se aplica solo (v37, v44).
- Ficha de la vacante con la descripción en bloques, nunca como HTML; la descripción que falta se trae una vez de la
  ficha original solo de dominios de la lista fija (1 MB, 12 s) (v29). `**negritas**` de LinkedIn se pintan como texto
  (v34).
- Vista previa del perfil con `ultimos_30` y `por_dia` (v35).
- CSV con las columnas del contrato v1; `/api/base.csv` añade `numero` al final (v48).

## 16. Datos de la vacante y tablas

- **`ofertas` (v1):** columnas y valores del contrato v1; una fila por vacante reconocida con `vacante_id` y
  `enlaces_alternativos`; las copias antiguas en `ofertas_enlaces_historicos`. Nunca se sobrescribe; lo que el aviso no
  dice queda vacío (ni la moneda de un «$» solo, ni la modalidad). Sus columnas no cambian (v1, v5).
- **Catálogo (`catalogo_vacantes`, v2):** aditivo; publicación, detección y última vista por separado; nunca usar
  actualización como publicación; `active`/`closed`/`archived`; no se borra el histórico (v2). Campos del mundo:
  `paises_mundo`, `alcance_mundial`, `zona_utc` (v23); `requisito_ingles` (v7); `numero` fijo y único (SQL 020, v48).
- **`entregas_diarias`:** un lote por fecha; no se sobrescribe una selección confirmada; seleccionada ≠ enviada (v2).
- **Identidad:** por URL compartida o contenido sustancialmente igual; títulos iguales sin evidencia no bastan; las
  fusiones conservan enlaces e IDs; lo ambiguo se conserva y se revisa (v5).
- Un futuro bot debe consultar el catálogo con comprobación vigente, no el `status=active` inmutable de `ofertas` (v3).

## 17. Supabase y migraciones

- **No se modifica SQL ya registrado:** se añade una migración nueva (también a `ENSAYABLES` y a
  `pruebas/test_migraciones.py`). Migraciones actuales: 002 a 021 (v2–v48).
- «Preparar Supabase» sube respaldo cifrado antes de aplicar SQL, registra hashes en `adaptia_migraciones` y activa por
  marca privada; no pedir copiar SQL a mano ni variables manuales. `SUPABASE_DB_URL` y `SUPABASE_BACKUP_KEY` se configuran
  una vez como Secrets; la clave administrativa solo prepara, nunca va a fuentes, navegador ni logs.
- Los cortes contienen **dieciséis tablas y tres secuencias** (`respaldo.SECUENCIAS`) (v16, v48).
- Estado operativo: SQL 003 + `ESTADO_SUPABASE_ACTIVO=true`; no asumir que está desplegado; no volver al contador local
  en silencio ni vaciar reservas o colas para resolver errores. Catálogo/horario: SQL 002 + `CAPTURA_HORARIA_ACTIVA=true`
  (v2; `docs/CONTRATO_ESTADO_OPERATIVO.md`).
- No se modifica el estado histórico v1 (`ofertas` y sus snapshots) (v4). El horario consulta la marca privada de
  activación aunque no exista la variable antigua (instalación automática).
- Activar requiere migración y variable: no afirmar que algo está activo porque el código existe; acreditarlo con su
  ejecución (v2).
- `python -m pruebas.probar_migraciones` solo en PostgreSQL aislado.
- Limpiezas de `ofertas` solo con su flujo manual (huella + `BORRAR` + copia cifrada); `entregas_diarias` y
  `panel_asignaciones` no se tocan (v12, v13). El objetivo de v13 (borrar lo de fuera de LATAM y España) deja de
  valer: una vacante que sirve a algún perfil no se borra por su país; solo por idioma distinto de español o inglés
  (decisión 27 nov). Fuera de eso, la limpieza de 30 días solo afecta al buscador activo:
  no se borran ofertas de Supabase (cobertura).
- La entrega sube a `ofertas` sin sobrescribir (un `external_id` repetido se ignora); hay cola de reintentos a
  Supabase; `--prueba` no marca entregadas ni sube (v1; reglas de integridad).
- SQL 010 y 011 recorren el grafo de identidades solo desde `ofertas` y referencias explícitas; comprobar instalación
  y la captura posterior antes de afirmar una recuperación (v5).
- **La reconciliación va por lotes (SQL 021, 27 nov):** la API llama de a 5.000 referencias explícitas y luego de a 500
  ofertas; cada lote es una transacción corta e idempotente, con un solo reintento si Supabase lo corta (57014). Así
  ninguna llamada crece con el catálogo ni con las ofertas. Mismas reglas de identidad, rechazos y archivo que 011,
  pero un rechazo en un lote deja confirmados los lotes anteriores (la corrida sigue en AVERÍA y repetir es seguro);
  `reconciliar_ofertas()` sigue existiendo para el instalador y el diagnóstico (todo en una transacción).
- El arranque importa un corte coherente; un respaldo previo a cambios no equivale a copias periódicas (domingos,
  `respaldo.yml`). El traspaso (`traspaso.yml`) va a un destino vacío y propio, exige tablas, memoria, colas y reservas
  (no solo cambiar secretos) y el origen trasladado deja de capturar (`docs/ENTREGA_AL_CLIENTE.md`).
- `publicar.py` conserva `datos/salud.json` y `trabajo/` en la rama `publicado` para la siguiente captura, sin borrar
  inventario, colas ni reservas. Las notas antiguas de instalación pendiente no prueban el estado actual.
- Despliegue del panel: Docker y guía sin proveedor obligatorio (`docs/PANEL_CONTROL.md`).

## 18. Seguridad y lo prohibido

Las «Reglas innegociables» de `CLAUDE.md` son el resumen de esta sección: si una cambia, se cambian las dos.

- **Sin IA en la búsqueda, la afinidad ni el aprendizaje.** La IA solo ayuda a ampliar el mapa leyendo archivos cortos
  (`reportes/`), nunca la bodega completa (v17; reglas de integridad).
- **Nada se envía solo** (WhatsApp, correos de clientes) (v10).
- **LinkedIn sin sesión ni cookie de nadie** (`li_at` incluida), ni actores de Apify que la pidan.
- Ninguna clave, ID, correo, teléfono ni dato de clientes en el repositorio, registros de Actions, reportes públicos,
  `trabajo/` ni la rama `publicado`; las claves van en los secretos (v10, v11, v40). La credencial de servicio nunca
  llega al navegador (v6).
- Las alertas por correo (Resend) solo llevan cifras por cargo, nunca datos de clientes (v10).
- No se reintroducen la web de Pages/Cloudflare, Excel, el envío automático de WhatsApp ni el seguimiento de
  postulaciones. No se depende del repositorio `ux_job_agent`.
- No se borra lo entregado, el historial, las reservas ni las colas para «arreglar» un error.
- No abrir datos reales sin autorización; para probar, `--demo`.
- Si falta una decisión, se pregunta antes de inventar una regla.

## 19. Medición

- Reportes públicos solo con conteos, sin datos de clientes: `embudo_idioma` (v50), `embudo[cargo].por_idioma` y
  `verificacion_enlaces.en_la_corrida` (v51). Cifras por persona solo en el resumen privado (v40).
- `python -m buscador.medicion --bodega …` mide sobre una bodega guardada (v49).
- Línea base del objetivo mundial: `--comparar pruebas/datos/linea_base_mundial.json` repite 8 escenarios ficticios del
  modo panel sobre la bodega fijada y falla si cambia el de control (`docs/LINEA_BASE_MUNDIAL.md`, 27 nov).

## Decisiones recientes

- **27 nov — objetivo mundial** (ver arriba). Resuelve las dos dudas anteriores: una vacante se conserva si sirve a
  algún perfil (deja de valer el borrado por país de v13) y Brasil es un país como cualquier otro (deja de valer la
  restricción de v12). El código todavía aplica parte de esas restricciones: ver la lista del PR que lo registró.

## Dudas para Oscar

Ninguna abierta.
