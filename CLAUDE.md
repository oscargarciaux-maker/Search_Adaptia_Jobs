# CLAUDE.md — Buscador de vacantes LATAM

## Qué es
Un buscador de vacantes para LATAM, España y remotas mundiales que:
1. llena una bodega con todas las vacantes abiertas de 30 días (LinkedIn público, Indeed, portales de empresas, Get on
   Board, tableros remotos y ofertas formales LinkedIn vía Apify);
2. arma la **entrega diaria**: 20 vacantes nuevas (nunca entregadas) por rol —Product designer, UX/UI designer, Product
   Owner, Product manager, AI Engineer, QA—, variadas, con las columnas del **contrato de datos v1**
   (`docs/CONTRATO_DATOS_v1.md`), y la guarda en **Supabase** (obligatorio);
3. permite consultar selección y disponibilidad mediante vistas privadas en Supabase.
La interfaz web, GitHub Pages y funciones Cloudflare se retiraron por decisión del usuario. No reintroducirlos.
Por decisión vigente del usuario, Excel no se usa: no reintroducir botón, exportador ni dependencia de hojas de cálculo.
Los CSV de configuración de empresas y reportes técnicos no son una base de datos alternativa.
La captura horaria gratuita actualiza catálogo y verificación sin crear otra entrega ni usar Apify. Los nuevos enlaces
para entregar se comprueban con presupuesto y caducidad; los pendientes no se dan por válidos.
Es un proyecto vendido por Oscar: se entrega a otra persona cambiando solo los secretos (`docs/TRASPASO.md`). Más adelante
un bot de WhatsApp tomará 5 vacantes de Supabase y las enviará.
Leer antes de trabajar `docs/GUIA_CLIENTE.md`, `docs/OPERACION_Y_RECUPERACION.md` y `docs/ACEPTACION_Y_ESTADO.md`.
Riesgos y prioridades de mantenimiento: `docs/REVISION_FIABILIDAD.md`.
Para reservas y pendientes centrales, leer `docs/CONTRATO_ESTADO_OPERATIVO.md` y `docs/ACTIVAR_ESTADO_OPERATIVO.md`.
Camino preferido de instalación: `docs/INSTALACION_AUTOMATICA.md`. `SUPABASE_DB_URL` y `SUPABASE_BACKUP_KEY` se configuran
una vez como Secrets. Preparar Supabase sube respaldo cifrado antes de SQL, registra hashes en `adaptia_migraciones`
y activa por marca privada; no pedir copiar 002/003 ni variables manuales para este camino. No modificar SQL ya registrado:
añadir migración. Clave administrativa limitada a preparación; no se entrega a fuentes, navegador ni logs. Tras el
instalador los cortes contienen siete tablas y dos secuencias. Probar `python -m pruebas.probar_migraciones` solo en PG aislado.
SQL 003 + `ESTADO_SUPABASE_ACTIVO=true` activan el modo; no asumir que está desplegado. No volver al contador local
como alternativa silenciosa ni vaciar reservas/colas para resolver errores. El arranque importa un corte coherente.
`docs/PLAN.md` se conserva como diseño histórico: sus instrucciones antiguas no prevalecen sobre decisiones actuales.

## Decisiones vigentes de cobertura e integridad

Leer `docs/CONTRATO_DATOS_v5.md`: una fila por vacante en `ofertas`, archivo íntegro de enlaces duplicados,
IDs agrupados y selección sin contar copias. No borrar archivos históricos ni snapshots para ocultar déficit.
Leer también `docs/CONTRATO_DATOS_v4.md`: vistas privadas de disponibilidad, afinidad vigente y reporte por rol.
SQL 004 es aditivo y automático; no modificar SQL 001–005 ni el estado histórico v1. Conservar variantes pertinentes;
desarrollo genérico no cuenta como QA/IA.
Leer `docs/CONTRATO_DATOS_v3.md` y `docs/CONTROL_CALIDAD_ENLACES.md`: comprobar enlaces antes de nuevas entregas,
no confundir HTTP 200 con ficha vigente ni 403 con cierre. La verificación tiene caducidad y presupuesto, no usa Apify
ni envía formularios. Los snapshots históricos no se reescriben; un futuro bot debe consultar el catálogo y sus enlaces
con comprobación vigente, no deducir disponibilidad del `status=active` inmutable de `ofertas` v1.

Leer `docs/REVISION_PRODUCTO.md`, `docs/CONTRATO_DATOS_v2.md` y `docs/ACTIVAR_CAPTURA_HORARIA.md`.
El catálogo v2 es aditivo; no cambiar las columnas de `ofertas` v1. La captura horaria gratuita no consume Apify ni
crea entregas. Repetir el día solo completa/reintenta el mismo lote. No confundir publicación con actualización o
detección, ni selección con envío WhatsApp. La activación requiere migración y variable; no afirmar que esté activa
solo porque el código existe. Las notas de instalación pendiente del estado histórico no prueban el estado actual.

