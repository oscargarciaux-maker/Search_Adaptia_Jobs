"""Auditoría de exposición (#2, #4): la rama publicado y los artefactos quedan solo con cifras agregadas; el detalle por
cargo vive en Supabase (`estado_trabajo`) y la siguiente corrida arranca igual que antes. Todo con datos ficticios."""
import ast
import gzip
import json
from pathlib import Path

import pytest

from buscador import arranque, estado_privado as ep

RAIZ = Path(__file__).resolve().parents[1]
CARGO = "cargo:11111111-2222-3333-4444-555555555555"
UUID = "11111111-2222-3333-4444-555555555555"
NOMBRE = "Cargo Ficticio Zeta"
VACANTE = "vacficticia00001"
HUELLA = "huellaficticia01"
HOY = "2026-11-27"
SECRETOS = (NOMBRE, UUID, VACANTE, HUELLA)
# 9.6: dónde y con qué se buscó (forma real: ciudad + idioma, país + idioma + remoto, términos de un cargo).
CIUDAD = "CIUDAD_VILLAFICTICIA:ES"
LUGAR = "ZZ:EN:REMOTO"
TERMINO = "termino ficticio omega"
CORRIDA_APIFY = "corridaficticia01"
LUGARES = (CIUDAD, LUGAR, TERMINO, CORRIDA_APIFY, "VILLAFICTICIA")
CAMPOS_POR_LUGAR = ("por_lugar", "respondidas", "por_pais", "motivos_por_pais", "portales_caidos", "reintentados",
                    "ejecuciones", "detalle")


def _json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _reporte():
    rol = {"nombre": NOMBRE, "candidatas": 4, "entregadas": 2, "unicas": 2, "faltan": 1, "idiomas": {"es": 2},
           "fuentes": {"LinkedIn": 2}, "paises": {"CO": 2}}
    return {
        "fecha": HOY, "modo": "diario", "consulta": "", "vacantes_en_bodega": 3, "nuevas_hoy": 1,
        "fuentes": {"LinkedIn (Apify)": {"busquedas": 1, "por_familia": {CARGO: 1, "qa": 2}, "por_lugar": {CIUDAD: 1},
                                         "ejecuciones": [{"run_id": CORRIDA_APIFY}], "descartadas": {"sin descripción": 1},
                                         "omitida": "sin crédito"},
                    "LinkedIn": {"busquedas": 3, "fallidas": 1, "por_lugar": {CIUDAD: 2, LUGAR: 1},
                                 "relectura": {"leidas": 2, "con_descripcion": 1}},
                    "Bumeran y portales hermanos": {"busquedas": 2, "por_pais": {"ZZ": 2}, "portales_caidos": ["ZZ"],
                                                    "motivos_por_pais": {"ZZ": {"http": 1}}, "reintentados": ["ZZ"]},
                    "Indeed": {"error": f"HTTPError: 403 para https://indeed.example/?q={NOMBRE}"}},
        "campo_nuevo_sin_clasificar": {"nombre": NOMBRE},
        "por_familia": {CARGO: 1, "qa": 2},
        "entrega": {"roles": {CARGO: rol}, "metas_por_rol": {CARGO: 3}, "meta_por_rol": None, "vacantes": 2,
                    "filas": 2, "meta_cumplida": False, "fecha": HOY,
                    "supabase": {"filas": 2, "enviadas": 2, "errores": [], "pendientes": 0},
                    "embudo": {CARGO: {"nuevas": 4}}},
        "seleccion_actual": {"fecha": HOY, "roles": {CARGO: {"nombre": NOMBRE, "meta": 3, "vacantes": [
            {"id": VACANTE, "catalog_status": "active", "afinidad_vigente": True, "verificacion": {"estado": "verificada"}}]}}},
        "refuerzos": [{"ronda": 1, "faltantes_antes": {CARGO: 1}, "crudas": 5, "fuentes": {
            "LinkedIn": {"busquedas": 2, "avisos": 4, "por_lugar": {CIUDAD: 1, LUGAR: 1}, "por_familia": {CARGO: 2}},
            "Indeed": {"busquedas": 1, "fallidas": 1, "por_lugar": {LUGAR: 1}, "por_familia": {"qa": 1}},
            "Get on Board": {"busquedas": 1, "avisos": 0, "fallidas": 0, "respondidas": [TERMINO]}}}],
        "historico_entregas": [{"fecha": HOY, "meta_cumplida": False, "roles": {CARGO: {"entregadas": 2}}}],
        "catalogo": {"filas": 3, "enviadas": 3, "errores": [], "pendientes": 0},
        "verificacion_enlaces": {"seleccion_del_dia": {"vacantes": 1, "estados": {"verificada": 1}}},
    }


