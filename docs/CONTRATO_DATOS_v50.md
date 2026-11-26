# Contrato de datos v50 — más vacantes en español, para cualquier país de LATAM y España (26 nov 2026)

Pedido de Oscar: las vacantes en español llegan muy pocas. Sin IA y sin SQL nuevo. Amplía v49; donde v44 y v49 decían
que los nombres compuestos en español «solo se sugieren», desde v50 se usan solos con control (§2.2).

## Evidencia (bodega pública del 26 nov, 11.260 vacantes, captura con el código anterior a v49; y pruebas en vivo)

| Paso | En español | En inglés |
|---|---|---|
| Guardadas con cargo reconocido (30 días) | 1.128 | 4.025 |
| Nuevas por día, todos los cargos y países | 27 a 40 | 150 a 330 |
| Con el enlace comprobado (entregables hoy) | 67 (6 %) | 1.124 (28 %) |

- **Encontrarlas no es lo que falla.** LinkedIn Colombia, Product Manager, 30 días: de 82 avisos del cargo listados en
  vivo, 67 ya estaban guardados (81 %). De esos, 56 con descripción, 23 en español y 11 con el enlace comprobado.
- **LinkedIn gasta sus lecturas en avisos que no son del cargo.** De LinkedIn sale el 57 % del español guardado. En una
  noche alcanza unas 290 peticiones (25 nov: 818 avisos listados, 75 fichas leídas, 100 relecturas; 1.581 en espera).
  Las fichas se leían sin mirar el título: en la prueba, solo 82 de 320 avisos listados eran del cargo. Sin ficha no hay
  descripción; sin descripción no se sabe el idioma y la vacante no se entrega: 1.273 vacantes de cargos reconocidos
  estaban así (684 de LinkedIn, 243 de Computrabajo), unas 490 en países hispanos.
- **Indeed solo cuenta el día que se ve.** No se puede comprobar directo (v41) y cada noche se pedía solo lo publicado
  desde la búsqueda anterior, con un nombre por combinación: 259 en español con cargo quedaban sin comprobar para
  siempre. Una búsqueda de 30 días tarda 1 segundo (72 búsquedas en 21 s el 25 nov).
- **Se buscaba en español solo para quien marcó «solo español»**: 15 de 112 búsquedas de LinkedIn y 6 de 72 de Indeed.
- **El 99 % de los avisos en español es de un solo país** (1.110 de 1.128) y el mercado por cargo y país es pequeño:
  Indeed Colombia, 30 días, en español: 7 de producto, 16 de QA y 6 de UX.

Un cargo, en un solo país y solo en español da de 2 a 4 vacantes nuevas al día sumando todas las fuentes. Este contrato
no promete llenar metas altas solo con español donde el mercado no lo tiene: lo muestra con cifras (§0).

## Decisiones de Oscar (26 nov)

1. El plan sirve para **cualquier país de LATAM y España**: los clientes pueden estar en cualquiera.
2. Remotas de otro país: **se mantiene la regla vigente** (v49). Entra si el aviso está abierto a LATAM, España o todo
   el mundo, o si nombra el país de la persona, aunque sea en la letra pequeña. Sin excepción nueva por idioma.
3. Los nombres hermanos en español de un cargo **se aplican solos, con control** de funciones.
4. El refuerzo de español aplica a **quien solo acepta español y a quien acepta español e inglés**. Sin cuota por idioma.

## 0. Medición

- Cada búsqueda publica `embudo_idioma` en su reporte (`datos/salud_bodega.json` y `datos/salud.json`): por idioma del
  aviso (`es`, `en`, `otro`, `sin_descripcion`) y por fuente, cuántas vacantes de un cargo buscado hay guardadas
  (`con_cargo`) y cuántas tienen el enlace comprobado (`comprobadas`: las que se pueden entregar hoy). Son conteos de
  avisos públicos, sin datos de clientes.
- `python -m buscador.medicion --bodega …` añade `embudo_idioma` a sus cifras.

## 1. No perder lo que ya se encuentra

