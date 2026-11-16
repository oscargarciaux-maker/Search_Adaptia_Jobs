"""Contrato v28 (16 nov): posts con más fuerza. Sin IA: pistas de ubicación por reglas y posts sin pistas marcados."""
from buscador import catalogo, contrato, familias, vacante
from buscador.fuentes import publicaciones_apify as pa
from panel import afinidad, borradores, ejecutor
from panel.repositorio import hoy
import pytest

from panel.repositorio import configuracion_demo
from pruebas.panel.test_posts import PERFIL, VALIDAS, _post


@pytest.fixture
def cfg():
    c = configuracion_demo()
    for p in c["perfiles"][1:3]:
        p["activo"] = False
    return c

SIN_LUGAR = ("¡Estamos contratando! Buscamos Product Designer con experiencia en Figma y design systems para nuestro "
             "equipo de producto. Si te interesa, envíame tu CV por DM.")


def test_pistas_de_ubicacion_por_reglas():
    assert pa.pistas_ubicacion("Escríbeme al +57 300 123 4567") == (["CO"], "prefijo telefónico +57")
    assert pa.pistas_ubicacion("Llámanos: +593 99 123 4567")[0] == ["EC"]  # el prefijo más largo gana
    assert pa.pistas_ubicacion("+1 555 123 4567") == ([], "")                # +1 es ambiguo
    assert pa.pistas_ubicacion("Salario 5.000.000 COP")[0] == ["CO"]
    assert pa.pistas_ubicacion("pago en pesos mexicanos")[0] == ["MX"]
    assert pa.pistas_ubicacion("Postula en https://empresa.com.mx/empleos")[0] == ["MX"]
    assert pa.pistas_ubicacion("Postula en https://startup.co/jobs") == ([], "")          # .co solo es ambiguo
    assert pa.pistas_ubicacion("x", {"author": {"location": "Lima, Perú"}})[0] == ["PE"]
    assert pa.pistas_ubicacion("x", empresa="Rappi", empresas_pais={"rappi": "CO"})[1].startswith("país de las otras")


def test_paises_por_empresa_solo_con_un_pais_confirmado():
    vs = [{"empresa": "Rappi", "paises": ["CO"], "confianza_pais": "alta"},
          {"empresa": "Rappi", "paises": ["CO"], "confianza_pais": "alta"},
          {"empresa": "Globant", "paises": ["AR"], "confianza_pais": "alta"},
          {"empresa": "Globant", "paises": ["CO"], "confianza_pais": "alta"},
          {"empresa": "Dudosa", "paises": ["MX"], "confianza_pais": "baja"}]
    assert pa.paises_por_empresa(vs) == {"rappi": "CO"}


def test_post_con_pista_queda_deducido_y_sin_pista_queda_marcado():
    con_pista, _ = pa.a_vacante(_post(SIN_LUGAR + " WhatsApp +57 310 000 0000"), VALIDAS, hoy())
    assert con_pista["ubicacion"] == "Colombia" and con_pista["ubicacion_deducida"] == "prefijo telefónico +57"
    sin_pista, motivo = pa.a_vacante(_post(SIN_LUGAR), VALIDAS, hoy())
    assert motivo == "" and sin_pista["ubicacion_sin_confirmar"] and sin_pista["ubicacion"] == ""


def test_post_sin_pistas_es_entregable_pero_no_uno_dudoso_con_pais():
    v, _ = pa.a_vacante(_post(SIN_LUGAR), VALIDAS, hoy())
    post = vacante.crear_post(v["titulo"], v["empresa"], v["enlace"], v["ubicacion"], v["descripcion"], v["fecha"],
                              v["remoto"], v["contacto"], hoy())
    assert contrato.entregable_post(post) == "elegibilidad regional por confirmar"
    post["ubicacion_sin_confirmar"] = True
    assert contrato.entregable_post(post) == ""
    assert afinidad.post_ubicacion(post) == "sin_confirmar"


