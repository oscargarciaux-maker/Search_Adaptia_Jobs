"""Contrato v34: «Por confirmar» rápido. La noche guarda un resumen corto en la fila de la bandeja (SQL 018) y el panel
lista sin leer el catálogo; las filas sin resumen (antes de 018 o de noches anteriores) se calculan como antes."""
import pytest

from buscador import ficha
from buscador.fuentes import linkedin_publico
from panel import revision
from panel.repositorio import RepositorioSupabase, hoy
from pruebas.panel.test_revision import Repo, _cfg, _fila


@pytest.fixture(autouse=True)
def _sin_automaticas(monkeypatch):
    monkeypatch.setattr(revision, "APLICAR_SUGERENCIAS", False)


class RepoContado(Repo):
    def __init__(self, candidatas, con_resumen=True):
        super().__init__(candidatas)
        self._con = con_resumen
        self.lecturas_catalogo = 0

    def con_resumen(self):
        return self._con

    def revisiones(self, estado=None, vacante_id=None, ligera=False):
        if ligera and self._con:  # como Supabase con SQL 018: sin el catálogo
            return super(Repo, self).revisiones(estado, vacante_id)
        return super().revisiones(estado, vacante_id, ligera)

    def filas_catalogo(self, ids):
        self.lecturas_catalogo += len(ids)
        por_id = {c["id"]: c for c in self._candidatas}
        return {i: por_id[i] for i in ids if i in por_id}


def test_la_noche_guarda_el_resumen_y_el_panel_no_lee_el_catalogo():
    cfg, _ = _cfg()
    r = RepoContado([_fila(n, f"Remote Remoto {n}") for n in range(3)])
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    filas = r.revisiones(estado="pendiente", ligera=True)
    assert filas and all(f["resumen"]["titulo"] == "Product Designer" for f in filas)
    assert {"empresa", "ubicacion", "modalidad", "salario", "idioma", "publicada", "enlace", "paises", "sugerida",
            "paises_sugeridos", "por_que", "frase"} <= set(filas[0]["resumen"])
    vista = revision.listar(r, hoy(), pagina=1)
    assert r.lecturas_catalogo == 0
    p = vista["pendientes"][0]
    assert p["titulo"] == "Product Designer" and p["empresa"].startswith("Empresa ") and p["idioma"] == "en"
    assert p["paises"] == ["AR", "CO", "MX"] and p["frase"]


def test_sin_sql_018_se_guarda_como_antes_y_se_calcula_al_mostrar():
    cfg, _ = _cfg()
    r = RepoContado([_fila(n, f"Remote Remoto {n}") for n in range(2)], con_resumen=False)
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    assert all("resumen" not in f for f in r.estado["revisiones"])
    vista = revision.listar(r, hoy(), pagina=1)
    assert vista["pendientes"][0]["titulo"] == "Product Designer" and vista["pendientes"][0]["sugerida"]


def test_las_pendientes_de_noches_anteriores_reciben_su_resumen_una_vez():
    cfg, _ = _cfg()
    r = RepoContado([_fila(n, f"Remote Remoto {n}") for n in range(2)], con_resumen=False)
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    r._con = True  # se instaló SQL 018
    revision.preparar_cola(r, cfg, hoy(), {p.id: 0 for p in cfg.perfiles})
    assert all(f.get("resumen", {}).get("titulo") for f in r.estado["revisiones"])
    revision.listar(r, hoy(), pagina=1)
    assert r.lecturas_catalogo == 0


class _Respuesta:
    def __init__(self, codigo, cuerpo):
        self.status_code, self._cuerpo = codigo, cuerpo
        self.content = b"x"

    def json(self):
        return self._cuerpo


class _Sesion:
    def __init__(self, existe):
        self.existe, self.pedidas = existe, []

    def request(self, metodo, url, **op):
        self.pedidas.append((metodo, url, op.get("params")))
        if "resumen" in str(op.get("params")) and not self.existe:
            return _Respuesta(400, {"code": "42703", "message": "column panel_revisiones.resumen does not exist"})
        return _Respuesta(200, [])


@pytest.mark.parametrize("existe", [True, False])
def test_supabase_lee_ligero_solo_si_existe_la_columna(existe):
    repo = RepositorioSupabase.__new__(RepositorioSupabase)
    repo.url, repo.cabeceras, repo.sesion = "https://x.supabase.co", {}, _Sesion(existe)
    repo._paginas = lambda tabla, orden, params, tam: iter([{"vacante_id": "a", "params": params}])
    fila = repo.revisiones(estado="pendiente", ligera=True)[0]
    assert ("catalogo_vacantes" in fila["params"]["select"]) is (not existe)
    assert ("resumen" in fila["params"]["select"]) is existe
    repo.revisiones(estado="pendiente", ligera=True)
    assert sum(1 for m, _, p in repo.sesion.pedidas if p == {"select": "resumen", "limit": 1}) == 1  # una vez


def test_linkedin_conserva_saltos_vinetas_y_negritas():
    html = ('<div class="show-more-less-html__markup x"><strong>About the role</strong><br><br>We build '
            '<b>great</b> things.<ul><li>Figma</li><li>Research</li></ul><p><strong>Requirements:</strong></p></div>')
    texto = linkedin_publico.ficha(html)[0]
    assert "\n" in texto and "**great**" in texto
    assert ficha.bloques(texto) == [{"tipo": "h", "texto": "About the role"},
                                    {"tipo": "p", "texto": "We build **great** things."},
                                    {"tipo": "li", "texto": "Figma"}, {"tipo": "li", "texto": "Research"},
                                    {"tipo": "h", "texto": "Requirements"}]
