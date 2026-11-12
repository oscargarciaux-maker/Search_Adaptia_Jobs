from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from buscador import bodega, entrega, familias, normalizar, vacante
from panel import afinidad, ejecutor, servicio, terminos
from panel.api import crear_app
from panel.modelos import Configuracion, Expansion, Perfil
from panel.repositorio import ErrorRepositorio, RepositorioDemo, RepositorioSupabase, configuracion_demo, hoy


@pytest.fixture
def cfg():
    return configuracion_demo()


def trabajo(**op):
    texto = ("We require 3 years of experience. English B2 required. We design digital products, "
             "test software and work with engineering and user research. ") * 4
    v = vacante.crear("Product Designer", "Empresa", "https://jobs.lever.co/empresa/uno", "Lever",
        ubicacion="Remote Worldwide", descripcion=texto, fecha=hoy(), hoy=hoy(), remoto=True)
    v["verificacion"] = {"estado": "verificada", "enlaces": [{"url": v["enlace"], "estado": "verificada",
        "comprobada_en": datetime.now(timezone.utc).isoformat()}]}
    v.update(op)
    return v


def test_cupos_se_validan_por_cargo_y_no_por_numero_de_clientes(cfg):
    c = Configuracion.model_validate(cfg)
    assert c.total == 120 and len(c.perfiles_activos(c.cargos[0].id)) == 3
    assert c.validar_publicacion()
    cfg["cargos"][0]["cupo"] += 1
    with pytest.raises(ValidationError, match="120"):
        Configuracion.model_validate(cfg)


def test_borrador_incompleto_no_se_publica(cfg):
    cfg["cargos"][0]["cupo"] -= 1
    c = Configuracion.model_validate(cfg)
    with pytest.raises(ValueError, match="exactamente 120"):
        c.validar_publicacion()


def test_no_programar_un_cargo_sin_cliente_activo(cfg):
    for c in cfg["clientes"]:
        c["activo"] = False
    with pytest.raises(ValueError, match="perfil"):
        Configuracion.model_validate(cfg).validar_publicacion()


def test_perfil_no_puede_referenciar_otro_cliente(cfg):
    cfg["perfiles"][0]["cliente_id"] = str(uuid4())
    with pytest.raises(ValidationError, match="existentes"):
        Configuracion.model_validate(cfg)


@pytest.mark.parametrize("cambio,motivo", [
    ({"paises": ["US"]}, "país"),
    ({"confianza_pais": "baja"}, "país"),
    ({"modalidad": "hibrido"}, "modalidad"),
    ({"idioma": "pt"}, "idioma"),
    ({"fecha_estimada": True}, "publicación"),
    ({"fecha_publicacion": "2020-01-01"}, "publicación"),
    ({"fecha_publicacion": "2099-01-01"}, "publicación"),
    ({"fecha_publicacion": ""}, "fecha"),
    ({"anos_min": 10}, "experiencia"),
    ({"anos_min": None}, "experiencia"),
    ({"ingles": "fluido", "_descripcion": "English C1 required. " * 20}, "inglés"),
])
def test_filtros_independientes_excluyen_antes_de_repartir(cfg, cambio, motivo):
    p = cfg["perfiles"][0]
    r = afinidad.evaluar(trabajo(**cambio), p, hoy())
    assert not r["compatible"] and any(motivo in m for m in r["motivos"])


def test_inglés_deseable_y_datos_faltantes_son_decisiones_explicitas(cfg):
    p = cfg["perfiles"][0]
    r = afinidad.evaluar(trabajo(_descripcion="English C1 preferred. " * 20, ingles="fluido"), p, hoy())
    assert r["compatible"]
    p["aceptar_ingles_sin_dato"] = True
    p["aceptar_experiencia_sin_dato"] = True
    assert afinidad.evaluar(trabajo(_descripcion="Build digital products. " * 20, ingles="", anos_min=None), p, hoy())["compatible"]


def test_archivar_y_guardar_preservan_version_programada(tmp_path):
    r = RepositorioDemo(tmp_path / "demo.json")
    programada = r.publicar(1)
    config = r.config()["borrador"]
    config["clientes"][0]["activo"] = False
    r.guardar(1, config)
    assert r.config()["publicada"]["configuracion"]["clientes"][0]["activo"]
    assert RepositorioDemo(tmp_path / "demo.json").config()["revision"] == 2
    assert programada["vigente_desde"] > hoy()
    with pytest.raises(ErrorRepositorio) as e:
        r.guardar(1, config)
    assert e.value.estado == 409


