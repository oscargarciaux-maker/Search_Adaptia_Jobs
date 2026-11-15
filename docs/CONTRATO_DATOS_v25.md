# Contrato de datos v25 — que no se pierdan vacantes por el título (huella de funciones)

Vigente desde el 15 nov 2026 (paso 6b de los ajustes de la reunión con el cliente). Amplía v24. Sin columnas nuevas en
`ofertas` ni SQL nuevo. **Sin IA**: reglas de texto y conteos.

## Cargo

- **`Cargo.funciones`** (hasta 40 términos): las tareas y herramientas típicas del cargo (por ejemplo, para Product
  Owner: backlog, historias de usuario, sprint, priorización, stakeholders).
  - Se proponen solas con «Proponer funciones»: el panel compara las descripciones del catálogo cuyo título sí es del
    cargo con las de otros títulos y sugiere los términos que más distinguen al cargo.
  - El operador las revisa, quita o añade.

## Clasificación (solo cargos del panel)

- **Título genérico + descripción**: si el título es genérico (profesional, especialista, consultor/a, analista,
  coordinador/a, asociado, specialist, consultant, professional, associate, lead) y la descripción nombra un término
  exacto del cargo dos o más veces, la vacante cuenta como **similar**, igual que si el título encajara.
- **Coincide por funciones**: si el título no encaja con ningún cargo pero la descripción contiene al menos
  max(4, 30 %) de las funciones distintas de un cargo, la vacante recibe el grado **`funciones`** para ese cargo.
  - Nunca se entrega sola ni entra por ampliación.
  - Va a «Por confirmar» con la etiqueta «Coincide por funciones», solo para los perfiles de ese cargo que cumplen
    todos sus demás filtros.

## Bandeja y aprendizaje

- **«Sí, sirve»**: no exige elegir país (la ubicación ya se comprobó con los filtros). Asigna la vacante y **aprende el
  título** para ese cargo en `panel_ajustes`, clave `titulos_aprendidos` (`{cargo_id: [títulos]}`, hasta 200 por
  cargo). Desde la búsqueda siguiente, ese título entra como similar sin pasar por la bandeja.
- **«No sirve»**: cierra la revisión sin archivar la vacante en el catálogo, porque puede servir a otro cargo.

## Límite conocido

Solo se puede leer la descripción que la fuente trae al capturar (portales de empresas, Computrabajo, Get on Board,
tableros). Las tarjetas de LinkedIn llegan sin descripción y solo la reciben si su título ya encajó.
