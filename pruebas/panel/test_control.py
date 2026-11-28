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
    if "paises" in op and "alcance_mundial" not in op:
        # Contrato v23: al cambiar los países de la vacante de prueba, sus campos del mundo dicen lo mismo.
        v["alcance_mundial"] = False
        v["paises_mundo"] = op.get("paises_mundo", list(op["paises"]))
    return v


def sin_metas(cfg):
    """Configuración anterior a v21: los perfiles no traen meta y manda el cupo de cada cargo."""
    for p in cfg["perfiles"]:
        p.pop("meta_diaria", None)
    cfg.pop("techo_diario", None)
    return cfg


def test_cupos_se_validan_por_cargo_y_no_por_numero_de_clientes(cfg):
    c = Configuracion.model_validate(cfg)
    assert c.total == 120 and len(c.perfiles_activos(c.cargos[0].id)) == 3
    assert c.validar_publicacion()
    cfg["perfiles"][0]["meta_diaria"] += 1  # contrato v21: el borrador puede pasar el techo; programar, no
    with pytest.raises(ValueError, match="suman 121 y el techo diario es 120"):
        Configuracion.model_validate(cfg).validar_publicacion()
    cfg["techo_diario"] = 121
    assert Configuracion.model_validate(cfg).validar_publicacion().total == 121


def test_configuracion_anterior_reparte_el_cupo_del_cargo_entre_sus_perfiles(cfg):
    sin_metas(cfg)
    cfg["cargos"][0]["cupo"] = 50  # tres perfiles: 17, 17 y 16
    c = Configuracion.model_validate(cfg)
    metas = [p.meta_diaria for p in c.perfiles_activos(c.cargos[0].id)]
    assert sorted(metas) == [16, 17, 17] and c.cargos[0].cupo == 50 and c.techo_diario == 120


def test_borrador_incompleto_no_se_publica(cfg):
    for p in cfg["perfiles"]:
        p["meta_diaria"] = 0
    c = Configuracion.model_validate(cfg)
    with pytest.raises(ValueError, match="meta diaria"):
        c.validar_publicacion()
    cfg["perfiles"][0]["meta_diaria"] = 5  # ya no hace falta repartir exactamente 120
    assert Configuracion.model_validate(cfg).validar_publicacion().total == 5


def test_comunidad_recibe_solo_lo_que_cabe_bajo_el_techo(cfg):
    cfg["clientes"][4]["comunidad"] = True  # su perfil es el de QA
    for p in cfg["perfiles"]:
        p["meta_diaria"] = 30
    c = Configuracion.model_validate(cfg)  # reales: 4 × 30 = 120; a Comunidad no le cabe nada
    assert c.metas() == {"techo": 120, "reales": 120, "comunidad": 30, "comunidad_cabe": 0, "libre": 0}
    assert c.cargos[2].cupo == 0  # sin cupo propio, pero su perfil sigue activo para recibir lo que sobre
    assert len(c.perfiles_activos(c.cargos[2].id)) == 1
    cfg["techo_diario"] = 140
    c = Configuracion.model_validate(cfg)
    assert c.metas()["comunidad_cabe"] == 20 and c.cargos[2].cupo == 20


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
])
def test_filtros_independientes_excluyen_antes_de_repartir(cfg, cambio, motivo):
    p = cfg["perfiles"][0]
    r = afinidad.evaluar(trabajo(**cambio), p, hoy())
    assert not r["compatible"] and any(motivo in m for m in r["motivos"])


def test_v27_anos_no_descartan_y_dejan_aviso(cfg):
    """Contrato v27: los años ordenan y quedan como etiqueta."""
    p = cfg["perfiles"][0]
    r = afinidad.evaluar(trabajo(anos_min=10), p, hoy())
    assert r["compatible"] and "Pide 10 años de experiencia" in r["avisos"] and afinidad.faltas(r) == 1
    assert afinidad.faltas(afinidad.evaluar(trabajo(), p, hoy())) == 0


def test_v33_ingles_exigido_mayor_ordena_y_deja_etiqueta(cfg):
    """Contrato v33 (Oscar, 16 nov): el nivel de inglés ordena y deja su etiqueta; nunca descarta."""
    p = cfg["perfiles"][0]  # inglés hasta B2
    exigido = afinidad.evaluar(trabajo(ingles="fluido", _descripcion="English C1 required. " * 20), p, hoy())
    assert exigido["compatible"] and "Pide inglés C1" in exigido["avisos"] and afinidad.faltas(exigido) == 1
    igual = afinidad.evaluar(trabajo(_descripcion="English B2 required. " * 20), p, hoy())
    assert igual["compatible"] and afinidad.faltas(igual) == 0


def test_v27_sin_dato_de_anos_no_descarta_ni_avisa(cfg):
    p = cfg["perfiles"][0]
    r = afinidad.evaluar(trabajo(anos_min=None), p, hoy())
    assert r["compatible"] and not r["avisos"]


def test_v27_antiguedad_del_perfil_ordena_pero_30_dias_descarta(cfg):
    p = dict(cfg["perfiles"][0], antiguedad_dias=7)
    veinte = (date.fromisoformat(hoy()) - timedelta(days=20)).isoformat()
    cuarenta = (date.fromisoformat(hoy()) - timedelta(days=40)).isoformat()
    r = afinidad.evaluar(trabajo(fecha_publicacion=veinte), p, hoy())
    assert r["compatible"] and "Publicada hace 20 días" in r["avisos"]
    assert not afinidad.evaluar(trabajo(fecha_publicacion=cuarenta), p, hoy())["compatible"]


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
    assert programada["vigente_desde"] == hoy()  # contrato v43: confirmar rige desde hoy
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
        # Contrato v43: 10 por defecto y 2 por empresa (la demostración tiene 5 empresas); el resto, «Tengo N más».
        from panel.borradores import SALUDOS  # el saludo cambia con la fecha («¡Buen día!» el 28 nov)
        assert msg["vacantes"] == 10 and msg["sobran"] == 40 and "Tengo 40" in msg["texto"]
        assert any(msg["texto"].startswith(s.split("{")[0]) for s in SALUDOS)
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
        cabeceras = c.get("/api/config").headers  # PR 1.5: HTTPS obligatorio y cabeceras de seguridad
        assert cabeceras["strict-transport-security"].startswith("max-age=") and cabeceras["x-frame-options"] == "DENY"
        Repo.sesion = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=401, json=lambda: {}))
        # 18 nov (velocidad): un acceso válido se recuerda 60 s por su huella; otro token siempre se comprueba.
        c.cookies.set("adaptia_session", "otro-token")
        assert c.get("/api/config").status_code == 401


def test_sesion_valida_se_comprueba_una_vez_por_minuto_y_se_olvida_al_salir():
    email = "operador" + "@" + "empresa.test"
    llamadas = []

    def preguntar(*a, **k):
        llamadas.append(1)
        return SimpleNamespace(status_code=200, json=lambda: {"email": email, "email_confirmed_at": "2026-01-01"})

    class Repo(RepositorioDemo):
        url = "https://supabase.example"
        cabeceras = {}
        sesion = SimpleNamespace(get=preguntar, post=lambda *a, **k: SimpleNamespace(status_code=204))
    with TestClient(crear_app(repositorio=Repo(), origen="https://panel.example", operadores=[email])) as c:
        c.cookies.set("adaptia_session", "token-ficticio")
        for _ in range(3):
            assert c.get("/api/config").status_code == 200
        assert len(llamadas) == 1
        assert "server-timing" in c.get("/api/config").headers
        c.post("/api/auth/logout", headers={"origin": "https://panel.example"})
        c.cookies.set("adaptia_session", "token-ficticio")
        c.get("/api/config")
        assert len(llamadas) >= 2  # al salir se olvida la copia y se vuelve a preguntar