def test_filtros_de_clientes_no_se_guardan_en_vacantes_y_contexto_se_restaura(cfg):
    anterior = entrega.config()
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        assert entrega.config()["roles"][0]["cupo"] == 50
        assert bodega.config()["control_dirigido"]
        combinaciones = __import__("buscador.fuentes.linkedin_publico", fromlist=["combinaciones"]).combinaciones(familias.mapa(), [])
        assert all(p.get("f_WT") == "2" for _,_,_,p in combinaciones)
        v = trabajo()
        assert entrega.rol_de(v, entrega.config()["roles"])[0]["nombre"] == "Product Designer"
        assert not any("cliente" in k or "perfil" in k for k in v)
    assert entrega.config() == anterior
    assert any(f["id"] == "qa" for f in familias.mapa())


def test_reparto_120_unicas_por_cargo_y_tres_clientes_no_triplican_cupo(cfg):
    ofertas = []
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for c in cfg["cargos"]:
            titulo = {"Product Designer": "Product Designer", "Frontend": "Frontend Developer", "QA": "QA Engineer"}[c["nombre"]]
            for n in range(c["cupo"] + 3):
                v = vacante.crear(titulo, f"Empresa {c['nombre']} {n}", f"https://jobs.lever.co/empresa/{c['id']}-{n}",
                    "Lever", ubicacion="Remote Worldwide", descripcion=trabajo()["_descripcion"], fecha=hoy(), hoy=hoy())
                v["verificacion"] = {"estado": "verificada"}
                ofertas.append(v)
        elegidas, resumen = entrega.elegir(ofertas, {}, hoy())
        assert [len(elegidas["cargo:" + c["id"]]) for c in cfg["cargos"]] == [50, 40, 30]
        assert len({v["id"] for lista in elegidas.values() for v,_ in lista}) == 120
        assert all(r["faltan"] == 0 for r in resumen["roles"].values())


def test_cargo_nuevo_funciona_sin_banco_y_afines_configurados(cfg):
    c = cfg["cargos"][0]
    c.update(nombre="Especialista en bioacústica", terminos_exactos=["Especialista en bioacústica"],
             terminos_similares=["Bioacoustics Researcher"], terminos_excluidos=["Junior"])
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        assert next(f for f in familias.clasificar("Bioacoustics Researcher") if f["familia"] == "cargo:" + c["id"])["coincidencia"] == "similar"
        assert not any(f["familia"] == "cargo:" + c["id"] for f in familias.clasificar("Junior Bioacoustics Researcher"))


def test_esco_no_adopta_resultados_ambiguos_ni_consulta_uris_arbitrarias():
    calls = []
    def get(url, **op):
        calls.append(url)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "_embedded": {"results": [{"title": "Neuroergonomics Researcher", "uri": "https://otro.example/privado"}]}})
    r = terminos.sugerir("Neuroergonomics Researcher", SimpleNamespace(get=get))
    assert calls == [terminos.ESCO + "/search"]
    assert r["requiere_revision"]
    assert r["terminos_exactos"]


def test_esco_proporciona_equivalentes_de_un_cargo_no_mapeado():
    def get(url, **op):
        if url.endswith("/search"):
            datos = {"_embedded": {"results": [{"title": "Neuroergonomics Researcher",
                "uri": "http://data.europa.eu/esco/occupation/ejemplo"}]}}
        else:
            datos = {"alternativeLabel": {op["params"]["language"]: ["Investigador de neuroergonomía"]}}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: datos)
    r = terminos.sugerir("Neuroergonomics Researcher", SimpleNamespace(get=get))
    assert "Investigador de neuroergonomía" in r["terminos_similares"]
    assert not r["requiere_revision"]


def test_sugerencias_del_mapa_priorizan_el_oficio_y_no_mezclan_cercanos():
    # «Editor de video» aparece como cercano en motion/animación, audio o redes: esos oficios no son equivalentes.
    r = terminos.sugerir("Editor de video", consultar_esco=False)
    claves = {normalizar.titulo_base(x) for x in r["terminos_exactos"] + r["terminos_similares"]}
    assert {"video editor", "editor audiovisual"} <= {normalizar.titulo_base(x) for x in r["terminos_exactos"]}
    assert "postproductor" in claves
    assert not claves & {"motion designer", "animador", "vfx artist", "community manager"}
    assert r["fuentes"] == ["Equivalentes del mapa existente"]
    assert len(claves) == len(r["terminos_exactos"]) + len(r["terminos_similares"])


def test_entrada_de_expansion_no_envia_contactos_a_fuentes_externas():
    with pytest.raises(ValidationError):
        Expansion(cargo="persona" + "@" + "empresa.test")