def _salida(tmp_path):
    salida = tmp_path / "salida"
    t = salida / "trabajo"
    _json(t / "lote_entrega.json", {"fecha": HOY, "elegidas": {CARGO: [[{"id": VACANTE, "titulo": "Diseño"}, "exacto"]]}})
    _json(t / "entregadas.json", {HUELLA: HOY})
    _json(t / "estado.json", {"rendimiento": {CARGO + "@CO": {"utiles": 1, "ceros": 0}}, "linkedin": {"qa@CO": HOY}})
    for cola in ("catalogo", "supabase", "registro"):
        _json(t / f"pendientes_{cola}.json", {})
    _json(t / "metricas_entrega.json", {HOY: {"pasadas": 1, "fecha": HOY, "meta_cumplida": True,
                                              "pendientes_supabase": 0, "registro_confirmado": True,
                                              "roles": {CARGO: {"entregadas": 2, "faltan": 0}}}})
    _json(t / "verificacion_enlaces.json", {"https://empresa.example/1": {"estado": "verificada"}})
    vacantes = [{"id": VACANTE, "titulo": "Diseño", "rol_entrega_actual": CARGO,
                 "familias": [{"familia": "ux", "grado": "exacto"}, {"familia": CARGO, "grado": "exacto"}]},
                {"id": "otraficticia0001", "titulo": "QA", "rol_entrega_actual": ""},
                {"id": "terceraficticia1", "titulo": "Datos"}]
    with gzip.open(t / "bodega.json.gz", "wt", encoding="utf-8") as f:
        json.dump(vacantes, f)
    _json(salida / "datos" / "salud.json", _reporte())
    _json(salida / "datos" / "salud_bodega.json", _reporte())
    return salida


def _texto_publico(salida, con_bodega=False):
    """La bodega trae todas las vacantes (también la elegida): lo que no debe haber es qué se eligió ni para quién."""
    partes = []
    for ruta in sorted(Path(salida).rglob("*")):
        if ruta.is_file() and (con_bodega or ruta.name != "bodega.json.gz"):
            datos = ruta.read_bytes()
            partes.append(gzip.decompress(datos).decode() if ruta.suffix == ".gz" else datos.decode())
    return "\n".join(partes)


class SesionFalsa:
    """Imita la API REST de Supabase para la tabla estado_trabajo."""
    def __init__(self, estado=200):
        self.filas, self.estado, self.escrituras = {}, estado, 0

    def post(self, url, json, headers, timeout):
        self.escrituras += 1
        for fila in json:
            self.filas[(fila["grupo"], fila["archivo"])] = fila
        return type("R", (), {"status_code": 201})()

    def get(self, url, headers, timeout, params):
        grupo = params["grupo"].removeprefix("eq.")
        filas = [f for (g, _), f in self.filas.items() if g == grupo]
        return type("R", (), {"status_code": self.estado, "json": lambda self: filas})()


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ficticio.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "clave-ficticia")


def test_lo_publicado_no_trae_cargos_metas_ni_vacantes_elegidas(tmp_path):
    salida = _salida(tmp_path)
    privados = ep.separar(salida, tmp_path / "copia")
    texto = _texto_publico(salida)
    for secreto in SECRETOS:
        assert secreto not in texto
    for secreto in (NOMBRE, UUID, HUELLA):
        assert secreto not in _texto_publico(salida, con_bodega=True)
    for clave in ('"metas_por_rol"', '"meta_por_rol"', '"roles"', '"faltantes_antes": {', '"rol_entrega_actual"'):
        assert clave not in texto
    for rel in ep.PRIVADOS:
        assert not (salida / rel).exists() and rel in privados
    assert ep.CARGOS_BODEGA in privados
    # La copia local (fuera de lo publicado) conserva el reporte completo para validar en el mismo trabajo.
    assert json.loads((tmp_path / "copia/datos/salud.json").read_text(encoding="utf-8")) == _reporte()


