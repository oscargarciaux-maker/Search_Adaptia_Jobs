# Cobertura, remotas e histórico

Uso vigente: [GUIA_CLIENTE.md](GUIA_CLIENTE.md). Persistencia actual: contratos [v2](CONTRATO_DATOS_v2.md) y
[v3](CONTRATO_DATOS_v3.md). Las cifras de pruebas al final son antecedentes, no certificación operativa actual.

Decisiones confirmadas por Oscar durante la revisión del repositorio. Estos ajustes están en el código;
no implican un despliegue ni una modificación de servicios externos.

## Cobertura y selección

Una región general de la fuente (por ejemplo EMEA) no convierte en elegible una oferta cuya residencia se limita
explícitamente a otros países. Se reconocen restricciones como «must be physically located in» y el alcance específico
del título «Remote in…», también cuando la ficha de ubicación es más amplia. Las restricciones explícitas reconocidas
se intersectan; una oficina o un cliente extranjero en la descripción no es por sí solo una restricción. La revisión
también se aplica al inventario guardado, archivando las no elegibles sin reescribir selecciones históricas.

Estonia y los demás países europeos fuera de España se reconocen también por sus aliases configurados. Una ubicación
extranjera específica prevalece frente a una etiqueta EMEA general. El texto comercial «global scope» no acredita
contratación mundial. Las ubicaciones de confianza baja se conservan para revisar, pero `contrato.entregable` las
excluye de nuevas entregas con motivo `elegibilidad regional por confirmar`; no cuentan para completar veinte.
Las remotas con alcance mundial explícito siguen siendo válidas. La sede extranjera de una empresa, por sí sola,
no restringe un aviso mundial. Frases de herramientas como «exclusively in Figma» no son restricciones geográficas.

- LATAM (20 territorios configurados), España y ofertas remotas mundiales. Otros países se ampliarán después.
- Bogotá fija únicamente la hora de ejecución, no una preferencia de país.
- LinkedIn incorpora búsquedas remotas para LATAM, España y Worldwide, además de las búsquedas por país.
- Indeed consulta modos remoto y general en sus 12 países soportados. No todos los países tienen una fuente equivalente.
- Se reparte el presupuesto por turnos entre familias, con cuatro turnos prioritarios por uno para las demás.
  Dentro de cada familia se atienden combinaciones menos recientes; en empates, remotas primero y desempate diario.
- La entrega favorece remotas para varios países con confianza alta, luego
  otras remotas con región identificada (incluye estimaciones de confianza media) y locales con país identificado.
  No se descartan locales para inflar una cuota remota artificial.
  El límite de dos ofertas por empresa y rol sigue vigente. `preferir_remotas` se configura en `datos/entrega.yaml`.
- Remoto no significa mundial: un puesto remoto limitado a Colombia sigue siendo solo para Colombia.
  Las restricciones de residencia prevalecen y una región desconocida se muestra como «por confirmar».
  Las estimaciones por zona horaria tienen confianza media; no equivalen a residencia confirmada por el empleador.
- No hay cuota por país: se diversifican las ofertas disponibles sin inventar cobertura. Que un país no aparezca en una
  entrega no prueba que no tenga ofertas. Las fuentes y sus bloqueos afectan el resultado.

## Cargos exactos y afines

El mapa ya reconocía coincidencias exactas, similares y cercanas. Antes se descubrían menos porque LinkedIn usaba solo
las primeras cuatro consultas e Indeed únicamente la primera. Ahora LinkedIn rota grupos de hasta cuatro términos;
Indeed y Get on Board rotan términos individuales, incluyendo aliases de los tres grados y las consultas originales.
Apify de ofertas usa también los grupos rotativos; las publicaciones del feed mantienen sus consultas explícitas.

Ejemplo de UX/UI: Product Designer, UX Designer, UI Designer, Interaction Designer, UX Researcher, Design Systems
Designer, Service Designer y vecinos definidos en el mapa. Los títulos genéricos todavía requieren evidencia del oficio;
no se incorpora cualquier «Designer» sin clasificación. Una exclusión genérica no anula un vecino escrito explícitamente
en el mapa, como UX Engineer. Las exclusiones de títulos ajenos siguen aplicándose.

Se conservan los seis roles de entrega. Cada vacante ocupa un solo rol, el de mejor coincidencia; Product Owner puede
aparecer como cercano en una búsqueda UX/UI y asignarse a Product Owner en la entrega, sin duplicar la oferta.

