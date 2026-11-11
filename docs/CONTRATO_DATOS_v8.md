# Perfil por país de residencia y modalidades — v8

Revisión del 11 de noviembre de 2026. Cambia la forma del perfil de cliente del contrato v6. No cambia el catálogo ni SQL.

## Campos del perfil

| Campo | Antes (v6) | Ahora (v8) |
|---|---|---|
| País | `paises`: lista de países «desde donde puede trabajar» | `vive_en`: código del país donde vive (uno) |
| Modalidad | `modalidad`: una de remoto, híbrido, presencial, cualquiera | `modalidades`: una o varias de remoto, híbrido, presencial |
| Mudanza | — | `paises_presenciales_extra`: países adicionales donde aceptaría trabajo híbrido o presencial (opcional) |

## Reglas de compatibilidad (`panel/afinidad.py`)

Siempre se exige ubicación confirmada (`confianza_pais` alta o media). `paises` de la vacante sigue siendo el resultado de
`buscador/paises.elegibles`: los países desde los que se puede postular.

- **Remoto aceptado y vacante remota:** compatible si el país donde vive está entre los países de la vacante. Esto incluye
  alcance LATAM o Latinoamérica, LATAM + España, mundial, España remoto abierto a LATAM y listas que nombren su país.
  Una remota limitada a otro país («Remoto, Brasil») o a una región que no incluye el suyo («Remote - South America» para
  quien vive en México) no es compatible.
- **Híbrido o presencial aceptado y vacante de esa modalidad:** compatible si la oficina está en su país o en uno de
  `paises_presenciales_extra`. Nunca se aceptan presenciales de otros países por haber elegido el país de residencia.
- **Vacante sin modalidad declarada:** solo si el perfil acepta las tres modalidades y su país está entre los de la vacante
  (equivale al antiguo «cualquiera»). No se inventa la modalidad.

## Compatibilidad hacia atrás

Las configuraciones, versiones y asignaciones guardadas con v6 se leen sin migración SQL. `panel/modelos.py` convierte al
validar:
- `paises[0]` pasa a `vive_en` y el resto a `paises_presenciales_extra`;
- `modalidad: cualquiera` pasa a las tres modalidades, y cualquier otra a una lista de una.

Al guardar desde el panel se escribe v8. Las versiones ya programadas no se reescriben: se interpretan con esta conversión.

## Búsqueda dirigida (`panel/ejecutor.py`)

Por cada perfil:
- su país, con filtro remoto si acepta remoto y sin filtro si acepta híbrido o presencial;
- si acepta remoto, también las búsquedas remotas regionales (Latin America y Worldwide);
- los países extra, sin filtro, si acepta híbrido o presencial.
