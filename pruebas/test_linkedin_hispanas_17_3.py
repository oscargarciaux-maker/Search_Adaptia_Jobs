"""P-17.3 (E-FUE T3): las fichas de LinkedIn van primero a las remotas de un país hispano sin idioma de un cargo de
quien solo acepta español (365 así en la bodega del 28 nov), y la captura horaria vuelve a releer lo guardado (le
quedaban 0 s). Mismo ritmo: solo cambia el orden."""
import pytest

from buscador import cobertura, incremental, paises
from buscador.fuentes import linkedin_publico

TEXTO = "Buscamos una persona para pruebas de software, automatización y calidad en un equipo remoto. " * 4
SOLO_ES = {"familia": "cargo:qa", "perfil": "a", "lugares": ["MX", "REMOTO_MX"], "peso": 5, "corto": False,
           "idiomas": ["es"]}
CORTO_EN = {"familia": "cargo:pm", "perfil": "b", "lugares": ["US"], "peso": 5, "corto": True, "idiomas": ["en"]}


@pytest.fixture
def personas():
    def configurar(*lista):
        cobertura.configurar_personas(list(lista))
    yield configurar
    cobertura.configurar_personas()


class _Respuesta:
    def __init__(self, texto, status=200):
        self.text, self.status_code = texto, status


class _Fichas:
    """Responde la ficha de cada aviso; `vacios` responden 200 sin texto (aviso borrado), `bloqueados` 429."""
    def __init__(self, vacios=(), bloqueados=(), borrados=()):
        self.pedidas, self.vacios, self.bloqueados, self.borrados = [], set(vacios), set(bloqueados), set(borrados)

    def get(self, url, params=None, **_):
        n = url.rsplit("/", 1)[1]
        self.pedidas.append(n)
        if n in self.bloqueados:
            return _Respuesta("", 429)
        if n in self.borrados:
            return _Respuesta("", 404)
        return _Respuesta("" if n in self.vacios else f'<div class="show-more-less-html__markup">{TEXTO}</div>')


def _guardada(n, familia, pais, modalidad="remoto", **extra):
    return {"id": str(n), "titulo": "Analista QA", "empresa": "Acme", "enlace": f"https://www.linkedin.com/jobs/view/{n}",
            "fecha_publicacion": "2026-11-27", "_descripcion": "", "idioma": "", "modalidad": modalidad,
            "familias": [{"familia": familia, "coincidencia": "exacto"}], "paises": [pais] if pais != "SE" else [],
            "paises_mundo": [pais], "alcance_mundial": False, **extra}


def _orden(previas, estado=None, maximo=10, cliente=None):
    cliente = cliente or _Fichas()
    _, stats = linkedin_publico.completar_descripciones(cliente, previas, maximo, hoy="2026-11-28", max_dias=30,
                                                        estado=estado)
    return cliente.pedidas, stats


def test_remota_hispana_es_de_un_pais_hispano_sin_alcance_mundial():
    assert linkedin_publico.remota_hispana({"modalidad": "remoto", "paises": ["ES"], "paises_mundo": []})  # «Madrid»
    assert linkedin_publico.remota_hispana({"modalidad": "remoto", "paises": ["CO"], "paises_mundo": ["CO"]})
    # Con la regla de la entrega (`paises.abiertos`): nombrar Colombia sin estar abierta a ella no cuenta.
    assert not linkedin_publico.remota_hispana({"modalidad": "remoto", "paises": [], "paises_mundo": ["CO"]})
    assert not linkedin_publico.remota_hispana({"modalidad": "remoto", "paises_mundo": ["SE"]})
    assert not linkedin_publico.remota_hispana({"modalidad": "remoto", "paises": ["BR"], "paises_mundo": ["BR"]})
    assert not linkedin_publico.remota_hispana({"modalidad": "hibrido", "paises": ["CO"]})
    assert not linkedin_publico.remota_hispana({"modalidad": "remoto", "paises": paises.datos()["codigos"],
                                                "alcance_mundial": True})