def test_lo_publicado_conserva_cifras_agregadas(tmp_path):
    salida = _salida(tmp_path)
    ep.separar(salida)
    s = json.loads((salida / "datos/salud.json").read_text(encoding="utf-8"))
    e = s["entrega"]
    assert e["cargos"] == 1 and e["totales"]["meta"] == 3 and e["totales"]["entregadas"] == 2
    assert e["totales"]["faltan"] == 1 and e["por_idioma"] == {"es": 2} and e["por_fuente"] == {"LinkedIn": 2}
    assert e["filas"] == 2 and e["meta_cumplida"] is False and e["supabase"]["enviadas"] == 2
    assert s["seleccion_actual"] == {"fecha": HOY, "cargos": 1, "vacantes": 1}
    assert s["refuerzos"][0]["faltantes_antes"] == 1
    assert s["por_familia"] == {"qa": 2} and s["vacantes_en_bodega"] == 3
    assert s["resultado"] == "CORTA"   # meta incompleta: COMPLETA/CORTA/AVERÍA (contrato v52)
    assert s["fuentes"]["LinkedIn (Apify)"] == {"busquedas": 1, "descartadas": {"sin descripción": 1},
                                               "omitida": "sin crédito"}
    assert s["fuentes"]["LinkedIn"] == {"busquedas": 3, "fallidas": 1, "relectura": {"leidas": 2, "con_descripcion": 1}}
    ronda = s["refuerzos"][0]
    assert ronda == {"ronda": 1, "crudas": 5, "faltantes_antes": 1, "fuentes": {
        "LinkedIn": {"busquedas": 2, "avisos": 4}, "Indeed": {"busquedas": 1, "fallidas": 1},
        "Get on Board": {"busquedas": 1, "avisos": 0, "fallidas": 0}}}


