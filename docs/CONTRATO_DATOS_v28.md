> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v28: posts con más fuerza

**Fecha:** 16 de noviembre de 2026. **Amplía:** [v11](CONTRATO_DATOS_v11.md) (posts para perfiles bajo 5) y
[v27](CONTRATO_DATOS_v27.md).

**No cambia:**
- `ofertas` ni el CSV: los posts siguen fuera de ambos;
- el cupo del día;
- el filtro contra basura (bancos de talento, listas de terceros, gente buscando empleo, cursos).

**Sin SQL ni IA.**

## Por qué
La noche del 15 nov se leyeron 23 posts y ninguno llegó. 9 se descartaron solo porque no decían país ni si eran
remotos. Oscar pidió no descartarlos todos ni mandarlos todos a «Por confirmar»: que el sistema busque más
información, sobre todo la ubicación, y que lleguen marcados para que el cliente sepa que no tienen todo.

## Qué cambia
1. **Un país de fuera nombrado es ubicación.** Antes, «New York» o «Madrid» contaban como «sin país», porque solo se
   buscaban países cubiertos. Ahora se reconocen con la tabla ISO (`paises.paises_en_texto`) y cada perfil decide
   (v23).
2. **Pistas de ubicación** (`publicaciones_apify.pistas_ubicacion`), cuando el post no nombra ningún país ni dice
   remoto. Gana la primera pista que aparece:
   1. la ubicación de quien publicó, si el actor la trae;
   2. el prefijo telefónico (+57, +52, +593…; +1 y +7 no cuentan por ambiguos);
   3. la moneda (COP, MXN, CLP…; «pesos colombianos»);
   4. el dominio de correos o enlaces (.com.co, .com.mx, .cl, .es…; «.co» solo no cuenta: lo usan empresas de todo
      el mundo);
   5. el país donde la misma empresa tiene todas sus otras vacantes confirmadas en el catálogo
      (`paises_por_empresa`);
   6. el `JobPosting` de la primera ficha enlazada, leído como en v16 (`confirmar_ubicacion`):
      - solo GET y nunca formularios;
      - solo en dominios de la lista fija de sistemas de postulación y portales (`datos/dominios.yaml`), para que quien
        escribe el post no pueda elegir a qué servidor se conecta el sistema;
      - con un tope de 1 MB y 12 s, y sin seguir redirecciones fuera de esa lista.
3. **Marcas del post** (en el catálogo, solo en posts):
   - `ubicacion_deducida`: de dónde salió el país;
   - `ubicacion_sin_confirmar`: ninguna pista sirvió. Su modalidad queda vacía en vez de suponer presencial.
4. **Asignación** (`afinidad.evaluar_post`, `ejecutor._posts`), solo a perfiles bajo el mínimo de 5 y siempre después
   de las vacantes formales:
   - un post deducido o sin confirmar que solo falla por país o modalidad se admite. Idioma, fecha y lo demás se
     exigen igual;
   - orden: primero los posts con ubicación clara, después los deducidos y al final los sin confirmar;
   - **máximo 2 «sin confirmar» por perfil al día**;
   - la asignación guarda `{"post_ubicacion": "deducida"|"sin_confirmar", "pista": …}`.
5. **Etiquetas:**
   - en el panel, «Post · ubicación deducida» o «Post · ubicación sin confirmar»;
   - en el WhatsApp, «(ubicación deducida, confírmala)» o «(no dice dónde es: pregúntalo)».
6. **Más alcance con el mismo presupuesto:**
   - consultas con el país de quien va corto o «remoto» (`consultas_post(..., lugares)`), hasta 8 por noche;
   - `posts_rescate` de 30 a 50, unos USD 0,11.
   - El tope de USD 5 al mes no cambia.
7. **Medición:** el informe suma `ubicacion_deducida` (cuántos por cada pista) y `ubicacion_sin_confirmar`.

## Excepción a la regla general
«País desconocido no completa la meta» sigue valiendo para todas las vacantes. Por decisión de Oscar (16 nov), un
**post** sin pistas puede completar el mínimo de 5, solo con su etiqueta y su tope diario.

## Pruebas
`pruebas/panel/test_posts_v28.py`:
- cada pista;
- empresa con un solo país;
- post deducido y post marcado;
- `entregable_post`;
- ficha enlazada;
- consultas con lugar;
- texto de WhatsApp;
- `registrar` con tope de 2.
