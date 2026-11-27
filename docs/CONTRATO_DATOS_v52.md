# Contrato de datos v52 — tres estados al terminar la búsqueda diaria (27 nov 2026)

Decisión de Oscar (27 nov). Sin IA, sin SQL nuevo, sin claves nuevas y sin campos nuevos en `salud.json`. Cambia solo
cómo termina la «Bodega nocturna» (`bodega.yml`, paso «Comprobar meta y sincronización», `buscador/validacion.py`).

## Por qué
De las últimas 40 corridas de la Bodega, 15 terminaron en rojo, casi todas por «La meta de selección diaria está
incompleta»: un resultado del día, no una avería. Con tanto rojo no se veía cuándo algo estaba roto de verdad (por
ejemplo, Supabase cancelando la reconciliación por tiempo, 57014).

## Los tres estados

| Estado | Cuándo | Corrida | Aviso (Healthchecks) |
|---|---|---|---|
| **COMPLETA** | Todo bien | Éxito | Ping de éxito |
| **CORTA** | Meta del día incompleta y/o vacantes de la selección con el enlace sin comprobar (igual no se comparten hasta comprobarlo) | Éxito, con `::warning::` y resumen de qué faltó | Ping de éxito |
| **AVERÍA** | Sincronización con Supabase sin confirmar; catálogo no sincronizado; reconciliación sin confirmar (incluido 57014); selección no registrada; operaciones centrales pendientes; sin catálogo válido; vacantes de hoy que ya no encajan en el perfil | Fallo (exit 1) | `/fail` |

Si hay a la vez una avería y una falta, manda la avería. Los mensajes son los mismos de antes.

## Qué cambia en el código
- `validacion.errores()` devuelve solo averías; `validacion.cortos()` devuelve las faltas (meta incompleta, enlaces sin
  comprobar); `validacion.estado()` da `completa`, `corta` o `averia`; `validacion.problemas()` = las dos listas.
- Si existe `GITHUB_STEP_SUMMARY`, se escribe un resumen: estado, motivo, y por cargo la meta (`entrega.metas_por_rol`),
  las logradas (`unicas`), las que faltan (`faltan`) y, en modo panel, los perfiles bajo el mínimo
  (`perfiles_bajo_minimo`), más los enlaces de la selección. Todo sale de `salud.json`; sin datos de clientes.
- `--catalogo` (`incremental.yml`, `profunda.yml`) no cambia.

## Qué NO cambia
- Qué vacantes se eligen y cuáles se comparten: un enlace sin comprobar sigue sin compartirse.
- Los reintentos: la segunda pasada (8:30) y su respaldo (9:30) deciden con `trabajo/metricas_entrega.json`
  (`arranque.falta_completar`: meta, registro y pendientes de Supabase), no con el color de la corrida. Los respaldos
  de las 7:15/7:50 miran si hoy terminó alguna búsqueda (`pasadas`), y el Reloj y el vigía (`toca_diaria`) tratan igual
  una corrida en verde o en rojo: ya corrió. Un día CORTO sigue pidiendo la segunda pasada.
- El panel: `panel/ejecutor.py` usa `problemas()`, así que un día corto sigue quedando como «parcial» («Con
  faltantes») en `panel_ejecuciones` y «Buscar ahora» sigue ofreciendo completar a quien va corto.
- Las otras partes de la corrida que fallan (búsqueda, publicación) siguen poniendo la corrida en rojo y el aviso en
  `/fail`.

Pruebas: `pruebas/test_estados_bodega.py`.