Leer también `docs/COBERTURA_HISTORICO.md`: LATAM y España más remotas mundiales, prioridad remota,
rotación de cargos exactos/similares/cercanos, identidad por enlace y evidencia de contenido, cola de reintentos
a Supabase y conservación sin borrado automático de ofertas de la base. No construir seguimiento de postulaciones
en esta etapa. El horario de Bogotá solo programa la ejecución; no limita los países.
Apify usa curious_coder/linkedin-jobs-scraper con permisos limitados para fichas formales, sin cookies y con tope USD 5/mes. El feed pagado queda
desactivado por defecto. Un post solo aporta una oferta si se recupera su ficha formal; sin ella sigue por verificar.
La entrega normal comprueba Supabase antes de recoger; la validación final falla si hay déficit o sincronización pendiente.

## Reglas que no se cambian sin preguntarle a Oscar
- **Volumen antes que filtros.** Solo filtran: el cargo (mapa de cargos), 30 días de antigüedad, que siga abierta, que no
  esté repetida, que tenga un enlace comprobado para nuevas entregas y que se pueda aplicar desde el país elegido.
  Inglés, nivel y años se muestran como columnas.
- **Contrato v1 + ampliación v5** en la entrega: nombres y valores compatibles, una fila por vacante reconocida; lo que el aviso no dice queda vacío (nunca se
  inventa: ni la moneda de un "$" solo, ni la modalidad que el aviso no dice). Un campo nuevo se agrega primero al
  contrato (versión nueva) y después al código. Solo ofertas en español o inglés.
- **Entrega diaria:** `por_rol` nuevas por rol, nunca repetidas (`trabajo/entregadas.json`), variadas (idioma, nivel,
  país, modalidad, fuente, máximo 2 por empresa). Países: LATAM y España (decisión de Oscar, 5 nov 2026).
- **Solo enlaces donde se postula de verdad:** el sistema de postulación de la empresa (Greenhouse, Lever, Ashby…), su
  página de empleo o un portal donde se postula ahí mismo (LinkedIn, Indeed, Computrabajo…). Nunca agregadores ni sitios
  de pago (Jooble, BeBee, trabajo.org, JobLeads, Talent.com…): se rastrea el original o la vacante no se guarda.
- **Enlace principal = LinkedIn** cuando la vacante está ahí; el directo de la empresa va en `enlace_directo`.
- **LinkedIn nunca con la sesión ni la cookie de nadie** (`li_at` incluida). Ni actores de Apify que la pidan.
- **Nada se envía solo:** el agente de WhatsApp no está implementado en esta etapa.
- **La búsqueda no usa IA.** Todo es código con pruebas. La IA solo construye y amplía el mapa de cargos leyendo
  archivos cortos (`reportes/`), nunca la bodega completa.
- **Traspasable:** nada depende de las cuentas personales de Oscar. Ninguna clave, ID, correo ni dato de clientes en el
  repositorio (las claves van en los secretos de GitHub). `pruebas/test_repositorio.py` lo revisa.
- **No se toca ni se depende del repositorio `ux_job_agent`** (el agente personal de Oscar): si se necesita código de
  allá, se lee y se copia aquí. Este repositorio es independiente.
- Si algo del plan no está claro o falta una decisión, se pregunta antes de inventar una regla.

## Cómo se trabaja
- Un paso del plan por sesión, en una rama, con un PR que Oscar revisa y fusiona.
- Pruebas obligatorias antes de cada push: `python -m pytest -q`; CI también comprueba PostgreSQL. No se requiere Node tras retirar la interfaz.
- Prueba en vivo corta (unos 5 minutos, con internet): `python -m buscador.bodega --salida /tmp/prueba --prueba`.
- Lo que cambia sin tocar código vive en `datos/` (mapa de cargos, países, dominios, empresas, `config.yaml`).
- Respuestas a Oscar en español y en lenguaje sencillo.

## Estructura
- `docs/` plan, instalación y traspaso · `datos/` archivos editables · `buscador/` Python (fuentes, normalizar,
  familias, paises, enlaces, etiquetas, bodega, publicar, diagnostico) · `pruebas/` · `reportes/` (los escribe la bodega) · `.claude/skills/` · `.github/workflows/`.

