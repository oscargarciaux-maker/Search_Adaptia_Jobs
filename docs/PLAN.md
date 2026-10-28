# Buscador de vacantes LATAM — Plan de la versión 1

28 de octubre de 2026. Copia del documento de planeación (Claude Docs). Si cambia una decisión, se actualiza aquí.
Nota: el plan llamaba al repositorio `buscador-vacantes-latam`; el repositorio real es `search_adaptia_jobs`.

## Resumen

La versión 1 es una página privada donde Oscar escribe un cargo y un país de LATAM y, en segundos, ve todas las vacantes
abiertas de ese cargo y de sus cargos parecidos de los últimos 30 días, listas para copiar al grupo de WhatsApp o bajar
en Excel.

- **Para quién:** Oscar, que asesora a personas de toda LATAM que buscan trabajo en tecnología y áreas creativas. Al
  final se le entrega a otra persona, que debe poder usarlo sin que nada se rompa.
- **Qué prioriza:** volumen. Pocos filtros duros; lo demás (inglés, nivel, años) va como dato visible.
- **Qué no hace:** no usa la cuenta de LinkedIn de nadie, no envía mensajes y no usa IA en la búsqueda diaria.
- **Dónde se construye:** en un repositorio nuevo de GitHub, aparte del agente personal de Oscar (`ux_job_agent`, que no
  se toca).
- **Cuánto cuesta operar:** entre USD 20 y 80 al mes, casi todo de Apify; se mide en la primera semana.

## Requisitos ya decididos

Estas reglas las fijó Oscar el 28 de octubre de 2026; quien construya no las cambia sin preguntarle.

| Tema | Regla |
| --- | --- |
| Cómo se usa | A pedido: Oscar escribe un cargo y elige un país; no es una lista diaria fija |
| Cargos | Cualquier cargo que escriba. Devuelve el exacto, los similares y los cercanos, de todos los niveles (trainee a lead). Ejemplo: «product design» trae UX/UI, UX Research, Product Owner, Lead Product Design |
| Herramientas | También cuentan las herramientas del oficio: un aviso que pide CapCut o Premiere es de edición de video aunque el título sea raro |
| Países | Toda LATAM. Al elegir un país salen las vacantes de ese país más todas las remotas a las que se puede aplicar desde él |
| Antigüedad | Hasta 30 días |
| Inglés, nivel, años | No filtran: se muestran como columnas |
| Enlaces | Solo donde se postula de verdad. Fuera agregadores y sitios de pago (Jooble, BeBee, trabajo.org, JobLeads, Talent.com…) |
| Enlace principal | El de LinkedIn cuando la vacante está ahí (para ver empresa y reclutadores); el directo de la empresa va en otra columna |
| LinkedIn | Nunca con la sesión de nadie ni con su cookie |
| Entrega | Un solo grupo de WhatsApp; Oscar copia y pega. Sin envío automático |
| Dispositivo | Sobre todo computador; también celular |
| Presupuesto | Sin tope por ahora, pero con límite de gasto configurado en cada servicio |
| Tokens | La búsqueda diaria no usa IA |
| Traspaso | Todo debe poder pasarse a otra persona sin romperse |

## Arquitectura

La versión 1 tiene dos piezas: GitHub recoge y publica las vacantes cada noche, y Cloudflare sirve la página privada
donde Oscar busca. Ninguna depende de la cuenta de Google de Oscar, así se puede traspasar.

```
Fuentes ──► GitHub: bodega.yml (cada noche) ──► rama publicado (página + datos) ──► Cloudflare Pages (la página)
  LinkedIn · Apify          recoge, clasifica enlaces,                              Access: solo correos autorizados
  LinkedIn · JobSpy         asigna familias y países,                               KV: enviadas (igual en PC y celular)
  Indeed · JobSpy           etiqueta, quita repetidas,                              Función profunda ──► profunda.yml
  Greenhouse, Lever…        revisa abiertas (30 días)                                        │
  Tableros remotos        datos/: mapa de cargos, países, dominios, empresas                 ▼
  Brave: más empresas                                                               Oscar: copia a WhatsApp o baja Excel
```

Las fuentes entran a la bodega nocturna, que publica en la rama `publicado`. La página lee esa rama y busca en el
navegador. La función de búsqueda profunda es el único camino de vuelta: lanza en GitHub una búsqueda en vivo cuando
Oscar la pide.

## Mapa de cargos

El mapa de cargos es un archivo de datos (`datos/mapa_cargos.yaml`) con unas 60 familias al inicio; la búsqueda y la
página lo leen, y crece sin tocar código.

**Qué tiene cada familia:**

