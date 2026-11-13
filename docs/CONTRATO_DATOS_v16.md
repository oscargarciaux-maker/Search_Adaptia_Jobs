# Confirmación automática por la ficha y bandeja «Por confirmar» — v16

Revisión del 13 de noviembre de 2026 (plan acordado con Oscar). Amplía v15. **SQL 014** añade dos tablas privadas.
Segunda de tres etapas; la tercera (v17) es el aprendizaje automático por código.

## 1. Primero, el sistema intenta confirmar solo (`buscador/confirmar_ubicacion.py`)

En la búsqueda de la noche y en la pasada de la mañana, antes de verificar enlaces, se revisan las vacantes que tienen
la ubicación «por confirmar». Deben estar en español o inglés, ser recientes y ser del cargo de algún rol. Para cada
una se lee **la ficha pública**: solo GET, sin Apify ni formularios, con un presupuesto en `datos/config.yaml →
confirmar_ubicacion` de 60 fichas y 180 s.

De la ficha se toman sus datos estructurados `schema.org/JobPosting`:
- `jobLocation.address` (ciudad, región y país);
- `applicantLocationRequirements` (países desde los que se puede postular);
- `jobLocationType: TELECOMMUTE` (remoto).

**Resultado:**
- Si hay evidencia, queda como una observación más de ubicación (fuente «ficha estructurada»): un país cubierto se
  confirma y un país solo extranjero se descarta.
- Un 403, un error o una página sin esos datos no prueban nada: la vacante sigue por confirmar.
- Lo leído se recuerda 7 días en `trabajo/ubicacion_fichas.json`. Solo guarda el enlace y la ubicación pública del
  aviso, ningún dato de clientes.
- `salud.json` muestra los conteos en «Ubicación desde la ficha».

## 2. Tablas (SQL 014, privadas, solo la credencial de servicio)

- **`panel_revisiones`**, una fila por vacante en la bandeja:
  - `estado`: `pendiente`, `confirmada`, `descartada`, `saltada` o `vencida`;
  - `motivo`, `pista` (frase del aviso), `ubicacion` (texto normalizado), `sugerencia` (países), `paises` decididos,
    `perfiles` a los que ayuda y `prioridad`.
- **`panel_reglas_ubicacion`**, una regla por ubicación exacta: `texto`, `resultado` (`{"paises": [...]}` o
  `{"extranjero": true}`), `origen` (`operador` o `aprendida`, esta última en v17), `activa`, `usos`, `conflictos` y
  `ejemplos`.
- Entran en las copias de seguridad y en el traspaso: ahora son **dieciséis tablas**.

## 3. Cola diaria (`panel/revision.preparar_cola`, al final de `panel/ejecutor.registrar`)

- **Candidatas:** vacantes del catálogo con `reason = "elegibilidad regional por confirmar"` vistas en los últimos 2
  días, con idioma `es`/`en`, que **cumplen todos los filtros de algún perfil activo salvo el país** y que esa persona
  no recibió antes.
- **Prioridad:** 100 puntos por cada perfil con menos de 5 vacantes, 10 por cada uno de los demás, y un extra por lo
  reciente.
- **Tope:** como mucho **10 pendientes a la vez**. El número se cambia en `panel_ajustes → revision.tope`.
- **Vencidas:** pasan a `vencida` las pendientes de más de 7 días y las que ya no le sirven a nadie.
- **Pista y sugerencia:** la «pista» es la frase del aviso con más evidencia de lugar. La «sugerencia» son los países
  cubiertos que nombra.
- **Reglas del operador:** una vacante nueva cuya ubicación ya tiene regla se decide sola, sin ocupar lugar en la
  bandeja.
- Solo conteos en el resumen de la ejecución (`por_confirmar`, `por_confirmar_faltantes`, `resueltas_por_regla`) y en
  el correo diario.

## 4. Decisiones (`POST /api/revisiones/{vacante_id}`)

| Botón | Efecto |
|---|---|
| **Sirve para [país]** | Asignación para los perfiles a los que ayuda: solo hasta 5 y sin repetir a nadie. Se comprueba el enlace en ese momento para poder compartirla hoy. Se rehacen los borradores de WhatsApp pendientes y sin editar. |
| **Solo para otro país** / **No sirve** | Se descarta y no vuelve a la bandeja. |
| **Saltar** | Se aparta por ahora. |

- **«Aplicar a las N con esta misma ubicación»:** guarda la regla y decide igual las demás pendientes con esa
  ubicación. **Nunca con ubicaciones genéricas** («Remote», «Remoto», «N/A»…), que no dicen ningún lugar.
- En «Vacantes», una vacante confirmada se evalúa con los países decididos (nota «confirmada por operador» o «por
  regla»). Que estuviera archivada en el catálogo solo por «elegibilidad regional por confirmar» ya no la retira.
- Validaciones:
  - los países deben ser cubiertos;
  - una vacante no se decide dos veces;
  - sin la búsqueda del día no se puede asignar, y el panel lo explica.

## 5. Panel

- Sección **«Por confirmar»** con un contador en el menú.
- Cada tarjeta muestra la ubicación tal como viene, la pista resaltada, a qué clientes ayudaría, el país sugerido ya
  elegido, cuatro botones con atajos de teclado (1–4) y un enlace al aviso.
- Estado vacío: «Todo al día».
- Accesibilidad como el resto del panel: texto ≥ 12 px, foco visible, sin desbordamiento en móvil.

## Garantía

Si nadie revisa la bandeja, nada empeora: las dudosas siguen sin entregarse, como antes. Si alguien la revisa, las que
le sirven a un cliente le llegan ese mismo día.