@pytest.mark.parametrize("estado,horas", [("active", 25), ("closed", 0), ("archived", 0), ("active", -1)])  # v31: 24 h
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
    # Contrato v43: una versión confirmada a mitad del día ya no tumba la búsqueda; la fila pasa a la más nueva y
    # anota la anterior. Una versión más vieja que la de la fila no la cambia.
    revision = repo.ejecucion["revision"]
    assert ejecutor.iniciar(repo, {**version, "revision": revision + 7}, hoy())["revision"] == revision + 7
    assert repo.ejecucion["resumen"]["revisiones_anteriores"] == [revision]
    assert ejecutor.iniciar(repo, version, hoy())["revision"] == revision + 7


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


def test_v27_vista_previa_ya_no_corta_por_datos_sin_informar(cfg):
    repo = RepositorioDemo()
    modelo = Configuracion.model_validate(cfg)
    r = servicio.vista_previa(repo, modelo)
    pid = str(modelo.perfiles[0].id)
    assert r["perfiles"][pid]["compatibles"] > 0
    assert not any("no informad" in l["sugerencia"] for l in r["perfiles"][pid]["limitantes"])
    modelo.perfiles[0].aceptar_experiencia_sin_dato = modelo.perfiles[0].aceptar_ingles_sin_dato = True
    assert servicio.vista_previa(repo, modelo)["perfiles"][pid]["compatibles"] == r["perfiles"][pid]["compatibles"]
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
        # Sección 7a: un perfil pendiente no deja sin estimación a los demás; dice qué le falta.
        incompleto = deepcopy(cfg)
        incompleto["perfiles"][0]["modalidades"] = []
        incompleto["clientes"].append({"id": "00000000-0000-4000-8000-0000000000aa", "nombre": " "})  # a medio escribir
        r = c.post("/api/vista-previa", json={"configuracion": incompleto}, headers={"Origin": "http://testserver"})
        pid = cfg["perfiles"][0]["id"]
        assert r.status_code == 200 and r.json()["incompletos"] == {
            pid: "Elige al menos una modalidad: remoto, híbrido o presencial."}
        assert set(r.json()["perfiles"]) == {p["id"] for p in cfg["perfiles"][1:]}
        assert "Nombre privado" not in r.text
        for p in incompleto["perfiles"]:
            p["modalidades"] = []
        r = c.post("/api/vista-previa", json={"configuracion": incompleto}, headers={"Origin": "http://testserver"})
        assert r.json()["incompleto"] is True and r.json()["motivo"] and "perfiles" not in r.json()


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
    return trabajo(paises=lugar["paises"], modalidad=lugar["modalidad"], confianza_pais=lugar["confianza"],
                   paises_mundo=lugar["paises_mundo"], alcance_mundial=lugar["alcance_mundial"],
                   zona_utc=lugar["zona_utc"], ubicacion=ubicacion)


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
    # Contrato v49 (decisión de Oscar): sin ciudad en el perfil no llegan presenciales ni híbridas.
    sin_ciudad = afinidad.evaluar(cdmx, Perfil.model_validate(base), hoy())
    assert not sin_ciudad["compatible"] and sin_ciudad["motivos"] == ["falta la ciudad en el perfil"]
    p = Perfil.model_validate({**base, "ciudades": ["Ciudad de México"]})
    assert afinidad.evaluar(cdmx, p, hoy())["compatible"]
    r = afinidad.evaluar(bogota, p, hoy())
    assert not r["compatible"] and "oficina en otro país" in r["motivos"]
    se_mudaria = Perfil.model_validate({**base, "ciudades": ["Ciudad de México", "Bogotá"], "paises_presenciales_extra": ["CO"]})
    assert afinidad.evaluar(bogota, se_mudaria, hoy())["compatible"]
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
              _crudo("Product Designer", "Remote - LATAM", 4, True, dias=20),  # fuera del plazo del perfil: solo avisa
              _crudo("Product Designer", "Remote - LATAM", 6, True, dias=40),  # más de 30 días: regla del sistema
              _crudo("Contador", "Remote - LATAM", 5, True)]                 # otro cargo
    llamadas = []

    def fuentes(cargo, perfil, limite):
        llamadas.append((cargo["nombre"], perfil.vive_en, limite))
        return crudas, {"LinkedIn": {"avisos": len(crudas)}}
    c = Configuracion.model_validate(cfg)
    r = servicio.estimacion_en_vivo(RepositorioDemo(), c, cfg["perfiles"][0]["id"], fuentes=fuentes)
    assert llamadas == [("Product Designer", "MX", servicio.LIMITE_SEGUNDOS)]
    assert r["del_cargo"] == 5 and r["compatibles"] == 3 and r["nuevas"] == 3
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


def test_api_en_vivo_solo_exige_el_perfil_y_dice_que_falta(monkeypatch):
    # Sección 4 (13 nov): con un cliente nuevo decía «no puede buscar» sin explicar por qué.
    monkeypatch.setattr(servicio, "_ULTIMA", {})
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    cfg = api.get("/api/config").json()["borrador"]
    pid, otro = cfg["perfiles"][0]["id"], cfg["perfiles"][1]["id"]
    for p in cfg["perfiles"]:
        if p["id"] == otro:
            p["modalidades"] = []  # otro perfil a medio editar
    cfg["cargos"][0]["cupo"] = 120  # cupos que todavía no cuadran
    pedir = lambda c, perfil: api.post("/api/estimacion-en-vivo", json={"configuracion": c, "perfil_id": perfil},
                                       headers={"origin": "http://testserver"}).json()
    assert "compatibles" in pedir(cfg, pid)
    r = pedir(cfg, otro)
    assert r == {"incompleto": True, "motivo": "Elige al menos una modalidad: remoto, híbrido o presencial."}
    sin_cargo = deepcopy(cfg)
    sin_cargo["cargos"] = []
    assert pedir(sin_cargo, pid)["motivo"] == "Elige un cargo para el perfil."
    assert "no está en el borrador" in pedir(cfg, "00000000-0000-4000-8000-000000000000")["motivo"]


def test_en_vivo_un_error_interno_se_explica_y_libera_el_turno(cfg, en_vivo, caplog):
    def rota(*a):
        raise RuntimeError("detalle interno")
    c = Configuracion.model_validate(cfg)
    r = servicio.estimacion_en_vivo(RepositorioDemo(), c, cfg["perfiles"][0]["id"], fuentes=rota)
    assert "error del servidor" in r["error"] and "detalle interno" not in r["error"]
    assert "La estimación en vivo falló" in caplog.text
    assert servicio._EN_CURSO.acquire(blocking=False)
    servicio._EN_CURSO.release()


def test_fuentes_publicas_no_espera_a_una_fuente_colgada(cfg, monkeypatch):
    import threading
    import time
    from buscador.fuentes import getonbrd, linkedin_publico
    soltar = threading.Event()
    monkeypatch.setattr(linkedin_publico, "buscar", lambda *a, **k: (soltar.wait(10), ([], {}))[1])
    monkeypatch.setattr(getonbrd, "buscar", lambda *a, **k: ([{"titulo": "x"}], {"avisos": 1}))
    p = Perfil.model_validate({**cfg["perfiles"][0], "modalidades": ["remoto"]})
    inicio = time.monotonic()
    try:
        crudas, fuentes = servicio.fuentes_publicas(cfg["cargos"][0], p, -4.5)  # medio segundo en total
    finally:
        soltar.set()
    assert time.monotonic() - inicio < 3
    assert fuentes["LinkedIn"] == {"error": True} and crudas == [{"titulo": "x"}]


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


# ── Contrato v9: mínimo de 5 por perfil con ampliación marcada ─────────────────────────────────────────────────────

SIN_DATO = "We design digital products with a collaborative team and research users every week. " * 4


def _oferta(titulo, n, texto, ubicacion="Remote - Worldwide", remoto=True):
    v = vacante.crear(titulo, f"Empresa {n}", f"https://jobs.lever.co/empresa/amp-{n}", "Lever", ubicacion=ubicacion,
                      descripcion=texto, fecha=hoy(), hoy=hoy(), remoto=remoto)
    v["verificacion"] = {"estado": "verificada"}
    return v


