# Contrato de datos v27: solo la ubicación y el idioma descartan

**Fecha:** 16 de noviembre de 2026. **Reemplaza:** las reglas de descarte por perfil de
[v20](CONTRATO_DATOS_v20.md), [v22](CONTRATO_DATOS_v22.md) y [v26](CONTRATO_DATOS_v26.md), y los niveles de
ampliación «sin dato», «cargo cercano» y «experiencia cercana» de [v9](CONTRATO_DATOS_v9.md) y
[v11](CONTRATO_DATOS_v11.md).

**No cambia:**
- las columnas de `ofertas` ni el CSV;
- los campos del perfil. Los perfiles guardados siguen valiendo tal cual.

**SQL:** una migración nueva, 016 (`panel_publicar_hoy`). La 009 y la 015 no se tocan.

## Por qué
La búsqueda del 15 de noviembre entregó 29 de 120.
- Casi todo lo que faltó se perdió por filtros del perfil que el aviso no decía o no cumplía por poco: años, nivel de
  inglés, salario y antigüedad.
- Oscar decidió (16 nov) que **solo la ubicación y el idioma del aviso determinan**. Lo demás debe ordenar y avisar,
  no esconder vacantes.

## Qué descarta
1. **Ubicación**, según el perfil: país, modalidad, ciudad, horario aceptado y permiso legal (v8, v23, v24).
2. **Idioma del aviso**: solo los idiomas que el perfil acepta (español, inglés).
3. **Reglas del sistema**, iguales para todos:
   - que siga abierta;
   - el enlace donde se postula;
   - que no se repita;
   - una fecha de publicación confirmada;
   - **un máximo de 30 días**.

## Qué solo ordena y deja una etiqueta
`panel.afinidad.evaluar` devuelve `compatible` (solo por lo de arriba) y además:
- `incumple`: los códigos de lo que no cumple, por ejemplo `experiencia fuera del rango`, `inglés requerido superior al
  indicado`, `nivel inferior al del perfil`, `salario menor al aceptado`, `menciona algo que el perfil no acepta`,
  `tipo de contrato no aceptado` y `publicación fuera del plazo del perfil`;
- `avisos`: el mismo dato en una frase corta para el panel, por ejemplo «Pide 7 años de experiencia», «Pide inglés C1»,
  «Salario menor al que pide», «Menciona algo que no acepta», «Tipo de contrato que no acepta», «Es de nivel junior o
  prácticas» o «Publicada hace 20 días».

**Cómo pesa al elegir.** Cada cosa que no cumple pesa como un grado de coincidencia menos
(`entrega.variadas`: exacto 0, similar 1, cercano 2, + `faltas`). Primero llegan las que encajan en todo, después las
que fallan en algo. Los años o el inglés **no informados** no descartan ni avisan.

**Siguen igual:**
- la regla de lo «deseable» (v22: «Java is a plus» no cuenta como mención);
- la conversión de monedas con margen del 10 % (v26);
- el junior abierto con 2 años o menos (v22).

Ahora solo deciden si aparece la etiqueta.

## Cargos
- **Los cargos cercanos entran directamente**, después de los exactos y los similares. Ya no esperan a la ampliación.
- La coincidencia **solo por funciones** (v25) sigue yendo a «Por confirmar» y nunca se entrega sola.
- **Importador:** en un cargo que ya existe, las columnas `nombres_del_cargo` y `funciones_del_cargo` **añaden**
  nombres (como similares) y funciones. Nunca quitan ni reemplazan nada, y la vista previa lo avisa. Antes se
  ignoraban.
- Mapa de cargos: la familia QA suma títulos de liderazgo (QA Manager, Head of QA, QA Team Lead, Quality Assurance
  Lead/Manager, Test Manager, Líder o Jefe de QA…).

## Mínimo de 5 por perfil
Con estas reglas casi todo entra en el primer intento.

**La ampliación queda solo como último recurso:**
- `remota_cercana`: una remota abierta a su país para un perfil que no marcó «remoto»;
- `empresa_4`: hasta 4 por empresa;
- después, reutilizar vacantes de otros días y los posts (v11).

Los nombres antiguos de ampliación se siguen leyendo para mostrar las asignaciones ya guardadas.

## «Aplicar hoy» (SQL 016)
Junto a «Programar para mañana», el panel ofrece **«Aplicar hoy»**:
- `panel_publicar_hoy(revision)` hace las mismas comprobaciones que programar: techo, metas y un perfil activo por
  cargo.
- Guarda la versión con vigencia **hoy en Bogotá**. Si esa revisión ya estaba programada para mañana, la adelanta a
  hoy.
- Si la búsqueda de hoy ya existe y terminó, pasa a la versión nueva y anota la anterior en
  `resumen.revisiones_anteriores`.
- **No borra ni cambia** lo entregado ni las asignaciones de hoy. La búsqueda siguiente de hoy (la manual, la de las
  8:30 o la horaria) completa el día con la configuración nueva.
- Si hay una búsqueda en curso (iniciada hace menos de 160 minutos, el tope del flujo), se rechaza: la que corre
  conserva su versión.
- Sin la migración instalada, el panel explica que hay que correr «Preparar Supabase». «Programar para mañana» sigue
  funcionando.

## Pruebas
- `pruebas/panel/test_control.py`:
  - años, inglés y restricciones dejan aviso sin descartar;
  - 30 días descarta;
  - la antigüedad del perfil solo avisa;
  - la vista previa ya no corta por datos sin informar;
  - los cercanos entran directo;
  - «Aplicar hoy» en la demostración.
- `pruebas/panel/test_rescate.py`: lo que encaja en todo va primero.
- `pruebas/panel/test_importar.py`: nombres y funciones que se añaden sin quitar nada.
- `pruebas/probar_panel.py` (PostgreSQL aislado):
  - SQL 016 rechaza con una búsqueda en curso;
  - al terminar, cambia la versión de la búsqueda de hoy sin borrar asignaciones.
- Playwright: «Aplicar hoy», la etiqueta «Pide 7 años de experiencia» y el distintivo de Comunidad, con contraste AA.