def test_servidor_real_permanece_cerrado_sin_autenticacion(monkeypatch):
    monkeypatch.delenv("PANEL_OPERATOR_EMAILS", raising=False)
    monkeypatch.delenv("PANEL_ORIGIN", raising=False)
    with pytest.raises(RuntimeError, match="cerrado"):
        crear_app()


def test_api_demo_guarda_conflictos_programa_y_bloquea_origen_ajeno():
    r = RepositorioDemo()
    with TestClient(crear_app(demo=True, repositorio=r)) as c:
        cfg = c.get("/api/config").json()
        assert c.put("/api/config", json={"revision": 1, "configuracion": cfg["borrador"]}).status_code == 403
        cab = {"Origin": "http://testserver"}
        assert c.put("/api/config", json={"revision": 1, "configuracion": cfg["borrador"]}, headers=cab).status_code == 200
        assert c.put("/api/config", json={"revision": 1, "configuracion": cfg["borrador"]}, headers=cab).status_code == 409
        assert c.post("/api/config/publicar", json={"revision": 2}, headers=cab).status_code == 200
        resultados = c.get("/api/resultados").json()
        assert resultados["listas"] == 50
        msg = c.get("/api/whatsapp/" + cfg["borrador"]["clientes"][0]["id"]).json()
        assert msg["vacantes"] == 50 and "Hola" in msg["texto"]
        assert "service_role" not in c.get("/api/session").text


def test_api_autoriza_solo_operador_confirmado_y_no_confia_en_cookie():
    email = "operador" + "@" + "empresa.test"
    class Repo(RepositorioDemo):
        url = "https://supabase.example"
        cabeceras = {}
        sesion = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=200,
            json=lambda: {"email": email, "email_confirmed_at": "2026-01-01"}))
    with TestClient(crear_app(repositorio=Repo(), origen="https://panel.example", operadores=[email])) as c:
        assert c.get("/api/config").status_code == 401
        c.cookies.set("adaptia_session", "token-ficticio")
        assert c.get("/api/config").status_code == 200
        Repo.sesion = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=401, json=lambda: {}))
        assert c.get("/api/config").status_code == 401


