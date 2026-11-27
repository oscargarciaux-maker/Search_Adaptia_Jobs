# Cómo funciona ahora — guía corta de entrada

Estado al 15 de noviembre de 2026, después de los ajustes de la reunión con Adaptia. Esta es la puerta de entrada:
explica qué hace el sistema, cómo se usa el panel día a día y cómo pedirle cambios a una IA sin romper nada. Los
detalles técnicos están en los documentos enlazados al final.

## 1. Qué es, en una frase

Cada mañana el sistema busca vacantes de empleo en portales públicos y, con los criterios de cada cliente, le asigna
las que le sirven. El operador las revisa en el panel, las descarga en CSV y le envía a cada cliente su mensaje de
WhatsApp a mano. **Nada se envía solo y la búsqueda no usa inteligencia artificial**: todo son reglas escritas en
código y probadas.

## 2. Un día normal (hora de Colombia)

| Hora | Qué pasa | Qué haces tú |
|---|---|---|
| 6:30 a. m. | Búsqueda principal: LinkedIn público, Indeed, portales de empresas, Computrabajo, Bumeran y sus portales hermanos, InfoJobs y Tecnoempleo (v50), Get on Board y tableros remotos. Cada vacante útil se asigna a los perfiles que cumple. | Nada. GitHub a veces la empieza con 30–60 minutos de retraso. |
| Cada 30 minutos | «Reloj» (v51, hay que activarlo una vez: `docs/ACTIVAR_RELOJ.md`): desde el 17 nov GitHub dispara sus horarios con horas de retraso. El Reloj es una cadena de relevos dentro de GitHub que pide la captura de cada hora y, desde las 6:30 a. m., la búsqueda del día si no ha corrido. | Nada. Si un día no hay ninguna corrida del Reloj esperando, se reanuda sola con la siguiente búsqueda o con «Buscar ahora». |
| 7:15 y 7:50 a. m. | Respaldos: solo si GitHub no lanzó la de las 6:30, la hacen ellos (si no, terminan sin hacer nada). Desde las 7:23, la captura horaria también la lanza una vez si hoy no corrió. | Nada. |
| 8:30 a. m. | Segunda pasada: completa a quien le faltó. | Nada. |
| 9:30 a. m. | Respaldo de la segunda pasada: solo si la de las 8:30 no corrió y aún falta. | Nada. |
| Cada hora (minuto 23) | Captura corta: comprueba enlaces y suma vacantes nuevas sin repetir. | Nada. |
| 10:15 a. m. | Se preparan los mensajes de WhatsApp de cada cliente. | En «Mensajes», «Abrir en WhatsApp», revisar y enviar. |
| Cuando quieras | | Mirar el Resumen, decidir «Por confirmar» (un par de minutos) y descargar los CSV. |
| Domingos 5:41 a. m. | Copia de seguridad cifrada de la base. | Nada. |
| Una vez al mes | | Actualizar las tasas de cambio de los salarios: `python -m buscador.tasas --actualizar` y subir el cambio (o pedírselo a la IA). Con tasas de más de 120 días, los salarios en otra moneda dejan de descartar. |

## 3. El panel, pantalla por pantalla

El panel se abre en el **Resumen**. Cada tarjeta lleva a su pantalla y «Volver al resumen» regresa. Arriba a la
derecha, el botón con el sol o la luna cambia entre modo claro y oscuro (por defecto sigue al computador).

- **Resumen.** El bloque verde tiene una tarjeta por cliente con lo recibido hoy frente a su meta y lo que tiene por
  confirmar. Los que van peor salen primero y la barra se pone ámbar si no llegan a la mitad. Con 9 clientes o más,
  las tarjetas pasan a dos columnas.
  - Al tocar un cliente se abre su detalle: últimos 7 días, sus perfiles, lo que más corta en su cargo, sus vacantes,
    su CSV de hoy y sus «por confirmar» para decidir ahí mismo.
  - A la derecha están el techo del día, las vacantes de la última búsqueda, lo pendiente, los mensajes y la
    actividad.
- **Clientes.** Cada cliente tiene uno o más **perfiles** (un perfil = un cargo con sus condiciones). En cada perfil
  se define:
  - meta diaria;
  - país donde vive (cualquiera del mundo), modalidades y ciudades donde trabajaría (incluidas las de mudanza);
  - países a los que se mudaría, permiso legal para trabajar en otros países y horarios que acepta;
  - idioma del aviso, antigüedad, años de experiencia (±3 o ±4) e inglés;
  - prioridades: sectores y palabras que solo ordenan;
  - «Este perfil NO acepta…»: salario menor (comparado en cualquier moneda), palabras o tipo de contrato.

  Un cliente marcado **«Comunidad»** (el grupo de WhatsApp) recibe después de los reales, con lo que sobre del techo.