| Campo | Para qué | Ejemplo (diseño de producto) |
| --- | --- | --- |
| `id`, `nombre`, `area` | Identificarla y agruparla en la página | `diseno-producto`, Diseño de producto, Diseño |
| `exactos` | Títulos del mismo cargo en español, inglés y portugués | Product Designer, Product Design, Diseñador de producto, Designer de Produto |
| `similares` | Cargos que hacen casi lo mismo | UX/UI Designer, UX Designer, UI Designer, Diseñador de experiencia de usuario, Interaction Designer, UX Researcher, Design Systems Designer |
| `cercanos` | Cargos vecinos que también le pueden servir a la persona | Product Owner, Product Manager, Service Designer, UX Writer, CX Designer, Web Designer |
| `herramientas` | Palabras del oficio que se buscan en la descripción | Figma, prototipos, design system, usabilidad |
| `excluir` | Palabras que delatan otro oficio con título parecido | UI Artist de videojuegos, Unreal, diseño industrial de manufactura |
| `consultas` | Los 4 a 8 términos que se mandan a las fuentes (no todos los títulos: así cuesta menos) | product designer, diseñador ux ui, ux designer, diseñador de producto |

**Niveles:** el programa quita y agrega solo trainee, junior, jr, semi senior, ssr, mid, senior, sr, lead, líder, head,
staff, principal, I/II/III. No se escriben en el mapa. El nivel de cada vacante se guarda como columna.

**Cómo se decide si una vacante es de una familia (sin IA):**

1. Se normaliza el título: minúsculas, sin tildes, sin nivel, sin ciudad entre paréntesis, sin «remote» ni «(m/f)».
2. Contiene un título de `exactos` → **exacto**. De `similares` → **similar**. De `cercanos` → **cercano**.
3. Si no, una comparación aproximada de palabras (90 de 100 o más contra un título del mapa) → **similar**.
4. Si no, el título trae una palabra genérica del oficio (editor, diseñador, desarrollador…) y la descripción trae 2 o
   más `herramientas` → **cercano**.
5. Si aparece una palabra de `excluir`, no entra.

Una vacante puede quedar en varias familias. Cada una guarda su nivel de coincidencia y la página lo muestra.

**Cómo crece el mapa:**

- **Al construirlo:** la IA escribe las 60 familias una sola vez. Lista inicial de áreas: diseño (producto, UX/UI,
  research, web, gráfico, ilustración, motion), video y audio, desarrollo (frontend, backend, fullstack, móvil,
  videojuegos, WordPress/no-code), QA, datos (análisis, ciencia, ingeniería, BI), IA/ML, infraestructura (DevOps, cloud,
  redes, soporte), seguridad, producto y proyectos (PO, PM, Scrum), contenido (copy, redacción, community, SEO),
  marketing digital, ventas y éxito del cliente en tecnología, RR. HH. tech y reclutamiento.
- **Cada noche:** el programa guarda los títulos que llegaron y no encajaron en ninguna familia, con cuántas veces
  aparecieron, en `reportes/titulos_sin_familia.csv`.
- **A pedido:** con la skill `ampliar-mapa`, Claude lee solo ese archivo corto, propone dónde va cada título y Oscar
  aprueba. Así se gastan pocos tokens.
- **Cargo nuevo:** si Oscar escribe algo que no está en el mapa, la página busca esas palabras tal cual en todos los
  títulos. Para crear la familia se usa la skill `nueva-familia`.
- **Más adelante:** importar los títulos alternativos de ESCO, el catálogo público de ocupaciones de la Unión Europea,
  para ampliar sin IA.

## Países: desde dónde se puede aplicar

Cada vacante lleva la lista de países de LATAM desde los que se puede postular; al elegir un país en la página salen las
de ese país más todas las remotas que lo incluyen.

**Archivo `datos/paises.yaml`:** los 19 países de LATAM continental más Cuba, República Dominicana y Puerto Rico. Por
cada uno: código ISO, nombres en español, inglés y portugués, gentilicio, las ciudades principales y su zona horaria
(por ejemplo Venezuela UTC−4, México UTC−6, Brasil UTC−3).

**Regla (una función sin IA, con pruebas):**

| El aviso dice | Pueden aplicar | Confianza |
| --- | --- | --- |
| Presencial o híbrido en una ciudad o país | Ese país | Alta |
| Remoto limitado a una lista («Remote — Mexico, Colombia») | Esos países | Alta |
| Remoto LATAM, Latin America, Américas, Sudamérica | Todos los de LATAM | Alta |
| Remoto Worldwide, Anywhere, Global | Todos los de LATAM | Alta |
| Remoto con zona horaria («UTC−3 a UTC−6», «EST overlap») | Los países que caen en esa franja | Media |
| Remoto «solo EE. UU.», «must reside in», Europa, India | Ninguno: no se guarda | Alta |
| Remoto en un país («Remote, Brazil») | Ese país | Media |
| Remoto sin decir dónde | Todos, con la marca «confirmar región» | Baja |

