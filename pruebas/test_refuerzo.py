"""El refuerzo atiende déficits reales sin repetir ofertas ni eliminar límites de negocio."""
from buscador import entrega, familias, refuerzo, vacante

HOY = "2026-11-04"
TEXTO = "We are looking for a UX Designer to improve our product through research and prototyping. " * 5


def oferta(n, empresa=None, texto=TEXTO):
    return vacante.crear("UX Designer", empresa or f"Empresa {n}", f"https://jobs.lever.co/a/{n}", "Lever",
                         ubicacion="Remote - Worldwide", descripcion=texto + f" Requisition {n}", hoy=HOY)


def test_refuerzo_solo_roles_insuficientes_y_se_detiene_al_completar():
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=2)
    llamadas, memoria = [], {}
    def buscar(mapa, ronda):
        llamadas.append(({f["id"] for f in mapa}, ronda))
        return [oferta(2)], {}
    vs, rondas = refuerzo.completar([oferta(1)], memoria, HOY, cfg, {"rondas": 2}, familias.mapa(),
                                   buscar, lambda a, b: vacante.juntar(a + b))
    assert len(vs) == 2 and len(rondas) == 1 and memoria == {}
    assert llamadas == [({"diseno-producto-ux", "ux-research"}, 1)]


def test_no_buscar_si_cuota_completa():
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=1)
    def prohibido(*args):
        raise AssertionError("No hace falta buscar")
    _, rondas = refuerzo.completar([oferta(1)], {}, HOY, cfg, {"rondas": 2}, familias.mapa(), prohibido, prohibido)
    assert rondas == []


def test_repetir_resultados_no_cumple_meta_ni_relaja_tope_empresa():
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=3, max_por_empresa=2)
    iniciales = [oferta(1, "Acme"), oferta(2, "Acme"), oferta(3, "Acme")]
    _, evaluacion = entrega.elegir(iniciales, {}, HOY, cfg)
    assert evaluacion["roles"]["ux-ui-designer"]["capacidad_con_tope_empresa"] == 2
    vs, rondas = refuerzo.completar(iniciales, {}, HOY, cfg, {"rondas": 2}, familias.mapa(),
                                   lambda m, n: ([oferta(1, "Acme")], {}), lambda a, b: vacante.juntar(a + b))
    assert len(rondas) == 2 and len(vs) == 3
    assert entrega.elegir(vs, {}, HOY, cfg)[1]["roles"]["ux-ui-designer"]["faltan"] == 1


def test_diagnostico_distingue_descripcion_duplicados_y_tope_empresa():
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=4, max_por_empresa=2)
    vs = [oferta(1, "Acme"), oferta(2, "Acme"), oferta(3, "Acme"), oferta(4, texto="corto"), oferta(5)]
    memoria = {vs[-1]["id"]: HOY}
    _, r = entrega.elegir(vs, memoria, HOY, cfg)
    r = r["roles"]["ux-ui-designer"]
    assert r["candidatas"] == 3 and r["entregadas"] == 2 and r["limitadas_por_empresa"] == 1
    assert r["descartadas"] == {"sin descripción completa": 1, "ya entregada": 1}


def test_historial_mide_dias_observados_y_reserva_sin_inventar_suministro():
    cfg = dict(entrega.config(), roles=[entrega.config()["roles"][1]], por_rol=1)
    # Construir un resumen real con la misma estructura que se guarda, sin enviar a servicios externos.
    elegidas, r = entrega.elegir([oferta(1), oferta(2)], {}, HOY, cfg)
    r["meta_cumplida"] = True
    historial = {"2025-01-01": {"fecha": "2025-01-01"}}
    dias = entrega.registrar_medicion(historial, r, HOY)
    assert len(dias) == 1 and list(historial) == [HOY]
    assert dias[0]["roles"]["ux-ui-designer"]["reserva_sin_entregar"] == 1
    assert "description_full" not in str(dias)


def test_refuerzo_fuentes_acotadas_sin_apify(monkeypatch):
    llamadas = []
    def linkedin(*args, **kwargs):
        llamadas.append(("linkedin", kwargs["desfase_terminos"], kwargs["limite_segundos"]))
        raise RuntimeError("bloqueada")
    def indeed(*args, **kwargs):
        llamadas.append(("indeed", kwargs["desfase_terminos"], kwargs["limite_segundos"]))
        return [{"titulo": "UX Designer"}], {"avisos": 1}
    monkeypatch.setattr(refuerzo.linkedin_publico, "buscar", linkedin)
    monkeypatch.setattr(refuerzo.indeed, "buscar", indeed)
    monkeypatch.setattr(refuerzo.getonbrd, "buscar", lambda *a: ([], {"avisos": 0}))
    crudas, salud = refuerzo.buscar([familias.mapa()[0]], [("ES", "España")], {}, HOY, 2, {"minutos_por_fuente": 1})
    assert len(crudas) == 1 and "error" in salud["LinkedIn"]
    assert set(llamadas) == {("linkedin", 8, 60), ("indeed", 8, 60)}
