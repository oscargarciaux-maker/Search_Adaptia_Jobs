# Apify para ofertas formales de LinkedIn

Oscar confirmó que desea aprovechar el crédito gratuito, con máximo USD 5 al mes. La integración anterior dejaba vacío
`actor_linkedin` y solo buscaba publicaciones del feed. Ahora usa `curious_coder/linkedin-jobs-scraper`, build `1.7.18`,
con permisos limitados. Harvest se descartó como predeterminado porque exige aprobar acceso completo a la cuenta.

Se comprobaron públicamente el esquema de entrada, el ejemplo de salida, la ausencia de cookies obligatorias y la tarifa
publicada para el plan gratuito: aproximadamente USD 0,002 por oferta más un pequeño cargo por inicio. La cuenta y condiciones de Apify prevalecen;
las reservas de este programa son límites conservadores, no facturas ni estimaciones de vacantes nuevas garantizadas.

## Qué busca y qué entrega

- Términos exactos, similares y cercanos con consultas OR, por turnos entre familias.
- LATAM, España y remotas mundiales, priorizando remoto; no filtra por seniority ni inglés.
- Entrada real del actor: `urls` con filtros LinkedIn, `limitPerSource`, `scrapeCompany: false` y
  `autoConvertToAiSearch: false`. No se activa búsqueda con IA ni enriquecimiento de empresas.
- No se envía `cookie`, `li_at`, usuario ni sesión personal. El actor elegido no exige compartir la cuenta personal. No se cambia de actor sin implementar y comprobar su adaptador.
- Se normalizan empresa, ubicación anidada, descripción, fecha y enlace de postulación. Los posts no se convierten en
  fichas inventadas. Se descartan avisos cerrados, incompletos o sin enlace formal antes de los filtros comunes.
- Las fichas obtenidas entran a clasificación, elegibilidad, antigüedad, deduplicación y entrega Supabase igual que las
  otras fuentes. No quedan todas pendientes de revisión por proceder de Apify.

## Cómo se limita el crédito

`datos/config.yaml`: máximo USD 5 por mes calendario, USD 3 por corrida, USD 0,025 por consulta y 10 resultados por consulta.
El mensual se reparte entre los días del mes: aproximadamente USD 0,16–0,18 diarios. El límite diario normalmente es el
que restringe primero; con la tarifa consultada representa del orden de 60–80 ofertas brutas al día, no 60–80 entregables.

Antes de iniciar se guarda una reserva en `trabajo/apify_presupuesto.json`. Las reservas comparten un bloqueo entre hilos,
se conservan al repetir corridas y no se reinician con modo inicial. Si el proveedor no confirma el inicio o falla la
lectura, la reserva no se devuelve ni se relanza automáticamente la misma petición. Es deliberadamente conservador:
puede quedar crédito sin usar. La ejecución también lleva `maxTotalChargeUsd` en Apify.

Se registra el identificador de ejecución y el costo de uso que informe el proveedor. Ese costo puede no representar
todos los conceptos facturados; no se descuenta de las reservas automáticamente. La búsqueda pagada del feed está apagada
por defecto. Si se habilita, comparte las mismas reservas y topes.

Hay que conservar la memoria de presupuesto al copiar el proyecto o recuperar estado. Su borrado puede habilitar nuevas
reservas. Otros proyectos, ejecuciones manuales y pruebas de diagnóstico consumen el crédito de la misma cuenta por
fuera de esta memoria: mantener el plan gratuito y límites de cuenta de Apify como control global. El calendario del
programa puede no coincidir con el ciclo de crédito del proveedor.

`--prueba` no ejecuta actores pagados. El diagnóstico explícito `probar_apify` comprueba una oferta real con máximo USD
0,01 y no escribe en Supabase; también consume crédito y no debe repetirse innecesariamente.

## Publicaciones complementarias y frescura

Si se habilita el feed, una publicación con enlace LinkedIn puede descubrir una oferta: el programa recupera la ficha,
comprueba que no esté cerrada y exige título, empresa y descripción reales de esa ficha. Las demás siguen pendientes.

El horario nocturno todavía no cambia. Para reducir retrasos se recomienda una captura incremental cada hora, independiente
de la selección diaria y con marcas de tiempo de publicación y detección. Con USD 5 no se garantiza búsqueda completa de
LinkedIn cada hora: las fuentes gratuitas deben aportar frecuencia y Apify un refuerzo acotado. Implementar ese cambio
requiere un flujo incremental y ampliar primero el contrato para conservar horas; no basta con multiplicar el cron actual.
