"""7.G (decisión de Oscar, 27 nov): «vacantes de la selección de hoy que ya no encajan» pasa de AVERÍA a CORTA. La
Bodega del 27 nov terminó en rojo solo por eso (2 vacantes, 2 cargos): era un cambio de datos, no algo roto."""
from buscador import validacion
from buscador.bodega import motivo_no_encaja
from pruebas.test_estados_bodega import _correr, _reporte


def _no_encaja(motivo=""):
    v = {"afinidad_vigente": False, "catalog_status": "active", "verificacion": {"estado": "verificada"}}
    return dict(v, motivo_no_encaja=motivo) if motivo else v


def _con(*vacantes, nombre="QA"):
    return _reporte(seleccion_actual={"roles": {"qa": {"nombre": nombre, "vacantes": list(vacantes)}}})


def test_una_que_ya_no_encaja_es_corta_en_verde_con_aviso(tmp_path, monkeypatch, capsys):
    r = _con(_no_encaja("configuracion"), {"afinidad_vigente": True, "catalog_status": "active"})
    assert not validacion.errores(r) and validacion.estado(r) == validacion.CORTA
    codigo, resumen = _correr(tmp_path, monkeypatch, r)
    salida = capsys.readouterr().out
    assert codigo == 0 and "::error::" not in salida
    assert ("::warning::1 vacantes de la selección de hoy ya no encajan en ningún perfil del cargo; no se comparten. "
            "(1 cargo)") in salida
    assert "Resultado del día: CORTA" in resumen and "ya no encajan no se comparten" in resumen
    # Público (registro y resumen de Actions): ni el nombre del cargo ni el motivo por cargo.
    assert "QA" not in salida and "QA" not in resumen and "se editó" not in salida + resumen


def test_el_detalle_privado_dice_el_motivo_agregado():
    r = _con(_no_encaja("configuracion"), _no_encaja("configuracion"), _no_encaja("vacante"), _no_encaja())
    assert validacion.cortos(r)[-1] == ("QA: 4 vacantes de la selección de hoy ya no encajan en ningún perfil del "
                                        "cargo; no se comparten. (2 se editó el cargo o el perfil, 1 cambió la vacante)")
    assert validacion.cortos(r, detalle=False)[-1].endswith("no se comparten. (1 cargo)")


def test_una_averia_real_sigue_siendo_averia_aunque_tambien_haya_no_encajan(tmp_path, monkeypatch):
    r = _con(_no_encaja())
    r["entrega"]["supabase"]["pendientes"] = 2
    assert validacion.estado(r) == validacion.AVERIA
    assert _correr(tmp_path, monkeypatch, r)[0] == 1


def test_lo_que_cerro_despues_sigue_siendo_solo_un_aviso():
    r = _con({"afinidad_vigente": False, "catalog_status": "closed"})
    assert validacion.estado(r) == validacion.COMPLETA and validacion.avisos(r)


def test_el_motivo_distingue_vacante_cambiada_de_cargo_o_perfil_editado():
    qa = {"id": "qa", "nombre": "QA", "familias": ["qa"]}
    diseno = {"id": "pd", "nombre": "Product Designer", "familias": ["diseno"]}
    original = {"id": "v1", "titulo": "QA Engineer", "familias": [{"familia": "qa", "coincidencia": "exacto"}]}
    # La copia de la mañana todavía encaja con los cargos de ahora: lo que cambió es la vacante.
    assert motivo_no_encaja(original, qa, [qa, diseno]) == "vacante"
    # Tampoco encaja la copia de la mañana: se editó el cargo (aquí, ya no tiene la familia).
    assert motivo_no_encaja(original, dict(qa, familias=["diseno"]), [dict(qa, familias=["diseno"])]) == "configuracion"
    assert motivo_no_encaja({"id": "v1"}, qa, [qa]) == ""  # sin datos de la copia no se adivina
