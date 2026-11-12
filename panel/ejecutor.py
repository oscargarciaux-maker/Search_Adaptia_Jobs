"""Adaptador del control privado al motor de captura existente, sin datos de clientes en reportes públicos."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from buscador import bodega, entrega, familias, paises, supabase
from panel.afinidad import AMPLIACIONES, MINIMO_POR_PERFIL, evaluar, evaluar_ampliada
from panel.modelos import Configuracion
from pydantic import ValidationError
from panel.repositorio import RepositorioSupabase, hoy
from panel.terminos import grado, sugerir


def validar_version(version):
    try:
        return Configuracion.model_validate(version["configuracion"]).validar_publicacion()
    except (ValidationError,ValueError,KeyError):
        raise RuntimeError("La configuración privada no es válida; revísala en el panel. No se muestran datos de clientes.") from None


def lugares_perfil(p, nombres=None):
    """Contrato v8: su país (remoto si lo acepta), las remotas regionales y, con híbrido/presencial, sus oficinas."""
    nombres = nombres or {x["codigo"]: x["nombre"] for x in paises.datos()["paises"]}
    lugares = {}
    if "remoto" in p.modalidades:
        lugares["REMOTO_" + p.vive_en] = {"location": nombres[p.vive_en], "f_WT": "2"}
        lugares["REMOTO"] = {"location": "Latin America", "f_WT": "2"}
        lugares["REMOTO_MUNDO"] = {"location": "Worldwide", "f_WT": "2"}
    if {"hibrido", "presencial"} & set(p.modalidades):
        for codigo in p.paises_oficina:
            lugares[codigo] = {"location": nombres[codigo]}
    return lugares


def preparar(version, fecha):
    cfg = validar_version(version)
    mapa, roles = [], []
    nombres = {p["codigo"]: p["nombre"] for p in paises.datos()["paises"]}
    for c in cfg.cargos:
        if not c.activo or not c.cupo:
            continue
        perfiles = cfg.perfiles_activos(c.id)
        raw = c.model_dump(mode="json")
        if not raw["terminos_exactos"]:
            raw["terminos_exactos"] = sugerir(c.nombre, consultar_esco=False)["terminos_exactos"]
        lugares = {}
        for p in perfiles:
            lugares.update(lugares_perfil(p, nombres))
        rid = "cargo:" + str(c.id)
        mapa.append({"id": rid, "nombre": c.nombre, "consultas": [c.nombre, *raw["terminos_exactos"], *raw["terminos_similares"]],
            "exactos": raw["terminos_exactos"], "similares": raw["terminos_similares"], "cercanos": raw.get("terminos_cercanos", []),
            "excluir": raw["terminos_excluidos"], "herramientas": [], "lugares": list(lugares.items()),
            "_control_cargo": raw,
            "paises_objetivo": sorted({x for p in perfiles for x in p.paises_oficina}),
            "solo_remoto": all(p.modalidades == ["remoto"] for p in perfiles)})
        roles.append({"id": rid, "nombre": c.nombre, "familias": [rid], "cupo": c.cupo,
                      "_perfiles": [p.model_dump(mode="json") for p in perfiles], "_hoy": fecha})
    configuracion = {"por_rol": 20, "roles": roles, "preferir_remotas": True, "max_por_empresa": 2,
                     "dias_frescura": 30, "idiomas": ["es", "en"]}
    motor = bodega.config()
    motor["paises_activos"] = sorted({p for x in mapa for p in x["paises_objetivo"]})
    motor["dias_maximos"] = max(p.antiguedad_dias for p in cfg.perfiles_activos())
    motor["control_dirigido"] = True
    motor["presupuestos"].update(linkedin_busquedas=min(300, max(24, len(roles) * 24)),
        indeed_busquedas=min(72, max(6, len(roles) * 8)), getonbrd_busquedas=min(30, len(roles) * 4),
        computrabajo_busquedas=min(90, max(12, len(roles) * 12)),
        empresas_por_probar=20, remotos_paginas=24)
    return mapa, configuracion, motor


@contextmanager
def activar(version, fecha):
    mapa, cfg, motor = preparar(version, fecha)
    anterior_e, anterior_b = entrega._config_operativa, bodega._config_operativa
    familias.configurar(mapa)
    entrega._config_operativa, bodega._config_operativa = cfg, motor
    try:
        yield cfg
    finally:
        familias.configurar()
        entrega._config_operativa, bodega._config_operativa = anterior_e, anterior_b


def iniciar(repo, version, fecha):
    """Fija una versión diaria y permite releer la misma ejecución al reintentar."""
    e = repo.pedir("GET", "panel_ejecuciones", params={"fecha": "eq." + fecha, "limit": 1})
    if not e:
        e = repo.pedir("POST", "panel_ejecuciones", json={"fecha": fecha, "revision": version["revision"]},
                       params={"on_conflict": "fecha"}, headers={"Prefer":"resolution=ignore-duplicates"})  # repositorio aplica cabeceras comunes
        e = repo.pedir("GET", "panel_ejecuciones", params={"fecha": "eq." + fecha, "limit": 1})
    ejecucion = e[0]
    if ejecucion["revision"] != version["revision"]:
        raise RuntimeError("La captura de hoy conserva otra versión; no se reasigna el historial.")
    return ejecucion


def _embudo_por_nombre(reporte):
    """Embudo de la nocturna por nombre de cargo; las capturas horarias conservan el último guardado."""
    embudo = ((reporte or {}).get("entrega") or {}).get("embudo") or {}
    return {e["nombre"]: {k: v for k, v in e.items() if k != "nombre"} for e in embudo.values()
            if isinstance(e, dict) and "nombre" in e}


def registrar(repo, version, fecha, reporte=None):
    """Reconstruible desde la selección confirmada, incluso tras perder el proceso anterior."""
    ejecucion = iniciar(repo, version, fecha)
    cfg = validar_version(version)
    seleccionadas = repo.pedir("GET", "entregas_diarias", params={"delivery_date": "eq." + fecha, "select": "*", "limit": 500})
    filas, conteos, estrictas, ampliables = [], {}, {}, []
    def fila(row, p, cargo_id, pruebas, extra=()):
        c = next(c for c in cfg.cargos if str(c.id) == cargo_id)
        _, evidencia = grado(row["snapshot"]["titulo"], c.model_dump(mode="json"), cercanos=True)
        return {"ejecucion_id": ejecucion["id"], "cliente_id": str(p.cliente_id),
                "perfil_id": str(p.id), "cargo_id": cargo_id, "vacante_id": row["vacante_id"],
                "match_grade": row["match_grade"], "explicacion": [*pruebas, evidencia or {"regla": "similitud textual"}, *extra],
                "filtros": p.model_dump(mode="json"), "cargo_configuracion": c.model_dump(mode="json")}
    for row in seleccionadas:
        if not row["role_id"].startswith("cargo:"):
            continue
        cargo_id = row["role_id"].split(":", 1)[1]
        conteos[cargo_id] = conteos.get(cargo_id, 0) + 1
        for p in cfg.perfiles_activos(cargo_id):
            match = evaluar(row["snapshot"], p, fecha)
            if match["compatible"]:
                estrictas[p.id] = estrictas.get(p.id, 0) + 1
                filas.append(fila(row, p, cargo_id, match["pruebas"]))
            elif row["snapshot"].get("_ampliacion") in AMPLIACIONES:
                ampliables.append((row, p, cargo_id))
    # Contrato v9: lo ampliado solo se asigna a perfiles que no llegaron al mínimo con vacantes que cumplen todo.
    for row, p, cargo_id in ampliables:
        nivel = row["snapshot"]["_ampliacion"]
        if estrictas.get(p.id, 0) >= MINIMO_POR_PERFIL:
            continue
        match = evaluar_ampliada(row["snapshot"], p, fecha, nivel)
        if match["compatible"]:
            estrictas[p.id] = estrictas.get(p.id, 0) + 1
            filas.append(fila(row, p, cargo_id, match["pruebas"], [{"ampliacion": nivel}]))
    for inicio in range(0, len(filas), 250):
        repo.pedir("POST", "panel_asignaciones", params={"on_conflict": "ejecucion_id,perfil_id,vacante_id"},
                    json=filas[inicio:inicio + 250], headers={"Prefer":"resolution=ignore-duplicates"})
    faltantes = {c.nombre: max(0, c.cupo - conteos.get(str(c.id), 0)) for c in cfg.cargos if c.activo}
    from buscador.validacion import errores_catalogo, errores
    confirmado = reporte is None or not (errores_catalogo(reporte) if reporte.get("modo") == "incremental" else errores(reporte))
    repo.pedir("PATCH", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"]},
        json={"estado": "parcial" if any(faltantes.values()) or not confirmado else "completa",
              "resumen": {"vacantes": sum(conteos.values()), "meta": 120, "faltantes": faltantes,
                          "asignaciones": len(filas),
                          "ampliadas": sum(any(isinstance(e, dict) and e.get("ampliacion") for e in f["explicacion"]) for f in filas),
                          "perfiles_bajo_minimo": sum(1 for c in cfg.cargos if c.activo for p in cfg.perfiles_activos(str(c.id))
                                                      if estrictas.get(p.id, 0) < MINIMO_POR_PERFIL),
                          **({"embudo": embudo} if (embudo := _embudo_por_nombre(reporte) or
                                                    (ejecucion.get("resumen") or {}).get("embudo")) else {})},
              "terminada_en": datetime.now().astimezone().isoformat()})


def correr(salida, modo="diario", prueba=False, repo=None):
    fecha = hoy()
    if prueba:
        return bodega.correr(salida, modo=modo, prueba=True)
    repo = repo or RepositorioSupabase()
    version = repo.operativa(fecha)
    if not version:
        return bodega.correr(salida, modo=modo)
    ejecucion = iniciar(repo, version, fecha)
    try:
        with activar(version, fecha):
            previas = bodega._leer_json(Path(salida) / "trabajo/bodega.json.gz", [])
            cargos = version["configuracion"]["cargos"]
            bodega._config_operativa["empresas_objetivo"] = sorted({v["empresa"] for v in previas
                if any(c["activo"] and grado(v["titulo"],c)[0] for c in cargos)})[:120]
            reporte = bodega.correr(salida, modo=modo, hoy=fecha)
            registrar(repo, version, fecha, reporte)
            if modo != "incremental":
                try:  # borradores de WhatsApp listos para revisar; un fallo aquí nunca tumba la búsqueda
                    from panel import borradores
                    borradores.generar(repo, fecha)
                except Exception:  # noqa: BLE001
                    pass
            return reporte
    except Exception:
        aviso = "La captura requiere revisión; se conserva su historial y pendientes."
        try:
            actual = (repo.pedir("GET", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"], "limit": 1}) or [{}])[0]
            if actual.get("estado") in ("parcial", "completa"):
                # Una pasada posterior fallida (mañana, cada hora) no borra el resultado ya registrado del día.
                cambio = {"resumen": {**(actual.get("resumen") or {}), "aviso_ultima_pasada": aviso}}
            else:
                cambio = {"estado": "fallida", "resumen": {"error": aviso}}
            repo.pedir("PATCH", "panel_ejecuciones", params={"id": "eq." + ejecucion["id"]}, json=cambio)
        except Exception:
            pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", required=True)
    parser.add_argument("--modo", choices=["diario", "incremental", "inicial"], default="diario")
    parser.add_argument("--prueba", action="store_true")
    parser.add_argument("--config", help="Versión ficticia para ensayo dirigido; requiere --prueba")
    args = parser.parse_args()
    if args.config:
        if not args.prueba: parser.error("--config requiere --prueba; producción lee únicamente Supabase")
        import json
        version = json.loads(Path(args.config).read_text())
        with activar(version,hoy()): bodega.correr(args.salida,modo=args.modo,prueba=True)
    else:
        correr(args.salida, args.modo, args.prueba)


if __name__ == "__main__":
    main()
