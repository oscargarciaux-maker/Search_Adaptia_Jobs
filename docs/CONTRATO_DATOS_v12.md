# Solo español e inglés; Brasil solo en remotas de varios países — v12

Revisión del 12 de noviembre de 2026 (decisión de Oscar). Amplía v1 (idioma), v8 (país de residencia) y la cobertura
«LATAM y España» del 5 de noviembre. Sin SQL nuevo.

## Lo que se encontró

- **Idioma:** el detector contaba palabras comunes al español y al portugués («de», «que», «para», «empresa»…). Un
  aviso largo en portugués salía como «es», y la regla «solo español e inglés» no lo frenaba. En el inventario del
  12 nov había 1.043 avisos en portugués; 872 estaban marcados «es».
- **Brasil:** era un país activo. Se buscaba en Brasil y una vacante local, híbrida o «Remoto, Brasil» contaba como
  válida.
- **Entregas:** del 5 al 10 nov, 145 de 620 entregas revisadas eran en portugués (99) o solo para Brasil (46). Desde
  el 11 nov, con los perfiles del panel, ninguna.

## Reglas

1. **Idioma** (`etiquetas.idioma`): cuenta solo palabras propias de cada idioma; las compartidas no deciden. Se
   recalcula también al releer el inventario (`vacante.reetiquetar`), así el arreglo alcanza a lo ya guardado. Se
   entrega solo `es` o `en` (sin cambios en `contrato.entregable`), también para los posts (v11).
2. **Brasil** (`datos/paises.yaml`, `cobertura: false`): se sigue **reconociendo** en los avisos («São Paulo» es
   Brasil, no «ubicación por confirmar»), pero no es país de cobertura:
   - fuera de `paises_activos`: no se busca en Brasil (LinkedIn, Indeed, Apify, refuerzo);
   - una vacante local, híbrida o remota solo para Brasil queda sin países (`nota_pais = "país fuera de la cobertura"`)
     y no se entrega;
   - una remota abierta a varios países («LATAM», «Americas», «Global», o una lista que incluye Brasil) se conserva
     para los demás países; Brasil nunca aparece en `paises`;
   - el panel no ofrece Brasil como país de residencia ni de oficina. Un perfil guardado antes con Brasil se sigue
     leyendo (no rompe la configuración), pero no recibirá vacantes.
3. `datos()` de `paises.py`: `paises` y `reconocidos` son todos los países que se identifican; `codigos`, `latam`,
   `europa` y `cubiertos`, solo los de cobertura (20).

## Limpieza única de la base de datos

Flujo manual **«Limpiar portugués y Brasil»** (ejecutado el 12 nov: 153 filas borradas de `ofertas`), autorizado por
Oscar para cumplir este contrato. No sirve para ocultar déficit. **Reemplazado por el flujo general de v13**
(«Revisar y limpiar vacantes fuera del objetivo»), que incluye estas reglas.

- **Simulación (por defecto):** aplica las reglas de arriba a todo `catalogo_vacantes` y cruza con `ofertas` por
  `vacante_id`, `external_id` en `ids_agrupados` y enlaces. Las filas de `ofertas` sin catálogo se juzgan por
  `hire_countries`: si dicen solo `BR`, salen. Informa solo conteos por motivo y por día, sin títulos, empresas ni
  enlaces.
- **Aplicar** (casilla «aplicar» + escribir `BORRAR`), en este orden:
  1. copia cifrada de las tablas (90 días en Actions);
  2. en una sola transacción, **borra esas filas de `ofertas`** y pasa sus vacantes del catálogo a `archived` con
     `reason = "contrato v12: idioma o país fuera de la cobertura"`.
- **Se conserva:** `entregas_diarias` y `panel_asignaciones` (historial privado). Las filas borradas se pueden
  reconstruir desde el catálogo, `entregas_diarias` y la copia cifrada. Repetir la limpieza no hace nada más.
- Las noches siguientes no vuelven a entrar: ya no son entregables, y el catálogo archiva por sí solo las que siguen
  en el inventario.
