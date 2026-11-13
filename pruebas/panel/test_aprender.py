"""Contrato v17: aprendizaje de ubicaciones solo con código, reglas que se aplican solas y revisión masiva por CSV."""
import pytest
from fastapi.testclient import TestClient

from buscador import alertas, paises
from panel import aprender, revision
from panel.api import crear_app
from panel.repositorio import RepositorioDemo, hoy


def _d(ubicacion, paises_=None, motivo=None):
    if paises_ is None:
        return {"estado": "descartada", "motivo": motivo or "otro país (operador)", "ubicacion": ubicacion}
    return {"estado": "confirmada", "motivo": motivo or "confirmada por operador", "paises": paises_, "ubicacion": ubicacion}


@pytest.fixture(autouse=True)
def sin_reglas():
    paises.cargar_reglas()
    yield
    paises.cargar_reglas()


def test_frases_sin_genericas_lugares_conocidos_ni_palabras_geograficas_solas():
    assert aprender.frases("Remote Remoto") == set() and aprender.frases("N/A") == set()
    assert "sant cugat" in aprender.frases("Sant Cugat del Vallès, Barcelona")
    assert "barcelona" not in aprender.frases("Sant Cugat del Vallès, Barcelona")  # la tabla ya la conoce
    assert aprender.frases("Villa Nueva") == set() and "sant" not in aprender.frases("Sant Cugat")


def test_dos_evidencias_crean_regla_una_sola_o_contradictorias_no():
    nuevas, _, _ = aprender.aprender([_d("Sant Cugat del Vallès", ["ES"]), _d("Área metropolitana de Sant Cugat", ["ES"])], [])
    assert [(n["texto"], n["resultado"], n["origen"]) for n in nuevas] == [("sant cugat", {"paises": ["ES"]}, "aprendida")]
    assert aprender.aprender([_d("Sant Cugat del Vallès", ["ES"])], [])[0] == []
    assert aprender.aprender([_d("Sant Cugat del Vallès", ["ES"]), _d("Sant Cugat Norte", ["CO"])], [])[0] == []
    # «no sirve» y lo decidido por regla no enseñan nada sobre el lugar
    assert aprender.aprender([_d("Pueblo Raro Uno", motivo="no sirve (operador)"),
                              _d("Pueblo Raro Dos", motivo="no sirve (operador)")], [])[0] == []
    assert aprender.aprender([_d("Lugar Zeta Uno", ["CO"], "decidida por regla"),
                              _d("Lugar Zeta Dos", ["CO"], "decidida por regla")], [])[0] == []


def test_palabra_suelta_necesita_tres_y_otro_pais_tambien_se_aprende():
    dos = [_d("Gotham Office", None), _d("Gotham HQ Annex", None)]
    assert not [n for n in aprender.aprender(dos, [])[0] if n["texto"] == "gotham"]
    tres = dos + [_d("Gotham", None)]
    assert {"texto": "gotham", "resultado": {"extranjero": True}} in [
        {k: n[k] for k in ("texto", "resultado")} for n in aprender.aprender(tres, [])[0]]


def test_contradiccion_desactiva_y_lo_desactivado_no_se_reactiva_solo():
    regla = {"texto": "sant cugat", "resultado": {"paises": ["ES"]}, "origen": "aprendida", "activa": True, "conflictos": 0}
    _, desactivar, conteos = aprender.aprender([_d("Sant Cugat Norte", ["CO"])], [regla])
    assert desactivar == [{"texto": "sant cugat", "activa": False, "conflictos": 1}] and conteos["desactivadas_por_conflicto"] == 1
    apagada = dict(regla, activa=False)
    nuevas, _, _ = aprender.aprender([_d("Sant Cugat del Vallès", ["ES"]), _d("Sant Cugat Sur", ["ES"])], [apagada])
    assert nuevas == []


