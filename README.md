# Search Adaptia Jobs — buscador de vacantes LATAM

Página privada para buscar vacantes de cualquier cargo (y sus cargos parecidos) abiertas en LATAM o remotas para LATAM,
de los últimos 30 días, y pasarlas a un grupo de WhatsApp o a Excel. La búsqueda corre cada noche en GitHub Actions,
sin IA; la página vive en Cloudflare Pages.

- Plan y paso a paso: [`docs/PLAN.md`](docs/PLAN.md)
- Reglas para quien trabaje en el código: [`CLAUDE.md`](CLAUDE.md)

Estado: en construcción (paso 1 de 12: esqueleto).

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q
```
