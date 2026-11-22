"""Contrato v48: «(ID N)» en cada vacante y el mensaje de WhatsApp de un día anterior."""
from datetime import datetime, timezone

from panel import borradores, servicio
from panel.repositorio import RepositorioDemo


def _vac(n, estado="entregada", empresa=None, numero=None):
    return {"id": f"{n:016x}", "titulo": f"Product Designer {n}", "empresa": empresa or f"Empresa {n}",
            "modalidad": "remoto", "enlace": f"https://jobs.lever.co/acme/{n}", "estado": estado,
            "cargo_nombre": "Product Designer", "tipo": "", "numero": numero or n}


def test_la_linea_lleva_el_numero_entre_parentesis():
    assert borradores._linea(1, _vac(7, numero=1234)) == (
        "1. Product Designer 7 · Empresa 7 (Remoto) (ID 1234)\nhttps://jobs.lever.co/acme/7")
    sin = dict(_vac(7), numero=None)
    assert "(ID" not in borradores._linea(1, sin)


def test_la_demostracion_numera_y_no_cambia(tmp_path):
    repo = RepositorioDemo(tmp_path / "demo.json")
    primero = repo.numeros(["b", "a"])
    assert primero == {"a": 1, "b": 2}
    assert repo.numeros(["c", "a"]) == {"c": 3, "a": 1}


class Repo:
    """Catálogo falso: datos por id; registra lo que se guarda."""
    def __init__(self):
        self.guardadas = {}

    def vacante(self, vid):
        n = int(vid, 16)
        return {"id": vid, "status": "active",
                "datos": {"titulo": f"Product Designer {n}", "enlace": f"https://jobs.lever.co/acme/{n}"}}

    def actualizar_catalogo_datos(self, vid, datos):
        self.guardadas[vid] = datos

    def numeros(self, ids):
        return {}

    def contactos(self):
        return [{"cliente_id": "c1", "nombre_saludo": "Ana"}]


def _comprobar(rotas, pedidas=None):
    def comprobar(url, titulo, **op):
        if pedidas is not None:
            pedidas.append(url)
        estado = "rechazada" if url.rsplit("/", 1)[-1] in rotas else "verificada"
        return {"url": url, "destino": url, "estado": estado, "motivo": "prueba", "http": 200,
                "comprobada_en": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "saltos": 0, "ruta": [url]}
    return comprobar


def test_un_dia_anterior_comprueba_al_momento_y_quita_las_cerradas():
    resultados = {"ejecucion": {"fecha": "2026-11-01"},
                  "vacantes": [_vac(1), _vac(2), _vac(3, "lista"), _vac(4, "retirada"), _vac(5, "por_confirmar")]}
    repo, pedidas = Repo(), []
    r = servicio.whatsapp(repo, "c1", "2026-11-01", resultados=resultados, cuantas=10,
                          comprobar=_comprobar({"2"}, pedidas))
    assert r["vacantes"] == 2 and "Se quitaron 1 que ya cerraron" in r["nota"]
    assert "(ID 1)" in r["texto"] and "(ID 3)" in r["texto"] and "Product Designer 2" not in r["texto"]
    assert "Product Designer 4" not in r["texto"] and "Product Designer 5" not in r["texto"]
    assert "Hoy encontré" not in r["texto"] and "siguen abiertas" in r["texto"]
    # La «lista» (comprobada en 24 h) no se vuelve a comprobar; solo las entregadas.
    assert sorted(pedidas) == ["https://jobs.lever.co/acme/1", "https://jobs.lever.co/acme/2"]
    assert set(repo.guardadas) == {f"{1:016x}"}  # la comprobación queda guardada para la próxima vez
    assert repo.guardadas[f"{1:016x}"]["verificacion"]["estado"] == "verificada"
    assert "verificacion" not in resultados["vacantes"][0]  # no toca la copia en memoria


def test_sin_tiempo_no_entra_lo_que_no_se_comprobo():
    resultados = {"ejecucion": {"fecha": "2026-11-01"}, "vacantes": [_vac(1), _vac(2)]}
    r = servicio.whatsapp(Repo(), "c1", "2026-11-01", resultados=resultados, comprobar=_comprobar(set()), segundos=0)
    assert r["vacantes"] == 0 and "sigue con el enlace" in r["nota"]


def test_hoy_no_cambia():
    from panel.repositorio import hoy
    resultados = {"ejecucion": {"fecha": hoy()}, "vacantes": [_vac(1, "lista"), _vac(2, "entregada")]}
    llamadas = []
    r = servicio.whatsapp(Repo(), "c1", None, resultados=resultados,
                          comprobar=lambda *a, **k: llamadas.append(a))
    assert r["vacantes"] == 1 and not r["nota"] and not llamadas


def test_resultados_dicen_si_es_dia_anterior_y_cuantas_se_pueden_copiar(tmp_path):
    repo = RepositorioDemo(tmp_path / "demo.json")
    r = servicio.resultados(repo, None, None)
    assert r["dia_anterior"] is False and r["para_copiar"] == r["listas"]
    assert all(v.get("numero") for v in r["vacantes"])
