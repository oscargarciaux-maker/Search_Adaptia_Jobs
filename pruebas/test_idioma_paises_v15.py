"""Contrato v15: solo español o inglés con evidencia; todos los países del mundo reconocidos desde la tabla oficial."""
import pytest
import yaml

from buscador import etiquetas, normalizar, paises

# ── Idioma ─────────────────────────────────────────────────────────────────────────────────────────────────────────
NO_PASAN = {
    "neerlandés": "Wij zoeken een Product Designer voor ons team in Amsterdam. Je werkt samen met de product owner en "
                  "is verantwoordelijk voor het ontwerp van onze app. Ervaring met Figma is een pre.",
    "turco": "Ekibimize Product Designer arıyoruz. Figma deneyimi ve ürün ekibiyle çalışma becerisi gereklidir. "
             "Kullanıcı araştırması yapacak ve prototip hazırlayacaksınız. Esnek çalışma saatleri sunuyoruz.",
    "polaco": "Szukamy Product Designera do naszego zespołu w Warszawie. Będziesz odpowiedzialny za projektowanie i "
              "współpracę z zespołem produktowym. Doświadczenie z Figma jest wymagane.",
    "polaco con requisitos en inglés": "Szukamy Product Designera do naszego zespołu w Warszawie. Będziesz "
              "odpowiedzialny za projektowanie i współpracę z zespołem produktowym. Requirements: Figma, team player.",
    "sueco": "Vi söker en Product Designer till vårt team i Stockholm. Du kommer att arbeta med produktteamet och "
             "ansvara för design. Erfarenhet av Figma är meriterande.",
    "danés": "Vi søger en Product Designer til vores team i København. Du vil arbejde med produktteamet og har "
             "erfaring med Figma. Det er ikke et krav.",
    "rumano": "Căutăm un Product Designer pentru echipa noastră din București. Vei lucra cu echipa de produs și vei fi "
              "responsabil pentru design. Experiența cu Figma este necesară.",
    "indonesio": "Kami mencari Product Designer untuk tim kami di Jakarta. Anda akan bekerja dengan tim produk dan "
                 "bertanggung jawab atas desain. Pengalaman dengan Figma diperlukan.",
    "vietnamita": "Chúng tôi đang tìm kiếm Product Designer cho đội ngũ tại Hà Nội. Bạn sẽ làm việc với đội sản phẩm "
                  "và chịu trách nhiệm thiết kế. Kinh nghiệm với Figma.",
    "checo": "Hledáme Product Designera do našeho týmu v Praze. Budete pracovat s produktovým týmem a máte "
             "zkušenosti s Figmou. Je to práce pro vás.",
    "húngaro": "Product Designert keresünk a budapesti csapatunkba. A munka során a termékcsapattal dolgozol, és "
               "tapasztalat szükséges a Figma terén. Nem kötelező, hogy legyen egy portfólió.",
    "francés": "Nous recherchons un Product Designer pour rejoindre notre équipe à Paris. Vous serez responsable des "
               "parcours utilisateurs et des prototypes avec les équipes produit.",
    "alemán": "Wir suchen eine Product Designerin für unser Team in Berlin. Ihre Aufgaben sind die Gestaltung und die "
              "Zusammenarbeit mit der Produktentwicklung und Erfahrung mit Figma.",
    "italiano": "Siamo alla ricerca di un Product Designer per il nostro team di Milano. Il candidato ideale ha "
                "esperienza con Figma e conoscenza delle metodologie agili.",
    "portugués": "Estamos buscando um(a) Product Designer para atuar na nossa equipe. Você será responsável por "
                 "pesquisas com usuários e protótipos. Requisitos: experiência com Figma.",
    "japonés": "プロダクトデザイナーを募集しています。チームと協力してUXを改善します。",
    "coreano": "프로덕트 디자이너를 모집합니다. 팀과 함께 사용자 경험을 개선합니다.",
}


@pytest.mark.parametrize("idioma", list(NO_PASAN))
def test_otros_idiomas_nunca_pasan(idioma):
    assert etiquetas.idioma("Product Designer\n" + NO_PASAN[idioma]) not in ("es", "en")


@pytest.mark.parametrize("texto, esperado", [
    ("Buscamos un Product Designer para nuestro equipo en Bogotá. Funciones: diseñar flujos y prototipos con el "
     "equipo de producto, y trabajar con usuarios.", "es"),
    ("We are looking for a Product Designer to join our team. You will design flows and prototypes with the product "
     "team and work with users.", "en"),
    ("¡Estamos contratando! Buscamos Product Designer remoto desde Colombia. Envía tu CV a talento@example.com", "es"),
])
def test_espanol_e_ingles_pasan(texto, esperado):
    assert etiquetas.idioma(texto) == esperado