def _claves(valor):
    if isinstance(valor, dict):
        for k, v in valor.items():
            yield k
            yield from _claves(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _claves(v)


def test_lo_publicado_no_dice_donde_ni_con_que_se_busco(tmp_path):
    """9.6: ni claves de ciudad o lugar, ni términos de búsqueda, ni desgloses por lugar, en fuentes y refuerzos."""
    salida = _salida(tmp_path)
    ep.separar(salida, tmp_path / "copia")
    texto = _texto_publico(salida, con_bodega=True)
    for secreto in LUGARES:
        assert secreto not in texto
    assert "CIUDAD_" not in texto
    for rel in ("datos/salud.json", "datos/salud_bodega.json"):
        s = json.loads((salida / rel).read_text(encoding="utf-8"))
        assert not set(_claves(s["fuentes"])) & set(CAMPOS_POR_LUGAR + ("por_familia",))
        assert not set(_claves(s["refuerzos"])) & set(CAMPOS_POR_LUGAR + ("por_familia",))
    # Se mueve, no se borra: la copia privada (y Supabase) conserva el detalle para quien opera.
    completo = (tmp_path / "copia/datos/salud.json").read_text(encoding="utf-8")
    assert CIUDAD in completo and TERMINO in completo


def test_un_desglose_nuevo_de_una_fuente_no_se_publica():
    """Lista blanca también dentro de cada fuente: lo que no es una cifra se queda fuera hasta clasificarlo."""
    publica = ep.fuente_publica({"busquedas": 1, "desglose_nuevo": {"ZZ": 1}, "lista_nueva": [TERMINO],
                                 "relectura": {"leidas": 1, "lugar": CIUDAD}})
    assert publica == {"busquedas": 1}


def test_el_registro_de_la_bodega_imprime_las_fuentes_recortadas():
    """El registro de Actions también es público: `bodega.main` imprime cada fuente ya recortada."""
    texto = (RAIZ / "buscador/bodega.py").read_text(encoding="utf-8")
    main = texto[texto.index("def main():"):]
    assert "fuentes_publicas(reporte[\"fuentes\"])" in main and "reporte[\"fuentes\"].items()" not in main


def test_el_arranque_decide_igual_con_las_metricas_publicadas(tmp_path):
    salida = _salida(tmp_path)
    completo = arranque.leer_dia(salida / "trabajo", HOY)
    ep.separar(salida)
    publico = arranque.leer_dia(salida / "trabajo", HOY)
    assert "roles" not in publico
    assert arranque.falta_completar(publico) == arranque.falta_completar(completo)
    assert arranque.busquedas_diarias(publico) == arranque.busquedas_diarias(completo)


def test_la_siguiente_corrida_arranca_con_el_mismo_estado(tmp_path, credenciales):
    salida = _salida(tmp_path)
    antes = {rel: (salida / rel).read_bytes() for rel in ep.PRIVADOS + ep.DIVIDIDOS}
    with gzip.open(salida / ep.BODEGA, "rt", encoding="utf-8") as f:
        bodega_antes = json.load(f)
    sesion = SesionFalsa()
    guardados = ep.guardar(salida, tmp_path / "copia", ejecucion="42", sesion=sesion)
    assert set(guardados) == set(ep.PRIVADOS + ep.DIVIDIDOS) | {ep.CARGOS_BODEGA}
    marca = json.loads((salida / ep.MARCA).read_text(encoding="utf-8"))
    assert marca["ejecucion"] == "42" and set(marca["archivos"]) == set(guardados)
    assert all(g == "vigente" for g, _ in sesion.filas)
    mensaje = ep.traer(salida, sesion=sesion)
    assert "recuperado" in mensaje
    for rel, datos in antes.items():
        assert (salida / rel).read_bytes() == datos
    with gzip.open(salida / ep.BODEGA, "rt", encoding="utf-8") as f:
        assert json.load(f) == bodega_antes   # "" y campo ausente se distinguen como antes


def test_sin_marca_se_usa_lo_que_trae_la_rama(tmp_path, credenciales):
    salida = _salida(tmp_path)
    antes = (salida / "trabajo/lote_entrega.json").read_bytes()
    assert "aún no separa" in ep.traer(salida, sesion=SesionFalsa(estado=404))
    assert (salida / "trabajo/lote_entrega.json").read_bytes() == antes


def test_con_marca_no_sigue_sin_el_estado_privado(tmp_path, credenciales):
    salida = _salida(tmp_path)
    sesion = SesionFalsa()
    ep.guardar(salida, None, ejecucion="42", sesion=sesion)
    with pytest.raises(RuntimeError, match="no se puede leer"):
        ep.traer(salida, sesion=SesionFalsa(estado=404))
    del sesion.filas[("vigente", "trabajo/lote_entrega.json")]
    with pytest.raises(RuntimeError, match=r"incompleto o mezclado \(1 archivos\)"):
        ep.traer(salida, sesion=sesion)


def test_un_estado_mezclado_de_dos_corridas_no_se_usa(tmp_path, credenciales):
    salida = _salida(tmp_path)
    sesion = SesionFalsa()
    ep.guardar(salida, None, ejecucion="42", sesion=sesion)
    sesion.filas[("vigente", "trabajo/entregadas.json")]["ejecucion"] = "41"
    with pytest.raises(RuntimeError, match="mezclado"):
        ep.traer(salida, sesion=sesion)


def test_se_guarda_en_una_sola_escritura_con_su_manifiesto(tmp_path, credenciales):
    sesion = SesionFalsa()
    ep.guardar(_salida(tmp_path), None, ejecucion="42", sesion=sesion)
    assert sesion.escrituras == 1 and ("vigente", ep.MARCA) in sesion.filas


def test_si_supabase_va_por_delante_de_la_rama_se_usa_supabase_con_aviso(tmp_path, credenciales):
    """La publicación falló después de guardar: la rama tiene la marca de la corrida 42 y Supabase la 43."""
    salida = _salida(tmp_path)
    sesion = SesionFalsa()
    ep.guardar(salida, None, ejecucion="42", sesion=sesion)
    marca_vieja = (salida / ep.MARCA).read_bytes()
    ep.traer(salida, sesion=sesion)
    ep.guardar(salida, None, ejecucion="43", sesion=sesion)
    (salida / ep.MARCA).write_bytes(marca_vieja)
    assert ep.traer(salida, sesion=sesion).startswith("Aviso")
    assert json.loads((salida / "trabajo/entregadas.json").read_text(encoding="utf-8")) == {HUELLA: HOY}


def test_si_algo_no_se_puede_leer_la_carpeta_queda_como_estaba(tmp_path):
    salida = _salida(tmp_path)
    (salida / "trabajo/metricas_entrega.json").write_text("{roto", encoding="utf-8")
    with pytest.raises(ValueError):
        ep.separar(salida)
    assert (salida / "trabajo/lote_entrega.json").exists()


def test_las_escrituras_cortadas_no_quedan_a_la_vista(tmp_path):
    salida = _salida(tmp_path)
    (salida / "trabajo/lote_entrega.json.tmp").write_text(NOMBRE, encoding="utf-8")
    ep.separar(salida)
    assert not list(salida.rglob("*.tmp"))


def test_el_reporte_publico_es_lista_blanca(tmp_path):
    salida = _salida(tmp_path)
    ep.separar(salida)
    s = json.loads((salida / "datos/salud.json").read_text(encoding="utf-8"))
    assert "campo_nuevo_sin_clasificar" not in s and s["campos_no_publicados"] == ["campo_nuevo_sin_clasificar"]
    assert s["fuentes"]["Indeed"]["error"] == "HTTPError"   # el texto del error puede traer el nombre del cargo


def test_cada_campo_del_reporte_real_esta_clasificado():
    """Si `bodega.correr` empieza a emitir un campo nuevo, hay que decidir cómo se publica (o que no se publique)."""
    arbol = ast.parse((RAIZ / "buscador/bodega.py").read_text(encoding="utf-8"))
    reportes = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                and any(isinstance(d, ast.Name) and d.id == "reporte" for d in n.targets)]
    claves = {k.value for d in reportes for k in d.keys if isinstance(k, ast.Constant)}
    assert claves and claves <= set(ep.CAMPOS_REPORTE)


