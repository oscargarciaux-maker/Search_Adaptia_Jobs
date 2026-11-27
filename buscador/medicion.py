"""Contrato v49: medición reproducible sobre una bodega guardada (`trabajo/bodega.json.gz`), sin datos de clientes.

Usa perfiles y cargos FICTICIOS (los cargos salen del mapa de cargos) para responder con cifras, antes y después de un
cambio: 1) ¿llegan vacantes de un país o una ciudad que el perfil no habilitó?; 2) ¿cuántas candidatas tiene alguien que
solo acepta español y solo remoto, y cuántas tienen el enlace comprobado?; 3) ¿cuántos títulos coinciden con el cargo
sin que las funciones lo respalden? Solo imprime conteos y títulos públicos de avisos.

    python -m buscador.medicion --bodega trabajo/bodega.json.gz

Sección 7 (objetivo mundial): `--mundial` mide 8 escenarios ficticios del modo panel por etapa y `--comparar
pruebas/datos/linea_base_mundial.json` compara con la línea base y falla si cambia el control (docs/LINEA_BASE_MUNDIAL.md).
"""
import argparse
import gzip
import hashlib
import json
from collections import Counter
from time import perf_counter
from uuid import NAMESPACE_DNS, uuid5

from buscador import paises

CARGOS = ("Product Designer", "Product Manager", "QA", "AI Product Manager", "Growth Marketing")
CIUDADES = {"CO": "Bogotá", "MX": "Ciudad de México", "AR": "Buenos Aires", "CL": "Santiago", "PE": "Lima",
            "ES": "Madrid"}


def _id(nombre):
    return str(uuid5(NAMESPACE_DNS, "adaptia.medicion." + nombre))


def cargo_crudo(nombre):
    """Un cargo como lo guardaría el panel con «Buscar denominaciones afines» (lo que acepta `panel.modelos.Cargo`)."""
    from panel.terminos import sugerir
    s = sugerir(nombre, consultar_esco=False)
    return {"id": _id(nombre), "nombre": nombre, "cupo": 20, "activo": True,
            "terminos_exactos": s["terminos_exactos"], "terminos_similares": s["terminos_similares"],
            "terminos_excluidos": [], "terminos_cercanos": [], "funciones": []}


def huella_ficticia(cargo, vacantes):
    """La huella de funciones que se calcularía esa noche para `cargo` con estas vacantes (contrato v49)."""
    from panel.contenido import huellas_automaticas
    return huellas_automaticas(vacantes, [cargo]).get(cargo["id"]) if vacantes else ()


def cargo_ficticio(nombre, vacantes=()):
    """Un cargo como lo dejaría el panel con «Buscar denominaciones afines», sin tocar nada guardado. Con `vacantes`,
    también con la huella de funciones que se calcularía esa noche (contrato v49)."""
    from panel.contenido import cargo_operativo
    cargo = cargo_crudo(nombre)
    return cargo_operativo(cargo, huella_auto=huella_ficticia(cargo, vacantes))


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


def _idioma(v):
    if len(v.get("_descripcion") or "") < 200:
        return "sin_descripcion"  # sin texto no se sabe el idioma y no se entrega
    return v.get("idioma") if v.get("idioma") in ("es", "en") else "otro"


def embudo_idioma(vacantes):
    """Contrato v50: por idioma del aviso y por fuente, cuántas vacantes de un cargo buscado hay guardadas y cuántas
    tienen el enlace comprobado (las que se pueden entregar hoy). `sin_descripcion`: no se sabe el idioma y no se
    entregan hasta leer su ficha. Conteos de avisos públicos, sin datos de clientes."""
    salida = {}
    for v in vacantes:
        if v.get("tipo") == "post" or not v.get("familias"):
            continue
        idioma = _idioma(v)
        fuente = (v.get("fuente") or "sin fuente").split(" (")[0]
        fila = salida.setdefault(idioma, {"con_cargo": 0, "comprobadas": 0, "fuentes": {}})
        por_fuente = fila["fuentes"].setdefault(fuente, {"con_cargo": 0, "comprobadas": 0})
        for d in (fila, por_fuente):
            d["con_cargo"] += 1
            d["comprobadas"] += _comprobada(v)
    return salida


