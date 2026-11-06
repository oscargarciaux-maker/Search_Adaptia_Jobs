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
