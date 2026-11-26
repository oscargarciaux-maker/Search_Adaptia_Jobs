"""Contrato v50: Bumeran y sus portales hermanos (misma API), sin red. La búsqueda trae el aviso completo; la vigencia
se comprueba con la ficha de la API del portal."""
from datetime import datetime, timezone

from buscador import bodega, verificar_enlaces
from buscador.fuentes import jobint

TEXTO = ("<p>Buscamos un/a QA Analyst con experiencia en testing de aplicaciones y aseguramiento de calidad de "
         "software. Diseñarás casos de prueba, ejecutarás pruebas manuales y automatizadas con Selenium y Postman y "
         "reportarás defectos en Jira.</p>") * 2


def _aviso(n, titulo="Analista QA", fecha="20-11-2026", modalidad="Híbrido", empresa="Empresa Uno"):
    return {"id": str(1118600000 + n), "titulo": titulo, "empresa": empresa, "detalle": TEXTO,
            "localizacion": "Capital Federal, Buenos Aires", "fechaPublicacion": fecha, "modalidadTrabajo": modalidad}


class Cliente:
    def __init__(self, respuestas=None):
        self.pedidas, self.respuestas = [], respuestas

    def post_json(self, url, cuerpo, headers=None, timeout=None):
        self.pedidas.append((url, cuerpo["query"], headers["x-site-id"]))
        if self.respuestas is not None:
            return self.respuestas.pop(0) if self.respuestas else None
        return {"total": 2, "content": [_aviso(1), _aviso(2, "Product Manager Textil", modalidad="Remoto")]}


MAPA = [{"id": "cargo:qa", "consultas": ["qa", "qa engineer", "tester"], "consultas_es": ["analista qa", "analista de pruebas"],
         "paises_objetivo": ["AR", "CL", "CO"], "paises_es": ["AR"]}]
PAISES = [("AR", "Argentina"), ("CL", "Chile"), ("CO", "Colombia")]


def _buscar(cliente, estado=None, **opciones):
    jobint.VISTAS.clear()
    return jobint.buscar(cliente, MAPA, PAISES, {} if estado is None else estado, hoy="2026-11-26",
                         dormir=lambda s: None, **{"presupuesto": 50, **opciones})


def test_busca_en_los_portales_de_los_paises_del_cargo_con_varios_nombres_y_en_espanol():
    cliente = Cliente()
    crudas, stats = _buscar(cliente)
    sitios = {sitio for _, _, sitio in cliente.pedidas}
    assert sitios == {"BMAR", "BMCL"}  # Colombia no tiene portal de esta familia
    assert all(url.startswith(("https://www.bumeran.com.ar/api/avisos/searchV2", "https://www.laborum.cl/api/avisos/searchV2"))
               for url, _, _ in cliente.pedidas)
    de_ar = [q for _, q, sitio in cliente.pedidas if sitio == "BMAR"]
    assert {"analista qa", "analista de pruebas"} <= set(de_ar) and {"qa", "qa engineer", "tester"} <= set(de_ar)
    assert not {"analista qa", "analista de pruebas"} & {q for _, q, s in cliente.pedidas if s == "BMCL"}  # nadie ahí acepta español
    assert stats["busquedas"] == len(cliente.pedidas) == 8 and stats["por_pais"] == {"AR": 5, "CL": 3}
    # El mismo aviso con varios nombres se guarda una vez por portal.
    assert len(crudas) == 4 and {c["fuente"] for c in crudas} == {"Bumeran", "Laborum"}


def test_la_vacante_lleva_pais_modalidad_fecha_descripcion_y_la_direccion_del_portal():
    crudas, _ = _buscar(Cliente(), presupuesto=1)
    qa = next(c for c in crudas if c["titulo"] == "Analista QA")
    assert qa["ubicacion"] == "Capital Federal, Buenos Aires, Argentina (Híbrido)" and qa["remoto"] is None
    assert qa["fecha"] == "2026-11-20" and "casos de prueba" in qa["descripcion"] and "<p>" not in qa["descripcion"]
    assert qa["enlace"] == "https://www.bumeran.com.ar/empleos/analista-qa-1118600001.html"
    remota = next(c for c in crudas if c["titulo"] == "Product Manager Textil")
    assert remota["remoto"] is True and remota["ubicacion"].endswith("(Remoto)")
    vacantes, _, _ = bodega.limpiar([], crudas, "2026-11-26", 30, set(), set())
    v = next(x for x in vacantes if x["titulo"] == "Analista QA")
    assert v["paises"] == ["AR"] and v["modalidad"] == "hibrido" and v["idioma"] == "es" and v["fuente"] == "Bumeran"
    # Verse hoy en la búsqueda del portal, con su descripción, comprueba el enlace (como una ficha de LinkedIn, v39).
    cache = {}
    assert verificar_enlaces.incorporar(vacantes, cache, jobint.VISTAS) >= 1
    assert cache[v["enlace"]]["estado"] == "verificada"


