# Contrato de datos de ofertas — Adaptia Jobs (v1)

**Para:** quien construye el scraper y cualquier agente futuro · **De:** Adaptia Jobs · **Fecha:** 28 de octubre de 2026

Los nombres/valores v1 siguen en la tabla histórica `ofertas`. El flujo vigente escribe JSON en Supabase; no utiliza
hojas de cálculo. Catálogo/selección y verificación se amplían en [v2](CONTRATO_DATOS_v2.md) y
[v3](CONTRATO_DATOS_v3.md). La sección 3 conserva diseño original de otra etapa, no funciones adicionales garantizadas.

Este documento define **una sola forma de describir una oferta**. La plataforma, el scraper, la IA que analiza ofertas pegadas y los agentes futuros usan **los mismos nombres de campo y los mismos valores permitidos**. Si algo no está aquí, se agrega aquí primero (con versión nueva) y después se usa.

## 1. Cómo se entregan las ofertas

Una fila por enlace de oferta, con estas columnas (nombres en inglés, en minúscula, con guion bajo). Dos enlaces de una
misma vacante pueden producir dos filas v1 y una sola selección canónica v2. El programa envía objetos JSON a Supabase;
los ejemplos CSV al final se conservan como representaciones históricas del vocabulario.

- Solo `job_title` y `company_name` son obligatorios. **Todo lo demás es opcional**: si no se conoce, se deja vacío. Nunca inventes un valor para llenar un campo.
- Las listas se escriben separadas por `|` (por ejemplo `CO|MX`). En JSON también pueden ser arreglos.
- Fechas: `AAAA-MM-DD` (por ejemplo `2026-10-27`). Fecha y hora: `AAAA-MM-DDThh:mm:ssZ`. Otro formato se descarta.
- Números: sin símbolos ni separadores de miles (`4500000`, `4500000.50`).
- Texto en UTF-8. La descripción puede tener saltos de línea (en CSV, entre comillas).

La plataforma **nunca falla por un valor fuera del vocabulario**: lo deja vacío y conserva la fila original completa en su repositorio. Pero un campo vacío significa un filtro que no encuentra la oferta, así que conviene respetar los valores de abajo.

## 2. Campos

### Identidad

| Campo | Obligatorio | Valores / formato | Ejemplo | Notas |
|---|---|---|---|---|
| `external_id` | Recomendado | Texto, único por fuente | `lnkd-4012345678` | Si se envía otra vez, no se duplica. |
| `job_title` | **Sí** | Texto (máx. 300) | `Senior Data Engineer` | Título exacto, sin prefijos ni sufijos de la plataforma. |
| `company_name` | **Sí** | Texto (máx. 300) | `Rappi` | |
| `offer_url` | Recomendado | URL completa | `https://www.linkedin.com/jobs/view/4012345678/` | Se limpian los parámetros de seguimiento. Una oferta puede tener **varios enlaces**: manda una fila por enlace con el mismo contenido y se unen sola. |
| `source_portal` | No | Texto | `LinkedIn` | Si falta, se deduce del dominio del enlace. |
| `status` | No | `active` (por defecto) o `expired` | `expired` | `vencida`, `cerrada` y `closed` también se entienden como vencida. |

### Fechas

| Campo | Valores / formato | Ejemplo | Notas |
|---|---|---|---|
| `published_date` | `AAAA-MM-DD` | `2026-10-27` | Fecha **real** de publicación. Si no se sabe, déjala **vacía**: la plataforma usa la fecha de carga. No pongas la fecha del día por defecto. |
| `scraped_at` | Fecha y hora ISO | `2026-10-28T08:00:00Z` | Cuándo la capturó el scraper. |

La plataforma guarda siempre la **fecha de carga** y calcula una **fecha de referencia** (`posted_on`) = fecha de publicación o, si no existe, la de carga. Con esa fecha filtra "publicadas hace 24 h / 7 días / 30 días".

### Ubicación (dos preguntas distintas)

**¿Dónde queda el puesto?** y **¿quién puede postularse?**

| Campo | Valores / formato | Ejemplo | Notas |
|---|---|---|---|
| `location` | Texto libre | `Bogotá, Colombia · Híbrido` | Tal como aparece en la oferta. |
| `work_mode` | `remote` · `hybrid` · `onsite` | `hybrid` | También se entiende `remoto`, `híbrido`, `presencial`. (`modality` es un nombre alternativo.) |
| `office_city` | Texto | `Bogotá` | Ciudad de la sede/puesto. Vacío si es remoto sin sede. |
| `office_country` | Código de país de 2 letras | `CO` | También se entiende el nombre común (`Colombia`). |
| `hire_scope` | `city` · `country` · `region` · `worldwide` | `region` | Quién puede postularse (ver abajo). |
| `hire_countries` | Lista de países (2 letras) | `CO\|MX` | Países permitidos cuando `hire_scope` es `country` o `city`. |
| `hire_regions` | Lista: `LATAM` · `NA` · `EU` · `APAC` · `MEA` | `LATAM` | Solo cuando `hire_scope` es `region`. |