La regla mira primero el campo de ubicación y el título, y después la descripción solo para frases de restricción
(«must be based in», «only candidates from»). En la página, el filtro «confianza» permite esconder las de confianza baja.

Ejemplo: Oscar elige Venezuela y salen las presenciales en Caracas o Valencia, las remotas para Venezuela, las remotas
LATAM o mundiales y las de franja horaria que incluye UTC−4.

## Fuentes y enlaces originales

La versión 1 usa LinkedIn (por Apify, con JobSpy de respaldo), Indeed, los sistemas de postulación de empresas y los
tableros remotos. Toda vacante debe terminar en un enlace donde se postula de verdad, o no se guarda.

| Fuente | Cómo se lee | Qué aporta | Versión |
| --- | --- | --- | --- |
| LinkedIn empleos | Actor de Apify sin sesión; si falla, el buscador público de LinkedIn con JobSpy (pausas y espera ante bloqueos) | El mayor volumen de LATAM y remoto | 1 |
| Indeed | JobSpy, un sitio por país que Indeed tenga en LATAM | Avisos locales | 1 |
| Sistemas de postulación (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee) | Sus API públicas, gratis | Avisos originales y siempre abiertos | 1 |
| Tableros remotos (Himalayas, Remotive, RemoteOK, Jobicy, Get on Board, We Work Remotely, Working Nomads) | Sus API o RSS; se guarda solo el enlace original al que llevan | Remotos LATAM y mundiales | 1 |
| Brave Search | Busca empresas que usan Greenhouse, Lever o Ashby y las agrega a la lista de empresas | Hace crecer la fuente de sistemas de postulación | 1 |
| Portales locales (Computrabajo, Bumeran, OCC, Laborum, Multitrabajos, Gupy) | Un lector por portal | Avisos locales por país | 2 |
| Publicaciones de LinkedIn | Actor de Apify sin sesión | Vacantes no publicadas formalmente; mucho ruido | 2, en pestaña aparte |

**Lista de empresas con sistema de postulación (`datos/empresas_ats.csv`).** Crece de tres formas:

1. Con listas públicas de tableros.
2. Con las empresas que aparecen en LinkedIn: el programa prueba su nombre en cada sistema, como ya hace el agente de
   Oscar.
3. Con Brave, buscando cosas como `site:jobs.lever.co remote latam`.

Cada empresa se revisa cada noche gratis.

**Regla de enlaces (función con pruebas, sin IA).** Cada enlace se clasifica en uno de tres tipos:

- **Original:** un sistema de postulación (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Teamtailor, Recruitee,
  BambooHR, Workday, Gupy, iCIMS, Jobvite, Breezy, Personio) o la página de empleo de la propia empresa.
- **Portal directo:** sitios donde se postula ahí mismo, como LinkedIn, Indeed, Computrabajo, elempleo, Bumeran, Get on
  Board o Magneto.
- **Agregador:** sitios que solo copian el aviso o cobran: Jooble, BeBee, trabajo.org, JobLeads, Talent.com, Jobted,
  Sercanto, buscojobs, Jora, Careerjet, Adzuna, Jobrapido, WhatJobs, vacantes.com y los tableros remotos. Para estos, el
  programa sigue el botón de postular hasta el original. Si no lo encuentra, la vacante no se guarda.

La lista de dominios vive en `datos/dominios.yaml`, para agregar sin tocar código.

**Enlaces que se guardan:** `enlace` es el de LinkedIn si existe; si no, el original. `enlace_directo` es el de la
empresa cuando LinkedIn redirige a ella.

**Llamadas en la búsqueda nocturna:** solo avisos de las últimas 24 horas (en LinkedIn, el filtro de tiempo de 1 día),
con las `consultas` de cada familia. Cada familia se busca en cada país, en «Latin America» y en remoto mundial. La
primera corrida es especial: trae los 30 días completos.

## Bodega nocturna

Todas las noches, hacia la 1:17 de Bogotá, un flujo de GitHub Actions (`bodega.yml`) recoge, limpia y publica las
vacantes en Python, sin IA. Debe tardar menos de 45 minutos.

1. **Recoger** de cada fuente, por familia y país. Cada fuente es un módulo aparte (`fuentes/<nombre>.py`) que devuelve
   vacantes en un formato común. Si una falla, se registra y las demás siguen.
