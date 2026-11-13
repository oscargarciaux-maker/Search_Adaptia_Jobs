# Ajustes del operador y alertas por correo — v10

Revisión del 12 de noviembre de 2026. Añade las tablas privadas `panel_ajustes` (SQL 012), `panel_contactos` y `panel_borradores` (SQL 013). No cambia el catálogo, las
ofertas ni la configuración versionada.

## Tabla `panel_ajustes`

Clave/valor jsonb, solo para `service_role` (RLS activa, sin acceso anónimo ni autenticado). Se incluye en los cortes,
respaldos y el traspaso. Fuera de la configuración versionada: un cambio se aplica al momento y no se copia en cada
versión programada.

| Clave | Valor | Quién escribe |
|---|---|---|
| `alertas` | `{"destinatarios": [correos, máx. 5], "tipos": ["exito", "pocas_vacantes", "fallo"]}` | Panel («Avisos por correo») |
| `alertas_estado` | `{"fallos_horarios_seguidos": n}` | `buscador/alertas.py` |

## Cuándo se envía cada alerta

| Tipo | Cuándo |
|---|---|
| `exito` | La búsqueda de la noche o la pasada de la mañana cumplió todos los cupos y ningún perfil quedó bajo el mínimo de 5. |
| `pocas_vacantes` | Tras la pasada de la mañana sigue faltando algún cupo o algún perfil quedó bajo el mínimo. La noche con faltantes no avisa: la mañana intenta completar. |
| `fallo` | La noche o la mañana fallaron sin producir resultado o con envíos a Supabase pendientes; en las capturas de cada hora, solo al tercer fallo seguido. |

El correo lleva cifras por cargo (entregadas, faltantes, ampliadas, mayor pérdida del embudo), el número de perfiles bajo
el mínimo y enlaces al panel y a la ejecución. **Nunca** incluye nombres, teléfonos ni filtros de clientes. Las
direcciones no se escriben en logs, `salud.json`, artefactos ni en el repositorio.

## Envío

API de Resend con `RESEND_API_KEY` (secreto de GitHub y variable del alojamiento del panel) y remitente
`ALERTAS_REMITENTE` (variable; p. ej. `Adaptia <alertas@dominio-del-cliente>`). Sin clave, sin remitente o sin
destinatario no se envía nada y la ejecución no falla por ello. Los avisos opcionales de Healthchecks (`AVISO_*`)
siguen funcionando aparte.

## WhatsApp: contactos y borradores diarios (SQL 013)

Decisión de Oscar (12 nov 2026): integración con WhatsApp mediante **un botón que abre el chat de la persona con el
mensaje ya escrito** (`https://wa.me/<número>?text=<mensaje>`). No se usa la API oficial ni ninguna automatización de
WhatsApp Web: **nada se envía solo**; el operador revisa y pulsa enviar en su WhatsApp.

### `panel_contactos` (una fila por cliente)

| Campo | Regla |
|---|---|
| `cliente_id` | id del cliente de la configuración |
| `telefono` | `+<código de país><número>`, 8 a 15 dígitos; sin código de país se rechaza (no se adivina) |
| `nombre_saludo` | nombre con el que se saluda (opcional, ≤60). Sin él, el saludo es neutro: la referencia interna nunca va en el mensaje |
| `consentimiento` | la persona aceptó recibir vacantes por WhatsApp; sin él no se prepara mensaje |

Fuera de la configuración versionada para no copiar teléfonos en cada versión. Solo `service_role`.

### `panel_borradores` (uno por cliente y día)

`fecha`, `cliente_id`, `texto`, `vacantes` (ids), `cargos`, `estado` (`pendiente`, `abierto`, `enviado`, `descartado`) y
`editado`. Reglas de `panel/borradores.generar`:
- Se prepara tras la búsqueda de la noche, otra vez tras la pasada de la mañana y, como respaldo, a las 8:05 Bogotá
  (`mensajes.yml`) o con «Preparar mensajes» en el panel.
- Solo vacantes asignadas a ese cliente con **enlace comprobado para compartir** (≤6 h), incluidas las «ampliadas».
  Máximo 10. Si hoy hay menos de 5, completa con días anteriores (hasta 3) y el panel avisa al operador; el mensaje no.
- Nunca repite una vacante que ya fue en otro borrador de esa persona.
- Regenerar no pisa un borrador abierto, enviado, descartado o editado a mano.
- Texto por plantillas que rotan por día, sin IA: saludo, una frase con su(s) cargo(s), lista «n. Título · Empresa
  (modalidad)» con su enlace y un cierre. No enumera filtros ni datos técnicos.

Teléfonos y textos nunca van a `salud.json`, artefactos, logs, correos de alerta ni al repositorio.
