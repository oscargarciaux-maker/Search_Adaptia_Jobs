"""Detalle por cargo del estado de trabajo: privado en Supabase, nunca en la rama pública `publicado`.

Auditoría de exposición (27 nov, hallazgos #2 y #4; decisión de Oscar: Supabase). La rama `publicado`, los artefactos
y el resumen de cada corrida de Actions se ven desde fuera porque el repositorio es público. Ahí queda solo lo
agregado (totales del día, por fuente, por idioma, estado COMPLETA/CORTA/AVERÍA). El resto lo necesita la siguiente
corrida y vive en la tabla privada `estado_trabajo` (SQL 022):

- archivos enteros: el lote del día, las vacantes ya entregadas, la rotación de búsquedas (claves cargo@país) y las
  colas de reintento (`PRIVADOS`);
- versión completa de lo que se publica recortado: las métricas de entrega por cargo y el reporte (`DIVIDIDOS`);
- en la bodega (`trabajo/bodega.json.gz`), a qué cargo va cada vacante (`rol_entrega_actual`) y sus familias propias
  de cargo del panel (`familias` con `cargo:<id>`): se quitan de lo publicado y se reponen al empezar.

`guardar` corre antes de publicar y de subir el artefacto: separa, recorta y sube todo en una sola escritura (una
transacción), con su manifiesto. `traer` corre después de clonar `publicado` y deja la carpeta como antes de este
cambio, así el resto del código no cambia. La marca pública `trabajo/estado_privado.json` solo dice que el estado está
en Supabase; sin ella (rama anterior a este cambio) se usa lo que trae la rama. Con ella, si Supabase no devuelve un
estado completo y de una sola corrida, la corrida se detiene: nunca sigue con el estado vacío o mezclado, porque
elegiría otra entrega del mismo día.

El reporte público se arma con lista blanca (`CAMPOS_REPORTE`): un campo nuevo del reporte no se publica hasta que
alguien decide cómo (la prueba `test_estado_privado.py` falla si `bodega.correr` emite uno sin clasificar).
"""
import argparse
import base64
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time

import requests

from buscador import supabase

PRIVADOS = ("trabajo/lote_entrega.json", "trabajo/entregadas.json", "trabajo/estado.json",
            "trabajo/pendientes_catalogo.json", "trabajo/pendientes_supabase.json", "trabajo/pendientes_registro.json")
DIVIDIDOS = ("trabajo/metricas_entrega.json", "datos/salud.json", "datos/salud_bodega.json")
BODEGA = "trabajo/bodega.json.gz"
CARGOS_BODEGA = "trabajo/cargos_bodega.json"   # solo en Supabase: {"roles": {id: rol}, "familias": {id: [...]}}
MARCA = "trabajo/estado_privado.json"          # pública en la rama; también en Supabase como manifiesto
TABLA = "estado_trabajo"
CAMPO_ROL = "rol_entrega_actual"
FORMATO = 1
COPIA = "privado/estado_trabajo"               # copia completa local, fuera de lo publicado (validación del trabajo)