def enlaces_de_la_corrida(cache, desde):
    """Contrato v51: los enlaces comprobados desde `desde` (instante ISO en UTC, como `tiempos.ahora()`), por sitio y
    resultado. El resumen de `verificar_enlaces.preparar` es de su última llamada y una corrida lo llama varias veces
    (lote, cola por persona, refuerzos): el reporte mostraba solo el último paso. Aquí se cuentan resultados guardados,
    no enlaces escogidos: uno que no alcanzó a abrirse no aparece. Los que valen por verse hoy en la búsqueda de su
    sitio van aparte (`vistas_en_busqueda`) y no entran en `comprobados` ni en `por_sitio`."""
    from buscador import contrato, enlaces
    from buscador.verificar_enlaces import VISTA_HOY
    por_sitio, vistas = {}, 0
    for url, r in (cache or {}).items():
        if not isinstance(r, dict) or str(r.get("comprobada_en") or "") < desde:
            continue
        if str(r.get("motivo") or "").startswith(VISTA_HOY):
            vistas += 1
            continue
        nombre = contrato.portal(url)  # un sitio que no es un portal conocido devuelve su propio dominio
        sitio = por_sitio.setdefault("Otros sitios" if nombre == enlaces.host(url) else nombre, Counter())
        sitio[r.get("estado") or "pendiente"] += 1
    return {"comprobados": sum(sum(c.values()) for c in por_sitio.values()), "vistas_en_busqueda": vistas,
            "por_sitio": {s: dict(c) for s, c in sorted(por_sitio.items(), key=lambda par: -sum(par[1].values()))}}


def medir(vacantes, hoy=None):
    hoy = hoy or max((v.get("visto_ultima_vez") or "")[:10] for v in vacantes)
    cargos = [cargo_ficticio(n, vacantes) for n in CARGOS]
    return {"fecha": hoy, "vacantes": len(vacantes), "embudo_idioma": embudo_idioma(vacantes),
            "fugas_de_ubicacion": fugas(vacantes, hoy),
            "solo_espanol_remoto": embudo_espanol(vacantes, hoy, cargos), "funciones": evidencias(vacantes, cargos)}


# ── Línea base del objetivo mundial (sección 7) ───────────────────────────────────────────────────────────────────
# Antes de quitar las restricciones LATAM/España/Brasil del código, se mide el comportamiento ACTUAL del modo panel con
# perfiles ficticios, para comparar después de cada sub-tarea (7.1–7.4). Solo conteos y tiempos: nunca títulos.
# Cada escenario es un cliente ficticio con un perfil por cada cargo de `CARGOS`, todos con el mismo lugar e idioma.

# LATAM tal como lo expande hoy el panel (`panel.revision.expandir(["LATAM"])`), escrito a mano para que el control no
# cambie si 7.x añade Brasil a la región.
LATAM_HOY = ["AR", "BO", "CL", "CO", "CR", "CU", "DO", "EC", "GT", "HN", "MX", "NI", "PA", "PE", "PR", "PY", "SV", "UY",
             "VE"]