@pytest.fixture
def cfg_un_perfil(cfg):
    for p in cfg["perfiles"][1:3]:
        p["activo"] = False  # el cargo Product Designer queda con un solo perfil (Colombia, remoto, 0–5 años, inglés ≤B2)
    cfg["cargos"][0]["terminos_cercanos"] = ["UX Researcher"]
    return cfg


def _elegir(cfg, ofertas):
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for v in ofertas:  # como hace la bodega al reetiquetar con el mapa del panel
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        elegidas, resumen = entrega.elegir(ofertas, {}, hoy())
    rid = "cargo:" + cfg["cargos"][0]["id"]
    return elegidas[rid], resumen["roles"][rid]


def test_v27_sin_dato_y_cercanos_entran_directo_despues_de_lo_que_encaja(cfg_un_perfil):
    con_dato = trabajo()["_descripcion"]  # dice 3 años e inglés B2: cumple el perfil
    ofertas = ([_oferta("Product Designer", n, con_dato) for n in range(2)] +
               [_oferta("Product Designer", 10, SIN_DATO)] +
               [_oferta("UX Researcher", 20 + n, SIN_DATO) for n in range(3)] +
               [_oferta("Product Designer", 30, con_dato, ubicacion="Bogotá, Colombia", remoto=None)])  # presencial
    elegidas, resumen = _elegir(cfg_un_perfil, ofertas)
    assert len(elegidas) == 6 and not any(v.get("_ampliacion") for v, _ in elegidas) and not resumen["ampliadas"]
    assert not any(v["empresa"] == "Empresa 30" for v, _ in elegidas)  # la ubicación sí descarta
    assert [g for _, g in elegidas][:3] == ["exacto"] * 3 and [g for _, g in elegidas][3:] == ["cercano"] * 3


def test_con_cinco_que_cumplen_no_se_amplia_y_el_cupo_manda(cfg_un_perfil):
    con_dato = trabajo()["_descripcion"]
    ofertas = [_oferta("Product Designer", n, con_dato) for n in range(5)] + \
              [_oferta("Product Designer", 10 + n, SIN_DATO) for n in range(4)]
    elegidas, _ = _elegir(cfg_un_perfil, ofertas)
    assert not any(v.get("_ampliacion") for v, _ in elegidas)
    pocas = [_oferta("Product Designer", 0, con_dato)] + [_oferta("Product Designer", 10 + n, SIN_DATO) for n in range(6)]
    cfg_un_perfil["perfiles"][0]["meta_diaria"] = 3  # contrato v21: la meta del perfil fija el cupo del cargo
    elegidas, _ = _elegir(cfg_un_perfil, pocas)
    assert len(elegidas) == 3  # las ampliadas cuentan dentro del cupo


def test_presencial_puede_ampliar_a_remotas_abiertas_a_su_pais(cfg_un_perfil):
    cfg_un_perfil["perfiles"][0].update(modalidades=["presencial"], aceptar_experiencia_sin_dato=True,
                                       aceptar_ingles_sin_dato=True)
    ofertas = [_oferta("Product Designer", n, SIN_DATO) for n in range(3)] + \
              [_oferta("Product Designer", 10, SIN_DATO, ubicacion="Remote - Brazil")]  # remota cerrada a Colombia
    elegidas, _ = _elegir(cfg_un_perfil, ofertas)
    assert [v.get("_ampliacion") for v, _ in elegidas] == ["remota_cercana"] * 3


def test_registro_v27_asigna_sin_marcar_como_ampliada_una_vacante_sin_datos(cfg):
    p_estricto = cfg["perfiles"][0]
    rid = "cargo:" + cfg["cargos"][0]["id"]
    ampliada = dict(_oferta("Product Designer", 1, SIN_DATO), _ampliacion="sin_dato")
    asignaciones = []
    class Repo:
        ejecucion = None
        def pedir(self, metodo, ruta, **op):
            if ruta == "panel_ejecuciones":
                if metodo == "GET": return [self.ejecucion] if self.ejecucion else []
                if metodo == "POST": self.ejecucion = {"id": "e1", **op["json"]}
                if metodo == "PATCH": self.ejecucion.update(op["json"])
            elif ruta == "entregas_diarias":
                return [{"role_id": rid, "vacante_id": ampliada["id"], "match_grade": "exact", "snapshot": ampliada}]
            elif ruta == "panel_asignaciones":
                asignaciones.extend(op["json"])
    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    perfiles = {a["perfil_id"] for a in asignaciones}
    assert p_estricto["id"] in perfiles
    assert not any({"ampliacion": "sin_dato"} in a["explicacion"] for a in asignaciones)  # v27: ya cumple
    assert repo.ejecucion["resumen"]["ampliadas"] == 0
    # El panel muestra la marca; el texto para WhatsApp no.
    fila = dict(asignaciones[0], catalogo_vacantes={"id": ampliada["id"], "status": "active", "datos": dict(
        ampliada, verificacion={"estado": "verificada", "enlaces": [{"url": ampliada["enlace"], "estado": "verificada",
        "comprobada_en": datetime.now(timezone.utc).isoformat()}]}), "description_full": SIN_DATO})
    class Resultados:
        def resultados(self, cliente_id, fecha):
            return {"ejecucion": repo.ejecucion, "clientes": [], "filas": [fila]}
    r = servicio.resultados(Resultados())
    assert r["vacantes"][0]["ampliacion"] == "" and r["vacantes"][0]["estado"] == "lista"
    texto = servicio.whatsapp(Resultados(), None)["texto"]
    assert ampliada["titulo"] in texto and "mpliad" not in texto and "sin años" not in texto


def test_vacantes_de_un_dia_anterior_se_ven_entregadas_y_no_por_confirmar(cfg):
    from datetime import date, timedelta
    rid = "cargo:" + cfg["cargos"][0]["id"]
    oferta = dict(_oferta("Product Designer", 1, SIN_DATO), _ampliacion="sin_dato")
    asignaciones = []
    class Repo:
        ejecucion = None
        def pedir(self, metodo, ruta, **op):
            if ruta == "panel_ejecuciones":
                if metodo == "GET": return [self.ejecucion] if self.ejecucion else []
                if metodo == "POST": self.ejecucion = {"id": "e1", **op["json"]}
                if metodo == "PATCH": self.ejecucion.update(op["json"])
            elif ruta == "entregas_diarias":
                return [{"role_id": rid, "vacante_id": oferta["id"], "match_grade": "exact", "snapshot": oferta}]
            elif ruta == "panel_asignaciones":
                asignaciones.extend(op["json"])
    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    vieja = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()  # comprobación ya caducada (más de 6 h)
    fila = dict(asignaciones[0], catalogo_vacantes={"id": oferta["id"], "status": "active", "datos": dict(
        oferta, verificacion={"estado": "verificada", "enlaces": [{"url": oferta["enlace"], "estado": "verificada",
        "comprobada_en": vieja}]}), "description_full": SIN_DATO})

    def ver(dia):
        class Resultados:
            def resultados(self, cliente_id, fecha):
                return {"ejecucion": dict(repo.ejecucion, fecha=dia), "clientes": [], "filas": [fila]}
        return servicio.resultados(Resultados())
    ayer = (date.fromisoformat(hoy()) - timedelta(days=1)).isoformat()
    r = ver(ayer)
    v = r["vacantes"][0]
    assert v["estado"] == "entregada" and v["entregada_el"] == ayer and v["enlace"] and r["listas"] == 0
    hoy_ = ver(hoy())["vacantes"][0]  # la de hoy sigue esperando su recomprobación
    assert hoy_["estado"] == "por_confirmar" and not hoy_["entregada_el"]


def test_sugerencias_traen_cercanos_y_la_estimacion_cuenta_la_ampliacion(cfg_un_perfil):
    s = terminos.sugerir("Product Designer", consultar_esco=False)
    assert s["terminos_cercanos"] and not set(map(str.lower, s["terminos_cercanos"])) & set(map(str.lower, s["terminos_exactos"]))
    r = servicio.vista_previa(RepositorioDemo(), Configuracion.model_validate(cfg_un_perfil), hoy())
    info = r["perfiles"][cfg_un_perfil["perfiles"][0]["id"]]
    assert "ampliables" in info
    assert info["compatibles"] >= 5 or info["compatibles"] + info["ampliables"] <= 5


