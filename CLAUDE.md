# CLAUDE.md — Buscador de vacantes LATAM

## Qué es
Un scraper de vacantes para LATAM y el mundo hispanohablante (España) que cada noche:
1. llena una bodega con todas las vacantes abiertas de 30 días (LinkedIn público, Indeed, portales de empresas, Get on
   Board, tableros remotos y publicaciones «contratando» de LinkedIn vía Apify);
2. arma la **entrega diaria**: 20 vacantes nuevas (nunca entregadas) por rol —Product designer, UX/UI designer, Product
   Owner, Product manager, AI Engineer, QA—, variadas, con las columnas del **contrato de datos v1**
   (`docs/CONTRATO_DATOS_v1.md`), y la guarda en **Supabase** (obligatorio; Excel automático desactivado);
3. publica una página donde se busca cualquier cargo y país y se copia a WhatsApp o Excel.
Es un proyecto vendido por Oscar: se entrega a otra persona cambiando solo los secretos (`docs/TRASPASO.md`). Más adelante
un bot de WhatsApp tomará 5 vacantes de Supabase y las enviará.
El plan completo, con el paso a paso, está en `docs/PLAN.md`: léelo antes de trabajar.

## Decisiones vigentes de cobertura e integridad

Leer también `docs/COBERTURA_HISTORICO.md`: LATAM y España más remotas mundiales, prioridad remota,
rotación de cargos exactos/similares/cercanos, identidad por enlace y evidencia de contenido, cola de reintentos
a Supabase y conservación sin borrado automático de ofertas de la base. No construir seguimiento de postulaciones
en esta etapa. El horario de Bogotá solo programa la ejecución; no limita los países.
Apify usa curious_coder/linkedin-jobs-scraper con permisos limitados para fichas formales, sin cookies y con tope USD 5/mes. El feed pagado queda
desactivado por defecto. Un post solo aporta una oferta si se recupera su ficha formal; sin ella sigue por verificar.
La entrega normal comprueba Supabase antes de recoger; la validación final falla si hay déficit o sincronización pendiente.

## Reglas que no se cambian sin preguntarle a Oscar
- **Volumen antes que filtros.** Solo filtran: el cargo (mapa de cargos), 30 días de antigüedad, que siga abierta, que no
  esté repetida y que se pueda aplicar desde el país elegido. Inglés, nivel y años se muestran como columnas.
- **Contrato de datos v1 manda** en la entrega: mismos nombres y valores; lo que el aviso no dice queda vacío (nunca se
  inventa: ni la moneda de un "$" solo, ni la modalidad que el aviso no dice). Un campo nuevo se agrega primero al
  contrato (versión nueva) y después al código. Solo ofertas en español o inglés.
- **Entrega diaria:** `por_rol` nuevas por rol, nunca repetidas (`trabajo/entregadas.json`), variadas (idioma, nivel,
  país, modalidad, fuente, máximo 2 por empresa). Países: LATAM y España (decisión de Oscar, 5 nov 2026).
- **Solo enlaces donde se postula de verdad:** el sistema de postulación de la empresa (Greenhouse, Lever, Ashby…), su
  página de empleo o un portal donde se postula ahí mismo (LinkedIn, Indeed, Computrabajo…). Nunca agregadores ni sitios
  de pago (Jooble, BeBee, trabajo.org, JobLeads, Talent.com…): se rastrea el original o la vacante no se guarda.
- **Enlace principal = LinkedIn** cuando la vacante está ahí; el directo de la empresa va en `enlace_directo`.
- **LinkedIn nunca con la sesión ni la cookie de nadie** (`li_at` incluida). Ni actores de Apify que la pidan.
- **Nada se envía solo:** la página arma el texto y Oscar lo pega en WhatsApp.
- **La búsqueda no usa IA.** Todo es código con pruebas. La IA solo construye y amplía el mapa de cargos leyendo
  archivos cortos (`reportes/`), nunca la bodega completa.
- **Traspasable:** nada depende de las cuentas personales de Oscar. Ninguna clave, ID, correo ni dato de clientes en el
  repositorio (las claves van en los secretos de GitHub y Cloudflare). `pruebas/test_repositorio.py` lo revisa.
- **No se toca ni se depende del repositorio `ux_job_agent`** (el agente personal de Oscar): si se necesita código de
  allá, se lee y se copia aquí. Este repositorio es independiente.
- Si algo del plan no está claro o falta una decisión, se pregunta antes de inventar una regla.