@pytest.mark.parametrize("estado,horas", [("active", 7), ("closed", 0), ("archived", 0), ("active", -1)])
def test_whatsapp_excluye_cierres_caducidad_y_fechas_futuras(estado, horas):
    repo = RepositorioDemo()
    r = repo.resultados(None)
    fila = r["filas"][0]
    fila["catalogo_vacantes"]["status"] = estado
    fila["catalogo_vacantes"]["datos"]["verificacion"]["enlaces"][0]["comprobada_en"] = (
        datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    repo.resultados = lambda *a: {**r, "filas": [fila]}
    assert servicio.whatsapp(repo, r["clientes"][0]["id"])["vacantes"] == 0


def test_whatsapp_no_duplica_una_oferta_por_perfiles_y_no_acepta_url_ajena():
    repo = RepositorioDemo()
    r = repo.resultados(None)
    fila = r["filas"][0]
    repo.resultados = lambda *a: {**r, "filas": [fila, deepcopy(fila)]}
    assert servicio.whatsapp(repo, r["clientes"][0]["id"])["vacantes"] == 1
    fila["catalogo_vacantes"]["datos"]["verificacion"]["enlaces"][0]["url"] = "https://otro.example/empleo"
    assert servicio.whatsapp(repo, r["clientes"][0]["id"])["vacantes"] == 0


def test_otro_perfil_compatible_rescata_la_misma_vacante_sin_duplicarla():
    repo = RepositorioDemo()
    r = repo.resultados(None)
    compatible = r["filas"][0]
    incompatible = deepcopy(compatible)
    incompatible["filtros"]["experiencia_min"] = 20
    incompatible["filtros"]["experiencia_max"] = 30
    repo.resultados = lambda *a: {**r, "filas": [incompatible, compatible]}
    assert servicio.whatsapp(repo, r["clientes"][0]["id"])["vacantes"] == 1


def test_cambio_de_titulo_actual_invalida_asignacion_historica():
    repo = RepositorioDemo()
    r = repo.resultados(None)
    fila = r["filas"][0]
    fila["catalogo_vacantes"]["datos"]["titulo"] = "Accountant"
    repo.resultados = lambda *a: {**r, "filas": [fila]}
    assert servicio.whatsapp(repo, r["clientes"][0]["id"])["vacantes"] == 0


def test_reparto_considera_clientes_sin_cubrir_dentro_del_mismo_cargo(cfg):
    p1, p2 = deepcopy(cfg["perfiles"][:2])
    p1["vive_en"], p2["vive_en"] = "CO", "ES"
    candidatas = [(trabajo(id=str(i), empresa="Empresa " + str(i), paises=[pais], confianza_pais="alta"), "exacto")
                  for i, pais in enumerate(["CO"] * 5 + ["ES"] * 5)]
    elegidas = entrega.variadas(candidatas, 4, 2, hoy(), perfiles=[p1, p2])
    assert sum("CO" in v["paises"] for v, _ in elegidas) == 2
    assert sum("ES" in v["paises"] for v, _ in elegidas) == 2


def test_registro_diario_reintentable_preserva_filtros_y_version(cfg):
    version = {"revision": 7, "configuracion": cfg}
    v = trabajo()
    class Repo:
        def __init__(self):
            self.ejecucion, self.asignaciones = None, {}
        def pedir(self, metodo, ruta, **op):
            if ruta == "panel_ejecuciones":
                if metodo == "GET": return [self.ejecucion] if self.ejecucion else []
                if metodo == "POST": self.ejecucion = {"id":str(uuid4()),**op["json"]}
                if metodo == "PATCH": self.ejecucion.update(op["json"])
            elif ruta == "entregas_diarias":
                return [{"role_id":"cargo:"+cfg["cargos"][0]["id"],"vacante_id":v["id"],"match_grade":"exact","snapshot":v}]
            elif ruta == "panel_asignaciones":
                for fila in op["json"]:
                    self.asignaciones[(fila["perfil_id"],fila["vacante_id"])] = fila
    repo = Repo()
    ejecutor.registrar(repo, version, hoy())
    ejecutor.registrar(repo, version, hoy())
    assert len(repo.asignaciones) == 3
    assert repo.ejecucion["estado"] == "parcial"
    assert repo.ejecucion["resumen"]["vacantes"] == 1
    assert next(iter(repo.asignaciones.values()))["cargo_configuracion"]["nombre"] == "Product Designer"
    with pytest.raises(RuntimeError, match="conserva otra versión"):
        ejecutor.iniciar(repo,{**version,"revision":8},hoy())


def test_captura_fallida_queda_visible_sin_exponer_clientes(cfg,monkeypatch,tmp_path):
    cambios=[]
    class Repo:
        def operativa(self, fecha): return {"revision":1,"configuracion":cfg}
        def pedir(self, metodo, ruta, **op):
            if metodo=="GET": return [{"id":"ejemplo","revision":1}]
            cambios.append(op["json"])
    def fallo(*a,**k): raise RuntimeError("Fuente no disponible")
    monkeypatch.setattr(bodega,"correr",fallo)
    with pytest.raises(RuntimeError,match="Fuente no disponible"):
        ejecutor.correr(tmp_path,repo=Repo())
    assert cambios[-1]["estado"] == "fallida"
    assert "Cliente de ejemplo" not in str(cambios)


def test_exclusion_de_nivel_prevalece_sobre_normalizacion_del_titulo():
    cargo = {"nombre":"Product Designer","terminos_excluidos":["junior"]}
    assert terminos.grado("Junior Product Designer",cargo)[0] is None
    assert terminos.grado("Senior Product Designer",cargo)[0] == "exacto"


# ── Vista previa: estimación con las reglas reales, sin guardar ni exponer vacantes o clientes ──────────────────────

def test_vista_previa_usa_las_mismas_reglas_que_la_seleccion():
    # Precalcular experiencia/inglés no cambia el veredicto de ningún perfil.
    perfiles = [Perfil.model_validate(dict(p, ingles_maximo=n, experiencia_min=a, experiencia_max=b,
                                           aceptar_experiencia_sin_dato=s, aceptar_ingles_sin_dato=s))
                for p in configuracion_demo()["perfiles"][:1]
                for n in ("sin_filtro", "A2", "B2") for a, b in ((None, None), (0, 2), (3, 8)) for s in (False, True)]
    textos = ["We require 3 years of experience. English B2 required. " * 4, "English C1 is a plus. " * 4, "Sin datos. " * 20]
    for texto in textos:
        for anos in (None, 1, 3, 6):
            v = trabajo(_descripcion=texto, anos_min=anos, paises=["CO", "ES"], confianza_pais="alta")
            ligera = afinidad.ligera(v, texto)
            assert "_descripcion" not in ligera and "enlace" not in ligera
            for p in perfiles:
                assert afinidad.evaluar(ligera, p, hoy()) == afinidad.evaluar(v, p, hoy())


def test_vista_previa_muestra_lo_que_bloquea_y_cuanto_se_gana_al_admitir_sin_dato(cfg):
    repo = RepositorioDemo()
    modelo = Configuracion.model_validate(cfg)
    r = servicio.vista_previa(repo, modelo)
    pid = str(modelo.perfiles[0].id)
    combinada = r["perfiles"][pid]["limitantes"][0]
    assert combinada["sugerencia"] == "Admitir experiencia e inglés no informados"
    modelo.perfiles[0].aceptar_experiencia_sin_dato = modelo.perfiles[0].aceptar_ingles_sin_dato = True
    despues = servicio.vista_previa(repo, modelo)["perfiles"][pid]["compatibles"]
    assert despues == r["perfiles"][pid]["compatibles"] + combinada["vacantes"] > 0
    assert set(r["cargos"]) == {c["id"] for c in cfg["cargos"]}
    assert all(c["estado"] in {"alcanza", "justo", "insuficiente", "sin_cupo"} for c in r["cargos"].values())


def test_vista_previa_api_no_guarda_ni_devuelve_vacantes_ni_clientes(cfg):
    repo = RepositorioDemo()
    with TestClient(crear_app(demo=True, repositorio=repo)) as c:
        borrador = deepcopy(cfg)
        borrador["clientes"][0]["nombre"] = "Nombre privado de prueba"
        assert c.post("/api/vista-previa", json={"configuracion": borrador}).status_code == 403
        r = c.post("/api/vista-previa", json={"configuracion": borrador}, headers={"Origin": "http://testserver"})
        assert r.status_code == 200
        assert "Nombre privado" not in r.text and "titulo" not in r.text and "example.org" not in r.text
        assert set(r.json()["perfiles"]) == {p["id"] for p in cfg["perfiles"]}
        assert c.get("/api/config").json()["revision"] == 1 and repo.config()["borrador"] == cfg
        incompleto = deepcopy(cfg)
        incompleto["perfiles"][0]["modalidades"] = []
        r = c.post("/api/vista-previa", json={"configuracion": incompleto}, headers={"Origin": "http://testserver"})
        assert r.status_code == 200 and r.json() == {"incompleto": True}


def test_catalogo_vigente_lee_solo_campos_de_filtro_y_excluye_entregadas_copias_y_rechazadas(monkeypatch):
    monkeypatch.setattr("buscador.supabase.credenciales", lambda: ("https://prueba.supabase.co", "clave-ficticia"))
    # PostgREST devuelve los campos ya extraídos de `datos` (select con ->/->>), sin descripción.
    filas = {"entregas_diarias": [{"vacante_id": "a" * 16}],
             "catalogo_vacantes": [
                 {"id": "a" * 16, "titulo": "QA Engineer"},
                 {"id": "b" * 16, "titulo": "QA Engineer", "ids_agrupados": ["b" * 16, "a" * 16]},
                 {"id": "c" * 16, "titulo": "QA Engineer", "duplicada_de": "d" * 16},
                 {"id": "d" * 16, "titulo": "QA Engineer", "verificacion": "rechazada"},
                 {"id": "e" * 16, "titulo": "QA Engineer", "anos_min": 3, "requisito_ingles": "en:B2:0"},
                 {"id": "f" * 16, "titulo": "QA Engineer", "ingles": "intermedio", "requisito_ingles": None}]}
    llamadas = []
    def request(metodo, url, **op):
        tabla = url.rsplit("/", 1)[1]
        llamadas.append((tabla, op["params"]))
        assert "description_full" not in op["params"]["select"]
        return SimpleNamespace(status_code=200, content=b"x", json=lambda: filas[tabla])
    repo = RepositorioSupabase(SimpleNamespace(request=request))
    vacantes = repo.catalogo_vigente()["vacantes"]
    assert [v["id"] for v in vacantes] == ["e" * 16, "f" * 16]
    assert vacantes[0]["_anos_minimos"] == 3 and vacantes[0]["_requisito_ingles"] == "en:B2:0"
    # Fila aún sin el campo v7: nivel guardado tratado como obligatorio (estimación conservadora).
    assert vacantes[1]["_requisito_ingles"] == "en:B1:1"
    n = len(llamadas)
    repo.catalogo_vigente()
    assert len(llamadas) == n  # reutilizado: editar el borrador no recorre otra vez Supabase
    # Vencida: responde al instante con la copia y renueva en segundo plano.
    repo._catalogo = (repo._catalogo[0] - 4000, repo._catalogo[1])
    assert repo.catalogo_vigente()["vacantes"] == vacantes
    import time as _t
    for _ in range(100):
        if not repo._refrescando: break
        _t.sleep(0.02)
    assert len(llamadas) > n and _t.monotonic() - repo._catalogo[0] < 60


def test_ingles_precalculado_en_el_catalogo_da_el_mismo_veredicto():
    perfiles = [Perfil.model_validate(dict(p, ingles_maximo=n, aceptar_ingles_sin_dato=s))
                for p in configuracion_demo()["perfiles"][:1] for n in ("sin_filtro", "A2", "B1", "B2", "C1") for s in (False, True)]
    for texto in ["English B2 required. " * 4, "English C1 is a plus. " * 4, "Advanced English is preferred. " * 4, "Sin datos. " * 20]:
        v = trabajo(_descripcion=texto, paises=["CO", "ES"], confianza_pais="alta")
        v["ingles"] = __import__("buscador.etiquetas", fromlist=["ingles"]).ingles(texto)
        datos = vacante.publica(v)
        assert "requisito_ingles" in datos
        ligera = afinidad.ligera(datos)
        for p in perfiles:
            assert afinidad.evaluar(ligera, p, hoy()) == afinidad.evaluar(v, p, hoy())


# ── Contrato v8: país de residencia y modalidades ──────────────────────────────────────────────────────────────────

def _vacante_en(ubicacion, titulo="Product Designer"):
    from buscador import paises as geo
    lugar = geo.elegibles(titulo, ubicacion, "", None)
    return trabajo(paises=lugar["paises"], modalidad=lugar["modalidad"], confianza_pais=lugar["confianza"])


@pytest.mark.parametrize("ubicacion,esperado", [
    ("Remote - LATAM", True), ("Remoto Latinoamérica", True), ("Madrid, Spain (Remote, open to LATAM)", True),
    ("Remote - Mexico, Colombia, Argentina", True), ("Remote - Worldwide", True),
    ("Remote - South America", False), ("Remoto, Brazil", False), ("Bogotá, Colombia", False),
])
def test_vive_en_mexico_y_acepta_remoto_recibe_las_remotas_abiertas_a_mexico(ubicacion, esperado):
    p = Perfil.model_validate({"id": str(uuid4()), "cliente_id": str(uuid4()), "cargo_id": str(uuid4()),
                               "vive_en": "MX", "modalidades": ["remoto"]})
    assert afinidad.evaluar(_vacante_en(ubicacion), p, hoy())["compatible"] is esperado


def test_presencial_solo_en_su_pais_o_en_los_que_se_mudaria():
    base = {"id": str(uuid4()), "cliente_id": str(uuid4()), "cargo_id": str(uuid4()), "vive_en": "MX",
            "modalidades": ["presencial", "hibrido"]}
    bogota, cdmx = _vacante_en("Bogotá, Colombia"), _vacante_en("Ciudad de México, México")
    assert bogota["modalidad"] == "presencial" and cdmx["modalidad"] == "presencial"
    p = Perfil.model_validate(base)
    assert afinidad.evaluar(cdmx, p, hoy())["compatible"]
    r = afinidad.evaluar(bogota, p, hoy())
    assert not r["compatible"] and "oficina en otro país" in r["motivos"]
    assert afinidad.evaluar(bogota, Perfil.model_validate({**base, "paises_presenciales_extra": ["CO"]}), hoy())["compatible"]
    # Solo presencial: una remota abierta a México no entra.
    assert not afinidad.evaluar(_vacante_en("Remote - LATAM"), p, hoy())["compatible"]


@pytest.mark.parametrize("antiguo,vive,mods,extra", [
    ({"paises": ["MX"], "modalidad": "remoto"}, "MX", ["remoto"], []),
    ({"paises": ["CO", "PE", "ES"], "modalidad": "cualquiera"}, "CO", ["remoto", "hibrido", "presencial"], ["PE", "ES"]),
    ({"paises": ["NI"], "modalidad": "presencial"}, "NI", ["presencial"], []),
])
def test_perfiles_v6_se_leen_como_v8_sin_migracion(antiguo, vive, mods, extra):
    p = Perfil.model_validate({"id": str(uuid4()), "cliente_id": str(uuid4()), "cargo_id": str(uuid4()), **antiguo})
    assert (p.vive_en, p.modalidades, p.paises_presenciales_extra) == (vive, mods, extra)
    assert "paises" not in p.model_dump() and "modalidad" not in p.model_dump()


def test_busqueda_dirigida_por_residencia_y_remotas_regionales(cfg):
    cfg["perfiles"][0].update(vive_en="MX", modalidades=["remoto", "presencial"], paises_presenciales_extra=["CO"])
    mapa, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy())
    lugares = dict(next(m for m in mapa if m["id"] == "cargo:" + cfg["perfiles"][0]["cargo_id"])["lugares"])
    assert lugares["REMOTO_MX"]["f_WT"] == "2" and lugares["REMOTO"]["location"] == "Latin America"
    assert "REMOTO_MUNDO" in lugares and "MX" in lugares and "CO" in lugares


