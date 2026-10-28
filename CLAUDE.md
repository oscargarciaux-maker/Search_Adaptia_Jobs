# CLAUDE.md — Buscador de vacantes LATAM

## Qué es
Una página privada donde se escribe un cargo y un país de LATAM y salen, en segundos, todas las vacantes abiertas de ese
cargo y de sus cargos parecidos (exactos, similares y cercanos, todos los niveles) de los últimos 30 días, listas para
copiar a un grupo de WhatsApp o bajar en Excel. Lo usa Oscar con sus clientes y después se le entrega a otra persona.
El plan completo, con el paso a paso, está en `docs/PLAN.md`: léelo antes de trabajar.

## Reglas que no se cambian sin preguntarle a Oscar
- **Volumen antes que filtros.** Solo filtran: el cargo (mapa de cargos), 30 días de antigüedad, que siga abierta, que no
  esté repetida y que se pueda aplicar desde el país elegido. Inglés, nivel y años se muestran como columnas.
- **Solo enlaces donde se postula de verdad:** el sistema de postulación de la empresa (Greenhouse, Lever, Ashby…), su
  página de empleo o un portal donde se postula ahí mismo (LinkedIn, Indeed, Computrabajo…). Nunca agregadores ni sitios
  de pago (Jooble, BeBee, trabajo.org, JobLeads, Talent.com…): se rastrea el original o la vacante no se guarda.
- **Enlace principal = LinkedIn** cuando la vacante está ahí; el directo de la empresa va en `enlace_directo`.
- **LinkedIn nunca con la sesión ni la cookie de nadie** (`li_at` incluida). Ni actores de Apify que la pidan.
- **Nada se envía solo:** la página arma el texto y Oscar lo pega en WhatsApp.
- **La búsqueda no usa IA.** Todo es código con pruebas. La IA solo construye y amplía el mapa de cargos leyendo
  archivos cortos (`reportes/`), nunca la bodega completa.
- **Traspasable:** nada depende de las cuentas personales de Oscar. Ninguna clave, ID, correo ni dato de clientes en el
  repositorio (las claves van en los secretos de GitHub y Cloudflare). `pruebas/test_repositorio.py` lo revisa.
- **No se toca el repositorio `ux_job_agent`** (el agente personal de Oscar): si se necesita código de allá, se lee y
  se copia aquí.
- Si algo del plan no está claro o falta una decisión, se pregunta antes de inventar una regla.

## Cómo se trabaja
- Un paso del plan por sesión, en una rama, con un PR que Oscar revisa y fusiona.
- Pruebas obligatorias antes de cada push: `python -m pytest -q` (desde el paso 8 también `node --test pruebas/`).
- Lo que cambia sin tocar código vive en `datos/` (mapa de cargos, países, dominios, empresas, `config.yaml`).
- Respuestas a Oscar en español y en lenguaje sencillo.

## Estructura
- `docs/` plan, instalación y traspaso · `datos/` archivos editables · `buscador/` Python (fuentes, normalizar,
  familias, paises, enlaces, etiquetas, bodega, publicar, diagnostico) · `web/` la página · `functions/api/` funciones de
  Cloudflare · `pruebas/` · `reportes/` (los escribe la bodega) · `.claude/skills/` · `.github/workflows/`.

## Estado
- Paso 1 (esqueleto): carpetas, este archivo, `README.md`, `docs/PLAN.md`, `datos/config.yaml` y `pruebas.yml`.
