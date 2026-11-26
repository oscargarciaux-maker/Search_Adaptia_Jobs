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
| InfoJobs | ES | No entra todavía: la búsqueda trae el aviso completo, pero la ficha pide captcha y el enlace no se puede comprobar después. Falta decidir si «visto hoy en su búsqueda» cuenta como comprobado, como en Indeed (v41) |
| Tecnoempleo | ES | No entra: está en la lista de agregadores desde el 15 nov (`datos/dominios.yaml`) |
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
- **Ubicación.** «Localidad, Provincia» más el país del portal. Si la localidad se llama como un lugar de otro país
  («Palermo», «Florida», «Concepción del Uruguay»), se quita: el aviso es del país de su portal y no abre otro.
- **Fecha.** La de publicación. Una fecha imposible, o posterior a hoy porque el portal va en otra hora, queda vacía.
- **Comprobación.** La página del aviso se arma en el navegador y no dice nada a una lectura simple. El enlace se
  comprueba, como cualquier otro antes de entregarse, con la ficha de la API del mismo portal: abierto si responde,
  está «activo» y el título coincide; cerrado si dice un estado de cierre conocido o no existe. Un bloqueo, una
  respuesta rara, una ficha sin estado o con un estado desconocido nunca aprueban ni cierran. Verse en la búsqueda
  **no** cuenta como comprobación (esa regla, la de Indeed en v41, no se decidió para estos portales).
- **Medido en vivo el 26 nov** (5 cargos, 7 países): 217 búsquedas en 160 segundos, 145 avisos, 120 de un cargo
  buscado y 118 en español (Perú 55, Chile 40, Argentina 21). Son casi todos presenciales o híbridos: sirven a quien
  vive en esa ciudad.

## Lo que no cambia

- Solo español e inglés; el idioma del perfil sigue siendo un filtro. Sin descripción o sin enlace comprobado en 24 h
  no se entrega.
- Si el aviso nombra un país, manda ese país (v49). La ciudad se exige en presenciales e híbridas.
- Sin IA, sin agregadores, sin envío automático, sin SQL nuevo. `ofertas` v1 no cambia.
- LinkedIn sin sesión ni cookie de nadie, con las mismas pausas.
- Los reportes públicos no llevan datos de clientes.