Cómo llenar `hire_scope`:

| La oferta dice | `work_mode` | `hire_scope` | `hire_countries` / `hire_regions` | `office_city` / `office_country` |
|---|---|---|---|---|
| "Remoto – LATAM" | remote | region | `LATAM` | vacío |
| "Híbrido en Bogotá" | hybrid | city | `CO` | `Bogotá` / `CO` |
| "Remoto desde México" | remote | country | `MX` | vacío |
| "Remote, open worldwide" | remote | worldwide | vacío | vacío |
| "Presencial en Medellín" | onsite | city | `CO` | `Medellín` / `CO` |
| "Remote – Europe" | remote | region | `EU` | vacío |
| La oferta no lo aclara | (lo que se sepa) | **vacío** | vacío | (lo que se sepa) |

Regiones: `LATAM` América Latina · `NA` Norteamérica (EE. UU. y Canadá) · `EU` Europa · `APAC` Asia-Pacífico · `MEA` Medio Oriente y África.

### Idioma

| Campo | Valores / formato | Ejemplo | Notas |
|---|---|---|---|
| `posting_language` | `es` · `en` | `en` | Idioma en que está **escrita** la oferta. **Por ahora solo se aceptan `es` y `en`**: una oferta en otro idioma (portugués, francés…) no entra al catálogo; su fila queda guardada en el repositorio con la razón. (`language` es un nombre alternativo; se entiende `Español`, `English`, etc.) |
| `language_requirements` | Lista de `idioma:nivel:obligatorio` separada por `\|`, o arreglo JSON | `en:B2:1\|fr:A2:0` | Idiomas que la oferta **pide** o valora. `idioma` = código de 2 letras (`en`, `es`, `pt`, `fr`, `de`…). `nivel` = `A1`, `A2`, `B1`, `B2`, `C1`, `C2` o `native` (vacío si no lo dicen). `obligatorio` = `1` o `0` (por defecto `1`). En JSON: `[{"language":"en","level":"B2","required":true}]`. |

Equivalencias de nivel cuando la oferta usa palabras: básico = A2 · intermedio / conversacional = B1 · intermedio alto = B2 · avanzado / fluido = C1 · bilingüe / nativo = native.
No agregues el idioma en que está escrita la oferta como requisito si la oferta no lo pide.

### Perfil buscado

| Campo | Valores / formato | Ejemplo | Notas |
|---|---|---|---|
| `employment_type` | `full_time` · `part_time` · `contract` · `internship` · `freelance` | `full_time` | También se entiende `tiempo completo`, `pasantía`, `prestación de servicios`… |
| `seniority` | `intern` · `junior` · `mid` · `senior` · `lead` | `mid` | Ver equivalencias abajo. |
| `years_experience_min` | Entero 0–40 | `3` | Años mínimos que pide la oferta. |
| `years_experience_max` | Entero 0–40 | `5` | Solo si la oferta da un rango. "5+ años" → min 5, max vacío. |

Equivalencias de `seniority` y bandas de filtro (la plataforma calcula las bandas sola):

| Valor | Se usa para | Banda de filtro |
|---|---|---|
| `intern` | Practicante, pasante, aprendiz, trainee | Practicante |
| `junior` | Junior, Jr, entry level | 0–3 años |
| `mid` | Semi senior, mid-level, intermedio | 0–3 y 4–7 años |
| `senior` | Senior, Sr, principal, staff | 4–7 años |
| `lead` | Líder, lead, manager, gerente, head, director | 8+ años |

Si hay años, mandan los años: 0–3 → banda "0–3 años"; 4–7 → "4–7 años"; 8 o más → "8+ años o líder". Una oferta de "3 a 5 años" aparece en las dos bandas. Una oferta con cargo `lead` aparece siempre en "8+ / líder, manager, head". Si la oferta no dice años ni cargo, `seniority` va vacío.

### Sector y habilidades

| Campo | Valores / formato | Ejemplo | Notas |
|---|---|---|---|
| `industries` | Lista de claves (máx. 5), separadas por `\|` | `fintech\|banca` | Sector de la **empresa o su producto**, no del cargo. Solo claves de la lista cerrada de abajo (también se entiende el nombre en español o inglés). |
| `keywords_role` | Lista | `Product Management\|B2B` | Cargo, seniority, tipo de cliente. Máx. 20. |
| `keywords_technical` | Lista | `Python\|SQL\|Airflow` | Herramientas, metodologías, hard skills, certificaciones. Máx. 40. |
| `keywords_soft` | Lista | `Liderazgo\|Comunicación` | Habilidades blandas. Máx. 20. |

Las palabras clave van en el idioma original de la oferta, de más a menos importante. Si el scraper no las extrae, déjalas vacías: la plataforma las completa con IA.