1. **LinkedIn lee primero las fichas de los avisos cuyo título es de un cargo buscado.** Los demás solo reciben ficha
   si sobra cupo (un título genérico puede coincidir por su descripción, v25). En una búsqueda profunda de un cargo
   que no está en el mapa, «del cargo» es el título que contiene el nombre buscado. Vale para la búsqueda de la mañana, el
   refuerzo y la captura horaria. El reporte de LinkedIn dice cuántos avisos listados eran del cargo (`del_cargo`) y
   cuántos de ellos recibieron ficha (`fichas_del_cargo`).
2. **Se relee primero lo que le sirve a quien tiene menos.** Las vacantes guardadas sin descripción (LinkedIn y
   Computrabajo) se releen por turnos entre las personas (`cobertura.por_necesidad`): primero quien va corta y quien
   tiene menos de dónde elegir, mirando su cargo y su ubicación (el idioma se sabrá al leer). Después las de un cargo
   buscado que hoy no le sirven a nadie y, al final, las que ya no son de ningún cargo.
3. **Indeed repasa cada noche los 30 días completos.** Cada combinación de cargo y país se busca con la ventana
   completa, hasta 100 resultados y con varios de sus nombres (4 de la combinación general y hasta 8 de la de español,
   no uno por día; `indeed_repaso` en `datos/config.yaml`). Va por vueltas: el primer nombre de cada combinación, luego
   el segundo… en el orden del reparto por persona, y cada búsqueda queda anotada con su propio nombre. Con el filtro
   «remoto» de Indeed sigue un solo nombre: la búsqueda sin filtro ya trae esos avisos. Así un aviso que sigue publicado vuelve a «verse hoy» y cuenta como
   comprobado 24 h (v41). Hasta 400 búsquedas y 10 minutos por búsqueda completa (la segunda pasada del día repite
   el repaso y vuelve a marcar lo que sigue publicado); tres fallos seguidos cortan la fuente, como antes. La captura horaria, el refuerzo y la búsqueda para quien falta (v47) no cambian: esta última no repite los
   nombres que la noche ya buscó.
   Prueba en vivo del 26 nov con la configuración de demostración (3 cargos, Colombia y España): como antes, 16
   búsquedas y 17 vacantes en español del cargo; con el repaso, 56 búsquedas en 31 segundos y 30.
4. **Comprobación de enlaces con LinkedIn aparte.** En la cola por persona (v49), el máximo cuenta solo los sitios
   que se comprueban en paralelo (Computrabajo, Elempleo, Get on Board…); LinkedIn sigue de una en una, con pausa,
   ordenado por necesidad y limitado por su parte del tiempo.

## 2. Buscar y reconocer más en español

1. **Quien acepta español e inglés también recibe búsquedas con nombres en español** en sus lugares (LinkedIn, Indeed,
   Computrabajo, Get on Board, Elempleo). El peso doble en los turnos sigue siendo solo para quien solo acepta español.
   Una búsqueda en español no cuenta como turno de quien solo acepta inglés.
   Elempleo busca con los nombres en español (si alguien de Colombia acepta español) y con los generales; antes, si
   había nombres en español, solo con esos.
2. **Nombres hermanos en español, solos y con control.** Un nombre hermano es el mismo oficio con otro nombre.
   Para cada cargo se usan sin que el operador los añada:
   - los títulos exactos en español de su familia del mapa (ya desde v44);
   - para un cargo compuesto (v44: «AI Product Manager» = AI + Product Manager), los nombres que arma el glosario
     (`datos/glosario_cargos.yaml`): «Gerente de Producto de IA». Antes eran solo sugerencias.
   Se usan para buscar en español y para reconocer el aviso (grado «similar»).
   - Los títulos «similares» del mapa son oficios vecinos («Analista de operaciones» para Data Analyst, «Director de
     producto» para Product Manager): **no** se usan solos; siguen como sugerencias para añadir.
   - El control es el de v49: sin evidencia de las funciones del cargo, la vacante va al final con «Funciones por
     confirmar»; con señal de otro oficio, va a «Por confirmar». Lo que el operador ponga en «excluidos» no se usa.
   - El diálogo del cargo los lista como «En español, se usan solos»; al tocar uno pasa a «Excluir estos términos».
     Qué nombres usa un cargo lo decide el servidor (`terminos.hermanos_del_cargo`), con sus términos y excluidos.
   - El mapa de cargos (`datos/mapa_cargos.yaml`) suma como exactos nombres reales que Indeed mostró el 26 nov en CO,
     MX, ES, AR, CL y PE y que nadie reconocía: «jefe de producto», «líder de producto», «responsable de producto»,
     «propietario de producto», «ingeniero de pruebas», «analista tester», «probador de software», «especialista en
     paid media»… No entran nombres que también son de otro oficio («analista de performance» es además de recursos
     humanos). `datos/oficios_ajenos.yaml` suma «destructivas», «eléctricas», «telecomunicaciones» y «simuladores»
     («Ingeniero de pruebas no destructivas» no es QA de software).
