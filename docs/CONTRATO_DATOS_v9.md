# Mínimo por perfil, ampliación marcada y vigencia para seleccionar — v9

Revisión del 12 de noviembre de 2026. Amplía v8 (perfil) y v3 (comprobación de enlaces). No requiere SQL nuevo.

## Mínimo por perfil

Cada perfil activo (cliente + cargo) debería recibir **al menos 5 vacantes al día**. Primero se eligen, como siempre,
las que cumplen todos sus filtros. Si un perfil queda por debajo de 5 y su cargo aún tiene cupo, se amplía por niveles,
en este orden y solo hasta llegar a 5:

| Nivel | Marca | Qué se admite además |
|---|---|---|
| 1 | `sin_dato` | Avisos que no dicen años de experiencia o nivel de inglés (como si el perfil marcara «Admitir … no informado»). |
| 2 | `cargo_cercano` | Títulos de `terminos_cercanos` del cargo (oficios vecinos). Incluye el nivel 1. |
| 3 | `remota_cercana` | Solo si el perfil no acepta remoto: vacantes remotas abiertas a su país. Incluye el nivel 1. |

**Nunca se amplía:** que se pueda postular desde su país, idioma español o inglés, enlace comprobado, que no esté
repetida, entregada antes ni cerrada, plazo de publicación, rango de años cuando el aviso sí lo dice ni nivel de inglés
cuando el aviso sí lo exige. Si ni así se llega a 5, no se rellena con nada más y se informa el faltante.

Las ampliadas cuentan dentro del cupo del cargo; el total diario sigue siendo la suma de cupos (120).

## Campos

- Cargo: `terminos_cercanos` (lista opcional, máx. 30, mismas reglas que los demás términos). Solo se usan para
  ampliar; la selección normal no los cuenta como del cargo. La búsqueda dirigida sí los consulta.
- Vacante seleccionada (snapshot del lote y de `entregas_diarias`): `_ampliacion` con el nivel (`sin_dato`,
  `cargo_cercano`, `remota_cercana`) cuando entró por ampliación. No contiene datos de clientes.
- Asignación (`panel_asignaciones.explicacion`, jsonb): un elemento `{"ampliacion": <nivel>}`. Solo se asigna por
  ampliación a perfiles que tenían menos de 5 vacantes estrictas ese día.

El texto de WhatsApp no muestra la marca; el panel sí, en «Vacantes».

## Vigencia de la comprobación de enlaces (modifica v3)

| Uso | Comprobación positiva o cierre | Bloqueo o fallo temporal |
|---|---|---|
| Decidir la selección | 24 h | 30 min |
| Compartir (copiar a WhatsApp) | 6 h | — |

Las capturas de cada hora comprueban primero el lote del día con el plazo de 6 h, después las candidatas en el orden en
que las elegiría la selección (más allá del cupo) y, con lo que sobre, lo reciente. Lo no comprobado sigue sin aprobarse.