def test_embudo_dice_que_filtro_del_cliente_corta(cfg_un_perfil):
    con_dato = trabajo()["_descripcion"]
    ofertas = [_oferta("Product Designer", n, con_dato) for n in range(3)]
    activo = next(p for p in cfg_un_perfil["perfiles"] if p.get("activo", True) and p["cargo_id"] == cfg_un_perfil["cargos"][0]["id"])
    activo["modalidades"] = ["presencial"]  # las ofertas de prueba son remotas: el filtro que corta es la modalidad
    with ejecutor.activar({"configuracion": cfg_un_perfil}, hoy()):
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        _, resumen = entrega.elegir(ofertas, {}, hoy())
        e = entrega.embudo(ofertas, {}, hoy(), resumen=resumen)["cargo:" + cfg_un_perfil["cargos"][0]["id"]]
    assert e["nuevas"] == 3 and e["cumplen_filtros"] == 0 and e["enlace_comprobado"] == 0
    assert e["filtros_que_cortan"].get("modalidad") == 3
    assert e["principal_perdida"].startswith("no cumplen los filtros") and "modalidad" in e["principal_perdida"]


def test_embudo_por_cargo_sin_datos_de_clientes_y_se_conserva_entre_capturas(cfg_un_perfil):
    con_dato = trabajo()["_descripcion"]
    ofertas = [_oferta("Product Designer", n, con_dato) for n in range(3)] + [_oferta("Product Designer", 9, "corta")]
    ofertas[2]["verificacion"] = {"estado": "pendiente"}
    with ejecutor.activar({"configuracion": cfg_un_perfil}, hoy()):
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        _, resumen = entrega.elegir(ofertas, {}, hoy())
        e = entrega.embudo(ofertas, {}, hoy(), resumen=resumen)["cargo:" + cfg_un_perfil["cargos"][0]["id"]]
    assert (e["encontradas"], e["con_descripcion"], e["cumplen_filtros"], e["enlace_comprobado"]) == (4, 3, 3, 2)
    assert e["principal_perdida"] and "Cliente" not in str(e)
    # Contrato v51: los últimos pasos también por idioma del aviso (solo cuentas), para ver dónde se pierde el español.
    idioma = ofertas[0]["idioma"]
    assert e["por_idioma"][idioma] == {"nuevas": 3, "cumplen_filtros": 3, "enlace_comprobado": 2,
                                       "entregadas": e["entregadas"]}
    otro = "en" if idioma == "es" else "es"
    assert e["por_idioma"][otro] == {"nuevas": 0, "cumplen_filtros": 0, "enlace_comprobado": 0, "entregadas": 0}
    # El registro guarda el embudo por nombre de cargo y una captura horaria sin embudo no lo borra.
    assert ejecutor._embudo_por_nombre({"entrega": {"embudo": {"cargo:x": dict(e, nombre="QA")}}})["QA"]["encontradas"] == 4


def test_estimacion_avisa_cargos_que_comparten_vacantes(cfg):
    cfg["cargos"][1].update(nombre="Diseñador UX/UI", terminos_exactos=["Product Designer"], terminos_similares=[])
    r = servicio.vista_previa(RepositorioDemo(), Configuracion.model_validate(cfg), hoy())
    segundo = r["cargos"][cfg["cargos"][1]["id"]]
    assert segundo["solapes"] and segundo["solapes"][0]["cargo"] == "Product Designer"
    assert not r["cargos"][cfg["cargos"][0]["id"]]["solapes"]


def test_cargos_parecidos_se_reparten_las_compartidas_por_turnos(cfg):
    """12 nov: «Diseñador UX/UI» recibía solo 2 porque «Product Designer», primero en la lista, se llevaba las compartidas."""
    sin_metas(cfg)
    cfg["cargos"][1].update(nombre="Diseñador UX/UI", terminos_exactos=["Product Designer"], terminos_similares=[],
                            cupo=10)
    cfg["cargos"][0]["cupo"], cfg["cargos"][2]["cupo"] = 20, 90
    for p in cfg["perfiles"]:
        p.update(experiencia_min=None, experiencia_max=None, ingles_maximo="sin_filtro")
    con_dato = trabajo()["_descripcion"]
    ofertas = [_oferta("Product Designer", n, con_dato) for n in range(15)]
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        elegidas, _ = entrega.elegir(ofertas, {}, hoy())
        legado_cfg = dict(entrega.config(), roles=[{k: v for k, v in r.items() if k != "_perfiles"}
                                                   for r in entrega.config()["roles"]])
        legado, _ = entrega.elegir(ofertas, {}, hoy(), legado_cfg)
    pd, ux = (elegidas["cargo:" + cfg["cargos"][i]["id"]] for i in (0, 1))
    assert (len(pd), len(ux)) == (10, 5)  # proporcional a lo que le falta a cada uno (20 y 10)
    assert not {v["id"] for v, _ in pd} & {v["id"] for v, _ in ux}
    # Sin perfiles (modo heredado) sigue mandando el orden de la lista.
    assert len(legado["cargo:" + cfg["cargos"][1]["id"]]) == 0


def test_lo_exclusivo_va_siempre_a_su_cargo(cfg):
    cfg["cargos"][1].update(nombre="Diseñador UX/UI", terminos_exactos=["Product Designer"],
                            terminos_similares=["Diseñador Gráfico Digital"], cupo=10)
    sin_metas(cfg)
    cfg["cargos"][0]["cupo"], cfg["cargos"][2]["cupo"] = 20, 90
    for p in cfg["perfiles"]:
        p.update(experiencia_min=None, experiencia_max=None, ingles_maximo="sin_filtro")
    con_dato = trabajo()["_descripcion"]
    ofertas = [_oferta("Diseñador Gráfico Digital", 100 + n, con_dato) for n in range(3)]
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        elegidas, _ = entrega.elegir(ofertas, {}, hoy())
    assert len(elegidas["cargo:" + cfg["cargos"][1]["id"]]) == 3


# ── Contrato v20: un solo campo de años de experiencia; el servidor busca ±3 ─────────────────────────────────────

@pytest.mark.parametrize("anos, minimo, maximo", [(5, 2, 8), (1, 0, 4), (0, 0, 3), (39, 36, 40)])
def test_anos_de_experiencia_dan_un_rango_de_mas_menos_tres(cfg, anos, minimo, maximo):
    p = Perfil.model_validate({**cfg["perfiles"][0], "experiencia_anos": anos, "experiencia_min": 30,
                               "experiencia_max": 31})  # lo que traiga el navegador no manda
    assert (p.experiencia_min, p.experiencia_max) == (minimo, maximo)


def test_perfil_antiguo_conserva_su_rango_y_vacio_es_sin_filtro(cfg):
    antiguo = Perfil.model_validate({**cfg["perfiles"][0], "experiencia_min": 0, "experiencia_max": 5})
    assert antiguo.experiencia_anos is None and (antiguo.experiencia_min, antiguo.experiencia_max) == (0, 5)
    vacio = Perfil.model_validate({**cfg["perfiles"][0], "experiencia_min": None, "experiencia_max": None})
    assert (vacio.experiencia_min, vacio.experiencia_max) == (None, None)
    with pytest.raises(ValidationError):
        Perfil.model_validate({**cfg["perfiles"][0], "experiencia_anos": 41})


