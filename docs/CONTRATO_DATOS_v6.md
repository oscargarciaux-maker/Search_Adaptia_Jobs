# Control por cargo y cliente — v6

El operador administra clientes, cargos, filtros y cupos desde una interfaz privada. El presupuesto diario se asigna
por cargo y suma 120 oportunidades distintas; varios clientes pueden recibir la misma oportunidad del cupo de su cargo
si cumplen sus filtros. Compartirla con tres clientes no la convierte en tres oportunidades del presupuesto.

La configuración tiene clientes (id, nombre, activo), cargos (id, nombre, cupo, activo, terminos_exactos,
terminos_similares, terminos_excluidos) y perfiles (id, cliente_id, cargo_id, activo, paises, modalidad,
antiguedad_dias, idiomas, ingles_maximo, experiencia_min, experiencia_max, aceptar_experiencia_sin_dato,
aceptar_ingles_sin_dato). El rango corresponde a los años mínimos exigidos por la vacante, no a una evaluación de un CV.
Idioma del aviso e inglés requerido son filtros diferentes.

Guardar conserva un borrador con control de revisión. Publicar para la siguiente búsqueda crea una versión inmutable
vigente desde el día siguiente en Colombia; no cambia el criterio de una corrida ya iniciada. No se publica si los
cupos activos no suman 120 o hay cargos con cupo sin perfiles activos. Archivar conserva el historial.

SQL 009 añade panel_configuracion, panel_versiones, panel_ejecuciones y panel_asignaciones. Solo service_role
accede: el servidor autentica y autoriza al operador. No hay claves administrativas en el navegador. Sin configurar
autenticación, el servidor real permanece cerrado; la demostración usa exclusivamente datos ficticios separados.
Los respaldos incluyen las once tablas y las dos secuencias existentes; no incluyen usuarios Auth del proveedor.

Las asignaciones conservan cliente/perfil/cargo, vacante canónica, grado, filtros, cargo_configuracion y explicación. Los grados exact,
similar y close describen afinidad del cargo, no compatibilidad de un candidato ni probabilidad de contratación.
Las comprobaciones de país, fecha, idioma, experiencia, inglés y enlace son independientes y explicables. No se
comparten pendientes, rechazadas, cerradas ni comprobaciones caducadas. Un déficit se muestra sin relajar filtros.

La captura consulta únicamente los cargos y lugares de la versión activa. La expansión usa normalización, variantes,
vocabulario ocupacional público ESCO cuando está disponible y términos editables; no requiere IA ni un banco cerrado.
La ausencia de equivalentes fiables se señala y permite añadirlos desde la interfaz. No se inventan sinónimos.

El botón WhatsApp copia título y URL comprobada de oportunidades utilizables al portapapeles. No envía mensajes,
no confirma postulaciones ni afirma que una copia se haya enviado. Los clientes no acceden a la interfaz en esta etapa.
Los contratos v1–v5, sus snapshots y la captura heredada se conservan hasta que exista una versión de control vigente.

Dentro de un mismo grado y prioridad remota, la selección favorece clientes menos cubiertos y diversifica el cupo.
No hay mínimo garantizado por persona; filtros estrechos o ausencia de oferta pueden dejar un cliente sin resultados.
La captura horaria actualiza disponibilidad pero no crea una segunda entrega diaria. El motor no guarda los perfiles
en su estado público. Los cargos dinámicos usan role_id cargo:<UUID>; las vistas históricas de roles fijos no sustituyen
las comprobaciones del panel. Una vacante con varios perfiles del mismo cliente se comparte una sola vez si alguno
sigue siendo compatible; todas sus asignaciones originales se conservan.