3. **Letra pequeña en español (la regla vigente, mejor leída).**
   - Suman países al aviso las frases que hablan de quien postula, seguidas de países o de una región: «abierto a
     candidatos de…», «puedes postular desde…», «aceptamos postulaciones de…», «contratamos personas en…», «vacante
     disponible para…». «Remoto, Chile» + «abierto a candidatos de Colombia y Perú» → Chile, Colombia y Perú, con la
     nota «abierta a esos países según el aviso». Una lista que mezcla países de fuera se lee entera.
   - Solo en remotas cuya ubicación nombra un país concreto. Si la ubicación ya es una región, LATAM o no dice país,
     deciden las reglas de siempre: una frase así nunca recorta lo que el aviso ya abría, ni pisa una restricción de
     residencia.
   - No abren nada las frases de la empresa («presencia en 6 países», «en 2024 contratamos en México a 200
     personas», «clientes en LATAM»), las de beneficios («puedes trabajar desde España cuatro semanas al año») ni las
     vagas («trabaja desde donde quieras»). Llevar las vagas a «Por confirmar» queda pendiente: esa bandeja decide por
     ubicación exacta y una regla así abriría todos los avisos de esa ciudad.
   - Medido el 26 nov: de 389 remotas en español de un solo país, unas 6 dicen de verdad que aceptan otros países
     («100% remoto desde LATAM») y ya las reconocía v49; con las frases nuevas no cambió ninguna. Es una regla
     correcta pero de poco volumen: el español de los avisos es local.

## 3. Fuentes en español para cualquier país (segunda entrega)

Una fuente entra solo si pasa una prueba en vivo: se lista, trae descripción, se postula ahí mismo y su aviso se puede
comprobar. Resultado del 26 nov:

| Fuente | Países | Resultado |
|---|---|---|
| Bumeran, Laborum, Multitrabajos y Konzerta (misma plataforma) | AR, MX, PE, VE, CL, EC, PA | **Entra** (`buscador/fuentes/jobint.py`) |
| InfoJobs | ES | **Entra, con límite** (`buscador/fuentes/infojobs.py`): pocas páginas por corrida; ver abajo |
| Tecnoempleo | ES | **Entra** (`buscador/fuentes/tecnoempleo.py`): pasa de la lista de agregadores a la de portales por decisión de Oscar; ver abajo |
| Magneto y Hireline por búsqueda, Get on Board por categorías, Chiletrabajos | CO, MX, LATAM, CL | Pendientes |
| OCC | MX | Bloquea (403) |

### Bumeran y sus portales hermanos
- **Búsqueda.** La API pública del portal (la misma de su página) devuelve el aviso completo: título, empresa, lugar,
  modalidad, fecha y descripción. Se busca por cargo y país con portal, con varios nombres por turno (3 generales y
  hasta 6 en español), cada búsqueda con su clave; los avisos de más de 30 días no se guardan. Presupuesto:
  `jobint_busquedas` (120; el panel, hasta 240 según los cargos). Tres fallos seguidos de un portal lo dejan
  descansar esa corrida; los demás siguen (el 26 nov el de Argentina respondió con error un rato y los otros no).
- **Dónde se postula.** En el mismo portal; la vacante lleva su dirección pública (`/empleos/<título>-<id>.html`) y el
  nombre de su portal como fuente.
