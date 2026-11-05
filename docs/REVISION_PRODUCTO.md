# Revisión de producto y preparación operativa

Revisión del 5 de noviembre de 2026. Fuentes públicas oficiales; observaciones de funciones visibles, no una auditoría
de los algoritmos internos de otros productos. La cobertura y los precios comerciales pueden cambiar.

## Productos comparables

| Producto | Qué se observó | Qué conviene adoptar aquí |
|---|---|---|
| [HiringCafe](https://hiring.cafe/) | Búsqueda por ubicación y modalidad, antigüedad relativa, enlace a la oferta, guardar/aplicado/ocultar. | Antigüedad precisa y elegibilidad geográfica explícita; separar descubrir una oferta de postularse. |
| [JobSpy](https://github.com/speedyapply/JobSpy) | Adaptadores para múltiples portales y formato común; documentación de limitaciones y bloqueos. | Varias fuentes con controles independientes y diagnóstico de cobertura. Ya usamos JobSpy para Indeed. Ninguna sesión personal de LinkedIn. |
| [Huntr](https://huntr.co/product/job-tracker) | Ofertas guardadas y etapas de candidatura organizadas por persona. | La candidatura futura debe referenciar una vacante conservada; cerrar una oferta no debe borrar la historia de un cliente. |
| [Teal](https://www.tealhq.com/tools/job-tracker) | Guardar ofertas, organizar candidaturas y seguir etapas. | Distinguir «seleccionada para compartir», «enviada», «guardada por cliente» y «postulada». |
| [Simplify](https://simplify.jobs/) | Descubrimiento, correspondencia de perfil, seguimiento y funciones de automatización. | Personalizar por país, cargo y modalidad cuando exista perfil/consentimiento. No añadir IA diaria ni postulaciones automáticas en esta etapa. |

Ninguno de estos productos demuestra por sí solo que podamos garantizar 120 ofertas nuevas elegibles todos los días
con USD 5 al mes. Los límites reales dependen de la oferta publicada, de los portales y de las cuentas del operador.

## Reglas técnicas contrastadas

- [Greenhouse](https://developers.greenhouse.io/job-board.html): `updated_at` indica modificación; el detalle puede
  proporcionar `first_published`. Se corrigió su uso como fecha de publicación. Cuando no existe fecha, se informa.
- [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api): publica campos como `publishedAt`, ubicación e
  `isListed`. [Lever](https://github.com/lever/postings-api) documenta ubicaciones/modalidad y límites de peticiones.
  Favorecer APIs públicas de empresas evita depender exclusivamente de un portal.
- [JobPosting de Schema.org](https://schema.org/JobPosting): distingue `datePosted`, `validThrough` y
  `applicantLocationRequirements`. «Remote» por sí solo no significa «se puede aplicar desde todo el mundo».
- [Programación de GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule):
  los horarios pueden retrasarse e incluso perder ejecuciones con carga alta. Se evita el minuto cero; una captura
  horaria es un objetivo operativo, no una promesa de disponibilidad en menos de 60 minutos.

## Cambios preparados a partir de esta revisión

1. Captura incremental horaria de LinkedIn público, Indeed y portales empresariales. No llama a Apify ni crea otra
   entrega diaria. La corrida nocturna mantiene las fuentes amplias y el presupuesto mensual existente de Apify.
2. Separación de publicación, primera detección y última observación efectiva. Filtro de 2/6/24 horas solo para
   publicación con hora confirmada; los datos sin precisión no se presentan como recientes por suposición.
3. Catálogo persistente y registro inmutable de selección en Supabase. Colas de reintento, conservación de primera
   detección y rechazo de actualizaciones antiguas. Cierre y archivo son estados distintos; no hay borrado automático.
4. Repetir el día recupera y completa el lote; no vuelve a seleccionar otras 20 para un rol ya completo. La memoria puede
   recuperarse desde Supabase al activar v2. No significa que se haya enviado WhatsApp.
5. Correcciones de elegibilidad: Sudamérica no incluye México ni España; «Global» en el título no prueba alcance
   mundial; se revisan restricciones en descripciones largas. Un dominio parecido a LinkedIn no se identifica como él.
6. Respuestas malformadas de un ATS no prueban que su tablero esté vacío y no deben cerrar sus ofertas.
7. Refresco de la página cuando cambia la captura, indicadores de frescura y comprobación explícita antes del piloto.
8. Flujo explícito de GitHub Pages, con activación independiente: los commits del token de Actions no reconstruyen el
   Pages desde rama. Se verificó que el sitio actual usa ese modo. [Documentación oficial](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

Contrato: [CONTRATO_DATOS_v2.md](CONTRATO_DATOS_v2.md). Migración y puesta en marcha:
[ACTIVAR_CAPTURA_HORARIA.md](ACTIVAR_CAPTURA_HORARIA.md).

## Evidencia y límites de la prueba en vivo

Captura incremental temporal, desde una bodega vacía, sin Apify ni escritura a Supabase: 4,7 minutos; 25.769 registros
crudos; 1.621 conservados tras filtros de familia/antigüedad/geografía. De estos, 1.178 cumplían el contrato de entrega;
439 no tenían descripción suficiente y 4 tenían idioma fuera del contrato. No se consideran todos entregables.
1.480 tenían hora de publicación y 57 habían sido publicados en las últimas 24 horas con esa precisión confirmada.
Las 24 consultas de LinkedIn y 6 de Indeed terminaron sin error; hubo un tablero empresarial fallido.

| Rol | Selección en esta captura corta |
|---|---:|
| Product Designer | 14 |
| UX/UI Designer | 8 |
| Product Owner | 20 |
| Product Manager | 20 |
| AI Engineer | 20 |
| QA | 20 |

Estas cifras son por rol, con memoria vacía. No equivalen a vacantes nuevas sostenibles cada día, ni a una corrida
nocturna completa con refuerzos. Tampoco sustituyen la comprobación del enlace y las restricciones por persona.
La selección evita entregar la misma vacante en dos roles; esto influye en la distribución de los dos roles de diseño.
Los alias y cargos afines ya existen; inventar afinidades o duplicar ofertas para llenar cupos empeoraría el servicio.

La migración se aplicó dos veces en PostgreSQL 17 temporal y se probaron restricciones, permisos, conservación y
reintentos. Esto no implica que esté aplicada al proyecto real de Supabase.

## Próximas oportunidades y criterio de salida

**Primero, operación real:** activar v2 y observar siete fechas consecutivas. Revisar déficit por rol, errores por
fuente, duplicados entre portales, antigüedad real, ubicación, saldo Apify y capacidad de Supabase. Seleccionar una
muestra diaria de enlaces de los seis roles para revisión humana. Ningún scraper certifica la autenticidad de una
empresa ni el estado instantáneo de todas las ofertas.

**Si diseño sigue corto:** ampliar la lista de empleadores con contrataciones de diseño en LATAM/España, revisar el
diagnóstico de alias/cobertura y completar las descripciones originales faltantes. Medir resultados únicos por
consulta antes de aumentar peticiones o contratar otro actor. La bodega debe crecer por fuentes útiles, no por ruido.

**Después, WhatsApp:** definir país de residencia, idiomas, seniority y roles de cada cliente; consentimiento,
destinatarios y frecuencia; registro de envíos confirmado, idempotencia por destinatario y bajas. La selección diaria
no sirve como comprobante de envío. Los cambios de etapa de una candidatura requerirán confirmación del cliente o una
integración autorizada: el portal de empleos no suele exponer el estado personal del aspirante.

La herramienta `python -m buscador.preparacion --salida <directorio>` devuelve si hay evidencia básica para un piloto:
captura y ofertas observadas en dos horas, catálogo sin pendientes y siete días con meta/registro confirmado. Ese
resultado no certifica perfección ni sustituye la revisión de calidad y el diseño del canal de mensajes.

**Capacidad:** el repositorio consultado es público. Revisar las condiciones actuales de Actions; si pasa a privado,
24 ejecuciones diarias de 4,7 minutos sumarían unas 3.384 min/mes antes de instalación y captura nocturna. Reducir la
frecuencia o asignar capacidad antes de asumir que cabe en una cuota gratuita. En Supabase medir tamaño de tablas e
índices y respaldar; archivar significa conservar filas, no liberar almacenamiento automáticamente.

El P90 publicación→detección de `salud.json` incluye la carga inicial de vacantes antiguas y solo fuentes con hora
conocida. No debe anunciarse como latencia de operación estable ni medirlo solo a partir de los datos favorables.
