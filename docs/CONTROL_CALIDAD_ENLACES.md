# Control de calidad de enlaces

## Hallazgos reales del 5 de noviembre de 2026

Se revisó por GET el lote completo de 120 vacantes seleccionado ese día, sin modificar Supabase, iniciar sesión,
postular, pagar ni consumir Apify. La revisión y comprobación focalizada de destinos se hizo entre las 11:25 y 11:32,
hora de Colombia. Los resultados son una foto de ese momento, no una certificación permanente:

Los [12 registros que necesitan atención](../reportes/auditoria_enlaces_2026-11-05.md) están identificados por cargo,
empresa, motivo y enlace original, para revisión manual. Este informe no sustituye la base de datos Supabase.

| Resultado por vacante | Cantidad |
|---|---:|
| Al menos un enlace comprobado | 108 |
| Sin confirmación suficiente | 5 |
| Sin enlace utilizable según los controles | 7 |

Los siete rechazos fueron: dos ciclos en la ruta visible de aplicación; una oferta con señal de cierre; un 404; y tres
páginas generales que no mostraban la oferta anunciada. No se detectó un requisito de pago en las páginas recorridas.
Esto no permite descartar cobros ocultos tras iniciar sesión o durante pasos posteriores que no se recorrieron.

Ejemplos observados:

- LinkedIn `4487531992`, «UX Researcher III BRL»: señal explícita de que ya no acepta solicitudes, aunque respondió 200.
- Ashby `truelogic/f55d9115-eaf9-4508-b980-6d1b5e345d65`: HTTP 404.
- Lemon.io `/for-developers/`: página general de inscripción; no correspondía a la ficha «Senior Vue Developer».
- Ofertas de EWOR en Greenhouse: terminaron en el listado de la empresa con `error=true`, sin la ficha anunciada.
- Dos rutas Indeed SmartApply repitieron su destino mediante HTTP 307. Se apartan para compartir; esto no prueba que
  la empresa sea fraudulenta ni que la vacante esté cerrada: puede intervenir la sesión o el cliente del portal.

Las cinco ofertas pendientes requieren revisión porque sus destinos no dejaron comprobar una ficha específica.
Páginas que cargan por JavaScript y rutas de registro pueden ser legítimas. No se etiquetan como fraude ni cierre.

## Controles incorporados

- GET limitado, hasta cinco saltos y un paso visible de aplicación; seguir HTTP y redirecciones HTML estáticas.
  Detectar ciclos, 404/410, cierres en contenido y expiración estructurada. HTTP 200 por sí solo no aprueba una oferta.
- Comparar el título con la ficha o `JobPosting` estructurado. Una portada, buscador o inscripción general no es el
  destino de una oferta específica. Los destinos agregadores/de pago conocidos se rechazan incluso tras redirigir.
- Detectar solicitudes explícitas de pago para postular. Salario, formación paga, Premium opcional y advertencias contra
  estafas no son motivo de rechazo. No se certifica la identidad legal de la empresa ni cada paso de postulación.
- Tratar bloqueos, CAPTCHA, login, timeout y errores temporales como pendientes. No cerrar una vacante por un 403.
- Comprobar los dos enlaces por separado. Si LinkedIn falla y el portal original funciona, compartir solo el original;
  conservar ambos como evidencia histórica. No publicar un enlace malo como alternativa al comprobado.
- Reutilizar comprobaciones positivas seis horas y pendientes treinta minutos, con la hora real de revisión. Limitar
  solicitudes simultáneas, bytes, tiempo y ofertas por corrida. Los pendientes no se aprueban al agotarse el presupuesto.
- Antes de nuevas selecciones, comprobar candidatas y buscar reemplazos cuando fallen. Los refuerzos gratuitos siguen
  operando cuando hay déficit. El presupuesto se comparte entre las rondas: no se multiplican los límites.
- La captura horaria prioriza revisar la selección del día y luego ofertas recientes. No promete revisar las diez mil
  ofertas cada hora. Los límites se ajustan en `datos/config.yaml`, sección `verificacion_enlaces`.
- La página muestra estado/hora y permite filtrar comprobadas. La selección para compartir, WhatsApp manual y exportación
  usan enlaces vigentes; la interfaz deshabilita la selección de pendientes. Los históricos sin metadatos no se certifican.

## Persistencia y puesta en marcha

No requiere SQL nuevo ni otros secretos. La verificación comienza cuando este código se fusiona y una captura ejecuta
la nueva versión. El primer ciclo deja parte del catálogo pendiente mientras revisa por lotes; eso se muestra explícitamente.
La entrega nocturna conserva sus reglas de variedad, países, roles y no repetición; puede quedar bajo meta si no encuentra
suficientes enlaces comprobados. No se rellenan cupos con registros sin revisar.

El estado se conserva en `trabajo/verificacion_enlaces.json` y en `catalogo_vacantes.datos.verificacion`. Los rechazos se
archivan o cierran según la evidencia, sin borrar registros. Un lote ya seleccionado y `ofertas` v1 son históricos y no
se sobrescriben para aparentar que no ocurrió un error. `salud.json.verificacion_enlaces.seleccion_del_dia` informa su
situación actual; la validación diaria advierte si no todos tienen enlace vigente. La captura horaria sigue conservando
el catálogo aunque una selección anterior se haya cerrado después.

El futuro WhatsApp deberá consultar el catálogo y sus comprobaciones vigentes antes de cada envío. No basta con leer
`ofertas.status=active`: ese campo forma parte del snapshot histórico. La comprobación para piloto ahora exige también
que todos los elementos de la selección actual tengan un enlace comprobado.
Los siete días de evidencia deben incluir selecciones comprobadas al seleccionar; los días antiguos sin ese dato no
se dan por verificados retroactivamente.

## Auditoría manual reproducible

Sobre una copia local del lote de `publicado`, sin escrituras remotas:

```bash
python -m buscador.verificar_enlaces --lote salida/trabajo/lote_entrega.json --salida /tmp/auditoria.json --maximo 120
```

El JSON contiene motivo, hora, estado HTTP y ruta de cada enlace. Puede incluir parámetros de seguimiento del portal;
no se muestra completo en la interfaz. Revisar manualmente una muestra de los seis roles y cualquier pendiente antes de
enviar a clientes. Abrir una oferta comprobada días después puede producir un resultado distinto.

Contrato público compatible: [CONTRATO_DATOS_v3.md](CONTRATO_DATOS_v3.md). La estructura SQL permanece en v2 y
`ofertas` conserva v1. Las utilidades offline antiguas siguen siendo compatibles; el flujo de producción aplica el control.
