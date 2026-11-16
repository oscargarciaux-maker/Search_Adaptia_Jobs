"""Retirar la interfaz no puede perder el inventario ni los pendientes de recuperación."""
from collections import Counter
import json

from buscador import publicar


def test_reanudar_salida_antigua_retira_web_y_preserva_estado(tmp_path):
    for nombre in publicar.INTERFAZ_RETIRADA:
        ruta = tmp_path / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(b"interfaz anterior")
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    archivos = {"bodega.json.gz": b"inventario", "pendientes_supabase.json": b"pendientes",
                "apify_presupuesto.json": b"reservas", "lote_entrega.json": b"seleccion"}
    for nombre, contenido in archivos.items():
        (trabajo / nombre).write_bytes(contenido)
    publicar.publicar(tmp_path, [], {"catalogo": {"pendientes": 0}}, Counter())
    publicar.publicar(tmp_path, [], {"catalogo": {"pendientes": 0}}, Counter())
    assert not any((tmp_path / nombre).exists() for nombre in publicar.INTERFAZ_RETIRADA)
    assert json.loads((tmp_path / "datos/salud.json").read_text())["catalogo"]["pendientes"] == 0
    assert all((trabajo / nombre).read_bytes() == contenido for nombre, contenido in archivos.items())


def test_la_captura_horaria_no_pisa_el_informe_de_la_busqueda_completa(tmp_path):
    import json
    publicar.publicar(tmp_path, [], {"modo": "diario", "nuevas_hoy": 50}, Counter())
    publicar.publicar(tmp_path, [], {"modo": "incremental", "nuevas_hoy": 3}, Counter())
    assert json.loads((tmp_path / "datos" / "salud.json").read_text())["nuevas_hoy"] == 3
    assert json.loads((tmp_path / "datos" / "salud_bodega.json").read_text())["nuevas_hoy"] == 50


def test_publicar_retira_la_carpeta_vieja_de_cloudflare_sin_tocar_trabajo(tmp_path):
    """PR 1.5: el resto `functions/api/.gitkeep` de la web retirada sale de la rama publicado; trabajo/ se conserva."""
    from collections import Counter
    from buscador import publicar
    (tmp_path / "functions" / "api").mkdir(parents=True)
    (tmp_path / "functions" / "api" / ".gitkeep").write_text("")
    (tmp_path / "trabajo").mkdir()
    (tmp_path / "trabajo" / "estado.json").write_text("{}")
    publicar.publicar(tmp_path, [], {"modo": "diario"}, Counter())
    assert not (tmp_path / "functions").exists() and (tmp_path / "trabajo" / "estado.json").exists()
