# Search Adaptia Jobs — buscador de vacantes LATAM

Página para buscar vacantes de cualquier cargo de tecnología y áreas creativas —con sus cargos parecidos (exactos,
similares y cercanos) y de todos los niveles— abiertas en un país de LATAM o remotas para LATAM, de los últimos 30 días,
y pasarlas a un grupo de WhatsApp o a Excel. Solo enlaces donde se postula de verdad (LinkedIn, Indeed, portales de las
empresas), nunca agregadores. La búsqueda corre sola cada noche en GitHub Actions, sin IA y sin la cuenta de LinkedIn de
nadie.

- Instalar y usar: [`docs/INSTALACION.md`](docs/INSTALACION.md)
- Pasar el proyecto a otra persona: [`docs/TRASPASO.md`](docs/TRASPASO.md)
- Plan y decisiones: [`docs/PLAN.md`](docs/PLAN.md) · Reglas para quien trabaje en el código: [`CLAUDE.md`](CLAUDE.md)

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q
node --test pruebas/*.test.js
python -m buscador.bodega --salida /tmp/prueba --prueba   # prueba en vivo de unos 5 minutos
```
