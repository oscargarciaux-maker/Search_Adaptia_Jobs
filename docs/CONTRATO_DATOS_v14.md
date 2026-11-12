# Ubicaciones a prueba de abreviaturas, ciudades y repeticiones — v14

Revisión del 12 de noviembre de 2026. Amplía v13. Sin SQL nuevo. Origen: la vacante 82 del listado de revisión
(«MX MX») quedó «sin confirmar» aunque era México.

## Reglas nuevas (`buscador/paises.py`, `datos/paises.yaml`)

1. **Códigos sueltos o al final de un tramo**, tras una coma o un guion:
   - **Dos letras:** «MX», «MX MX», «Bo», «Remote - MX».
   - **Tres letras ISO, solo en mayúsculas:** «Mumbai, IND», «Remote - USA», «Lima, PER».
   - El código de un país cubierto se lee como ese país. El de un país extranjero, como «pais extranjero».
   - Un código ambiguo tras una ciudad (CO, AR, PA también son estados de EE. UU.) solo cuenta si la ciudad es de ese
     país: «Bogotá, CO» → Colombia; «Conshohocken, PA» sigue «por confirmar».
2. **Ubicación repetida:** «Buenos Aires Buenos Aires» se lee una vez.
3. **Ciudad dentro de un texto más largo** («Área metropolitana de Bogotá D.C.», «Las Rozas de Madrid»):
   - Cuenta solo si todas las ciudades halladas son de un único país.
   - Gana la frase más larga: «Santiago de Compostela» es España, no Chile.
   - Los nombres que existen en varios países (Santiago, Córdoba, Valencia, Granada, Guadalajara, Cartagena, San José…)
     nunca deciden solos.
4. **«Autorizado para trabajar en el país»** se refiere al país del propio aviso cuando la ubicación lo nombra. Una
   frase de residencia que no se entiende ya no vuelve «por confirmar» una ubicación que es solo extranjera.
5. **Más lugares:**
   - municipios de España y variantes de Bogotá y Buenos Aires;
   - ciudades extranjeras frecuentes en los avisos: India, EE. UU., Japón, Australia, Polonia, Emiratos…

## Efecto medido (inventario del 12 nov, 9.964 vacantes)

- «Por confirmar»: de 816 a 439. Lo que queda casi siempre no dice el país en ningún lado («Remote», «Remoto», «N/A»)
  o es ambiguo de verdad (Granada).
- Ninguna vacante que ya tenía país lo cambia.
- Vacantes que se pueden entregar: de 3.877 a 3.974, porque se recuperan vacantes válidas de LATAM y España.

## Revisión de `ofertas` (flujo de v13)

- Si se escriben datos para borrar pero no se marca «aplicar», el resumen avisa que no se borró nada.
- «borrar_tambien» acepta también números de las propuestas, que de todos modos se borran.
- Un número no puede estar a la vez en «conservar» y en «borrar_tambien».