def test_con_cinco_anos_entra_un_aviso_de_ocho_y_no_uno_de_nueve(cfg):
    p = Perfil.model_validate({**cfg["perfiles"][0], "experiencia_anos": 5, "modalidades": ["remoto"],
                               "ingles_maximo": "sin_filtro", "vive_en": "CO"})
    base = dict(paises=["CO", "ES"], confianza_pais="alta")
    ocho = afinidad.evaluar(trabajo(_descripcion="We require 8 years of experience. " * 4, anos_min=8, **base), p, hoy())
    nueve = afinidad.evaluar(trabajo(_descripcion="We require 9 years of experience. " * 4, anos_min=9, **base), p, hoy())
    assert "experiencia fuera del rango" not in ocho["incumple"]
    assert "experiencia fuera del rango" in nueve["incumple"]
    # El rescate por persona (v11) sigue sumando ±2 sobre el rango de ±3.
    assert afinidad.relajado(p, "experiencia_cercana").experiencia_max == 10


def test_lo_que_sobra_del_techo_va_a_comunidad(cfg):
    """Contrato v21: los clientes reales piden 10; el techo es 30. Las 9 vacantes que nadie tomó y sirven a Comunidad
    no se pierden: completan el día hasta el techo."""
    cfg["clientes"][1]["comunidad"] = True
    for i, p in enumerate(cfg["perfiles"]):
        p.update(meta_diaria=[10, 1, 0, 0, 0][i], vive_en="CO", experiencia_min=None, experiencia_max=None,
                 ingles_maximo="sin_filtro")
    cfg["techo_diario"] = 30
    con_dato = trabajo()["_descripcion"]
    ofertas = [_oferta("Product Designer", n, con_dato) for n in range(20)]
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        for v in ofertas:
            v["familias"] = familias.clasificar(v["titulo"], v["_descripcion"])
        elegidas, _ = entrega.elegir(ofertas, {}, hoy())
        sin_comunidad = dict(entrega.config(), roles=[{**r, "_comunidad": []} for r in entrega.config()["roles"]])
        solo_cupo, _ = entrega.elegir(ofertas, {}, hoy(), sin_comunidad)
    rid = "cargo:" + cfg["cargos"][0]["id"]
    assert len(solo_cupo[rid]) == 11  # meta real (10) + lo que cabe de Comunidad (1)
    assert len(elegidas[rid]) == 20  # y el sobrante del techo completa con lo que sirve a Comunidad
    assert len({v["id"] for v, _ in elegidas[rid]}) == 20


def test_sin_sql_015_se_explica_como_instalarla(monkeypatch):
    monkeypatch.setattr("buscador.supabase.credenciales", lambda: ("https://prueba.supabase.co", "clave-ficticia"))
    cuerpo = {"code": "P0001", "message": "Reparte exactamente 120 vacantes"}
    sesion = SimpleNamespace(request=lambda *a, **k: SimpleNamespace(status_code=400, content=b"x", json=lambda: cuerpo))
    repo = RepositorioSupabase(sesion)
    with pytest.raises(ErrorRepositorio, match="Preparar Supabase") as e:
        repo.pedir("POST", "rpc/panel_publicar", json={})
    assert e.value.estado == 422
    cuerpo["message"] = "Las metas superan el techo diario"
    with pytest.raises(ErrorRepositorio, match="más que el techo diario: baja algunas metas"):  # v49: qué hacer
        repo.pedir("POST", "rpc/panel_publicar", json={})


# ── Contrato v22: restricciones, prioridades, margen y nivel según los años ──────────────────────────────────────

def _perfil_v22(cfg, **cambios):
    return Perfil.model_validate({**cfg["perfiles"][0], "experiencia_min": None, "experiencia_max": None,
                                  "ingles_maximo": "sin_filtro", **cambios})


def test_margen_de_cuatro_anos(cfg):
    p = _perfil_v22(cfg, experiencia_anos=6, margen_experiencia=4)
    assert (p.experiencia_min, p.experiencia_max) == (2, 10)
    with pytest.raises(ValidationError):
        _perfil_v22(cfg, experiencia_anos=6, margen_experiencia=5)


def test_nivel_segun_los_anos(cfg):
    junior = trabajo(titulo="Junior Product Designer")
    senior = _perfil_v22(cfg, experiencia_anos=7)
    assert "nivel inferior al del perfil" in afinidad.evaluar(junior, senior, hoy())["incumple"]
    assert "nivel inferior al del perfil" in afinidad.evaluar(trabajo(titulo="Product Design Intern"), senior, hoy())["incumple"]
    assert afinidad.evaluar(trabajo(titulo="Senior Product Designer", anos_min=6), senior, hoy())["compatible"]
    # Con 2 años o menos no hay filtro de experiencia: entra aunque pida 8 años.
    nuevo = _perfil_v22(cfg, experiencia_anos=1)
    pide_seis = trabajo(anos_min=8)
    assert afinidad.evaluar(pide_seis, nuevo, hoy())["compatible"]
    assert "experiencia fuera del rango" in afinidad.evaluar(pide_seis, _perfil_v22(cfg, experiencia_anos=3), hoy())["incumple"]


def _tasas_fijas(monkeypatch, fecha=None):
    from datetime import date
    from buscador import tasas
    monkeypatch.setattr(tasas, "tabla", lambda: {"fecha": fecha or date.today().isoformat(), "inestables": ["ARS", "VES"],
                                                 "tasas": {"USD": 1.0, "EUR": 0.9, "COP": 4000.0, "ARS": 1500.0}})


def test_salario_minimo_compara_en_la_misma_moneda(cfg, monkeypatch):
    _tasas_fijas(monkeypatch)
    p = _perfil_v22(cfg, restricciones=[{"tipo": "salario_minimo", "monto": 3000, "moneda": "USD", "periodo": "month"}])
    bajo = trabajo(salario="USD 1.500 - 2.000 per month")
    alto = trabajo(salario="USD 40,000 - 50,000 per year")  # 4.166 al mes: pasa
    sin_dato = trabajo(salario="")
    assert "salario menor al aceptado" in afinidad.evaluar(bajo, p, hoy())["incumple"]
    for v in (alto, sin_dato):
        assert "salario menor al aceptado" not in afinidad.evaluar(v, p, hoy())["incumple"]


def test_salario_minimo_con_equivalencia_de_monedas_v26(cfg, monkeypatch):
    _tasas_fijas(monkeypatch)
    mil_usd = _perfil_v22(cfg, restricciones=[{"tipo": "salario_minimo", "monto": 1000, "moneda": "USD",
                                               "periodo": "month"}])
    motivo = "salario menor al aceptado"
    assert motivo not in afinidad.evaluar(trabajo(salario="EUR 999 per month"), mil_usd, hoy())["incumple"]  # ≈1110 USD
    assert motivo in afinidad.evaluar(trabajo(salario="EUR 700 per month"), mil_usd, hoy())["incumple"]  # ≈778 USD
    assert motivo in afinidad.evaluar(trabajo(salario="COP 2.000.000 mensual"), mil_usd, hoy())["incumple"]  # 500 USD
    assert motivo not in afinidad.evaluar(trabajo(salario="COP 4.500.000 mensual"), mil_usd, hoy())["incumple"]
    # Margen del 10 %: 1050 frente a 1100 no descarta; 950 frente a 1100 sí.
    mil_cien = _perfil_v22(cfg, restricciones=[{"tipo": "salario_minimo", "monto": 1100, "moneda": "USD",
                                                "periodo": "month"}])
    assert motivo not in afinidad.evaluar(trabajo(salario="USD 1,050 per month"), mil_cien, hoy())["incumple"]
    assert motivo in afinidad.evaluar(trabajo(salario="USD 950 per month"), mil_cien, hoy())["incumple"]
    # Moneda inestable, por hora frente a mensual: no se compara.
    assert motivo not in afinidad.evaluar(trabajo(salario="ARS 100.000 por mes"), mil_usd, hoy())["incumple"]
    assert motivo not in afinidad.evaluar(trabajo(salario="EUR 5 per hour"), mil_usd, hoy())["incumple"]


def test_salario_con_tabla_vencida_no_descarta(cfg, monkeypatch):
    _tasas_fijas(monkeypatch, fecha="2026-01-01")
    p = _perfil_v22(cfg, restricciones=[{"tipo": "salario_minimo", "monto": 1000, "moneda": "USD", "periodo": "month"}])
    assert "salario menor al aceptado" not in afinidad.evaluar(trabajo(salario="EUR 300 per month"), p, "2026-11-15")[
        "incumple"]
    assert "salario menor al aceptado" in afinidad.evaluar(trabajo(salario="USD 300 per month"), p, hoy())["incumple"]


