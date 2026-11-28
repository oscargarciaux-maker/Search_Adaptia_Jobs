"""P-16.1: medidor de entrega estable (solo lectura) con datos sintéticos: embudo por paso, causa, índice anónimo,
conteo de repeticiones de la 12.15 y lista blanca de lo que sale (nada de nombres, ids, ciudades, cargos ni metas)."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json

import pytest

from buscador import diagnostico_entrega as de
from panel import contenido
from panel.terminos import grado
from panel.modelos import Configuracion
from panel.repositorio import configuracion_demo

FECHA = "2026-11-28"
RECIENTE = (date.fromisoformat(FECHA) - timedelta(days=2)).isoformat() + "T10:00:00+00:00"
VIEJA = (date.fromisoformat(FECHA) - timedelta(days=60)).isoformat() + "T10:00:00+00:00"
AHORA = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)
COMPROBADA = "2026-11-28T08:00:00+00:00"  # 4 h antes de AHORA: vigente


def fila(i, titulo="Product Designer", idioma="es", estado="verificada", motivo="", publicada=RECIENTE,
         modalidad="remoto", fuente="Computrabajo", **extra):
    """Una fila del catálogo tal como la devuelve el `select` de `CAMPOS_CATALOGO`."""
    return {"id": f"v{i}", "titulo": titulo, "paises": [], "paises_mundo": [], "alcance_mundial": True,
            "zona_utc": None, "ubicacion": "Remoto", "nota_pais": "", "confianza_pais": "alta",
            "modalidad": modalidad, "idioma": idioma, "publicada_en": publicada, "fecha_publicacion": None,
            "fecha_estimada": None, "ids_agrupados": [], "anos_min": None, "ingles": "", "requisito_ingles": None,
            "salario": None, "duplicada_de": None, "tipo": None, "verificacion": estado,
            "verificacion_motivo": motivo, "comprobada_en": COMPROBADA, "fuente": fuente, "fuentes": [fuente], **extra}


CATALOGO = [
    fila(1),                                                          # pasa todo y se asignó hoy
    fila(2),                                                          # ya la recibió otro día
    fila(3, estado="pendiente", motivo="presupuesto de comprobación agotado"),
    fila(4, estado="pendiente", motivo="acceso bloqueado"),
    fila(5, idioma="en"),                                             # solo acepta español
    fila(6, modalidad="presencial", ubicacion="Madrid, España", alcance_mundial=False, paises=["ES"]),
    fila(7, publicada=VIEJA),                                         # más de 30 días
    fila(8, titulo="Contador Público"),                               # otro cargo
    fila(9, estado="rechazada", motivo="página general sin vacante", fuente="LinkedIn (Apify)"),
    fila(10, comprobada_en="2026-11-25T08:00:00+00:00"),            # comprobada hace 3 días: ya no vale
    fila(11, estado="pendiente", motivo="sin comprobación directa", fuente="Indeed"),
]


def _cfg(metas=(10, 10, 10, 10, 10), comunidad=False):
    crudo = configuracion_demo()
    for p, meta in zip(crudo["perfiles"], metas):
        p.update(meta_diaria=meta, idiomas=["es"], modalidades=["remoto"])
    if comunidad:
        crudo["clientes"][-1]["comunidad"] = True
    return Configuracion.model_validate(crudo)


def _cargos(cfg):
    return {str(c.id): contenido.cargo_operativo(c.model_dump(mode="json")) for c in cfg.cargos}


def test_embudo_cuenta_cada_paso_con_las_reglas_de_la_seleccion():
    cfg = _cfg()
    p = cfg.perfiles[0]
    cargo = _cargos(cfg)[str(p.cargo_id)]
    catalogo = [de._vacante(f) for f in CATALOGO]
    del_cargo = [v for v in catalogo if grado(v["titulo"], cargo, cercanos=True)[0]]
    por_fuente = defaultdict(Counter)
    pasos, enlace, lugares = de.embudo(del_cargo, p, FECHA, {"v2"}, {"v1"}, por_fuente, AHORA)
    assert pasos == {"cargo": 10, "lugar": 9, "idioma": 8, "requisitos": 7, "enlace": 2, "no_recibida": 1,
                     "asignada": 1}
    assert enlace == {"sin_turno": 1, "bloqueo": 1, "rechazada": 1, "vencida": 1, "solo_vista": 1}
    assert lugares == {"modalidad": 1}
    assert por_fuente["_apify"]["cargo"] == 1 and por_fuente["_apify"]["enlace"] == 0
    assert por_fuente["Computrabajo"]["asignada"] == 1


def test_causa_es_el_primer_paso_bajo_la_meta():
    base = {"cargo": 30, "lugar": 20, "idioma": 12, "requisitos": 12, "enlace": 3, "no_recibida": 3, "asignada": 3}
    assert de.causa_de(base, {"sin_turno": 8, "bloqueo": 1}, 10, 3) == ("capacidad", "enlace")
    assert de.causa_de(base, {"vencida": 5, "sin_turno": 1, "bloqueo": 4}, 10, 3) == ("capacidad", "enlace")
    assert de.causa_de(base, {"bloqueo": 8, "sin_turno": 1}, 10, 3) == ("sistema", "enlace")
    assert de.causa_de(base, {"solo_vista": 8, "sin_turno": 2}, 10, 3) == ("sistema", "enlace")
    assert de.causa_de({**base, "cargo": 4}, {}, 10, 3) == ("mercado", "cargo")
    assert de.causa_de({**base, "idioma": 2}, {}, 10, 2) == ("sistema", "idioma")
    assert de.causa_de({**base, "enlace": 12, "no_recibida": 12}, {}, 10, 4) == ("sistema", "asignada")
    assert de.causa_de(base, {}, 10, 10) == ("cumple", "")


def _datos(cfg):
    pids = [str(p.id) for p in cfg.perfiles]
    ejecuciones = [{"id": "e3", "fecha": FECHA}, {"id": "e2", "fecha": "2026-11-27"},
                   {"id": "e1", "fecha": "2026-11-26"}, {"id": "e0", "fecha": "2026-11-01"}]  # e0: fuera de los 14 días
    conteo = Counter({("e3", pids[0]): 1, ("e2", pids[0]): 0, ("e1", pids[0]): 3,
                      ("e3", pids[1]): 12, ("e2", pids[1]): 11, ("e1", pids[1]): 10, ("e0", pids[1]): 99})
    metas = {e["id"]: {pid: 10 for pid in pids} for e in ejecuciones}
    revisiones = [{"vacante_id": "r1", "motivo": "ubicación por confirmar", "creada_en": FECHA + "T05:00:00+00:00",
                   "perfiles": [{"perfil_id": pids[0], "cliente_id": "x", "cargo_id": "y", "faltan": True}]},
                  {"vacante_id": "r2", "motivo": "Coincide por funciones", "creada_en": "2026-11-15T05:00:00+00:00",
                   "perfiles": [{"perfil_id": pids[0]}, {"perfil_id": pids[2]}]}]
    return {"fecha": FECHA, "cfg": cfg, "cargos": _cargos(cfg), "catalogo": [de._vacante(f) for f in CATALOGO],
            "ejecuciones": ejecuciones, "conteo": conteo, "metas": metas,
            "recibidas": {pids[0]: {"v1", "v2"}}, "asignadas_hoy": {pids[0]: {"v1"}}, "revisiones": revisiones}


def test_calcular_mide_14_dias_y_ordena_de_quien_menos_recibe():
    cfg = _cfg(comunidad=True)
    r = de.calcular(**_datos(cfg), ahora=AHORA)
    assert r["busquedas_en_ventana"] == 3 and r["ultima_busqueda"] == FECHA
    assert r["totales"]["perfiles"] == 4 and r["totales"]["comunidad"] == 1
    assert [f["media"] for f in r["perfiles"][:4]] == [0.0, 0.0, 1.3, 11.0]  # de quien menos recibe a quien más
    primero = r["perfiles"][2]
    assert primero["por_dia"] == [3, 0, 1] and primero["media"] == 1.3 and primero["dias_en_0"] == 1
    assert primero["dias_bajo_5"] == 3 and primero["dias_bajo_meta"] == 3 and primero["hoy"] == 1
    assert primero["embudo"]["asignada"] == 1
    assert (primero["causa"], primero["paso"]) == ("sistema", "lugar")  # 10 del cargo, 9 pasan el lugar (meta 10)
    assert primero["por_confirmar"] == {"total": 2, "ubicacion": 1, "funciones": 1, "otro_oficio": 0}
    estable = next(f for f in r["perfiles"] if f["media"] == 11.0)
    assert estable["causa"] == "cumple" and estable["dias_bajo_meta"] == 0 and 99 not in estable["por_dia"]
    assert r["totales"]["estables_en_meta"] == 1 and r["totales"]["en_0_algun_dia"] == 3
    assert [f["indice"] for f in r["perfiles"]] == ["P01", "P02", "P03", "P04", "P05"]
    assert r["perfiles"][-1]["tipo"] == "comunidad"  # la Comunidad va al final y no entra en los totales
    assert r["por_confirmar"]["pendientes"] == 2 and r["por_confirmar"]["por_antiguedad_dias"]["8_o_mas"] == 1
    assert sum(c["faltan_hoy"] for c in r["causas"]) == r["totales"]["faltan_hoy"] == 9 + 10 + 10
    # 3 perfiles de clientes con el mismo cargo (Product Designer): cada par perfil-vacante cuenta una vez.
    assert r["apify"] == {"cargo": 3, "lugar": 3, "idioma": 3, "requisitos": 3, "enlace": 0, "no_recibida": 0,
                          "asignada": 0}
    assert r["enlace_sin_comprobar"]["rechazada"] == 3 and r["enlace_sin_comprobar"]["vencida"] == 3
    assert r["por_fuente"]["Indeed"]["requisitos"] == 3 and r["por_fuente"]["Indeed"]["enlace"] == 0
    assert r["grupos"]["solo_es+remoto"]["perfiles"] == 4


def test_lo_que_sale_no_dice_nombres_ids_ciudades_cargos_ni_metas():
    cfg = _cfg(metas=(7, 13, 10, 10, 10))
    r = de.calcular(**_datos(cfg), ahora=AHORA)
    r["repeticiones"] = {"disponible": False}
    r["avisos_internos"] = 0
    de.lista_blanca(r)
    texto = json.dumps(r, ensure_ascii=False) + de.resumen_md(r)
    prohibidos = [*(c.nombre for c in cfg.clientes), *(c.nombre for c in cfg.cargos), *(str(p.id) for p in cfg.perfiles),
                  *(str(c.id) for c in cfg.clientes), *(str(c.id) for c in cfg.cargos), "Madrid", "Contador",
                  "Designer", "UX", '"CO"', '"ES"', "v1", "r1"]
    assert not [x for x in prohibidos if x in texto]
    assert "meta_diaria" not in texto and "_faltan" not in texto and "_deficit" not in texto


@pytest.mark.parametrize("malo", [{"perfiles": [{"causa": "Product Designer"}]}, {"Bogotá": 1},
                                  {"por_dia": ["Cliente de ejemplo 01"]}, {"fecha": object()},
                                  {"primer_camino_y_repeticion": {"lote -> Ana": 1}}])
def test_lista_blanca_rechaza_texto_libre(malo):
    with pytest.raises(ValueError):
        de.lista_blanca(malo)


def test_textos_fijos():
    assert de.familia_fuente("LinkedIn (Apify)") == "LinkedIn (Apify)"
    assert de.familia_fuente("Laborum") == "Bumeran y hermanos" and de.familia_fuente("Greenhouse") == \
        "Portales de empresas"
    assert de.familia_fuente("Un portal nuevo de Lima") == "Otras"
    assert de.categoria_enlace({"_verificacion": "verificada", "_comprobada_en": COMPROBADA}, AHORA) == ""
    assert de.categoria_enlace({"_verificacion": "verificada", "_comprobada_en": ""}, AHORA) == "vencida"
    assert de.categoria_enlace({"_verificacion": "pendiente", "_motivo_enlace": "sin comprobación directa"}) == \
        "solo_vista"
    assert de.categoria_enlace({"_verificacion": "pendiente", "_motivo_enlace": "requiere iniciar sesión"}) == "bloqueo"
    assert de.categoria_enlace({"_verificacion": "pendiente", "_motivo_enlace": "contenido insuficiente"}) == \
        "no_comprobable"
    assert de.categoria_enlace({"_verificacion": ""}) == "sin_turno"
    assert de.camino([{"rescatada": "bodega"}]) == "rescate" and de.camino([{"tipo": "post"}]) == "post"
    assert de.camino([{"reutilizada": True}]) == "reutilizada" and de.camino([{"aprobada_por": "x"}]) == "sirve"
    assert de.camino([{"ampliacion": "empresa_4"}]) == "lote_ampliada" and de.camino(None) == "lote"
    assert de.camino([{"funciones": True}]) == "sirve"  # «Sirve» anterior a v49
    assert de.camino([{"funciones": "fuerte"}]) == "lote"  # el nivel de evidencia no es un «Sirve»


class Pedir:
    """PostgREST falso: filtra `in.(…)`, `eq.` y la página siguiente (`gt.`), ordena y corta como `paginar` espera."""

    def __init__(self, tablas):
        self.tablas, self.llamadas = tablas, []

    def __call__(self, metodo, ruta, params=None, **_):
        assert metodo == "GET"  # solo lectura
        self.llamadas.append(ruta)
        filas = list(self.tablas[ruta])
        orden = (params or {}).get("order")
        for campo, valor in (params or {}).items():
            if campo in ("select", "order", "limit"):
                continue
            if valor.startswith("in.("):
                filas = [f for f in filas if str(f[campo]) in valor[4:-1].split(",")]
            elif valor.startswith("eq."):
                filas = [f for f in filas if str(f.get(campo)) == valor[3:]]
            elif valor.startswith("gt."):
                filas = [f for f in filas if str(f[campo]) > valor[3:]]
        if orden:
            filas.sort(key=lambda f: str(f[orden]))
        return filas[:int(params.get("limit", len(filas) or 1))] if orden else filas


ASIGNACIONES = [
    {"id": "a1", "perfil_id": "p1", "cliente_id": "c1", "vacante_id": "v1", "ejecucion_id": "e1",
     "creada_en": "2026-11-27T11:00:00", "explicacion": [{"grado": "exacto"}]},
    {"id": "a2", "perfil_id": "p1", "cliente_id": "c1", "vacante_id": "v1", "ejecucion_id": "e2",
     "creada_en": "2026-11-28T11:00:00", "explicacion": [{"rescatada": "bodega"}]},
    {"id": "a3", "perfil_id": "p2", "cliente_id": "c2", "vacante_id": "v1", "ejecucion_id": "e1",
     "creada_en": "2026-11-27T11:00:00", "explicacion": []},
    {"id": "a4", "perfil_id": "p1", "cliente_id": "c1", "vacante_id": "v3", "ejecucion_id": "e2",
     "creada_en": "2026-11-28T11:00:00", "explicacion": [{"reutilizada": True}]},
]


def test_repeticiones_por_camino_fecha_y_whatsapp():
    pedir = Pedir({"panel_ejecuciones": [{"id": "e1", "fecha": "2026-11-27"}, {"id": "e2", "fecha": "2026-11-28"}],
                   "panel_asignaciones": ASIGNACIONES,
                   "panel_borradores": [{"id": "b1", "cliente_id": "c1", "estado": "enviado", "vacantes": ["v1"]},
                                        {"id": "b2", "cliente_id": "c1", "estado": "enviado", "vacantes": ["v1", "v3"]},
                                        {"id": "b3", "cliente_id": "c2", "estado": "pendiente", "vacantes": ["v1"]}]})
    r = de.repeticiones(pedir)
    assert r["asignaciones_total"] == 4 and r["pares_distintos"] == 3 and r["pares_repetidos"] == 1
    assert r["filas_de_mas"] == 1 and r["perfiles_afectados"] == 1 and r["clientes_afectados"] == 1
    assert r["primer_camino_y_repeticion"] == {"lote -> rescate": 1}
    assert r["repeticiones_por_fecha"] == {"2026-11-28": 1}
    assert r["whatsapp"] == {"pares_repetidos_en_2_o_mas_borradores": 1, "pares_repetidos_enviados_2_o_mas_veces": 1}
    de.lista_blanca({"repeticiones": r})


class Repo:
    """Lo mínimo de RepositorioSupabase que usa `leer`, con datos sintéticos; `ajuste` falla con un texto privado."""

    def __init__(self, cfg):
        self.cfg = cfg
        pids = [str(p.id) for p in cfg.perfiles]
        self.pids = pids
        self.pedir = Pedir({
            "catalogo_vacantes": [{**f, "status": "active"} for f in CATALOGO],
            "panel_revisiones": [{"vacante_id": "r1", "estado": "pendiente", "motivo": "ubicación por confirmar",
                                  "creada_en": FECHA, "perfiles": [{"perfil_id": pids[0]}]}],
            "panel_ejecuciones": [{"id": "e1", "fecha": FECHA}],
            "panel_asignaciones": [{"id": "a1", "perfil_id": pids[0], "cliente_id": "c", "vacante_id": "v1",
                                    "ejecucion_id": "e1", "creada_en": FECHA, "explicacion": []}],
            "panel_borradores": []})

    def operativa(self, fecha):
        return {"revision": 4, "configuracion": self.cfg.model_dump(mode="json")}

    def ejecuciones(self):
        return [{"id": "e1", "fecha": FECHA, "revision": 4}]

    def versiones(self, revisiones):
        assert revisiones == [4]
        return {4: self.cfg.model_dump(mode="json")}

    def asignaciones_por_perfil(self, ids):
        return Counter({("e1", self.pids[0]): 1})

    def recibidas(self, perfil_ids):
        return {self.pids[0]: {"v1", "v2"}}

    def asignadas_de(self, ejecucion_id):
        return {self.pids[0]: {"v1"}}

    def ajuste(self, clave, defecto=None):
        raise RuntimeError("Cliente de ejemplo 01 en Bogotá")


def test_medir_lee_solo_y_no_imprime_los_avisos_internos(capsys):
    r = de.medir(Repo(_cfg()), FECHA, AHORA)
    salida = capsys.readouterr()
    assert "Bogotá" not in salida.out + salida.err and r["avisos_internos"] >= 1
    assert next(f for f in r["perfiles"] if f["hoy"] == 1)["embudo"]["asignada"] == 1 and r["repeticiones"]["pares_repetidos"] == 0


def test_main_si_falla_solo_dice_el_tipo(monkeypatch, capsys, tmp_path):
    import panel.repositorio as repositorio

    def roto():
        raise RuntimeError("clave sb_secret_xxx de Cliente de ejemplo 01")
    monkeypatch.setattr(repositorio, "RepositorioSupabase", roto)
    assert de.main(["--salida", str(tmp_path)]) == 1
    salida = capsys.readouterr().out
    assert "::error::" in salida and "RuntimeError" in salida and "Cliente" not in salida and "sb_secret" not in salida