2. **Clasificar el enlace** (original, portal directo o agregador) y rastrear el original de los agregadores.
3. **Asignar familias** con el mapa de cargos y descartar las que no encajan en ninguna (sus títulos van al reporte de
   títulos sin familia).
4. **Calcular países** con la regla de países.
5. **Etiquetar:** idioma del aviso (español, inglés o portugués), inglés pedido (no, básico, intermedio, avanzado,
   fluido, nativo), nivel, años mínimos, modalidad, salario si lo publica y herramientas detectadas. Todo con reglas de
   texto.
6. **Quitar repetidas:** misma empresa normalizada (sin S.A.S., Inc., Ltda.) y mismo título sin ciudad, o la misma
   descripción completa. Al juntar copias, se queda el enlace de LinkedIn como principal y el de la empresa como directo.
7. **Revisar las de días anteriores:** las de sistemas de postulación siguen abiertas si siguen en su lista; las de
   LinkedIn se revisan una vez por semana por su página pública («No longer accepting applications»). Se borran las de
   más de 30 días y las cerradas.
8. **Publicar:** escribe los datos por familia (`datos_publicados/<familia>.json.gz`), un índice de títulos y el reporte
   de salud. Luego hace un único commit forzado en la rama `publicado` con la página y los datos, de donde Cloudflare los
   sirve.

**Datos de cada vacante:**

| Campo | Contenido |
| --- | --- |
| `id` | Huella de empresa + título + país normalizados |
| `titulo`, `empresa`, `ubicacion` | Como los publica el aviso |
| `familias` | Lista de familia + coincidencia (exacto, similar, cercano) |
| `paises`, `confianza_pais`, `modalidad` | De la regla de países |
| `idioma`, `ingles`, `nivel`, `anos_min`, `salario`, `herramientas` | Etiquetas |
| `fecha_publicacion`, `visto_primera_vez`, `visto_ultima_vez` | Fechas; si el aviso no trae fecha, se usa la primera vez que se vio, con la marca «fecha sin confirmar» |
| `fuente`, `enlace`, `enlace_directo`, `tipo_enlace` | Origen y enlaces |
| `resumen` | Primeros 300 caracteres de la descripción (para que los datos pesen poco) |

La descripción completa no se publica; solo se guarda dentro del repositorio para la deduplicación de la siguiente noche.

**Orden por defecto en la página:**

1. Coincidencia: exacto, luego similar, luego cercano.
2. Fecha, de la más nueva a la más vieja.
3. Enlace original o portal directo antes que uno rastreado.
4. Variedad: máximo 3 seguidas de la misma empresa.

## Página web

La página es un sitio estático en Cloudflare Pages, protegido con Cloudflare Access para que solo entren los correos
autorizados. La búsqueda corre en el navegador sobre los datos publicados, así responde en segundos y sin servidor.

**Pantallas:**

| Pantalla | Qué hace |
| --- | --- |
| Buscar | Campo de texto con sugerencias de familias mientras se escribe («ux» sugiere Diseño de producto, UX Research, Diseño web). Selector de país con toda LATAM y «Cualquiera». Interruptores: incluir remotas, incluir presenciales, solo confianza alta. Antigüedad: 7, 14 o 30 días. Ocultar las ya enviadas |
| Palabras | Los títulos de la familia agrupados en exactos, similares y cercanos, cada uno con su casilla para quitarlo o dejarlo, y un campo para agregar palabras sueltas a esta búsqueda |
| Resultados | Total y cuántas son exactas, similares o cercanas. Tabla en computador y tarjetas en celular: cargo, empresa, dónde se puede aplicar, modalidad, idioma, inglés, nivel, fecha y enlace. Filtros rápidos por nivel, idioma e inglés. Casillas para elegir cuáles mandar |
| Acciones | «Copiar para WhatsApp», «Descargar Excel», «Marcar como enviadas» y «Búsqueda profunda» |
| Salud | Cuándo corrió la última búsqueda, cuántas trajo cada fuente, qué falló y cuánto se gastó en Apify |
| Mapa | Las familias con sus títulos (solo lectura en la versión 1) y los títulos sin familia más frecuentes |

**Copiar para WhatsApp** arma un texto con un encabezado y un bloque por vacante. Se corta en mensajes de 15 vacantes si
son muchas:

```
*Vacantes de Product Designer · Venezuela y remoto · 28 oct*

*Senior Product Designer* — Empresa X
Remoto LATAM · Inglés avanzado · hace 3 días
https://www.linkedin.com/jobs/view/...
```

**Excel:** se genera en el navegador con la librería SheetJS. Columnas: cargo, coincidencia, empresa, países, modalidad,
idioma, inglés, nivel, años, salario, fecha, fuente, enlace, enlace directo y resumen.

