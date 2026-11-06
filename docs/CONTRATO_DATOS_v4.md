# Consulta operativa v4: selección e información vigente

Extensión aditiva. No cambia columnas, estados ni snapshots de `ofertas` v1 o `entregas_diarias`.
La selección histórica cuenta lo elegido; la disponibilidad cuenta lo utilizable en este momento.

`catalogo_vacantes.datos.rol_entrega_actual` es el ID del rol diario que corresponde al mapa vigente, o cadena vacía
si no corresponde a los seis roles. Se recalcula al capturar, también para vacantes anteriores. No modifica el rol
histórico. Los cargos genéricos de desarrollo no deben contar como QA ni como ingeniería de IA por mera cercanía.
Se conservan variantes pertinentes y los grados del mapa; se prefiere afinidad antes de alcance remoto y diversidad.

SQL 004 añade vistas privadas `seleccion_estado_actual` y `resumen_entregas_actual`. La primera une cada selección
con su catálogo actual y expone fecha, rol, grado histórico, título, empresa, estado del catálogo, afinidad vigente,
comprobación, enlace utilizable y `estado_actual`: `lista`, `closed`, `archived`, `fuera_de_perfil`,
`afinidad_por_confirmar` o `por_verificar`. Solo `lista` es apta para compartir: catálogo activo, rol confirmado y
un enlace de esa ficha verificado hace menos de seis horas, sin fecha futura. Sin evidencia no se presume validez.
La segunda agrupa estos estados por fecha/rol. Las vistas usan permisos del invocador, sin acceso anónimo.
El resumen no inventa roles ausentes ni sustituye la meta configurada de veinte. No se reescribe un lote para
rellenar cierres posteriores; un déficit se informa y requiere nuevas oportunidades, no duplicados.

`salud.json.seleccion_actual` contiene fecha y roles (ID, nombre, meta y `vacantes`); cada entrada de vacante incluye
solo ID, `catalog_status` (`active`, `closed`, `archived`, `sin_catalogo`), afinidad vigente, enlaces públicos y
verificación pública, sin descripción ni snapshot privado. Un cierre/archivo del catálogo impide contar una oferta
lista aunque aún quede un enlace positivo en caché. La página calcula cantidades
vigentes con la hora del navegador; un dato caducado deja de contar aunque no haya nueva captura. La ausencia del
campo en datos antiguos se indica y no se convierte en un conteo de disponibles.

El diagnóstico de producto es manual y de solo lectura: conteos por rol/fecha, títulos públicos de QA y consulta
de una URL pública. No aplica migraciones ni consulta fuentes ni consume Apify. Errores privados no se imprimen.
