---
name: auditor-ux
description: Audita la experiencia de uso de una página web, un dashboard o un panel de control (este panel u otro) y entrega un informe priorizado con evidencia, severidad y recomendación concreta. Úsala con "audita la UX", "revisa la usabilidad", "qué mejorarías del panel", "auditoría de experiencia", "revisa accesibilidad" o "por qué el flujo es difícil de entender". No implementa cambios: solo diagnostica y propone.
---

# Auditor UX

Auditoría heurística y por tareas, con capturas reales y criterios verificables. El resultado es un **informe priorizado**;
**no se cambia código** hasta que el responsable apruebe hallazgos concretos.

## 0. Reglas

- **Evidencia o no cuenta.** Cada hallazgo cita lo que se observó: captura (archivo y zona), texto literal, medida
  (contraste, tamaño, tiempo) o paso del recorrido donde falló. Nada de «podría confundir» sin decir a quién, dónde y por qué.
- **Datos ficticios.** En este repositorio, auditar con `python -m panel.api --demo` (no toca Supabase). Nunca abrir datos
  reales ni pedir credenciales para auditar. En otros sitios, solo páginas públicas o entornos de prueba autorizados.
- **No inventar usuarios.** Si falta saber quién usa la pantalla y para qué, se pregunta. Si no se puede preguntar, se
  declaran los supuestos al principio del informe.
- **Lenguaje sencillo** en el informe: el lector puede no ser técnico. Términos técnicos solo con explicación breve.
- **Separar** problema, causa probable y recomendación. Una recomendación es una acción concreta («cambiar el texto del
  botón a "Programar desde mañana"»), no un deseo («mejorar la claridad»).
- **No implementar.** Proponer; implementar solo lo aprobado, en un PR aparte, con pruebas.

## 1. Preparación (antes de mirar pantallas)

1. **Usuarios y objetivos.** Quién usa la pantalla (rol, frecuencia, conocimientos, dispositivo) y qué quiere lograr.
   En este panel: un operador no técnico que configura cargos, cupos y clientes y copia vacantes para WhatsApp.
2. **Tareas clave** (3 a 7), cada una con **criterio de éxito** observable y el **camino ideal** (mínimo de pasos).
   Ejemplo: «Crear un cliente que vive en México y acepta remoto — éxito: aparece en Clientes con "Vive en México ·
   Remoto" y estimación visible; ideal: 6 interacciones».
3. **Contexto técnico**: rutas, modos (demo/real), estados que dependen del tiempo (p. ej. «primera búsqueda mañana»),
   documentación de uso (`docs/PANEL_CONTROL.md`, `docs/GUIA_CLIENTE.md`) y decisiones vigentes (CLAUDE.md).
4. **Alcance**: escritorio (1440×900) y móvil (390×844) como mínimo; tablet (768×1024) si hay tablas o paneles laterales.

## 2. Captura de evidencia con Playwright

Chromium y Playwright ya están instalados (`require('playwright')`; no ejecutar `playwright install`). Script de
captura en el directorio temporal de la sesión, nunca dentro del repositorio.

- Levantar el sitio (`python -m panel.api --demo --port 8011` con `PANEL_DEMO_FILE` en un temporal).
- Por cada tarea: captura **antes y después de cada paso** relevante; nombrar `tarea-paso-dispositivo.png`.
- Registrar: número de clics/teclas, textos visibles en cada paso, errores de consola, peticiones fallidas, tiempo hasta
  respuesta visible (rendimiento percibido) y si apareció un estado de carga.
- **Estados a provocar**: vacío (sin clientes/cargos), carga (respuestas lentas: `page.route` con retraso), error
  (`page.route` con 500/422), datos largos (nombres de 100 caracteres, muchos ítems), permisos/sesión vencida.
- **Accesibilidad automatizable**:
  - Recorrido solo con teclado (Tab/Shift+Tab/Enter/Espacio/Escape): orden lógico, foco visible, sin trampas, el diálogo
    devuelve el foco al cerrarse.
  - Árbol de accesibilidad (`page.accessibility.snapshot()` o `getByRole`): cada control con nombre, cada campo con
    etiqueta, encabezados en orden, regiones (`main`, `nav`), `role=status`/`aria-live` en mensajes dinámicos.
  - Contraste de texto y de componentes: calcular con los colores computados (`getComputedStyle`) — 4,5:1 texto normal,
    3:1 texto grande (≥18,66 px negrita o ≥24 px) y bordes/iconos que transmiten información.
  - Objetivos táctiles: tamaño con `boundingBox()`; mínimo 24×24 px (WCAG 2.2 AA, 2.5.8), recomendado 44×44 en móvil.
  - Zoom 200 % y ancho 320 px: sin desplazamiento horizontal (`scrollWidth <= innerWidth`) ni contenido cortado.
  - Movimiento reducido (`reducedMotion: 'reduce'`) si hay animaciones.

