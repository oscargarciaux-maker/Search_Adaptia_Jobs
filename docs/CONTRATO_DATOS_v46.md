> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v46 — «Mandarme todos» en un solo mensaje y Mensajes que cuadran con el Resumen (18 nov 2026)

Decisión de Oscar (18 nov): «Mandarme todos a mi WhatsApp» debe llegar en **un solo mensaje y con un solo clic**,
sin partes. Eligió enlaces cortos. Sin IA y sin SQL. Reemplaza el punto 3 de v31 (partes de 7.000 caracteres).

## Reglas
1. **Un solo mensaje al número del operador** (`panel/borradores.para_operador`, `GET /api/borradores/para-mi`):
   un encabezado y, por cliente con mensaje pendiente o abierto y WhatsApp, «*Nombre* (N vacantes): <enlace corto>».
   Con 30 clientes son unos 2.500 caracteres. Ya no hay `partes` ni `LARGO_ENLACE`.
2. **Enlace corto** `GET /w/<borrador_id>.<firma>`, fuera de `/api/` y sin sesión, porque se abre desde el teléfono:
   - `firma` = HMAC-SHA256 (16 caracteres) de `borrador_id|fecha`. La llave se deriva en el servidor de la
     credencial de servicio (`SUPABASE_SECRET_KEY`); en demostración es una llave al azar del proceso. No hay
     variable nueva, y la llave nunca sale del servidor: ni al navegador, ni a los registros, ni a los enlaces.
   - Vale solo el día del mensaje (Bogotá) y mientras el mensaje esté pendiente o abierto, y el cliente tenga WhatsApp.
   - Al abrirlo, marca el mensaje «abierto» y redirige (302) a `wa.me/<cliente>?text=<su mensaje actual>`: lo editado
     en el panel cuenta.
   - Si no vale, una página corta: «Este enlace ya no sirve». Tampoco vale si el cliente retiró su consentimiento.
   - La vista previa del enlace (WhatsApp, Facebook) no lo marca «abierto».
   - Respuestas con `Cache-Control: no-store`. El registro de accesos guarda solo «/w/…», sin la ficha, porque la
     ruta completa sirve hasta medianoche para abrir el mensaje del cliente.
   - La llave sale de la misma credencial que usa el panel (`SUPABASE_SECRET_KEY` o `SUPABASE_SERVICE_ROLE_KEY`),
     así que no cambia al reiniciar.
   - La dirección base es `PANEL_ORIGIN` (HTTPS, la misma que protege el panel); en demostración, la de la petición.
3. **Un clic:** el panel prepara el enlace al abrir Mensajes y cada vez que cambian los mensajes, así el botón es un
   enlace de verdad. No hay «Preparar» ni lista de partes.
4. **Nada se envía solo:** el operador envía su mensaje y, desde su teléfono, toca cada cliente y envía.
5. **De qué día es cada vacante del mensaje:**
   - `GET /api/borradores` añade por mensaje `de_hoy` y `anteriores`: cuántas vacantes están asignadas a ese cliente
     en la búsqueda de hoy y cuántas vienen de los 3 días anteriores, sin haber ido nunca en otro mensaje (regla de
     v10/v31 que no cambia). Se calcula con una lectura ligera de `panel_asignaciones` (solo ids).
   - Mensajes lo dice: «0 de hoy y 7 de días anteriores». La tarjeta del cliente en el Resumen sigue contando lo
     asignado hoy, y debajo dice «7 por enviar (de días anteriores)». Caso Juan, 18 nov: «0 de 10» en el Resumen y
     7 en Mensajes.
   - Si alguna vacante del mensaje es de días anteriores, la frase de entrada no dice «hoy» ni «nuevas»: «Te comparto
     N vacantes de <cargo> que siguen abiertas…».
6. **Velocidad:**
   - escribir un mensaje, un contacto o «Mi número» solo renueva las copias de Mensajes (`sello_mensajes`), no las
     de resultados, configuración ni historial;
   - las vacantes de un cliente solo se piden en la pestaña Vacantes.

## Mismo PR (sin contrato de datos)
- **Editar cargo:**
  - «En español», «Sugeridos» y «Más amplio» van arriba, antes de «Nombres del cargo», y se ven siempre. Si uno queda
    vacío dice por qué: ya los tiene, no hay nombres en español conocidos, o es el oficio general.
  - Si la carga falla, se dice, con «Reintentar».
  - Más aire entre títulos, campos y «Opciones avanzadas».
- **Resumen:** «Cupo diario · 130 a clientes · Comunidad hasta 20» en una sola línea, y «Ver historial» al pie de su
  tarjeta, como los otros enlaces.
