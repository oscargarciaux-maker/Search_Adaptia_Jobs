> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v35: formulario del cliente más claro

**Fecha:** 16 de noviembre de 2026. **Sin SQL ni IA.** Los perfiles guardados siguen valiendo sin cambios.

## 1. Zonas horarias
- `Perfil.acepta_horario` pasa de tres claves fijas a una lista de hasta 12 zonas `UTC±H` o `UTC±H:30/45`
  (por ejemplo `UTC-5`, `UTC+5:30`). Cada zona cubre ±1 hora, para incluir el horario de verano.
- Las claves antiguas se leen como su zona: `us_este` = `UTC-5`, `us_pacifico` = `UTC-8`, `europa` = `UTC+1`. El
  resultado es el mismo que con v23. La zona de donde vive sigue contando siempre.
- El panel las elige de una lista con ciudades de referencia («UTC−5 · Bogotá, Lima, Nueva York»). El importador
  acepta `UTC-5`, `GMT+1` o los nombres antiguos.

## 2. «Otra…» restricción
- `{"tipo": "otra", "texto": "…"}` (2 a 80 caracteres, sin correos ni enlaces). Como las demás restricciones desde
  v27, nunca descarta: si el título o un requisito del aviso la nombra, la vacante llega después, con la etiqueta
  «Menciona «texto»».

## 3. Cifra del perfil: últimos 30 días
- La vista previa añade `ultimos_30` (vacantes que cumplieron el perfil en los últimos 30 días, entregadas o no) y
  `por_dia` (`ultimos_30 / 30`, un decimal). Es la cifra principal: un perfil sencillo ya no aparece con 0 solo porque
  lo disponible se entregó. «Aún sin entregar» queda como dato secundario.
- La búsqueda en internet ahora, si no encuentra nada nuevo, lo dice como una muestra y remite a la cifra de 30 días.

## 4. Pantalla
- El nombre ocupa media fila. El WhatsApp va en una fila: país (lista con el código de todos los países), número sin
  código y «Nombre para saludar». Se sigue guardando como `+código número`.
- Sin «Vacantes al día para este perfil». La primera ubicación se titula «¿Dónde vive?».
- Las explicaciones de años de experiencia y del nivel de inglés pasan al «ⓘ» junto al título.
- En todo el panel: el texto escrito se ve más fuerte que el de ejemplo; los números no muestran flechitas; las
  listas desplegables y el calendario tienen el estilo base; las barras de desplazamiento son finas y no se salen de
  las esquinas de los modales.

Pruebas: `pruebas/panel/test_formulario_v35.py` y los recorridos del formulario en `web/tests/control.spec.ts`.