## 3. Qué revisar (lista de comprobación)

Para cada punto, anotar «cumple / no cumple / no aplica» con evidencia.

### 3.1 Objetivos y recorrido de punta a punta
- ¿La primera pantalla responde «qué es esto, qué debo hacer ahora y qué pasó la última vez»?
- ¿Cada tarea clave se completa sin documentación? ¿Cuántos pasos de más respecto al camino ideal?
- ¿Las dependencias del flujo son explícitas? (p. ej. «primero cargos, luego clientes, luego programar»).
- ¿El sistema comunica **cuándo** tendrá efecto una acción (inmediato, mañana, tras la próxima búsqueda)?

### 3.2 Arquitectura de información y navegación
- Nombres del menú en el lenguaje del usuario, no del sistema. ¿Se entiende qué hay detrás de cada uno sin abrirlo?
- Agrupación: lo que se usa junto está junto; nada importante enterrado en un tercer nivel.
- Ubicación actual siempre visible (sección activa, título de página). Volver atrás no pierde trabajo.
- Duplicidades: la misma información o acción en dos sitios con nombres distintos.

### 3.3 Carga cognitiva y densidad
- Cuántas decisiones pide cada pantalla a la vez; valores por defecto razonables; divulgación progresiva de lo avanzado.
- Elementos decorativos o promocionales que compiten con la tarea (eliminar o reducir).
- Números sin contexto (¿≈ 0 de qué? ¿frente a qué meta?). Unidades y periodos explícitos.

### 3.4 Jerarquía visual
- Una acción principal clara por pantalla/diálogo; secundarias y destructivas diferenciadas.
- Lectura en F/Z: lo crítico arriba a la izquierda; tamaños y pesos coherentes con la importancia.
- Alineación, espaciado consistente (escala), agrupación por proximidad, líneas y tarjetas solo cuando separan algo.

### 3.5 Textos y microcopy (español claro)
- Verbos de acción en botones («Programar desde mañana», no «Aceptar»). Mismo término para el mismo concepto en todo
  el producto (cargo/rol/puesto; perfil/cliente).
- Etiquetas que dicen qué se pide y en qué formato; ayudas cortas junto al campo, no en un manual.
- Mensajes de error: qué pasó, por qué y cómo arreglarlo, sin culpar ni códigos técnicos.
- Fechas y horas con zona («1:17 a. m. hora de Colombia»), números con separadores locales.

### 3.6 Estados vacíos, carga y error
- Vacío: explica por qué está vacío y ofrece la acción siguiente (no una página en blanco).
- Carga: indicador en < 1 s; si tarda > 10 s, progreso o expectativa («hasta 30 s»); no bloquear lo que no depende de ello.
- Error: recuperable sin perder lo escrito; reintento; distingue «sin resultados» de «falló».
- Éxito: confirmación visible y proporcional (toast, cambio de estado), con lo que pasará después.

### 3.7 Retroalimentación, prevención y recuperación de errores
- Cambios sin guardar: aviso visible y confirmación al salir.
- Acciones irreversibles o con efecto programado: confirmación que resume el efecto (qué, cuándo, a quién).
- Validación en línea y al enviar, enfocando el primer campo con error; límites (máx./mín.) anunciados antes.
- Deshacer o archivar en vez de borrar cuando sea posible.

### 3.8 Consistencia y estándares
- Componentes iguales se ven y se comportan igual (botones, diálogos, chips, tablas). Iconos con el mismo significado.
- Convenciones de la plataforma (Escape cierra diálogos, Enter envía formularios, enlaces parecen enlaces).