ESCENARIOS = {
    "a": {"nombre": "Brasil, inglés, remoto mundial", "idiomas": ["en"],
          "filas": [{"paises": ["BR"], "modalidades": ["remoto"]}]},
    "b": {"nombre": "Brasil, inglés, presencial en São Paulo", "idiomas": ["en"],
          "filas": [{"paises": ["BR"], "ciudades": ["São Paulo"], "modalidades": ["presencial"]}]},
    "c": {"nombre": "EE. UU., solo español, remoto mundial", "idiomas": ["es"],
          "filas": [{"paises": ["US"], "modalidades": ["remoto"]}]},
    "d": {"nombre": "Colombia, solo inglés, remoto mundial", "idiomas": ["en"],
          "filas": [{"paises": ["CO"], "modalidades": ["remoto"]}]},
    "e": {"nombre": "Alemania, inglés, híbrido en Berlín", "idiomas": ["en"],
          "filas": [{"paises": ["DE"], "ciudades": ["Berlin"], "modalidades": ["hibrido"]}]},
    "f": {"nombre": "Kenia, inglés, remoto mundial (sin fuentes locales)", "idiomas": ["en"],
          "filas": [{"paises": ["KE"], "modalidades": ["remoto"]}]},
    "g": {"nombre": "India, inglés, remoto en su país", "idiomas": ["en"],
          "filas": [{"paises": ["IN"], "modalidades": ["remoto"]}]},
    "h": {"nombre": "Control: Colombia, español, remoto LATAM", "idiomas": ["es"],
          "filas": [{"paises": ["CO"], "modalidades": ["remoto"]}, {"paises": LATAM_HOY, "modalidades": ["remoto"]}]},
}
CONTROL = "h"
ETAPAS = ("objetivo", "limpiar", "entregable", "afinidad", "panel")
QUE_MIDE = {"objetivo": "del cargo, en un idioma del perfil y con un lugar que el objetivo mundial acepta",
            "limpiar": "de esas, siguen tras `bodega.limpiar`", "entregable": "y pasan `contrato.entregable`",
            "afinidad": "y `panel.afinidad.evaluar` las da por compatibles", "panel": "y `entrega.elegir` las ofrece"}
META_ESCENARIO = 100  # alta a propósito: que la meta del día no esconda dónde se pierden (5 perfiles × 100 = 500)
META_CONJUNTO = 15   # todos los escenarios juntos: 8 × 5 perfiles × 15 = 600, el techo máximo del panel


def _nombrados(v):
    return set(v.get("paises") or []) | set(v.get("paises_mundo") or [])


def lugar_objetivo(v, fila):
    """¿El objetivo mundial aceptaría esta vacante para esta fila? Regla propia y simple sobre las etiquetas ya
    guardadas en la bodega (no usa el código que la sección 7 va a cambiar, para que esta etapa quede fija):
    - remota: nombra un país de la fila, o es de alcance mundial sin nombrar países;
    - presencial o híbrida: la ubicación nombra una ciudad de la fila y no nombra solo otros países."""
    from buscador import normalizar
    modo = v.get("modalidad")
    if modo not in fila["modalidades"]:
        return False
    nombrados = _nombrados(v)
    if modo == "remoto":
        return bool(nombrados & set(fila["paises"])) or (bool(v.get("alcance_mundial")) and not v.get("paises_mundo"))
    if nombrados and not nombrados & set(fila["paises"]):
        return False
    texto = normalizar.texto(v.get("ubicacion") or "")
    return any(normalizar.contiene_frase(texto, normalizar.texto(c)) for c in fila.get("ciudades", []))


def encaja_objetivo(v, escenario, cargos):
    from panel.terminos import grado
    if v.get("tipo") == "post" or v.get("idioma") not in escenario["idiomas"]:
        return False
    if not any(lugar_objetivo(v, f) for f in escenario["filas"]):
        return False
    return any(grado(v.get("titulo") or "", c)[0] in ("exacto", "similar") for c in cargos)


def configuracion_ficticia(claves, crudos, meta):
    """Una versión del panel con un cliente ficticio y, por cada escenario, un perfil en cada cargo."""
    cliente = _id("cliente.mundial")
    campos = ("id", "nombre", "cupo", "activo", "terminos_exactos", "terminos_similares", "terminos_excluidos",
              "terminos_cercanos", "funciones")
    cargos = [{k: (c[k][:30] if isinstance(c[k], list) else c[k]) for k in campos} for c in crudos]
    perfiles = [{"id": _id(f"perfil.{clave}.{c['nombre']}"), "cliente_id": cliente, "cargo_id": c["id"],
                 "idiomas": ESCENARIOS[clave]["idiomas"], "antiguedad_dias": 30, "meta_diaria": meta,
                 "ubicaciones": ESCENARIOS[clave]["filas"]} for clave in claves for c in crudos]
    return {"revision": 0, "configuracion": {"clientes": [{"id": cliente, "nombre": "Cliente ficticio"}],
                                             "cargos": cargos, "perfiles": perfiles,
                                             "techo_diario": meta * len(perfiles)}}