def test_api_muestra_perfiles_v6_ya_convertidos():
    from panel.api import a_v8
    antiguo = {"id": str(uuid4()), "cliente_id": str(uuid4()), "cargo_id": str(uuid4()),
               "paises": ["MX", "CO"], "modalidad": "cualquiera"}
    estado = a_v8({"revision": 3, "borrador": {"perfiles": [dict(antiguo)]},
                   "publicada": {"configuracion": {"perfiles": [dict(antiguo)]}}})
    for p in (estado["borrador"]["perfiles"][0], estado["publicada"]["configuracion"]["perfiles"][0]):
        assert p["vive_en"] == "MX" and p["paises_presenciales_extra"] == ["CO"] and len(p["modalidades"]) == 3


# ── Estimación con búsqueda en vivo ────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def en_vivo(monkeypatch):
    monkeypatch.setattr(servicio, "_ULTIMA", {})
    from buscador.fuentes import linkedin_apify, publicaciones_apify

    def prohibido(*a, **k):
        raise AssertionError("la estimación en vivo nunca usa Apify")
    monkeypatch.setattr(linkedin_apify, "buscar", prohibido)
    monkeypatch.setattr(publicaciones_apify, "buscar", prohibido)


def _crudo(titulo, ubicacion, n, remoto=None, dias=1):
    texto = "We design digital products with a collaborative team and research users every week. " * 3
    return {"titulo": titulo, "empresa": f"Empresa {n}", "ubicacion": ubicacion, "descripcion": texto,
            "fecha": (date.fromisoformat(hoy()) - timedelta(days=dias)).isoformat(),
            "enlace": f"https://www.linkedin.com/jobs/view/{4100000000 + n}", "remoto": remoto, "fuente": "LinkedIn"}


