# CLAUDE.md — Buscador de vacantes LATAM

## Qué es y decisión vigente
Desde la petición del 6 de noviembre, existe un panel de control privado para el operador: clientes con perfiles,
cargos abiertos y cupos por cargo que suman 120, filtros por país/modalidad/idioma/publicación/experiencia/inglés,
y copia manual de WhatsApp. La retirada de la web histórica no prohíbe esta nueva plataforma expresamente solicitada.
No reintroducir Pages/Cloudflare antiguos, Excel, envío automático de WhatsApp ni seguimiento de candidaturas.
Leer primero docs/PANEL_CONTROL.md y docs/CONTRATO_DATOS_v6.md. Estos prevalecen sobre restricciones históricas
que prohibían filtrar experiencia/inglés o fijaban seis cargos. El acceso real queda cerrado hasta configurar login,
por decisión del propietario; --demo usa datos ficticios y no toca Supabase. No abrir datos reales sin autorización.

La captura heredada mantiene seis cargos por veinte hasta existir una versión privada vigente; panel.ejecutor carga
la versión activa desde Supabase, sustituye cargos/lugares/cupos y asigna resultados compatibles por perfil.
Búsqueda y afinidad sin IA; variantes/ESCO/términos editables para cargos nuevos. No inventar equivalentes ni un score
personal de contratación. No persistir datos de clientes en reportes/cachés públicos de la captura.
La configuración y asignaciones viven en Supabase; SQL 009 añade cuatro tablas privadas. UI React/Vite, API FastAPI,
servidor con credencial de servicio; nunca compartirla al navegador. Docker y guía de despliegue sin proveedor obligatorio.
Los cambios del borrador son explícitos; programar fija una versión desde mañana en Bogotá y conserva la de corridas iniciadas.

Leer antes de trabajar `docs/GUIA_CLIENTE.md`, `docs/OPERACION_Y_RECUPERACION.md` y `docs/ACEPTACION_Y_ESTADO.md`.
Riesgos y prioridades de mantenimiento: `docs/REVISION_FIABILIDAD.md`.
Para reservas y pendientes centrales, leer `docs/CONTRATO_ESTADO_OPERATIVO.md` y `docs/ACTIVAR_ESTADO_OPERATIVO.md`.
Entrega al cliente y traspaso a su Supabase: `docs/ENTREGA_AL_CLIENTE.md` y flujo `traspaso.yml` (destino vacío y propio; el origen trasladado detiene las capturas). Camino preferido de instalación: `docs/INSTALACION_AUTOMATICA.md`. `SUPABASE_DB_URL` y `SUPABASE_BACKUP_KEY` se configuran
una vez como Secrets. Preparar Supabase sube respaldo cifrado antes de SQL, registra hashes en `adaptia_migraciones`
y activa por marca privada; no pedir copiar 002/003 ni variables manuales para este camino. No modificar SQL ya registrado:
añadir migración. Clave administrativa limitada a preparación; no se entrega a fuentes, navegador ni logs. Tras el
instalador los cortes contienen dieciséis tablas (SQL 014 añade `panel_revisiones` y `panel_reglas_ubicacion`) y dos secuencias. Probar `python -m pruebas.probar_migraciones` solo en PG aislado.
SQL 003 + `ESTADO_SUPABASE_ACTIVO=true` activan el modo; no asumir que está desplegado. No volver al contador local
como alternativa silenciosa ni vaciar reservas/colas para resolver errores. El arranque importa un corte coherente.
`docs/PLAN.md` se conserva como diseño histórico: sus instrucciones antiguas no prevalecen sobre decisiones actuales.

## Decisiones vigentes de cobertura e integridad

