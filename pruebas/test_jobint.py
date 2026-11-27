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
    # Verse en la búsqueda no comprueba el enlace: se comprueba después, con la ficha del portal.
    assert verificar_enlaces.anotar(v, {})["estado"] == "pendiente"
    # «Confidencial» no es el nombre de una empresa.
    confidencial = Cliente([{"content": [_aviso(7, empresa="Confidencial")]}])
    assert _buscar(confidencial, presupuesto=1)[0][0]["empresa"] == ""


def test_una_localidad_con_nombre_de_otro_pais_no_abre_ese_pais():
    from buscador import paises
    for localizacion, esperado in (("Palermo, Capital Federal", "Capital Federal, Argentina"),
                                   ("Florida, Buenos Aires", "Buenos Aires, Argentina"),
                                   ("Concepción del Uruguay, Entre Ríos", "Entre Ríos, Argentina"),
                                   ("Capital Federal, Buenos Aires", "Capital Federal, Buenos Aires, Argentina")):
        cruda = jobint.vacante(dict(_aviso(8, modalidad="Remoto"), localizacion=localizacion), "AR", dict(PAISES))
        assert cruda["ubicacion"] == esperado + " (Remoto)"
        vacantes, _, _ = bodega.limpiar([], [cruda], "2026-11-26", 30, set(), set())
        assert vacantes[0]["paises"] == ["AR"] and paises.abiertos(vacantes[0])[0] == {"AR"}
    assert jobint.vacante(dict(_aviso(9), localizacion=None), "CL", dict(PAISES))["ubicacion"] == "Chile (Híbrido)"


def test_una_fecha_imposible_o_futura_queda_vacia():
    assert jobint._fecha("24-11-2026 10:20:32", "2026-11-26") == "2026-11-24"
    assert jobint._fecha("99-99-9999") == "" and jobint._fecha(None) == "" and jobint._fecha("ayer") == ""
    assert jobint._fecha("27-11-2026", "2026-11-26") == ""  # el portal va unas horas adelante
    raro = Cliente([{"content": [_aviso(5, fecha="99-99-9999"), {"id": 1}, "x", None]}])
    crudas, _ = _buscar(raro, presupuesto=1)
    assert len(crudas) == 1 and crudas[0]["fecha"] == ""


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
    # Tres fallos seguidos de un portal lo dejan descansar; los demás portales siguen (el 26 nov cayó solo el de AR).
    class SoloArgentinaCaida(Cliente):
        def post_json(self, url, cuerpo, headers=None, timeout=None):
            datos = super().post_json(url, cuerpo, headers, timeout)
            return None if headers["x-site-id"] == "BMAR" else datos
    medio = SoloArgentinaCaida()
    medio.ultimo_error = {"http": 403}
    crudas, stats = _buscar(medio)
    # Contrato v51: al final el portal en descanso recibe una sola oportunidad más (4 = 3 + 1) y el reporte dice por qué.
    assert [s for _, _, s in medio.pedidas].count("BMAR") == 4 and stats["fallidas"] == 4
    assert [s for _, _, s in medio.pedidas][-1] == "BMAR"  # el reintento va al final, después de los demás portales
    assert stats["portales_caidos"] == ["AR"] and stats["por_pais"]["CL"] == 3 and {c["fuente"] for c in crudas} == {"Laborum"}
    assert stats["motivos_por_pais"] == {"AR": "HTTP 403"} and stats["reintentados"] == ["AR"]
    sin_tiempo = Cliente()
    reloj = iter(range(0, 1000, 10))
    _buscar(sin_tiempo, limite_segundos=25, reloj=lambda: next(reloj))
    assert 1 <= len(sin_tiempo.pedidas) <= 3  # el tope de tiempo corta aunque quede presupuesto


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
    cerrado = _comprobar(_Respuesta({"aviso": {"titulo": "Analista QA", "estado": "Finalizado"}}))[0]
    assert (cerrado["estado"], cerrado["motivo"]) == ("rechazada", "vacante cerrada")
    roto = _comprobar(_Respuesta({}, 404))[0]
    assert (roto["estado"], roto["motivo"]) == ("rechazada", "enlace roto")
    # Un bloqueo, una respuesta rara, una ficha sin estado (o con uno desconocido) u otro aviso con ese número nunca
    # aprueban ni cierran: si la API cambia, no se cierran todas las vacantes.
    for respuesta in (_Respuesta({}, 403), _Respuesta(None), _Respuesta({"aviso": {}}), _Respuesta([1]), _Respuesta("x"),
                      _Respuesta({"aviso": "x"}), _Respuesta({"aviso": {"titulo": "Analista QA"}}),
                      _Respuesta({"aviso": {"titulo": "Analista QA", "estado": 7}}),
                      _Respuesta({"aviso": {"titulo": "Analista QA", "estado": "en revisión"}}),
                      _Respuesta({"aviso": {"titulo": "Vendedor de mostrador", "estado": "activo"}})):
        assert _comprobar(respuesta)[0]["estado"] == "pendiente"


