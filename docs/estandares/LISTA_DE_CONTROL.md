# Lista de control de estándares (PR 1.5, 16 nov 2026)

Cada auditoría (skill `auditoria-codigo`, cada mes) se mide contra esta lista.

**Estados:**
- ✅ cumple, con la prueba o el archivo que lo demuestra;
- ⚠️ parcial o riesgo aceptado;
- ⬜ pendiente.

## 1. Seguridad web: OWASP ASVS nivel 2 y OWASP API Security Top 10

| Control | Estado | Evidencia |
|---|---|---|
| Sesión en cookie `HttpOnly`, `Secure`, `SameSite=Strict` (ASVS 3.4) | ✅ | `panel/api.py` login; `test_api_autoriza_solo_operador…` |
| Cada petición verifica al operador contra Supabase; no se confía en la cookie (API2 autenticación) | ✅ | middleware `proteccion` |
| Lista cerrada de operadores con correo confirmado (API5 autorización por función) | ✅ | `PANEL_OPERATOR_EMAILS` |
| Escrituras solo desde el mismo origen (protección CSRF por `Origin`) | ✅ | middleware `proteccion` |
| Límite de intentos de inicio de sesión (API4 consumo de recursos) | ✅ | `intentos` en `panel/api.py` |
| Tamaño máximo de petición: 1 MB (API4) | ✅ | middleware `proteccion` |
| Cabeceras: CSP estricta, `nosniff`, `X-Frame-Options DENY`, `Referrer-Policy`, HSTS (ASVS 14.4) | ✅ | HSTS desde el PR 1.5; prueba de cabeceras |
| La credencial de servicio nunca va al navegador (ASVS 2.10) | ✅ | `test_api…`: `service_role` no aparece en `/api/session` |
| Ninguna clave, ID ni dato de clientes en el repositorio | ✅ | `pruebas/test_repositorio.py`; hook `bloquear_secretos.py` |
| Validación estricta de entradas (`extra="forbid"`, longitudes) (API3, API6) | ✅ | `panel/modelos.py` (pydantic) |
| Dependencias sin vulnerabilidades conocidas (A06) | ✅ | `pip-audit` y `npm audit` en CI (job `auditoria`) |
| Dependencias fijadas con huella (integridad, A08) | ✅ | `requirements.lock` con `--require-hashes`; `test_dependencias.py` |
| Errores sin detalles internos al usuario (ASVS 7.4) | ✅ | `_mensaje_sql` y manejadores de error |
| Registro de errores tolerados sin datos sensibles (ASVS 7.1) | ✅ | `buscador/registro.py` |
| La sesión no vence mientras se usa (refresh token) | ⬜ | PR 5 (hoy dura 1 h) |

## 2. Accesibilidad: WCAG 2.2 AA

| Control | Estado | Evidencia |
|---|---|---|
| Contraste ≥ 4,5:1 (≥ 3:1 en texto grande), en claro y en oscuro | ✅ | `web/tests/contraste.ts` + axe |
| Sin fallos «serios» o «críticos» de axe (WCAG 2.1 A y AA) en todas las pantallas y en el formulario | ✅ | prueba «auditoría axe» |
| Cada campo con su etiqueta asociada | ✅ | `eslint-plugin-jsx-a11y` en CI |
| Foco visible y retorno del foco al cerrar diálogos | ✅ | `Dialog`; pruebas Playwright |
| Objetivos táctiles ≥ 24 px (2.5.8); los principales ≥ 40 px | ✅ | prueba de botones táctiles |
| Respeta «reducir movimiento» | ✅ | `@media (prefers-reduced-motion)` |
| Arrastrar y soltar con alternativa por botón (2.5.7) | ⬜ | PR 2, al crear la grilla de cargos |

## 3. Base de datos: Production Checklist de Supabase y revisiones al estilo Splinter

| Control | Estado | Evidencia |
|---|---|---|
| RLS activo en todas las tablas públicas | ✅ | `probar_inventario`, flujo «Inventario de la base» |
| Sin permisos para `anon`/`authenticated` | ✅ | igual |
| Funciones `security definer` con `search_path` fijo | ✅ | igual |
| Migraciones con hash registrado, sin editar las ya aplicadas, respaldo cifrado antes | ✅ | `migraciones.py`, `probar_migraciones` |
| Copia semanal cifrada y restauración probada | ✅ | `respaldo.yml`; `probar_migraciones` (restauración) |
| Claves foráneas con índice | ⚠️ | faltan `panel_asignaciones.vacante_id` y `panel_ejecuciones.revision`; se evalúan con el inventario real (PR 3, velocidad) |
| Índices sin uso o duplicados revisados | ⬜ | correr el inventario real y decidir |
| Tamaño frente al plan gratis (500 MB) | ⬜ | correr el inventario real cada mes |

## 4. 12-Factor App (configuración y procesos)

| Factor | Estado | Evidencia |
|---|---|---|
| Configuración y secretos en el entorno, no en el código | ✅ | secretos de GitHub y del alojamiento |
| Dependencias declaradas y aisladas | ✅ | `requirements.lock`, `package-lock.json`, Docker |
| Procesos sin estado (el estado vive en Supabase y en la rama `publicado`) | ✅ | `docs/OPERACION_Y_RECUPERACION.md` |
| Registros a la salida estándar con marcas de tiempo | ✅ | `bodega.etapa`, `registro.aviso` |
| Igualdad entre desarrollo y producción | ⚠️ | la demostración usa datos ficticios; Docker reproduce producción |

## 5. Higiene del repositorio (OpenSSF)

| Control | Estado | Evidencia |
|---|---|---|
| CI en cada push y PR (pruebas, SQL, navegador, auditoría) | ✅ | `.github/workflows/pruebas.yml` |
| Actualizaciones propuestas por Dependabot | ✅ | `.github/dependabot.yml` |
| Permisos mínimos en los flujos (`contents: read` salvo publicar) | ✅ | cada flujo |
| Protección de la rama `main` (no fusionar en rojo) | ⬜ | la activa Oscar en GitHub → Settings → Branches |
| OpenSSF Scorecard | ⬜ | la acción oficial requiere permisos de escritura de seguridad; se evalúa con la protección de rama |

## 6. Objetivos de servicio (al estilo SRE)

| Objetivo | Medida | Estado |
|---|---|---|
| La búsqueda diaria termina antes de las 8:30 (Bogotá) | `panel_ejecuciones` y Actions | ⬜ se mide una semana |
| Cada perfil recibe ≥ 5 vacantes en el 95 % de los días | resumen por cliente | ⬜ se mide una semana |
| Ninguna corrida sin registro (cortes por tiempo) | Actions | ✅ registro por etapas desde el 15 nov |
