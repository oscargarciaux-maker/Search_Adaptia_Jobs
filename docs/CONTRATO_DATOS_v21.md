> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v21 — metas diarias por perfil, techo del día y cliente Comunidad

Vigente desde el 14 nov 2026, a pedido del cliente en la reunión del 14 nov. Amplía la configuración del panel
(contratos v6, v8 y v20). Sin columnas nuevas en `ofertas`. **SQL 015** reemplaza solo las comprobaciones de guardar y
programar de SQL 009 (sin tablas nuevas). La configuración sigue guardándose como JSON.

## Qué cambia

- **`Perfil.meta_diaria`** (entero de 0 a 120): cuántas vacantes al día busca ese perfil. Un perfil nuevo empieza con
  10. Con 0 el perfil no busca.
- **`Configuracion.techo_diario`** (entero de 1 a 600; por defecto 120): máximo de vacantes del día. Protege los
  consumos (presupuesto de Apify y tiempo de búsqueda); sus topes propios siguen aparte (USD 5 al mes en Apify).
- **`Cliente.comunidad`** (sí/no): el cliente «Comunidad» (grupo de WhatsApp) recibe **después** de los clientes
  reales, solo con lo que cabe bajo el techo.
- **El cupo por cargo ya no se edita.** El servidor lo calcula (`panel/modelos.py`, `aplicar_metas`):
  - cupo del cargo = suma de las metas de sus perfiles de clientes reales + la parte de las metas de Comunidad que cabe
    bajo el techo (proporcional, redondeada hacia abajo);
  - el motor sigue eligiendo por cargo, con ese cupo.
- **Lo que sobra del techo no se pierde.** Si los clientes reales no llenan su meta, la selección del día completa
  hasta el techo con vacantes que sirven a los perfiles de Comunidad y que nadie tomó, con la misma variedad
  (`buscador/entrega.sobrante_para_comunidad`). Sin Comunidad, no cambia nada.
- **Guardar y programar.**
  - Un borrador puede pasar el techo mientras se edita.
  - Para programar: las metas de los clientes reales no pasan el techo y la suma del día va de 1 al techo. Ya no hay
    que repartir exactamente 120.

## Configuraciones anteriores

Un perfil sin `meta_diaria` recibe su parte del cupo antiguo de su cargo, repartido entre los perfiles activos de ese
cargo (por ejemplo 50 entre tres perfiles: 17, 17 y 16). El techo queda en 120. Así, lo programado antes busca
exactamente lo mismo hasta que el operador edite las metas.

## Lo que sigue igual

- Los filtros de cada perfil, el mínimo de 5 por perfil y sus ampliaciones (v9, v11), y la reasignación de días
  anteriores.
- La tabla `ofertas`, el CSV del contrato y la regla de no inventar datos.
- Nada se envía solo; la búsqueda sigue sin IA.

## SQL 015

- `panel_guardar`: el techo va de 1 a 600 (120 si la configuración no lo trae). Ya no compara con 120.
- `panel_publicar`: la suma de cupos activos va de 1 al techo, y cada cargo con cupo necesita un perfil activo.
- Se instala con «Preparar Supabase», que corre solo al fusionar cambios en `supabase/`, con copia cifrada previa.
  Si el panel nuevo se usa antes, el aviso dice que hay que correrlo.

## Informe de la búsqueda completa

`datos/salud_bodega.json` en la rama `publicado` guarda una copia del informe de la búsqueda completa (6:30 y 8:30).
La captura de cada hora ya no lo pisa. Solo trae conteos, como `salud.json`.