def test_actualizar_tasas_conserva_la_tabla_si_la_fuente_falla(tmp_path, monkeypatch):
    from buscador import tasas
    monkeypatch.setattr(tasas, "RUTA", tmp_path / "tasas.yaml")
    tasas.tabla.cache_clear()
    with pytest.raises(RuntimeError):
        tasas.actualizar(lambda: {"result": "error"})
    assert not (tmp_path / "tasas.yaml").exists()
    tasas.actualizar(lambda: {"result": "success", "rates": {"USD": 1, "EUR": 0.9, "COP": 4000}})
    assert tasas.tabla()["tasas"] == {"EUR": 0.9, "COP": 4000.0, "USD": 1.0}
    assert round(tasas.convertir(900, "EUR", "USD"), 2) == 1000.0
    tasas.tabla.cache_clear()


def test_palabras_y_tipo_de_contrato_descartan(cfg):
    p = _perfil_v22(cfg, restricciones=[{"tipo": "palabras", "palabras": ["call center", "Java"]},
                                        {"tipo": "contrato", "tipos": ["freelance"]}])
    con_java = trabajo(_descripcion=trabajo()["_descripcion"] + " Strong Java experience required.")
    javascript = trabajo(_descripcion=trabajo()["_descripcion"] + " JavaScript and Figma.")
    freelance = trabajo(titulo="Product Designer (Freelance)")
    assert "menciona algo que el perfil no acepta" in afinidad.evaluar(con_java, p, hoy())["incumple"]
    assert afinidad.evaluar(javascript, p, hoy())["compatible"]  # palabra completa: JavaScript no es Java
    assert "tipo de contrato no aceptado" in afinidad.evaluar(freelance, p, hoy())["incumple"]
    # La ampliación nunca relaja una restricción.
    assert afinidad.evaluar_ampliada(con_java, p, hoy(), "empresa_4")["incumple"]  # la ampliación no las borra
    with pytest.raises(ValidationError):
        _perfil_v22(cfg, restricciones=[{"tipo": "palabras", "palabras": []}])


def test_preferidas_solo_ordenan_cuando_sobran_candidatas(cfg):
    perfil = {**cfg["perfiles"][0], "sectores_preferidos": ["Fintech"], "palabras_preferidas": ["AI prototyping"]}
    texto = trabajo()["_descripcion"]
    comunes = [_oferta("Product Designer", n, texto) for n in range(4)]
    fintech = _oferta("Product Designer", 9, texto + " We are a fintech doing AI prototyping.")
    fintech["visto_primera_vez"] = fintech["fecha_publicacion"] = (date.fromisoformat(hoy()) - timedelta(days=9)).isoformat()
    candidatas = [(v, "exacto") for v in comunes + [fintech]]
    una = entrega.variadas(candidatas, 1, 2, hoy(), perfiles=[perfil])
    assert una[0][0]["empresa"] == "Empresa 9"  # más vieja, pero menciona dos preferidas
    sin_preferencias = entrega.variadas(candidatas, 1, 2, hoy(), perfiles=[cfg["perfiles"][0]])
    assert sin_preferencias[0][0]["empresa"] != "Empresa 9"
    assert len(entrega.variadas(candidatas, 10, 2, hoy(), perfiles=[perfil])) == 5  # con pocas, entran todas


@pytest.mark.parametrize("texto, descarta", [
    ("Requirements:\n- Java and Python", True),
    ("Requirements:\n- Python\nNice to have:\n- Java", False),
    ("We need Figma. Java is a plus.", False),
    ("Deseable: experiencia en call center.", False),
    ("Experiencia en call center (excluyente).", True),
    ("Responsabilidades\nAtender llamadas en call center", True),
    ("Nice to have\n- Java\nRequirements\n- Java", True),
    ("Bonus points: Java, Go\nWe build apps.", False),
    ("Idealmente conocimientos de call center.", False),
    ("Preferred qualifications\n* Java\n* Kotlin", False),
])
def test_lo_deseable_no_descarta(cfg, texto, descarta):
    """14 nov, pedido de Oscar: si el aviso menciona algo solo como deseable, no se descarta la vacante."""
    p = _perfil_v22(cfg, restricciones=[{"tipo": "palabras", "palabras": ["Java", "call center"]}])
    v = trabajo(_descripcion=trabajo()["_descripcion"] + "\n" + texto)
    assert ("menciona algo que el perfil no acepta" in afinidad.evaluar(v, p, hoy())["incumple"]) is descarta


def test_en_el_titulo_siempre_descarta(cfg):
    p = _perfil_v22(cfg, restricciones=[{"tipo": "palabras", "palabras": ["Java"]}])
    assert "menciona algo que el perfil no acepta" in afinidad.evaluar(trabajo(titulo="Java Product Designer"), p, hoy())["incumple"]


# ── Contrato v23: ubicaciones del mundo, permiso legal, ciudades y horario compatible ────────────────────────────

def _perfil_mundo(**cambios):
    return Perfil.model_validate({"id": str(uuid4()), "cliente_id": str(uuid4()), "cargo_id": str(uuid4()),
                                  "vive_en": "CO", "modalidades": ["remoto"], **cambios})


def _vacante_texto(ubicacion, descripcion=""):
    from buscador import paises as geo
    lugar = geo.elegibles("Product Designer", ubicacion, descripcion, None)
    return trabajo(paises=lugar["paises"], modalidad=lugar["modalidad"], confianza_pais=lugar["confianza"],
                   nota_pais=lugar["nota"], paises_mundo=lugar["paises_mundo"],
                   alcance_mundial=lugar["alcance_mundial"], zona_utc=lugar["zona_utc"], ubicacion=ubicacion,
                   _descripcion=trabajo()["_descripcion"] + " " + descripcion)


def test_vive_en_alemania_recibe_la_presencial_de_berlin():
    berlin = _vacante_texto("Berlin, Germany (On-site)")
    assert berlin["paises"] == [] and berlin["paises_mundo"] == ["DE"]
    en_berlin = {"modalidades": ["presencial"], "ciudades": ["Berlin"]}  # v49: presencial exige la ciudad
    assert afinidad.evaluar(berlin, _perfil_mundo(vive_en="DE", **en_berlin), hoy())["compatible"]
    assert not afinidad.evaluar(berlin, _perfil_mundo(vive_en="DE", modalidades=["presencial"]), hoy())["compatible"]
    assert not afinidad.evaluar(berlin, _perfil_mundo(modalidades=["presencial"], ciudades=["Bogotá"]), hoy())["compatible"]
    # Se mudaría a Alemania aunque viva en Colombia.
    assert afinidad.evaluar(berlin, _perfil_mundo(paises_presenciales_extra=["DE"], **en_berlin), hoy())["compatible"]


def test_permiso_legal_recibe_la_remota_restringida_a_ese_pais():
    solo_us = _vacante_texto("Remote", "Candidates must reside in the US.")
    assert not afinidad.evaluar(solo_us, _perfil_mundo(), hoy())["compatible"]
    assert afinidad.evaluar(solo_us, _perfil_mundo(puede_trabajar_en=["US"]), hoy())["compatible"]


def test_vive_fuera_de_latam_recibe_las_remotas_mundiales():
    mundial = _vacante_texto("Remote - Worldwide")
    assert afinidad.evaluar(mundial, _perfil_mundo(vive_en="AU"), hoy())["compatible"]
    assert not afinidad.evaluar(_vacante_texto("Remote - LATAM"), _perfil_mundo(vive_en="AU"), hoy())["compatible"]