def test_la_relectura_lee_primero_las_remotas_hispanas_de_quien_solo_acepta_espanol(personas):
    personas(SOLO_ES, CORTO_EN)
    del_corto = [_guardada(10 + n, "cargo:pm", "US") for n in range(3)]   # quien va corto (inglés) iba primero
    hispanas = [_guardada(20, "cargo:qa", "CO"), _guardada(21, "cargo:qa", "ES")]  # no son de su país: iban al final
    otras = [_guardada(30, "cargo:qa", "CO", modalidad="presencial"),         # no es remota
             _guardada(31, "cargo:qa", "SE"),                                 # remota de un país no hispano
             _guardada(32, "cargo:qa", "CO", alcance_mundial=True, paises=paises.datos()["codigos"],
                       paises_mundo=[]),                                     # remota mundial («Worldwide»)
             _guardada(33, "cargo:qa", "CO", idioma="en"),                    # ya se sabe el idioma
             _guardada(34, "cargo:pm", "CO")]                                 # cargo de quien acepta inglés
    pedidas, stats = _orden(del_corto + otras + hispanas)
    assert pedidas[:2] == ["20", "21"]
    assert pedidas[2:] == [v["id"] for v in cobertura.por_necesidad(del_corto + otras)]  # el resto, en el orden de antes
    assert stats["remotas_hispanas"] == 2 and stats["hispanas_con_descripcion"] == 2


def test_sin_personas_de_solo_espanol_el_orden_no_cambia(personas):
    previas = [_guardada(10, "cargo:pm", "US"), _guardada(20, "cargo:qa", "CO")]
    personas(CORTO_EN, dict(SOLO_ES, idiomas=["es", "en"]))
    pedidas, stats = _orden(previas)
    personas()  # modo heredado: nadie
    assert pedidas == _orden(previas)[0] == ["10", "20"] and stats["remotas_hispanas"] == 0


def test_una_ficha_sin_texto_no_vuelve_a_ir_primero_hasta_manana(personas):
    personas(SOLO_ES, CORTO_EN)
    previas = [_guardada(10, "cargo:pm", "US"), _guardada(20, "cargo:qa", "CO"), _guardada(21, "cargo:qa", "MX")]
    estado = {"cargo:qa@MX": "2026-11-27", linkedin_publico.RELEIDAS: {"99": "2026-11-27"}}
    pedidas, _ = _orden(previas, estado, cliente=_Fichas(vacios={"20"}))
    assert pedidas == ["21", "20", "10"]  # «21» le sirve a su país: dentro de la tanda va primero (por necesidad)
    assert estado[linkedin_publico.RELEIDAS] == {"20": "2026-11-28"}  # la de ayer se olvida
    assert estado["cargo:qa@MX"] == "2026-11-27"  # el resto del estado de LinkedIn no se toca
    pedidas, stats = _orden(previas, estado, cliente=_Fichas(vacios={"20"}))
    assert pedidas == ["21", "10", "20"] and stats["remotas_hispanas"] == 1  # «20» vuelve al orden de siempre por hoy
    estado[linkedin_publico.RELEIDAS] = {"20": "2026-11-27"}  # mañana vuelve a la tanda
    assert _orden(previas, estado)[0] == ["21", "20", "10"]


def test_un_bloqueo_de_linkedin_no_cuenta_como_ficha_sin_texto(personas):
    personas(SOLO_ES)
    estado = {}
    _orden([_guardada(20, "cargo:qa", "CO")], estado, cliente=_Fichas(bloqueados={"20"}))
    assert estado[linkedin_publico.RELEIDAS] == {}
    _orden([_guardada(20, "cargo:qa", "CO")], estado, cliente=_Fichas(borrados={"20"}))  # un 404 sí es del aviso
    assert estado[linkedin_publico.RELEIDAS] == {"20": "2026-11-28"}


