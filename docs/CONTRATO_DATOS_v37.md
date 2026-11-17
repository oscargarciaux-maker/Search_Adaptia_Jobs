# Contrato de datos v37: más vacantes para quien va corto y cobertura por persona

**Fecha:** 17 de noviembre de 2026. **Sin SQL ni IA.** Viene del documento «Ampliación: cobertura de cargos actuales y
futuros» (revisado con Oscar) y de lo medido en la búsqueda del 16 nov.

## 1. Turnos para quien va corto
- Antes de cada búsqueda (diaria u horaria), el panel mira la última búsqueda registrada: los perfiles con menos de 5,
  y los que no recibieron nada (como los nuevos), son «cortos» (`panel.ejecutor.perfiles_cortos`).
- Sus lugares (país, ciudades, remoto desde su país) van primero, dentro de su cargo, en LinkedIn, Indeed,
  Computrabajo y Elempleo (`buscador.cobertura.configurar_primero` / `va_primero`). Sus avisos de LinkedIn reciben la
  ficha (descripción) antes que los demás.
- Si no se puede leer la última búsqueda, todo reparte como antes.

## 2. Tiempo para leer descripciones
- LinkedIn busca páginas solo hasta la mitad de su tiempo y deja el resto para leer fichas
  (`fraccion_busqueda=0.5`). El 16 nov revisó los 55 lugares pero leyó solo 40 fichas de 765 avisos: sin descripción
  una vacante no se puede entregar.

## 3. Cobertura por persona (`GET /api/cobertura`, panel privado)
- Por perfil activo, en las últimas 14 búsquedas en que existía ese perfil:
  - `hoy`: lo que recibió en la última búsqueda;
  - `dias_con_minimo` de `dias_medidos` (con su denominador);
  - `listas`: vacantes guardadas, con enlace comprobado, que cumplen su ubicación e idioma y que esa persona nunca
    recibió, aunque otro cliente sí;
  - `por_comprobar`: las que cumplen, pero aún no tienen el enlace comprobado;
  - `causa`: por qué le faltan, en palabras.
- Estado: «Mínimo cubierto» (hoy ≥ 5), «Aún sin datos» (menos de 3 búsquedas medidas) o «Mínimo pendiente».
- Totales por cargo, país e idioma, con «N de M días»: el promedio no esconde a un grupo.
- Aviso cuando alguien lleva 3 o más búsquedas seguidas bajo 5. Las metas nunca pasan el cupo diario, porque el
  panel no deja programarlo.
- Solo cuenta lo medido: no reparte el inventario en días ni lo llama probabilidad.

## 4. Oficios nuevos
- Femenino y masculino cuentan igual también con reglas generales: -era/-ero, -ora/-or, -iva/-ivo, -ica/-ico,
  -ada/-ado, -stra/-stro y jefa/jefe. Por ejemplo, «Enfermera» = «Enfermero» y «Coordinadora logística» =
  «Coordinador logístico». La identidad de cada vacante no cambia: usa el enlace o el texto, no esta forma del título.
- Un cargo que solo busca por su nombre lo dice en su tarjeta y pide «Buscar denominaciones afines» (ESCO) para sumar
  nombres en inglés y parecidos. Sin ESCO, el cargo sigue buscando por su nombre y queda marcado para revisión.
- Un oficio parecido no se vuelve equivalente solo: «Auxiliar contable» no es «Contador» y «Docente» no incluye
  «Profesora» sin que alguien lo apruebe.

Pruebas: `pruebas/panel/test_cobertura_v37.py`, que incluye la matriz de oficios contador, enfermero, docente,
ejecutivo de ventas, ingeniero industrial y coordinador logístico.
