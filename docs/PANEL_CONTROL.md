# Panel de control — uso, arquitectura e instalación

Revisión v6, preparada el 6 de noviembre de 2026. Este es un manual operativo y técnico, no un documento comercial.
El propietario solicitó una interfaz nueva para dirigir la búsqueda por clientes. Reemplaza la decisión anterior de
operar únicamente desde Supabase; la antigua web de Pages/Cloudflare continúa retirada.

## Estado y alcance

La demostración funciona con datos ficticios. Se han probado interfaz, API, filtros y persistencia en PostgreSQL aislado.
**El inicio de sesión y el despliegue privado real se configurarán más adelante**, por decisión del propietario.
No se han creado usuarios, invitado personas ni enviado WhatsApp. La demostración no utiliza la base real.
Fusionar código no acredita una primera corrida dirigida real: falta configurar el servidor, habilitar al operador,
programar sus criterios y comprobar la captura siguiente. La captura heredada sigue funcionando mientras no exista
una versión de panel vigente. SQL 008 repara la reconciliación por timeout y SQL 009 instala las tablas privadas.
Ambas se aplican por el instalador automático tras el respaldo; no hace falta copiar SQL al editor.

## 1. Cómo preparar la búsqueda del siguiente día

1. Abrir **Cargos y cupos**. Añadir los cargos necesarios y repartir 120 vacantes diarias entre ellos. Por ejemplo,
   Product Designer 50, Frontend 40 y QA 30. Se permite un borrador inferior a 120; solo se programa al completar 120.
2. En cada cargo, revisar sus denominaciones principales, afines y exclusiones. **Buscar denominaciones afines** ofrece
   variantes y vocabulario disponible. Al guardar un cargo nuevo sin términos, primero se muestran sugerencias para
   revisarlas; después se confirma. Se puede escribir cualquier cargo y añadir términos sin modificar código.
3. En **Clientes → Nuevo cliente**, usar un nombre o referencia interna. No se necesita teléfono ni contraseña del cliente.
4. Añadir uno o más perfiles y elegir el cargo, los países desde los que puede trabajar, modalidad, plazo de publicación,
   idioma del aviso, experiencia e inglés. Un cliente puede tener varios perfiles.
   Debajo de cada perfil aparece una **estimación**: cuántas vacantes ya guardadas y aún no entregadas cumplirían hoy
   ese perfil, y qué ajuste sumaría más (con «Aplicar» para admitir datos no informados). En **Cargos y cupos** cada
   cargo muestra «alcanza para el cupo», «puede quedar corto» o «probable faltante». Usa las mismas reglas de la
   selección, no busca en internet ni guarda nada; un cargo nuevo empieza bajo porque todavía no se ha buscado.
5. **Guardar borrador** conserva los cambios; todavía no cambia la búsqueda confirmada. Una advertencia muestra cambios
   sin guardar. Si otra ventana guardó antes, se rechaza la revisión antigua: recargar y revisar antes de guardar otra vez.
6. **Programar para mañana** muestra la distribución, guarda los cambios pendientes y confirma una versión inmutable.
   Entra en vigor al día siguiente según Bogotá. Se exige un perfil activo por cada cargo con cupo positivo.
7. En **Actividad**, comprobar la captura y sus faltantes. No se inventan vacantes ni se completan cupos con duplicados,
   ubicaciones ajenas o enlaces pendientes. Si las fuentes no ofrecen suficientes resultados, se indica el déficit.

Archivar un cliente o cargo lo retira de la siguiente configuración que se programe. Conserva versiones, asignaciones
y resultados anteriores. Se puede reactivar desde el listado archivado. Archivar un cargo obliga a redistribuir su cupo.
Editar un borrador no modifica una versión ya confirmada ni los criterios de la corrida que comenzó.

## 2. Qué significan los filtros

