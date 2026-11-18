# Contrato de datos v42: portales de empresas comprobados por su propio listado

**Fecha:** 18 de noviembre de 2026. **Sin SQL ni IA.** Aprobado por Oscar tras la búsqueda #32.

## Por qué
La búsqueda #32 trajo 1.333 vacantes nuevas de los portales de empleo de las empresas (Greenhouse, Lever, Ashby,
Workable, SmartRecruiters, Recruitee), 129 tableros de ellas gracias a Open Seat. Solo 57 se alcanzaron a comprobar en
el tiempo de la noche. Sin comprobación vigente no se entregan, así que casi todas quedaban fuera.

## Reglas
1. **Listada hoy en el portal de la empresa = abierta 24 h.** Un aviso que la API pública del portal de la propia
   empresa listó en esta corrida cuenta como comprobado, con el motivo «vista hoy en el portal de la empresa»
   (`verificar_enlaces.vistas_en_portales(enlaces_ats)` → `verificar_enlaces.incorporar`).
   - Esas API solo listan avisos activos (Ashby, además, sin los no listados) y son el mismo sitio donde se postula.
   - Vale las mismas 24 h de siempre (v9, v31); si al día siguiente no aparece, vuelve a quedar sin comprobar.
   - Si la vacante también está en LinkedIn, su enlace de LinkedIn conserva su propia comprobación (v39); la vacante
     queda comprobada por el enlace del portal, que es el que se comparte.
2. **No entran** Computrabajo ni Get on Board (sus listados pueden traer avisos viejos), ni enlaces de LinkedIn, Indeed
   o agregadores aunque aparezcan en el listado. Esos siguen con su comprobación de siempre.
3. Lo ya comprobado así no se vuelve a pedir en la noche: el tiempo de comprobación queda para Computrabajo, Get on
   Board, LinkedIn y los portales que no se leyeron hoy.
4. Se informa cuántas se incorporaron en `verificacion_enlaces.vistas_portales_incorporadas`.

## Lo que no cambia
- Un aviso que desaparece del portal de una empresa leída completa sigue contando como cerrado (cobertura v2).
- Sin comprobación vigente no se entrega ni se comparte.
- La comprobación no inicia sesión ni envía formularios.
