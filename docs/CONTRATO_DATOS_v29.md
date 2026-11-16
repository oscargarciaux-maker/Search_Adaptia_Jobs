# Contrato de datos v29: Vacantes y «Por confirmar» rápidos y tipo LinkedIn

**Fecha:** 16 de noviembre de 2026. **Amplía:** [v16](CONTRATO_DATOS_v16.md) (bandeja «Por confirmar») y
[v28](CONTRATO_DATOS_v28.md) (lectura acotada de fichas). **Sin SQL ni IA.** No cambia `ofertas`, el CSV, el cupo, la
generación nocturna de la bandeja ni sus decisiones.

## Por qué
- El panel no podía mostrar el aviso completo: la descripción nunca llegaba al navegador.
- «Por confirmar» mostraba solo 10 de cientos, y para eso leía la descripción de todas las pendientes.
- «Vacantes» leía todas las asignaciones con la fila completa del catálogo en cada visita.

## Qué cambia
1. **Ficha de una vacante:** `GET /api/vacantes/{id}/ficha` (operador). Devuelve:
   - los datos del catálogo (título, empresa, ubicación, modalidad, salario, publicación, años, inglés y enlaces);
   - la descripción en bloques `{tipo: "p"|"li"|"h", texto}`, que el panel pinta como texto, nunca como HTML;
   - `origen`: `guardada`, `traida` o `sin_descripcion`.
2. **Descripción que falta:** se lee una vez del `JobPosting` de la ficha original (`buscador/ficha.py`) y se
   guarda en `catalogo_vacantes.description_full`, solo si estaba vacía y con el tope de 30.000. La lectura:
   - es solo GET, sin cookies ni formularios;
   - solo va a dominios de la lista fija `datos/dominios.yaml`, nunca a agregadores;
   - tiene un tope de 1 MB y 12 s, y no sigue redirecciones fuera de la lista (la misma regla del contrato v28,
     ahora compartida).
   La demostración no lee sitios.
3. **«Por confirmar» completa:** `GET /api/revisiones?pagina=&por_pagina=&cliente_id=`. Muestra todas las pendientes
   por prioridad, en páginas de hasta 100, con:
   - `total`: las que cumplen el filtro;
   - `en_espera`: todas;
   - `por_cliente`: el conteo de cada cliente;
   - `mas_util`: marca las 10 más útiles de hoy (el antiguo `tope`).

   Se leen sin la descripción y se pide la descripción solo de la página. Sin `pagina`, la ruta responde como en
   v16.
4. **Copias cortas en memoria del servidor:**
   - resultados por cliente y fecha durante 2 minutos; cualquier escritura del panel (POST, PUT, PATCH, DELETE) las
     invalida;
   - fichas durante 10 minutos.
5. **Menos «por confirmar»:** `confirmar_ubicacion` lee hasta 300 fichas por noche en 480 s (antes 150 en 300 s).
   Las vacantes con enlace de LinkedIn ya se leían por su ficha pública, sin sesión ni cookies.

## Interfaz
- **Vista dividida en Vacantes y «Por confirmar»:**
  - lista compacta a la izquierda y aviso completo a la derecha;
  - ↑/↓ o J/K cambian de vacante;
  - `#vacantes/<id>` recuerda la elegida;
  - en el celular, la ficha ocupa la pantalla y tiene «Volver a la lista».
- **En «Por confirmar»:**
  - la decisión va a la derecha con la descripción;
  - después de decidir se pasa sola a la siguiente y conserva el foco para seguir con los atajos;
  - filtro «Para» por cliente.
- **El Resumen y el detalle del cliente** usan el total real y el conteo por cliente.
- **Archivos:**
  - `web/src/comunes.tsx`;
  - `web/src/vistas/Vacantes.tsx`, `PorConfirmar.tsx` y `FichaVacante.tsx`.

## Pruebas
- `pruebas/panel/test_ficha_v29.py`:
  - bloques sin HTML;
  - `JobPosting`;
  - dominio fuera de la lista;
  - ficha guardada, traída y sin descripción;
  - páginas, total real, filtro y conteo por cliente;
  - copia de resultados invalidada al decidir.
- **Playwright:**
  - vista dividida, teclado, dirección, celular y contraste;
  - bandeja con total, filtro y paso automático a la siguiente.