def test_en_vivo_aplica_cargo_y_filtros_del_perfil_y_no_devuelve_vacantes(cfg, en_vivo):
    cfg["perfiles"][0].update(vive_en="MX", modalidades=["remoto"], experiencia_min=None, experiencia_max=None,
                              ingles_maximo="sin_filtro", antiguedad_dias=14)
    crudas = [_crudo("Product Designer", "Remote - LATAM", 1, True),
              _crudo("UX Designer", "Remote - Worldwide", 2, True),
              _crudo("Product Designer", "Remote - Worldwide", 2, True),  # mismo enlace: se cuenta una vez
              _crudo("Product Designer", "Bogotá, Colombia", 3),            # presencial en otro país
              _crudo("Product Designer", "Remote - LATAM", 4, True, dias=20),  # fuera del plazo
              _crudo("Contador", "Remote - LATAM", 5, True)]                 # otro cargo
    llamadas = []

    def fuentes(cargo, perfil, limite):
        llamadas.append((cargo["nombre"], perfil.vive_en, limite))
        return crudas, {"LinkedIn": {"avisos": len(crudas)}}
    c = Configuracion.model_validate(cfg)
    r = servicio.estimacion_en_vivo(RepositorioDemo(), c, cfg["perfiles"][0]["id"], fuentes=fuentes)
    assert llamadas == [("Product Designer", "MX", servicio.LIMITE_SEGUNDOS)]
    assert r["del_cargo"] == 4 and r["compatibles"] == 2 and r["nuevas"] == 2
    assert [l["motivo"] for l in r["limitantes"]] == ["publicación fuera del plazo"]  # Bogotá falla dos filtros
    assert "vacantes" not in r and "Es una muestra" in r["nota"]


