# Historial de cambios relevantes para el cliente

Resumen de decisiones del 5 de noviembre de 2026. No sustituye los PR ni sus pruebas. La documentación de uso vigente
empieza en [GUIA_CLIENTE.md](GUIA_CLIENTE.md); los resultados observados están en [ACEPTACION_Y_ESTADO.md](ACEPTACION_Y_ESTADO.md).

| Revisión | Qué cambió | Consecuencia para el cliente |
|---|---|---|
| Vigencia y demostración — requiere fusión y captura | QA/IA sin cercanos genéricos, reclasificación, vistas privadas SQL 004 y conteos actuales por rol | No confundir 120 históricas con 120 listas; manual de demostración y diagnóstico de solo lectura con evidencia real |
| PR #6 — cobertura/integridad | LATAM y España más remotas mundiales, prioridad remota, rotación de aliases, identidad por enlaces/contenido y reintentos | Colombia no limita cobertura; la cuota se evalúa por rol y la no repetición necesita memoria |
| PR #7 — calidad y Supabase | Contenido que no es oferta, preflight obligatorio, persistencia/reintentos y retirada del Excel automático | Supabase obligatorio; la descarga opcional que existía entonces se retiró en la revisión posterior |
| PR #8 — Apify formal | Actor de ofertas LinkedIn sin cookies, build comprobado, tope USD 5/mes, reservas durables y feed pagado apagado | Apify sí aporta ofertas; conservar presupuesto y revisar gasto de toda la cuenta |
| PR #9 — catálogo y frecuencia | Captura horaria, tres tiempos, lote idempotente recuperable, catálogo/selección privados y despliegue explícito Pages | Aplicar SQL 002/variables si falta; repetir el día no crea otras veinte por rol |
| PR #10 — portales inválidos | Limitar etiqueta DNS Recruitee y aislar errores de un candidato | Un nombre largo o URL inválida no aborta todos los descubrimientos |
| PR #11 — enlaces vigentes | GET acotado, redirecciones, cierres, cobro explícito, título, pendiente ante bloqueo, caché y enlaces compartibles | Las nuevas selecciones requieren evidencia; puede haber déficit; se conservan snapshots y se informa estado actual |
| Revisión documental posterior | Manual del operador, instalación/traspaso actualizados, mantenimiento, recuperación y aceptación con evidencias | El cliente tiene una ruta de operación coherente; las instrucciones históricas quedan identificadas |
| Revisión de producto y mantenimiento | Retirada de exportaciones de hojas de cálculo, guardia de recuperación parcial y trazabilidad de ejecución | Supabase como destino, inconsistencia sin lote detiene selección antes de gastar y riesgos priorizados en el manual |
| Estado operativo duradero — preparado, activación separada | Reservas con bloqueo en Supabase, colas con revisión y recuperación de selecciones interrumpidas | SQL 003 + variable después de corte/importación; guía didáctica y ensayo de cinco tablas/dos secuencias |
| Instalación automática — nueva evolución | Secretos iniciales, respaldo cifrado confirmado antes de SQL, migraciones atómicas con hashes y activación privada | No copiar SQL 002/003 ni activar variables manuales; diario adicional, seis tablas en cortes y ensayo de fallos/restauración |

## Datos y activación

- `supabase/esquema.sql`: tabla/vista histórica v1 y permisos.
- `supabase/migraciones/002_catalogo.sql`: catálogo y registro v2, aditivo y sin borrado histórico.
- Contrato público v3: objeto de verificación en JSON; por sí solo no requiere SQL nuevo.
- SQL 003 es la extensión de estado operativo, independiente de v3. `ESTADO_SUPABASE_ACTIVO=true` solo tras seguir su
  [guía de activación](ACTIVAR_ESTADO_OPERATIVO.md); no se aplicó a producción al desarrollar el código.
- `CAPTURA_HORARIA_ACTIVA=true`: horario y v2 de la nocturna, después del SQL.
- `PAGES_POR_ACTIONS=true`: solo para GitHub Pages por Actions; con Cloudflare se usa su despliegue.
- Con instalación automática confirmada no se requieren las variables de captura/estado anteriores: Preparar Supabase
  aplica e importa desde el corte y deja una marca privada. Requiere configurar una vez `SUPABASE_DB_URL` y
  `SUPABASE_BACKUP_KEY`. Las alternativas manuales se conservan para instalaciones existentes.

Una fusión aprueba código para las próximas ejecuciones; la evidencia de activación es una captura real con ese commit,
su persistencia y su página actualizada. No se restauran ofertas recortadas/fusionadas por versiones antiguas de forma
automática: puede ser necesario volver a obtener información original.

## Decisiones que permanecen

No se usa sesión personal de LinkedIn ni IA diaria. La meta sigue siendo 20 distintas por cada uno de seis roles,
con máximo dos por empresa/rol/día, idiomas de entrega español/inglés y prioridad remota sin inventar elegibilidad.
Se conserva historial para futuras candidaturas; aún no hay clientes, seguimiento individual ni agente WhatsApp.
La auditoría de enlaces no certifica a la empresa, elimina cargos ocultos tras login ni convierte cualquier cargo afín
en una coincidencia perfecta para la persona.