Leer `docs/CONTRATO_DATOS_v17.md` (aprendizaje de ubicaciones solo con código: reglas del operador y aprendidas que solo resuelven lo «por confirmar» y nunca pisan la tabla; aprendizaje nocturno determinista con mínimo de evidencias, conflictos que desactivan y sin reactivación automática; CSV de revisión masiva; **no requiere IA**), `docs/CONTRATO_DATOS_v16.md` (confirmación automática de ubicación leyendo el JobPosting de la ficha; bandeja «Por confirmar» en el panel: SQL 014 `panel_revisiones`/`panel_reglas_ubicacion`, cola diaria de hasta 10 priorizando perfiles bajo 5, decisiones de un clic, reglas por ubicación exacta y nunca con ubicaciones genéricas), `docs/CONTRATO_DATOS_v15.md` (idioma: solo `es`/`en` con evidencia positiva frente a perfiles de 14 idiomas; tabla ISO completa `datos/paises_mundo.yaml` con siglas, nombres y subdivisiones; ambigüedad calculada por código y lista editable; AR/CO/PA tras palabra por confirmar), `docs/CONTRATO_DATOS_v14.md` (códigos sueltos de 2/3 letras, ubicaciones repetidas, ciudad dentro del texto si apunta a un único país y nunca por nombres ambiguos, «trabajar en el país» = país del aviso; el flujo de limpieza avisa si no se marcó «aplicar»), `docs/CONTRATO_DATOS_v13.md` (ubicaciones extranjeras reconocidas en español, por código ISO final o estado de EE. UU.; idiomas fr/de/it detectados; revisión de `ofertas` con `limpiar_fuera_objetivo.yml`: listado, huella, conservar/borrar_tambien, copia cifrada y BORRAR), `docs/CONTRATO_DATOS_v12.md` (solo español e inglés con detector de idioma por palabras propias; Brasil se reconoce pero no se cubre: solo cuenta dentro de remotas de varios países), `docs/CONTRATO_DATOS_v11.md` (rescate por persona hasta 5: experiencia ±2, hasta 4 por empresa, reutilizar entre personas sin repetir a la misma, Apify dirigido solo a perfiles con déficit; posts de LinkedIn etiquetados «Post» como último recurso), `docs/CONTRATO_DATOS_v10.md` (ajustes `panel_ajustes` SQL 012 y alertas por correo con Resend; contactos y borradores de WhatsApp SQL 013), `docs/CONTRATO_DATOS_v9.md` (mínimo de 5 por perfil con ampliación marcada; comprobación 24 h para seleccionar y 6 h para compartir), `docs/CONTRATO_DATOS_v8.md` (perfil por país de residencia y modalidades), `docs/CONTRATO_DATOS_v7.md` (inglés exigido precalculado para estimar), `docs/CONTRATO_DATOS_v6.md` y `docs/CONTRATO_DATOS_v5.md`: una fila por vacante en `ofertas`, archivo íntegro de enlaces duplicados,
IDs agrupados y selección sin contar copias. No borrar archivos históricos ni snapshots para ocultar déficit.
Leer también `docs/CONTRATO_DATOS_v4.md`: vistas privadas de disponibilidad, afinidad vigente y reporte por rol.
SQL 004 es aditivo y automático; no modificar SQL registrado ni el estado histórico v1. SQL 010 optimiza el grafo de aliases;
SQL 011 lo recorre solo desde ofertas y referencias explícitas con índices (010 leía todo el catálogo y agotaba 3 s);
comprobar instalación y captura posterior antes de afirmar recuperación. Conservar variantes pertinentes;
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
en esta etapa. El horario de Bogotá solo programa la ejecución; no limita los países. La admisión exige ubicación positiva:
locales/híbridas en cobertura, remotas con alcance pertinente; horario compatible o país desconocido no completan la meta.
Apify usa curious_coder/linkedin-jobs-scraper con permisos limitados para fichas formales, sin cookies y con tope USD 5/mes. El feed pagado queda
desactivado por defecto. Un post solo aporta una oferta (cupo/`ofertas`) si se recupera su ficha formal; sin ella, desde v11
solo llega etiquetado «Post» a perfiles con déficit, hasta completar 5, tras el filtro estricto contra basura.
La entrega normal comprueba Supabase antes de recoger; la validación final falla si hay déficit o sincronización pendiente.

