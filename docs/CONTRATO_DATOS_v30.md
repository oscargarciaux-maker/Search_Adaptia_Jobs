> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v30: dónde trabajaría, en filas

**Fecha:** 16 de noviembre de 2026.
**Amplía:** [v8](CONTRATO_DATOS_v8.md) (residencia y modalidades), [v23](CONTRATO_DATOS_v23.md) (permiso legal,
horario, ciudades) y [v24](CONTRATO_DATOS_v24.md) (la ciudad implica el país).
**Sin SQL:** el perfil vive en el JSON de la configuración. **Sin IA.**

## Por qué
Oscar pidió las ubicaciones en filas («Ciudades · Países · modalidades», más «Añadir otra»), en lugar de «se mudaría a»,
las casillas de países y «puede trabajar legalmente en». Un mismo perfil puede aceptar cosas distintas en cada lugar.
Por ejemplo, Danna: remoto desde Colombia, e híbrido o presencial solo en Chicago. Con los campos sueltos eso no se
podía decir.

## Qué cambia
1. **`Perfil.ubicaciones`:** hasta 10 filas `{paises, ciudades, modalidades}`.
   - La primera fila es donde vive.
   - Cada fila necesita un país o una ciudad, y al menos una modalidad.
   - Las regiones («LATAM», «Sudamérica»…) se convierten en sus países al guardar.
2. **Evaluación** (`panel/afinidad.lugar`): la ubicación cumple si **alguna fila** acepta la vacante.
   - Remota: abierta a uno de los países de la fila, mundial, o con horario aceptado (`acepta_horario`, que sigue
     siendo del perfil).
   - Híbrida o presencial: oficina en un país de la fila o en una de sus ciudades. Si la fila tiene ciudades, no se
     acepta otra ciudad.
   - Si ninguna fila sirve, los motivos son los de la primera, que es donde vive.
3. **Compatibilidad:**
   - Con filas, los campos de siempre (`vive_en`, `modalidades`, `ciudades`, `paises_presenciales_extra`,
     `puede_trabajar_en`) se calculan desde ellas. Así la búsqueda por lugares (v24) y la admisión los siguen leyendo
     igual.
   - Sin filas (perfiles anteriores e importador), `Perfil.filas` las arma con el mismo resultado que tenían:
     - donde vive, con sus modalidades y ciudades;
     - los países de la mudanza, en híbrido o presencial;
     - el permiso legal, en remoto.

     No se guardan: quien edite esos campos sigue viendo su efecto. El panel recibe las filas ya armadas.
   - El importador conserva sus columnas (`vive_en`, `modalidades`, `ciudades`, `se_mudaria_a`, `puede_trabajar_en`),
     que se convierten así. `admitir_*` se acepta, pero desde v27 no tiene efecto.
4. **Corrección:** al buscar «otra ciudad», el nombre de la ciudad se compara solo con nombres de país completos. «New
   York» es también un estado y ya no se toma por un país.
5. **Panel:**
   - la sesión trae los prefijos telefónicos para mostrar la bandera del WhatsApp (solo se muestra);
   - los contactos se cargan con el panel y se guardan sin hacer esperar el formulario.
6. **Sugerencias de la vista previa:** las de «admitir experiencia o inglés no informados» se retiran, porque desde v27
   no descartan. Se añaden «Añadir una ubicación donde trabajaría», «Añadir la ciudad» y «Añadir un país donde puede
   trabajar en remoto».

## Pruebas
- `pruebas/panel/test_ubicaciones_v30.py`:
  - perfil anterior en filas con el mismo resultado;
  - filas de Danna;
  - regiones;
  - fila sin lugar;
  - remota cercana;
  - `/api/config` con filas.
- **Playwright:**
  - filas en el formulario (añadir y quitar);
  - inglés condicional;
  - ubicaciones guardadas;
  - bandera, contacto precargado y guardado sin esperar.