**Enviadas:** se guardan en Cloudflare KV, gratis, con una función pequeña (`functions/api/enviadas.js`). Así el
computador y el celular ven lo mismo, sin repetir vacantes en el grupo. Tiene un botón para exportar e importar ese
historial.

**Búsqueda profunda:** otra función (`functions/api/profunda.js`) lanza en GitHub el flujo `profunda.yml` con el texto y
el país. Busca en vivo en todas las fuentes, suma lo nuevo a la bodega y vuelve a publicar en unos 10 minutos. La página
muestra el estado.

**Estándares de diseño:** primero celular y después computador, contraste WCAG 2.2 AA, botones de 44 px, estados vacío,
cargando y error. Se revisa con capturas a 390 y 1280 px. Los datos de cada familia se cargan solo cuando se buscan, para
que el celular no descargue todo.

## Estructura del repositorio

Todo el código vive en este repositorio; no se crea código en ningún otro lado. Cloudflare, Apify y Brave solo se
configuran desde sus paneles.

```
search_adaptia_jobs/
├── CLAUDE.md                  reglas del proyecto para cualquier sesión de Claude
├── README.md                  qué es y cómo se usa
├── docs/
│   ├── PLAN.md                este documento
│   ├── INSTALACION.md         cuentas, secretos y clics, paso a paso
│   └── TRASPASO.md            cómo entregarlo a otra persona
├── datos/                     se editan sin tocar código
│   ├── config.yaml
│   ├── mapa_cargos.yaml
│   ├── paises.yaml
│   ├── dominios.yaml          originales, portales directos y agregadores
│   └── empresas_ats.csv
├── buscador/                  Python 3.12
│   ├── fuentes/               un módulo por fuente (linkedin_apify, linkedin_publico, indeed, ats, remotos, brave)
│   ├── normalizar.py          títulos, empresas, niveles
│   ├── familias.py            mapa de cargos y coincidencia
│   ├── paises.py              desde dónde se puede aplicar
│   ├── enlaces.py             tipo de enlace y rastreo del original
│   ├── etiquetas.py           idioma, inglés, nivel, años, salario
│   ├── bodega.py              repetidas, retención de 30 días, revisión de abiertas
│   ├── publicar.py            datos por familia, índice, salud
│   └── diagnostico.py         revisa claves y fuentes
├── web/                       la página, sin framework
│   ├── index.html
│   ├── app.js                 pantalla
│   ├── motor.js               búsqueda, filtros, texto de WhatsApp (lógica pura, con pruebas)
│   └── estilos.css
├── functions/api/             funciones de Cloudflare: enviadas.js, profunda.js
├── pruebas/                   pruebas de Python y de motor.js, con ejemplos reales anonimizados
├── reportes/                  salud.json, titulos_sin_familia.csv (los escribe la bodega)
├── .claude/skills/            skills del proyecto (sección siguiente)
└── .github/workflows/
    ├── pruebas.yml            en cada push y PR
    ├── bodega.yml             cada noche + a mano (modo 30 días)
    ├── profunda.yml           a pedido desde la página
    └── diagnostico.yml        a mano
```

**Ramas:** `main` tiene el código y los datos de trabajo. `publicado` tiene un solo commit, reescrito cada noche, con la
página y los datos publicados; Cloudflare Pages sirve esa rama.

**Configuración:** nada personal en el código. Lo que cambia entre dueños va en los secretos de GitHub y de Cloudflare, o
en `datos/config.yaml`: países activos, hora de la bodega, actor de Apify elegido y topes de gasto.

## Skills, agentes y uso de IA

La versión 1 necesita cuatro skills y ningún agente. Las skills viven dentro del repositorio (`.claude/skills/`) para que
viajen con él al traspaso; no hay que crear nada en la cuenta de Claude de Oscar.

| Skill | Cuándo se usa | Qué lee (para gastar poco) | Qué entrega |
| --- | --- | --- | --- |
| `nueva-familia` | «Agrega la familia ingeniero de datos» | Solo el esquema y una familia de ejemplo del mapa | La familia nueva en `mapa_cargos.yaml`, con las pruebas pasando, en un PR |
| `ampliar-mapa` | «Revisa los títulos sin familia» | Solo `reportes/titulos_sin_familia.csv` (los 100 más frecuentes) | Una propuesta de dónde va cada título; aplica lo que Oscar apruebe |
| `diagnostico` | «Qué pasó anoche», «por qué salieron pocas» | Solo `reportes/salud.json` | La causa en lenguaje sencillo y qué hacer |
| `nueva-fuente` | «Agrega Computrabajo» | La plantilla de fuente y sus pruebas | El módulo nuevo con pruebas, en un PR |

