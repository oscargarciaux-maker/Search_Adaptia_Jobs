> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v36: nadie se queda bajo el mínimo si la bodega tiene vacantes para esa persona

**Fecha:** 17 de noviembre de 2026. **Sin SQL ni IA.** Caso que lo motivó: Danna (vive en Chicago, EE. UU.) recibió
2 vacantes y ninguna de Product Designer.

## Qué pasaba
1. La asignación por persona solo tomaba vacantes del **lote del día** o de lotes de días anteriores (v11). El lote se
   llena por cargo, y sus cupos se iban sobre todo en vacantes de LATAM. Lo que estaba en la bodega y servía a una
   persona de fuera nunca le llegaba si no entraba a un lote.
2. La corrida del 16 nov usó código anterior al PR #105: «Chicago, IL» no se reconocía como EE. UU. y unas 400
   vacantes se descartaron por «no se puede aplicar desde LATAM». Ya está corregido (#105).
3. Indeed solo buscaba en LATAM y España. Y solo buscaba en los países de oficina, no en el país de quien trabaja en
   remoto.
4. LinkedIn leyó la ficha completa de 40 de 765 avisos, casi todos remotos de LATAM. Sin descripción, una vacante no se
   puede entregar, y las búsquedas de Chicago o EE. UU. se quedaban sin ella.

## Qué cambia
- **Rescate con toda la bodega** (`panel/ejecutor._rescatar`). Después de reutilizar (v11) y antes de los posts, a cada
  perfil bajo 5 se le asignan vacantes de la bodega de la noche que cumplen:
  - **Lo que descarta (v27):** el cargo (exacto, similar o cercano; nunca solo por funciones), la ubicación y el idioma.
    Si nada cumple todo, se usan los niveles de ampliación de v9.
  - **No haberla recibido nunca esa persona.** Si otro cliente ya la recibió, sí puede llegarle.
  - **Máximo 2 por empresa.**
  - **Enlace comprobado como vigente en las últimas 24 h.**
- **Enlaces sin comprobación vigente:** se comprueban en ese momento, como mucho 80 en la corrida diaria (150 s) y 30
  en las horarias (60 s). Sin Apify ni formularios. La comprobación nueva se guarda en el catálogo para que el panel y
  WhatsApp puedan compartirlas.
- **Lo que no tocan las rescatadas:** no cuentan en el cupo ni van a `ofertas`. Llevan la marca `{"rescatada": "bodega"}`
  y el resumen de la corrida cuenta `rescatadas`.
- **Indeed** busca también en EE. UU., Canadá, Reino Unido, Irlanda, Alemania, Francia, Italia, Portugal, Países Bajos,
  Bélgica, Suiza, Austria, Australia y Nueva Zelanda, cuando un perfil los necesita. Cada cargo busca en los países de
  sus perfiles: oficinas y, desde v36, también el país de las filas con «remoto». Si un aviso de esos Indeed no nombra
  país («Remote»), se añade el del Indeed donde salió, como ya se hacía con los avisos sin ubicación.
- **LinkedIn** lee las fichas por turnos entre los lugares buscados: la primera de cada lugar, luego la segunda, etc.
  Así, las búsquedas de cada perfil (Chicago, EE. UU.) también reciben descripción.

Pruebas: `pruebas/panel/test_rescate_v36.py`.