def test_no_guarda_avisos_viejos_ni_repite_nombres_ya_buscados_hoy_y_se_detiene_si_el_portal_falla():
    viejo = {"total": 1, "content": [_aviso(3, fecha="01-09-2026")]}
    crudas, _ = _buscar(Cliente([viejo]), presupuesto=1)
    assert crudas == []
    estado = {}
    cliente = Cliente()
    _buscar(cliente, estado)
    from buscador import cobertura
    cobertura.configurar_personas([{"familia": "cargo:qa", "perfil": "p", "lugares": ["AR", "CL"], "peso": 5,
                                    "corto": True, "idiomas": ["es", "en"]}])
    cobertura.configurar_faltantes(True)
    try:
        otra = Cliente()
        _buscar(otra, estado)
    finally:
        cobertura.configurar_faltantes(False)
        cobertura.configurar_personas()
    assert otra.pedidas == []  # la búsqueda para quien falta no repite lo que la noche ya buscó (v47)
    caido = Cliente([None, None, None, None, None])
    _, stats = _buscar(caido)
    assert stats["fallidas"] == 3 and len(caido.pedidas) == 3  # tres fallos seguidos cortan la fuente


class _Respuesta:
    def __init__(self, cuerpo, codigo=200):
        self.cuerpo, self.status_code = cuerpo, codigo

    def json(self):
        if self.cuerpo is None:
            raise ValueError("sin JSON")
        return self.cuerpo


class _Sesion:
    def __init__(self, respuesta):
        self.respuesta, self.pedidas = respuesta, []

    def get(self, url, headers=None, timeout=None, **_):
        self.pedidas.append((url, (headers or {}).get("x-site-id")))
        return self.respuesta

    def close(self):
        pass


URL = "https://www.laborum.cl/empleos/analista-qa-1118600001.html"


def _comprobar(respuesta, titulo="Analista QA", url=URL):
    sesion = _Sesion(respuesta)
    r = verificar_enlaces.comprobar(url, titulo, sesion=sesion, ahora=datetime(2026, 11, 26, tzinfo=timezone.utc))
    return r, sesion


def test_el_enlace_se_comprueba_con_la_ficha_de_la_api_del_portal():
    assert jobint.aviso_de(URL) == ("www.laborum.cl", "BMCL", "1118600001")
    assert jobint.aviso_de("https://www.bumeran.com.ar/empleos-busqueda-qa.html") is None
    assert jobint.aviso_de("https://www.laborum.cl.evil.com/empleos/x-1118600001.html") is None
    r, sesion = _comprobar(_Respuesta({"aviso": {"titulo": "Analista QA", "estado": "activo"}}))
    assert r["estado"] == "verificada" and r["http"] == 200
    assert sesion.pedidas == [("https://www.laborum.cl/api/candidates/fichaAvisoNormalizada/1118600001", "BMCL")]
    assert _comprobar(_Respuesta({"aviso": {"titulo": "Analista QA", "estado": "finalizado"}}))[0]["motivo"] == "vacante cerrada"
    assert _comprobar(_Respuesta({}, 404))[0] == {**_comprobar(_Respuesta({}, 404))[0], "estado": "rechazada", "motivo": "enlace roto"}
    # Un bloqueo, una respuesta rara u otro aviso con ese número nunca aprueban ni cierran.
    for respuesta in (_Respuesta({}, 403), _Respuesta(None), _Respuesta({"aviso": {}}),
                      _Respuesta({"aviso": {"titulo": "Vendedor de mostrador", "estado": "activo"}})):
        assert _comprobar(respuesta)[0]["estado"] == "pendiente"


def test_la_fuente_esta_registrada_donde_hace_falta():
    from buscador import enlaces
    from panel import ejecutor
    assert bodega.config()["presupuestos"]["jobint_busquedas"] > 0
    for pais, (dominio, _, nombre) in jobint.SITIOS.items():
        assert nombre in ejecutor.fuentes_en(pais)
        assert enlaces.sirve(jobint.enlace(dominio, "Analista QA", "1118600001"))  # se postula en el mismo portal
    assert "Bumeran" not in ejecutor.fuentes_en("CO")
