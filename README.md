# Adaptia Jobs — control de búsquedas por cliente

El operador gestiona clientes, perfiles, cargos y cupos desde una interfaz. Define país, modalidad, idioma del aviso,
plazo de publicación, años de experiencia exigidos e inglés requerido. El objetivo diario es **120 oportunidades
únicas distribuidas por cargo**: varios clientes compatibles pueden aprovechar el mismo cupo sin contar copias.

Guardar conserva un borrador. **Programar para mañana** fija una versión para el día siguiente en Colombia. El scraper
consulta esos cargos y lugares; cada cliente ve su subconjunto compatible. Los enlaces caducados o retirados no se
copian. El botón **Copiar WhatsApp** prepara un mensaje en el portapapeles; el operador decide cuándo enviarlo.

La búsqueda, los filtros y la afinidad funcionan con código, sin IA. Se pueden añadir cargos nuevos y revisar sus
variantes/términos afines sugeridos mediante reglas y vocabulario público ESCO; no hay que editar un banco cerrado.
La expansión puede necesitar corrección del operador. No se promete inferir todos los sinónimos de cualquier profesión.

**Estado de esta revisión:** plataforma implementada y ensayada con datos ficticios; acceso real cerrado por defecto.
El propietario decidió configurar el inicio de sesión más adelante. La demostración no modifica Supabase, no programa
capturas reales y no consume Apify. El despliegue privado y la primera corrida dirigida real aún deben acreditarse.
Hasta existir una versión de control vigente en Supabase, continúa la selección heredada de seis cargos por veinte.
No se recupera la web histórica de Pages/Cloudflare: este panel tiene servidor privado y nueva finalidad autorizada.

## Ejecutar la demostración

Requiere Python 3.12 y Node 24. Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
python -m panel.api --demo --port 8000
```

Abrir http://localhost:8000. Los cambios ficticios persisten en /tmp/adaptia-panel-demo/config.json; se pueden borrar
con el servidor detenido para reiniciar la demostración. **No usar --demo con datos reales.**
Instalación privada, Docker, configuración y guía detallada: [Panel de control](docs/PANEL_CONTROL.md).

## Documentación de entrega

| Para quién / tarea | Documento vigente |
|---|---|
| Operador: clientes, filtros, cupos y vacantes | [Manual del cliente](docs/GUIA_CLIENTE.md) |
| Administrador: instalar o actualizar sin perder datos | [Instalación](docs/INSTALACION.md) |
| Configurar una vez y aplicar SQL/activación automáticamente | [Instalación automática](docs/INSTALACION_AUTOMATICA.md) |
| **Entregar al cliente: pruebas manuales, traspaso a su Supabase y primera semana** | [Entrega al cliente](docs/ENTREGA_AL_CLIENTE.md) |
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
  [verificación v3](docs/CONTRATO_DATOS_v3.md), [consulta v4](docs/CONTRATO_DATOS_v4.md),
  [identidad y entrega única v5](docs/CONTRATO_DATOS_v5.md), [control privado v6](docs/CONTRATO_DATOS_v6.md) · Reglas para desarrollo: [CLAUDE.md](CLAUDE.md)

## Cobertura y conservación

Prioriza remotas para varios países, con cobertura de LATAM, España y remotas mundiales. Los títulos exactos,
similares y cercanos rotan en las búsquedas; no se promete agotar todas las combinaciones cada noche.
La limpieza de 30 días solo afecta al buscador activo; no borra ofertas de Supabase. Apify busca fichas formales de
LinkedIn con un tope de USD 5/mes; las publicaciones solo aportan una oferta si se verifica
su ficha original. La búsqueda pagada del feed está desactivada para reservar el crédito a fichas formales.
Con el panel activo, los cupos configurados suman 120; antes se mantienen seis roles por veinte. Si un rol queda corto, hay búsquedas adicionales gratuitas
acotadas y un reporte de los motivos. La continuidad se mide entre días distintos, conservando la memoria de entregas. El panel muestra faltantes sin relajar filtros.
Decisiones, límites y seguimiento futuro: [`docs/COBERTURA_HISTORICO.md`](docs/COBERTURA_HISTORICO.md).

El catálogo v2 permite actualizar durante el día sin crear otra entrega diaria. Conserva publicación, detección y
última observación por separado y archiva sin borrar historial en Supabase. El instalador aplica las migraciones y activa
catálogo/estado central tras respaldar e importar el corte. Requiere configurar una vez conexión administrativa y clave
de cifrado como Secrets. La alternativa manual conserva variables anteriores. La activación se acredita por la ejecución,
no solo por la fusión. Repetir una entrega completa reintenta el mismo lote; las cachés siguen en GitHub.
La copia manual de WhatsApp está en el panel; el agente y los envíos automáticos siguen fuera del alcance.
La programación solicita 1:17 a. m. Colombia para la nocturna y minuto 23 de cada hora para la captura; GitHub puede
retrasar/saltar ejecuciones. El límite de USD 5 es Apify, no un precio total garantizado de todos los proveedores.

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q
npm --prefix web run build
npm --prefix web test   # requiere Chromium: cd web && npx playwright install chromium
python -m buscador.bodega --salida /tmp/prueba --prueba   # prueba en vivo de unos 5 minutos
```
