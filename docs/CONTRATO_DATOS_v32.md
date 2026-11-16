# Contrato de datos v32: más vacantes y menos «por confirmar»

**Fecha:** 16 de noviembre de 2026 (después de la búsqueda de las 7:38: 37 de 120, con el país como el mayor corte y
127 «por confirmar»).
**Amplía:**
- [v27](CONTRATO_DATOS_v27.md): qué descarta;
- [v17](CONTRATO_DATOS_v17.md): reglas sin IA;
- [v19](CONTRATO_DATOS_v19.md): lugares del mundo.

**Sin SQL ni IA.**

## Qué cambia
1. **El inglés exigido vuelve a descartar** (decisión de Oscar, 16 nov):
   - si el aviso **exige** un nivel mayor que el del perfil, no llega: «Head of Design» pide C1 y el perfil es B1;
   - si lo pide como deseable o no lo dice, sí llega.

   Vale para todos los clientes. Donde v27 dice que el inglés solo ordena, desde v32 el inglés exigido descarta.
2. **Áreas metropolitanas con formato de LinkedIn** (`datos/areas_metropolitanas.yaml`, editable):
   - «Roma y alrededores», «Greater Rome Area», «Área metropolitana de Guadalajara»: el área de la ciudad grande,
     aunque el nombre exista en otros países. Ejemplos: Roma → Italia; Granada → España; Guadalajara → México.
   - Sin el sufijo, un nombre ambiguo («Granada») sigue preguntándose.
3. **Sugerencias claras que se aplican solas** en la cola de la noche (`panel/revision.preparar_cola`):
   - si la sugerencia por reglas (`panel/sugerir.py`, v17) es «sí» con países cubiertos y sin extranjeros, o «otro
     país» con solo lugares extranjeros, la vacante se decide sola y no ocupa la bandeja;
   - queda con el motivo «decidida por sugerencia clara». No enseña al aprendizaje: solo aprende de lo que decide la
     persona;
   - lo dudoso (mezclas, Europa o EMEA, «cualquier lugar», sin evidencia) sigue preguntándose.
4. **Las fuentes respetan su límite de tiempo:**
   - un tiempo restante de 0 detiene la fuente. Antes se leía como «sin límite», y LinkedIn tardó 101 min el 16 nov;
   - LinkedIn usa ~65 % de su tiempo para buscar y el resto para releer fichas sin descripción. Esa relectura dio
     214 descripciones el 16 nov.

## Pruebas
- `pruebas/test_areas_metropolitanas.py`
- `pruebas/test_limites_fuentes.py`
- `pruebas/panel/test_control.py::test_v32_ingles_exigido_mayor_descarta_y_el_deseable_no`
- `pruebas/panel/test_revision.py::test_v32_sugerencia_clara_se_aplica_sola_y_la_dudosa_espera`