| Campo | Regla aplicada |
|---|---|
| Cargo | Términos principales/afines, exclusiones y coincidencia textual; ver explicación por resultado |
| Países | Elegibilidad positiva para alguno de esos países dentro de LATAM/España; país desconocido no cuenta |
| Modalidad | Remoto, híbrido, presencial o cualquiera; remoto extranjero restringido no pasa por ser remoto |
| Publicación | Edad de la fecha real de publicación, entre 1 y 30 días configurables; fecha desconocida/estimada no pasa |
| Idioma del aviso | Español, inglés o ambos; es distinto del nivel de inglés solicitado |
| Experiencia | Años mínimos exigidos por la vacante dentro del rango configurado; vacío significa sin ese límite |
| Inglés requerido | Hasta el nivel del cliente; se rechaza un nivel obligatorio superior, no uno solamente deseable |
| Datos no informados | Si se filtra experiencia/inglés, solo se admiten sin evidencia si se marca expresamente la opción |

El filtro de experiencia no evalúa un CV ni certifica seniority. La clasificación del inglés depende de lo que diga
el anuncio; no todos publican niveles CEFR. Un filtro estricto puede dejar pocos resultados. El plazo usa publicación,
no primera detección: encontrada hoy no significa publicada hoy. Todas las fuentes tienen límites de acceso y cobertura.

Entre resultados pertinentes se priorizan remotos. Dentro del mismo grado y prioridad remota, se favorece a los
clientes menos cubiertos y se diversifican empresas, idiomas y fuentes. No existe un mínimo individual garantizado.
Una vacante válida para tres clientes cuenta una sola vez en el cupo del cargo; cada cliente puede ver un subconjunto
diferente. Las 120 son oportunidades distintas, no 120 por persona ni una suma de enlaces repetidos.

## 3. Cómo revisar y compartir

En **Vacantes**, escoger cliente y fecha de captura. Los perfiles nuevos empiezan a recibir resultados cuando se ejecute
su versión programada; editar sus filtros no vuelve a generar resultados históricos. **Por qué coincide** muestra términos
 y reglas aplicadas. Exacta/afín describe el cargo, no una probabilidad personal de contratación.

- **Verificada:** catálogo activo, criterios vigentes y al menos un enlace de esa ficha comprobado hace menos de seis horas.
- **Por confirmar:** falta evidencia vigente o ya no cumple los criterios; no se incluye en el mensaje.
- **Retirada:** el catálogo registra la oferta cerrada o archivada; se conserva para consulta histórica.

**Actualizar estado** relee la base y vuelve a contrastar los filtros. No lanza un scraper ni evita CAPTCHA; la captura
horaria renueva evidencias dentro de su presupuesto. **Copiar WhatsApp** vuelve a consultar el catálogo, prepara el saludo
 y la lista de títulos/enlaces utilizables, permite previsualizar y copia al portapapeles. No envía ni registra un envío.
Si el navegador bloquea el portapapeles, se puede seleccionar el texto y copiarlo manualmente. Una oferta compatible
con varios perfiles del mismo cliente aparece una sola vez cuando alguno sigue cumpliendo sus filtros.

Un enlace puede cerrar después de comprobarse. No se promete disponibilidad eterna, autenticidad absoluta de empresas,
ni acceso tras autenticarse en un portal. La evidencia caduca; las comprobaciones pendientes nunca se anuncian válidas.
El historial puede seguir sumando 120 mientras algunas oportunidades ya no están listas para compartir.

## 4. Qué hace cada componente