def _correr_panel(texto, claves, crudos, huellas, hoy, meta):
    """Pasa la bodega (copia nueva desde `texto`) por el flujo real del modo panel con estos escenarios. Devuelve
    (vacantes tras limpiar, ids ofrecidos por `entrega.elegir`, segundos de limpiar y de la selección, perfiles)."""
    from buscador import bodega, entrega
    from panel import ejecutor
    from panel.modelos import Perfil
    version = configuracion_ficticia(claves, crudos, meta)
    with ejecutor.activar(version, hoy, huellas=huellas) as cfg:
        previas = json.loads(texto)
        t0 = perf_counter()
        limpias, _, _ = bodega.limpiar(previas, [], hoy, bodega.config()["dias_maximos"], set(), set())
        t1 = perf_counter()
        # La comprobación de enlaces depende de qué pidió cada noche cada cliente real: no se usa aquí (sería ruido).
        salida, _ = entrega.elegir(limpias, set(), hoy, cfg, omitir_verificacion=True)
        t2 = perf_counter()
        perfiles = [Perfil.model_validate(p) for p in version["configuracion"]["perfiles"]]
        return limpias, {v["id"] for lista in salida.values() for v, _ in lista}, (t1 - t0, t2 - t1), perfiles


def medir_mundial(texto, hoy=None):
    """Línea base del objetivo mundial sobre una bodega (`texto` = su JSON). Solo conteos y segundos."""
    from buscador import contrato
    from panel.afinidad import evaluar
    from panel.contenido import cargo_operativo
    vacantes = json.loads(texto)
    hoy = hoy or max((v.get("visto_ultima_vez") or "")[:10] for v in vacantes)
    crudos = [cargo_crudo(n) for n in CARGOS]
    huellas = {c["id"]: huella_ficticia(c, vacantes) for c in crudos}
    cargos = [cargo_operativo(c, huella_auto=huellas[c["id"]]) for c in crudos]
    salida = {"hoy": hoy, "vacantes": len(vacantes), "meta_por_perfil": META_ESCENARIO, "escenarios": {}}
    for clave, esc in ESCENARIOS.items():
        objetivo = {v["id"] for v in vacantes if encaja_objetivo(v, esc, cargos)}
        limpias, ofrecidas, (s_limpiar, s_elegir), perfiles = _correr_panel(texto, [clave], crudos, huellas, hoy,
                                                                             META_ESCENARIO)
        # Una vacante puede unirse a otra al limpiar: se sigue por su id o por los ids que absorbió.
        por_id = {i: v for v in limpias for i in (v["id"], *v.get("_ids_fusionados", []))}
        sigue = {por_id[i]["id"]: por_id[i] for i in objetivo if i in por_id}
        entregables = {i for i, v in sigue.items() if not contrato.entregable(v, ("es", "en"), panel=True)}
        compatibles = {i for i in entregables if evaluar(sigue[i], perfiles[0], hoy)["compatible"]}
        salida["escenarios"][clave] = {
            "nombre": esc["nombre"],
            "etapas": {"objetivo": len(objetivo), "limpiar": len(sigue), "entregable": len(entregables),
                       "afinidad": len(compatibles), "panel": len(ofrecidas & set(sigue))},
            # Lo que el panel ofrece fuera de la regla del objetivo (ampliaciones, lugares que la regla no reconoce).
            "panel_fuera_del_objetivo": len(ofrecidas - set(sigue)),
            "admitidas": len(limpias),
            "segundos": {"limpiar": round(s_limpiar, 2), "seleccion": round(s_elegir, 2)}}
    limpias, ofrecidas, (s_limpiar, s_elegir), _ = _correr_panel(texto, list(ESCENARIOS), crudos, huellas, hoy,
                                                                  META_CONJUNTO)
    salida["conjunto"] = {"meta_por_perfil": META_CONJUNTO, "admitidas": len(limpias), "ofrecidas": len(ofrecidas),
                          "segundos": {"limpiar": round(s_limpiar, 2), "seleccion": round(s_elegir, 2)}}
    return salida


def _cifras(r):
    """Los conteos que se comparan (los segundos se muestran pero no deciden nada: cambian con la máquina)."""
    return {**r["etapas"], "panel_fuera_del_objetivo": r["panel_fuera_del_objetivo"], "admitidas": r["admitidas"]}


