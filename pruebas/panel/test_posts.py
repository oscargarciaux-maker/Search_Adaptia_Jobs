"""Contrato v11 (segunda parte): posts de LinkedIn etiquetados «Post» para completar hasta 5, sin basura."""
from datetime import date, timedelta

import pytest

from buscador import apify, catalogo, contrato, entrega, familias, refuerzo, vacante
from buscador.fuentes import publicaciones_apify as pa
from panel import borradores, ejecutor
from panel.repositorio import configuracion_demo, hoy

VALIDAS = {"diseno-producto-ux", "qa"}
PERFIL = "https://www.linkedin.com/in/reclutadora-ejemplo"


def _post(texto, **extra):
    item = {"linkedinUrl": "https://www.linkedin.com/posts/reclutadora_hiring-activity-7391234567890123456-abcd",
            "content": texto, "postedAt": {"date": hoy() + "T10:00:00.000Z"},
            "author": {"name": "Ana Pérez", "info": "Talent Acquisition at Rappi", "type": "profile", "linkedinUrl": PERFIL}}
    item.update(extra)
    return item


BUENO = ("¡Estamos contratando! Buscamos Product Designer para trabajar 100% remoto desde Colombia o México. "
         "Experiencia con Figma y design systems. Si te interesa, envíame tu CV por DM o a talento@example.com")


# ── Filtro estricto contra posts basura ────────────────────────────────────────────────────────────────────────────

def test_post_de_contratacion_real_pasa_y_trae_contacto():
    v, motivo = pa.a_vacante(_post(BUENO), VALIDAS, hoy())
    assert motivo == "" and v["titulo"] == "Product Designer" and v["empresa"] == "Rappi"
    assert v["contacto"] == {"perfil": PERFIL, "correo": "talento@example.com"}


@pytest.mark.parametrize("texto, motivo", [
    # Personas que buscan empleo
    ("#OpenToWork Soy Product Designer y estoy buscando trabajo remoto en Colombia. Escríbeme.", "busca empleo, curso o evento"),
    ("Me encuentro en búsqueda de nuevas oportunidades como Product Designer, remoto desde México. Contáctame.",
     "busca empleo, curso o evento"),
    ("I'm open to new opportunities as a Product Designer, remote from Colombia. DM me.", "busca empleo, curso o evento"),
    # Cursos, eventos
    ("Webinar gratis: cómo ser Product Designer. Buscamos asistentes de Colombia, remoto. Inscríbete en el link.",
     "busca empleo, curso o evento"),
    # Base de datos / a futuro
    ("Estamos buscando Product Designer para nuestro banco de talento, remoto en Colombia. Envía tu CV.",
     "banco de talento o vacante a futuro"),
    ("Buscamos Product Designer remoto en México para futuras oportunidades. Te contactaremos. Envía tu CV.",
     "banco de talento o vacante a futuro"),
    ("Join our talent community! We are hiring Product Designer roles, remote LATAM. Send your CV.",
     "banco de talento o vacante a futuro"),
    # Empresa que menciona el cargo sin contratar
    ("Hoy nuestro equipo de Product Designer en Colombia celebró 5 años creando productos remotos.",
     "no anuncia una contratación"),
    ("We're hiring a Product Designer remote in LATAM and we are so proud of the team growing fast.",
     "no pide postular ni escribir"),
])
def test_posts_basura_rechazados(texto, motivo):
    assert pa.a_vacante(_post(texto), VALIDAS, hoy()) == (None, motivo)


def test_lista_de_vacantes_de_terceros_y_post_viejo_rechazados():
    lista = BUENO + " https://a.example/1 https://b.example/2 https://c.example/3 https://d.example/4"
    assert pa.a_vacante(_post(lista), VALIDAS, hoy())[1] == "lista de vacantes de terceros"
    viejo = (date.fromisoformat(hoy()) - timedelta(days=40)).isoformat()
    assert pa.a_vacante(_post(BUENO, postedAt={"date": viejo}), VALIDAS, hoy())[1] == "fuera del plazo"
    reclutador_buscando = _post(BUENO, author={"name": "X", "info": "Product Designer | Open to work", "type": "profile",
                                               "linkedinUrl": PERFIL})
    assert pa.a_vacante(reclutador_buscando, VALIDAS, hoy())[1] == "busca empleo, curso o evento"


# ── Post etiquetado: nunca cupo ni `ofertas` ───────────────────────────────────────────────────────────────────────

