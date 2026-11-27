> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v23 — ubicaciones del mundo, permiso legal y horario compatible

Vigente desde el 15 nov 2026, por decisión de Oscar tras la reunión con el cliente (punto 4). Amplía el perfil del
panel (v8, v21, v22) y los datos de la vacante en el catálogo. Sin columnas nuevas en `ofertas` ni SQL nuevo. Sin IA.

## Decisión vigente

- La **residencia de un perfil puede ser cualquier país**. Reemplaza el límite «LATAM hispanohablante + España» para la
  residencia; la cobertura de búsqueda sigue priorizando LATAM y España.
- Solo avisos en español o inglés, como siempre.

## Vacante (JSON del catálogo `catalogo_vacantes.datos`)

- **`paises_mundo`**: ISO2 de todos los países que el aviso nombra como lugar o como alcance permitido («Berlin,
  Germany» → DE; «Remote, US only» → US), cubiertos o no. `paises` sigue con solo los cubiertos, como antes.
- **`alcance_mundial`**: sí cuando el aviso es remoto para cualquier lugar (worldwide, anywhere).
- **`zona_utc`**: `[mínimo, máximo]` en horas UTC cuando el aviso pide una franja horaria (UTC-5, EST, CET…).
- Las vacantes guardadas antes de v23 no traen estos campos y se evalúan como hasta ahora.

## Perfil

- **`vive_en`**: cualquier ISO2 de `datos/paises_mundo.yaml`.
- **`paises_presenciales_extra`** («También se mudaría a…»): cualquier país, hasta 60.
- **`ciudades`** (opcional, hasta 10): para presencial o híbrida, solo esas ciudades. Descarta solo si el aviso nombra
  otra ciudad; sin ciudad en el aviso, no descarta.
- **`puede_trabajar_en`** (hasta 30): países donde la persona puede trabajar legalmente aunque no viva allí. Una remota
  restringida a esos países le llega.
- **`acepta_horario`**: entre `us_este` (UTC-5), `us_pacifico` (UTC-8) y `europa` (UTC+1). Siempre cuenta además la
  zona del país donde vive.

## Reglas del filtro

- **Remota**: sirve si el país donde vive está en `paises`, o si `paises_mundo` incluye donde vive o donde puede
  trabajar, o si tiene `alcance_mundial`.
- **Horario compatible** (cambia la regla anterior «horario compatible no completa la meta»): una remota sin país que
  solo pide una franja horaria sirve si la franja cruza una zona aceptada por el perfil o la de su país (±2 h).
- **Híbrida o presencial**: la oficina (`paises` o `paises_mundo`) está donde vive o donde se mudaría, y, si hay
  `ciudades`, el aviso no nombra otra ciudad.
- La confianza de país se exige igual que antes, salvo el caso del horario aceptado.

## «Por confirmar»

Al confirmar se pueden marcar varias etiquetas a la vez: regiones (LATAM, España, Europa, Mundo) y países de cualquier
parte (por ejemplo LATAM y EE. UU.). Los cubiertos van a `paises`; todos, a `paises_mundo`.

## Pendiente (paso 6)

Buscar avisos en los países de residencia fuera de LATAM y España, y no descartarlos al ingresar. Hasta entonces, un
perfil que vive fuera de LATAM recibe sobre todo remotas mundiales.
