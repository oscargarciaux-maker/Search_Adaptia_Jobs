"""Contrato v49: medición reproducible sobre una bodega guardada (`trabajo/bodega.json.gz`), sin datos de clientes.

Usa perfiles y cargos FICTICIOS (los cargos salen del mapa de cargos) para responder con cifras, antes y después de un
cambio: 1) ¿llegan vacantes de un país o una ciudad que el perfil no habilitó?; 2) ¿cuántas candidatas tiene alguien que
solo acepta español y solo remoto, y cuántas tienen el enlace comprobado?; 3) ¿cuántos títulos coinciden con el cargo
sin que las funciones lo respalden? Solo imprime conteos y títulos públicos de avisos.

    python -m buscador.medicion --bodega trabajo/bodega.json.gz
"""
import argparse
import gzip
import json
from collections import Counter
from uuid import NAMESPACE_DNS, uuid5

from buscador import paises

CARGOS = ("Product Designer", "Product Manager", "QA", "AI Product Manager", "Growth Marketing")
CIUDADES = {"CO": "Bogotá", "MX": "Ciudad de México", "AR": "Buenos Aires", "CL": "Santiago", "PE": "Lima",
            "ES": "Madrid"}


def _id(nombre):
    return str(uuid5(NAMESPACE_DNS, "adaptia.medicion." + nombre))


def cargo_ficticio(nombre, vacantes=()):
    """Un cargo como lo dejaría el panel con «Buscar denominaciones afines», sin tocar nada guardado. Con `vacantes`,
    también con la huella de funciones que se calcularía esa noche (contrato v49)."""
    from panel.contenido import cargo_operativo, huellas_automaticas
    from panel.terminos import sugerir
    s = sugerir(nombre, consultar_esco=False)
    cargo = {"id": _id(nombre), "nombre": nombre, "cupo": 20, "activo": True, "terminos_exactos": s["terminos_exactos"],
             "terminos_similares": s["terminos_similares"], "terminos_excluidos": [], "terminos_cercanos": [],
             "funciones": []}
    huella = huellas_automaticas(vacantes, [cargo]).get(cargo["id"]) if vacantes else ()
    return cargo_operativo(cargo, huella_auto=huella)


def perfil(pais, idiomas=("es", "en"), modalidades=("remoto",), ciudades=()):
    return {"id": _id(f"{pais}{idiomas}{modalidades}{ciudades}"), "cliente_id": _id("cliente"), "cargo_id": _id("cargo"),
            "idiomas": list(idiomas), "antiguedad_dias": 30,
            "ubicaciones": [{"paises": [pais], "ciudades": list(ciudades), "modalidades": list(modalidades)}]}


def nombra_otro_pais(v, pais):
    """El aviso nombra países y ninguno es `pais` (y no es de verdad para cualquier país): no debería llegarle."""
    nombrados = set(v.get("paises") or []) | set(v.get("paises_mundo") or [])
    return bool(nombrados) and pais not in nombrados and not paises.abiertos(v)[1]


def _entregable(v):
    return len(v.get("_descripcion") or "") >= 200 and v.get("idioma") in ("es", "en") and v.get("tipo") != "post"


def _comprobada(v):
    return (v.get("verificacion") or {}).get("estado") == "verificada"


def fugas(vacantes, hoy, ejemplos=5):
    """Por país: compatibles para un perfil remoto que nombran otro país, y presenciales/híbridas fuera de su ciudad."""
    from panel.afinidad import en_sus_ciudades, evaluar
    salida = {}
    utiles = [v for v in vacantes if _entregable(v)]
    for pais, ciudad in CIUDADES.items():
        remoto, oficina = perfil(pais), perfil(pais, modalidades=("hibrido", "presencial"), ciudades=(ciudad,))
        remotas = [v for v in utiles if evaluar(v, remoto, hoy)["compatible"]]
        otro_pais = [v for v in remotas if nombra_otro_pais(v, pais)]
        locales = [v for v in utiles if v.get("modalidad") in ("hibrido", "presencial")
                   and evaluar(v, oficina, hoy)["compatible"]]
        otra_ciudad = [v for v in locales if nombra_otro_pais(v, pais) or not en_sus_ciudades(v, [ciudad])]
        salida[pais] = {"remotas_compatibles": len(remotas), "remotas_de_otro_pais": len(otro_pais),
                        "oficinas_fuera_de_su_ciudad": len(otra_ciudad),
                        "oficinas_en_su_ciudad": len(locales) - len(otra_ciudad),
                        "ejemplos": [f"{v['titulo'][:50]} | {(v.get('ubicacion') or '')[:40]}"
                                     for v in (otro_pais + otra_ciudad)[:ejemplos]]}
    return salida