## Cómo funciona (estado vigente)
- **Bodega nocturna** (`.github/workflows/bodega.yml`, 1:17 Bogotá): `buscador/bodega.py` corre en paralelo las fuentes
  de `buscador/fuentes/` —LinkedIn público (rotación familia × país, consultas con OR), Indeed (JobSpy, 11 países),
  portales de empresas (`ats.py`: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee; la lista crece sola
  probando las empresas que traen las demás fuentes), tableros remotos (Remotive y Working Nomads con el enlace
  original), Get on Board, y Apify/Brave si existen `APIFY_TOKEN`/`BRAVE_API_KEY`—; `vacante.py` arma cada vacante
  (familias, países, etiquetas) y junta copias; `limpiar` quita viejas, cerradas y las que no sirven desde LATAM;
  `publicar.py` conserva `datos/salud.json` y `trabajo/` en la rama histórica `publicado` para la siguiente captura;
  retira los archivos antiguos de la interfaz sin borrar inventario, colas ni reservas. Presupuestos de cada fuente en `datos/config.yaml`. Las familias de los roles de la entrega se buscan
  primero, todas las noches (LinkedIn e Indeed), y sus avisos reciben primero la descripción completa.
- **Entrega diaria** (`entrega.py`, `contrato.py`, `supabase.py`; configuración en `datos/entrega.yaml`): al final de la
  bodega elige las vacantes, sube las filas a la
  tabla `ofertas` de Supabase (`supabase/esquema.sql`; secretos `SUPABASE_URL`, `SUPABASE_SECRET_KEY`; nunca
  sobrescribe: external_id repetido se ignora). En `--prueba` no marca entregadas ni sube.
- **Apify formal**: `curious_coder/linkedin-jobs-scraper`, build `1.7.18`, USD 5/mes de reservas durables compartidas
  entre nocturna/búsquedas profundas. El feed `harvestapi/linkedin-post-search` sigue implementado pero desactivado
  (`publicaciones_por_dia=0`); solo una ficha formal recuperada puede aportar una oferta, no un post por sí mismo.
- **Catálogo/horario**: SQL 002 aditivo, `catalogo_vacantes` y `entregas_diarias`; `CAPTURA_HORARIA_ACTIVA=true` activa
  el horario y el catálogo v2 nocturno. `ofertas` permanece v1; verificación pública v3 se almacena en JSON, sin SQL nuevo.
- **Enlaces**: `verificar_enlaces.py`, presupuestos en `datos/config.yaml`, caché en `trabajo/`; no confundir datos
  antiguos con comprobación vigente. El control del lote actual no reescribe sus snapshots históricos.
- **Estado operativo optativo**: SQL 003, `estado_operativo.py`, variable `ESTADO_SUPABASE_ACTIVO`; reservas/colas/lote
  sin confirmar centrales, recuperación por snapshot, revisión contra confirmaciones atrasadas. Tras 003, respaldar
  cinco tablas y dos secuencias. GitHub conserva inventario, rotaciones, verificación y métricas auxiliares.
- **Instalación automática**: `migraciones.py`, `preparar.py`, `respaldo.py` y acción compartida: claves iniciales,
  plan/corte cifrado confirmado, migraciones transaccionales, versiones y activación sin variables. El horario consulta
  la marca incluso si no existe la variable antigua. Respaldo previo a cambios no equivale a backups periódicos.
- **Búsqueda profunda** (`profunda.yml`): un cargo a pedido, en vivo. **Diagnóstico** (`diagnostico.yml`).
- Skills del proyecto: `nueva-familia`, `ampliar-mapa`, `diagnostico`, `nueva-fuente` (leen archivos cortos, no la bodega).
- Instalación y traspaso: `docs/INSTALACION.md`, `docs/TRASPASO.md`.

## Estado
- Versión 1 construida el 28 oct 2026 (pasos 1 a 11 del plan); corre cada noche desde el 29 oct.
- 5 nov 2026: PR 6–11 fusionados; catálogo/horario/Supabase/Pages observados y control de enlaces probado/fusionado.
  La evidencia fechada y los pendientes están en `docs/ACEPTACION_Y_ESTADO.md`; no afirmar siete días ni activación
  productiva de un cambio hasta comprobar sus ejecuciones. El traspaso exige las tablas, memoria/colas y reservas,
  no solo reemplazar secretos o importar `ofertas`. Manuales y cambios: `docs/GUIA_CLIENTE.md` y `docs/HISTORIAL_CAMBIOS.md`.
- Hallazgos de las pruebas en vivo: LinkedIn acepta consultas con OR; su página pública no muestra el enlace externo de
  postulación (sale de juntar con el portal de la empresa); Indeed bloquea la web (403) pero JobSpy funciona; Himalayas,
  We Work Remotely, RemoteOK y Jobicy no dejan ver el original (aportan nombres de empresas); Workable responde 429 si se
  le pregunta mucho (no se insiste en la misma corrida).