El presupuesto, la paginación y los bloqueos impiden garantizar todas las variantes en todos los países cada noche.
Se guarda la fecha por variante de consulta para que cambiar de término no recorte indebidamente la ventana de 30 días.
`salud.json` incluye búsquedas por familia y lugar, modalidades, pendientes de sincronización y remotas por rol.
Hace falta observar al menos siete días para medir volumen útil, cobertura y costos reales.

## Meta diaria y búsquedas de refuerzo

La meta es **20 por cada uno de los seis roles**, es decir 120 ofertas distintas al día. «Nueva» significa nunca
entregada; no necesariamente publicada en las últimas 24 horas. El sistema combina nuevas capturas con una reserva
reciente sin entregar. Esa reserva ayuda a cubrir variaciones, pero no reemplaza el ingreso sostenido de ofertas.

Si faltan ofertas, la ejecución normal hace hasta dos rondas adicionales en LinkedIn público, Indeed y Get on Board,
solo para las familias de los roles insuficientes y con nuevas variantes de términos. Los límites viven en
`datos/config.yaml`, sección `refuerzo`. No se activa Apify adicional ni se relajan ubicación, idioma, pertinencia,
no repetición o máximo por empresa para presentar una meta como cumplida.

Las pruebas cortas no ejecutan esos refuerzos automáticamente. En la primera prueba había 14 candidatas UX/UI
entregables y otras 14 sin descripción suficiente. Product Owner tenía 43 candidatas, pero solo capacidad para 19
aplicando el límite de dos por empresa. No eran conteos del mercado completo ni evidencia de suministro diario.

El diagnóstico por rol distingue candidatas, descartes, capacidad bajo el máximo por empresa y reserva sin entregar.
Si continúa el déficit tras los refuerzos, la pantalla lo muestra y Actions emite una advertencia. Se conserva una serie
de hasta 30 días en `trabajo/metricas_entrega.json`; `salud.json` incluye las siete mediciones más recientes. La meta
de selección y las filas pendientes de Supabase son indicadores distintos. Una ejecución «success» de GitHub no prueba
que la cuota o la sincronización hayan sido completas.

Para verificar continuidad hacen falta corridas reales de días diferentes con memoria de entregas preservada. Repetir
la misma prueba sobre una bodega sin memoria no demuestra que mañana habrá 120 ofertas nuevas. No se garantiza oferta
externa ilimitada: si las fuentes y el flujo diario no sostienen la meta, habrá que ampliar cobertura/fuentes o presupuesto
con evidencia de esos reportes.

## Entorno, PR y archivos de descarga

La copia de trabajo está dentro del entorno de nube de este chat; «local» significa local a esa máquina, no al computador
del usuario. Editar esa copia, subir una rama, abrir un PR, fusionarlo y desplegar son pasos diferentes. El PR permite
revisar cambios antes de incorporarlos a `main`; no se fusiona ni se lanza el despliegue automáticamente desde este chat.

Supabase es la base de datos obligatoria de la entrega. Excel pertenecía a una versión anterior; se retiraron tanto
la generación como la descarga opcional por decisión del usuario. No reintroducirlas desde el plan histórico.
No se borran los históricos anteriores. Las publicaciones del feed de Apify no cuentan como ofertas hasta verificarse.
Controles actuales de calidad y primera corrida: [`CALIDAD_ARRANQUE.md`](CALIDAD_ARRANQUE.md).

## Identidad, descripciones y sincronización

- Ya no se unen ofertas únicamente por empresa y título sin nivel. Se une por enlace compartido o por empresa,
  título completo, ubicación y contenido iguales. Se conservan identificadores existentes al completar una oferta.
  La deduplicación es conservadora: puede dejar copias con textos distintos para no perder puestos diferentes.
- Se conservan aliases de enlaces internamente. Los países combinados mantienen la confianza menos segura de las
  fuentes; no se convierte una lista dudosa en confirmada por mezclarla con un país conocido.
- Las descripciones pueden conservar hasta 30.000 caracteres, según el contrato. Lever incorpora requisitos y beneficios;
  SmartRecruiters pagina su listado y, junto a Workable, intenta completar descripciones con consultas de detalle acotadas.
  Un fallo del detalle no equivale a una oferta cerrada. Un listado incompleto no se toma como evidencia de cierre.
