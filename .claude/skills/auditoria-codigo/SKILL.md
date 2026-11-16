---
name: auditoria-codigo
description: Audita la calidad, la seguridad, las dependencias, el código sin uso y la base de datos de este repositorio con herramientas deterministas y los revisores oficiales, y entrega un informe priorizado en lenguaje sencillo. Úsala con "audita el código", "revisa la calidad", "qué sobra", "revisa la base de datos", "auditoría mensual", "¿se va a romper?" o antes de entregar el proyecto. Diagnostica y arregla solo lo crítico; lo demás lo propone.
---

# Auditoría de código

Complementa a `auditor-ux` (lo visual). Todo es código y reglas fijas: **sin IA en la búsqueda** (CLAUDE.md). El
informe va a Oscar en español sencillo: qué se revisó, qué está bien, qué hay que arreglar y por qué importa.

## 0. Reglas

- **Evidencia o no cuenta.** Cada hallazgo cita la herramienta, el archivo y la línea, o la cifra del inventario.
- **Nada se borra sin su visto bueno.** Código muerto, ramas, tablas o índices se listan como «propuesta de borrar»;
  se borran en un PR aparte, después de que Oscar los marque. Nunca `ofertas`, el archivo de enlaces ni los
  snapshots (CLAUDE.md).
- **Sin datos de clientes.** El inventario de la base solo da cifras y nombres de objetos.
- **Herramientas con versión fija:** `requirements-auditoria.lock` (Python) y `web/package-lock.json` (web).

## 1. Python (motor y servidor)

```bash
pip install --require-hashes -r requirements-auditoria.lock
ruff check buscador panel pruebas                  # errores reales: nombres, imports, bugbear
bandit -q -c pyproject.toml -r buscador panel -ll  # seguridad (alta y media)
vulture                                           # código sin uso (confirmar con grep antes de proponer)
pip-audit -r requirements.lock --disable-pip --no-deps   # vulnerabilidades conocidas en dependencias
python -m pytest -q                               # incluye test_dependencias y test_repositorio
```

- **Falsos positivos conocidos de bandit:**
  - B608, nombres de tabla constantes en `auditoria_producto.py`;
  - B108, la carpeta temporal de la demostración.
- **Fallos silenciosos:** buscar `except Exception` sin `registro.aviso(...)`. Si el error debe tolerarse, deja rastro
  con `buscador.registro.aviso("modulo:linea", e)`.

## 2. Web (panel)

```bash
cd web
npm run lint                          # React hooks, TypeScript y accesibilidad (eslint)
npm run sobrante                      # archivos, exports y dependencias sin uso (knip)
npm audit --audit-level=high --omit=dev
npm run build && npm test             # incluye la prueba axe (WCAG 2.1 AA) y el contraste en claro y oscuro
```

Localmente, Playwright usa `/opt/pw-browsers/chromium`; ver la nota de `CLAUDE.md` sobre `pw.local.config.ts`.

## 3. Base de datos

- **En el PostgreSQL aislado:**
  - `python -m pruebas.probar_inventario` comprueba RLS, permisos y `search_path` con todas las migraciones;
  - `EXPLAIN (ANALYZE, BUFFERS)` de las consultas lentas, ejecutadas con datos ficticios.
- **En Supabase real:** pedir a Oscar que corra **Actions → «Inventario de la base»**. Solo lee. Da:
  - tamaño frente al límite de 500 MB del plan gratis;
  - tablas sin RLS o con permisos públicos (lo hace fallar);
  - índices sin uso o duplicados;
  - claves foráneas sin índice;
  - funciones y vistas sin llamadas en el código.
- Un índice nuevo o un cambio de tabla va **siempre en una migración nueva** (nunca se edita una registrada).

## 4. Revisores oficiales (plugins de `.claude/settings.json`)

- `pr-review-toolkit`: revisores de código, pruebas, fallos silenciosos, tipos, comentarios y simplificación.
- `claude-security`: búsqueda profunda de vulnerabilidades.
- `security-guidance`: avisos al editar.
- Skills de sesión: `code-review` (nivel alto) y `simplify` sobre el diff de cada PR, y `security-review`.

## 5. GitHub y repositorio

- Ramas ya fusionadas: proponer su borrado (las borra Oscar en GitHub o con su permiso).
- Archivos sin referencias: `grep` de cada módulo en código, flujos y docs. Los generadores
  (`generar_lugares.py`, `generar_paises_mundo.py`) se usan a mano y se quedan.
- Rama `publicado`: lo que ningún flujo lee. `publicar.py` retira lo de la web antigua.

## 6. Informe

Una tabla por área: **Bien · Arreglado en este PR · Para decidir (con recomendación) · Riesgo aceptado**.

- **Formato:** si es para compartir, Artifact privado; si no, el mensaje.
- **Cierre:**
  - qué medir el próximo mes;
  - comparación con los límites de `docs/LIMITES.md`, si existe.
