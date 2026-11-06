# Guion de demostración y explicación del sistema

Preparado la noche del 5 de noviembre de 2026, hora de Colombia. Leer junto al [manual del cliente](GUIA_CLIENTE.md).
Los cambios incluidos con este documento requieren fusión, preparación automática y una captura/despliegue posteriores.
La evidencia fechada de abajo corresponde a la versión productiva observada, no acredita esos cambios nuevos.

## 1. Cómo explicarlo en un minuto

«Este sistema reúne ofertas de empleo de varias fuentes, reconoce nombres alternativos de los cargos y organiza
las oportunidades para personas de LATAM y España, incluidas remotas mundiales. Actualiza el catálogo durante el día
y cada noche intenta seleccionar veinte oportunidades nuevas por cada uno de seis perfiles. Comprueba enlaces,
conserva el historial en Supabase y permite buscar y preparar mensajes para compartir por WhatsApp manualmente».

El valor comercial es ahorrar búsqueda, clasificación y revisión repetitiva. La decisión de si una oportunidad
le sirve a una persona requiere mirar experiencia, país, idioma y condiciones. No prometer contratación, cobertura
total de LinkedIn, disponibilidad perpetua, detección de todo fraude ni ciento veinte ofertas útiles garantizadas.

## 2. Qué hace cada parte y dónde encontrarla