# Identificador de cargo del panel: «cargo:…» o un UUID al inicio de la clave (también «<UUID>@país»).
_ID_CARGO = re.compile(r"^(cargo:|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)
CAMPOS_ENTREGA = ("fecha", "vacantes", "vacantes_unicas", "copias_en_lote", "enlaces_comprobados", "filas",
                  "archivos", "meta_cumplida", "supabase", "registro_seleccion", "descartadas")
SUMABLES = ("candidatas", "entregadas", "unicas", "duplicadas", "faltan", "faltan_para_minimo", "remotas",
            "remotas_amplias", "perfiles_bajo_minimo", "reserva_sin_entregar")


# ---------------------------------------------------------------- versión pública (solo cifras agregadas)

def _sin_cargos(valor):
    """Segunda red: quita, en cualquier nivel, las entradas cuya clave es un identificador de cargo del panel, y deja
    de cada «error» solo el tipo (el texto puede traer una URL con los términos de búsqueda de un cargo)."""
    if isinstance(valor, dict):
        return {k: (v.split(":", 1)[0] if k == "error" and isinstance(v, str) else _sin_cargos(v))
                for k, v in valor.items() if not _ID_CARGO.search(str(k))}
    if isinstance(valor, list):
        return [_sin_cargos(v) for v in valor]
    return valor


def _sumar(destino, origen):
    for k, v in (origen or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            destino[k] += v


def _entero(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _sin_roles(registro):
    return {k: v for k, v in registro.items() if k != "roles"} if isinstance(registro, dict) else registro


def entrega_publica(entrega):
    if not isinstance(entrega, dict):
        return entrega
    salida = {k: entrega[k] for k in CAMPOS_ENTREGA if k in entrega}
    roles = [r for r in (entrega.get("roles") or {}).values() if isinstance(r, dict)]
    totales, idiomas, fuentes = Counter(), Counter(), Counter()
    for r in roles:
        _sumar(totales, {k: r.get(k) for k in SUMABLES})
        _sumar(idiomas, r.get("idiomas"))
        _sumar(fuentes, r.get("fuentes"))
    metas = entrega.get("metas_por_rol") or {}
    totales["meta"] = sum(_entero(m) for m in metas.values()) if isinstance(metas, dict) else 0
    salida.update(cargos=len(roles), totales=dict(totales), por_idioma=dict(idiomas), por_fuente=dict(fuentes))
    return salida


def seleccion_publica(seleccion):
    seleccion = seleccion if isinstance(seleccion, dict) else {}
    roles = [r for r in (seleccion.get("roles") or {}).values() if isinstance(r, dict)]
    return {"fecha": seleccion.get("fecha"), "cargos": len(roles),
            "vacantes": sum(len(r.get("vacantes") or []) for r in roles)}


def refuerzos_publicos(refuerzos):
    return [dict(r, faltantes_antes=sum(_entero(n) for n in (r.get("faltantes_antes") or {}).values()))
            if isinstance(r, dict) else r for r in refuerzos or []]


def resultado_del_dia(reporte):
    """COMPLETA, CORTA o AVERÍA (contrato v52) de una búsqueda diaria; vacío en capturas y búsquedas profundas."""
    if not isinstance(reporte, dict) or reporte.get("modo") == "incremental" or reporte.get("consulta"):
        return ""
    from buscador import validacion
    try:
        return validacion.NOMBRE_ESTADO[validacion.estado(reporte)]
    except Exception as e:  # noqa: BLE001 — un reporte incompleto no impide guardar el estado; queda el aviso
        print(f"::warning::No se pudo calcular el resultado del día para el reporte público ({type(e).__name__}).")
        return ""


_IGUAL = _sin_cargos
# Lista blanca del reporte público. Lo que no está aquí no se publica (y queda nombrado en `campos_no_publicados`).
CAMPOS_REPORTE = {
    **{k: _IGUAL for k in ("fecha", "hora_utc", "modo", "codigo_commit", "ejecucion_id", "pais", "minutos",
                           "vacantes_en_bodega", "crudas_hoy", "nuevas_hoy", "fuentes", "descartes", "por_familia",
                           "por_pais", "por_fuente", "por_modalidad", "ubicacion_por_confirmar", "catalogo",
                           "capturada_en", "frescura", "embudo_idioma", "verificacion_enlaces", "estado_operativo",
                           "apify")},  # 8.2: gasto y rendimiento de Apify, solo cifras del día y del mes
    "consulta": lambda v: "(privada)" if v else "",   # texto de una búsqueda profunda: puede ser el nombre de un cargo
    "entrega": lambda v: _sin_cargos(entrega_publica(v)),
    "seleccion_actual": seleccion_publica,
    "refuerzos": lambda v: _sin_cargos(refuerzos_publicos(v)),
    "historico_entregas": lambda v: [_sin_cargos(_sin_roles(d)) for d in v or []],
}


def salud_publica(reporte):
    if not isinstance(reporte, dict):
        return {}
    publico = {k: recortar(reporte[k]) for k, recortar in CAMPOS_REPORTE.items() if k in reporte}
    publico["resultado"] = resultado_del_dia(reporte)
    publico["detalle_por_cargo"] = f"privado: Supabase, tabla {TABLA}"
    publico["campos_no_publicados"] = sorted(k for k in reporte if k not in CAMPOS_REPORTE)
    return publico


def metricas_publicas(historial):
    """Lo que leen el arranque, el vigía y el reloj (fechas y banderas del día), sin el reparto por cargo."""
    if not isinstance(historial, dict):
        return {}
    return {dia: _sin_roles(registro) for dia, registro in historial.items()}


PUBLICAR = {"trabajo/metricas_entrega.json": metricas_publicas, "datos/salud.json": salud_publica,
            "datos/salud_bodega.json": salud_publica}


def resumen(salud):
    """Markdown para el resumen público de la corrida, desde el reporte ya recortado."""
    e = salud.get("entrega") or {}
    t = e.get("totales") or {}
    lineas = [f"Vacantes en la bodega: {salud.get('vacantes_en_bodega')} · nuevas hoy: {salud.get('nuevas_hoy')} · "
              f"{salud.get('minutos')} min", ""]
    lineas += [f"- {nombre}: {datos}" for nombre, datos in (salud.get("fuentes") or {}).items()]
    lineas += ["", f"Selección del día: {e.get('vacantes', 0)} vacantes, {e.get('filas', 0)} filas en {e.get('cargos', 0)} "
               f"cargos · meta total {t.get('meta', 0)}, faltan {t.get('faltan', 0)} · Supabase: {e.get('supabase')}",
               f"Por idioma: {e.get('por_idioma', {})} · por fuente: {e.get('por_fuente', {})}",
               f"Verificación de enlaces: {salud.get('verificacion_enlaces', {})}", ""]
    if (salud.get("apify") or {}).get("mes"):
        from buscador import medicion_apify
        lineas += [medicion_apify.linea(totales=salud["apify"]["mes"]), ""]
    return "\n".join(lineas) + "\n"


# ---------------------------------------------------------------- archivos

def _escribir_bytes(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_bytes(datos)
    temporal.replace(ruta)


def _json_bytes(datos):
    return json.dumps(datos, ensure_ascii=False, indent=1).encode("utf-8")


def _leer_bodega(ruta):
    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        return json.load(f)


def _escribir_bodega(ruta, vacantes):
    """Mismo formato que `buscador.bodega._guardar_json(..., comprimido=True)`, sin cargar las fuentes."""
    temporal = ruta.with_name(ruta.name + ".tmp")
    with gzip.open(temporal, "wt", encoding="utf-8") as f:
        json.dump(vacantes, f, ensure_ascii=False, separators=(",", ":"))
    temporal.replace(ruta)


def _es_de_cargo(familia):
    return isinstance(familia, dict) and bool(_ID_CARGO.search(str(familia.get("familia", ""))))


def separar(salida, copia=None):
    """Recorta `salida` a su versión pública y devuelve {archivo: bytes} con lo privado. `copia` (fuera de lo que se
    publica) recibe los archivos completos, para los pasos del mismo trabajo que necesitan el detalle.
    Todo se calcula antes de tocar nada: si algo no se puede leer, la carpeta queda como estaba y el error sube."""
    salida = Path(salida)
    privados = {rel: (salida / rel).read_bytes() for rel in PRIVADOS + DIVIDIDOS if (salida / rel).is_file()}
    publicos = {rel: _json_bytes(recortar(json.loads(privados[rel].decode("utf-8"))))
                for rel, recortar in PUBLICAR.items() if rel in privados}
    ruta_bodega = salida / BODEGA
    vacantes = _leer_bodega(ruta_bodega) if ruta_bodega.is_file() else None
    bodega_publica = None
    if vacantes is not None:
        if not (isinstance(vacantes, list) and all(isinstance(v, dict) and "id" in v for v in vacantes)):
            # Sin id no se puede reponer lo quitado: mejor no publicar que publicar el detalle o perderlo.
            raise RuntimeError("La bodega no tiene el formato esperado (lista de vacantes con id); no se publica.")
        cargos = {"roles": {v["id"]: v[CAMPO_ROL] for v in vacantes if CAMPO_ROL in v},
                  "familias": {v["id"]: v["familias"] for v in vacantes
                               if isinstance(v.get("familias"), list) and any(map(_es_de_cargo, v["familias"]))}}
        privados[CARGOS_BODEGA] = json.dumps(cargos, ensure_ascii=False, separators=(",", ":")).encode()
        bodega_publica = []
        for v in vacantes:
            v = {k: x for k, x in v.items() if k != CAMPO_ROL}
            if isinstance(v.get("familias"), list):
                v["familias"] = [f for f in v["familias"] if not _es_de_cargo(f)]
            bodega_publica.append(v)
    if copia is not None:
        for rel, datos in privados.items():
            _escribir_bytes(Path(copia) / rel, datos)
    for rel in PRIVADOS:
        (salida / rel).unlink(missing_ok=True)
    for temporal in salida.rglob("*.tmp"):   # una escritura cortada (tope de tiempo) dejaría el detalle a la vista
        temporal.unlink()
    for rel, datos in publicos.items():
        _escribir_bytes(salida / rel, datos)
    if bodega_publica is not None:
        _escribir_bodega(ruta_bodega, bodega_publica)
    return privados


def reponer(salida, privados):
    """Lo inverso de `separar`: deja `salida` como la dejó la corrida anterior antes de recortarla."""
    salida = Path(salida)
    for rel, datos in privados.items():
        if rel not in (CARGOS_BODEGA, MARCA):
            _escribir_bytes(salida / rel, datos)
    ruta_bodega = salida / BODEGA
    if CARGOS_BODEGA in privados and ruta_bodega.is_file():
        cargos = json.loads(privados[CARGOS_BODEGA].decode("utf-8"))
        vacantes = _leer_bodega(ruta_bodega)
        for v in vacantes:
            if v["id"] in cargos["familias"]:
                v["familias"] = cargos["familias"][v["id"]]
            if v["id"] in cargos["roles"]:
                v[CAMPO_ROL] = cargos["roles"][v["id"]]
        _escribir_bodega(ruta_bodega, vacantes)


# ---------------------------------------------------------------- Supabase (REST con la clave de servicio)

def _conexion():
    url, clave = supabase.credenciales()
    if not url or not clave:
        return None, None
    return url, supabase.cabeceras(clave)


def _empacar(datos):
    return base64.b64encode(gzip.compress(datos, mtime=0)).decode("ascii")


def _desempacar(fila):
    datos = gzip.decompress(base64.b64decode(fila["contenido"]))
    if hashlib.sha256(datos).hexdigest() != fila["sha256"]:
        raise RuntimeError(f"El estado privado {fila['archivo']} no coincide con su huella; no se usará.")
    return datos


def _pedir(hacer, que, pausa=5):
    """Tres intentos ante fallos de red o del servidor (5xx); un 4xx no se repite. Devuelve la respuesta 2xx o 404."""
    for intento in range(3):
        try:
            r = hacer()
        except requests.RequestException as e:
            causa = type(e).__name__
        else:
            if 200 <= r.status_code < 300 or r.status_code == 404:
                return r
            causa = f"HTTP {r.status_code}"
            if r.status_code < 500:
                break
        if intento < 2:
            time.sleep(pausa)
    raise RuntimeError(f"No se pudo {que} en Supabase ({causa}).")


def subir(grupo, privados, ejecucion, sesion=None, pausa=5):
    """Una sola escritura: PostgREST inserta el arreglo en una transacción, así nunca queda la mitad de una corrida."""
    url, cabeceras = _conexion()
    if not url:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY: no se puede guardar el estado privado.")
    sesion = sesion or requests.Session()
    filas = [{"grupo": grupo, "archivo": rel, "contenido": _empacar(datos),
              "sha256": hashlib.sha256(datos).hexdigest(), "ejecucion": ejecucion}
             for rel, datos in sorted(privados.items())]
    cabeceras = dict(cabeceras, Prefer="resolution=merge-duplicates,return=minimal")
    r = _pedir(lambda: sesion.post(f"{url}/rest/v1/{TABLA}?on_conflict=grupo,archivo", json=filas,
                                   headers=cabeceras, timeout=300), "guardar el estado privado", pausa)
    if r.status_code == 404:
        raise RuntimeError("Falta la tabla estado_trabajo (SQL 022): «Preparar Supabase» la instala. No se publica.")


def leer(grupo="vigente", sesion=None, pausa=5):
    """{archivo: (bytes, ejecucion)}; None si la tabla aún no existe (SQL 022 sin aplicar) o faltan credenciales."""
    url, cabeceras = _conexion()
    if not url:
        return None
    sesion = sesion or requests.Session()
    r = _pedir(lambda: sesion.get(f"{url}/rest/v1/{TABLA}", headers=cabeceras, timeout=300,
                                  params={"select": "archivo,contenido,sha256,ejecucion", "grupo": "eq." + grupo}),
               "leer el estado privado", pausa)
    if r.status_code == 404:
        return None
    filas = r.json()
    if not isinstance(filas, list):
        raise RuntimeError("Supabase devolvió el estado privado en un formato inesperado.")
    return {f["archivo"]: (_desempacar(f), f.get("ejecucion", "")) for f in filas}


# ---------------------------------------------------------------- pasos del flujo

def guardar(salida, copia, grupo="vigente", ejecucion="", sesion=None):
    salida = Path(salida)
    if copia is not None and Path(copia).exists():
        shutil.rmtree(copia)
    privados = separar(salida, copia)
    if not privados:
        return []
    marca = _json_bytes({"formato": FORMATO, "ejecucion": ejecucion, "archivos": sorted(privados),
                         "donde": f"Supabase, tabla {TABLA} (privada)"})
    subir(grupo, {**privados, MARCA: marca}, ejecucion, sesion=sesion)
    if grupo == "vigente":
        _escribir_bytes(salida / MARCA, marca)   # solo una corrida que sigue hacia «Publicar» la deja en la rama
    return sorted(privados)


def traer(salida, sesion=None):
    """Devuelve un mensaje para el registro (sin datos). Lanza error si la marca existe y el estado no está completo."""
    salida = Path(salida)
    if not (salida / MARCA).is_file():
        return "La rama publicado aún no separa el estado privado: se usa lo que trae."
    publicada = json.loads((salida / MARCA).read_text(encoding="utf-8"))
    guardados = leer("vigente", sesion=sesion)
    if not guardados or MARCA not in guardados:
        raise RuntimeError("La rama publicado dice que el estado privado está en Supabase, pero no se puede leer "
                           "(credenciales, tabla estado_trabajo o manifiesto). No se continúa con el estado vacío. "
                           "Ver docs/OPERACION_Y_RECUPERACION.md.")
    # El manifiesto de Supabase manda: se escribió en la misma transacción que los archivos.
    manifiesto = json.loads(guardados[MARCA][0].decode("utf-8"))
    ejecucion = manifiesto.get("ejecucion", "")
    incompletos = [rel for rel in manifiesto.get("archivos", [])
                   if rel not in guardados or guardados[rel][1] != ejecucion]
    if incompletos:
        raise RuntimeError(f"El estado privado de Supabase está incompleto o mezclado ({len(incompletos)} archivos). "
                           "No se continúa. Ver docs/OPERACION_Y_RECUPERACION.md.")
    reponer(salida, {rel: guardados[rel][0] for rel in manifiesto["archivos"]})
    if ejecucion != publicada.get("ejecucion", ""):
        return ("Aviso: el estado privado es de una corrida posterior a la rama publicado (¿falló la publicación "
                "después de guardarlo?). Se usa el de Supabase, que es el más reciente.")
    return f"Estado privado recuperado de Supabase: {len(manifiesto['archivos'])} archivos."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["traer", "guardar", "resumen"])
    ap.add_argument("--salida", required=True)
    ap.add_argument("--copia", default=COPIA, help="guardar: carpeta fuera de lo publicado con los archivos completos")
    ap.add_argument("--fallida", action="store_true",
                    help="guardar: la corrida falló; se guarda aparte (grupo «fallida») y la siguiente no lo lee")
    a = ap.parse_args()
    if a.accion == "resumen":
        ruta = Path(a.salida) / "datos/salud.json"
        if ruta.is_file():
            print(resumen(json.loads(ruta.read_text(encoding="utf-8"))))
        return
    if a.accion == "traer":
        mensaje = traer(a.salida)
        print(("::warning::" if mensaje.startswith("Aviso") else "") + mensaje)
        return
    grupo = "fallida" if a.fallida else "vigente"
    archivos = guardar(a.salida, a.copia, grupo, os.environ.get("GITHUB_RUN_ID", ""))
    print(f"Estado privado guardado en Supabase ({grupo}): {len(archivos)} archivos. "
          "La rama publicado y el artefacto quedan solo con cifras agregadas.")


if __name__ == "__main__":
    main()