**`CLAUDE.md` del repositorio** dice lo esencial para cualquier sesión:

- Las reglas de la sección de requisitos.
- Que nunca se usa sesión ni cookie de LinkedIn, ni se escriben claves o datos personales.
- Que las pruebas se corren antes de cada push.
- Que no se lee la bodega completa con IA: solo los reportes.

**Dónde se gastan tokens y dónde no:**

| Momento | Tokens |
| --- | --- |
| Búsqueda nocturna, búsqueda en la página, búsqueda profunda | 0 |
| Construir la versión 1 | Unas 10 a 12 sesiones cortas de Claude Code, una por paso, cada una con sus pruebas |
| Escribir las 60 familias del mapa | Una vez, dentro del paso 3 |
| Cada familia nueva o revisión del mapa | Pocos: la skill lee archivos cortos |

**Opcional, apagado en la versión 1:** con una clave de la API de Claude (modelo Haiku), la página podría crear sola una
familia nueva cuando Oscar escribe un cargo desconocido. Cuesta centavos por familia; se decide después de usar la
versión 1.

## Paso a paso de la versión 1

Son 12 pasos. Cada uno es una sesión corta de Claude Code que termina en un PR con sus pruebas en verde; Oscar lo revisa
y lo fusiona antes del siguiente. Los pasos 2 a 4 no necesitan red ni cuentas.

- [x] **Paso 0 — Oscar prepara lo básico.** Crea el repositorio vacío y lo conecta a la sesión de Claude Code.
- [ ] **Paso 1 — Esqueleto.** Carpetas, `CLAUDE.md`, `README.md`, `docs/PLAN.md`, `datos/config.yaml` de ejemplo y el
  flujo `pruebas.yml`. Listo cuando el flujo de pruebas corre en verde.
- [ ] **Paso 2 — Países.** `paises.yaml` con todos los países y `paises.py` con la regla de desde dónde se aplica. Listo
  cuando pasan al menos 40 casos de ubicación reales (presencial, remoto LATAM, solo EE. UU., franja horaria, sin región).
- [ ] **Paso 3 — Mapa de cargos.** Esquema, las 60 familias, `normalizar.py` y `familias.py`. Listo cuando al menos 150
  títulos reales de prueba quedan en la familia y el nivel esperados, incluidos los casos difíciles («Linux» no es UX;
  «UI Artist» de videojuegos no es diseño de producto).
- [ ] **Paso 4 — Enlaces, etiquetas y repetidas.** `dominios.yaml`, `enlaces.py`, `etiquetas.py` y la deduplicación.
  Listo cuando ningún enlace de agregador pasa en las pruebas y las copias del mismo aviso se juntan en una.
- [ ] **Paso 5 — Fuentes gratis.** LinkedIn público con JobSpy, Indeed, sistemas de postulación y tableros remotos. Se
  adaptan los lectores que ya funcionan en el agente de Oscar (`tools/jobspy_buscar.py` y `apps_script/Fuentes.gs` de
  `ux_job_agent`), copiando el código, nunca tocando ese repositorio. Listo cuando una corrida a mano trae vacantes de
  cada fuente y el reporte de salud las cuenta.
- [ ] **Paso 6 — Apify y Brave.** Se prueban dos actores de LinkedIn sin sesión con las mismas 5 búsquedas y se elige el
  que trae más vacantes con descripción por dólar; el otro queda de respaldo. Brave alimenta la lista de empresas con
  sistema de postulación. Listo cuando el gasto de cada corrida queda en el reporte de salud.
- [ ] **Paso 7 — Bodega nocturna.** El flujo `bodega.yml` con el orden de la sección de la bodega: retención de 30 días,
  revisión de abiertas, publicación en la rama `publicado` y modo inicial de 30 días. Listo cuando dos noches seguidas
  terminan en menos de 45 minutos.
- [ ] **Paso 8 — Página.** `web/` completa con las pantallas de la sección de la página; la lógica de `motor.js` va con
  pruebas. Listo cuando las capturas a 390 y 1280 px pasan la lista de chequeo de diseño y la búsqueda responde en menos
  de 3 segundos en computador.
- [ ] **Paso 9 — Cloudflare.** Pages conectado a la rama `publicado`, Access con los correos autorizados, KV para enviadas
  y las dos funciones. Claude escribe el código y la guía; Oscar hace los clics. Listo cuando Oscar entra desde el
  computador y el celular, y lo marcado como enviado en uno aparece en el otro.