## Cómo se trabaja
- Un paso del plan por sesión, en una rama, con un PR que Oscar revisa y fusiona.
- Pruebas obligatorias antes de cada push: `python -m pytest -q` y `node --test pruebas/*.test.js`.
- Prueba en vivo corta (unos 5 minutos, con internet): `python -m buscador.bodega --salida /tmp/prueba --prueba`.
- Lo que cambia sin tocar código vive en `datos/` (mapa de cargos, países, dominios, empresas, `config.yaml`).
- Respuestas a Oscar en español y en lenguaje sencillo.

## Estructura
- `docs/` plan, instalación y traspaso · `datos/` archivos editables · `buscador/` Python (fuentes, normalizar,
  familias, paises, enlaces, etiquetas, bodega, publicar, diagnostico) · `web/` la página · `functions/api/` funciones de
  Cloudflare · `pruebas/` · `reportes/` (los escribe la bodega) · `.claude/skills/` · `.github/workflows/`.

## Cómo funciona (versión 1)
- **Bodega nocturna** (`.github/workflows/bodega.yml`, 1:17 Bogotá): `buscador/bodega.py` corre en paralelo las fuentes
  de `buscador/fuentes/` —LinkedIn público (rotación familia × país, consultas con OR), Indeed (JobSpy, 11 países),
  portales de empresas (`ats.py`: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee; la lista crece sola
  probando las empresas que traen las demás fuentes), tableros remotos (Remotive y Working Nomads con el enlace
  original), Get on Board, y Apify/Brave si existen `APIFY_TOKEN`/`BRAVE_API_KEY`—; `vacante.py` arma cada vacante
  (familias, países, etiquetas) y junta copias; `limpiar` quita viejas, cerradas y las que no sirven desde LATAM;
  `publicar.py` arma la rama `publicado` (página + `datos/vacantes.json.gz` + `salud.json` + `trabajo/` para la noche
  siguiente). Presupuestos de cada fuente en `datos/config.yaml`. Las familias de los roles de la entrega se buscan
  primero, todas las noches (LinkedIn e Indeed), y sus avisos reciben primero la descripción completa.
- **Entrega diaria** (`entrega.py`, `contrato.py`, `supabase.py`; configuración en `datos/entrega.yaml`): al final de la
  bodega elige las vacantes, sube las filas a la
  tabla `ofertas` de Supabase (`supabase/esquema.sql`; secretos `SUPABASE_URL`, `SUPABASE_SECRET_KEY`; nunca
  sobrescribe: external_id repetido se ignora). En `--prueba` no marca entregadas ni sube.
- **Publicaciones «contratando»** (`fuentes/publicaciones_apify.py`): actor `harvestapi/linkedin-post-search` (sin
  cookie, ≈ USD 2 por 1.000; tope `apify.publicaciones_por_dia` = 72 ≈ USD 4,3 al mes, plan gratis de Apify). Solo
  se propone para revisión una publicación que anuncia contratación, nombra un cargo del mapa, un país activo o remoto, y cuya empresa se
  sabe (autor empresa o "at <Empresa>" en el cargo del autor). No entra automáticamente en la entrega.
- **Página** (`web/`): `motor.js` (lógica pura, con pruebas) y `app.js` (pantalla). Se sirve desde la rama `publicado`
  con GitHub Pages (básico) o Cloudflare Pages (privada, con `functions/api/enviadas.js` y `profunda.js`).
- **Búsqueda profunda** (`profunda.yml`): un cargo a pedido, en vivo. **Diagnóstico** (`diagnostico.yml`).
- Skills del proyecto: `nueva-familia`, `ampliar-mapa`, `diagnostico`, `nueva-fuente` (leen archivos cortos, no la bodega).
- Instalación y traspaso: `docs/INSTALACION.md`, `docs/TRASPASO.md`.

## Estado
- Versión 1 construida el 28 oct 2026 (pasos 1 a 11 del plan); corre cada noche desde el 29 oct.
- 5 nov 2026: entrega diaria con el contrato de datos v1, Supabase, publicaciones de Apify y España. Falta que Oscar cree
  Supabase y Apify y ponga los secretos (`docs/INSTALACION.md`), y medir cuántas nuevas por rol llegan cada día (antes
  de priorizar los roles, diseño traía 1 a 13 nuevas por día).
- Hallazgos de las pruebas en vivo: LinkedIn acepta consultas con OR; su página pública no muestra el enlace externo de
  postulación (sale de juntar con el portal de la empresa); Indeed bloquea la web (403) pero JobSpy funciona; Himalayas,
  We Work Remotely, RemoteOK y Jobicy no dejan ver el original (aportan nombres de empresas); Workable responde 429 si se
  le pregunta mucho (no se insiste en la misma corrida).
