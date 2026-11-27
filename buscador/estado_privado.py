"""Detalle por cargo del estado de trabajo: privado en Supabase, nunca en la rama pública `publicado`.

Auditoría de exposición (27 nov, hallazgos #2 y #4; decisión de Oscar: Supabase). La rama `publicado` y los artefactos
de Actions se ven desde fuera porque el repositorio es público. Ahí queda solo lo agregado (totales del día, por
fuente, por idioma, estado COMPLETA/CORTA/AVERÍA). El resto lo necesita la siguiente corrida y vive en la tabla
privada `estado_trabajo` (SQL 022):

- archivos enteros: el lote del día, las vacantes ya entregadas, la rotación de búsquedas (claves cargo@país) y las
  colas de reintento (`PRIVADOS`);
- versión completa de lo que se publica recortado: las métricas de entrega por cargo y el reporte (`DIVIDIDOS`);
- en la bodega (`trabajo/bodega.json.gz`), a qué cargo va cada vacante (`rol_entrega_actual`) y sus familias propias
  de cargo del panel (`familias` con `cargo:<id>`): se quitan de lo publicado y se reponen al empezar.

`traer` corre justo después de clonar `publicado` y deja la carpeta como antes de este cambio, así el resto del código
no cambia. `guardar` corre antes de publicar y de subir el artefacto: separa, sube y recorta. La marca pública
`trabajo/estado_privado.json` dice qué archivos guardó la última corrida publicada; sin ella (rama anterior a este
cambio) se usa lo que trae la rama. Con ella, si Supabase no los devuelve, la corrida se detiene: nunca sigue con el
estado vacío, porque elegiría otra entrega del mismo día.
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

import requests

from buscador import supabase

PRIVADOS = ("trabajo/lote_entrega.json", "trabajo/entregadas.json", "trabajo/estado.json",
            "trabajo/pendientes_catalogo.json", "trabajo/pendientes_supabase.json", "trabajo/pendientes_registro.json")
DIVIDIDOS = ("trabajo/metricas_entrega.json", "datos/salud.json", "datos/salud_bodega.json")
BODEGA = "trabajo/bodega.json.gz"
CARGOS_BODEGA = "trabajo/cargos_bodega.json"   # solo en Supabase: {"roles": {id: rol}, "familias": {id: [...]}}
MARCA = "trabajo/estado_privado.json"
TABLA = "estado_trabajo"
CAMPO_ROL = "rol_entrega_actual"
FORMATO = 1

# Identificadores de cargo del panel: «cargo:<UUID>» o el UUID solo (también como prefijo de «…@país»).
_ID_CARGO = re.compile(r"(^|cargo:)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|^cargo:", re.I)
CAMPOS_ENTREGA = ("fecha", "vacantes", "vacantes_unicas", "copias_en_lote", "enlaces_comprobados", "filas",
                  "archivos", "meta_cumplida", "supabase", "registro_seleccion", "descartadas")
SUMABLES = ("candidatas", "entregadas", "unicas", "duplicadas", "faltan", "remotas", "remotas_amplias",
            "perfiles_bajo_minimo", "reserva_sin_entregar")


# ---------------------------------------------------------------- versión pública (solo cifras agregadas)

def _sin_cargos(valor):
    """Quita, en cualquier nivel, las entradas cuya clave es un identificador de cargo del panel."""
    if isinstance(valor, dict):
        return {k: _sin_cargos(v) for k, v in valor.items() if not _ID_CARGO.search(str(k))}
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


def resultado_del_dia(reporte):
    """COMPLETA, CORTA o AVERÍA (contrato v52) de una búsqueda diaria; vacío en capturas y búsquedas profundas."""
    if not isinstance(reporte, dict) or reporte.get("modo") == "incremental" or reporte.get("consulta"):
        return ""
    from buscador import validacion
    try:
        estado = validacion.estado(reporte, validacion.errores(reporte), validacion.cortos(reporte))
    except Exception:  # noqa: BLE001 — un reporte incompleto no debe impedir guardar el estado
        return ""
    return validacion.NOMBRE_ESTADO[estado]


def salud_publica(reporte):
    if not isinstance(reporte, dict):
        return reporte
    publico = dict(reporte)
    seleccion = reporte.get("seleccion_actual") or {}
    roles = (seleccion.get("roles") or {}) if isinstance(seleccion, dict) else {}
    publico["seleccion_actual"] = {"fecha": seleccion.get("fecha") if isinstance(seleccion, dict) else None,
                                   "cargos": len(roles),
                                   "vacantes": sum(len(r.get("vacantes") or []) for r in roles.values()
                                                   if isinstance(r, dict))}
    publico["entrega"] = entrega_publica(reporte.get("entrega"))
    publico["historico_entregas"] = [{k: v for k, v in d.items() if k != "roles"} if isinstance(d, dict) else d
                                     for d in reporte.get("historico_entregas") or []]
    publico["refuerzos"] = [dict(r, faltantes_antes=sum(_entero(n) for n in (r.get("faltantes_antes") or {}).values()))
                            if isinstance(r, dict) else r for r in reporte.get("refuerzos") or []]
    if reporte.get("consulta"):
        publico["consulta"] = "(privada)"   # el texto de una búsqueda profunda puede ser el nombre de un cargo
    publico["resultado"] = resultado_del_dia(reporte)
    publico["detalle_por_cargo"] = "privado: Supabase, tabla estado_trabajo"
    return _sin_cargos(publico)


def metricas_publicas(historial):
    """Lo que leen el arranque, el vigía y el reloj (fechas y banderas del día), sin el reparto por cargo."""
    if not isinstance(historial, dict):
        return historial
    return {dia: ({k: v for k, v in registro.items() if k != "roles"} if isinstance(registro, dict) else registro)
            for dia, registro in historial.items()}


PUBLICAR = {"trabajo/metricas_entrega.json": metricas_publicas, "datos/salud.json": salud_publica,
            "datos/salud_bodega.json": salud_publica}


# ---------------------------------------------------------------- archivos

def _escribir_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(ruta)


def _escribir_bytes(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_bytes(datos)
    temporal.replace(ruta)


def _es_de_cargo(familia):
    return isinstance(familia, dict) and bool(_ID_CARGO.search(str(familia.get("familia", ""))))


def _leer_bodega(ruta):
    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        return json.load(f)


def _escribir_bodega(ruta, vacantes):
    """Mismo formato que `buscador.bodega._guardar_json(..., comprimido=True)`, sin cargar las fuentes."""
    temporal = ruta.with_name(ruta.name + ".tmp")
    with gzip.open(temporal, "wt", encoding="utf-8") as f:
        json.dump(vacantes, f, ensure_ascii=False, separators=(",", ":"))
    temporal.replace(ruta)


def separar(salida, copia=None):
    """Recorta `salida` a su versión pública y devuelve {archivo: bytes} con lo privado. `copia` (fuera de lo que se
    publica) recibe los archivos completos, para los pasos del mismo trabajo que necesitan el detalle."""
    salida = Path(salida)
    privados = {}
    for rel in PRIVADOS + DIVIDIDOS:
        ruta = salida / rel
        if ruta.is_file():
            privados[rel] = ruta.read_bytes()
    ruta_bodega = salida / BODEGA
    vacantes = _leer_bodega(ruta_bodega) if ruta_bodega.is_file() else None
    if vacantes is not None and not (isinstance(vacantes, list) and all(isinstance(v, dict) and "id" in v
                                                                        for v in vacantes)):
        # Sin id no se puede reponer lo quitado: mejor no publicar que publicar el detalle o perderlo.
        raise RuntimeError("La bodega no tiene el formato esperado (lista de vacantes con id); no se publica.")
    if vacantes is not None:
        cargos = {"roles": {v["id"]: v[CAMPO_ROL] for v in vacantes if CAMPO_ROL in v},
                  "familias": {v["id"]: v["familias"] for v in vacantes
                               if isinstance(v.get("familias"), list) and any(map(_es_de_cargo, v["familias"]))}}
        privados[CARGOS_BODEGA] = json.dumps(cargos, ensure_ascii=False, separators=(",", ":")).encode()
    if copia is not None:
        copia = Path(copia)
        for rel, datos in privados.items():
            _escribir_bytes(copia / rel, datos)
    for rel in PRIVADOS:
        (salida / rel).unlink(missing_ok=True)
    for rel, recortar in PUBLICAR.items():
        if rel in privados:
            _escribir_json(salida / rel, recortar(json.loads(privados[rel].decode("utf-8"))))
    if vacantes is not None:
        publicas = []
        for v in vacantes:
            v = {k: x for k, x in v.items() if k != CAMPO_ROL}
            if isinstance(v.get("familias"), list):
                v["familias"] = [f for f in v["familias"] if not _es_de_cargo(f)]
            publicas.append(v)
        _escribir_bodega(ruta_bodega, publicas)
    return privados


def reponer(salida, privados):
    """Lo inverso de `separar`: deja `salida` como la dejó la corrida anterior antes de recortarla."""
    salida = Path(salida)
    for rel, datos in privados.items():
        if rel != CARGOS_BODEGA:
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
    cabeceras = {"apikey": clave}
    if clave.startswith("eyJ"):
        cabeceras["Authorization"] = f"Bearer {clave}"
    return url, cabeceras


def _empacar(datos):
    return base64.b64encode(gzip.compress(datos, mtime=0)).decode("ascii")


def _desempacar(fila):
    datos = gzip.decompress(base64.b64decode(fila["contenido"]))
    if hashlib.sha256(datos).hexdigest() != fila["sha256"]:
        raise RuntimeError(f"El estado privado {fila['archivo']} no coincide con su huella; no se usará.")
    return datos


def subir(grupo, privados, ejecucion, sesion=None):
    url, cabeceras = _conexion()
    if not url:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY: no se puede guardar el estado privado.")
    sesion = sesion or requests.Session()
    cabeceras = dict(cabeceras, Prefer="resolution=merge-duplicates,return=minimal")
    for rel, datos in sorted(privados.items()):
        fila = {"grupo": grupo, "archivo": rel, "contenido": _empacar(datos),
                "sha256": hashlib.sha256(datos).hexdigest(), "ejecucion": ejecucion}
        for intento in range(3):
            try:
                r = sesion.post(f"{url}/rest/v1/{TABLA}?on_conflict=grupo,archivo", json=[fila],
                                headers=cabeceras, timeout=120)
                if 200 <= r.status_code < 300:
                    break
                causa = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                causa = type(e).__name__
            if intento == 2:
                raise RuntimeError(f"No se pudo guardar {rel} en Supabase ({causa}); no se publica esta corrida.")


def leer(grupo="vigente", sesion=None):
    """{archivo: (bytes, ejecucion)}; None si la tabla aún no existe (SQL 022 sin aplicar)."""
    url, cabeceras = _conexion()
    if not url:
        return None
    sesion = sesion or requests.Session()
    for _intento in range(3):
        try:
            r = sesion.get(f"{url}/rest/v1/{TABLA}", headers=cabeceras, timeout=120,
                           params={"select": "archivo,contenido,sha256,ejecucion", "grupo": "eq." + grupo})
        except requests.RequestException as e:
            causa = type(e).__name__
        else:
            if r.status_code == 404:
                return None
            if r.status_code == 200 and isinstance(r.json(), list):
                return {f["archivo"]: (_desempacar(f), f.get("ejecucion", "")) for f in r.json()}
            causa = f"HTTP {r.status_code}"
    raise RuntimeError(f"No se pudo leer el estado privado de Supabase ({causa}).")


# ---------------------------------------------------------------- pasos del flujo

def guardar(salida, copia, grupo="vigente", ejecucion="", sesion=None):
    salida = Path(salida)
    if copia is not None and Path(copia).exists():
        shutil.rmtree(copia)
    privados = separar(salida, copia)
    if not privados:
        return []
    if grupo == "vigente":
        _escribir_json(salida / MARCA, {"formato": FORMATO, "ejecucion": ejecucion, "archivos": sorted(privados),
                                        "donde": f"Supabase, tabla {TABLA} (privada)"})
    subir(grupo, privados, ejecucion, sesion=sesion)
    return sorted(privados)


def traer(salida, sesion=None):
    """Devuelve un mensaje para el registro (sin datos). Lanza error si la marca existe y falta algo."""
    salida = Path(salida)
    marca = salida / MARCA
    if not marca.is_file():
        return "La rama publicado aún no separa el estado privado: se usa lo que trae."
    esperados = json.loads(marca.read_text(encoding="utf-8"))
    guardados = leer("vigente", sesion=sesion)
    if guardados is None:
        raise RuntimeError("La rama publicado dice que el estado privado está en Supabase, pero no se puede leer "
                           "(faltan credenciales o la tabla estado_trabajo). No se continúa con el estado vacío.")
    faltan = [rel for rel in esperados.get("archivos", []) if rel not in guardados]
    if faltan:
        raise RuntimeError(f"Faltan {len(faltan)} archivos del estado privado en Supabase. No se continúa con el "
                           "estado incompleto.")
    reponer(salida, {rel: guardados[rel][0] for rel in esperados["archivos"]})
    ejecuciones = {guardados[rel][1] for rel in esperados["archivos"]}
    if ejecuciones != {esperados.get("ejecucion", "")}:
        return ("Aviso: el estado privado es de otra corrida que la rama publicado (¿falló una publicación después "
                "de guardarlo?). Se usa el de Supabase, que es el más reciente.")
    return f"Estado privado recuperado de Supabase: {len(esperados['archivos'])} archivos."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["traer", "guardar"])
    ap.add_argument("--salida", required=True)
    ap.add_argument("--copia", default="privado/estado_trabajo",
                    help="guardar: carpeta fuera de lo publicado con los archivos completos")
    ap.add_argument("--fallida", action="store_true",
                    help="guardar: la corrida falló; se guarda aparte (grupo «fallida») y la siguiente no lo lee")
    a = ap.parse_args()
    if a.accion == "traer":
        mensaje = traer(a.salida)
        print(("::warning::" if mensaje.startswith("Aviso") else "") + mensaje)
        return
    archivos = guardar(a.salida, a.copia, "fallida" if a.fallida else "vigente", os.environ.get("GITHUB_RUN_ID", ""))
    print(f"Estado privado guardado en Supabase ({'fallida' if a.fallida else 'vigente'}): {len(archivos)} archivos. "
          "La rama publicado queda solo con cifras agregadas.")


if __name__ == "__main__":
    main()
