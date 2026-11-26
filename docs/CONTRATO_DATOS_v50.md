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
- `verificacion_enlaces.por_idioma` dice lo mismo para la comprobación de la corrida.
- `python -m buscador.medicion --bodega …` añade `embudo_idioma` a sus cifras.

## 1. No perder lo que ya se encuentra

1. **LinkedIn lee primero las fichas de los avisos cuyo título es de un cargo buscado.** Los demás solo reciben ficha
   si sobra cupo (un título genérico puede coincidir por su descripción, v25). Vale para la búsqueda de la mañana, el
   refuerzo y la captura horaria. El reporte de LinkedIn dice cuántos avisos listados eran del cargo (`del_cargo`) y
   cuántos de ellos recibieron ficha (`fichas_del_cargo`).
2. **Se relee primero lo que le sirve a quien tiene menos.** Las vacantes guardadas sin descripción (LinkedIn y
   Computrabajo) se releen por turnos entre las personas (`cobertura.por_necesidad`): primero quien va corta y quien
   tiene menos de dónde elegir, mirando su cargo y su ubicación (el idioma se sabrá al leer). Después las de un cargo
   buscado que hoy no le sirven a nadie y, al final, las que ya no son de ningún cargo.
3. **Indeed repasa cada noche los 30 días completos.** Cada combinación de cargo y país se busca con la ventana
   completa, hasta 100 resultados y con varios de sus nombres (4 de la combinación general y hasta 8 de la de español,
   no uno por día), primero las combinaciones en español. Con el filtro «remoto» de Indeed sigue un solo nombre: la
   búsqueda sin filtro ya trae esos avisos. Así un aviso que sigue publicado vuelve a «verse hoy» y cuenta como
   comprobado 24 h (v41). Hasta 400 búsquedas y 10 minutos por noche; tres fallos seguidos cortan la fuente, como
   antes. La captura horaria, el refuerzo y la búsqueda para quien falta (v47) no cambian.
   Prueba en vivo del 26 nov con la configuración de demostración (3 cargos, Colombia y España): como antes, 16
   búsquedas y 17 vacantes en español del cargo; con el repaso, 56 búsquedas en 31 segundos y 30.
4. **Comprobación de enlaces por carril.** En la cola por persona (v49), los sitios que no son LinkedIn se comprueban
   en paralelo y no gastan el cupo de LinkedIn; LinkedIn sigue de una en una, con pausa y ordenado por necesidad.

## 2. Buscar y reconocer más en español

1. **Quien acepta español e inglés también recibe búsquedas con nombres en español** en sus lugares (LinkedIn, Indeed,
   Computrabajo, Get on Board, Elempleo). El peso doble en los turnos sigue siendo solo para quien solo acepta español.
   Una búsqueda en español no cuenta como turno de quien solo acepta inglés.
   Elempleo busca con los nombres en español y con los generales (antes, si había nombres en español, solo con esos).
2. **Nombres hermanos en español, solos y con control.** Para cada cargo se usan sin que el operador los añada:
   - los títulos exactos en español de su familia del mapa (ya desde v44);
   - los títulos similares en español de esa familia, de varias palabras;
   - para un cargo compuesto (v44: «AI Product Manager» = AI + Product Manager), los nombres que arma el glosario
     (`datos/glosario_cargos.yaml`): «Gerente de Producto de IA».
   Se usan para buscar en español y para reconocer el aviso (grado «similar», regla «nombre hermano en español»).
   El control es el de v49: sin evidencia de las funciones del cargo, la vacante va al final con «Funciones por
   confirmar»; con señal de otro oficio, va a «Por confirmar». Lo que el operador ponga en «excluidos» no se usa.
   El diálogo del cargo los lista como «En español, se usan solos»; al tocar uno pasa a «Excluir estos términos».
   - El mapa de cargos (`datos/mapa_cargos.yaml`) suma nombres reales que Indeed mostró el 26 nov en CO, MX, ES, AR,
     CL y PE y que nadie reconocía: «jefe de producto», «líder de producto», «responsable de producto», «propietario
     de producto», «ingeniero de pruebas», «analista tester», «probador de software», «especialista en paid media»,
     «analista de performance»… `datos/oficios_ajenos.yaml` suma «destructivas», «telecomunicaciones» y
     «simuladores» («Ingeniero de pruebas no destructivas» no es QA de software).
3. **Letra pequeña en español (la regla vigente, mejor leída).**
   - Abren el aviso a los lugares que nombran las frases que hablan de la persona: «abierto a candidatos de…»,
     «puedes trabajar/postular desde…», «contratamos en…», «para residentes de…», seguidas de países o de una región.
   - No abren nada las frases que hablan de la empresa: «presencia en 6 países», «líder en Latinoamérica», «clientes en
     LATAM», «equipos en…».
   - Las frases vagas («trabaja desde donde quieras», «desde cualquier lugar» sin región) no abren el aviso, como
     hasta ahora. Llevarlas a «Por confirmar» queda pendiente: esa bandeja decide por ubicación exacta y una regla así
     abriría todos los avisos de esa ciudad.
   - Los países nombrados se suman a los del aviso («Remoto, Chile» + «abierto a candidatos de Colombia y Perú» →
     Chile, Colombia y Perú), con la nota «abierta a esos países según el aviso». Solo en remotas y nunca por encima
     de una restricción de residencia.
   - Medido el 26 nov: de 389 remotas en español de un solo país, unas 6 dicen de verdad que aceptan otros países
     («100% remoto desde LATAM») y ya las reconocía v49; con las frases nuevas no cambió ninguna. Es una regla
     correcta pero de poco volumen: el español de los avisos es local.

## 3. Fuentes en español para cualquier país (segunda entrega)

Cada fuente entra solo si pasa una prueba en vivo: se lista, trae descripción, se postula ahí mismo y su ficha se puede
comprobar. Orden: Bumeran y su familia (Zonajobs, Laborum, Multitrabajos, Konzerta: AR, MX, PE, VE, CL, EC, PA);
InfoJobs y Tecnoempleo (ES); Magneto y Hireline por búsqueda (CO, MX); Get on Board por categorías completas;
Chiletrabajos (CL). Quedan fuera OCC (bloquea) y los portales de empresas latinas (requieren descubrir empresas).

## Lo que no cambia

- Solo español e inglés; el idioma del perfil sigue siendo un filtro. Sin descripción o sin enlace comprobado en 24 h
  no se entrega.
- Si el aviso nombra un país, manda ese país (v49). La ciudad se exige en presenciales e híbridas.
- Sin IA, sin agregadores, sin envío automático, sin SQL nuevo. `ofertas` v1 no cambia.
- LinkedIn sin sesión ni cookie de nadie, con las mismas pausas.
- Los reportes públicos no llevan datos de clientes.