- [ ] **Paso 10 — Búsqueda profunda.** `profunda.yml` y el botón de la página. Listo cuando una búsqueda de un cargo
  nuevo aparece en la página en 15 minutos o menos.
- [ ] **Paso 11 — Diagnóstico y traspaso.** `diagnostico.yml`, `INSTALACION.md` y `TRASPASO.md`. Se prueba el traspaso
  completo a una cuenta de prueba. Listo cuando esa cuenta queda funcionando siguiendo solo la guía.
- [ ] **Paso 12 — Semana de medición.** Oscar lo usa 7 días con sus clientes. Se ajustan el mapa, las fuentes y los topes
  de gasto con lo que diga el reporte de salud.

## Lo que tiene que hacer Oscar

Oscar crea cuatro cuentas y pone sus claves como secretos; nunca pega una clave en el chat ni en un archivo. Lo de Apify,
Brave y Cloudflare hace falta desde los pasos 6 y 9, no antes.

| Cuándo | Cuenta | Qué hacer | Secreto que se guarda |
| --- | --- | --- | --- |
| Paso 0 | GitHub | Crear el repositorio y conectarlo a la sesión de Claude Code. Si ya se sabe quién será el dueño final, mejor crearlo en su cuenta y agregar a Oscar como colaborador: así no hay traspaso | — |
| Paso 6 | Apify | Crear la cuenta, el token de API y el límite de gasto mensual en la configuración de facturación (sugerido para empezar: USD 50) | `APIFY_TOKEN` en GitHub |
| Paso 6 | Brave Search API | Crear la cuenta (pide tarjeta), la clave y un límite de gasto | `BRAVE_API_KEY` en GitHub |
| Paso 9 | Cloudflare | Crear la cuenta gratis, el proyecto de Pages conectado al repositorio (rama `publicado`), la regla de Access con los correos autorizados y un espacio KV llamado `ENVIADAS` | — |
| Paso 9 | GitHub | Crear un token de acceso con permiso solo para lanzar flujos en este repositorio | `GITHUB_TOKEN_FLUJOS` en Cloudflare |

**Decisiones que Oscar debe confirmar antes del paso 3:**

- La lista de áreas del mapa de cargos (sección del mapa), para quitar o agregar.
- Quiénes entran a la página: los correos para Cloudflare Access.

**Decisión que Oscar debe confirmar antes del paso 9:**

- Quién será el dueño final y si se transfiere o se crea en su cuenta desde el inicio.

## Pruebas y criterios de terminado

La versión 1 está terminada cuando cumple los ocho criterios de abajo durante la semana de medición. Las pruebas
automáticas corren en cada PR y bloquean el cambio que rompa algo.

**Pruebas automáticas (`pruebas.yml`):**

- Países: al menos 40 ubicaciones reales con su resultado esperado.
- Familias: al menos 150 títulos reales con su familia, coincidencia y nivel esperados.
- Enlaces: cada dominio de `dominios.yaml` cae en su tipo y ningún agregador pasa.
- Repetidas: el mismo aviso por ciudad o en dos fuentes queda como una sola vacante.
- Lectores de cada fuente: con respuestas guardadas, sin red.
- `motor.js`: búsqueda, filtros, orden, texto de WhatsApp y columnas del Excel.
- El mapa de cargos y los datos tienen el formato correcto.
- Ningún archivo trae una clave ni un correo.

**Criterios de terminado (se miden con muestras revisadas a mano):**

| Criterio | Meta |
| --- | --- |
| Enlaces de agregador en una muestra de 50 vacantes | 0 |
| Enlaces que abren el aviso correcto en esa muestra | 95 % o más |
| Países bien asignados en una muestra de 30 | 90 % o más |
| Vacantes que de verdad son del cargo buscado en tres búsquedas de prueba (Product Designer en Colombia, desarrollador en Venezuela, editor de video en México) | 85 % o más entre exactas y similares |
| Tiempo de respuesta de la búsqueda en computador | Menos de 3 segundos |
| Duración de la bodega nocturna | Menos de 45 minutos |
| Noches seguidas sin fallar | 7 |
| Traspaso a una cuenta de prueba siguiendo solo la guía | Funciona |

El volumen no tiene meta fija: se mide cuántas vacantes salen por familia y país y se decide con eso si hacen falta más
fuentes.

## Traspaso a otra persona

El traspaso toma una tarde. Se pasa el repositorio y la otra persona conecta sus propias cuentas; los datos se
reconstruyen solos en la primera noche. No hay nada que dependa del Google, el Drive ni el Apps Script de Oscar.

1. **La otra persona crea sus cuentas:** GitHub, Cloudflare, Apify y Brave, con sus propios límites de gasto.
2. **Oscar le pasa el repositorio:** en GitHub, Settings > Transfer ownership, que conserva código, historial y flujos.
   Otra opción es que la otra persona lo copie desde una plantilla.