def test_la_fuente_esta_registrada_donde_hace_falta():
    from buscador import enlaces
    from panel import ejecutor
    from buscador import contrato
    assert bodega.config()["presupuestos"]["jobint_busquedas"] > 0
    assert {contrato.portal(jobint.enlace(d, "QA", "1118600001")) for d, _, _ in jobint.SITIOS.values()} == {
        "Bumeran", "Laborum", "Multitrabajos", "Konzerta"}
    for pais, (dominio, _, nombre) in jobint.SITIOS.items():
        assert nombre in ejecutor.fuentes_en(pais)
        assert enlaces.sirve(jobint.enlace(dominio, "Analista QA", "1118600001"))  # se postula en el mismo portal
    assert "Bumeran" not in ejecutor.fuentes_en("CO")


def test_un_portal_que_falla_al_empezar_y_luego_responde_recupera_sus_turnos_al_final(capsys):
    # Contrato v51: un fallo pasajero al empezar dejaba al portal sin buscar toda la corrida.
    class ArgentinaSeRecupera(Cliente):
        fallos = 0

        def post_json(self, url, cuerpo, headers=None, timeout=None):
            datos = super().post_json(url, cuerpo, headers, timeout)
            if headers["x-site-id"] == "BMAR" and self.fallos < 3:
                self.fallos += 1
                self.ultimo_error = {"tipo": "ConnectTimeout"}
                return None
            return datos
    cliente = ArgentinaSeRecupera()
    crudas, stats = _buscar(cliente)
    sitios = [s for _, _, s in cliente.pedidas]
    assert sitios.count("BMAR") > 4 and stats["fallidas"] == 3  # tras responder, siguen sus turnos pendientes
    assert stats["portales_caidos"] == [] and "motivos_por_pais" not in stats and stats["reintentados"] == ["AR"]
    assert "Bumeran" in {c["fuente"] for c in crudas}
    assert "[aviso] jobint" not in capsys.readouterr().err  # nada que avisar: terminó respondiendo


def test_el_registro_dice_que_portal_no_respondio_y_por_que_sin_claves(capsys):
    class TodoCaido(Cliente):
        ultimo_error = {"http": 530, "tipo": "respuesta no JSON"}

        def post_json(self, url, cuerpo, headers=None, timeout=None):
            self.pedidas.append((url, cuerpo["query"], headers["x-site-id"]))
            return None
    crudas, stats = _buscar(TodoCaido())
    assert crudas == [] and stats["portales_caidos"] == ["AR", "CL"]
    assert stats["motivos_por_pais"] == {"AR": "HTTP 530 (respuesta no JSON)", "CL": "HTTP 530 (respuesta no JSON)"}
    aviso = capsys.readouterr().err
    assert "[aviso] jobint" in aviso and "www.bumeran.com.ar" in aviso and "HTTP 530" in aviso
    # Una respuesta que llega pero no trae avisos también se cuenta, con su propio motivo.
    crudas, stats = _buscar(Cliente([{"error": "x"}] * 20))
    assert stats["motivos_por_pais"]["AR"] == "respuesta sin avisos"


def test_se_guarda_una_busqueda_para_la_ultima_oportunidad_del_portal_en_descanso():
    # Con el mapa real los portales que responden gastan todo el presupuesto: sin guardar una búsqueda, el portal en
    # descanso nunca tenía su oportunidad y el reporte decía «reintentados» sin haberlo intentado.
    class SoloArgentinaCaida(Cliente):
        def post_json(self, url, cuerpo, headers=None, timeout=None):
            datos = super().post_json(url, cuerpo, headers, timeout)
            return None if headers["x-site-id"] == "BMAR" else datos
    cliente = SoloArgentinaCaida()
    _, stats = _buscar(cliente, presupuesto=6)
    sitios = [s for _, _, s in cliente.pedidas]
    assert len(sitios) == 6 and sitios.count("BMAR") == 4 and sitios[-1] == "BMAR"  # 3 fallos + la oportunidad final
    assert stats["reintentados"] == ["AR"] and stats["portales_caidos"] == ["AR"]
    # Si el tiempo se acaba antes, no hubo oportunidad y el reporte no dice que la hubo.
    sin_tiempo = SoloArgentinaCaida()
    reloj = iter([0, 0, 0, 0, 0, 0, 100, 100, 100, 100, 100])
    _, stats = _buscar(sin_tiempo, limite_segundos=50, reloj=lambda: next(reloj))
    assert "reintentados" not in stats


def test_el_motivo_queda_en_el_registro_aunque_ningun_portal_llegue_a_descansar(capsys):
    # La corrida de prueba del 27 nov hizo 6 búsquedas repartidas entre portales: 0 avisos y ni una línea que dijera
    # por qué, porque solo se avisaba con tres fallos seguidos del mismo portal.
    class TodoCaido(Cliente):
        ultimo_error = {"http": 403}

        def post_json(self, url, cuerpo, headers=None, timeout=None):
            self.pedidas.append((url, cuerpo["query"], headers["x-site-id"]))
            return None
    _, stats = _buscar(TodoCaido(), presupuesto=2)
    assert stats["fallidas"] == 2 and stats["portales_caidos"] == [] and "reintentados" not in stats
    aviso = capsys.readouterr().err
    assert "[aviso] jobint" in aviso and "HTTP 403" in aviso and "en descanso" not in aviso
    for pais in stats["motivos_por_pais"]:
        assert f"{pais} (" in aviso

