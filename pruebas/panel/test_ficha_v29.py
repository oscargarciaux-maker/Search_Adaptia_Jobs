"""Contrato v29: ficha de una vacante, «Por confirmar» por páginas y copias cortas de resultados."""
import json

import pytest
from fastapi.testclient import TestClient

from buscador import ficha
from panel import revision, servicio
from panel.api import crear_app
from panel.repositorio import ErrorRepositorio, RepositorioDemo, configuracion_demo, hoy


def _html(descripcion, titulo="Product Designer"):
    datos = {"@context": "https://schema.org", "@type": "JobPosting", "title": titulo, "description": descripcion}
    return f'<html><script type="application/ld+json">{json.dumps(datos)}</script><body>Otra cosa</body></html>'


def test_bloques_con_formato_y_sin_html():
    texto = ficha.a_texto("<p>Somos un equipo.</p><h3>Requisitos</h3><ul><li>Figma</li><li>Inglés <b>B2</b></li></ul>"
                          "<script>alert(1)</script>")
    assert "alert" not in texto
    b = ficha.bloques(texto)
    assert b == [{"tipo": "p", "texto": "Somos un equipo."}, {"tipo": "h", "texto": "Requisitos"},
                 {"tipo": "li", "texto": "Figma"}, {"tipo": "li", "texto": "Inglés **B2**"}]
    plano = ficha.bloques("Responsabilidades:\n- Diseñar\n• Probar\n1. Medir\n\nTexto largo del aviso.")
    assert [x["tipo"] for x in plano] == ["h", "li", "li", "li", "p"]
    assert all("<" not in x["texto"] for x in b + plano)


def test_descripcion_del_jobposting_y_lista_fija_de_dominios():
    html = _html("<p>Diseñarás productos.</p><ul><li>Figma</li></ul>")
    assert ficha.descripcion_jobposting(html, "Product Designer") == "Diseñarás productos.\n\n- Figma"
    pedidas = []

    def obtener(url):
        pedidas.append(url)
        return html
    # Un sitio fuera de la lista fija nunca se lee (evita SSRF y descargas de sitios arbitrarios).
    assert ficha.traer_descripcion(["https://sitio-cualquiera.example/x"], "Product Designer", obtener) == ""
    assert pedidas == []
    texto = ficha.traer_descripcion(["https://sitio-cualquiera.example/x", "https://jobs.lever.co/acme/1"],
                                    "Product Designer", obtener)
    assert "Figma" in texto and pedidas == ["https://jobs.lever.co/acme/1"]


class Repo(RepositorioDemo):
    def __init__(self, fila):
        super().__init__()
        self.fila, self.guardadas = fila, {}

    def vacante(self, vacante_id):
        return self.fila if self.fila and self.fila["id"] == vacante_id else None

    def guardar_descripcion(self, vacante_id, texto):
        self.guardadas[vacante_id] = texto


def _fila(descripcion):
    return {"id": "vac-1", "status": "active", "description_full": descripcion,
            "datos": {"titulo": "Product Designer", "empresa": "Acme", "enlace": "https://jobs.lever.co/acme/1",
                      "salario": "USD 3000", "anos_min": 3, "modalidad": "remoto"}}


def test_ficha_con_descripcion_guardada_no_lee_el_sitio():
    repo = Repo(_fila("Somos Acme.\n- Figma"))
    f = servicio.ficha(repo, "vac-1", obtener=lambda url: pytest.fail("no debía leer el sitio"))
    assert f["origen"] == "guardada" and f["salario"] == "USD 3000" and f["anos_min"] == 3
    assert f["bloques"][1] == {"tipo": "li", "texto": "Figma"}


def test_ficha_sin_descripcion_la_trae_una_vez_y_la_guarda():
    repo = Repo(_fila(""))
    f = servicio.ficha(repo, "vac-1", obtener=lambda url: _html("<p>Traída del sitio.</p>"))
    assert f["origen"] == "traida" and f["bloques"] == [{"tipo": "p", "texto": "Traída del sitio."}]
    assert repo.guardadas == {"vac-1": "Traída del sitio."}
    sin = servicio.ficha(Repo(_fila("")), "vac-1", obtener=lambda url: None)
    assert sin["origen"] == "sin_descripcion" and sin["bloques"] == []
    assert servicio.ficha(Repo(_fila("")), "vac-1", traer=False)["origen"] == "sin_descripcion"
    with pytest.raises(ErrorRepositorio):
        servicio.ficha(Repo(None), "vac-1")


def test_por_confirmar_por_paginas_con_total_real_y_filtro_por_cliente():
    repo = RepositorioDemo()
    hoy_cola = revision.listar(repo, hoy())
    assert hoy_cola["total"] == 4 and "pagina" not in hoy_cola
    p1 = revision.listar(repo, hoy(), pagina=1, por_pagina=3)
    p2 = revision.listar(repo, hoy(), pagina=2, por_pagina=3)
    assert (p1["total"], p1["paginas"], len(p1["pendientes"]), len(p2["pendientes"])) == (4, 2, 3, 1)
    assert all(x["mas_util"] for x in p1["pendientes"])
    ids = {x["vacante_id"] for x in p1["pendientes"] + p2["pendientes"]}
    assert len(ids) == 4
    cliente = p1["pendientes"][0]["cliente_ids"][0]
    solo = revision.listar(repo, hoy(), pagina=1, cliente_id=cliente)
    assert solo["total"] < 4 and all(cliente in x["cliente_ids"] for x in solo["pendientes"])
    assert p1["por_cliente"][cliente] == solo["total"]


def test_api_ficha_y_copia_de_resultados_que_se_invalida_al_decidir():
    api = TestClient(crear_app(demo=True, repositorio=RepositorioDemo()))
    h = {"origin": "http://testserver"}
    cliente = configuracion_demo()["clientes"][0]["id"]
    primera = api.get("/api/resultados", params={"cliente_id": cliente}).json()
    vid = primera["vacantes"][0]["id"]
    f = api.get(f"/api/vacantes/{vid}/ficha").json()
    assert f["titulo"] and any(b["tipo"] == "li" for b in f["bloques"]) and any(b["tipo"] == "h" for b in f["bloques"])
    assert api.get("/api/vacantes/xx/ficha").status_code == 422
    assert api.get("/api/vacantes/no-existe/ficha").status_code == 404
    assert api.get("/api/revisiones", params={"pagina": 0}).status_code == 422
    # La bandeja confirma una vacante para este cliente: la copia de resultados no puede ocultarla.
    pendiente = next(p for p in api.get("/api/revisiones").json()["pendientes"] if cliente in p.get("cliente_ids", []))
    assert api.post(f"/api/revisiones/{pendiente['vacante_id']}", json={"decision": "sirve", "paises": ["CO"]},
                    headers=h).status_code == 200
    despues = api.get("/api/resultados", params={"cliente_id": cliente}).json()
    assert len(despues["vacantes"]) == len(primera["vacantes"]) + 1
