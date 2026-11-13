# Contrato de datos v20 — años de experiencia en un solo campo (±3)

Vigente desde el 13 nov 2026. Amplía el perfil del panel (contratos v6 y v8). Sin columnas nuevas en `ofertas` ni SQL
nuevo: la configuración del panel se guarda como JSON.

## Qué cambia

- **Campo nuevo del perfil: `experiencia_anos`** (entero de 0 a 40, o vacío). Son los años de experiencia que tiene la
  persona.
- **El servidor calcula el rango.** Con un valor, el perfil busca vacantes que pidan de 3 años menos a 3 años más:
  - `experiencia_min = max(0, experiencia_anos - 3)`;
  - `experiencia_max = min(40, experiencia_anos + 3)`.
  - Lo hace la validación del modelo (`panel/modelos.py`), así que el panel, la vista previa, la búsqueda en vivo y la
    selección nocturna usan siempre el mismo rango.
- **Vacío = sin filtro de experiencia**, igual que antes con mínimo y máximo vacíos. La casilla «Admitir experiencia no
  informada» sigue funcionando igual.

## Lo que sigue igual

- **El filtro no cambia** (`panel/afinidad.evaluar`): compara los años mínimos que pide el aviso con
  `experiencia_min/max`, que siguen existiendo.
- **El rescate por persona (v11)** sigue sumando ±2 años sobre ese rango cuando una persona tiene menos de 5 vacantes.
- **Perfiles guardados antes de v20** (sin `experiencia_anos`) conservan su mínimo y máximo y se filtran igual que hoy.
  Solo pasan a ±3 cuando el operador escribe los años en el formulario. Nada cambia sin que lo decida el operador.
