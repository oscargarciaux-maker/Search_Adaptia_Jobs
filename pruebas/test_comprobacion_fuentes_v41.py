"""Contrato v41 (17 nov): 487 vacantes de Indeed con solo 17 comprobadas (Indeed responde 401 a toda comprobación) y
Computrabajo y Get on Board casi sin turno (las de LinkedIn ocupaban los hilos esperando su pausa)."""
import time
from datetime import datetime, timezone

from buscador import vacante, verificar_enlaces as ve
from buscador.fuentes import indeed

AHORA = datetime(2026, 11, 17, 22, tzinfo=timezone.utc)


def _v(enlace, titulo="Product Designer", fuente="LinkedIn", directo=""):
    return vacante.crear(titulo, "Acme " + enlace[-3:], enlace, fuente, ubicacion="Bogotá",
                         descripcion="Design " * 60, enlace_directo=directo, hoy="2026-11-17")


def test_indeed_visto_hoy_en_su_busqueda_cuenta_como_comprobado():
    indeed.VISTAS.clear()
    url = "https://co.indeed.com/viewjob?jk=abc123"
    indeed._anotar_vista(url)
    v = _v(url, fuente="Indeed")
    cache = {}
    assert ve.incorporar([v], cache, indeed.VISTAS) == 1
    r = ve.anotar(v, cache, datetime.now(timezone.utc))
    assert r["estado"] == "verificada" and cache[url]["motivo"] == "vista hoy en la búsqueda de Indeed"
    # Lo que no apareció hoy sigue sin comprobar.
    otra = _v("https://co.indeed.com/viewjob?jk=zzz999", fuente="Indeed")
    assert ve.anotar(otra, cache, datetime.now(timezone.utc))["estado"] == "pendiente"
    indeed.VISTAS.clear()


def test_las_otras_fuentes_avanzan_aunque_linkedin_vaya_lento(monkeypatch):
    monkeypatch.setattr(ve, "PAUSA_LINKEDIN", 0)
    lentas = [_v(f"https://www.linkedin.com/jobs/view/{n}") for n in range(20)]
    rapidas = [_v(f"https://co.computrabajo.com/ofertas-de-trabajo/oferta-{n}", fuente="Computrabajo")
               for n in range(20)]
    hechas = []

    def comprobar(u, titulo, **op):
        if "linkedin" in u:
            time.sleep(0.2)
        hechas.append(u)
        return {"url": u, "estado": "verificada", "motivo": "ok", "destino": u, "http": 200,
                "comprobada_en": AHORA.isoformat().replace("+00:00", "Z"), "saltos": 0, "ruta": [u]}
    ve.auditar(lentas + rapidas, {}, comprobar_url=comprobar, ahora=AHORA, segundos=1.5)
    assert sum("computrabajo" in u for u in hechas) == 20  # antes esperaban detrás de LinkedIn
    assert sum("linkedin" in u for u in hechas) < 20


def test_linkedin_no_se_lleva_todo_el_cupo(monkeypatch):
    monkeypatch.setattr(ve, "PAUSA_LINKEDIN", 1.0)
    vs = [_v(f"https://www.linkedin.com/jobs/view/{n}") for n in range(30)] + \
         [_v(f"https://www.getonbrd.com/jobs/x-{n}", fuente="Get on Board") for n in range(10)]
    pedidas = []

    def comprobar(u, titulo, **op):
        pedidas.append(u)
        return None
    monkeypatch.setattr(ve.time, "sleep", lambda s: None)
    escogidas = ve.auditar(vs, {}, comprobar_url=comprobar, ahora=AHORA, segundos=5, maximo=40)
    assert escogidas == 6 + 10  # 5 s / 1 s de pausa (+1) para LinkedIn, y todas las de Get on Board
