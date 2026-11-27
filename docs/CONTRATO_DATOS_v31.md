> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v31: mensajes, Actividad y sesión

**Fecha:** 16 de noviembre de 2026.
**Amplía:** [v9](CONTRATO_DATOS_v9.md) (comprobación de enlaces), [v10](CONTRATO_DATOS_v10.md) (borradores de
WhatsApp, ajustes) y [v11](CONTRATO_DATOS_v11.md) (posts).
**Sin SQL ni IA. Nada se envía solo.**

## Qué cambia
1. **Mensajes de WhatsApp** (`panel/borradores.generar`):
   - **Cuántas:** hasta 10 vacantes por cliente, con un máximo de 2 de la misma empresa (los posts no cuentan para
     ese tope).
   - **Las que sobran:** si quedan vacantes listas que no entran por el tope de 10 o por empresa, el mensaje lo
     ofrece: «Tengo N vacantes más para ti; si quieres, te las paso.»
2. **Enlace para compartir:** sirve si se comprobó en las últimas **24 h** (antes, 6 h; los posts ya tenían 24 h desde
   v11). Está en `panel/afinidad.HORAS_COMPARTIR`.
   - Es la misma regla para «listas para compartir», el WhatsApp y el CSV.
   - La comprobación sigue sin enviar formularios ni usar Apify.
3. **«Mandarme todos a mi WhatsApp»:**
   - `panel_ajustes.operador = {telefono}` guarda el número del operador, en el campo «Mi número» de Mensajes.
     Lo validan `GET /api/ajustes/operador` y `PUT /api/ajustes/operador`.
   - `GET /api/borradores/para-mi` (`borradores.para_operador`) arma un mensaje a ese número con un enlace wa.me por
     cliente con mensaje pendiente o abierto. Si el enlace pasa de 7.000 caracteres, se parte en varias partes.
   - El operador abre cada parte en su WhatsApp y, desde el teléfono, toca cada cliente. No se envía nada solo.
4. **Lista de enviados:** las casillas «Enviados hoy» cambian el estado del borrador a `enviado` o `abierto`. El
   cambio se ve al momento y se deshace si el servidor lo rechaza.
5. **Actividad:**
   - el embudo usa nombres claros: «Abiertas y vigentes hoy» en lugar de «Enlace comprobado», «Le sirven a algún
     cliente», etc.;
   - la etapa que más pierde trae «Qué hacer», con una acción concreta.
6. **Sesión:**
   - Al entrar se guardan dos cookies httponly, secure y samesite strict:
     - el acceso, de 1 h;
     - la renovación, de 30 días, solo para `/api/`.
   - Si el acceso venció, el servidor pide uno nuevo a Supabase con la renovación. Vuelve a comprobar que sea un
     operador con el correo confirmado y repone las dos cookies.
   - «Cerrar sesión» borra las dos y anula la renovación en Supabase.
7. **Código:** Mensajes y Actividad pasan a `web/src/vistas/`.

## Pruebas
- `pruebas/panel/test_mensajes_v31.py`:
  - 2 por empresa y «Tengo más»;
  - sin sobrantes no se ofrece nada;
  - enlace de 24 h;
  - número del operador y mensaje en partes;
  - sesión renovada, rechazada y cerrada.
- **Playwright:**
  - Mi número, «Mandarme todos» y la lista de enviados;
  - embudo con «Qué hacer»;
  - contraste.
