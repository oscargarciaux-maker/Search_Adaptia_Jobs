# Contrato de datos v38: cualquier ciudad del mundo dice su país

**Fecha:** 17 de noviembre de 2026. **Sin SQL ni IA.** Pedido de Oscar: «que el sistema reconozca bien cualquier parte
del mundo… si es de USA, busca trabajo en USA, pero es de New York no le lleguen porque como no dice USA no funciona».

## 1. La ciudad dice el país
- `datos/lugares_mundo.json.gz` (GeoNames, CC BY 4.0, generado con `buscador/generar_lugares.py`) guarda ahora el
  país de cada ciudad de fuera (`extranjeros`: nombre → ISO2) y coordenadas (`coordenadas`). Antes (v19) solo decía
  «de fuera», sin país, y una persona que vive en EE. UU. no recibía «Chicago», «Seattle» o «Toronto».
- **Regla del país de una ciudad de fuera:** el país que tiene, con ese nombre, al menos 5 veces más habitantes que
  cualquier otro país («Chicago» → US, «London» → GB, «Kingston» → JM). Frente a un lugar de un país cubierto hacen
  falta 20 veces más y solo con el nombre principal, no con traducciones («Los Angeles» → US frente a Los Ángeles de
  Chile; «Colonia» sigue siendo Uruguay aunque Köln se llame así en español).
- **Si no llega, no se adivina:** «Cambridge», «Richmond», «Vancouver» o «Hamilton» solos siguen «de fuera» sin
  país. Con su sigla o su país («Cambridge, MA», «Vancouver, BC») sí se reconocen.
- Las regiones de fuera («Bavaria», «Ontario») dan su país si el nombre no se repite en otro.
- La lista curada de `datos/paises.yaml` siempre manda («Acre» es el estado de Brasil). En los países cubiertos no
  cambia nada: siguen decidiendo con su tabla curada y v15 (comprobado con las 4.476 vacantes de la bodega del 17 nov:
  solo cambian «SF», que ahora es EE. UU., y «Peru, IN, USA», que es Peru, Indiana, y ya no se entrega en Perú).
- Nombres que nunca son lugar: siglas de regiones de trabajo (APAC, EMEA, LATAM, DACH…) y puntos cardinales.

## 2. Formatos de ubicación
- Código postal tras el estado o la provincia: «New York, NY 10001», «Toronto, ON M5V 3L9».
- Provincias de Canadá (ON, QC, BC…) y estados de Australia (NSW, VIC, QLD, WA, SA, NT…).
- Una sigla que también es código de país la decide la ciudad: «Berlin, DE» es Alemania, «Toronto, CA» es Canadá,
  «Perth, WA» es Australia, «Seattle, WA» y «London, KY» son EE. UU.
- Una sigla de estado de EE. UU. manda sobre la ciudad homónima: «Paris, TX», «Toledo, OH» y «Panama City, FL» son
  EE. UU. (antes «Panama City, FL» se entregaba a Panamá). No suma EE. UU. si se nombra otro país («Barcelona, CT,
  Spain»), y tras una ciudad de España las siglas de comunidad son España («Sabadell, CT», «Vigo, GA»).
- «US-Remote», «Remote/USA», «USA - Remote»; «North America» = EE. UU. y Canadá (México solo si se nombra).
- Un tramo que es entero una ciudad de fuera manda sobre el país que contiene: «Jersey City» es EE. UU., no Jersey;
  «Atlanta, Georgia» es EE. UU. y «Tbilisi, Georgia» es Georgia.
- Apodos en `datos/alias_lugares.yaml` (editable): NYC, SF, Bay Area, Silicon Valley, GTA, CDMX, CABA…
- Áreas metropolitanas que la lista de v32 no trae: el país de la ciudad en GeoNames («Greater Toronto Area» → CA).

## 3. Los alrededores de la ciudad del perfil
- Una ciudad a 50 km o menos de una ciudad de la fila del perfil cuenta como la misma (`paises.RADIO_CIUDAD_KM`):
  «Brooklyn», «Jersey City» o «NYC» para New York; «Evanston» o «Naperville» para Chicago; «Chía» o «Soacha» para
  Bogotá; «Alcobendas» para Madrid. «Boston» no es New York ni «Toluca» es Ciudad de México.
- La ciudad del perfil se ubica primero en su país («Madrid» es España, no el Madrid de Cundinamarca).
- Sin coordenadas de alguna de las dos ciudades, no se acepta por distancia: nunca se adivina.

## 4. Lo que no cambia
- La admisión (`bodega`) y la afinidad usan `paises_mundo` como antes; ahora lo traen más avisos.
- Los países cubiertos (`paises`) y la confianza siguen las reglas de v13–v19 y v32.
- Para actualizar los datos: los tres comandos de la cabecera de `buscador/generar_lugares.py`.