## Reglas de integridad y modo heredado
- **Modo heredado sin versión de panel.** Solo filtran: el cargo (mapa de cargos), 30 días de antigüedad, que siga abierta, que no
  esté repetida, que tenga un enlace comprobado para nuevas entregas y que se pueda aplicar desde el país elegido.
  Inglés, nivel y años se muestran como columnas. Con panel activo, los filtros explícitos de cada perfil sí se aplican.
- **Contrato v1 + ampliaciones v5/v6** en la entrega: nombres y valores compatibles, una fila por vacante reconocida; lo que el aviso no dice queda vacío (nunca se
  inventa: ni la moneda de un "$" solo, ni la modalidad que el aviso no dice). Un campo nuevo se agrega primero al
  contrato (versión nueva) y después al código. Solo ofertas en español o inglés.
- **Entrega diaria:** cupos por cargo en el panel o `por_rol` en legado, nuevas por rol, nunca repetidas (`trabajo/entregadas.json`), variadas (idioma, nivel,
  país, modalidad, fuente, máximo 2 por empresa; hasta 4 solo como último recurso v11). Por persona, una vacante de días
  anteriores puede reasignarse a quien nunca la recibió (v11); nunca dos veces a la misma persona. Países: LATAM hispanohablante y España (decisión de Oscar, 5 nov 2026); desde el 12 nov, Brasil solo dentro de remotas abiertas a varios países (v12).
- **Solo enlaces donde se postula de verdad:** el sistema de postulación de la empresa (Greenhouse, Lever, Ashby…), su
  página de empleo o un portal donde se postula ahí mismo (LinkedIn, Indeed, Computrabajo…). Nunca agregadores ni sitios
  de pago (Jooble, BeBee, trabajo.org, JobLeads, Talent.com…): se rastrea el original o la vacante no se guarda.
- **Enlace principal = LinkedIn** cuando la vacante está ahí; el directo de la empresa va en `enlace_directo`.
- **LinkedIn nunca con la sesión ni la cookie de nadie** (`li_at` incluida). Ni actores de Apify que la pidan.
- **Nada se envía solo:** desde el 12 nov hay borradores diarios de WhatsApp por cliente (contrato v10) que el operador
  abre con un botón (wa.me) y envía a mano. No hay API de WhatsApp ni automatización que envíe mensajes.
- **La búsqueda no usa IA.** Todo es código con pruebas; el aprendizaje de ubicaciones también (v17). La IA solo construye y amplía el mapa de cargos leyendo
  archivos cortos (`reportes/`), nunca la bodega completa.
- **Traspasable:** nada depende de las cuentas personales de Oscar. Ninguna clave, ID, correo ni dato de clientes en el
  repositorio (las claves van en los secretos de GitHub). `pruebas/test_repositorio.py` lo revisa.
- **No se toca ni se depende del repositorio `ux_job_agent`** (el agente personal de Oscar): si se necesita código de
  allá, se lee y se copia aquí. Este repositorio es independiente.
- Si algo del plan no está claro o falta una decisión, se pregunta antes de inventar una regla.

## Cómo se trabaja
- Completar el alcance autorizado en una rama, con un PR que Oscar revisa y fusiona; no auto-fusionar.
- Pruebas obligatorias antes de cada push: `python -m pytest -q`; CI también comprueba PostgreSQL. La interfaz nueva requiere Node 24 para compilar; CI verifica formato, compilación y recorridos Playwright.
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
  original), Get on Board, Computrabajo (17 países, fecha de `datePosted`, nunca la de actualización), y Apify/Brave si existen `APIFY_TOKEN`/`BRAVE_API_KEY`—; `vacante.py` arma cada vacante
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
  (`publicaciones_por_dia=0`); solo una ficha formal recuperada puede aportar una oferta. Desde v11, `posts_rescate`
  busca posts para perfiles bajo 5 y los guarda en el catálogo con `tipo="post"` (fuera del cupo, de `ofertas` y de `trabajo/`).
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
- Skills del proyecto: `nueva-familia`, `ampliar-mapa`, `diagnostico`, `nueva-fuente` (leen archivos cortos, no la bodega),
  `auditor-ux` (auditoría UX/accesibilidad con capturas en modo demo; no implementa sin aprobación).
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