def test_horario_compatible_solo_si_el_perfil_acepta_esa_zona():
    est = _vacante_texto("Remote", "You must overlap with EST hours.")
    assert est["zona_utc"] == [-7, -3] and est["confianza_pais"] == "baja"
    # Vive en España (UTC+1): no le sirve salvo que acepte el horario del Este de EE. UU.
    assert not afinidad.evaluar(est, _perfil_mundo(vive_en="ES"), hoy())["compatible"]
    r = afinidad.evaluar(est, _perfil_mundo(vive_en="ES", acepta_horario=["us_este"]), hoy())
    assert r["compatible"] and "Remota con horario compatible" in r["pruebas"]
    # Contrato v49 (decisión de Oscar): la zona del país donde vive ya no cuenta sola; hay que marcar el horario.
    assert not afinidad.evaluar(est, _perfil_mundo(), hoy())["compatible"]
    assert afinidad.evaluar(est, _perfil_mundo(acepta_horario=["UTC-5"]), hoy())["compatible"]


def test_ciudades_exigen_que_el_aviso_nombre_la_suya():
    p = _perfil_mundo(modalidades=["presencial"], ciudades=["Medellín"])
    assert not afinidad.evaluar(_vacante_texto("Bogotá, Colombia (On-site)"), p, hoy())["compatible"]
    assert afinidad.evaluar(_vacante_texto("Medellín, Antioquia, Colombia (On-site)"), p, hoy())["compatible"]
    # Contrato v49: un aviso presencial que no dice ciudad ya no pasa («exigir ciudad»).
    sin_ciudad = afinidad.evaluar(_vacante_texto("Colombia (On-site)"), p, hoy())
    assert not sin_ciudad["compatible"] and sin_ciudad["motivos"] == ["oficina sin ciudad confirmada"]


def test_vacantes_sin_campos_del_mundo_siguen_igual():
    vieja = trabajo(paises=["CO"])
    for k in ("paises_mundo", "alcance_mundial", "zona_utc"):
        vieja.pop(k, None)
    assert afinidad.evaluar(vieja, _perfil_mundo(), hoy())["compatible"]
    assert not afinidad.evaluar(vieja, _perfil_mundo(vive_en="MX"), hoy())["compatible"]


def test_residencia_de_cualquier_pais_y_paises_validos():
    assert _perfil_mundo(vive_en="DE").vive_en == "DE"
    with pytest.raises(ValidationError):
        _perfil_mundo(vive_en="XX")
    with pytest.raises(ValidationError):
        _perfil_mundo(puede_trabajar_en=["ZZ"])


# ── Contrato v24: búsqueda por perfil, ciudades con mudanza y admisión de países objetivo ───────────────────────

def test_lugares_de_busqueda_en_ingles_y_por_ciudad():
    p = _perfil_mundo(vive_en="DE", modalidades=["remoto", "presencial"], ciudades=["Madrid, España"])
    lugares = ejecutor.lugares_perfil(p)
    assert lugares["REMOTO_DE"]["location"] == "Germany" and lugares["DE"] == {"location": "Germany"}
    assert {"location": "Madrid, España"} in lugares.values()
    # Los países propios conservan su nombre de siempre.
    assert ejecutor.lugares_perfil(_perfil_mundo())["REMOTO_CO"]["location"] == "Colombia"


def test_la_ciudad_implica_el_pais():
    p = _perfil_mundo(modalidades=["presencial"], ciudades=["Medellín", "Madrid"])
    assert afinidad.evaluar(_vacante_texto("Madrid, Spain (On-site)"), p, hoy())["compatible"]
    assert not afinidad.evaluar(_vacante_texto("Barcelona, Spain (On-site)"), p, hoy())["compatible"]
    assert not afinidad.evaluar(_vacante_texto("Bogotá, Colombia (On-site)"), p, hoy())["compatible"]


def test_admision_conserva_los_paises_objetivo_solo_en_modo_panel(monkeypatch):
    from buscador import contrato
    berlin = _vacante_texto("Berlin, Germany (On-site)")
    monkeypatch.setattr(bodega, "_config_operativa", {"paises_objetivo_mundo": ["DE"], "acepta_horario": False})
    assert bodega._sirve_a_perfiles(berlin)
    monkeypatch.setattr(bodega, "_config_operativa", {"paises_objetivo_mundo": ["US"], "acepta_horario": False})
    assert not bodega._sirve_a_perfiles(berlin)
    est = _vacante_texto("Remote", "You must overlap with EST hours.")
    monkeypatch.setattr(bodega, "_config_operativa", {"paises_objetivo_mundo": [], "acepta_horario": True})
    assert bodega._sirve_a_perfiles(est)
    # Selección: en modo heredado sigue bloqueando lo que no tiene países cubiertos; en panel decide cada perfil.
    assert contrato.entregable(berlin, panel=False) == "no se puede aplicar desde los países"
    assert contrato.entregable(berlin, panel=True) == ""
    assert contrato.entregable(est, panel=False) == "elegibilidad regional por confirmar"
    assert contrato.entregable(est, panel=True) == ""
    sin_dato = _vacante_texto("Remote")
    assert contrato.entregable(sin_dato, panel=True) == "elegibilidad regional por confirmar"


def test_objetivo_mundo_suma_residencia_mudanza_permiso_y_ciudades(cfg):
    cfg["perfiles"][0].update(vive_en="DE", paises_presenciales_extra=["CA"], puede_trabajar_en=["US"],
                              ciudades=["Lisboa, Portugal"], acepta_horario=["europa"], modalidades=["presencial"])
    objetivo, acepta = ejecutor.objetivo_mundo(Configuracion.model_validate(cfg))
    assert {"DE", "CA", "US", "PT", "CO"} <= set(objetivo) and acepta


def test_resumen_cuenta_de_que_fuente_vino_cada_entregada():
    assert entrega._fuente({"fuente": "LinkedIn", "fuentes": []}) == "LinkedIn"
    assert entrega._fuente({"fuente": "Computrabajo", "fuentes": ["Computrabajo", "LinkedIn"]}) == "LinkedIn"
    assert entrega._fuente({"fuente": "LinkedIn (Apify)"}) == "LinkedIn (Apify)"


# ── Contrato v25: título genérico, funciones y propuesta de la huella ───────────────────────────────────────────

FUNCIONES_PD = ["user research", "wireframes", "prototipos", "figma", "design system", "usabilidad", "journey maps",
                "interaccion", "accesibilidad", "sketch"]


def _con_funciones(cfg):
    cfg["cargos"][0]["funciones"] = FUNCIONES_PD
    return cfg


def test_titulo_generico_con_el_cargo_en_la_descripcion_es_similar(cfg):
    _con_funciones(cfg)
    rid = "cargo:" + cfg["cargos"][0]["id"]
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        desc = "Buscamos un Product Designer. Como Product Designer liderarás el diseño de la app."
        assert familias.clasificar("Especialista Senior", desc) == [{"familia": rid, "coincidencia": "similar"}]
        assert familias.clasificar("Especialista Senior", "Liderarás el diseño de la app.") == []


def test_coincide_por_funciones_solo_con_suficientes_y_nunca_se_entrega_solo(cfg):
    _con_funciones(cfg)
    rid = "cargo:" + cfg["cargos"][0]["id"]
    cinco = "Tareas: user research, wireframes, prototipos en Figma y pruebas de usabilidad."
    dos = "Tareas: user research y wireframes."
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        assert familias.clasificar("Experience Lead Nexo", cinco) == [{"familia": rid, "coincidencia": "funciones"}]
        assert familias.clasificar("Experience Lead Nexo", dos) == []
        v = trabajo(titulo="Experience Lead Nexo", familias=[{"familia": rid, "coincidencia": "funciones"}])
        assert entrega.roles_de(v, entrega.config()["roles"]) == ([], None)


def test_proponer_funciones_devuelve_lo_que_distingue_al_cargo():
    from panel import funciones
    del_cargo = ["Haremos user research, wireframes y prototipos en Figma con el equipo."] * 8
    otros = ["Atención a clientes, reportes semanales y coordinación con el equipo."] * 20
    propuestas = funciones.proponer(del_cargo, otros)
    assert {"user research", "wireframes", "figma"} <= set(propuestas) and "equipo" not in propuestas
    assert funciones.proponer(del_cargo[:3], otros) == []  # con menos de 5, no propone