- **Cargos y metas.** Aquí se define el **techo del día** (120 por defecto), que protege los consumos. Cada cargo
  tiene una lista de «Nombres del cargo». En «Opciones avanzadas» están las funciones del cargo (con «Proponer
  funciones»), los cargos cercanos y los términos excluidos.
- **Vacantes.** Lo que recibió cada cliente, con «Por qué coincide», y la descarga del **CSV**: general o de un
  cliente, de un día o de toda la base, con las columnas del contrato.
- **Por confirmar.** Vacantes que le servirían a alguien, pero con una duda que el código no resuelve solo:
  - el país desde el que se puede postular;
  - un título distinto que «Coincide por funciones».

  Se decide con un clic. Lo aprobado se asigna ese mismo día y el sistema aprende la ubicación o el título para la
  próxima vez.
- **Mensajes.** El mensaje de WhatsApp de cada cliente, listo para abrir, revisar y enviar a mano.
- **Actividad.** Cada búsqueda con su resultado, cuántas vinieron de la búsqueda de cada perfil y de la amplia, y
  «Dónde se pierden las vacantes de cada cargo».

**Aplicar cambios** (26 nov, contrato v49) guarda y deja la configuración vigente: la próxima búsqueda la usa. Es el
único botón. En el detalle de cada cliente, **Buscar ahora** lanza la búsqueda solo para sus perfiles.

## 4. Cómo se decide qué vacante llega a quién

1. **El cargo.** El título coincide con los nombres del cargo, o es genérico («Especialista», «Consultor») y la
   descripción nombra el cargo. Si solo coinciden las funciones, va a «Por confirmar»; nunca entra sola.
   - Desde el 26 nov (contrato v49) también se leen las funciones del aviso. Si el título coincide pero la
     descripción no trae ninguna función del cargo, llega al final con la etiqueta «Funciones por confirmar». Si
     además parece otro oficio («QA Manufacturing Analyst»), va a «Por confirmar».
   - Los nombres hermanos en español del cargo (el mismo oficio con otro nombre: «Jefe de producto» para Product
     Manager, «Ingeniero de pruebas» para QA) se buscan y se reconocen solos (contrato v50), con ese mismo control
     de funciones. Los oficios vecinos siguen como sugerencias. En el diálogo del cargo
     están en «En español, se usan solos»; tocar uno lo deja de usar.
2. **La ubicación.**
   - Remota: abierta a su país, al mundo o a un país donde puede trabajar legalmente. Si el aviso nombra un país,
     manda ese país (contrato v49). Una remota que solo dice un horario, sin país, llega solo a quien marcó ese
     horario.
   - Presencial o híbrida: en una de sus ciudades (o a 50 km). Sin ciudad escrita en el perfil no llegan (contrato
     v49).
   - Si no se sabe, puede ir a «Por confirmar» (hasta 10 al día, primero las de quien va corto): un país desconocido
     nunca completa la meta.
3. **Idioma y fecha (descartan):**
   - el idioma del aviso, solo español o inglés según el perfil;
   - la publicación, de hasta 30 días.
   - **Desde el 16 nov (contrato v27) solo esto y la ubicación descartan.**
4. **Lo demás del perfil solo ordena y deja una etiqueta.** Las que encajan en todo van primero, y las demás llegan
   después con lo que no cumplen («Pide 7 años», «Pide inglés C1», «Salario menor al que pide»…):
   - años y nivel;
   - inglés exigido;
   - restricciones;
   - la antigüedad que pidió el perfil.
5. **Enlace comprobado.** Solo se entregan enlaces donde de verdad se postula y que siguen abiertos.
6. **Cuántas.** Primero se cubren las metas de los clientes reales, sin pasar el techo. Después Comunidad recibe con lo
   que sobre. Entre varias candidatas ganan las que coinciden con las prioridades, con variedad de empresas, países y
   fuentes.
7. **Si alguien no llega a su meta.** Se le completa hasta su meta diaria (contrato v49; antes hasta 5) con vacantes
   de días anteriores y de toda la bodega que esa persona nunca recibió, sin pasar el techo del día. Los cargos
   cercanos ya entran directo. Como último recurso: remotas abiertas a su
   país, más de la misma empresa, vacantes de días
   anteriores que esa persona nunca recibió y, como último recurso, posts de LinkedIn etiquetados «Post». Nunca se
   repite una vacante a la misma persona.

## 5. Lo que el sistema no hace (a propósito)

- No envía mensajes ni correos por su cuenta.
- No usa la sesión ni las cookies de LinkedIn de nadie.
- No usa IA para buscar ni para decidir; tampoco para aprender títulos o ubicaciones.
- No hace seguimiento de postulaciones.
- No inventa datos: lo que el aviso no dice queda vacío.
- Límites de gasto: Apify como máximo USD 5 al mes. El panel en el plan gratuito se duerme y la primera visita puede
  tardar un minuto.

## 6. Si algo no se ve bien