| Componente | Función |
|---|---|
| web/src | Interfaz React/TypeScript, formularios, resultados, actividad y portapapeles; sin claves administrativas |
| panel/api.py | Servidor FastAPI, acceso privado, validación, endpoints y archivos compilados de la interfaz |
| panel/modelos.py | Reglas de configuración y límites: referencias, países, rangos, cupos y publicación |
| panel/terminos.py | Variantes ortográficas, términos editables y consulta opcional al vocabulario público ESCO |
| panel/afinidad.py | Comprobaciones explicables de país, modo, publicación, idioma, experiencia e inglés |
| panel/servicio.py | Resultados según catálogo actual, texto WhatsApp y estimación previa por perfil/cargo; excluye enlaces/criterios vencidos |
| panel/repositorio.py | Lectura/escritura Supabase; repositorio ficticio separado exclusivamente para demo |
| panel/ejecutor.py | Carga la versión diaria, prepara búsquedas dirigidas, ejecuta el motor y asigna por perfil |
| buscador | Fuentes, extracción, identidad, comprobación de enlaces, presupuesto y sincronización |
| .github/workflows | Nocturna, captura horaria, pruebas, instalación y diagnóstico |
| supabase/migraciones | Evoluciones SQL registradas por hash, sin editar las ya instaladas |

No hace falta IA para ejecutar. Para cargos conocidos se aprovecha el vocabulario existente; para otros se consulta
ESCO si está disponible y hay una correspondencia fiable. Solo se envía el nombre del cargo, nunca los clientes/perfiles.
Si no hay equivalentes fiables se señala y el operador añade términos desde la interfaz. No existe una forma puramente
algorítmica de garantizar todos los títulos afines de cualquier profesión sin vocabulario o revisión humana.

## 5. Tablas privadas nuevas y relación con las anteriores

| Tabla | Qué guarda y por qué |
|---|---|
| panel_configuracion | Un borrador y su número de revisión; permite editar sin cambiar búsquedas ya confirmadas |
| panel_versiones | Copias inmutables de configuraciones confirmadas y su día de entrada en vigor |
| panel_ejecuciones | Una ejecución por fecha, versión utilizada, estado, cantidades y faltantes |
| panel_asignaciones | Vínculo vacante canónica–cliente–perfil, grado, explicación y copia de filtros/cargo utilizados |
| catalogo_vacantes | Contenido y disponibilidad actuales; las asignaciones apuntan aquí para comprobar vigencia |
| entregas_diarias | Selección histórica por cargo/día; evita duplicar entregas al reintentar |
| ofertas / ofertas_enlaces_historicos | Compatibilidad del contrato histórico y archivo íntegro de enlaces fusionados |
| estado_operativo / apify_reservas | Recuperación y presupuesto duradero; no son vacantes para compartir |
| adaptia_migraciones | Versiones SQL instaladas y hashes; lo administra el instalador |

Los identificadores UUID enlazan entidades sin depender del nombre. role_id de un cargo nuevo usa cargo:<UUID>.
Las vistas heredadas de seis cargos no evalúan todos los filtros privados; para v6 se utiliza el panel.
Los nombres/perfiles no se escriben en la rama de reportes del scraper. Esta revisión no borra historial de vacantes.
Los respaldos automáticos incluyen once tablas y dos secuencias; Auth/Storage del proveedor se recuperan por separado.

## 6. Ejecutar en demostración

Desde la raíz, con Python 3.12 y Node 24:

```bash
pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
python -m panel.api --demo --port 8000
```

Abrir http://localhost:8000. Es una muestra de cinco clientes ficticios con cupos 50/40/30. Los cambios persisten en
/tmp/adaptia-panel-demo/config.json y los resultados simulados representan una captura anterior independiente del borrador.
PANEL_DEMO_FILE permite escoger otro archivo ficticio. No introducir clientes reales en este modo sin autenticación.
No se requiere ninguna contraseña, API key ni gasto para explorar la demo. En desarrollo se puede usar npm --prefix web
run dev con API en el puerto 8000; para revisar el producto completo basta el servidor anterior.

## 7. Instalación privada posterior — administrador, una sola vez

Esta sección queda **pendiente** hasta que el propietario configure el login y elija alojamiento. No es una tarea
que deba repetirse por cada cliente ni al cambiar criterios. No se eligió ni contrató un proveedor de alojamiento.