# ── Búsqueda: entre los avisos del cargo, primero las remotas hispanas de quien solo acepta español ────────────────
def _tarjeta(n, titulo, lugar):
    return (f'<li><div class="base-card" data-entity-urn="urn:li:jobPosting:{n}">'
            f'<h3 class="base-search-card__title">{titulo}</h3><h4 class="base-search-card__subtitle">Empresa</h4>'
            f'<span class="job-search-card__location">{lugar}</span>'
            '<time class="job-search-card__listdate" datetime="2026-11-27">hace 1 día</time></div></li>')


class _Busqueda(_Fichas):
    def __init__(self, por_lugar):
        super().__init__()
        self.por_lugar = por_lugar

    def get(self, url, params=None, **k):
        if "jobPosting/" in url:
            return super().get(url, params, **k)
        if (params or {}).get("start") != "0":
            return _Respuesta("")
        return _Respuesta(self.por_lugar.get(((params or {}).get("location"), (params or {}).get("f_WT")), ""))


def test_la_busqueda_lee_primero_las_fichas_de_remotas_hispanas(personas):
    personas(SOLO_ES)
    lugares = [("MX", {"location": "Mexico"}), ("REMOTO_MX", {"location": "Mexico", "f_WT": "2"}),
               ("REMOTO_MUNDO", {"location": "Worldwide", "f_WT": "2"})]
    mapa = [{"id": "cargo:qa", "consultas": ["qa analyst"], "lugares": lugares}]
    cliente = _Busqueda({("Mexico", None): _tarjeta(1, "QA Analyst", "Ciudad de México, México"),
                         ("Mexico", "2"): _tarjeta(2, "QA Analyst", "México") + _tarjeta(3, "Vendedor", "México"),
                         ("Worldwide", "2"): _tarjeta(4, "QA Analyst", "Estocolmo, Suecia")
                         + _tarjeta(5, "QA Analyst", "Madrid y alrededores")})
    _, stats = linkedin_publico.buscar(cliente, mapa, [], {}, presupuesto=3, hoy="2026-11-28", max_fichas=2)
    assert sorted(cliente.pedidas) == ["2", "5"]  # las remotas de México y de España; no la presencial ni la de Suecia
    assert stats["remotas_hispanas"] == 2 and stats["fichas_hispanas"] == 2


# ── Captura horaria: la relectura recibe su parte del tiempo ───────────────────────────────────────────────────────
def test_la_captura_horaria_reserva_tiempo_para_releer(monkeypatch, tmp_path):
    llamadas = {}

    def buscar(cliente, mapa, activos, estado, presupuesto, **k):
        llamadas["buscar"] = k
        return [], {}

    def completar(cliente, previas, maximo, **k):
        llamadas["releer"] = k
        return [], {"peticiones": 0}
    monkeypatch.setattr(linkedin_publico, "buscar", buscar)
    monkeypatch.setattr(linkedin_publico, "completar_descripciones", completar)
    monkeypatch.setattr(incremental.ats, "leer_lista", lambda *a: [])
    monkeypatch.setattr(incremental.ats, "buscar", lambda *a, **k: ([], set(), {}))
    monkeypatch.setattr(incremental.indeed, "buscar", lambda *a, **k: ([], {}))
    cfg = {"incremental": {"minutos_por_fuente": 2, "linkedin_relectura": 48}, "paises_activos": [],
           "dias_maximos": 30}
    estado = {}
    sin_texto = {"enlace": "https://www.linkedin.com/jobs/view/1", "_descripcion": ""}
    incremental.recoger(cfg, estado, "2026-11-28", tmp_path, previas=[sin_texto])
    b = llamadas["buscar"]
    assert b["limite_segundos"] == 120 and b["reserva"] == pytest.approx(0.35)  # las páginas, con la mitad de siempre
    assert llamadas["releer"]["limite_segundos"] > 120 * 0.3 and llamadas["releer"]["estado"] is estado["linkedin"]
    llamadas.clear()
    # Sin avisos de LinkedIn guardados sin descripción, todo el tiempo a la búsqueda.
    incremental.recoger(cfg, {}, "2026-11-28", tmp_path, previas=[dict(sin_texto, _descripcion="x" * 300)])
    assert llamadas["buscar"]["reserva"] == 0 and "releer" not in llamadas
