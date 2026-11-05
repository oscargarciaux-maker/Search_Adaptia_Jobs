# Search Adaptia Jobs — scraper de vacantes LATAM y España

Busca y clasifica ofertas para LATAM, España y remotas mundiales, con cargos exactos, similares y cercanos. Cada noche
intenta seleccionar **20 nuevas por cada uno de seis roles** (Product Designer, UX/UI Designer, Product Owner, Product
Manager, AI Engineer y QA), variadas y sin repetir, en **Supabase**. La captura horaria gratuita actualiza el catálogo
sin crear otra entrega. Se comprueban enlaces antes de nuevas selecciones; cierres, páginas generales y cobros detectados
se apartan y lo que no puede comprobarse queda pendiente. La cobertura/volumen no se garantizan por completo.

La página permite buscar dentro de la ventana activa de 30 días, elegir ofertas comprobadas y copiar para WhatsApp
para compartir por WhatsApp manualmente. Supabase es el destino de las vacantes; se retiró la exportación a hojas de
cálculo. La búsqueda diaria no usa IA ni sesión personal de LinkedIn. Todavía no hay agente
WhatsApp ni seguimiento individual de candidaturas.

## Documentación de entrega

| Para quién / tarea | Documento vigente |
|---|---|
| Operador y cliente: aprender a usar e interpretar resultados | [Manual del cliente](docs/GUIA_CLIENTE.md) |
| Administrador: instalar o actualizar sin perder datos | [Instalación](docs/INSTALACION.md) |
| Configurar una vez y aplicar SQL/activación automáticamente | [Instalación automática](docs/INSTALACION_AUTOMATICA.md) |
| Cambiar propietario/cuentas conservando historial y presupuesto | [Traspaso](docs/TRASPASO.md) |
| Operar, resolver incidentes, respaldar y restaurar | [Operación y recuperación](docs/OPERACION_Y_RECUPERACION.md) |
| Decidir qué está comprobado y qué falta antes de aceptar/automatizar | [Aceptación y estado](docs/ACEPTACION_Y_ESTADO.md) |
| Entender lo que cambió en las revisiones | [Historial de cambios](docs/HISTORIAL_CAMBIOS.md) |
| Priorizar riesgos de producto, arquitectura, operación e IA | [Revisión de fiabilidad](docs/REVISION_FIABILIDAD.md) |
| Aprender GitHub/Supabase y activar reservas/pendientes duraderos | [Estado operativo y activación](docs/ACTIVAR_ESTADO_OPERATIVO.md) |

Los manuales anteriores prevalecen para uso/instalación. `docs/PLAN.md` conserva el diseño histórico; sus costos,
casillas y actores originales no describen por sí solos la operación vigente.

Referencias técnicas y antecedentes:

- Revisión de alternativas y mejoras: [`docs/REVISION_PRODUCTO.md`](docs/REVISION_PRODUCTO.md)
- Activar captura horaria y catálogo Supabase: [`docs/ACTIVAR_CAPTURA_HORARIA.md`](docs/ACTIVAR_CAPTURA_HORARIA.md)
- Integridad de enlaces y resultados de auditoría: [`docs/CONTROL_CALIDAD_ENLACES.md`](docs/CONTROL_CALIDAD_ENLACES.md)
- Contratos: [v1 histórico](docs/CONTRATO_DATOS_v1.md), [catálogo v2](docs/CONTRATO_DATOS_v2.md),
  [verificación pública v3](docs/CONTRATO_DATOS_v3.md) · Reglas para desarrollo: [CLAUDE.md](CLAUDE.md)

## Cobertura y conservación

Prioriza remotas para varios países, con cobertura de LATAM, España y remotas mundiales. Los títulos exactos,
similares y cercanos rotan en las búsquedas; no se promete agotar todas las combinaciones cada noche.
La limpieza de 30 días solo afecta al buscador activo; no borra ofertas de Supabase. Apify busca fichas formales de
LinkedIn con un tope de USD 5/mes; las publicaciones solo aportan una oferta si se verifica
su ficha original. La búsqueda pagada del feed está desactivada para reservar el crédito a fichas formales.
La meta es 20 por cada uno de seis roles (120 al día). Si un rol queda corto, hay búsquedas adicionales gratuitas
acotadas y un reporte de los motivos. La continuidad se mide entre días distintos, conservando la memoria de entregas.
Decisiones, límites y seguimiento futuro: [`docs/COBERTURA_HISTORICO.md`](docs/COBERTURA_HISTORICO.md).

El catálogo v2 permite actualizar durante el día sin crear otra entrega diaria. Conserva publicación, detección y
última observación por separado y archiva sin borrar historial en Supabase. El instalador aplica las migraciones y activa
catálogo/estado central tras respaldar e importar el corte. Requiere configurar una vez conexión administrativa y clave
de cifrado como Secrets. La alternativa manual conserva variables anteriores. La activación se acredita por la ejecución,
no solo por la fusión. Repetir una entrega completa reintenta el mismo lote; las cachés siguen en GitHub.
WhatsApp sigue pendiente de validar continuidad y definir destinatarios/confirmaciones; no hay envíos automáticos.
La programación solicita 1:17 a. m. Colombia para la nocturna y minuto 23 de cada hora para la captura; GitHub puede
retrasar/saltar ejecuciones. El límite de USD 5 es Apify, no un precio total garantizado de todos los proveedores.

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q
node --test pruebas/*.test.js
python -m buscador.bodega --salida /tmp/prueba --prueba   # prueba en vivo de unos 5 minutos
```
