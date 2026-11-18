# Continuar el trabajo en otra cuenta o con otro asistente

**Fecha:** 18 de noviembre de 2026. Esta guía es para que una sesión nueva (otra cuenta de Claude Code, Codex u otro
asistente) siga el trabajo sin romper nada. Lo vigente manda en `CLAUDE.md`; esto es el punto de partida y el estado
del momento. No contiene claves ni datos de clientes, y nunca debe contenerlos.

## 1. Qué hay que preparar en la cuenta nueva (lo hace Oscar)

| Qué | Dónde | Por qué |
|---|---|---|
| Conectar GitHub | claude.ai → Ajustes → Conectores → GitHub. La app de Claude ya está instalada en el repositorio. | Para clonar, abrir PR y lanzar flujos. |
| Entorno de nube | claude.ai/code → entorno «Default»: red **sin restricciones**, sin script de arranque y sin variables. | Es lo mismo que se usa hoy. Python, Node y Chromium ya vienen instalados. |
| Secreto de red de Apify | En el entorno, en «Secretos de red»: host `api.apify.com`, cabecera `Authorization`, tipo Bearer, con el token de Apify. | El proxy pone la clave sola; nunca se escribe en el chat ni en el repositorio. |
| Plugins (opcional) | Los de esta cuenta, entre ellos `pr-review-toolkit`, `claude-md-management`, `claude-security`, `frontend-design`, `design`. | Revisión de PR, seguridad e interfaz. Ninguno es obligatorio para trabajar. |
| Conectores (opcional) | Figma, Gmail, Google Drive/Docs/Sheets/Calendar, Notion. | Este proyecto no los necesita para la búsqueda. |

**Lo que no hay que tocar:** los secretos de GitHub del repositorio (`SUPABASE_*`, `APIFY_TOKEN`, etc.) viven en
GitHub, no en la cuenta de Claude, y siguen funcionando igual.

**Lo que no pasa a la cuenta nueva:**
- la conversación anterior;
- las tareas programadas de la cuenta vieja;
- los archivos temporales de la sesión vieja, incluido el CSV de perfiles v6, que tiene datos de clientes y nunca va
  al repositorio. Si se necesita, Oscar lo vuelve a entregar a la sesión nueva o autoriza leer los perfiles en solo
  lectura.

## 2. Qué ya viene en el repositorio (no hay que copiar nada)
- **`CLAUDE.md`:** reglas, decisiones vigentes y la lista de contratos v2…v42 que hay que leer. Codex u otros
  asistentes deben leerlo como sus instrucciones; en Codex, como si fuera `AGENTS.md`.
- **Skills del proyecto en `.claude/skills/`:** `nueva-familia`, `ampliar-mapa`, `diagnostico`, `nueva-fuente`,
  `auditor-ux`, `auditoria-codigo`. En Claude Code se cargan solas; otro asistente puede leer su `SKILL.md` y seguir
  los pasos.
- **Documentos:**
  - `docs/COMO_FUNCIONA_AHORA.md`: el panorama vigente y corto;
  - `docs/HISTORIAL_CAMBIOS.md`: qué cambió y por qué, en lenguaje de cliente;
  - `docs/ACEPTACION_Y_ESTADO.md`: lo comprobado con fecha;
  - `docs/REVISION_FIABILIDAD.md`: los riesgos.

## 3. Cómo se trabaja con Oscar
1. **Idioma:** respuestas en español sencillo, sin jerga. Con tablas de antes y después cuando hay cifras.
2. **Un bloque de trabajo por PR:**
   - se trabaja en una rama;
   - antes de cada push: `python -m pytest -q` (hoy 1.558 pruebas) y `ruff check buscador pruebas panel`;
   - Oscar revisa y fusiona; **nunca auto-fusionar**.
3. **Interfaz (`web/`):** requiere Node 24. Se revisa con `npm run format:check`, `npm run lint`, `npm run build` y
   Playwright. La CI (`pruebas.yml`) también lo comprueba, igual que PostgreSQL.
