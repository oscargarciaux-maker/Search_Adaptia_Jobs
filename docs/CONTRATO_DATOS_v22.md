# Contrato de datos v22 — restricciones, prioridades, margen de años y nivel según la experiencia

Vigente desde el 14 nov 2026, a pedido del cliente en la reunión del 14 nov (puntos 3.2 y 5). Amplía el perfil del
panel (v8, v20, v21). Sin columnas nuevas en `ofertas` ni SQL: la configuración se guarda como JSON. Todo es código con
pruebas; **sin IA**.

## Campos nuevos del perfil

- **`margen_experiencia`**: 3 o 4 (por defecto 3). Con `experiencia_anos` busca vacantes que pidan de N años menos a N
  años más (v20 fijaba 3).
- **`restricciones`**: «Este perfil NO acepta…», hasta 10 reglas. Cada una descarta **solo con evidencia clara en el
  aviso**; sin el dato, nunca descarta.
  - `{"tipo": "salario_minimo", "monto": >0, "moneda": "USD", "periodo": "month"}`. Se compara solo si el aviso trae
    **la misma moneda**. El periodo se convierte (un año = 12 meses); por hora solo se compara con hora. Descarta si el
    máximo del aviso (o su único valor) es menor que el monto.
  - `{"tipo": "palabras", "palabras": [...]}` (hasta 30): descarta si el título o la descripción las mencionan como
    palabras completas. **Lo que el aviso pide solo como deseable no descarta** (pedido de Oscar, 14 nov): no cuentan
    las oraciones con marcas como «deseable», «se valora», «plus», «nice to have», «bonus», «preferred»,
    «idealmente» u «opcional», ni las secciones cuyo encabezado es de ese tipo («Nice to have:», «Deseable»,
    «Preferred qualifications»), hasta el siguiente encabezado. En el título siempre descarta. Las marcas están en
    `panel/afinidad.MARCAS_DESEABLE` y se pueden ampliar.
  - `{"tipo": "contrato", "tipos": [...]}` entre `freelance`, `part_time`, `contract` e `internship`: descarta si el
    aviso es de ese tipo (`contrato.tipo_contrato`).
- **`sectores_preferidos`** y **`palabras_preferidas`** (hasta 30 cada uno, de 2 a 60 caracteres): **solo ordenan,
  nunca descartan.** Cuando hay más candidatas que el cupo, se eligen primero las que mencionan más términos preferidos
  en el título, la descripción o la empresa. Vacíos: no cambian nada (como conviene a QA).

## Nivel según la experiencia (automático)

Solo para perfiles con `experiencia_anos`:
- **5 años o más:** se descartan las vacantes de nivel junior, trainee, pasantía o prácticas (por el título o por el
  tipo de contrato).
- **2 años o menos:** no se aplica el filtro de experiencia; entra cualquier vacante de entrada.
- En medio: el margen normal.

## Lo que sigue igual

- Las ampliaciones (v9, v11) nunca relajan restricciones ni el nivel: solo lo que ya relajaban.
- La estimación del panel ve el título, no la descripción: las palabras restringidas se buscan solo en el título, así
  que puede quedar un poco por encima de lo que la selección nocturna entrega.
- `ofertas`, el CSV del contrato y la regla de no inventar datos.