def _registro(texto=BUENO, contacto=None):
    v, _ = pa.a_vacante(_post(texto), VALIDAS, hoy())
    return vacante.crear_post(v["titulo"], v["empresa"], v["enlace"], v["ubicacion"], v["descripcion"], v["fecha"],
                              v["remoto"], v["contacto"] if contacto is None else contacto, hoy())


def test_post_sin_ficha_queda_etiquetado_y_fuera_de_ofertas():
    p = _registro()
    assert p["tipo"] == "post" and p["id"].startswith("post-") and contrato.entregable_post(p) == ""
    assert contrato.entregable(p) == "post de LinkedIn: no es una oferta formal"  # nunca a `ofertas` ni al cupo
    datos = catalogo.fila(p, p["vista_en"])["datos"]
    assert datos["tipo"] == "post" and datos["contacto"]["perfil"] == PERFIL
    assert contrato.entregable_post(_registro(contacto={})) == "sin forma de contacto"
    normal = vacante.crear("Product Designer", "A", "https://jobs.lever.co/a/1", "Lever", descripcion=BUENO * 3, hoy=hoy())
    assert "tipo" not in vacante.publica(normal)  # el resto del catálogo no cambia de huella


def test_post_no_entra_a_la_seleccion_del_cupo():
    p = _registro()
    p["familias"] = familias.clasificar(p["titulo"], p["_descripcion"])
    elegidas, _ = entrega.elegir([p], {}, hoy())
    assert not any(v["id"] == p["id"] for lista in elegidas.values() for v, _ in lista)


class ClientePosts:
    def __init__(self, items, ficha=None):
        self.items, self.ficha, self.cargos = items, ficha, []

    def post_json(self, url, cuerpo, headers=None, timeout=None):
        self.cargos.append(url)
        return {"data": {"id": "run", "status": "SUCCEEDED", "defaultDatasetId": "d"}}

    def json(self, *a, **k):
        return self.items

    def get(self, url, **op):
        if self.ficha is None:
            return None
        return type("R", (), {"status_code": 200, "text": self.ficha})()


def test_buscar_posts_separa_fichas_formales_y_posts():
    ficha = ('<h1>Product Designer</h1><a class="topcard__org-name-link">Rappi</a>'
             '<span class="topcard__flavor--bullet">Remote - LATAM</span>'
             '<div class="show-more-less-html__markup">' + BUENO * 3 + '</div>')
    con_ficha = _post(BUENO + " https://www.linkedin.com/jobs/view/1234567890/")
    formales, posts, stats = pa.buscar_posts(ClientePosts([con_ficha], ficha), "harvestapi/linkedin-post-search",
                                             ["q"], VALIDAS, hoy(), token="ficticio",
                                             control_gasto=apify.Presupuesto({}, hoy()))
    assert len(formales) == 1 and "/jobs/view/" in formales[0]["enlace"] and posts == []
    formales, posts, stats = pa.buscar_posts(ClientePosts([_post(BUENO), _post("#opentowork busco trabajo")]),
                                             "harvestapi/linkedin-post-search", ["q"], VALIDAS, hoy(),
                                             token="ficticio", control_gasto=apify.Presupuesto({}, hoy()))
    assert formales == [] and len(posts) == 1 and stats["descartadas"] == {"busca empleo, curso o evento": 1}
    assert "Ana" not in str(stats) and "@" not in str(stats)  # salud.json: solo conteos


def test_buscar_posts_respeta_el_tope_de_apify():
    agotado = apify.Presupuesto({"mes": hoy()[:7], "reservas": {hoy(): 5}}, hoy())
    cliente = ClientePosts([_post(BUENO)])
    assert pa.buscar_posts(cliente, "actor", ["q"], VALIDAS, hoy(), token="t", control_gasto=agotado)[2] == \
        {"omitida": "presupuesto de Apify agotado"}
    assert cliente.cargos == []
    cliente = ClientePosts([_post(BUENO)])
    pa.buscar_posts(cliente, "actor", ["q"], VALIDAS, hoy(), maximo=30, token="t", control_gasto=apify.Presupuesto({}, hoy()))
    assert "maxTotalChargeUsd=0.07" in cliente.cargos[0]  # 30 posts ≈ USD 0,06 + margen, dentro del día


# ── Solo para perfiles con déficit ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def cfg():
    c = configuracion_demo()
    for p in c["perfiles"][1:3]:
        p["activo"] = False
    return c