def test_en_vivo_espera_entre_busquedas_del_mismo_perfil_y_una_a_la_vez(cfg, en_vivo):
    c = Configuracion.model_validate(cfg)
    reloj = iter([100.0, 101.0, 150.0, 230.0, 231.0])
    vacias = lambda *a: ([], {})
    pid = cfg["perfiles"][0]["id"]
    assert "compatibles" in servicio.estimacion_en_vivo(RepositorioDemo(), c, pid, fuentes=vacias, reloj=lambda: next(reloj))
    r = servicio.estimacion_en_vivo(RepositorioDemo(), c, pid, fuentes=vacias, reloj=lambda: next(reloj))
    assert r["espera"] == 71 and "compatibles" not in r
    assert "compatibles" in servicio.estimacion_en_vivo(RepositorioDemo(), c, pid, fuentes=vacias, reloj=lambda: next(reloj))
    servicio._EN_CURSO.acquire()
    try:
        assert servicio.estimacion_en_vivo(RepositorioDemo(), c, cfg["perfiles"][1]["id"], fuentes=vacias)["ocupado"]
    finally:
        servicio._EN_CURSO.release()


def test_en_vivo_excluye_ya_entregadas(cfg, en_vivo):
    cfg["perfiles"][0].update(vive_en="CO", modalidades=["remoto"], experiencia_min=None, experiencia_max=None,
                              ingles_maximo="sin_filtro")
    crudas = [_crudo("Product Designer", "Remote - LATAM", n, True) for n in (1, 2)]
    entregada = vacante.crear(**{k: crudas[0][k] for k in ("titulo", "empresa", "enlace")}, fuente="LinkedIn")["id"]
    repo = RepositorioDemo()
    repo._catalogo = {"vacantes": [], "entregadas": {entregada}, "actualizado": "x"}
    r = servicio.estimacion_en_vivo(repo, Configuracion.model_validate(cfg), cfg["perfiles"][0]["id"],
                                    fuentes=lambda *a: (crudas, {}))
    assert r["ya_entregadas"] == 1 and r["compatibles"] == 1


