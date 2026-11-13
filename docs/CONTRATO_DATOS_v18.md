# Contrato de datos v18 — política remota de Get on Board y regiones combinadas

Vigente desde el 13 nov 2026. Amplía v17 y versiones anteriores, sin columnas nuevas en `ofertas` ni SQL nuevo. Cambia
la forma de leer la ubicación de una fuente y de una frase con varias regiones.

## Por qué

- De las 296 dudosas del inventario del 13 nov, **125 eran de Get on Board con ubicación «Remote Remoto»**. La API pone
  `countries: ["Remote"]` en todos sus avisos remotos, así que esa ubicación no dice nada. Sin embargo, cada aviso trae
  su política remota.
- La ficha pública la escribe así, comprobado en inglés y en español:

| `remote_modality` | Ficha pública | Cómo se lee |
|---|---|---|
| `fully_remote` | «Fully remote — Candidates can reside anywhere in the world» / «Totalmente remoto — 100% remoto desde cualquier país» | `Remote - Worldwide`: cualquier país, LATAM y España incluidos |
| `remote_local` | «Locally remote only — candidates must reside in United States» / «…deben residir en Sudamérica, Centroamérica o México para postular» | `Remote - <lugares>` con el país o países de `location_tenants` (API) o de la ficha |
| `hybrid`, `no_remote`, `temporarily_remote` | Ciudad y país | Como antes, con los países de `countries` |

- `remote_local` sin país sigue «por confirmar». En caso de duda, no entra.
- `remote_zone`, si el aviso la trae, acota la ubicación (`Remote - <zona>`).

## Reglas

1. **Fuente (`buscador/fuentes/getonbrd.py`).**
   - La búsqueda pide `expand=["company","location_tenants"]`.
   - `ubicacion` se arma con la tabla anterior. El marcador «Remote» de `countries` ya no se copia como si fuera un país.
2. **Vacantes ya guardadas (`buscador/confirmar_ubicacion.py`).**
   - La ficha de Get on Board no trae `JobPosting`, así que se lee su política remota escrita.
   - El resultado entra como una observación más, con la fuente «ficha estructurada».
   - Si una vacante tiene enlace de Get on Board, se lee esa ficha aunque el principal sea LinkedIn.
   - Las de Get on Board van primero en la cola.
   - Presupuesto: 150 fichas y 300 s por noche (`datos/config.yaml`).
   - Además, cuando la búsqueda nocturna vuelve a ver un aviso, su observación nueva reemplaza a la vieja del mismo
     enlace (`vacante.unir`).
3. **Varias regiones (`buscador/paises.py`).**
   - «Sudamérica, Centroamérica o México» suma todas las subregiones nombradas y los países sueltos. Antes se quedaba
     con la primera.
   - Lo mismo vale dentro de una frase de residencia («must reside in Central America, Chile or Mexico»).
   - Brasil sigue sin cobertura (v12).
4. **Bandeja «Por confirmar».** Una pendiente cuya vacante el sistema ya resolvió deja de pedir revisión: queda
   `vencida` con el motivo «resuelta sola». Pasa cuando en el catálogo ya no tiene la razón «elegibilidad regional por
   confirmar».

## Medición (13 nov, solo conteos)

- **Muestra de 30 de las 125 fichas reales de Get on Board:**
  - 12 «desde cualquier país»;
  - 17 solo para países o regiones concretas, casi todas de LATAM («Chile, Colombia o México», «Sudamérica, Centroamérica
    o México»…);
  - 1 sin dato.
- **Inventario completo (8.306 vacantes) con la nueva lectura de regiones:** ninguna vacante cambió de país.

## Lo que no cambia

- Sin IA, sin Apify y sin formularios.
- `robots.txt` de Get on Board: `Allow: /` y `search=yes`.
- Una frase de residencia de la descripción sigue pudiendo restringir más una ubicación `Remote - Worldwide`.
