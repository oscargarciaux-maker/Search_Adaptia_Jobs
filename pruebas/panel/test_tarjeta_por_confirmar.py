"""18 nov: la tarjeta de «Por confirmar» del detalle del cliente muestra cargo, nivel y un extracto corto."""
from panel import revision
from panel.repositorio import RepositorioDemo, hoy


def test_resumen_trae_nivel_y_extracto_corto_sin_html():
    texto = "<p>We are hiring a **Senior** Product Designer.</p> " + "Design flows and prototypes. " * 40
    res = revision.resumen_de({"titulo": "Senior Product Designer", "nivel": "senior", "_descripcion": texto})
    assert res["nivel"] == "senior"
    assert res["extracto"].startswith("We are hiring a Senior Product Designer.")
    assert "<" not in res["extracto"] and "**" not in res["extracto"]
    assert len(res["extracto"]) <= 261 and res["extracto"].endswith("…")


def test_listar_dice_los_cargos_a_los_que_ayuda():
    r = RepositorioDemo()
    pendientes = revision.listar(r, hoy(), pagina=1)["pendientes"]
    assert pendientes and all(isinstance(p["cargos"], list) for p in pendientes)
    assert any(p["cargos"] for p in pendientes)