def test_una_corrida_fallida_no_pisa_el_estado_vigente(tmp_path, credenciales):
    salida = _salida(tmp_path)
    sesion = SesionFalsa()
    ep.guardar(salida, None, grupo="fallida", ejecucion="43", sesion=sesion)
    assert sesion.filas and all(g == "fallida" for g, _ in sesion.filas)
    assert not (salida / ep.MARCA).exists()
    for secreto in SECRETOS:
        assert secreto not in _texto_publico(salida)   # el artefacto de una corrida fallida también queda limpio


def test_huella_alterada_no_se_usa(tmp_path, credenciales):
    salida = _salida(tmp_path)
    sesion = SesionFalsa()
    ep.guardar(salida, None, ejecucion="42", sesion=sesion)
    sesion.filas[("vigente", "trabajo/entregadas.json")]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="huella"):
        ep.traer(salida, sesion=sesion)


@pytest.mark.parametrize("flujo", ["bodega.yml", "incremental.yml", "profunda.yml"])
def test_los_flujos_separan_antes_de_publicar_y_de_subir_el_artefacto(flujo):
    texto = (RAIZ / ".github/workflows" / flujo).read_text(encoding="utf-8")
    traer = texto.index("python -m buscador.estado_privado traer --salida salida")
    guardar = texto.index("python -m buscador.estado_privado guardar --salida salida")
    assert texto.index("git clone --depth 1 --branch publicado") < traer
    assert guardar < texto.index("uses: actions/upload-artifact") and guardar < texto.index("git push -q --force")
    assert "hashFiles('salida/trabajo/estado.json')" not in texto   # estado.json ya no queda en la carpeta publicada
    paso = texto[texto.rindex("- name:", 0, guardar):guardar]
    assert "always()" in paso and "id: separar" in paso and "--fallida" in texto[guardar:texto.index("\n", guardar)]
    assert "validacion --salida privado/estado_trabajo" in texto
    artefacto = texto[texto.rindex("- name:", 0, texto.index("uses: actions/upload-artifact")):]
    assert "steps.separar.outcome == 'success'" in artefacto.split("uses:", 1)[0]


def test_bodega_decide_con_lo_publico_y_repone_solo_si_trabaja():
    texto = (RAIZ / ".github/workflows/bodega.yml").read_text(encoding="utf-8")
    traer = texto.index("python -m buscador.estado_privado traer")
    paso = texto[texto.rindex("- name:", 0, traer):traer]
    assert texto.index("python -m buscador.arranque --trabajo") < traer < texto.index("uses: ./.github/actions/preparar")
    assert "steps.decidir.outputs.ejecutar == 'true'" in paso
    assert "rm -f salida/datos/salud.json" in texto[traer:texto.index("- name:", traer)]
    resumen = texto[texto.index("- name: Resumen"):texto.index("- name: Avisar")]
    assert "estado_privado resumen --salida salida" in resumen and "nombre" not in resumen


def test_el_resumen_publico_no_nombra_cargos(tmp_path):
    salida = _salida(tmp_path)
    ep.separar(salida)
    texto = ep.resumen(json.loads((salida / "datos/salud.json").read_text(encoding="utf-8")))
    assert "meta total 3, faltan 1" in texto and NOMBRE not in texto and UUID not in texto


def test_migracion_022_es_privada():
    sql = (RAIZ / "supabase/migraciones/022_estado_trabajo.sql").read_text(encoding="utf-8")
    assert "enable row level security" in sql
    assert "revoke all on public.estado_trabajo from public, anon, authenticated, service_role;" in sql
    assert "grant select, insert, update on public.estado_trabajo to service_role;" in sql
    assert "anon" not in sql.split("revoke all", 1)[1].split("\n", 1)[1]
