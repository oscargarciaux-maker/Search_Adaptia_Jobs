# Contrato de datos v40: la búsqueda se arma leyendo a cada persona

**Fecha:** 17 de noviembre de 2026. **Sin SQL ni IA.** Pedido de Oscar: «un plan que sirva para cualquier cargo… que
cualquier persona el sistema lo lea».

## Por qué
- El 17 nov, a las personas que viven fuera de LATAM les llegaba muy poco. Por ejemplo, quien vive en Emiratos y
  trabajaría en remoto para Europa: LinkedIn hizo 3 búsquedas para Emiratos y Europa nunca se buscó.
- Los lugares de búsqueda salían solo de donde vive la persona y de sus oficinas. Cada combinación de cargo y lugar
  recibía los mismos turnos, sin mirar cuántas personas la necesitaban ni cuántas fuentes tiene ese país.

## 1. Lugares desde todas las filas del perfil (`panel.ejecutor.lugares_perfil`)
- Cada fila de «¿Dónde trabajaría?» se vuelve lugares de búsqueda:
  - remoto en un país → `REMOTO_<país>`;
  - híbrido o presencial → `<país>` y las ciudades de esa fila (`CIUDAD_…`).
- **Regiones** (`datos/regiones_busqueda.yaml`, editable: Europa, LATAM, Norteamérica, Asia-Pacífico y Medio
  Oriente):
  - si una fila abarca 6 países o más y al menos el 60 % de una región, LinkedIn la busca con el nombre de la región
    («European Union», «Middle East»…) y, aparte, en sus países principales que la fila incluya;
  - los demás países sueltos de la fila se buscan uno a uno, hasta 10 por fila.
- «Remoto en LATAM» solo se busca para quien vive en LATAM. «Remoto en cualquier parte», para todo el que acepta
  remoto.
- Vale para cualquier país del mundo y cualquier cargo, también los creados hoy. Los países de fuera van por su
  nombre en inglés (v24).

## 2. Cuota de búsquedas por persona (`buscador.cobertura`)
- Cada persona activa pesa su meta del día, ×2 si quedó con menos de 5 (o es nueva) y ×2 si ninguno de sus países
  tiene fuentes propias. Fuentes propias: Computrabajo, Elempleo y Get on Board; fuera de ellas solo quedan LinkedIn e
  Indeed.
- Las fuentes que reparten por combinación (LinkedIn, Indeed, Computrabajo, Elempleo, Apify) dan turnos ponderados
  por persona:
  - avanza la persona con menos búsquedas para su peso;
  - toma su combinación menos reciente;
  - una búsqueda compartida sirve a todas sus personas y cuenta como turno para cada una.
- Lo que no es de ninguna persona sigue después, con el reparto de siempre. Sin personas (modo heredado), el reparto
  no cambia.
- Con los 21 perfiles reales del CSV v6 y las 46 combinaciones que LinkedIn alcanza a revisar en un día, la persona
  con menos búsquedas pasa de 1 a 2, y varias de Product Designer pasan de 1 o 2 a 4.

### Ajuste del 17 nov (tarde), tras la búsqueda de prueba #31
- **Lugares principales primero.** Cada día, los turnos de una persona empiezan por sus lugares principales: los de
  donde vive (su primera fila) y las regiones de sus filas. Después siguen los demás, por antigüedad.
- **Por qué:** en la #31, los turnos de quien vive en Emiratos se fueron en países sueltos de Europa, y ni «remoto en
  Emiratos» ni «European Union» llegaron a buscarse.
- **Resultado simulado:** con los perfiles reales, Emiratos, la Unión Europea, EE. UU. y Chicago quedan dentro de las
  primeras 46 búsquedas.

## 3. Rendimiento medido (`cobertura.medir`, `estado["rendimiento"]`)
- Cada aviso de LinkedIn e Indeed guarda de qué búsqueda salió (`_busqueda` = cargo@lugar).
- Al limpiar se cuenta cuántas vacantes nuevas de un cargo trajo cada combinación buscada hoy.
- Una combinación con 3 búsquedas seguidas sin nada útil pasa al final de los turnos de su persona; vuelve a subir
  apenas trae algo.
- Lo de más de 30 días se olvida.

## 4. Fuentes según el país
- **Indeed:** los 62 países que admite JobSpy (antes 26), Emiratos, Japón, India y Singapur incluidos. Solo busca en
  los países de los lugares de las personas (`paises_busqueda`), no en los 30 de una fila «Europa».
- **Relectura de fichas de LinkedIn:** empieza por los avisos de un cargo y un país de alguien que va corto
  (`cobertura.sirve_a_corta`). Sin descripción no se sabe el idioma y no se entrega; el 17 nov eran el 20 % de las
  vacantes nuevas.

## 5. En el panel
- «Cobertura por persona» suma la columna «Búsquedas hoy» (páginas de LinkedIn e Indeed hechas para esa persona).
- Si su país solo tiene LinkedIn e Indeed, la explicación lo dice.
- El conteo se guarda solo en el resumen privado de la corrida (`panel_ejecuciones.resumen.busquedas_por_perfil`),
  nunca en archivos públicos.

## 5 bis. La limpieza ya no borra lo de fuera de LATAM (17 nov, caso Danna)
- Al final de `bodega.limpiar` se archivaba toda vacante sin un país de LATAM o España («sin elegibilidad
  regional»), aunque la admisión de v24 la hubiera dejado pasar por ser de un país de los perfiles.
- Así se perdían, por ejemplo, los Product Designer de Chicago que LinkedIn sí traía: de 5.034 vacantes guardadas,
  solo 15 eran de EE. UU.
- En modo panel ahora se conservan si sirven a algún perfil (`_sirve_a_perfiles`); en modo heredado se archivan como
  siempre. La entrega ya las aceptaba desde v24 (`contrato.entregable` con `paises_mundo`).

- **Ventana de días al repetir una búsqueda** (`cobertura.dias_busqueda`, en LinkedIn, Indeed y Apify): una búsqueda
  repetida pide solo lo publicado desde la vez anterior; pero si esa vez no dejó nada útil (`ceros` en el rendimiento),
  pide los 30 días completos.
  - **Por qué:** lo que se perdió por la regla anterior vuelve a entrar. Si no, Chicago solo pedía el último día.

## 6. Comprobación final (`buscador/validacion.py`, 17 nov)
- Una vacante elegida hoy que después cerró, o salió del inventario, ya no se comparte (su enlace queda rechazado).
  Ahora es un **aviso**, no una falla; antes salía como «fuera del perfil».
- Sigue fallando:
  - una vacante que ya no encaja en ningún perfil del cargo;
  - un enlace de la selección de hoy que quedó sin comprobar.
- **El Resumen** vuelve a pedir las búsquedas cada vez que se entra en él y dice a qué hora se actualizó. Una segunda
  búsqueda del mismo día actualiza la de hoy y antes no se notaba hasta recargar la página.

## Lo que no cambia
- Admisión, afinidad, filtros por persona, comprobación de enlaces (v39) y reglas de entrega.
- LinkedIn sigue sin sesión ni cookies.
- El presupuesto total de búsquedas por noche no sube. Lo que cambia es a quién se le dedica cada búsqueda.
