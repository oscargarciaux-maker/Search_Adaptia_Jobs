> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v44 — vacantes para quien solo habla español, en cualquier país (18 nov 2026)

Pedido de Oscar: «cualquier persona que coloque reciba vacantes; en este caso en español; que abarque todos los países».
Decisiones de Oscar: hacer a, b y c para Carolina (AI Product Manager); sumar Hireline, Magneto, RemotosLatam y WeRemoto
(solo empresas); los nombres en español del mapa se usan solos; los compuestos solo se sugieren. Sin IA en nada.

## Evidencia (búsqueda #34, 7.325 vacantes, perfiles del CSV v6)
- Carolina (AI Product Manager, Colombia, solo español): 5 vacantes en toda la bodega. «Buscar denominaciones afines» no
  propuso nombres en español porque el mapa no tiene «AI product manager» (solo «product manager»).
- Itza (Costa Rica), Juan (Colombia), Jesús (México), Product Designer, remoto, solo español: 0, 0 y 1. Las remotas en
  español abiertas a su país son pocas. Muchas son solo para otros países o presenciales.
- El español solo llegaba a LinkedIn, Computrabajo y Elempleo. En Computrabajo compartía el turno con el inglés, y
  `en_espanol` aceptaba títulos en portugués.

## Reglas
1. **Sugerencias en español compuestas** (`panel/terminos.compuestos`, glosario editable `datos/glosario_cargos.yaml`).
   - Si el nombre del cargo no está en el mapa pero sí su oficio base con un modificador (AI, ML, Data, Growth, Mobile,
     E-commerce…), se combinan los nombres en español del oficio base con las formas en español del modificador.
     Ejemplos: «Gerente de Producto de IA», «Product Manager IA», «Gestor de Producto de Inteligencia Artificial».
   - Se muestran primero, en el grupo «En español», en «Buscar denominaciones afines».
   - También se muestra el oficio base («Más amplio»: Product Manager, Gerente de Producto…).
   - Las dos listas son solo sugerencias: entran con un clic del operador.
2. **Reconocer lo que se busca en español** (`panel/terminos.espanol_del_mapa`, `grado` y el campo `similares_es` del
   mapa operativo).
   - Los títulos exactos en español de la familia del mapa del cargo («Diseñador UX/UI» para Product Designer) cuentan
     como «similar» al reconocer y al clasificar.
   - Son curados y ya se usaban para buscar; antes, lo encontrado así podía quedar sin cargo.
   - **Solo clasifican: no se buscan.** No van en `consultas` ni en `similares`, que rotan en todas las fuentes y en
     todos los países. La búsqueda en español es la de `consultas_es`, solo para quien solo habla español.
   - Solo cuando el cargo es un título exacto de la familia: un cargo que es «similar» de una familia amplia, como QA
     Lead en QA, no hereda sus títulos.
   - Nunca títulos de una sola palabra («Programador», «Redactor»).
   - Los similares del mapa y los compuestos no entran solos.
   - Aviso: las familias del mapa son amplias. Por ejemplo, «Scrum Master» acepta «Gerente de proyectos». Si un cargo
     recibe títulos que no le sirven, se añaden a sus «términos excluidos».
3. **El español en todas las fuentes que lo admiten**, para perfiles que solo hablan español:
   - Indeed: un título en español por país de esos perfiles, con y sin filtro remoto (lugares «XX:ES» y
     «XX:ES:REMOTO»).
   - Get on Board: una consulta en español por cargo.
   - Computrabajo: turno propio en español («XX:ES»).
   - Apify (rescate): primero los títulos en español.
   - `en_espanol` descarta títulos con palabras del portugués (produto, desenvolvedor, dados…).
4. **Cualquier país** (`panel/ejecutor.fuentes_en`).
   - Todo país del mundo se busca, como mínimo, con LinkedIn, los portales de empresas y las remotas de Get on Board.
   - Se suman Indeed (sus 62 países), Computrabajo (18 de LATAM), Elempleo, Hireline y Magneto donde existen.
   - Una prueba recorre los 249 países de `paises_mundo.yaml`.
   - Cuando el país de una persona solo tiene fuentes globales, «Cobertura por persona» lo dice: «Cobertura limitada
     donde vive…».
5. **Fuentes nuevas en español.**
   - **Hireline** (México y Colombia, tecnología) y **Magneto** (Colombia), en `buscador/fuentes/sitemaps_empleo.py`:
     - del sitemap de ofertas se toman las vacantes cuya dirección nombra un cargo buscado y que se actualizaron en los
       últimos 30 días;
     - de cada ficha se toma el `JobPosting`: fecha real, cierre, remota, país desde donde se postula y salario;
     - se postula en el mismo sitio; nunca se usa su búsqueda con parámetros ni su API (robots.txt);
     - una expresión por cargo compara las direcciones: las 29 mil de Magneto se revisan en unos 2 s (con una
       comparación por título tardaba minutos);
     - el `JobPosting` se lee con el lector común `buscador/fuentes/jobposting.py`, que comparte con Elempleo; una ficha
       rara se salta y no tumba la fuente;
     - presupuesto en `datos/config.yaml`: `hireline_fichas` y `magneto_fichas`.
   - **RemotosLatam y WeRemoto** (`buscador/fuentes/tableros_latam.py`), solo como descubridores de empresas, igual que
     Open Seat:
     - de sus páginas de categoría se toman los portales Greenhouse, Lever, Ashby, Workable, SmartRecruiters y
       Recruitee, y se leen con `ats.py`;
     - sus avisos nunca se toman: son agregadores.
6. **«Qué hacer» por persona, con cifras** (`panel/servicio.que_hacer`, en «Cobertura por persona»).
   - Para quien no llega a su meta, con el catálogo de los últimos 30 días, se calcula cuántas vacantes más le
     llegarían con cada ajuste:
     - añadir los nombres en español sugeridos;
     - aceptar el oficio general;
     - aceptar híbrido o presencial donde vive (si hoy solo acepta remoto);
     - y bajar la meta, solo si en sus últimos días medidos (al menos 3) ninguno llegó a la meta. Se propone el promedio
       que recibió, nunca menos de 5.
   - Solo se muestran los ajustes que suman algo, y nada se aplica solo.

## Lo que no cambia
- Solo español e inglés.
- El idioma del perfil sigue siendo un filtro: a quien solo habla español nunca le llega un aviso en inglés.
- «No admite postular desde su país» se respeta: una remota solo para otro país no se entrega.
- Sin agregadores.
- Sin SQL.
- La captura horaria no crea entregas (salvo v43).