- **Pocas vacantes para un cliente:** abrir su detalle en el Resumen («Lo que más corta en su cargo») y la estimación
  de su perfil en Clientes. Casi siempre es un filtro muy estricto (país, modalidad, inglés o años) o un cargo con pocos
  nombres.
- **La búsqueda falló o no aparece:** mirar Actividad. En GitHub → Actions, revisar «Bodega nocturna». GitHub avisa por
  correo al dueño del repositorio cuando un flujo falla.
- **Algo raro en el panel:** recargar. Si sigue, anotar la pantalla y lo que se hizo, y pedir revisión (ver la sección
  siguiente).

## 7. Cómo pedirle cambios a una IA (por ejemplo, Claude Code)

El repositorio está preparado para que una IA lo lea y lo cambie con cuidado.

**Qué leer primero:**
- **`CLAUDE.md`**, en la raíz: las reglas vigentes. La IA lo lee sola.
- **Este documento**, para el panorama.
- El **contrato de datos** más reciente (`docs/CONTRATO_DATOS_v25.md` y los anteriores que cite): qué significa cada
  campo y cada regla.

**Cómo pedirlo bien:**
- Una cosa por vez y en lenguaje normal. Ejemplos: «que los perfiles puedan excluir empresas concretas», «añade el
  portal X», «¿por qué Laura recibió pocas ayer?».
- Pedir que primero haga preguntas y un plan, y que no cambie nada hasta aprobarlo.
- Pedir un PR por cambio, con pruebas, y revisarlo antes de fusionar. La IA nunca fusiona sola.

**Atajos ya preparados** (habilidades del proyecto, en `.claude/skills/`):
- `diagnostico`: qué pasó en la última búsqueda.
- `ampliar-mapa`: títulos que no encajaron en ningún cargo.
- `nueva-familia`: añadir un tipo de cargo.
- `nueva-fuente`: añadir un portal.
- `auditor-ux`: revisión de usabilidad del panel con capturas de demostración.

**Reglas que la IA debe respetar** (están en `CLAUDE.md`; recuérdaselas si duda):
- Nunca poner claves, correos, IDs ni datos de clientes en el repositorio. Las claves van en los secretos de GitHub o
  del alojamiento.
- Un campo nuevo se escribe primero en un contrato nuevo y después en el código.
- No modificar SQL ya instalado: se añade una migración nueva.
- Antes de subir: `python -m pytest -q`. Si cambia el panel, también el formato, la compilación y las pruebas de
  navegador (Playwright), incluida la de contraste en claro y oscuro.
- No abrir datos reales de clientes sin permiso; para probar, usar la demostración (`--demo`).

**Dónde vive cada cosa:**

| Carpeta | Qué hay |
|---|---|
| `buscador/` | La búsqueda: fuentes, lectura de avisos, países, cargos, limpieza, entrega |
| `panel/` | El servidor del panel: modelos, filtros por perfil, asignación diaria, bandeja «Por confirmar» |
| `web/` | La interfaz del panel (React); `web/tests/` son los recorridos de navegador |
| `datos/` | Lo que se cambia sin tocar código: mapa de cargos, países, dominios, presupuestos (`config.yaml`) |
| `supabase/migraciones/` | Las tablas, una migración por cambio |
| `pruebas/` | Las pruebas de Python |
| `.github/workflows/` | Los horarios automáticos (búsquedas, mensajes, copias) |

## 8. Mapa de documentos

- Uso diario: [GUIA_CLIENTE.md](GUIA_CLIENTE.md) y [PANEL_CONTROL.md](PANEL_CONTROL.md).
- Qué cambió y cuándo: [HISTORIAL_CAMBIOS.md](HISTORIAL_CAMBIOS.md).
- Reglas de los datos: [CONTRATO_DATOS_v50.md](CONTRATO_DATOS_v50.md) (más vacantes en español: fichas de LinkedIn
  al cargo, repaso de Indeed, nombres hermanos), [CONTRATO_DATOS_v49.md](CONTRATO_DATOS_v49.md) (ubicación sin fugas,
  funciones, completar hasta la meta y panel de un botón), [CONTRATO_DATOS_v27.md](CONTRATO_DATOS_v27.md) (qué descarta y qué solo ordena; «Aplicar
  hoy»), [v25](CONTRATO_DATOS_v25.md) (funciones), [v24](CONTRATO_DATOS_v24.md)
  (búsqueda por perfil), [v23](CONTRATO_DATOS_v23.md) (ubicaciones del mundo), [v22](CONTRATO_DATOS_v22.md) (filtros
  del perfil) y [v21](CONTRATO_DATOS_v21.md) (metas y techo).
- Entrega y traspaso al Supabase del cliente: [ENTREGA_AL_CLIENTE.md](ENTREGA_AL_CLIENTE.md) e
  [INSTALACION_AUTOMATICA.md](INSTALACION_AUTOMATICA.md).
- Si algo falla: [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md).