- **Ubicación.** «Localidad, Provincia» más el país del portal. En una remota, si la localidad se llama como un lugar
  de otro país («Palermo», «Florida», «Concepción del Uruguay»), se quita: el aviso es del país de su portal y no abre
  otro. En una presencial o híbrida la localidad se conserva siempre: sin ciudad no le llega a nadie (v49). Vale igual
  para InfoJobs («Granada, España» es la ciudad, no la isla).
- **Fecha.** La de publicación. Una fecha imposible, o posterior a hoy porque el portal va en otra hora, queda vacía.
- **Comprobación.** La página del aviso se arma en el navegador y no dice nada a una lectura simple. El enlace se
  comprueba, como cualquier otro antes de entregarse, con la ficha de la API del mismo portal: abierto si responde,
  está «activo» y el título coincide; cerrado si dice un estado de cierre conocido o no existe. Un bloqueo, una
  respuesta rara, una ficha sin estado o con un estado desconocido nunca aprueban ni cierran. Verse en la búsqueda
  **no** cuenta como comprobación (esa regla, la de Indeed en v41, no se decidió para estos portales).
- **Medido en vivo el 26 nov** (5 cargos, 7 países): 217 búsquedas en 160 segundos, 145 avisos, 120 de un cargo
  buscado y 118 en español (Perú 55, Chile 40, Argentina 21). Son casi todos presenciales o híbridos: sirven a quien
  vive en esa ciudad.

### InfoJobs (España)
- **Decisión de Oscar (26 nov).** InfoJobs entra, y un aviso que su búsqueda mostró hoy cuenta como comprobado 24 h,
  igual que Indeed (v41).
- **Búsqueda.** La página de búsqueda trae cada aviso completo en sus datos: título, empresa, ciudad, modalidad, fecha,
  enlace y descripción. Se busca por los nombres de los cargos con alguien que trabajaría en España; los nombres en
  español tienen su turno si alguien de España acepta español. Una página por nombre (20 avisos, de lo más reciente a
  lo más antiguo), cada búsqueda con su clave; no se guardan los de más de 30 días. Un nombre ya buscado hoy no se
  repite: la segunda pasada del día sigue con los siguientes.
- **Comprobación.** La ficha de cada aviso pide captcha: nunca se pide, desde ningún camino
  (`verificar_enlaces.SIN_COMPROBACION_DIRECTA`; `comprobar` y la lectura de descripciones la saltan, igual que la de
  Indeed).
  Lo que la búsqueda mostró hoy, con fecha y con descripción de 200 caracteres o más, queda comprobado 24 h («vista hoy
  en la búsqueda de InfoJobs»). Al día siguiente vuelve a quedar sin comprobar si no se vuelve a ver.
- **Límite medido.** InfoJobs muestra unas cinco páginas de búsqueda y después pide captcha, aunque se vaya despacio; si
  se insiste, bloquea desde la primera durante un rato. Ese control se respeta: `infojobs_busquedas: 5` por corrida y
  15 páginas al día entre todas las corridas, con pausa, y al primer captcha la fuente se detiene hasta la corrida
  siguiente y lo dice en el reporte (`bloqueada`). No se reinicia la visita para seguir.
- **Límites conocidos.** No se sabe si la fecha de un aviso republicado es la original o la de republicación. Un aviso
  de InfoJobs con ciudad de otro país se guarda como de España.
- **Qué esperar.** Hasta unos 100 avisos vistos por corrida, de los nombres que les toque ese día. Desde los servidores
  de GitHub, que comparten dirección con mucha gente, puede venir bloqueada a menudo: solo las búsquedas reales lo
  dirán. La vía estable sería la API oficial de InfoJobs, que pide registrar una aplicación y guardar su clave como
  secreto; queda como propuesta.
- En vivo el 26 nov, antes del bloqueo: 6 nombres, 62 avisos, 47 de un cargo buscado y todos en español (17
  presenciales, 16 híbridos y 14 remotos).

