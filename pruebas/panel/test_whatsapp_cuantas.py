"""Contrato v43 (regla 7, decisión de Oscar del 18 nov): al copiar a WhatsApp desde «Vacantes» el operador elige
cuántas; se mantienen 2 por empresa y, con más de 10, el mensaje se entrega en partes de 10 sin cortar ninguna."""
import re

from fastapi.testclient import TestClient

from panel import servicio
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, configuracion_demo


def _r(n, empresas):
    return {"ejecucion": {"fecha": "2026-11-18"}, "clientes": [], "vacantes": [
        {"id": f"v{i}", "estado": "lista", "titulo": f"Diseñador {i}", "empresa": f"Empresa {i % empresas}",
         "modalidad": "remoto", "enlace": f"https://jobs.lever.co/e/{i}", "cargo_nombre": "Product Designer"}
        for i in range(n)]}


def test_elige_cuantas_con_dos_por_empresa_y_avisa_las_demas():
    msg = servicio.whatsapp(None, "c1", resultados=_r(30, 15), contactos=[], cuantas=7)
    assert msg["vacantes"] == 7 and msg["sobran"] == 23 and "Tengo 23 vacantes más" in msg["texto"]
    msg = servicio.whatsapp(None, "c1", resultados=_r(30, 3), contactos=[], cuantas=30)
    assert msg["vacantes"] == 6  # 3 empresas × 2


def test_mas_de_diez_se_parte_de_diez_en_diez_sin_cortar_ninguna():
    msg = servicio.whatsapp(None, "c1", resultados=_r(40, 40), contactos=[], cuantas=25)
    assert msg["vacantes"] == 25 and len(msg["partes"]) == 3
    assert msg["partes"][0].startswith("¡Hola!") and "1. Diseñador" in msg["partes"][0]
    assert "11. " in msg["partes"][1] and "21. " in msg["partes"][2]
    assert sum(p.count("https://jobs.lever.co/") for p in msg["partes"]) == 25
    assert "\n\n".join(msg["partes"]) == msg["texto"]


def test_por_defecto_diez_y_una_sola_parte():
    msg = servicio.whatsapp(None, "c1", resultados=_r(40, 40), contactos=[])
    assert msg["vacantes"] == 10 and len(msg["partes"]) == 1


def test_api_valida_cuantas():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    cliente = configuracion_demo()["clientes"][0]["id"]
    assert api.get(f"/api/whatsapp/{cliente}?cuantas=0").status_code == 422
    assert api.get(f"/api/whatsapp/{cliente}?cuantas=3").json()["vacantes"] == 3


def test_con_dos_cargos_el_titulo_no_queda_suelto_y_se_repite():
    """Revisión Thermos del 18 nov: con 10 del cargo A y 4 del B, la parte 1 terminaba en «*B*» suelto y la parte 2
    empezaba sin decir de qué cargo eran sus vacantes."""
    r = _r(14, 14)
    for v in r["vacantes"][10:]:
        v["cargo_nombre"] = "QA"
    msg = servicio.whatsapp(None, "c1", resultados=r, contactos=[], cuantas=14)
    assert len(msg["partes"]) == 2
    assert not msg["partes"][0].rstrip().endswith("*QA*")
    assert msg["partes"][1].startswith("*QA*\n\n11. ")
    for parte in msg["partes"][1:]:
        primer = parte.split("\n\n")[0]
        assert primer.startswith("*") or not re.match(r"^\d+\. ", primer)
