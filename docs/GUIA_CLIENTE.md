# Manual operativo — Adaptia Jobs

El producto es un scraper automatizado que guarda y permite consultar vacantes en Supabase. La interfaz web,
sus funciones Cloudflare y el despliegue de GitHub Pages se retiran por decisión del propietario. No se requiere
alojamiento web ni navegador especial para que se ejecuten las búsquedas. No hay agente de WhatsApp ni seguimiento
individual de postulaciones en esta etapa.

## 1. Dónde consultar resultados

En Supabase, abrir el proyecto correcto y el esquema `public`. En Table Editor pueden verse tablas y vistas;
SQL Editor permite consultar las vistas si no aparecen en el listado. No compartir claves administrativas.

| Objeto | Uso |
|---|---|
| `catalogo_vacantes` | Registro principal por oportunidad, descripción, tiempos y verificación |
| `entregas_diarias` | Selección histórica por fecha y rol, sin contar cada enlace como otra vacante |
| `seleccion_estado_actual` | Selección cruzada con catálogo, afinidad y enlace vigentes; `estado_actual=lista` es la consulta operativa |
| `resumen_entregas_actual` | Seleccionadas, listas ahora, pendientes, retiradas y afinidad por revisar, agrupadas por fecha y rol |
| `ofertas` | Una fila operativa por vacante reconocida tras SQL 005, con los enlaces alternativos asociados |
| `ofertas_enlaces_historicos` | Copias anteriores por URL conservadas íntegramente, con referencia al registro principal |
| `entrega_de_hoy` | Última fecha existente en el histórico v1; puede corresponder a un día anterior |
| `estado_operativo` | Tareas administrativas pendientes y recuperación; no es un listado para clientes |
| `apify_reservas` | Reservas duraderas del presupuesto de Apify; no borrar para liberar crédito |
| `adaptia_migraciones` | Versiones SQL instaladas; uso administrativo |

Para QA, filtrar `role_id=qa` en la selección o `search_tag=QA` en el histórico. Sus títulos también pueden ser
Tester, SDET o variantes pertinentes. Dos enlaces de la misma vacante se asocian a una sola fila. SQL 005 archiva las copias antiguas sin perder sus datos
y evita que un reintento las recree. Las filas con vínculo ambiguo se conservan y se informan como sin identificar;
no se eliminan por compartir título. Consultar [Identidad v5](CONTRATO_DATOS_v5.md).

## 2. Estados, fechas y límites

`ofertas.status=active` es histórico. En el catálogo, `active` tampoco certifica disponibilidad por sí solo.
La vista actual exige catálogo activo, perfil correspondiente y enlace de esa ficha comprobado hace menos de seis
horas. `closed` significa cierre observado; `archived` puede ser antigüedad, calidad u otra retirada. `por_verificar`
indica falta de evidencia vigente; `fuera_de_perfil` indica que la clasificación actual no corresponde al rol;
`afinidad_por_confirmar` requiere la siguiente actualización de clasificación.

Los bloqueos, CAPTCHA o respuestas incompletas quedan pendientes y se reintentan automáticamente dentro del
presupuesto. No requieren configurar una contraseña por vacante. Cierres, enlaces rotos y otras causas de rechazo
se apartan conservando sus referencias. No se comprueba una postulación completa ni se autentica a toda empresa.

Publicación, primera detección, última observación y comprobación del enlace son momentos distintos. Detectada hoy
no significa publicada hoy. Las horas terminadas en Z se expresan en UTC; Colombia está cinco horas atrás.

La meta diaria es veinte nuevas por cada uno de seis roles: Product Designer, UX/UI Designer, Product Owner,
Product Manager, AI Engineer y QA. Las capturas horarias no crean otro lote ni reponen automáticamente cierres del
histórico. La cifra seleccionada no equivale a oportunidades disponibles ahora. Un déficit debe mostrarse, no
rellenarse con repeticiones, pendientes o cargos ajenos. Las ubicaciones con confianza baja quedan fuera de nuevas
entregas hasta confirmarse; una etiqueta remota no acredita que se pueda aplicar desde cualquier país. Se conservan variantes pertinentes del mapa de cargos.

## 3. Ejecuciones y horarios

En GitHub → Actions se revisan Bodega nocturna, Captura horaria, Preparar Supabase, Búsqueda profunda, Diagnóstico
y Pruebas. La nocturna solicita inicio a la 1:17 a. m. Colombia y la captura al minuto 23 de cada hora. GitHub puede
retrasar o saltar horarios; comprobar que la tarea se ejecutó y terminó, no solo que el código fue fusionado.

La captura horaria no consume Apify. La búsqueda nocturna y la profunda pueden usarlo con presupuesto compartido de
hasta USD 5/mes para este programa. Revisar el gasto global de la cuenta, que puede incluir otros trabajos.
Las fuentes y variantes rotan; no se recorren todos los títulos de todos los países en cada ejecución.

Una búsqueda a pedido se inicia en Actions → Búsqueda profunda → Run workflow, rama main, con cargo y país opcional.
No crea otra entrega diaria ni acredita la vigencia de todas las ofertas encontradas.

## 4. Rutina y mantenimiento

Antes de usar vacantes, consultar fecha del último reporte, sincronización sin pendientes y disponibilidad por rol.
Abrir una muestra de los enlaces comprobados y revisar restricciones de país, idioma y experiencia. Si la captura
falla, conservar su enlace, mensaje y cantidades; seguir [Operación](OPERACION_Y_RECUPERACION.md).

El reporte técnico está en `publicado/datos/salud.json`; es una foto de la ejecución, no un estado de enlaces en
vivo. La rama histórica `publicado` conserva inventario y memoria: no eliminarla por haber retirado la web.
Las vistas de Supabase calculan caducidad con la hora de la base.

La instalación preferida es [automática](INSTALACION_AUTOMATICA.md). Las migraciones se preparan con respaldo cifrado
previo; no copiar SQL 002/003/004 cada vez. Un respaldo previo a migraciones no equivale a una copia periódica diaria.
Para cambiar propietario seguir [Traspaso](TRASPASO.md); para aceptar la entrega, [Estado y aceptación](ACEPTACION_Y_ESTADO.md).
La automatización de WhatsApp y el seguimiento de candidaturas requieren una ampliación separada.
