# Idioma por evidencia y todos los países del mundo — v15

Revisión del 13 de noviembre de 2026 (pedido de Oscar). Amplía v12–v14. Sin SQL nuevo. Primera de tres etapas: después
vienen la bandeja «Por confirmar» en el panel (v16) y el aprendizaje por código (v17).

## Idioma: solo pasa español o inglés con evidencia (`buscador/etiquetas.py`)

- **El problema:** el detector decidía por descarte («¿a qué idioma conocido se parece más?»). Un aviso en neerlandés
  o turco salía como inglés y podía pasar.
- **La regla nueva:** `idioma()` devuelve `es` o `en` **solo si hay evidencia positiva y clara**. Se cumplen todas
  estas condiciones:
  - al menos 3 palabras del idioma, una de ellas exclusiva;
  - esas palabras son al menos el 3,5 % del texto;
  - el idioma gana por 1,4 veces al mejor de los otros perfiles.
  - Frente al portugués solo cuentan las palabras exclusivas de cada uno, así que «de», «que» o «para» no deciden.
- Hay perfiles de palabras frecuentes de 14 idiomas: portugués, francés, alemán, italiano, neerlandés, sueco,
  danés/noruego, polaco, turco, rumano, indonesio/malayo, vietnamita, checo/eslovaco y húngaro. **No sirven para
  aceptar nada**, solo para que el español o el inglés tengan que ganarles.
- Un idioma sin perfil también queda fuera: le falta la evidencia. El resultado es `""` (no confirmado), y solo `es` y
  `en` se pueden entregar.
- Un texto escrito mayoritariamente en otro alfabeto (japonés, coreano, chino, árabe, cirílico…) → `""`.
- Correos y enlaces se quitan antes de contar, porque «example.com» no es portugués.
- Un aviso bilingüe español-inglés pasa. Un aviso en otro idioma con requisitos en inglés no pasa: cuenta el idioma
  principal.

**Calibración** con el inventario del 12 nov: los avisos que dejan de pasar estaban todos en otro idioma (francés,
neerlandés, vietnamita, alemán, italiano, polaco, japonés, coreano), y no se pierde ninguno válido.

## Países: la tabla ISO completa (`datos/paises_mundo.yaml`, `buscador/paises.py`)

- **La tabla:** `python -m buscador.generar_paises_mundo` (requiere `pycountry` solo para generarla) escribe los 249
  países con:
  - siglas de 2 y 3 letras;
  - nombres en inglés, español y portugués, más alias comunes (UK, USA, Holanda, Emiratos…);
  - las subdivisiones ISO 3166-2 de los 21 países propios y de 15 extranjeros frecuentes.
- **Cómo se usa** (`paises.datos()`):
  - Cada lugar apunta a su país propio (los de `datos/paises.yaml`) o a «extranjero».
  - Las subdivisiones de los países cubiertos se reconocen como ese país: Pichincha → EC, Antioquia → CO, Jalisco → MX.
  - Todo nombre de otro país, y sus siglas, es extranjero.
- **Ambigüedad, calculada por código:**
  - Un nombre que apunta a más de un país es ambiguo y nunca decide solo. La tabla detecta Bolívar, La Paz, Florida,
    Cuenca, Santander y otros.
  - La lista editable `ambiguas` de `datos/paises.yaml` añade los que la tabla no ve porque no son provincias: Valencia,
    Córdoba, Santa Lucía…
  - Con el país al lado, sí cuentan.
- **Precedencias:**
  - Las ciudades elegidas a mano en `datos/paises.yaml` ganan a una provincia homónima de otro país. Por ejemplo,
    «Área metropolitana de Santiago» es Chile, aunque Santiago también sea una provincia dominicana.
  - Un lugar propio que contiene un nombre extranjero gana: «Baja California» es México.
  - Un lugar extranjero que contiene un país propio gana: «New Mexico» y «Nuevo México» son EE. UU.
- **Provincias extranjeras con nombre de palabra corriente:** las de la lista `palabras_comunes` («Como», «Mayo»,
  «Laguna»…) no se usan. Las demás provincias extranjeras se buscan solo en el campo de ubicación, nunca en la
  descripción.
- **Siglas**, desde la tabla:
  - ISO2 de cualquier país, suelta o al final de un tramo, e ISO3 en mayúsculas.
  - **AR, CO y PA** (también estados de EE. UU.) tras una palabra solo cuentan si la ciudad es de ese país. «Remote -
    CO» queda por confirmar porque puede ser Colorado.
  - **PA es Panamá**; Paraguay es **PY**.
- **Rendimiento:** las listas de frases se compilan en una sola expresión. La lectura de cada vacante es más rápida que
  antes (5,2 ms frente a 7,3 ms).

## Efecto medido (inventario del 12 nov, 9.964 vacantes)

| Medida | Antes (v14) | Después (v15) |
|---|---|---|
| Ubicación por confirmar | 439 | 388 |
| Vacantes confirmadas que cambian de país | — | 2 (Nuevo México, EE. UU., antes leídas como México) |
| Pasaban por es/en y quedan fuera por idioma | — | 15 (neerlandés, polaco, vietnamita, ilegibles) |
| Entregables | 3.974 | 3.973 |

Pruebas generadas desde la tabla:
- cada país cubierto se reconoce por sigla y nombre;
- **ningún país extranjero se acepta nunca**;
- las provincias de los países cubiertos nunca se leen como extranjeras;
- los casos ambiguos quedan por confirmar.