| Parte | Explicación para el cliente | Dónde se encuentra |
|---|---|---|
| Página de búsqueda | Pantalla para buscar, filtrar y preparar mensajes | [Abrir buscador](https://oscargarciaux-maker.github.io/Search_Adaptia_Jobs/) |
| GitHub, repositorio | Guarda el programa, las reglas y sus manuales | [Repositorio](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs) → pestaña Code |
| GitHub Actions | Computadores temporales de la nube que ejecutan las tareas | [Actions](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions) |
| Supabase | Base de datos con ofertas, selección histórica y recuperación de tareas | Proyecto del propietario → Table Editor / SQL Editor |
| LinkedIn público | Una fuente de fichas de empleos sin sesión personal | Métricas LinkedIn en Estado y Actions |
| Apify | Refuerzo para recuperar ofertas formales de LinkedIn, con tope configurado | Cuenta del propietario → Runs y Billing; métricas LinkedIn (Apify) |
| Otras fuentes | Indeed, Get on Board, portales de empresas y tableros remotos con original | Página → Estado → fuentes |
| GitHub Pages | Sirve la página y la copia pública de sus datos | Repositorio → Settings → Pages; Actions → Actualizar página |
| Navegador | Muestra resultados y recuerda marcas manuales de enviadas | Página → Estado → Historial de enviadas |
| Documentos | Instrucciones de operación, instalación y entrega | Repositorio → carpeta docs |

Todo esto corre en la nube. El computador del cliente puede estar apagado. Una tarea de GitHub utiliza una máquina
temporal; por eso Supabase conserva los datos importantes entre ejecuciones. El programa consulta y clasifica con
código y reglas: no paga consultas de IA por cada oferta. La IA utilizada para desarrollar el programa no es un
agente que esté buscando o conversando con los candidatos en producción.

## 3. Qué significan código, PR, preparación y publicación

1. Un **PR** propone una mejora y muestra sus pruebas. Mientras no se fusione, `main` conserva la versión aprobada anterior.
2. Al **fusionar**, el código queda aprobado para las siguientes ejecuciones.
3. La **preparación automática de Supabase** revisa versiones y, si corresponde, sube un respaldo cifrado y aplica las
   migraciones nuevas. El operador no copia SQL 002, 003 ni 004 cada vez. Requiere secretos iniciales correctos.
4. Una **captura** busca, comprueba y guarda datos; debe verse que realmente se ejecutó y terminó.
5. El **despliegue de página** hace visible la copia recién generada. Una captura y su despliegue son tareas diferentes.

Una vista de base de datos es una consulta guardada: muestra información de las tablas sin duplicar ni borrar el
historial. La vista de estado actual combina «qué seleccionamos» con «qué sabemos ahora de esa oferta».

## 4. Dónde mirar las vacantes en Supabase

Abrir el proyecto correcto y, en Table Editor, seleccionar el esquema `public`. Si una vista no aparece allí,
se puede consultar en SQL Editor. Quitar filtros anteriores antes de comparar números.

| Tabla o vista | Para qué sirve | Cómo consultar QA |
|---|---|---|
| `catalogo_vacantes` | Una ficha por oportunidad: descripción, países, tiempos y verificación actual | El cargo está en `datos.titulo`; las familias en `datos.familias`. No tiene columna `search_tag` |
| `entregas_diarias` | Una selección por oportunidad, con día, rol y copia histórica | Filtrar `role_id = qa` y la fecha deseada |
| `ofertas` | Histórico compatible con la plataforma anterior, una fila por enlace | Filtrar `search_tag = QA` y `delivery_date`; el título puede decir Tester o SDET |
| `entrega_de_hoy` | Última fecha disponible de `ofertas` | No significa necesariamente la fecha del calendario de hoy |
| `seleccion_estado_actual` — SQL 004 | Cruza la selección con estado, afinidad y enlace vigentes | Filtrar `role_id = qa`; para compartir, `estado_actual = lista` |
| `resumen_entregas_actual` — SQL 004 | Cantidades históricas y disponibles por día y rol | Comparar `seleccionadas`, `listas_ahora`, `por_verificar`, `retiradas`, `revisar_afinidad` |
| `estado_operativo` | Tareas pendientes y selecciones en recuperación | Es administrativa, no un listado para clientes |
| `apify_reservas` | Memoria durable del presupuesto compartido | No borrar para volver a tener crédito |
| `adaptia_migraciones` | Registro administrativo de versiones SQL aplicadas | El operador no la edita |

Ejemplo de consulta de solo lectura para el administrador, después de aplicar automáticamente SQL 004:

```sql
select * from public.resumen_entregas_actual
where delivery_date = (select max(delivery_date) from public.entregas_diarias)
order by role_id;

select delivery_date, job_title, estado_actual, url_utilizable, comprobada_en
from public.seleccion_estado_actual
where role_id = 'qa'
  and delivery_date = (select max(delivery_date) from public.entregas_diarias)
order by estado_actual, job_title;
```

No es necesario ejecutar estas consultas cada día para operar la página. Sirven para explicar y contrastar datos.
Las vistas son privadas; no poner la clave administrativa en el navegador para permitir una demostración.

## 5. Por qué una cerrada podía decir active

`ofertas.status` conserva el dato histórico de selección. No se actualiza como un monitor de disponibilidad.
En `catalogo_vacantes`, `active` significa que no hay una retirada confirmada; una ficha pendiente o con comprobación
caducada también puede seguir ahí. **Ninguno de esos dos active basta para compartir una oferta**.

La consulta actual exige estado de catálogo activo, cargo pertinente para el rol y enlace comprobado hace menos de
seis horas. Si caduca, deja de figurar como lista sin borrar el histórico. Cuando una captura confirma cierre, el
catálogo pasa a `closed`; antigüedad u otras causas pueden dejarla `archived`. El sistema conserva los registros.
La revisión usa un presupuesto y las fuentes pueden bloquearla: no hay comprobación instantánea de todo el inventario.

Caso reportado por Oscar: [Indeed, identificador 9e7537b067923296](https://es.indeed.com/viewjob?jk=9e7537b067923296),
«Frontend & UX/UI Junior Designer». La auditoría de solo lectura confirmó `active` tanto en histórico como catálogo.
La misma ficha tiene un [original de Deloitte](https://empleo.es.deloitte.com/job/Madrid-Frontend-&-UXUI-Junior-Designer/1449096133/):
la comprobación de las 11:02 p. m. Colombia lo consideró ficha específica accesible. Indeed quedó sin confirmar.
Esto permite compartir únicamente el enlace comprobado de Deloitte; no acredita que la copia de Indeed siga abierta.
Incluso un original comprobado puede cerrar después o antes de terminar una postulación.

## 6. Qué pasa con pendientes, rechazadas y la meta de 120

| Situación | Acción automática | Acción de la persona |
|---|---|---|
| Aún no revisada o comprobación caducada | Entra en la revisión acotada de próximas capturas | Usar otras comprobadas; no configurar contraseñas por vacante |
| 403, CAPTCHA, login, timeout o contenido insuficiente | Se mantiene por verificar y se reintenta; no se inventa cierre | No requiere intervención rutinaria; comunicar si afecta muchas ofertas o persiste |
| Un enlace falla y otro está comprobado | Comparte exclusivamente el comprobado | Abrir ese enlace y revisar condiciones |
| Cierre, 404, cobro, ciclo o página general confirmados | Aparta el enlace/oferta; conserva histórico | No compartir como disponible; reportar una muestra si se repite mucho |
| Cargo fuera de perfil con el mapa corregido | Deja de contar como disponible para ese rol | Revisar reglas con mantenimiento si era un afín legítimo |
| Error de Supabase o ejecución detenida | Conserva pendientes e informa fallo; reintenta al recuperar | Administrador revisa Actions y causa técnica |
| Déficit real por rol | Intenta refuerzos durante la selección diaria y muestra el faltante | No compensar QA con otros cargos; revisar cobertura y fuentes |

La revisión horaria tiene un máximo de 120 candidatas y 180 segundos; la diaria, 300 y 240 segundos. La caché evita
repetir comprobaciones todavía vigentes; los límites y los bloqueos pueden impedir revisar todas. No consume Apify
ni aumenta la concurrencia por dominio. «Por verificar» no es una solicitud de asistencia individual al dueño.

La meta es **20 por cada rol**, no veinte entre todos. Una oferta con dos enlaces puede generar dos filas v1, pero
solo una selección. La cobertura del catálogo contiene 53 familias configuradas; la cuota diaria existe únicamente
para los seis roles. Las consultas rotan: no se consultan todas las variantes y países en cada corrida.

Mantener las 120 seleccionadas históricas no equivale a tener 120 listas ahora. El mercado cierra ofertas y las
fuentes bloquean consultas. Se conserva el lote para no repetir ni cambiar la historia. Las capturas horarias no
seleccionan silenciosamente otro lote ni sustituyen las cerradas. Si se desea una reposición continua adicional a la
selección diaria, debe definirse y construirse esa función con reglas de cupos e historial antes de ofrecerla al cliente.

## 7. Qué se encontró realmente en la auditoría

La [auditoría de Supabase](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42160286445)
terminó a las 11:04 p. m. Colombia del 5 de noviembre. No escribió datos ni utilizó Apify.

| Rol | Selecciones del 5 de noviembre | Filas v1, contando enlaces |
|---|---:|---:|
| Product designer | 20 | 29 |
| UX/UI designer | 20 | 28 |
| Product Owner | 20 | 26 |
| Product manager | 20 | 25 |
| AI Engineer | 20 | 27 |
| QA | 20 | 27 |
| Total | 120 | 162 |

Había un problema de pertinencia: diez seleccionadas QA eran cargos generales de desarrollo/DevOps clasificados como
cercanos. Por tanto, ese veinte no demostraba veinte oportunidades pertinentes de QA. La corrección elimina esos
alias demasiado generales y el caso de QA de Customer Success que no corresponde a pruebas de software. Prioriza
afinidad antes de alcance remoto/diversidad y restringe cercanos genéricos de IA, conservando variantes explícitas
como «Machine Learning / Data Engineer». Reclasifica inventario anterior,
mantiene las selecciones históricas y permite ver los faltantes sin ocultarlos.

La [primera captura confirmada tras la preparación central](https://github.com/oscargarciaux-maker/Search_Adaptia_Jobs/actions/runs/42159000280)
terminó a las 11:00 p. m. Colombia: en su comprobación parcial, el lote histórico tenía 32 verificadas, 86 pendientes
y 2 rechazadas. Son estados de enlace de ese corte, anteriores a la corrección de afinidad; no significan 32 aptas
definitivas ni el estado de la demostración del día siguiente. Consultar nuevamente antes de presentarlo.

## 8. Demostración de diez minutos

1. **Minutos 0–1:** explicar el problema y el circuito fuentes → captura → Supabase → página → mensaje manual.
2. **Minutos 1–2:** abrir Estado, mostrar hora de datos y distinguir seleccionadas de listas ahora. Si el dato tiene
   más de dos horas, mostrar el aviso y revisar Actions antes de describirlo como actualizado.
3. **Minutos 2–4:** buscar UX/UI, seleccionar país, remotas y «Solo enlaces comprobados». Mostrar una variante afín
   y explicar que remoto puede estar limitado a un país. Comparar orden por afinidad, alcance y fecha.
4. **Minutos 4–5:** usar últimas 24 horas. Explicar que exige hora real de publicación; las detectadas hoy sin hora
   conocida no se presentan como recién publicadas.
5. **Minutos 5–6:** buscar QA y mostrar Tester/SDET/QA Engineer según resultados disponibles. No llamar QA a un
   DevOps genérico ni ocultar un faltante real. Abrir un enlace comprobado sin completar una postulación.
6. **Minutos 6–7:** marcar una o dos oportunidades y copiar el mensaje. No enviarlo a nadie sin autorización del
   destinatario. Explicar que copiar o marcar no certifica envío, lectura ni postulación.
7. **Minutos 7–9:** mostrar en Supabase el resumen por roles y una selección con su estado actual. Contrastar
   `role_id=qa` con `search_tag=QA`; explicar las dos filas por dos enlaces.
8. **Minutos 9–10:** abrir Actions, una ejecución real completada y su despliegue. Acordar quién vigila fallos,
   administra accesos y presta mantenimiento. Entregar este guion y el manual.

Antes de la reunión dejar abiertas esas pestañas. No mostrar Settings → Secrets, URI de conexión, claves, respaldo
descifrado ni información de clientes. Si no hay comprobadas para el ejemplo, mostrar el pendiente con honestidad
y utilizar otra oferta/rol comprobado; no desactivar controles para una demostración.

## 9. Operación y entrega al propietario

La nocturna solicita inicio a la **1:17 a. m. Colombia**. La captura gratuita solicita el **minuto 23 de cada hora**.
GitHub puede retrasarlas; deben terminar y desplegarse antes de verse en pantalla. Apify formal está acotado a USD 5
por mes en este programa; otras tareas de la cuenta pueden consumir crédito adicional. Revisar su Billing.

Cada día: revisar última captura, datos publicados, pendientes de sincronización, cantidades disponibles por rol y una
muestra de enlaces. Cada semana: comprobar uso de Supabase/Actions/Apify, cambios en fuentes, calidad de nombres y
notificaciones del responsable. Antes de actualizar: pruebas y respaldo automático confirmado. Ensayar recuperación
según [Operación](OPERACION_Y_RECUPERACION.md); un respaldo previo a migraciones no es un respaldo periódico diario.

Los secretos cumplen funciones distintas: `SUPABASE_URL` identifica el proyecto; `SUPABASE_SECRET_KEY` permite al
programa acceder por API; `SUPABASE_DB_URL` incluye la conexión y contraseña de PostgreSQL para preparación;
`SUPABASE_BACKUP_KEY` cifra los respaldos; `APIFY_TOKEN` permite al refuerzo usar Apify. GitHub oculta los valores
guardados: permite reemplazarlos, no recuperarlos después. No son contraseñas intercambiables. Ver
[instalación automática](INSTALACION_AUTOMATICA.md) y [traspaso](TRASPASO.md) para la configuración inicial.

La persona que recibe el proyecto debe tener sus cuentas y permisos, conocer la conservación del historial y poder
recuperar datos. No necesita instalar programas ni intervenir por cada oferta. Sí necesita un responsable de soporte:
las fuentes externas y los planes gratuitos cambian. El bot WhatsApp, seguimiento individual de postulaciones y
reposiciones continuas son ampliaciones futuras. No forman parte de esta demostración.