1. Fusionar la revisión aprobada. Comprobar Preparar Supabase: instala 008/009 de forma automática tras respaldo cifrado.
2. Elegir un servidor o alojamiento de contenedores con HTTPS, almacenamiento de secretos y soporte para un proceso Python.
   GitHub Pages no ejecuta este backend privado. Un dominio/origen HTTPS debe dirigir tráfico al puerto interno 8000.
3. Crear más adelante el usuario del operador en Supabase Auth y confirmar su correo. No habilitar registro público.
   Si requiere invitación o correo, el propietario decide y la realiza; esta revisión no envía invitaciones.
4. Guardar en el alojamiento SUPABASE_URL, SUPABASE_SECRET_KEY, PANEL_ORIGIN y PANEL_OPERATOR_EMAILS. El ejemplo sin valores
   está en panel/.env.example. PANEL_ORIGIN es el origen HTTPS exacto; PANEL_OPERATOR_EMAILS es el correo autorizado.
   La clave de servicio solo está en el servidor. No se necesita contraseña PostgreSQL ni token Apify en el servidor web.
5. Compilar/ejecutar con Docker o el procedimiento Python/Node anterior, **sin --demo**. El servidor rechaza arrancar sin
   origen HTTPS y operador autorizado. La API verifica la sesión y el correo confirmado antes de devolver datos.
6. Probar rechazo sin sesión, acceso del operador, guardado/recarga y programación de una versión. Comprobar que secretos
   no aparezcan en archivos del navegador ni en respuestas. Verificar exclusión de otros usuarios.
7. Revisar la captura del siguiente día y sus asignaciones. Confirmar presupuesto, filtros, identidad y enlaces con una
   muestra real por cargo. Solo entonces acreditar operación dirigida en producción.

```bash
docker build -t adaptia-control .
# Archivo de variables privado fuera del repositorio, con valores propios del alojamiento.
docker run --env-file /ruta/privada/panel.env -p 127.0.0.1:8000:8000 adaptia-control
# Demostración local con la misma imagen, sin credenciales:
docker run --rm -p 127.0.0.1:8000:8000 adaptia-control python -m panel.api --demo --host 0.0.0.0 --port 8000
```

La imagen corre como usuario sin privilegios. Los proxy CA montados como secretos de compilación son opcionales para
entornos administrados; no se incluyen en capas. Las sesiones usan cookie HttpOnly/Secure/SameSite Strict y se comprueban
contra Supabase; no se almacena la clave administrativa en el navegador. Cada API protegida verifica el acceso real.
El alojamiento debe conservar HTTPS y el origen correcto; no abrir CORS global ni desactivar autorización para probar.

## 8. Automatización, costes y límites operativos

La nocturna solicita 1:17 a. m. Colombia; la captura gratuita solicita minuto 23 de cada hora. GitHub puede retrasar o
omitir horarios. La horaria actualiza catálogo y asignaciones existentes, sin generar otras 120. Los reintentos conservan
la versión diaria y no multiplican asignaciones. El historial de actividad distingue completa, parcial y fallida.
Las fuentes públicas pueden devolver resultados más amplios que los filtros; la admisión final es estricta.

Se consultan cargos y lugares activos; no todas las familias históricas. Los portales de empresas se limitan a empresas
asociadas a cargos pertinentes; si aún no se conocen se descubren progresivamente, no se rastrean todos por defecto.
El crédito Apify sigue limitado a USD 5/mes del proyecto y dedicado a fichas LinkedIn, con feed de posts desactivado.
La horaria y las pruebas no consumen Apify. Hosting, GitHub, Supabase y otros servicios tienen sus propios límites/costes.

Pruebas automáticas: pytest, migraciones PostgreSQL aisladas, restauración de once tablas, concurrencia de configuración,
compilación TypeScript/Vite y Playwright con Chromium para CRUD, cuotas, programación, WhatsApp y pantalla móvil.
Un test verde no demuestra 120 resultados reales ni una semana de continuidad. Mantener alertas y revisar las capturas.
