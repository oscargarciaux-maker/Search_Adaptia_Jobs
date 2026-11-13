# Manual operativo — Adaptia Jobs

La revisión v6 incorpora un panel privado para el operador. La guía de uso detallada está en [PANEL_CONTROL.md](PANEL_CONTROL.md):
añadir clientes/perfiles, revisar cargos afines, repartir cupos, guardar, programar y copiar resultados para WhatsApp.
El acceso real requiere configurar inicio de sesión más adelante; la demostración usa datos ficticios.

La meta de 120 se reparte por cargo, no por persona: tres Product Designers pueden compartir resultados del mismo cupo
cuando sus filtros coincidan. Los filtros pertenecen a cada perfil y pueden producir cantidades diferentes por cliente.
Mientras se edita un perfil, el panel estima cuántas vacantes ya guardadas y aún no entregadas lo cumplirían hoy y
qué ajuste añadiría más (por ejemplo, admitir experiencia o inglés no informados: solo ~1 de cada 4 avisos dice los
años exigidos y ~1 de cada 8 el nivel de inglés). En «Cargos y cupos» cada cargo indica si alcanza para su cupo.
Si a una persona le faltan vacantes para llegar a 5, pueden aparecer **posts de LinkedIn** de quien está contratando su cargo, con la etiqueta «Post» (en el panel) o «📣 Post» (en WhatsApp): no tienen formulario de postulación, se contacta a quien publicó por mensaje o por el correo que deja. Van siempre al final y nunca reemplazan vacantes formales.

**Por confirmar (un par de minutos al día).** Algunas vacantes le servirían a un cliente, pero el aviso no dice con claridad desde qué país se puede postular. En «Por confirmar» aparecen como mucho 10 al día, primero las que ayudan a clientes con menos de 5. Lee la frase resaltada, revisa el país sugerido y pulsa «Sirve para…», «Solo para otro país», «No sirve» o «Saltar» (o las teclas 1–4). Las que confirmes llegan ese mismo día a sus clientes. Si varias tienen la misma ubicación, marca «Aplicar a las … con esta misma ubicación»: desde la noche siguiente esa ubicación se resuelve sola. Si un día no revisas, no pasa nada: esas vacantes simplemente no se entregan. El sistema aprende solo de tus decisiones: cuando dos o más coinciden en un lugar (por ejemplo, dos pueblos de «Sant Cugat»), crea una regla y la próxima vez lo resuelve sin preguntarte. Las ves y puedes desactivarlas en «Actividad → Reglas de ubicación». Para revisar muchas de una vez, usa «Descargar todas (CSV)», llena las columnas «decision» (sirve, otro país, no sirve o saltar) y «pais», y pulsa «Subir revisión».

Nada se envía solo. Cada mañana, en «Mensajes», cada cliente con WhatsApp y aceptación tiene su mensaje listo: «Abrir en WhatsApp» abre su chat con el texto escrito para revisarlo y enviarlo. No hay seguimiento de postulaciones.

Los apartados siguientes describen también el scraper heredado y sus consultas técnicas en Supabase. **Con panel activo,
los cargos son configurables y role_id adopta cargo:<UUID>; no hay que buscar siempre role_id=qa.** Las vistas antiguas
no calculan los filtros privados del panel; consultar las asignaciones desde la nueva interfaz.

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

Mientras no exista una versión vigente del panel, la meta heredada es veinte nuevas por cada uno de seis roles: Product Designer, UX/UI Designer, Product Owner,
Product Manager, AI Engineer y QA. Las capturas horarias no crean otro lote ni reponen automáticamente cierres del
histórico. La cifra seleccionada no equivale a oportunidades disponibles ahora. Un déficit debe mostrarse, no
rellenarse con repeticiones, pendientes o cargos ajenos. Las ubicaciones con confianza baja quedan fuera de nuevas
entregas hasta confirmarse; una etiqueta remota no acredita que se pueda aplicar desde cualquier país. Se conservan variantes pertinentes del mapa de cargos.

La cobertura permitida es LATAM y España, solo con vacantes escritas en español o inglés. Desde el 12 de noviembre, Brasil solo cuenta dentro de remotas abiertas a varios países: no llegan vacantes en portugués ni locales, híbridas o remotas solo para Brasil (contrato v12). Entre ofertas pertinentes se priorizan las remotas que permitan trabajar
desde esa cobertura, incluidas las mundiales. Las presenciales e híbridas necesitan una ubicación local identificada;
las remotas limitadas a países ajenos se excluyen. País desconocido, simple coincidencia horaria o texto comercial
sobre un equipo global no son prueba de elegibilidad. Si falta evidencia, no se completa la meta con ese aviso.
La sede de la empresa puede estar en otro país si el puesto permite realmente trabajar desde la cobertura.
Las fichas externas pueden contener errores: estas reglas no equivalen a una garantía absoluta sobre cada anuncio.

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
El envío automático por WhatsApp (API oficial) y el seguimiento de candidaturas requieren una ampliación separada.