### 3.9 Accesibilidad (WCAG 2.2 AA)
- 1.1.1 alternativas de texto · 1.3.1 estructura y relaciones (etiquetas, `fieldset/legend`, encabezados) ·
  1.4.3/1.4.11 contraste · 1.4.10 reflujo a 320 px · 1.4.12 espaciado de texto · 2.1.1 teclado · 2.4.3 orden del foco ·
  2.4.6 encabezados y etiquetas · 2.4.7/2.4.11 foco visible y no tapado · 2.5.3 nombre accesible contiene el texto
  visible · 2.5.8 tamaño del objetivo (24 px) · 3.3.1/3.3.3 identificación y sugerencia de errores · 3.3.7 entrada
  redundante · 4.1.2 nombre, rol y valor · 4.1.3 mensajes de estado.
- La información no depende solo del color (estados verdes/ámbar con texto o icono).

### 3.10 Móvil y responsive
- Sin scroll horizontal; menú alcanzable; diálogos que caben y desplazan su contenido; teclado que no tapa el campo.
- Tablas convertidas en tarjetas o con columnas prioritarias; objetivos táctiles ≥ 44 px recomendados.
- Acciones principales al alcance del pulgar; nada crítico solo en `hover`.

### 3.11 Rendimiento percibido
- Tiempo hasta contenido útil; saltos de diseño (CLS) al cargar; peticiones repetidas en cada tecla (usar espera/debounce).
- Respuesta optimista o indicador inmediato tras cada clic.

### 3.12 Heurísticas de Nielsen (resumen para clasificar)
1 visibilidad del estado · 2 lenguaje del usuario · 3 control y libertad · 4 consistencia · 5 prevención de errores ·
6 reconocer antes que recordar · 7 flexibilidad y eficiencia · 8 diseño estético y minimalista · 9 ayudar a reconocer y
recuperarse de errores · 10 ayuda y documentación.

## 4. Severidad (0–4)

| Nivel | Significado | Criterio |
|---|---|---|
| 4 | Catastrófico | Impide completar una tarea clave o provoca un resultado erróneo (p. ej. programar sin saber que se aplica). Corregir antes de entregar. |
| 3 | Grave | La tarea se completa con mucha dificultad, errores frecuentes o incumple WCAG A/AA en un control principal. |
| 2 | Moderado | Fricción repetida, confusión recuperable o incumplimiento AA en un elemento secundario. |
| 1 | Cosmético | Molestia menor, inconsistencia visual sin efecto en la tarea. |
| 0 | No es problema | Observación o mejora opcional. |

Prioridad = severidad × frecuencia (¿cuántas veces aparece en el uso normal?) × alcance (¿a cuántos usuarios/tareas
afecta?). Indicar el **esfuerzo** estimado (bajo/medio/alto) para ordenar «ganancias rápidas».

## 5. Formato del informe

1. **Resumen ejecutivo** (5 líneas): estado general, 3 problemas principales, 3 ganancias rápidas.
2. **Supuestos y alcance**: usuarios, tareas, dispositivos, modo (demo), fecha y versión (commit).
3. **Resultado por tarea**: éxito sí/no/parcial, pasos reales vs ideales, dónde se tropezó (con captura).
4. **Hallazgos priorizados** (tabla): ID · severidad · heurística/criterio WCAG · pantalla · evidencia (captura, texto,
   medida) · problema · recomendación concreta · esfuerzo.
5. **Accesibilidad**: tabla de criterios WCAG revisados con cumple/no cumple y medida.
6. **Lo que funciona bien** (para no romperlo).
7. **Siguientes pasos** propuestos, separando «sin riesgo» de «requiere decisión de producto».

Entregar como página privada (Artifact) con las capturas incrustadas o como Markdown si se pide archivo. Las capturas
de personas viendo el informe van a `deviceScaleFactor: 2`; las de comprobación interna, a 1.

## 6. Particularidades de este panel

- Modo demo: `python -m panel.api --demo` (datos ficticios; la estimación en vivo usa avisos ficticios).
- Recorrido mínimo: crear o editar cargos y cupos (suman 120) → crear cliente y perfil (país donde vive, modalidades,
  filtros) → leer la estimación y la búsqueda en vivo → guardar borrador o programar → ver Vacantes del cliente →
  copiar WhatsApp → revisar Actividad.
- Conceptos que suelen confundir y hay que verificar: borrador vs programado; «desde mañana a la 1:17 a. m.»; estimación
  (guardadas sin entregar) vs búsqueda en vivo (muestra) vs resultado real de la noche; un cargo por vacante.
- No proponer funciones fuera de alcance vigente (agente WhatsApp, seguimiento de candidaturas, IA en la búsqueda).