**Sectores (`industries`):** `tecnologia` Tecnología y software · `datos_ia` Datos e inteligencia artificial · `ciberseguridad` · `telecomunicaciones` · `fintech` Fintech y pagos · `banca` Banca y servicios financieros · `seguros` · `salud` Salud y farmacéutica · `educacion` Educación y formación · `retail_ecommerce` Retail y comercio electrónico · `consumo_masivo` Consumo masivo y alimentos · `manufactura` Manufactura e industria · `automotriz` Automotriz y movilidad · `construccion` Construcción e inmobiliario · `energia` Energía, petróleo y gas · `mineria` · `agroindustria` · `logistica` Logística y transporte · `turismo` Turismo y hotelería · `medios` Medios y entretenimiento · `marketing` Marketing y publicidad · `consultoria` · `servicios_prof` Servicios profesionales (legal, contable, RR. HH.) · `gobierno_ong` Sector público y ONG · `bpo` BPO y contact center · `moda_textil` · `quimica` Química y materiales · `videojuegos` · `sostenibilidad` Sostenibilidad y medio ambiente · `otros`.

### Compensación

| Campo | Valores / formato | Ejemplo | Notas |
|---|---|---|---|
| `salary_text` | Texto literal | `COP 3.000.000 – 4.000.000 al mes` | Solo si trae **cifras**. "Competitivo" o "según experiencia" van vacío. |
| `salary_min` | Número | `3000000` | Solo si `salary_text` tiene cifras. |
| `salary_max` | Número | `4000000` | Solo si es un rango. |
| `salary_currency` | Código de 3 letras | `COP` | `COP`, `USD`, `MXN`, `EUR`… |
| `salary_period` | `hour` · `month` · `year` | `month` | También se entiende `hora`, `mensual`, `anual`. |

### Contenido

| Campo | Valores / formato | Notas |
|---|---|---|
| `description_full` | Texto (máx. 30.000) | **Todas** las secciones de la oferta: responsabilidades, requisitos, beneficios, compensación. Sin menús, botones ni ofertas relacionadas. Con menos de ~200 caracteres no se puede detectar duplicados por contenido. |
| `company_about` | Texto (máx. 3.000) | Sección "Acerca de la empresa". |
| `summary` | Texto (máx. 2.000) | Opcional; la plataforma lo genera con IA si falta. |
| `apply_email` | Correo | Solo si la oferta lo trae. |
| `company_website` | URL o dominio | Solo si aparece. |

Cualquier columna adicional que mande el scraper (por ejemplo `search_tag`) **no se pierde**: se guarda aparte en un campo de extras (hasta 20 columnas, 500 caracteres cada una).

## 3. Diseño original de la plataforma receptora (histórico)

1. **Idioma:** si `posting_language` es un idioma distinto de `es`/`en`, la fila **no entra al catálogo** (queda guardada con el motivo).
2. **Duplicados:** primero por enlace (sin parámetros de seguimiento; en LinkedIn solo cuenta el número de la oferta) y luego por contenido (empresa + cargo + descripción iguales). Misma oferta con otro enlace → el enlace se **agrega** a la oferta existente. Si cambia el cargo o la descripción, es **otra oferta**.
3. **Nunca sobrescribe:** una oferta que ya existe no se modifica por una nueva fila. Solo se le agregan enlaces, o se marca vencida si la fila trae `status = expired`.
4. **Repositorio propio:** toda fila recibida se guarda tal cual llegó, aunque se omita o falle. Si la hoja de origen se daña, las ofertas y los procesos de los clientes no se afectan.
5. **Límites:** el adaptador v1 vigente envía hasta 500 objetos JSON por llamada a Supabase.

## 4. Ejemplos

**Remoto para Latinoamérica, en inglés, con requisito de inglés:**

```csv
external_id,job_title,company_name,offer_url,published_date,location,work_mode,hire_scope,hire_regions,posting_language,language_requirements,seniority,years_experience_min,years_experience_max,industries,keywords_technical,employment_type
lnkd-4012345678,Senior Data Engineer,Alfa Labs,https://www.linkedin.com/jobs/view/4012345678/,2026-10-27,Remote - LATAM,remote,region,LATAM,en,en:B2:1,senior,5,7,tecnologia|datos_ia,Python|SQL|Airflow,full_time
```

**Híbrido en Bogotá, en español, con sueldo y sin fecha de publicación (queda la fecha de carga):**

```csv
external_id,job_title,company_name,offer_url,location,work_mode,office_city,office_country,hire_scope,hire_countries,posting_language,seniority,years_experience_min,years_experience_max,industries,salary_text,salary_min,salary_max,salary_currency,salary_period
cc-88231,Analista Junior de Riesgo,Banco Beta,https://empleos.beta.com/88231,"Bogotá, Colombia (híbrido)",hybrid,Bogotá,CO,city,CO,es,junior,0,2,banca,"COP 3.000.000 - 4.000.000 al mes",3000000,4000000,COP,month
```

## 5. Cambios de este contrato

Cualquier campo o valor nuevo se agrega primero a este documento (con número de versión), luego a la base de datos, y después al scraper y a la IA. Nadie inventa campos por su cuenta. Versión actual: **v1** (28 oct 2026).
