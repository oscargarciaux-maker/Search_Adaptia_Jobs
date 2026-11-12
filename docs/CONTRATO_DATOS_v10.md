# Ajustes del operador y alertas por correo — v10

Revisión del 12 de noviembre de 2026. Añade la tabla privada `panel_ajustes` (SQL 012). No cambia el catálogo, las
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
