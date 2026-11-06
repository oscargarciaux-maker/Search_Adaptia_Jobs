# Identidad y entrega única por vacante v5

Por decisión del propietario, una oportunidad en varios portales cuenta una sola vez y `ofertas` pasa a contener
una fila por vacante reconocida. No se rellenan cupos contando enlaces. Se mantienen las columnas v1 y se añaden
`vacante_id` (identificador del catálogo) y `enlaces_alternativos` (JSON con URLs de origen, no todas comprobadas).
`offer_url` continúa siendo el enlace principal comprobado; LinkedIn tiene prioridad cuando está comprobado.

Los registros adicionales antiguos se conservan íntegros en `ofertas_enlaces_historicos`: `oferta_id`, `vacante_id`,
`fila_original` JSON y `archivada_en`. SQL 005 vincula únicamente URLs con identidad inequívoca, archiva las filas
adicionales y conserva la de menor ID. Los vínculos ambiguos no se inventan y se informan como sin identificar.
Un disparador serializa inserciones y evita recrear una segunda fila para la misma identidad, conservando copias
alternativas. Las actualizaciones repetidas no duplican archivo. Los respaldos incluyen la nueva tabla.

La identidad se reconoce por URL compartida o contenido sustancialmente igual con empresa, título, nivel y lugar
compatibles. Se normalizan HTML y diferencias de formato; los títulos iguales sin evidencia de contenido no bastan.
Requisiciones distintas y ubicaciones incompatibles permanecen separadas. Las fusiones conservan todos los enlaces
e identificadores previos. `datos.duplicada_de` señala un registro de catálogo archivado por fusión;
`datos.enlaces_alternativos` conserva los enlaces asociados al registro principal. Los snapshots históricos no cambian.

Las selecciones futuras se deduplican antes de elegir. Se conserva la memoria de IDs fusionados para impedir que
la copia de otro portal se elija de nuevo. Las cantidades históricas seleccionadas no se convierten en evidencia
de veinte oportunidades únicas: el reporte añade cantidad única y déficit real cuando detecta copias en el lote.
La reparación de duplicidad no repone automáticamente vacantes cerradas ni reescribe la selección histórica.

La migración y reconciliación son automáticas después del respaldo; no requieren pegar SQL. Un vínculo desconocido
o una fusión ambigua debe conservarse y revisarse, no eliminarse por compartir título. La auditoría devuelve conteos
y una muestra pública acotada, nunca el contenido completo de la bodega ni credenciales.
