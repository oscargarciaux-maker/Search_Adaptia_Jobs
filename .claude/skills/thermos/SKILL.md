---
name: thermos
description: Revisión a fondo de una rama antes de fusionarla, con dos revisores en paralelo (errores y seguridad, y calidad del código) y un informe único ordenado por gravedad. Úsala con "thermos", "revisa la rama a fondo", "revisión termonuclear" o antes de abrir cada PR.
---
<!-- Adaptado de Thermos (cursor/plugins), licencia MIT © 2026 Cursor (ver LICENSE en esta carpeta). Traducido y
ajustado a este proyecto el 18 nov 2026. -->

# Thermos

Dos revisiones de **solo lectura** a la vez sobre los cambios de la rama y un informe único. No arregla nada sola:
propone; lo grave se arregla si Oscar (o la tarea en curso) lo pide.

## Pasos
1. **Alcance.** Por defecto, la rama actual contra `origin/main`: `git fetch -q origin main` y
   `git diff origin/main...HEAD` (más `git diff --stat` y la lista de archivos). Si se pide un PR, un commit o
   archivos concretos, usa ese alcance. Si el diff está vacío, dilo y termina.
2. **Contexto.** Junta el diff completo y la lista de archivos cambiados. No pegues contenidos de `trabajo/`,
   CSV de clientes ni nada con datos reales: los revisores leen el repositorio por su cuenta.
3. **Lanza los dos revisores en el mismo mensaje**, en segundo plano, con el mismo diff y la misma lista:
   - `subagent_type: "thermos-errores"`: errores, roturas, seguridad, experiencia de desarrollo, funciones a
     medio activar y reglas de `CLAUDE.md`;
   - `subagent_type: "thermos-calidad"`: estructura, simplificación, tamaño de archivos, espagueti, límites y tipos.
   Pide a cada uno hallazgos ordenados con `archivo:línea` y evidencia.
4. **Une los resultados** cuando terminen los dos:
   - primero los hallazgos, sin repetidos; lo que encontraron los dos pesa más;
   - si discrepan, decide con tu propio criterio y di por qué;
   - verifica tú mismo lo grave antes de presentarlo (abre el archivo, sigue la llamada);
   - informe corto en español sencillo: **Arreglar antes de fusionar** · **Puede esperar** · **Bien hecho** (una
     línea), y la incertidumbre que quede.
5. Si la revisión es parte de un PR en curso: arregla lo grave en la misma rama, corre las pruebas
   (`python -m pytest -q`, y para la interfaz `npm run format:check`, `npm run lint`, `npm run build`) y menciona en
   el PR qué encontró Thermos y qué se corrigió.

## Notas
- Los revisores son `.claude/agents/thermos-errores.md` y `.claude/agents/thermos-calidad.md`.
- Complementa a `auditoria-codigo` (herramientas deterministas de todo el repositorio) y a `auditor-ux` (lo
  visual); Thermos mira solo lo que cambia la rama.
- Copia adaptada: si Cursor actualiza el original, se revisa a mano.
