"""P-13.1: el Vigía de avisos. Respuestas falsas de GitHub (JSON de `gh`) y de Supabase (conexión y Storage
simulados) y de la API de issues, sin red. Avisa al pasar cada umbral, calla debajo, un solo issue abierto y ningún
texto sale de la lista blanca."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
import requests
import yaml

from buscador import almacen_respaldos as ar, arranque, vigia

RAIZ = Path(__file__).resolve().parent.parent
AHORA = datetime(2026, 11, 28, 16, 0, tzinfo=timezone.utc)  # 11:00 de Bogotá
MB = 1_048_576


def _corrida(horas_atras, conclusion="success", estado="completed", rama="main", evento="workflow_dispatch"):
    creada = (AHORA - timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"databaseId": 1, "status": estado, "conclusion": conclusion if estado == "completed" else "",
            "createdAt": creada, "event": evento, "headBranch": rama}


SANAS = {"bodega": [_corrida(3)], "captura": [_corrida(1)], "reloj": [_corrida(0.5)], "respaldo": [_corrida(100)]}


def _carpeta(tmp_path, corridas=None, flujos=None, commit=None, publicado="1000\n2000\n"):
    for clave, lista in {**SANAS, **(corridas or {})}.items():
        if lista is not None:
            (tmp_path / f"corridas_{clave}.json").write_text(json.dumps(lista), encoding="utf-8")
    estado = flujos if flujos is not None else [{"path": f".github/workflows/{f.archivo}", "state": "active"}
                                                for f in vigia.FLUJOS.values()]
    (tmp_path / "flujos.json").write_text(json.dumps(estado), encoding="utf-8")
    (tmp_path / "commit.txt").write_text(commit or (AHORA - timedelta(days=2)).isoformat(), encoding="utf-8")
    if publicado is not None:
        (tmp_path / "publicado.txt").write_text(publicado, encoding="utf-8")
    (tmp_path / "rama.txt").write_text("main\n", encoding="utf-8")
    return tmp_path


def _caducidades(tmp_path, entradas=()):
    ruta = tmp_path / "caducidades.yaml"
    ruta.write_text(yaml.safe_dump({"revisado": "2026-11-28", "caducidades": list(entradas)}), encoding="utf-8")
    return ruta


def _revisar(tmp_path, base=100 * MB, storage=200_000_000, entradas=(), **carpeta):
    (tmp_path / "datos").mkdir(parents=True)
    datos = _carpeta(tmp_path / "datos", **carpeta)
    return vigia.revisar(datos, AHORA, base=lambda: base, storage=lambda: storage,
                         caducidades=_caducidades(tmp_path, entradas))[0]


def _codigos(avisos):
    return sorted((a.codigo, a.urgente) for a in avisos)


# ── Todo en orden ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_con_todo_bien_no_avisa(tmp_path):
    assert _revisar(tmp_path) == []


def test_la_lista_real_de_caducidades_es_valida_y_hoy_no_avisa():
    datos = yaml.safe_load(vigia.CADUCIDADES.read_text(encoding="utf-8"))
    assert datos["caducidades"] and vigia.de_caducidades(datos, date(2026, 11, 28)) == []
    for e in datos["caducidades"]:
        assert e["tipo"] in vigia.ANTELACION and re.fullmatch(vigia.TEXTO_LIBRE, e["nombre"])
        assert re.fullmatch(vigia.TEXTO_LIBRE, e["paso"])


# ── Umbrales: avisa al pasar, calla debajo ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("usado,esperado", [(399, []), (400, [False]), (474, [False]), (475, [True]), (520, [True])])
def test_base_avisa_al_80_y_urgente_al_95(tmp_path, usado, esperado):
    avisos = _revisar(tmp_path, base=usado * MB)
    assert [a.urgente for a in avisos if a.codigo == "base"] == esperado


@pytest.mark.parametrize("usado,esperado", [(799, []), (800, [False]), (950, [True])])
def test_storage_avisa_al_80_y_urgente_al_95(tmp_path, usado, esperado):
    avisos = _revisar(tmp_path, storage=usado * 1_000_000)
    assert [a.urgente for a in avisos if a.codigo == "storage"] == esperado


@pytest.mark.parametrize("mayor,esperado", [(79, []), (80, [False]), (96, [True])])
def test_publicado_avisa_por_el_archivo_mas_grande(tmp_path, mayor, esperado):
    avisos = _revisar(tmp_path, publicado=f"12\n{mayor * MB}\n-\n300\n")
    assert [a.urgente for a in avisos if a.codigo == "publicado"] == esperado


@pytest.mark.parametrize("dias,esperado", [(29, []), (30, [False]), (49, [False]), (50, [True])])
def test_dias_sin_commits_en_main(tmp_path, dias, esperado):
    avisos = _revisar(tmp_path, commit=(AHORA - timedelta(days=dias, hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert [a.urgente for a in avisos if a.codigo == "commit"] == esperado


@pytest.mark.parametrize("tipo,faltan,esperado", [
    ("soporte", 181, []), ("soporte", 180, [("caduca", False)]), ("soporte", 30, [("caduca", True)]),
    ("clave", 31, []), ("clave", 30, [("caduca", True)]), ("clave", -1, [("caducado", True)]),
])
def test_caducidades_con_su_antelacion(tipo, faltan, esperado):
    hoy = date(2026, 11, 28)
    entrada = {"nombre": "Pieza ficticia", "tipo": tipo, "fecha": hoy + timedelta(days=faltan), "paso": "Haz algo."}
    assert _codigos(vigia.de_caducidades({"caducidades": [entrada]}, hoy)) == esperado


def test_una_fecha_con_hora_no_tumba_el_vigia():
    hoy = date(2026, 11, 28)
    entrada = {"nombre": "Token", "tipo": "clave", "fecha": datetime(2026, 12, 5, 10, 0), "paso": "Genera otro."}
    assert _codigos(vigia.de_caducidades({"caducidades": [entrada]}, hoy)) == [("caduca", True)]


def test_una_caducidad_con_texto_raro_no_sale_y_se_avisa_que_no_se_pudo_comprobar():
    hoy = date(2026, 11, 28)
    malas = [{"nombre": "x", "tipo": "clave", "fecha": hoy, "paso": "Escribe a alguien" + "@" + "ejemplo.com"},
             {"nombre": "x", "tipo": "clave", "fecha": hoy, "paso": "Abre https://sitio"},
             {"nombre": "x", "tipo": "otro", "fecha": hoy, "paso": "Paso."},
             {"nombre": "x", "tipo": "clave", "fecha": "mañana", "paso": "Paso."}]
    assert _codigos(vigia.de_caducidades({"caducidades": malas}, hoy)) == [("no_medido", False)]


# ── Corridas de GitHub ─────────────────────────────────────────────────────────────────────────────────────────────
def test_bodega_en_rojo_avisa_urgente_y_un_solo_aviso(tmp_path):
    avisos = _revisar(tmp_path, corridas={"bodega": [_corrida(2, "failure"), _corrida(30)]})
    assert [(a.codigo, a.urgente, a.valores["flujo"]) for a in avisos] == [("flujo_rojo", True, "bodega")]


def test_un_respaldo_de_la_bodega_que_no_trabajo_no_tapa_el_rojo(tmp_path):
    # La de la mañana publica y termina en AVERÍA; los horarios de respaldo terminan en verde sin trabajar.
    corridas = [_corrida(1, evento="schedule"), _corrida(2, evento="schedule"), _corrida(3, "failure")]
    assert _codigos(_revisar(tmp_path, corridas={"bodega": corridas})) == [("flujo_rojo", True)]
    # «Buscar ahora» (o el Reloj) después del rojo sí trabaja: lo tapa.
    corridas = [_corrida(1), _corrida(3, "failure", evento="schedule")]
    assert _revisar(tmp_path / "b", corridas={"bodega": corridas}) == []
    # Un rojo de hace más de 24 h ya no cuenta si después hubo verdes.
    corridas = [_corrida(2, evento="schedule"), _corrida(25, "failure")]
    assert _revisar(tmp_path / "c", corridas={"bodega": corridas}) == []


def test_bodega_que_no_termina_bien_en_30_horas_avisa_aunque_no_haya_rojo(tmp_path):
    avisos = _revisar(tmp_path, corridas={"bodega": [_corrida(31), _corrida(1, "cancelled"),
                                                     _corrida(0.2, estado="in_progress")]})
    assert _codigos(avisos) == [("flujo_parado", True)]


def test_captura_solo_avisa_con_dos_rojas_seguidas(tmp_path):
    assert _revisar(tmp_path, corridas={"captura": [_corrida(1, "failure"), _corrida(2)]}) == []
    avisos = _revisar(tmp_path / "b", corridas={"captura": [_corrida(1, "failure"), _corrida(2, "timed_out"), _corrida(3)]})
    assert _codigos(avisos) == [("flujo_rojo", False)]


def test_corridas_de_otra_rama_no_cuentan(tmp_path):
    avisos = _revisar(tmp_path, corridas={"reloj": [_corrida(0.5, "failure", rama="prueba")] * 3 + [_corrida(5)]})
    assert _codigos(avisos) == [("flujo_parado", False)]  # en main, el último relevo bueno fue hace 5 h


def test_flujo_desactivado_por_inactividad(tmp_path):
    flujos = [{"path": ".github/workflows/bodega.yml", "state": "disabled_inactivity"},
              {"path": ".github/workflows/reloj.yml", "state": "active"}]
    assert _codigos(_revisar(tmp_path, flujos=flujos)) == [("flujo_desactivado", True)]


def test_lo_que_no_se_pudo_leer_se_avisa_como_no_comprobado(tmp_path):
    def falla():
        raise RuntimeError("[DB_PASSWORD] detalle con postgres://usuario:clave@host")
    datos = _carpeta(tmp_path, corridas={"reloj": None}, publicado=None)
    (datos / "commit.txt").unlink()
    (datos / "flujos.json").write_text("no es json", encoding="utf-8")
    avisos, hoy = vigia.revisar(datos, AHORA, base=falla, storage=falla,
                                caducidades=tmp_path / "no-existe.yaml")
    assert sorted(a.valores["que"] for a in avisos) == sorted(vigia.NO_MEDIDO)
    texto = vigia.componer(avisos, hoy)
    assert "postgres" not in texto and "clave" not in texto and "@" not in texto


# ── Supabase simulado ──────────────────────────────────────────────────────────────────────────────────────────────
class ConexionFalsa:
    def __init__(self, tamano):
        self.tamano, self.sql = tamano, []

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql):
        self.sql.append(sql)
        return SimpleNamespace(fetchone=lambda: (self.tamano,))


def test_tamano_de_la_base_en_solo_lectura():
    conn = ConexionFalsa(420 * MB)
    assert vigia.tamano_base(conn) == 420 * MB
    assert conn.sql[0] == "set transaction read only" and "pg_database_size" in conn.sql[-1]


class StorageFalso:
    """Lista del bucket: dos copias semanales de 150 MB y una de instalación de 250 MB."""
    ARBOL = {"semanal/": ["2026-11-22_1", "2026-11-29_2"], "instalacion/": ["2026-11-27_3"]}

    def request(self, metodo, url, json=None, **k):
        prefijo = json["prefix"]
        if prefijo in self.ARBOL:
            lista = [{"name": n, "id": None} for n in self.ARBOL[prefijo]]
        elif prefijo.startswith(("semanal/", "instalacion/")):
            tamano = 150_000_000 if prefijo.startswith("semanal/") else 250_000_000
            lista = [{"name": "parte-000", "id": "x", "metadata": {"size": tamano}},
                     {"name": "manifiesto.json", "id": "x", "metadata": {"size": 0}}]
        else:
            lista = []
        return SimpleNamespace(status_code=200, json=lambda: lista[json["offset"]:])


def test_espacio_de_las_copias_con_storage_simulado():
    almacen = ar.Almacen("https://ficticio.supabase.co", "sb_secret_ficticia", sesion=StorageFalso(), pausa=0)
    usado = vigia.medir_storage(almacen)
    assert usado == 2 * 150_000_000 + 250_000_000
    assert vigia.por_uso("storage", usado, ar.CUOTA_GRATUITA) == []
    assert _codigos(vigia.por_uso("storage", usado + 300_000_000, ar.CUOTA_GRATUITA)) == [("storage", False)]


# ── Texto: lista blanca ────────────────────────────────────────────────────────────────────────────────────────────
def _todos():
    return ([vigia.Aviso("flujo_rojo", True, flujo=c) for c in vigia.FLUJOS]
            + [vigia.Aviso("flujo_parado", False, flujo=c, n=6) for c in vigia.FLUJOS]
            + [vigia.Aviso("flujo_desactivado", True, flujo=c) for c in vigia.FLUJOS]
            + [vigia.Aviso(c, False, pct=83) for c in ("base", "storage", "publicado")]
            + [vigia.Aviso("commit", False, dias=31)]
            + [vigia.Aviso("caduca", False, nombre="Python 3.12", fecha="2028-10-31", dias=170, paso="Pide algo.")]
            + [vigia.Aviso("caducado", True, nombre="Token", fecha="2027-11-27", paso="Genera otro.")]
            + [vigia.Aviso("no_medido", que=q) for q in vigia.NO_MEDIDO])


def test_cada_plantilla_encaja_en_la_lista_blanca_y_da_un_solo_paso():
    texto = vigia.componer(_todos(), date(2026, 11, 28))
    lineas = texto.splitlines()
    assert vigia.GENERICO not in lineas
    assert lineas[0] == f"Adaptia · Vigía 2026-11-28: {len(_todos())} avisos."
    assert all(l.count(" Paso: ") == 1 for l in lineas[1:])
    assert lineas[1].startswith("URGENTE")  # los urgentes primero


@pytest.mark.parametrize("aviso", [
    vigia.Aviso("flujo_rojo", flujo="Cliente Real S.A."),           # un nombre que no es de FLUJOS
    vigia.Aviso("base", pct="83 % — Bogotá"),                        # un valor que no es cifra
    vigia.Aviso("base", pct=83, cliente="Ana"),                      # un campo que no existe
    vigia.Aviso("caduca", nombre="x" + "@" + "y.com", fecha="2027-01-01", dias=3, paso="p"),
    vigia.Aviso("caduca", nombre="ok", fecha="pronto", dias=3, paso="p"),
    vigia.Aviso("no_medido", que="el error: HTTP 400 en /rest/v1/clientes"),
    vigia.Aviso("desconocido"),
])
def test_nada_fuera_de_la_lista_blanca_sale(aviso):
    texto = vigia.componer([aviso], date(2026, 11, 28))
    assert texto.splitlines()[1] == vigia.GENERICO


def test_texto_seguro_cambia_cualquier_linea_no_prevista():
    assert vigia.texto_seguro(["AVISO: La base de Supabase ocupa el 83 % de sus 500 MB. Paso: llama a Ana"]) == [vigia.GENERICO]


# ── Aviso en GitHub: un solo issue (API simulada) ──────────────────────────────────────────────────────────────────
class GitHubFalso:
    """Imita las rutas de la API de issues que usa el Vigía. `fallar` = estado HTTP que devuelve todo."""

    def __init__(self, fallar=None):
        self.issues, self.comentarios, self.etiquetas, self.llamadas, self.fallar = {}, [], set(), [], fallar

    def request(self, metodo, url, headers=None, json=None, params=None, timeout=None):
        ruta = url.split("/repos/dueno/repo", 1)[1]
        self.llamadas.append((metodo, ruta, dict(headers or {})))
        if self.fallar:
            return self._r(self.fallar)
        if metodo == "GET" and ruta == "/issues":
            abiertos = [{"number": n, **i} for n, i in sorted(self.issues.items())
                        if i["state"] == "open" and params["labels"] in i["labels"]]
            return self._r(200, abiertos + [{"number": 99, "title": vigia.TITULO, "pull_request": {}}])
        if metodo == "POST" and ruta == "/labels":
            if json["name"] in self.etiquetas:
                return self._r(422, {})
            self.etiquetas.add(json["name"])
            return self._r(201, {})
        if metodo == "POST" and ruta == "/issues":
            numero = len(self.issues) + 1
            self.issues[numero] = {"title": json["title"], "body": json["body"], "labels": json["labels"],
                                   "state": "open"}
            return self._r(201, {"number": numero})
        if metodo == "POST" and ruta.endswith("/comments"):
            self.comentarios.append((int(ruta.split("/")[2]), json["body"]))
            return self._r(201, {})
        if metodo == "PATCH":
            self.issues[int(ruta.split("/")[2])]["state"] = json["state"]
            return self._r(200, {})
        return self._r(404, {})

    @staticmethod
    def _r(estado, datos=None):
        return SimpleNamespace(status_code=estado, json=lambda: datos)


TOKEN = "token-ficticio-que-no-debe-salir"


@pytest.fixture
def entorno(monkeypatch):
    monkeypatch.setenv("GH_REPO", "dueno/repo")
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setenv("AVISO_GITHUB_USUARIO", "persona-de-soporte")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def test_mencion_solo_con_un_usuario_valido(capsys):
    assert vigia.mencion("persona-de-soporte") == vigia.mencion("@persona-de-soporte") == "@persona-de-soporte"
    for malo in ("", None, "dos palabras", "-guion", "a--b", "x" * 40, "a@b"):
        assert vigia.mencion(malo) == ""
    assert "AVISO_GITHUB_USUARIO" in capsys.readouterr().err


def test_abre_comenta_solo_lo_nuevo_y_cierra_al_volver_a_verde(tmp_path, entorno, capsys):
    api, firma = GitHubFalso(), tmp_path / "firma.txt"
    cad = _caducidades(tmp_path)
    vueltas = iter(range(100))

    def correr(base, corridas=None):
        carpeta = tmp_path / f"d{next(vueltas)}"
        carpeta.mkdir()
        vigia.main(["--datos", str(_carpeta(carpeta, corridas=corridas)), "--firma", str(firma)], ahora=AHORA,
                   sesion=api, base=lambda: base, storage=lambda: 10, caducidades=cad)

    firma.write_text("", encoding="utf-8")                        # ayer todo en orden
    correr(100 * MB)
    assert api.issues == {} and api.comentarios == []             # en orden y sin issue: nada
    correr(420 * MB)                                              # aviso: abre el issue con la mención
    issue = api.issues[1]
    assert issue["title"] == "Atención: Adaptia" and issue["labels"] == ["vigia"] and issue["state"] == "open"
    assert "La base de Supabase ocupa el 84 %" in issue["body"] and issue["body"].endswith("Para @persona-de-soporte.")
    correr(430 * MB)                                              # mismo aviso, otra cifra: no comenta
    assert api.comentarios == []
    correr(430 * MB, corridas={"bodega": [_corrida(2, "failure")]})  # aviso nuevo: comenta en el mismo issue
    assert len(api.issues) == 1 and api.comentarios[-1][0] == 1 and "Bodega nocturna" in api.comentarios[-1][1]
    assert "@persona-de-soporte" in api.comentarios[-1][1]
    correr(100 * MB)                                              # todo en orden: comenta y cierra, sin mención
    assert api.issues[1]["state"] == "closed" and api.comentarios[-1][1] == "Adaptia · Vigía 2026-11-28: todo en orden."
    correr(420 * MB)                                              # vuelve a fallar: issue nuevo
    assert len(api.issues) == 2 and api.issues[2]["state"] == "open"
    assert TOKEN not in capsys.readouterr().err
    assert all(h["Authorization"] == f"Bearer {TOKEN}" for _, _, h in api.llamadas)


def test_sin_firma_anterior_y_con_issue_abierto_comenta_por_si_acaso():
    api = GitHubFalso()
    github = vigia.GitHub("dueno/repo", TOKEN, api)
    assert vigia.avisar(github, "x", True, True, "@a") == "abierto"
    assert vigia.avisar(github, "x", True, True, "@a") == "comentado"
    assert vigia.avisar(github, "x", True, False, "@a") == "nada"
    assert vigia.avisar(github, "y", False, True) == "cerrado"
    assert vigia.avisar(github, "y", False, True) == "nada"
    assert api.etiquetas == {"vigia"}


def test_sin_usuario_abre_el_issue_sin_mencion_y_lo_dice(tmp_path, entorno, monkeypatch, capsys):
    monkeypatch.delenv("AVISO_GITHUB_USUARIO")
    api = GitHubFalso()
    datos = _carpeta(tmp_path, corridas={"bodega": [_corrida(2, "failure")]})
    vigia.main(["--datos", str(datos)], ahora=AHORA, sesion=api, base=lambda: MB, storage=lambda: 10,
               caducidades=_caducidades(tmp_path))
    assert "@" not in api.issues[1]["body"] and "Buscar ahora" in api.issues[1]["body"]
    assert "AVISO_GITHUB_USUARIO" in capsys.readouterr().err


def test_si_github_falla_la_corrida_queda_en_rojo_sin_el_token_y_sin_guardar_la_firma(tmp_path, entorno, capsys):
    firma = tmp_path / "firma.txt"
    firma.write_text("", encoding="utf-8")
    datos = _carpeta(tmp_path, corridas={"bodega": [_corrida(2, "failure")]})
    with pytest.raises(SystemExit) as salida:
        vigia.main(["--datos", str(datos), "--firma", str(firma)], ahora=AHORA, sesion=GitHubFalso(fallar=403),
                   base=lambda: MB, storage=lambda: 10, caducidades=_caducidades(tmp_path))
    assert salida.value.code == 1
    err = capsys.readouterr().err
    assert "HTTP 403" in err and TOKEN not in err and firma.read_text(encoding="utf-8") == ""


def test_el_cuerpo_del_issue_solo_lleva_lineas_de_la_lista_blanca():
    texto = vigia.componer(_todos(), date(2026, 11, 28))
    parrafos = vigia.cuerpo(texto, "@persona").split("\n\n")
    assert parrafos[-1] == "Para @persona."
    assert all(any(p.fullmatch(t) for p in vigia.PATRONES) for t in parrafos[:-1])


# ── El Reloj lo pide una vez al día ────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hora,vigias,esperado", [
    (15, [], False),                                         # 10:00 de Bogotá: aún no
    (16, [], True),                                          # 11:00, hoy no corrió
    (16, [_corrida(1)], False),                              # ya corrió hoy
    (16, [_corrida(0.1, estado="queued")], False),           # en marcha
    (16, [_corrida(1, "cancelled")], True),                  # GitHub lo canceló: se vuelve a pedir
    (16, [_corrida(1, "cancelled")] * 3, False),             # pero no más de 3 veces
    (16, [{**_corrida(1, "cancelled"), "empezo": True}], False),  # cortada a medias: ya corrió
    (16, [_corrida(1, rama="otra")], True),                  # una prueba en otra rama no cuenta
    (16, [_corrida(20)], True),                              # el de ayer no cuenta
    (16, None, False),                                       # sin lista: nada a ciegas
])
def test_toca_vigia(hora, vigias, esperado):
    ahora = AHORA.replace(hour=hora, minute=0)
    assert arranque.toca_vigia(vigias, "main", ahora)[0] is esperado


def test_linea_de_comandos_del_reloj_para_el_vigia(tmp_path, capsys):
    (tmp_path / "v.json").write_text("[]", encoding="utf-8")
    arranque.main(["--avisos", str(tmp_path / "v.json"), "--rama", "main"], ahora=AHORA)
    assert capsys.readouterr().out == "avisos=true\n"
    arranque.main(["--avisos", str(tmp_path / "no.json"), "--rama", "main"], ahora=AHORA)
    assert capsys.readouterr().out == "avisos=false\n"


# ── Flujos ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _flujo(nombre):
    return yaml.safe_load((RAIZ / ".github/workflows" / nombre).read_text(encoding="utf-8"))


def test_el_flujo_del_vigia_solo_lee_y_no_pega_valores_en_los_guiones():
    flujo = _flujo("vigia.yml")
    assert flujo["permissions"] == {"actions": "read", "contents": "read", "issues": "write"}
    assert flujo[True]["schedule"] and "workflow_dispatch" in flujo[True]
    trabajo = flujo["jobs"]["vigia"]
    assert trabajo["if"] == "github.ref == 'refs/heads/main'" and trabajo["timeout-minutes"] <= 15
    pasos = {p.get("name"): p for p in trabajo["steps"]}
    reunir = pasos["Reunir el estado de GitHub"]["run"]
    for clave, f in vigia.FLUJOS.items():
        assert f"{clave}:{f.archivo}" in reunir
    assert "awk '{print $4}'" in reunir  # de `publicado` solo los tamaños, sin nombres de archivo
    revisar = pasos["Revisar y avisar"]
    assert revisar["env"]["AVISO_GITHUB_USUARIO"] == "${{ vars.AVISO_GITHUB_USUARIO }}"
    assert "secrets." not in json.dumps(revisar["env"]).replace("secrets.SUPABASE", "")  # solo las de Supabase
    assert "pip install --require-hashes" in json.dumps(trabajo)
    for paso in trabajo["steps"]:
        assert "${{" not in paso.get("run", "")


def test_el_reloj_pide_el_vigia_al_final_sin_cortar_la_cadena():
    trabajo = _flujo("reloj.yml")["jobs"]["relevo"]
    orden = [p.get("name") for p in trabajo["steps"]]
    paso = trabajo["steps"][orden.index("Pedir el Vigía de avisos")]
    assert orden.index("Pedir el siguiente relevo") < orden.index("Pedir el Vigía de avisos")
    assert paso["continue-on-error"] is True and paso["if"] == "steps.decidir.outputs.actuar == 'true'"
    assert "--avisos" in paso["run"] and "gh workflow run vigia.yml" in paso["run"] and "${{" not in paso["run"]