def test_ficha_enlazada_da_la_ubicacion():
    html = ('<script type="application/ld+json">{"@type":"JobPosting","title":"Product Designer",'
            '"jobLocation":{"address":{"addressLocality":"Bogotá","addressCountry":"CO"}}}</script>')
    pedidos = []
    def obtener(url):
        pedidos.append(url)
        return html
    texto = ("Postula aquí http://169.254.169.254/latest https://sitio-cualquiera.example/x "
             "https://jobs.lever.co/acme/1 o en https://www.linkedin.com/jobs/view/1")
    assert pa.ubicacion_en_enlaces(texto, "Product Designer", obtener=obtener) == ("Bogotá, CO", None)
    # Solo dominios de la lista fija: ni direcciones internas ni sitios arbitrarios; LinkedIn lo resuelve otra función.
    assert pedidos == ["https://jobs.lever.co/acme/1"]


def test_lectura_acotada_corta_descargas_grandes_y_dominios_desconocidos():
    class Respuesta:
        status_code, headers, encoding = 200, {}, "utf-8"
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def iter_content(self, n): return iter([b"x" * 600_000, b"y" * 600_000])
    class Sesion:
        def get(self, *a, **k): return Respuesta()
    import buscador.verificar_enlaces as ve
    original = ve.publica
    ve.publica = lambda url: True
    try:
        assert pa._leer_acotado("https://jobs.lever.co/acme/1", Sesion()) is None  # pasa de 1 MB
        assert pa._leer_acotado("https://sitio-cualquiera.example/x", Sesion()) is None
    finally:
        ve.publica = original


def test_consultas_con_lugar_de_quien_va_corto():
    q = pa.consultas_post(["Product Designer", "UX Designer"], lugares=["Colombia", "remoto"])
    assert q[-2:] == ['(hiring OR contratando OR buscamos) "Product Designer" Colombia',
                      '(hiring OR contratando OR buscamos) "Product Designer" remoto']


def test_whatsapp_avisa_la_ubicacion_del_post():
    v = {"titulo": "Product Designer", "empresa": "Acme", "tipo": "post", "enlace": PERFIL, "contacto": {},
         "post_ubicacion": "sin_confirmar"}
    assert "no dice dónde es" in borradores._linea(1, v)
    assert "ubicación deducida" in borradores._linea(1, dict(v, post_ubicacion="deducida"))


def test_registrar_da_posts_sin_confirmar_solo_hasta_dos_y_marcados(cfg):
    p = cfg["perfiles"][0]
    p["modalidades"] = ["remoto"]
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        posts = []
        for n in range(4):
            item = _post(SIN_LUGAR + f" Referencia {n}.",
                         linkedinUrl=f"https://www.linkedin.com/posts/r_hiring-activity-73912345678901234{n:02d}")
            item["author"] = dict(item["author"], info=f"Talent Acquisition at Empresa {n}")
            v, _ = pa.a_vacante(item, {f["id"] for f in familias.mapa()}, hoy())
            post = vacante.crear_post(v["titulo"], v["empresa"], v["enlace"], v["ubicacion"], v["descripcion"],
                                      v["fecha"], v["remoto"], v["contacto"], hoy())
            post.update(ubicacion_sin_confirmar=True, ubicacion_deducida="")
            posts.append(post)
    filas_catalogo = [catalogo.fila(x, x["vista_en"]) for x in posts]
    asignaciones = []

    class Repo:
        ejecucion = None

        def pedir(self, metodo, ruta, **op):
            params = op.get("params") or {}
            if params.get("offset"):
                return []
            if ruta == "panel_ejecuciones":
                if metodo == "POST":
                    self.ejecucion = {"id": "e1", **op["json"]}
                elif metodo == "PATCH":
                    self.ejecucion.update(op["json"])
                return [self.ejecucion] if self.ejecucion else []
            if ruta == "catalogo_vacantes":
                return filas_catalogo
            if ruta == "panel_asignaciones" and metodo == "POST":
                asignaciones.extend(op["json"])
            return []
    ejecutor.registrar(Repo(), {"revision": 1, "configuracion": cfg}, hoy())
    mias = [a for a in asignaciones if a["perfil_id"] == p["id"]]
    assert len(mias) == 2  # tope diario de «sin confirmar» aunque vaya bajo 5
    assert all({"post_ubicacion": "sin_confirmar", "pista": ""} in a["explicacion"] for a in mias)
