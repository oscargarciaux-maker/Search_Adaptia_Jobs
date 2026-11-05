# Calidad de ofertas, Supabase y primera corrida

Actualización posterior al PR #6, a partir de las aclaraciones de Oscar. Supabase es obligatorio para la entrega normal;
el Excel era parte de la versión anterior y ya no se genera automáticamente. Se conservan históricos y una utilidad de
exportación opcional, que no sustituyen la base.

## Vacantes e indicios de contratación

Apify es un proveedor, no una certificación de que el contenido sea una vacante. El actor del feed puede traer consejos,
autopromoción o búsquedas de trabajo. Las reglas anteriores de palabras («contratando», cargo, empresa, país) no eran
suficientes para garantizarlo. Ahora sus coincidencias quedan pendientes de revisión: no completan la cuota ni se
insertan en Supabase. Estado muestra un conteo y hasta diez enlaces para revisión, sin afirmar que sean ofertas aprobadas.
Todavía no existe un flujo de aprobación que convierta esas publicaciones en ofertas automáticamente.

Las publicaciones antiguas sin enlace formal se retiran del catálogo activo, sin borrar filas históricas de Supabase.
Los avisos formales siguen procediendo de fichas LinkedIn/Indeed y APIs de portales o ATS. Se rechazan títulos de cursos,
webinars o búsqueda personal de empleo, enlaces sin HTTP/HTTPS y enlaces LinkedIn que no sean fichas de empleo.
Apify de ofertas no admite posts del feed como fichas ni inventa un enlace de empleo a partir de un post.

Estos controles reducen falsos positivos; no certifican autenticidad de cada empresa, ausencia de fraude ni vigencia de
cada aviso en este instante. No se promete precisión absoluta a partir de coincidencias de texto.

## Controles de arranque y recuperación

1. Antes de recoger, una entrega normal exige credenciales secretas y lectura de todas las columnas del contrato en
   Supabase. Rechaza claves públicas y formatos ajenos a una clave secreta/service_role. `--prueba` no exige secretos.
2. Una corrida sin catálogo válido no reemplaza el estado anterior. Las escrituras JSON usan reemplazo atómico para
   evitar truncar un archivo válido si la escritura se interrumpe.
3. Los envíos aceptados se confirman por lote; las filas fallidas siguen en la cola. La lectura previa no demuestra permiso
   de INSERT: la escritura queda comprobada al aceptar la carga real, sin crear ofertas ficticias para probarlo.
4. Se conserva el estado y la cola en la rama publicada para reintentos. Actions guarda además un artefacto de recuperación
   durante 14 días. La recuperación desde ese artefacto es manual si falla la publicación, no automática. No sustituye
   copias de seguridad permanentes de Supabase.
5. Después de conservar el estado, la validación final marca la corrida como fallida si la meta queda incompleta, hay
   errores/pendientes o no se confirma la sincronización. Se puede conservar una entrega parcial con su reporte; no se
   presenta como una cuota cumplida. El artefacto de estado tampoco afirma que se sincronizaron todas las ofertas.

`Actions → Diagnóstico → solo_supabase: true` comprueba únicamente conexión y columnas, sin insertar nada. Las pruebas
simulan claves faltantes, respuestas malformadas, publicaciones falsas, escrituras interrumpidas y sincronización parcial.

Este cambio no aplica migraciones ni ejecuta una entrega productiva. Ningún test garantiza cero fallos futuros de red o
proveedores. Los controles permiten detectarlos y recuperarlos sin ocultarlos ni sustituir Supabase por un Excel.