def test_reglas_solo_resuelven_lo_dudoso_y_nunca_pisan_la_tabla():
    assert paises.elegibles("QA", "Pueblo Ejemplo Uno", "")["confianza"] == "baja"
    paises.cargar_reglas([{"texto": "pueblo ejemplo uno", "resultado": {"paises": ["CO"]}, "origen": "operador"},
                          {"texto": "bogota", "resultado": {"extranjero": True}, "origen": "aprendida"},
                          {"texto": "zeta norte", "resultado": {"paises": ["PE"]}, "origen": "aprendida"},
                          {"texto": "zeta", "resultado": {"paises": ["CL"]}, "origen": "aprendida"},
                          {"texto": "inactiva", "resultado": {"paises": ["CL"]}, "origen": "aprendida", "activa": False}])
    r = paises.elegibles("QA", "Pueblo Ejemplo Uno", "")
    assert r["paises"] == ["CO"] and r["confianza"] == "alta" and r["nota"] == "regla del operador"
    assert paises.elegibles("QA", "Bogotá, Colombia", "")["paises"] == ["CO"]  # la tabla manda
    assert paises.elegibles("QA", "Zeta Norte", "")["confianza"] == "baja"  # dos reglas que se contradicen: no decide
    assert paises.elegibles("QA", "Inactiva", "")["confianza"] == "baja"
    assert paises.USOS["pueblo ejemplo uno"] == 1


def test_preparar_guarda_carga_y_cuenta_usos():
    r = RepositorioDemo()
    r.estado["revisiones"] = [{"vacante_id": f"x{n}", "estado": "confirmada", "motivo": "confirmada por operador",
                                "paises": ["ES"], "ubicacion": u} for n, u in enumerate(["sant cugat del valles",
                                                                                        "area metropolitana de sant cugat"])]
    conteos, reglas = aprender.preparar(r)
    assert conteos["aprendidas_nuevas"] == 1 and conteos["reglas_activas"] == 1
    assert paises.elegibles("QA", "Sant Cugat de Prueba", "")["paises"] == ["ES"]
    assert aprender.guardar_usos(r, reglas) == 1 and r.reglas()[0]["usos"] == 1


def test_csv_ida_y_vuelta_con_punto_y_coma_nombres_y_errores():
    r = RepositorioDemo()
    exportado = revision.exportar_csv(r, hoy())
    assert exportado.startswith("﻿") and exportado.count("\n") == 5  # cabecera + instrucciones + 3 pendientes
    contenido = ("vacante_id;decision;pais;aplicar_a_iguales\n"
                 "rev-demo-0;sí;Colombia;no\nrev-demo-1;otro país;;\nrev-demo-2;tal vez;;\nrev-demo-9;;;\n")
    res = revision.importar_csv(r, contenido)
    assert res["aplicadas"] == 2 and res["omitidas"] == 1 and [e["fila"] for e in res["errores"]] == [4]
    assert r.revisiones(vacante_id="rev-demo-0")[0]["estado"] == "confirmada"
    assert r.revisiones(vacante_id="rev-demo-1")[0]["motivo"] == "otro país (operador)"


def test_api_de_reglas_y_csv():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    h = {"origin": "http://testserver"}
    assert api.get("/api/revisiones.csv").headers["content-type"].startswith("text/csv")
    res = api.post("/api/revisiones/csv", headers=h,
                   json={"contenido": "vacante_id,decision,pais,aplicar_a_iguales\nrev-demo-1,sirve,ES,sí\n"}).json()
    assert res["aplicadas"] == 1
    reglas = api.get("/api/reglas").json()["reglas"]
    assert reglas[0]["texto"] == "granada" and reglas[0]["resultado"] == "España" and reglas[0]["origen"] == "operador"
    assert api.post("/api/reglas/estado", json={"texto": "granada", "activa": False}, headers=h).json()["activa"] is False
    assert api.get("/api/reglas").json()["reglas"][0]["activa"] is False


def test_correo_cuenta_el_aprendizaje():
    _, _, texto = alertas.contenido("exito", "diario", {"fecha": hoy(), "entrega": {"vacantes": 120, "roles": {}}},
                                    {"resumen": {"reglas": {"ubicaciones_resueltas_por_reglas": 7, "aprendidas_nuevas": 2,
                                                            "desactivadas_por_conflicto": 1}}})
    assert "7 ubicaciones resueltas solas" in texto and "2 reglas nuevas" in texto and "1 desactivadas" in texto
