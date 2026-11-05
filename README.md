# Search Adaptia Jobs — scraper de vacantes LATAM y España

Cada noche entrega **hasta 20 vacantes nuevas por rol** (Product designer, UX/UI designer, Product Owner, Product manager, AI
Engineer, QA), variadas y nunca repetidas, con las columnas del contrato de datos (`docs/CONTRATO_DATOS_v1.md`), en
Supabase como base de datos obligatoria. Además, una página para buscar vacantes de cualquier cargo de tecnología y áreas creativas —con sus cargos parecidos (exactos,
similares y cercanos) y de todos los niveles— abiertas en un país de LATAM o España, o remotas para ellos, de los últimos 30 días,
y pasarlas a un grupo de WhatsApp o a Excel. Solo enlaces donde se postula de verdad (LinkedIn, Indeed, portales de las
empresas), nunca agregadores. La búsqueda corre sola cada noche en GitHub Actions, sin IA y sin la cuenta de LinkedIn de
nadie.

- Instalar y usar: [`docs/INSTALACION.md`](docs/INSTALACION.md)
- Revisión de alternativas y mejoras: [`docs/REVISION_PRODUCTO.md`](docs/REVISION_PRODUCTO.md)
- Activar captura horaria y catálogo Supabase: [`docs/ACTIVAR_CAPTURA_HORARIA.md`](docs/ACTIVAR_CAPTURA_HORARIA.md)
- Integridad de enlaces y resultados de auditoría: [`docs/CONTROL_CALIDAD_ENLACES.md`](docs/CONTROL_CALIDAD_ENLACES.md)
- Pasar el proyecto a otra persona: [`docs/TRASPASO.md`](docs/TRASPASO.md)
- Plan y decisiones: [`docs/PLAN.md`](docs/PLAN.md) · Reglas para quien trabaje en el código: [`CLAUDE.md`](CLAUDE.md)

## Cobertura y conservación

Prioriza remotas para varios países, con cobertura de LATAM, España y remotas mundiales. Los títulos exactos,
similares y cercanos rotan en las búsquedas; no se promete agotar todas las combinaciones cada noche.
La limpieza de 30 días solo afecta al buscador activo; no borra ofertas de Supabase. La generación automática de Excel
de la entrega anterior está desactivada. Apify busca fichas formales de LinkedIn con un tope de USD 5/mes; las publicaciones solo aportan una oferta si se verifica
su ficha original. La búsqueda pagada del feed está desactivada para reservar el crédito a fichas formales.
La meta es 20 por cada uno de seis roles (120 al día). Si un rol queda corto, hay búsquedas adicionales gratuitas
acotadas y un reporte de los motivos. La continuidad se mide entre días distintos, conservando la memoria de entregas.
Decisiones, límites y seguimiento futuro: [`docs/COBERTURA_HISTORICO.md`](docs/COBERTURA_HISTORICO.md).

El catálogo v2 permite actualizar durante el día sin crear otra entrega diaria. Conserva publicación, detección y
última observación por separado y archiva sin borrar historial en Supabase. Requiere la migración aditiva y la variable
de activación; la captura horaria queda desactivada hasta entonces. Repetir una entrega completa solo reintenta el lote.
WhatsApp sigue pendiente de validar continuidad y definir destinatarios/confirmaciones; no hay envíos automáticos.

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q
node --test pruebas/*.test.js
python -m buscador.bodega --salida /tmp/prueba --prueba   # prueba en vivo de unos 5 minutos
```
