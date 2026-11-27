# CLAUDE.md — Buscador de vacantes

## Qué es
**Objetivo (decisión 27 nov):** una persona de cualquier país crea su perfil y recibe vacantes que le sirven según sus
características; si pide remoto mundial, le llegan de todo el mundo. El idioma lo decide el perfil, no el país donde
vive (solo español o inglés). El origen LATAM/España es histórico.

Cada mañana el sistema busca vacantes en portales públicos y, con los criterios de cada cliente, asigna las que le
sirven. Un panel privado (React/Vite + FastAPI) deja al operador gestionar clientes, perfiles, cargos y metas diarias
bajo un techo del día, revisar vacantes, descargar CSV y copiar el WhatsApp de cada cliente para enviarlo a mano.
Sin versión de panel vigente sigue la captura heredada: seis cargos fijos, veinte vacantes por cargo.

**Las reglas vigentes están en `docs/CONTRATO_VIGENTE.md`: es la fuente principal y gana sobre cualquier otro
documento.** Los `docs/CONTRATO_DATOS_vNN.md` son históricos (el código los cita): no se editan.
Panorama para el operador: `docs/COMO_FUNCIONA_AHORA.md`. `docs/PLAN.md` es diseño histórico y no prevalece.

## Reglas innegociables
- **Sin IA en la búsqueda, la afinidad ni el aprendizaje.** Todo es código con pruebas. La IA solo amplía el mapa de
  cargos leyendo archivos cortos (`reportes/`), nunca la bodega completa. No inventar sinónimos ni un puntaje de
  contratación.
- **Nada se envía solo.** WhatsApp solo con `wa.me` y a mano; no hay API de WhatsApp ni automatización de mensajes.
- **LinkedIn nunca con la sesión ni la cookie de nadie** (`li_at` incluida), ni actores de Apify que la pidan.
- **No modificar SQL ya registrado** en `supabase/migraciones/`: se añade una migración nueva (y se agrega a
  `ENSAYABLES` y a `pruebas/test_migraciones.py`). `ofertas` conserva sus columnas v1.
- **Traspasable, sin claves en el repo:** nada depende de las cuentas personales de Oscar. Ninguna clave, ID, correo,
  teléfono ni dato de clientes en el repositorio, en registros de Actions, en reportes públicos, `trabajo/` ni la rama
  `publicado`; las claves van en los secretos. `pruebas/test_repositorio.py` lo revisa. La credencial de servicio y la
  clave administrativa nunca llegan al navegador, a las fuentes ni a los logs.
- **Solo enlaces donde se postula de verdad** (portal de la empresa o portal donde se postula ahí mismo); nunca
  agregadores ni sitios de pago. Sin comprobación vigente no se entrega ni se comparte; un bloqueo no es cierre.
- **No inventar datos:** lo que el aviso no dice queda vacío (ni la moneda de un «$» solo, ni la modalidad).
- **No borrar para arreglar:** ni lo entregado, ni el historial, snapshots, reservas o colas; no ocultar déficit.
- **Prohibido reintroducir:** la web de Pages/Cloudflare, Excel, el envío automático de WhatsApp y el seguimiento de
  postulaciones. No tocar ni depender del repositorio `ux_job_agent`.
- **Datos reales:** no abrirlos sin autorización; para probar, `--demo` (datos ficticios, no toca Supabase). El acceso
  real queda cerrado hasta configurar el inicio de sesión.
- **No afirmar que algo está activo** porque el código existe: la activación requiere migración y variable y se
  acredita con su ejecución (`docs/ACEPTACION_Y_ESTADO.md`).
- Si falta una decisión o algo no está claro, se pregunta antes de inventar una regla.

## Cómo se decide algo nuevo
**Una decisión nueva se escribe editando `docs/CONTRATO_VIGENTE.md` + una línea en `docs/HISTORIAL_CAMBIOS.md`. Ya
no se crean archivos `CONTRATO_DATOS_vNN.md`.** Un campo nuevo de la entrega va primero a `docs/CONTRATO_VIGENTE.md`
y después al código. Si una regla nueva contradice otra, se reemplaza la vieja en su sección (no se apila).

