# Aprendizaje autónomo de ubicaciones, solo con código — v17

Revisión del 13 de noviembre de 2026 (decisión de Oscar: el sistema debe aprender y mantenerse **sin IA ni Claude**).
Amplía v16. Sin SQL nuevo (usa las tablas de SQL 014). Tercera y última etapa del plan.

## 1. Las reglas se aplican solas (`buscador/paises.py`)

- `paises.cargar_reglas(filas)` activa las reglas de `panel_reglas_ubicacion`:
  - las del **operador** (exactas, de «Aplicar a las iguales»);
  - las **aprendidas** (frases).
- `paises.elegibles` decide primero con la tabla oficial. **Solo si el resultado queda «por confirmar»** consulta las
  reglas: la exacta para esa ubicación y, si no hay, las frases aprendidas que contiene.
  - Si dos reglas aprendidas se contradicen, no decide.
  - Una regla **nunca cambia un país ya reconocido**. Por ejemplo, «Bogotá, Colombia» sigue siendo Colombia aunque
    exista una regla equivocada.
- **Dónde se cargan:**
  - en la búsqueda de la noche, la pasada de la mañana y las capturas de cada hora (`panel.ejecutor.correr`, desde
    Supabase), y se retiran al terminar;
  - en la revisión de `ofertas` (`limpiar_fuera_objetivo`).
  - Nunca se guardan en `trabajo/` ni en archivos públicos.
- **Efecto:** las vacantes resueltas por una regla dejan de estar «por confirmar». Siguen el camino normal (selección,
  verificación de enlaces, WhatsApp) y ya no llegan a la bandeja. `paises.USOS` cuenta cuántas veces se usó cada regla,
  y se suma a `usos` después de la búsqueda.

## 2. Aprendizaje nocturno (`panel/aprender.py`), determinista y auditable

Antes de cada búsqueda en modo panel se ejecutan estos pasos:

1. **Se leen las decisiones** de la bandeja. Ahora quedan registradas en `panel_revisiones.motivo`, con estos valores:
   - «confirmada por operador»;
   - «otro país (operador)»;
   - «no sirve (operador)»;
   - «decidida por regla».

   Solo enseñan las dos primeras. «No sirve» no dice nada del lugar, y lo decidido por regla no se cuenta dos veces.
2. **Frases candidatas** de cada ubicación decidida: de 1 a 4 palabras seguidas, sin palabras genéricas (remote,
   remoto, N/A, HQ…), sin palabras vacías (de, área, metropolitana, y alrededores, ciudad…) y sin lugares que la tabla
   ya conoce, ni nombres ambiguos o palabras corrientes. Las palabras geográficas comunes (nuevo, pueblo, villa,
   puerto, san, sant…) **nunca forman una frase solas**.
3. **Nace una regla aprendida** cuando la frase aparece en **al menos 2 ubicaciones distintas** (3 si es una sola
   palabra), todas con el mismo resultado y ninguna en contra. Se queda la frase más larga con la misma evidencia: «sant
   cugat», y no también «cugat».
4. **Conflictos:** una regla aprendida que una decisión posterior contradice **se desactiva sola** y suma
   `conflictos`.
5. **No se reactiva sola:** una regla desactivada, por conflicto o a mano, nunca vuelve a activarse por su cuenta.

Los conteos (`aprendidas_nuevas`, `desactivadas_por_conflicto`, `ubicaciones_resueltas_por_reglas`, `reglas_activas`)
quedan en el resumen de la ejecución y en el correo diario («Aprendizaje: …»).

## 3. Control humano

- **«Actividad → Reglas de ubicación»:** cada regla muestra su frase, su resultado, su origen (del operador o
  aprendida), cuántas veces se usó, sus conflictos y un botón «Desactivar»/«Activar».
- Las reglas viven en Supabase: viajan en las copias de seguridad y en el traspaso al cliente.

## 4. Revisión masiva por CSV, también sin IA

- **Qué se guarda y qué se muestra:** la bandeja guarda hasta 300 candidatas. El panel sigue mostrando solo las **10
  más útiles**.
- **«Descargar todas (CSV)»** (`GET /api/revisiones.csv`): todas las pendientes, con las columnas `vacante_id`, `cargo`,
  `empresa`, `ubicacion`, `pista`, `le_serviria_a` y `pais_sugerido` para leer, y `decision`, `pais`,
  `aplicar_a_iguales` y `comentario` para llenar.
- **«Subir revisión»** (`POST /api/revisiones/csv`):
  - aplica cada fila llenada como si fuera un clic en la bandeja, con las mismas reglas y el mismo aprendizaje;
  - acepta comas o punto y coma (Excel en español);
  - entiende «sí/sirve», «otro país», «no sirve» y «saltar»;
  - acepta el país por nombre o por sigla;
  - informa las filas con error y sigue con las demás.

## Depuración completa de la base

La bandeja diaria solo trae dudosas que **hoy** le sirven a algún cliente y se arma al final de la búsqueda de la noche.
Para depurar la base entera antes de entregarla:

- **«Cargar todas las dudosas de la base»** (`POST /api/revisiones/cargar`) llena la bandeja al momento con **todas** las
  vacantes del catálogo «por confirmar» (`reason = elegibilidad regional por confirmar`), sin filtro de fecha y también
  las que hoy no le sirven a ningún cliente (`motivo = depuración completa`, sin perfiles, prioridad baja), hasta 3.000.
  Las reglas activas resuelven solas las que pueden.
- Las cargadas así **no vencen** con la búsqueda de la noche: esperan a la persona hasta 30 días.
- El panel sigue mostrando las 10 más útiles; el CSV («Descargar todas») trae todas.
- **Cada decisión cambia la base al momento:**
  - «Sirve para…» guarda el país en el catálogo (confianza alta, «confirmada por el operador»);
  - «Solo para otro país» y «No sirve» archivan la vacante del catálogo (`reason = descartada por el operador`);
  - si la vacante no le sirve hoy a nadie, no se crean asignaciones ni se exige la búsqueda del día.
- **Cada búsqueda respeta lo decidido** (noche, mañana y cada hora): `bodega` recibe las decisiones
  (`decisiones_operador`) y `confirmar_ubicacion.aplicar_operador` añade la observación «operador» (el país elegido, o
  «país extranjero») o marca `descartada_operador`, que `contrato.entregable` rechaza («descartada por el operador»).
- **La limpieza de `ofertas`** («Revisar y limpiar vacantes fuera del objetivo», v13) lee `panel_revisiones`:
  - lo descartado en la bandeja («otro país» o «no sirve») aparece para borrar con el motivo «descartada por el operador»;
  - lo confirmado se conserva aunque la lectura automática dude;
  - lo saltado sigue en «revisar».
  Borrar sigue exigiendo la huella y «aplicar», como siempre.

## Garantía

Todo el ciclo funciona solo con código:

1. el sistema resuelve lo que puede, con la tabla, la ficha y las reglas;
2. el operador decide lo dudoso;
3. el código aprende de esas decisiones y la bandeja tiende a vaciarse.

Una IA o una persona técnica pueden revisar o ampliar las listas de `datos/`, pero no hacen falta para que el
aprendizaje funcione.