- **API oficial (optativa, la vía estable).** Decisión de Oscar del 26 nov: dejarla preparada. Con los secretos
  `INFOJOBS_CLIENT_ID` e `INFOJOBS_CLIENT_SECRET` (guía: `docs/ACTIVAR_INFOJOBS_API.md`) la fuente usa la API en vez de
  la página: búsqueda por nombre en España y ficha solo de los títulos de un cargo buscado. La ficha da la descripción,
  la **fecha de creación** (no la de republicación), si el aviso sigue activo y, si se postula fuera, esa dirección
  como enlace directo. El reporte dice `modo: api` o `modo: pagina`.
  - Comprobación con clave: una ficha leída hoy que dice «activo», con descripción, comprueba el enlace; «archivado»
    o «borrado» lo cierra; lo demás no decide, tampoco un 404 (sin clave real no se sabe qué significa y un cierre
    retira la vacante). Después el enlace se vuelve a comprobar con esa misma ficha de la API. La página del aviso
    sigue sin abrirse. Sin clave vale la regla de arriba («vista hoy»).
  - Los secretos solo llegan a `bodega.yml` y `profunda.yml`. La captura horaria y el servidor del panel no los
    reciben: ahí el enlace queda «sin comprobación directa» y vale la comprobación de la última búsqueda (24 h).
  - Una clave rechazada (401/403) detiene la fuente y lo dice, sin mostrarla; en esa corrida no se vuelve a usar,
    tampoco al comprobar enlaces. Las claves solo viajan en la cabecera de autenticación.
  - No se pudo probar contra la API real: no hay clave todavía. Está hecha con su documentación pública y probada con
    respuestas de ejemplo.

### Tecnoempleo (España, tecnología)
- **Decisión de Oscar (26 nov).** Pasa de `agregadores` a `portales` en `datos/dominios.yaml` y entra como fuente. En
  los 13 avisos revisados ninguno enlaza a otro sitio para postular y todos piden entrar como candidato en el propio
  portal. No se entró con cuenta: el último paso de la postulación no se vio.
- **Búsqueda y ficha.** Búsqueda por nombre (`/ofertas-trabajo/?te=…`) y ficha con su `JobPosting` (empresa, ciudad,
  fecha y descripción), con el lector común de Elempleo. Solo se lee la ficha de un título de un cargo buscado; un
  nombre ya buscado hoy no se repite. Solo para cargos con alguien que trabajaría en España.
- **Comprobación.** La de siempre: se abre la ficha. En vivo, nueve fichas reales quedaron «verificada» y una
  inexistente «enlace roto». Cierra por la fecha de cierre de la ficha (`validThrough`), por enlace roto o si la
  página dice «oferta caducada/finalizada» o «esta oferta ha caducado/finalizado» (frases añadidas a la comprobación
  común). **No se pudo ver un aviso caducado real** de Tecnoempleo: si muestra otra frase y sigue respondiendo, ese
  aviso seguiría como abierto hasta que el portal lo retire.
- Una página de búsqueda sin avisos no cuenta como buscada: ese nombre se reintenta en la siguiente pasada.
- **Búsqueda profunda.** En Tecnoempleo, InfoJobs (API), Computrabajo y LinkedIn un cargo que no está en el mapa
  cuenta como «cargo buscado» si el título contiene uno de los nombres con que se buscó
  (`cobertura.titulos_del_cargo`); antes esas fuentes no leían ninguna ficha en ese caso.
- **Medido en vivo el 26 nov** (5 cargos): 12 búsquedas en 67 segundos, 67 avisos, 51 de un cargo buscado; de 30
  fichas leídas se guardaron 26, todas en español (11 híbridas, 9 remotas y 6 presenciales).

## Lo que no cambia

- Solo español e inglés; el idioma del perfil sigue siendo un filtro. Sin descripción o sin enlace comprobado en 24 h
  no se entrega.
- Si el aviso nombra un país, manda ese país (v49). La ciudad se exige en presenciales e híbridas.
- Sin IA, sin agregadores, sin envío automático, sin SQL nuevo. `ofertas` v1 no cambia.
- LinkedIn sin sesión ni cookie de nadie, con las mismas pausas.
- Los reportes públicos no llevan datos de clientes.