def test_bilingue_espanol_ingles_pasa():
    texto = ("About the role: we are looking for a QA Engineer to join our team and work with the product owner. "
             "Sobre el puesto: buscamos una persona con experiencia en pruebas automatizadas para nuestro equipo.")
    assert etiquetas.idioma(texto) in ("es", "en")


# ── Países ─────────────────────────────────────────────────────────────────────────────────────────────────────────
MUNDO = yaml.safe_load(paises.RUTA_MUNDO.read_text(encoding="utf-8"))["paises"]
CUBIERTOS = paises.datos()["codigos"]
PROPIOS = set(paises.datos()["reconocidos"])


@pytest.mark.parametrize("codigo", CUBIERTOS)
def test_cada_pais_cubierto_por_sigla_y_nombre(codigo):
    fila = next(m for m in MUNDO if m["iso2"] == codigo)
    nombre = next(p["nombre"] for p in paises.datos()["paises"] if p["codigo"] == codigo)
    # «Remote - CO» puede ser Colorado (empresas de EE. UU.): AR, CO y PA tras una palabra quedan por confirmar.
    tras_palabra = [] if codigo in ("AR", "CO", "PA") else [f"Remote - {codigo}"]
    for ubicacion in (codigo, f"{codigo} {codigo}", *tras_palabra, f"Oficina central, {fila['iso3']}",
                      f"Remote - {fila['iso3']}", nombre):
        r = paises.elegibles("QA", ubicacion, "", True)
        assert r["paises"] == [codigo] and r["confianza"] in ("alta", "media"), (ubicacion, r)


@pytest.mark.parametrize("fila", [m for m in MUNDO if m["iso2"] not in PROPIOS], ids=lambda m: m["iso2"])
def test_ningun_pais_extranjero_se_acepta(fila):
    for ubicacion in [*fila["nombres"][:3], fila["iso2"], f"Remote - {fila['iso3']}"]:
        r = paises.elegibles("QA", ubicacion, "", True)
        assert not (r["paises"] and r["confianza"] in ("alta", "media") and set(r["paises"]) != set(CUBIERTOS)), \
            (ubicacion, r)  # nunca un país cubierto concreto; «todos con confianza baja» es «por confirmar»


@pytest.mark.parametrize("codigo", CUBIERTOS)
def test_provincias_de_paises_cubiertos_no_son_extranjeras(codigo):
    fila = next(m for m in MUNDO if m["iso2"] == codigo)
    d = paises.datos()
    curadas = {normalizar.texto(c) for p in d["paises"] for c in p["ciudades"]}
    for sub in fila.get("subdivisiones", []):
        if sub in d["ambiguas"] or sub in d["palabras_comunes"]:
            continue
        r = paises.elegibles("QA", sub, "", None)
        assert r["paises"] != [] or r["confianza"] == "baja", (sub, r)  # nunca extranjera
        if sub not in curadas:  # una ciudad elegida a mano (Córdoba, La Paz…) gana a la provincia homónima de otro país
            assert not (r["paises"] and set(r["paises"]) != {codigo} and r["confianza"] != "baja"), (sub, r)


@pytest.mark.parametrize("ubicacion, esperado", [
    ("Quito, EC", ["EC"]), ("Remote - UY", ["UY"]), ("Lima, PER", ["PE"]), ("Asunción, PY", ["PY"]),
    ("Pichincha", ["EC"]), ("Antioquia", ["CO"]), ("Guayaquil, Guayas", ["EC"]), ("Jalisco, México", ["MX"]),
    ("Panamá, PA", ["PA"]), ("New Mexico", []), ("Albuquerque, Nuevo México, Estados Unidos", []),
    ("Texas", []), ("Bayern", []), ("Puerto Rico", ["PR"]),
])
def test_casos_conocidos(ubicacion, esperado):
    assert paises.elegibles("QA", ubicacion, "", None)["paises"] == esperado


@pytest.mark.parametrize("ubicacion", ["Córdoba", "Bolívar", "Granada", "Valencia", "Santa Cruz", "Conshohocken, PA"])
def test_ambiguas_quedan_por_confirmar(ubicacion):
    assert paises.elegibles("QA", ubicacion, "", None)["confianza"] == "baja"


def test_palabra_comun_en_la_descripcion_no_es_provincia_extranjera():
    desc = "Nos importa no solo los resultados sino en como los alcanzamos. Buscamos personas en Buenos Aires."
    assert paises.elegibles("Analyst", "Buenos Aires, B, Argentina", desc)["paises"] == ["AR"]


def test_tabla_oficial_completa():
    assert len(MUNDO) >= 249 and {m["iso2"] for m in MUNDO} >= PROPIOS
    assert all(normalizar.texto(n) == n for m in MUNDO for n in m["nombres"])