4. **Probar de verdad:** Oscar quiere la prueba por el camino real. Se lanza `bodega.yml` (`workflow_dispatch`, modo
   `diario`, `prueba=false`), tarda unos 80 min, y se revisa en solo lectura:
   - el resumen publicado en la rama `publicado` (`trabajo/` y `datos/salud.json`);
   - los registros del flujo.
5. **Regla de cambio:** una regla nueva va primero a un contrato (`docs/CONTRATO_DATOS_vNN.md`), después al código con
   pruebas, y después a `CLAUDE.md`, al historial y a la guía.
6. **Si falta una decisión, se pregunta.** Ejemplos de cosas que Oscar aprobó explícitamente:
   - v41: lo que Indeed mostró hoy cuenta como comprobado;
   - v42: lo que el portal de la empresa listó hoy cuenta como comprobado.

## 4. Lo que nunca se hace (rompe el proyecto o la confianza)
- **Datos y claves:** ninguna clave, ID, correo ni dato de clientes en el repositorio, en los registros de Actions
  (son públicos) ni en reportes o cachés públicos. `pruebas/test_repositorio.py` lo revisa.
- **LinkedIn:** nunca con sesión ni cookie de nadie (`li_at` incluida), ni con actores de Apify que la pidan.
- **IA:** no se usa IA en la búsqueda ni en la afinidad; todo es código con pruebas.
- **Mensajes:** nada se envía solo. WhatsApp es copiar y pegar a mano.
- **SQL:** no se modifica SQL ya registrado; se añade una migración nueva. La clave administrativa solo sirve para
  preparar la base.
- **Datos históricos:** no se borran archivos históricos, snapshots, reservas ni colas para «arreglar» un error.
- **Otro repositorio:** no se toca `ux_job_agent`. JobSpy no se copia al repositorio.
- **Supabase:** no se abren datos reales de Supabase sin autorización de Oscar.

## 5. Estado al 18 nov 2026 (madrugada)
**Fusionado hasta el #122** (`main` = 98a90a1). Lo último:
- **v38:** cualquier ciudad del mundo dice su país.
- **v39:** LinkedIn se comprueba con su ficha pública.
- **v40:** la búsqueda se arma leyendo a cada persona, en los 62 países de Indeed.
- **#119:** ya no se archivan las vacantes que sirven a un perfil fuera de LATAM. Era la causa de que un perfil de Chicago
  quedara en 0.
- **v41:** Indeed visto hoy cuenta como comprobado.
- **Open Seat:** lista de empresas que contratan en LATAM.
- **v42:** portal de la empresa listado hoy cuenta como comprobado.

**Búsqueda #32** (17 nov, antes de v42):
- **Volumen:** 6.930 vacantes en la bodega, 2.637 nuevas y 1.374 enlaces comprobados.
- **Fuera de LATAM:** EE. UU. 935, Emiratos 17 y Europa 740.
- **Metas cumplidas:** Product Designer 70/70, Growth Marketing 10/10, QA Lead 5/5, Product Design Lead 5/5, y
  completos PM, QA, Fullstack y Product Owner.

**Búsqueda #33:** se lanzó el 18 nov a las 03:05 UTC con v42. Está por revisar.

**Comparar contra #32:**
- `verificacion_enlaces.vistas_portales_incorporadas`;
- comprobadas por fuente: portales 57 de 1.333, Computrabajo 5 de 286, Get on Board 1 de 75, Indeed 339 de 706;
- entregas por cargo;
- la persona de Chicago en Product Designer y Growth Marketing;
- la validación final (el único rojo aceptable es «meta incompleta»).

**Pendientes:**
1. **AI Product Manager** va 5 de 10. Oscar cambió en el panel el inglés de ese cargo; hay que confirmarlo con la
   siguiente búsqueda.
2. **Perfiles de Product Designer que solo aceptan español** (Costa Rica, México y Colombia) tienen 0 o 1 vacantes
   compatibles. Es una decisión del cliente, no un error.
3. **Computrabajo y Get on Board** casi sin comprobar por falta de tiempo. Revisar si v42 liberó tiempo para ellos.
4. **Revisar la corrida programada de las 6:30 a. m. de Bogotá** del 18 nov, con la misma comparación.