- La selección y la sincronización tienen estados separados. Las filas seleccionadas quedan en una cola antes del envío
  y solo salen cuando Supabase confirma el lote. Los reintentos son idempotentes por `external_id` y conservan fechas.
  «Filas sincronizadas» incluye las que ya existían; no significa que todas fueran insertadas por primera vez.
- Las pruebas cortas de Actions no actualizan la rama publicada. Una prueba local escribe solo su carpeta de salida.

Los datos fusionados o recortados por versiones anteriores no se pueden reconstruir automáticamente. La corrección
protege nuevas capturas; recuperar contenido o separar ofertas antiguas exige volver a recogerlas de sus fuentes.

## Conservación y futuro seguimiento de postulaciones

Hay plazos distintos para la vista activa, la memoria y el histórico:

| Datos | Conservación actual | Propósito |
|---|---|---|
| Bodega activa del buscador | 30 días; también retira cierres detectados | Mostrar oportunidades recientes |
| Archivos antiguos CSV/Excel | No se generan; funcionalidad retirada | Históricos anteriores conservados |
| Memoria local de entregas | 180 días; complementada por recuperación Supabase con v2 activo | Evitar repetir entregas |
| Ofertas guardadas en Supabase | Sin borrado automático por este código | Histórico persistente |
| Cola pendiente de Supabase | Hasta confirmación; sin limpieza por antigüedad | Recuperar fallos de sincronización |

`ofertas` almacena filas seleccionadas, hasta dos enlaces por vacante. `catalogo_vacantes` conserva vacantes y retiros
normalizados; `entregas_diarias` conserva la selección canónica con referencia y snapshot. No se guardan todos los avisos
crudos ajenos al mapa/países/ventana. Las tablas no se eliminan por la limpieza de la bodega.

La retirada por antigüedad no prueba cierre. V2 sincroniza cierres/archivos observados del catálogo; v3 incorpora evidencia
de enlaces. No implica que todas las ofertas se hayan revisado recientemente. `ofertas.status=active` es histórico e
inmutable: consultar el estado actual del catálogo y la caducidad de su verificación. Ninguno informa el progreso privado
de una candidatura. La vista `entrega_de_hoy` muestra la fecha máxima disponible, que podría ser anterior a hoy.

Para la futura etapa se recomienda:

1. Utilizar el catálogo canónico ya implementado y sus evidencias vigentes; no duplicarlo ni borrar ofertas referenciadas.
2. Postulaciones separadas por cliente y oferta, con historial de eventos: aplicada, entrevista, rechazada, etc.
3. Relaciones que impidan eliminar una oferta referenciada y una copia de su contenido al postular.
4. Políticas de acceso por cliente, copias de seguridad, restauración comprobada y supervisión de tamaño de la base.
5. Definir la procedencia del progreso: actualización manual, integración autorizada o datos del portal. Ver la página
   pública de una oferta normalmente no permite conocer el resultado privado de la postulación de una persona.

No se crean tablas de clientes ni seguimiento en este cambio. La retención prolongada no tiene por qué mantener ofertas
viejas dentro de las búsquedas activas; la vista comercial y el histórico deben ser independientes.

## Validación de esta revisión

- 362 pruebas de Python y las pruebas del motor JavaScript pasaron; se comprobó sintaxis de la pantalla y formato del diff.
- Prueba corta con fuentes públicas, sin claves de Apify/Brave ni escrituras a Supabase: 5,9 minutos, 25.810 registros
  crudos y 1.648 vacantes en el catálogo activo; 828 clasificadas remotas. 817 registros del catálogo tenían ubicación
  por confirmar: no deben confundirse con cobertura regional verificada. Los conteos por país se superponen.
- Entrega simulada: Product Designer 20, UX/UI 14, Product Owner 19, Product Manager 20, AI Engineer 20 y QA 20.
  La prueba usa presupuestos reducidos y no verifica cuotas diarias sostenidas.
- Refuerzo gratuito real sobre ese catálogo: una ronda reunió 468 registros adicionales (18 búsquedas LinkedIn,
  6 Indeed y 6 Get on Board). La selección posterior llegó a **20 en cada uno de los seis roles**, 120 en total,
  manteniendo máximo por empresa, pertinencia y no repetición. No demuestra continuidad entre días distintos.
- Se completaron 44 descripciones de portales en esa corrida. Apify y la conexión real a Supabase quedaron sin validar
  por falta de credenciales en este entorno; los reintentos se probaron con respuestas simuladas.
- La salida fue temporal, fuera del repositorio; no se guardó memoria de entregas, no se subió nada y no se desplegó.
