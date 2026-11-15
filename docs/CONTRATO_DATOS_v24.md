# Contrato de datos v24 — búsqueda guiada por cada perfil y ciudades con mudanza

Vigente desde el 15 nov 2026 (paso 6a de los ajustes de la reunión con el cliente). Amplía v23. Sin columnas nuevas en
`ofertas` ni SQL. Sin IA.

## Búsqueda por perfil

- En modo panel, LinkedIn busca con los lugares de cada perfil activo:
  - remoto en su país, remoto LATAM y remoto mundial;
  - los países de oficina (residencia y mudanza);
  - **desde v24, cada ciudad del perfil** cuando acepta presencial o híbrida.
- Los países fuera de la tabla propia se buscan por su **nombre en inglés** (`nombre_en` de `datos/paises_mundo.yaml`).
  LinkedIn no reconoce «Alemania», pero sí «Germany».
- Las demás fuentes (Indeed, Computrabajo, Get on Board, tableros remotos, portales de empresas) siguen como búsqueda
  amplia, que completa lo que falte.

## Ciudades con mudanza

- `ciudades` del perfil = **ciudades donde trabajaría**: la suya y aquellas a las que se mudaría, de cualquier país.
- En una presencial o híbrida, si la ubicación del aviso nombra una de esas ciudades, la ubicación cumple **aunque su
  país no esté** en la residencia ni en «También se mudaría a…»: la ciudad implica el país.
- Si el perfil tiene ciudades y el aviso nombra otra ciudad, se descarta. Un aviso sin ciudad no se descarta.

## Admisión en modo panel

- Al ingresar avisos, una vacante sin países cubiertos (`paises` vacío) se conserva si `paises_mundo` cruza los
  **países objetivo** de los perfiles activos o si pide una franja horaria (`zona_utc`) y algún perfil acepta horario.
  Los países objetivo son la residencia, la mudanza, el permiso legal y el país de sus ciudades cuando se reconoce.
  Si no cumple nada de eso, se descarta como antes.
- En la selección del día (`contrato.entregable` con `panel=True`) basta con evidencia geográfica: `paises`,
  `paises_mundo`, `alcance_mundial` o `zona_utc`. Cada perfil decide después con sus filtros. La confianza baja sin
  franja horaria sigue sin entregarse.
- El modo heredado (sin versión de panel) no cambia.

## Medición

El resumen de cada cargo cuenta de qué fuente vino cada vacante entregada (`fuentes`). Actividad lo muestra como
«N de su búsqueda propia (LinkedIn por perfil) · M de la amplia».