def embudo_espanol(vacantes, hoy, cargos):
    """Por cargo y país, para quien solo acepta español y solo remoto: del cargo → con descripción → en español →
    ubicación e idioma compatibles → con enlace comprobado."""
    from panel.afinidad import evaluar
    from panel.terminos import grado
    salida = {}
    for cargo in cargos:
        del_cargo = [v for v in vacantes if v.get("titulo") and v.get("tipo") != "post"
                     and grado(v["titulo"], cargo)[0] in ("exacto", "similar")]
        con_texto = [v for v in del_cargo if len(v.get("_descripcion") or "") >= 200]
        en_es = [v for v in con_texto if v.get("idioma") == "es"]
        fila = {"del_cargo": len(del_cargo), "con_descripcion": len(con_texto), "en_espanol": len(en_es), "paises": {}}
        for pais in CIUDADES:
            p = perfil(pais, idiomas=("es",))
            sirven = [v for v in en_es if evaluar(v, p, hoy)["compatible"]]
            fila["paises"][pais] = {"compatibles": len(sirven), "comprobadas": sum(map(_comprobada, sirven))}
        salida[cargo["nombre"]] = fila
    return salida


def evidencias(vacantes, cargos, ejemplos=6):
    """Por cargo: cuántos títulos que coinciden tienen las funciones del cargo en la descripción (contrato v49)."""
    from panel.contenido import evidencia
    from panel.terminos import grado
    salida = {}
    for cargo in cargos:
        fila = {"huella": len(cargo["funciones"])}
        for idioma in ("es", "en"):
            niveles, dudosos = Counter(), []
            for v in vacantes:
                if not _entregable(v) or v["idioma"] != idioma \
                        or grado(v.get("titulo") or "", cargo)[0] not in ("exacto", "similar"):
                    continue
                e = evidencia(v["titulo"], v["_descripcion"], cargo)
                niveles["otro_oficio" if e["otro_oficio"] else e["nivel"]] += 1
                niveles["sin_distintivo"] += bool(e["falta_distintivo"])
                if e["otro_oficio"] and len(dudosos) < ejemplos:
                    dudosos.append(f"{v['titulo'][:60]} [{e['senal']}]")
            fila[idioma] = {**dict(niveles), "ejemplos_otro_oficio": dudosos}
        salida[cargo["nombre"]] = fila
    return salida


def medir(vacantes, hoy=None):
    hoy = hoy or max((v.get("visto_ultima_vez") or "")[:10] for v in vacantes)
    cargos = [cargo_ficticio(n, vacantes) for n in CARGOS]
    return {"fecha": hoy, "vacantes": len(vacantes), "fugas_de_ubicacion": fugas(vacantes, hoy),
            "solo_espanol_remoto": embudo_espanol(vacantes, hoy, cargos), "funciones": evidencias(vacantes, cargos)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bodega", required=True, help="trabajo/bodega.json.gz de una búsqueda")
    p.add_argument("--hoy", help="fecha de la medición (por defecto, la última en que se vio una vacante)")
    p.add_argument("--reetiquetar", action="store_true",
                   help="vuelve a leer país, modalidad e idioma con el código actual (como hará la próxima búsqueda)")
    a = p.parse_args()
    with gzip.open(a.bodega, "rt", encoding="utf-8") as f:
        vacantes = json.load(f)
    if a.reetiquetar:
        from buscador import vacante
        vacantes = [vacante.reetiquetar(dict(v)) for v in vacantes]
    print(json.dumps(medir(vacantes, a.hoy), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
