# Cómo funciona ahora — guía corta de entrada

Estado al 15 de noviembre de 2026, después de los ajustes de la reunión con Adaptia. Esta es la puerta de entrada:
explica qué hace el sistema, cómo se usa el panel día a día y cómo pedirle cambios a una IA sin romper nada. Los
detalles técnicos están en los documentos enlazados al final.

## 1. Qué es, en una frase

Cada mañana el sistema busca vacantes de empleo en portales públicos y, con los criterios de cada cliente, le asigna
las que le sirven. El operador las revisa en el panel, las descarga en CSV y le envía a cada cliente su mensaje de
WhatsApp a mano. **Nada se envía solo y la búsqueda no decide con inteligencia artificial**: todo son reglas escritas
en código y probadas. Lo único (opcional y hoy apagado) es que un LLM proponga nombres de búsqueda para un cargo, que
después el código filtra y reconoce (P-14.2).

## 2. Un día normal (hora de Colombia)

| Hora | Qué pasa | Qué haces tú |
|---|---|---|
| 6:30 a. m. | Búsqueda principal: LinkedIn público, Indeed, portales de empresas, Computrabajo, Bumeran y sus portales hermanos, InfoJobs y Tecnoempleo (v50), Get on Board y tableros remotos. Cada vacante útil se asigna a los perfiles que cumple. | Nada. Con el «Reloj» activado (fila siguiente) arranca entre las 6:30 y las 7:00 a. m.; sin él, desde el 17 nov GitHub la empieza con 7 a 11 horas de retraso. |
| Cada 30 minutos | «Reloj» (v51, hay que activarlo una vez: `docs/ACTIVAR_RELOJ.md`): desde el 17 nov GitHub dispara sus horarios con horas de retraso. El Reloj es una cadena de relevos dentro de GitHub que pide la captura de cada hora y, desde las 6:30 a. m., la búsqueda del día si no ha corrido. | Nada. Si un día no hay ninguna corrida del Reloj esperando, se reanuda sola con la siguiente búsqueda o con «Buscar ahora». |
| 7:15 y 7:50 a. m. | Respaldos: solo si GitHub no lanzó la de las 6:30, la hacen ellos (si no, terminan sin hacer nada). Desde las 7:23, la captura horaria también la lanza una vez si hoy no corrió. | Nada. |
| 8:30 a. m. | Segunda pasada: completa a quien le faltó. | Nada. |
| 9:30 a. m. | Respaldo de la segunda pasada: solo si la de las 8:30 no corrió y aún falta. | Nada. |
| Cada hora (minuto 23) | Captura corta: comprueba enlaces y suma vacantes nuevas sin repetir. | Nada. |
| 10:15 a. m. | Se preparan los mensajes de WhatsApp de cada cliente. | En «Mensajes», «Abrir en WhatsApp», revisar y enviar. |
| Cuando quieras | | Mirar el Resumen, decidir «Por confirmar» (un par de minutos) y descargar los CSV. |
| Domingos 5:41 a. m. | Copia de seguridad cifrada de la base. | Nada. |
| Una vez al mes | | Actualizar las tasas de cambio de los salarios: `python -m buscador.tasas --actualizar` y subir el cambio (o pedírselo a la IA). Con tasas de más de 120 días, los salarios en otra moneda dejan de compararse (el salario solo deja etiqueta). |

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

  Un cliente marcado **«Comunidad»** (el grupo de WhatsApp) recibe después de los reales, con lo que sobre del techo
  y hasta su meta.
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

Resumen corto; la regla exacta de cada punto está en [CONTRATO_VIGENTE.md](CONTRATO_VIGENTE.md), que es la fuente.

1. **El cargo:** el título (o un título genérico cuya descripción nombra el cargo) y, desde v49, las funciones del
   aviso. Sin funciones del cargo llega al final con «Funciones por confirmar»; si parece otro oficio, o solo coinciden
   las funciones, va a «Por confirmar».
2. **Solo descartan la ubicación, el idioma y las reglas del sistema** (abierta, enlace comprobado, sin repetir, fecha
   confirmada, 30 días). Si el aviso nombra un país, manda ese país; presencial e híbrida exigen ciudad en el perfil.
3. **Lo demás solo ordena y deja etiqueta:** años, nivel, inglés exigido, salario, restricciones y antigüedad.
4. **Cuántas:** primero las metas de los clientes reales sin pasar el techo; después Comunidad, hasta su meta.
5. **Si alguien no llega a su meta:** se le completa hasta ella con vacantes que nunca recibió (otros días y toda la
   bodega) y, como último recurso, posts etiquetados «Post». Nunca se repite una vacante a la misma persona.

## 5. Lo que el sistema no hace (a propósito)

- No envía mensajes ni correos por su cuenta.
- No usa la sesión ni las cookies de LinkedIn de nadie.
- No usa IA para decidir qué vacante sirve, ni para aprender títulos o ubicaciones. Para buscar, solo si se enciende
  `llm.terminos_activo`: un LLM propone nombres del mismo oficio por cargo (sin datos de personas).
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
- **`CLAUDE.md`**, en la raíz: las reglas innegociables y cómo trabajar. La IA lo lee sola.
- **Este documento**, para el panorama.
- **`docs/CONTRATO_VIGENTE.md`**: la regla vigente de cada tema (los `CONTRATO_DATOS_vNN.md` son históricos).

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
- Una regla o un campo nuevo se escribe primero en `docs/CONTRATO_VIGENTE.md` (y una línea en el historial) y
  después en el código. Ya no se crean contratos `CONTRATO_DATOS_vNN.md`.
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
- Reglas vigentes: [CONTRATO_VIGENTE.md](CONTRATO_VIGENTE.md). Los `CONTRATO_DATOS_vNN.md` quedan como historia.
- Entrega y traspaso al Supabase del cliente: [ENTREGA_AL_CLIENTE.md](ENTREGA_AL_CLIENTE.md) e
  [INSTALACION_AUTOMATICA.md](INSTALACION_AUTOMATICA.md).
- Si algo falla: [OPERACION_Y_RECUPERACION.md](OPERACION_Y_RECUPERACION.md).