def test_rescate_de_posts_solo_si_falta_y_con_el_cargo(cfg):
    llamadas = []

    def buscar_posts(consultas, validas):
        llamadas.append((consultas, validas))
        return [], [], {"publicaciones": 0}
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        _, stats, posts = refuerzo.rescate_posts([], {}, hoy(), entrega.config(), familias.mapa(), buscar_posts,
                                                 lambda a, b: a + b)
    assert stats["perfiles_con_deficit"] >= 1 and posts == []
    consultas, validas = llamadas[0]
    assert len(consultas) <= 6 and all(q.startswith("(hiring OR contratando") for q in consultas)
    assert any("Product Designer".lower() in q.lower() for q in consultas)


def test_registrar_asigna_posts_solo_hasta_cinco_y_sin_repetir(cfg):
    p = cfg["perfiles"][0]
    rid = "cargo:" + cfg["cargos"][0]["id"]
    with ejecutor.activar({"configuracion": cfg}, hoy()):
        formal = vacante.crear("Product Designer", "Lumen", "https://jobs.lever.co/lumen/1", "Lever",
                               ubicacion="Remote - Worldwide", descripcion=("We require 3 years of experience. "
                               "English B2 required. We design digital products with research. ") * 4,
                               fecha=hoy(), hoy=hoy(), remoto=True)
        posts = []
        for n in range(6):
            texto = BUENO.replace("Product Designer", "Product Designer") + f" Referencia {n}."
            item = _post(texto, linkedinUrl=f"https://www.linkedin.com/posts/r_hiring-activity-73912345678901234{n:02d}")
            item["author"] = dict(item["author"], info=f"Talent Acquisition at Empresa {n}")
            v, _ = pa.a_vacante(item, {f["id"] for f in familias.mapa()}, hoy())
            posts.append(vacante.crear_post(v["titulo"], v["empresa"], v["enlace"], v["ubicacion"], v["descripcion"],
                                            v["fecha"], v["remoto"], v["contacto"], hoy()))
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
            if ruta == "entregas_diarias":
                return [{"vacante_id": formal["id"], "delivery_date": hoy(), "role_id": rid, "match_grade": "exact",
                         "snapshot": formal}] if params.get("delivery_date", "").startswith("eq.") else []
            if ruta == "catalogo_vacantes":
                assert params["datos->>tipo"] == "eq.post"
                return filas_catalogo
            if ruta == "panel_asignaciones":
                if metodo == "GET":  # ya recibió el primer post otro día
                    return [{"perfil_id": p["id"], "vacante_id": posts[0]["id"]}]
                asignaciones.extend(op["json"])
            return []
    repo = Repo()
    ejecutor.registrar(repo, {"revision": 1, "configuracion": cfg}, hoy())
    mias = [a for a in asignaciones if a["perfil_id"] == p["id"]]
    con_post = [a for a in mias if {"tipo": "post"} in a["explicacion"]]
    assert len(mias) == 5 and len(con_post) == 4  # 1 formal + 4 posts: solo hasta completar 5
    assert posts[0]["id"] not in {a["vacante_id"] for a in mias}
    assert repo.ejecucion["resumen"]["posts"] == 4 and repo.ejecucion["resumen"]["vacantes"] == 1  # fuera del cupo


# ── WhatsApp ───────────────────────────────────────────────────────────────────────────────────────────────────────

def _v(i, tipo=""):
    return {"id": str(i), "titulo": f"Cargo {i}", "empresa": f"Empresa {i}", "modalidad": "remoto",
            "enlace": f"https://example.org/{i}", "tipo": tipo,
            "contacto": {"perfil": PERFIL, "correo": "rrhh@example.org"} if tipo else {}}


def test_whatsapp_etiqueta_posts_al_final_y_solo_completan():
    lista = borradores.con_posts([_v(1, "post"), _v(2), _v(3, "post"), _v(4), _v(5, "post"), _v(6, "post")])
    assert [v["id"] for v in lista] == ["2", "4", "1", "3", "5"]
    assert borradores.con_posts([_v(i) for i in range(6)] + [_v(9, "post")]) == [_v(i) for i in range(6)]
    texto = borradores.texto("Ana", [("Product Designer", lista)], hoy(), "c1")
    assert texto.index("Cargo 4") < texto.index("📣 Post · Cargo 1 · Empresa 1")
    assert "Escríbele por mensaje a quien publicó: https://example.org/1" in texto
    assert "O al correo: rrhh@example.org" in texto and borradores.NOTA_POSTS in texto
    assert borradores.NOTA_POSTS not in borradores.texto("Ana", [("QA", [_v(2)])], hoy(), "c1")