def test_api_proponer_funciones_en_demostracion():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    r = api.post("/api/cargos/funciones", json={"nombre": "Product Designer", "terminos_exactos": ["Product Designer"],
                                                "terminos_similares": ["UX Designer"]},
                 headers={"origin": "http://testserver"})
    assert r.status_code == 200 and "user research" in r.json()["funciones"]


def test_resumen_por_cliente_cuenta_recibidas_de_los_ultimos_dias():
    """Paso 8 (variante B): recibidas de cada cliente por búsqueda, de la más antigua a la de hoy; solo conteos."""
    from collections import Counter
    from panel import servicio

    class Repo:
        def historial_ejecuciones(self, dias=7):
            return [{"id": "e3", "fecha": "2026-11-16", "estado": "en_curso"},  # mañana: no cuenta
                    {"id": "e2", "fecha": "2026-11-15", "estado": "completa"},
                    {"id": "e1", "fecha": "2026-11-14", "estado": "parcial"}]

        def asignaciones_por_cliente(self, ids):
            self.pedidas = ids
            return Counter({("e2", "c1"): 4, ("e1", "c1"): 2, ("e1", "c2"): 7})

    repo = Repo()
    r = servicio.resumen_clientes(repo, fecha="2026-11-15")
    assert repo.pedidas == ["e2", "e1"]
    assert r["busqueda_de_hoy"] is True
    assert r["dias"] == [{"fecha": "2026-11-14", "estado": "parcial", "clientes": {"c1": 2, "c2": 7}},
                         {"fecha": "2026-11-15", "estado": "completa", "clientes": {"c1": 4}}]
    assert servicio.resumen_clientes(Repo(), fecha="2026-11-17")["busqueda_de_hoy"] is False


def test_resumen_clientes_en_demo_y_por_confirmar_con_ids():
    from panel import revision
    repo = RepositorioDemo()
    api = TestClient(crear_app(demo=True, repositorio=repo))
    r = api.get("/api/resumen-clientes").json()
    assert len(r["dias"]) == 7 and r["busqueda_de_hoy"]
    activos = {c["id"] for c in configuracion_demo()["clientes"]}
    assert set(r["dias"][-1]["clientes"]) == activos
    pendientes = revision.listar(repo, r["fecha"])["pendientes"]
    assert all(set(p["cliente_ids"]) <= activos and p["cliente_ids"] for p in pendientes)


class _RepoPaginas:
    _paginas = RepositorioSupabase._paginas

    def __init__(self, filas):
        self.filas, self.pedidos = filas, []

    def pedir(self, metodo, ruta, params=None, **_):
        self.pedidos.append(params)
        return [f for f in self.filas if not params.get("id") or f["id"] > params["id"][3:]][:params["limit"]]


def test_asignaciones_por_cliente_agrupa_por_busqueda_y_cliente():
    repo = _RepoPaginas([{"id": "a1", "ejecucion_id": "e1", "cliente_id": "c1"},
                         {"id": "a2", "ejecucion_id": "e1", "cliente_id": "c1"},
                         {"id": "a3", "ejecucion_id": "e2", "cliente_id": "c2"}])
    conteo = RepositorioSupabase.asignaciones_por_cliente.__get__(repo)(["e1", "e2"])
    assert conteo == {("e1", "c1"): 2, ("e2", "c2"): 1}
    assert repo.pedidos[0]["ejecucion_id"] == "in.(e1,e2)"
    assert RepositorioSupabase.asignaciones_por_cliente.__get__(repo)([]) == {}


def test_v49_lo_que_impide_aplicar_se_explica_con_que_hacer():
    from panel.repositorio import _mensaje_sql
    for sql in ("Cada cargo necesita un perfil activo", "Las metas superan el techo diario",
                "Da una meta diaria a algún perfil antes de confirmar"):
        assert "«Aplicar cambios»" in _mensaje_sql(sql)
    assert "SQL 015" in _mensaje_sql("Reparte exactamente 120 vacantes")


def test_demo_aplicar_rige_desde_hoy_y_queda_en_uso(tmp_path):
    r = RepositorioDemo(tmp_path / "demo.json")
    cfg = r.config()["borrador"]
    cfg["clientes"][0]["nombre"] = "Cliente aplicado"
    r.guardar(r.config()["revision"], cfg)
    assert r.publicar(r.config()["revision"])["vigente_desde"] == hoy()
    # Contrato v49: lo aplicado es lo que usa «Buscar ahora» del cliente.
    assert r.operativa(hoy())["configuracion"]["clientes"][0]["nombre"] == "Cliente aplicado"
    with pytest.raises(ErrorRepositorio):
        r.publicar(r.config()["revision"] + 1)


def test_v49_ya_no_existe_aplicar_hoy():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    r = api.post("/api/config/aplicar-hoy", json={"revision": 1}, headers={"origin": "http://testserver"})
    assert r.status_code in (404, 405)
    assert not hasattr(RepositorioDemo, "publicar_hoy") and not hasattr(RepositorioSupabase, "publicar_hoy")


# ── PR 1b (16 nov): más vacantes para quien solo acepta avisos en español ─────────────────────────────────────────

def test_pr1b_perfil_solo_espanol_busca_titulos_en_espanol_en_sus_lugares(cfg):
    from buscador.fuentes import computrabajo, linkedin_publico
    cfg["perfiles"][0]["idiomas"] = ["es"]
    mapa, _, motor = ejecutor.preparar({"configuracion": cfg}, hoy())
    f = next(x for x in mapa if x["id"] == "cargo:" + cfg["perfiles"][0]["cargo_id"])
    assert f["consultas_es"] and all(ejecutor.en_espanol(t) for t in f["consultas_es"])
    assert "diseñador ux/ui" in f["consultas_es"]
    assert f["lugares_es"] and all(k != "REMOTO_MUNDO" for k, _ in f["lugares_es"])
    combos = linkedin_publico.combinaciones(mapa, [])
    espanol = [c for c in combos if c[2].endswith(":ES") and c[0] == f["id"]]
    assert espanol and all(c[1] == f["consultas_es"] for c in espanol)
    # v44: en Computrabajo el español tiene su propio turno en los países de quien solo habla español.
    ct = [c for c in computrabajo.combinaciones(mapa, {}) if c[0] == f["id"]]
    assert any(c[2].endswith(":ES") and c[1] == f["consultas_es"] for c in ct) == bool(set(f["paises_es"]) & set(computrabajo.SITIOS))
    assert motor["dias_maximos"] == afinidad.ANTIGUEDAD_SISTEMA  # v27: la antigüedad del perfil solo ordena


def test_v50_quien_acepta_espanol_e_ingles_tambien_busca_en_espanol_y_quien_solo_ingles_no(cfg):
    from buscador.fuentes import linkedin_publico
    for p in cfg["perfiles"]:
        p["idiomas"] = ["es", "en"]
    mapa, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy())
    con_espanol = [f for f in mapa if f["consultas_es"]]
    assert con_espanol and all(f["lugares_es"] and f["paises_es"] for f in con_espanol)  # antes: solo «solo español»
    assert [c for c in linkedin_publico.combinaciones(mapa, []) if c[2].endswith(":ES")]
    for p in cfg["perfiles"]:
        p["idiomas"] = ["en"]
    mapa, _, _ = ejecutor.preparar({"configuracion": cfg}, hoy())
    assert all(not f["consultas_es"] and not f["lugares_es"] for f in mapa)
    assert not [c for c in linkedin_publico.combinaciones(mapa, []) if c[2].endswith(":ES")]


@pytest.mark.parametrize("titulo,es", [("Product Manager IA", True), ("Jefe de QA", True), ("Diseñadora UX", True),
                                       ("Product Designer", False), ("QA Lead", False)])
def test_pr1b_reconoce_titulos_en_espanol(titulo, es):
    assert ejecutor.en_espanol(titulo) is es