## Cómo se trabaja
- Una rama por alcance autorizado y un PR que Oscar revisa y fusiona. Nunca auto-fusionar.
- Antes de abrir cada PR: skill `thermos` (`.claude/skills/thermos/`) con sus dos revisores de solo lectura
  (`.claude/agents/thermos-errores.md` y `thermos-calidad.md`) sobre `git diff origin/main...HEAD`; lo grave se arregla
  antes de pedir revisión.
- Antes de cada push: `python -m pytest -q`. CI también prueba PostgreSQL; la interfaz necesita Node 24 y CI revisa
  formato, compilación y recorridos Playwright. `python -m pruebas.probar_migraciones` solo en PostgreSQL aislado.
- **Dependencias con huella:** `requirements.in` compilado con pip-compile en `requirements.txt` (comando en
  `pruebas/test_dependencias.py`); nunca `pip install` sin `--require-hashes`. JobSpy no se copia al repo.
- Calidad: job `auditoria` en CI (ruff, pip-audit, bandit alto, eslint y npm audit bloquean; vulture y knip informan),
  prueba axe, `docs/estandares/LISTA_DE_CONTROL.md` y skill `auditoria-codigo`. Un error tolerado deja `registro.aviso`.
- Prueba en vivo corta (unos 5 min, con internet): `python -m buscador.bodega --salida /tmp/prueba --prueba`.
- Lo que cambia sin tocar código vive en `datos/` (mapa de cargos, países, dominios, empresas, `config.yaml`).
- Respuestas a Oscar en español y en lenguaje sencillo.

## Estructura
- `buscador/` búsqueda en Python: `fuentes/`, `bodega.py`, `vacante.py`, `paises.py`, `etiquetas.py`,
  `verificar_enlaces.py`, `entrega.py`, `contrato.py`, `arranque.py`, `estado_operativo.py`, `migraciones.py`,
  `preparar.py`, `respaldo.py`.
- `panel/` servidor del panel (modelos, afinidad, ejecutor, bandeja, borradores) · `web/` interfaz (`web/tests/`
  Playwright).
- `datos/` archivos editables · `supabase/migraciones/` una migración por cambio · `pruebas/` · `reportes/` (los
  escribe la bodega).
- `.github/workflows/`: `bodega.yml` (búsqueda diaria y «Buscar ahora»), `incremental.yml` (captura horaria),
  `reloj.yml` (relevos de 30 min), `mensajes.yml`, `profunda.yml`, `diagnostico.yml`, `preparar.yml`, `respaldo.yml`,
  `traspaso.yml`, `limpiar_fuera_objetivo.yml`, `inventario.yml`.
- `.claude/skills/`: `nueva-familia`, `ampliar-mapa`, `diagnostico`, `nueva-fuente` (leen archivos cortos),
  `auditor-ux` (no implementa sin aprobación), `auditoria-codigo`, `thermos`.

## Dónde leer más
Leer antes de trabajar: `docs/GUIA_CLIENTE.md`, `docs/OPERACION_Y_RECUPERACION.md` y `docs/ACEPTACION_Y_ESTADO.md`.
- Uso y panel: `docs/GUIA_CLIENTE.md`, `docs/PANEL_CONTROL.md`.
- Operación e incidentes: `docs/OPERACION_Y_RECUPERACION.md`; riesgos: `docs/REVISION_FIABILIDAD.md`.
- Estado comprobado y pendientes: `docs/ACEPTACION_Y_ESTADO.md`; cambios: `docs/HISTORIAL_CAMBIOS.md`.
- Reservas y pendientes centrales: `docs/CONTRATO_ESTADO_OPERATIVO.md`, `docs/ACTIVAR_ESTADO_OPERATIVO.md`.
- Instalación: `docs/INSTALACION_AUTOMATICA.md` (camino preferido), `docs/INSTALACION.md`.
- Entrega, traspaso y cesión: `docs/ENTREGA_AL_CLIENTE.md`, `docs/TRASPASO.md`, `docs/CEDER_EL_PROYECTO.md`.
- Enlaces: `docs/CONTROL_CALIDAD_ENLACES.md`; cobertura histórica: `docs/COBERTURA_HISTORICO.md`;
  alternativas de producto: `docs/REVISION_PRODUCTO.md`.
- Activaciones: `docs/ACTIVAR_RELOJ.md`, `docs/ACTIVAR_CAPTURA_HORARIA.md`, `docs/ACTIVAR_INFOJOBS_API.md`.