def comparar(base, ahora):
    """(líneas de la tabla antes → después, el control cambió)."""
    def celda(a, d):
        return f"{a}" if a == d else f"{a}→{d} ({d - a:+d})"
    columnas = (*ETAPAS, "panel_fuera_del_objetivo", "admitidas")
    lineas = ["| escenario | " + " | ".join(columnas) + " | s limpiar | s selección |",
              "|---" * (len(columnas) + 3) + "|"]
    for clave, b in base["escenarios"].items():
        a = ahora["escenarios"].get(clave)
        if a is None:
            lineas.append(f"| {clave} | (falta en la medición nueva) |")
            continue
        cb, ca = _cifras(b), _cifras(a)
        tiempos = [f"{b['segundos'][k]}→{a['segundos'][k]}" for k in ("limpiar", "seleccion")]
        lineas.append(f"| {clave} {b['nombre']} | " + " | ".join(celda(cb[k], ca[k]) for k in columnas) + " | "
                      + " | ".join(tiempos) + " |")
    cb, ca = base.get("conjunto"), ahora.get("conjunto")
    if cb and ca:
        lineas.append(f"\nTodos juntos: admitidas {celda(cb['admitidas'], ca['admitidas'])}, ofrecidas "
                      f"{celda(cb['ofrecidas'], ca['ofrecidas'])}, s limpiar {cb['segundos']['limpiar']}→"
                      f"{ca['segundos']['limpiar']}, s selección {cb['segundos']['seleccion']}→"
                      f"{ca['segundos']['seleccion']}")
    control = ahora["escenarios"].get(CONTROL)
    cambio = control is None or _cifras(base["escenarios"][CONTROL]) != _cifras(control)
    return lineas, cambio


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bodega", required=True, help="trabajo/bodega.json.gz de una búsqueda")
    p.add_argument("--hoy", help="fecha de la medición (por defecto, la última en que se vio una vacante)")
    p.add_argument("--reetiquetar", action="store_true",
                   help="vuelve a leer país, modalidad e idioma con el código actual (como hará la próxima búsqueda)")
    p.add_argument("--mundial", action="store_true", help="línea base del objetivo mundial (escenarios a–h)")
    p.add_argument("--guardar", help="con --mundial: escribe la línea base en este archivo")
    p.add_argument("--commit", default="", help="con --guardar: SHA del commit de `publicado` de donde salió la bodega")
    p.add_argument("--comparar", help="línea base guardada: imprime antes → después y falla si cambia el control (h)")
    a = p.parse_args(argv)
    if a.mundial or a.comparar:
        with gzip.open(a.bodega, "rt", encoding="utf-8") as f:
            texto = f.read()
        sha = _sha256(a.bodega)
        if a.comparar:
            with open(a.comparar, encoding="utf-8") as f:
                base = json.load(f)
            if base["bodega"]["sha256"] != sha:
                print("La bodega no es la fijada en la línea base (sha256 distinto): la comparación no vale.")
                return 2
            lineas, cambio = comparar(base, medir_mundial(texto, a.hoy or base["hoy"]))
            print("\n".join(lineas))
            if cambio:
                print(f"\nFALLA: el escenario de control ({CONTROL}) cambió y debía quedar igual.")
                return 1
            print(f"\nEl escenario de control ({CONTROL}) no cambió.")
            return 0
        r = medir_mundial(texto, a.hoy)
        r = {"bodega": {"commit": a.commit, "sha256": sha, "vacantes": r["vacantes"]}, **r}
        salida = json.dumps(r, ensure_ascii=False, indent=1)
        if a.guardar:
            with open(a.guardar, "w", encoding="utf-8", newline="\n") as f:
                f.write(salida + "\n")
        print(salida)
        return 0
    with gzip.open(a.bodega, "rt", encoding="utf-8") as f:
        vacantes = json.load(f)
    if a.reetiquetar:
        from buscador import vacante
        vacantes = [vacante.reetiquetar(dict(v)) for v in vacantes]
    print(json.dumps(medir(vacantes, a.hoy), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