3. **La otra persona pone sus secretos:** `APIFY_TOKEN` y `BRAVE_API_KEY` en GitHub; `GITHUB_TOKEN_FLUJOS` en Cloudflare.
   Se ponen de nuevo, sin dar por hecho que viajan con el repositorio.
4. **Conecta Cloudflare Pages** a su repositorio (rama `publicado`), crea la regla de Access con sus correos y el espacio
   KV `ENVIADAS`.
5. **Corre `diagnostico.yml`:** dice en una lista qué clave falta, qué fuente no responde y si la página ve los datos.
6. **Corre `bodega.yml` en modo 30 días** para llenar la bodega desde cero.
7. **Historial de enviadas (opcional):** Oscar lo exporta desde la página y la otra persona lo importa en la suya.
8. **Oscar revoca sus tokens viejos** y sale como colaborador.

`docs/TRASPASO.md` repite estos pasos con capturas, y el paso 11 los prueba con una cuenta de prueba antes de hacerlo de
verdad.

## Costos, riesgos y pendientes

Operar cuesta entre USD 20 y 80 al mes, casi todo Apify; la cifra real sale de la semana de medición. Precios consultados
el 28 de octubre de 2026.

| Servicio | Costo mensual | Nota |
| --- | --- | --- |
| GitHub (repositorio y Actions) | USD 0 | Un repositorio privado incluye 2.000 minutos al mes y la bodega gasta unos 1.200; uno público no tiene límite ([fuente](https://cicdcalculator.com/github-actions-free-tier)) |
| Cloudflare Pages, Access y KV | USD 0 | Plan gratis |
| Apify | Plan Starter USD 19 con USD 19 de uso; luego, lo que se use | Actores de LinkedIn sin sesión desde unos USD 0,30 a 1 por cada 1.000 vacantes ([precios](https://apify.com/pricing), [actor ejemplo](https://apify.com/meka.im/linkedin-jobs-scraper)) |
| Brave Search API | USD 0 a 5 | USD 5 de crédito al mes, unas 1.000 búsquedas ([fuente](https://apiserpent.com/blog/free-brave-search-api)) |

**Riesgos:**

| Riesgo | Qué se hace |
| --- | --- |
| Un actor de Apify deja de funcionar (son de terceros) | Actor de respaldo y JobSpy como tercera opción; el reporte de salud avisa |
| LinkedIn bloquea las lecturas | Afecta al proveedor, no a una cuenta de usuario; leer LinkedIn con programas va contra sus condiciones, es zona gris |
| El país se asigna mal en avisos ambiguos | Marca de confianza y filtro en la página |
| Con pocos filtros llegan avisos malos | Revisión de Oscar antes de mandar; ajustes del mapa con `ampliar-mapa` |
| El gasto crece | Límite de gasto en Apify y Brave; gasto por corrida en la pantalla Salud |
| La página pesa en el celular | Datos por familia, solo el resumen de 300 caracteres |
| Se acaban los minutos de GitHub | La bodega mide su duración; si se acerca al límite, se baja la frecuencia de las revisiones de abiertas |

**Pendientes para comprobar al construir:**

- Si el buscador de LinkedIn acepta varias palabras unidas con OR en una consulta. Si sí, se gastan menos llamadas.
- Qué países de LATAM tiene Indeed.
- Cuál actor de Apify rinde más (paso 6).

**Para la versión 2:**

- Portales locales.
- Publicaciones de LinkedIn en una pestaña aparte.
- Crear familias desde la página con la API de Claude.
- Importar ESCO.

## Prompt para arrancar cada paso

Oscar abre una sesión nueva de Claude Code con este repositorio y pega este texto, cambiando solo el número del paso. Una
sesión por paso mantiene bajo el gasto de tokens.

```
Trabajas en el repositorio search_adaptia_jobs. Lee completos docs/PLAN.md y CLAUDE.md.
Haz SOLO el Paso N del plan, nada de los siguientes.
Reglas: nunca uses ni pidas sesión o cookie de LinkedIn; ningún agregador como enlace final;
ninguna clave, ID ni dato personal en el repositorio; no toques el repositorio ux_job_agent
(si necesitas su código, léelo y cópialo aquí).
Corre las pruebas antes de cada push. Trabaja en una rama y abre un PR; no lo fusiones.
Si algo del plan no está claro o falta una decisión mía, pregúntame antes de inventar una regla.
Al terminar dime en español sencillo: qué hiciste, cómo lo probé, el enlace del PR y qué tengo que hacer yo.
```
