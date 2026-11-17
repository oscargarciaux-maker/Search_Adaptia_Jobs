# Contrato de datos v39: comprobar enlaces de LinkedIn sin que nos bloqueen

**Fecha:** 17 de noviembre de 2026. **Sin SQL ni IA.** Viene del embudo de la búsqueda #30 del 17 nov.

## Por qué
- Product Designer tenía 100 vacantes nuevas que cumplían los filtros de algún cliente, pero solo 27 con el enlace
  comprobado en las últimas 24 h. Se entregaron 22 de una meta de 70.
- En total, 415 vacantes se quedaron fuera por «enlaces sin comprobar o rechazados».
- La causa: LinkedIn responde 429 a la comprobación de la página `/jobs/view/` (1.676 enlaces «bloqueados») e Indeed
  responde 401 siempre (1.293).

## Reglas
1. **Lo que la búsqueda ya leyó cuenta como comprobación.** La ficha pública de LinkedIn
   (`jobs-guest/jobs/api/jobPosting/<id>`), leída en la búsqueda o en la relectura, se registra igual que una
   comprobación (`linkedin_publico.FICHAS` → `verificar_enlaces.incorporar`):
   - **abierta**, solo si trae el título del aviso y su descripción;
   - **cerrada**, si dice que ya no recibe postulaciones;
   - **lo dudoso** no se anota.

   Vale las mismas 24 h y no reemplaza una comprobación más reciente.
2. **La comprobación de un enlace de LinkedIn lee esa misma ficha** en lugar de la página del aviso, con el mismo
   criterio (`ficha_linkedin`).
   - Un 200 sin el título del aviso nunca aprueba, porque un aviso que ya no existe también responde 200.
   - Va de una en una, con 1,5 s entre consultas.
   - Tras 3 bloqueos seguidos, LinkedIn descansa el resto de la ronda y el tiempo queda para los demás sitios.
3. **Indeed no se comprueba directamente:** siempre responde 401. Su vacante cuenta como comprobada si el enlace
   directo de la empresa (`enlace_directo`) lo está. Un bloqueo sigue sin confundirse con un cierre.
4. **Presupuesto por búsqueda diaria:** 800 enlaces en 10 minutos (antes 400 en 6).

## Lo que no cambia
- Sin comprobación vigente no se entrega ni se comparte (v3, v9, v31): solo cambia por dónde se comprueba.
- La comprobación no inicia sesión, no usa cookies ni Apify y no envía formularios.

Prueba en vivo del 17 nov: 8 avisos reales de LinkedIn resueltos en 11 s, 4 abiertos y 4 cerrados, sin ningún
bloqueo.