def test_fuentes_publicas_respetan_limite_sin_reintentar_429(cfg, monkeypatch):
    from buscador.fuentes import getonbrd, linkedin_publico
    vistos = {}

    def li(cliente, mapa, activos, estado, presupuesto, **k):
        vistos["li"] = (presupuesto, k["limite_segundos"], k["max_dias"], k["max_paginas"], dict(mapa[0]["lugares"]))
        cliente.get("https://www.linkedin.com/x")
        return [], {"busquedas": 1}

    def gob(cliente, consultas):
        vistos["gob"] = consultas
        raise RuntimeError("caída")

    class Falso:
        def __init__(self, **k): pass
        def get(self, url, params=None, reintentar_429=True, **k):
            vistos["reintentar"] = reintentar_429
    monkeypatch.setattr(linkedin_publico, "buscar", li)
    monkeypatch.setattr(getonbrd, "buscar", gob)
    monkeypatch.setattr("buscador.http.Cliente", Falso)
    p = Perfil.model_validate({**cfg["perfiles"][0], "vive_en": "MX", "modalidades": ["remoto"], "antiguedad_dias": 7})
    cargo = cfg["cargos"][0]
    _, fuentes = servicio.fuentes_publicas(cargo, p, 25)
    presupuesto, limite, dias, paginas, lugares = vistos["li"]
    assert limite < 25 and dias == 7 and paginas == 1 and presupuesto == len(lugares)
    assert set(lugares) == {"REMOTO_MX", "REMOTO", "REMOTO_MUNDO"} and vistos["reintentar"] is False
    assert fuentes["Get on Board"] == {"error": True} and "LinkedIn" in fuentes


def test_api_en_vivo_en_demo_no_sale_a_internet(monkeypatch):
    monkeypatch.setattr(servicio, "_ULTIMA", {})
    monkeypatch.setattr(servicio, "fuentes_publicas", lambda *a: (_ for _ in ()).throw(AssertionError("internet")))
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    cfg = api.get("/api/config").json()["borrador"]
    r = api.post("/api/estimacion-en-vivo", json={"configuracion": cfg, "perfil_id": cfg["perfiles"][0]["id"]},
                 headers={"origin": "http://testserver"}).json()
    assert r["fuentes"] == {"Demostración": {"avisos": r["avisos"], "busquedas": 0, "fallidas": 0}}
    assert r["del_cargo"] >= r["compatibles"] >= 0


def test_pasada_posterior_fallida_no_borra_el_resultado_del_dia(cfg, monkeypatch, tmp_path):
    cambios = []
    class Repo:
        def operativa(self, fecha): return {"revision": 1, "configuracion": cfg}
        def pedir(self, metodo, ruta, **op):
            if metodo == "GET":
                return [{"id": "ejemplo", "revision": 1, "estado": "parcial",
                         "resumen": {"vacantes": 35, "meta": 120, "faltantes": {"QA": 13}}}]
            cambios.append(op["json"])
    monkeypatch.setattr(bodega, "correr", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("selección canónica")))
    with pytest.raises(RuntimeError):
        ejecutor.correr(tmp_path, repo=Repo())
    assert "estado" not in cambios[-1]
    assert cambios[-1]["resumen"]["vacantes"] == 35 and cambios[-1]["resumen"]["aviso_ultima_pasada"]
