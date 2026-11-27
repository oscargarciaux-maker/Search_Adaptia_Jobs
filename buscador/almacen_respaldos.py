"""Guarda los respaldos cifrados en un bucket PRIVADO de Supabase Storage del mismo proyecto (27 nov, opción B).

Antes iban como artefacto de GitHub Actions, que en un repo público puede bajar cualquiera con cuenta. El plan gratuito
de Supabase admite como máximo 50 MB por archivo y 1 GB en total, por eso:
- cada `.enc` (ya cifrado por `buscador.respaldo`) se parte en trozos de 40 MiB;
- cada respaldo es una carpeta `<tipo>/<AAAA-MM-DD>_<ejecución>/` con `parte-000`, `parte-001`… y, al final,
  `manifiesto.json` (tamaño y sha256 del total y de cada trozo). Sin manifiesto el respaldo no cuenta como válido;
- tras subir se vuelve a bajar cada trozo y se compara tamaño y sha256: si algo no cuadra, el job falla;
- de los semanales se conservan los últimos `CONSERVAR` válidos; nunca se borra el último válido. Los de
  «antes de limpiar» no se borran solos.

Usa SUPABASE_URL y SUPABASE_SECRET_KEY (la clave nunca se imprime). Nada aquí descifra: la clave de cifrado no hace falta.
Restaurar: `listar` y `bajar` (ver docs/OPERACION_Y_RECUPERACION.md §8).
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote
from uuid import uuid4

import requests

from buscador import registro, supabase

BUCKET = "respaldos"
TROZO = 40 * 1024 * 1024        # bajo el máximo de 50 MB por archivo del plan gratuito
LIMITE_BUCKET = 50 * 1000 * 1000  # el bucket rechaza cualquier archivo mayor
CONSERVAR = 4                    # semanales válidos que se guardan (decisión de Oscar, 27 nov)
CUOTA_GRATUITA = 1000 * 1000 * 1000  # 1 GB de Storage en el plan gratuito
AVISO = 0.8                      # aviso si la próxima copia (mientras convive con las demás) pasaría del 80 %
TIPOS = ("semanal", "antes-de-limpiar")
PODABLES = ("semanal",)
MANIFIESTO = "manifiesto.json"
_ID = "A-Za-z0-9-"
_CARPETA = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}_[{_ID}]+$")


def _no_existe(r):
    """Storage responde «no encontrado» con 404 o con 400 y `statusCode: 404`/`not_found` en el cuerpo. Otro 400 no se
    toma como ausencia: así un error raro nunca hace que un respaldo bueno parezca incompleto."""
    if r.status_code == 404:
        return True
    if r.status_code != 400:
        return False
    try:
        cuerpo = json.dumps(r.json()).lower()
    except ValueError:
        return False
    return "not found" in cuerpo or "not_found" in cuerpo or '"404"' in cuerpo


def _duplicado(r):
    try:
        cuerpo = json.dumps(r.json()).lower()
    except ValueError:
        return False
    return r.status_code == 409 or (r.status_code == 400 and ("duplicate" in cuerpo or "already exists" in cuerpo))


class Almacen:
    def __init__(self, url=None, clave=None, sesion=None, pausa=5):
        if url is None:
            url, clave = supabase.credenciales()
        if not url or not clave:
            raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY: no se puede guardar el respaldo.")
        self.url = url.rstrip("/") + "/storage/v1"
        self.cabeceras = supabase.cabeceras(clave)
        self.sesion = sesion or requests.Session()
        self.pausa = pausa

    # ------------------------------------------------------------ HTTP
    def _pedir(self, metodo, ruta, que, aceptar=(), **k):
        """Tres intentos ante red o 5xx; un 4xx no se repite. Los estados de `aceptar` se devuelven sin error."""
        causa, cabeceras = "", {**self.cabeceras, **k.pop("headers", {})}
        for intento in range(3):
            try:
                r = self.sesion.request(metodo, self.url + ruta, headers=cabeceras, timeout=600, **k)
            except requests.RequestException as e:
                causa = type(e).__name__
            else:
                if 200 <= r.status_code < 300 or r.status_code in aceptar:
                    return r
                causa = f"HTTP {r.status_code}"
                if r.status_code < 500:
                    break
            if intento < 2:
                time.sleep(self.pausa)
        raise RuntimeError(f"No se pudo {que} en Supabase Storage ({causa}).")

    @staticmethod
    def _ruta(nombre):
        return quote(nombre, safe="/")

    # ------------------------------------------------------------ bucket
    def asegurar_bucket(self):
        """Crea el bucket privado si no existe. Si existe y es público, falla: nunca se sube a un bucket público."""
        r = self._pedir("GET", f"/bucket/{BUCKET}", "consultar el bucket", aceptar=(400, 404))
        if r.status_code in (400, 404):
            if not _no_existe(r):
                raise RuntimeError(f"Supabase Storage rechazó la consulta del bucket (HTTP {r.status_code}).")
            self._pedir("POST", "/bucket", "crear el bucket privado", aceptar=(409,),
                        json={"id": BUCKET, "name": BUCKET, "public": False, "file_size_limit": LIMITE_BUCKET})
            r = self._pedir("GET", f"/bucket/{BUCKET}", "consultar el bucket")
        datos = r.json()
        if not isinstance(datos, dict) or datos.get("public") is not False:
            raise RuntimeError(f"El bucket «{BUCKET}» de Supabase Storage es público (o no se pudo comprobar): "
                               "hazlo privado en Storage > Buckets antes de guardar respaldos. No se subió nada.")

    # ------------------------------------------------------------ objetos
    def listar(self, prefijo):
        """Entradas directas bajo `prefijo` (carpetas sin `id`, archivos con `metadata.size`)."""
        salida, desde = [], 0
        while True:
            r = self._pedir("POST", f"/object/list/{BUCKET}", "listar los respaldos",
                            json={"prefix": prefijo, "limit": 1000, "offset": desde,
                                  "sortBy": {"column": "name", "order": "asc"}})
            lote = r.json()
            if not isinstance(lote, list):
                raise RuntimeError("Supabase Storage devolvió la lista de respaldos en un formato inesperado.")
            salida += [e for e in lote if e.get("name") and e["name"] != ".emptyFolderPlaceholder"]
            if len(lote) < 1000:
                return salida
            desde += 1000

    def subir_objeto(self, nombre, datos):
        """Si un reintento encuentra el trozo ya guardado (la respuesta anterior se perdió), lo da por subido:
        `comprobar` lo baja después y compara su sha256, así que un trozo distinto nunca pasa."""
        r = self._pedir("POST", f"/object/{BUCKET}/{self._ruta(nombre)}", f"subir {nombre}", aceptar=(400, 409),
                        data=datos, headers={"Content-Type": "application/octet-stream", "x-upsert": "false"})
        if r.status_code in (400, 409) and not _duplicado(r):
            raise RuntimeError(f"No se pudo subir {nombre} en Supabase Storage (HTTP {r.status_code}).")

    def bajar_objeto(self, nombre, faltante=False):
        """Bytes del objeto. Con `faltante=True` devuelve None si no existe; cualquier otro error lanza."""
        r = self._pedir("GET", f"/object/authenticated/{BUCKET}/{self._ruta(nombre)}", f"bajar {nombre}",
                        aceptar=(400, 404) if faltante else ())
        if r.status_code in (400, 404):
            if _no_existe(r):
                return None
            raise RuntimeError(f"No se pudo bajar {nombre} de Supabase Storage (HTTP {r.status_code}).")
        return r.content

    def borrar(self, nombres):
        if nombres:
            self._pedir("DELETE", f"/object/{BUCKET}", "borrar respaldos viejos", json={"prefixes": list(nombres)})


# ---------------------------------------------------------------- respaldos
def _sha(datos):
    return hashlib.sha256(datos).hexdigest()


def _trozos(archivo):
    with Path(archivo).open("rb") as f:
        while True:
            datos = f.read(TROZO)
            if not datos:
                return
            yield datos


def _bajar_trozo(almacen, carpeta, parte):
    datos = almacen.bajar_objeto(f"{carpeta}/{parte['nombre']}")
    if len(datos) != parte["tamano"] or _sha(datos) != parte["sha256"]:
        raise RuntimeError(f"El trozo {parte['nombre']} de {carpeta} no coincide con el manifiesto (tamaño o sha256).")
    return datos


def subir(almacen, archivo, tipo, ejecucion, ahora=None):
    """Sube, comprueba (vuelve a bajar cada trozo) y deja el manifiesto. Devuelve el manifiesto. Cualquier fallo lanza.
    `ejecucion` distingue cada intento (en Actions: ejecución-intento), para que «Re-run» no choque con el anterior."""
    if tipo not in TIPOS:
        raise RuntimeError(f"Tipo de respaldo desconocido: {tipo}.")
    ejecucion = re.sub(f"[^{_ID}]", "", str(ejecucion or "")) or "local"
    ahora = ahora or datetime.now(timezone.utc)
    carpeta = f"{tipo}/{ahora:%Y-%m-%d}_{ejecucion}"
    almacen.asegurar_bucket()
    if almacen.listar(carpeta + "/"):
        raise RuntimeError(f"Ya existe un respaldo en {carpeta}: no se sobrescribe.")
    total, partes = hashlib.sha256(), []
    for i, datos in enumerate(_trozos(archivo)):
        nombre = f"parte-{i:03d}"
        almacen.subir_objeto(f"{carpeta}/{nombre}", datos)
        total.update(datos)
        partes.append({"nombre": nombre, "tamano": len(datos), "sha256": _sha(datos)})
    if not partes:
        raise RuntimeError("El respaldo cifrado está vacío: no se sube.")
    manifiesto = {"formato": 1, "tipo": tipo, "carpeta": carpeta, "creado_en": ahora.isoformat(),
                  "tamano": sum(p["tamano"] for p in partes), "sha256": total.hexdigest(), "partes": partes}
    if manifiesto["tamano"] != Path(archivo).stat().st_size:
        raise RuntimeError("El archivo cambió mientras se subía: no se da por bueno.")
    comprobar(almacen, manifiesto)
    almacen.subir_objeto(f"{carpeta}/{MANIFIESTO}", json.dumps(manifiesto, indent=1).encode())
    if leer_manifiesto(almacen, carpeta) != manifiesto:
        raise RuntimeError("El manifiesto guardado no coincide con lo subido.")
    return manifiesto


def comprobar(almacen, manifiesto):
    """Que cada trozo exista con su tamaño y que, bajado de nuevo, tenga el mismo sha256."""
    carpeta = manifiesto["carpeta"]
    tamanos = {e["name"]: (e.get("metadata") or {}).get("size") for e in almacen.listar(carpeta + "/")}
    for p in manifiesto["partes"]:
        if tamanos.get(p["nombre"]) != p["tamano"]:
            raise RuntimeError(f"El trozo {p['nombre']} de {carpeta} no está en Storage con su tamaño.")
        _bajar_trozo(almacen, carpeta, p)


def _manifiesto_valido(m, carpeta):
    if not isinstance(m, dict) or m.get("carpeta") != carpeta or not isinstance(m.get("sha256"), str):
        return False
    partes = m.get("partes")
    if not partes or not all(isinstance(p, dict) and {"nombre", "tamano", "sha256"} <= set(p) for p in partes):
        return False
    return m.get("tamano") == sum(p["tamano"] for p in partes)


def leer_manifiesto(almacen, carpeta):
    """El manifiesto si la carpeta tiene uno válido para ella; None si es un respaldo incompleto. Es la única regla de
    «respaldo válido». Un fallo de red lanza: así nunca se confunde un respaldo bueno con uno incompleto al podar."""
    datos = almacen.bajar_objeto(f"{carpeta}/{MANIFIESTO}", faltante=True)
    if datos is None:
        return None
    try:
        m = json.loads(datos)
    except ValueError:
        return None
    return m if _manifiesto_valido(m, carpeta) else None


def carpetas(almacen, tipo):
    """Carpetas de respaldo del tipo, de la más vieja a la más nueva (el nombre empieza por la fecha)."""
    return sorted(f"{tipo}/{e['name']}" for e in almacen.listar(tipo + "/")
                  if not e.get("id") and _CARPETA.match(e["name"]))


def validos(almacen, tipo, todas=None):
    """[(carpeta, manifiesto)] de los respaldos completos, del más viejo al más nuevo."""
    salida = []
    for carpeta in carpetas(almacen, tipo) if todas is None else todas:
        m = leer_manifiesto(almacen, carpeta)
        if m:
            salida.append((carpeta, m))
    return salida


def podar(almacen, tipo, conservar=CONSERVAR):
    """Borra los semanales más viejos que los últimos `conservar` válidos (y los incompletos anteriores al último
    válido). Nunca borra el último válido. Devuelve las carpetas borradas."""
    if tipo not in PODABLES:
        return []
    conservar = max(1, conservar)
    todas = carpetas(almacen, tipo)
    buenos = validos(almacen, tipo, todas)
    if not buenos:
        return []
    quedan = {c for c, _ in buenos[-conservar:]}
    ultimo = buenos[-1][0]
    borradas = []
    for carpeta in todas:
        if carpeta in quedan or carpeta >= ultimo:
            continue
        almacen.borrar([f"{carpeta}/{e['name']}" for e in almacen.listar(carpeta + "/")])
        borradas.append(carpeta)
    return borradas


def ocupado(almacen):
    """Bytes que ocupan todos los respaldos del bucket (también los incompletos)."""
    return sum((e.get("metadata") or {}).get("size") or 0
               for tipo in TIPOS for carpeta in carpetas(almacen, tipo) for e in almacen.listar(carpeta + "/"))


def bajar(almacen, carpeta, destino):
    """Reúne los trozos en `destino` (archivo nuevo), comprobando cada sha256 y el total. Devuelve el manifiesto."""
    destino = Path(destino)
    if destino.exists():
        raise RuntimeError(f"{destino} ya existe: no se sobrescribe.")
    m = leer_manifiesto(almacen, carpeta)
    if not m:
        raise RuntimeError(f"{carpeta} no tiene manifiesto válido: el respaldo está incompleto.")
    temporal = destino.with_name(f"{destino.name}.{uuid4().hex}.partial")
    total = hashlib.sha256()
    try:
        with os.fdopen(os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as salida:
            for p in m["partes"]:
                datos = _bajar_trozo(almacen, carpeta, p)
                salida.write(datos)
                total.update(datos)
        if total.hexdigest() != m["sha256"]:
            raise RuntimeError("El respaldo reunido no coincide con el sha256 del manifiesto.")
        os.link(temporal, destino)  # falla si alguien creó el destino mientras tanto: nunca se sobrescribe
        return m
    finally:
        temporal.unlink(missing_ok=True)


# ---------------------------------------------------------------- línea de órdenes
def _mb(n):
    return f"{n / 1_000_000:.1f} MB"


def _resumen(texto):
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    print(texto)


def _archivo_unico(carpeta):
    encontrados = sorted(Path(carpeta).glob("*.enc"))
    if len(encontrados) != 1:
        raise RuntimeError(f"Se esperaba exactamente un respaldo .enc en {carpeta} y hay {len(encontrados)}.")
    return encontrados[0]


def _subir_cli(args, almacen):
    ejecucion = "-".join(filter(None, (os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT"))))
    m = subir(almacen, _archivo_unico(args.carpeta), args.tipo, ejecucion or "local")
    lineas = [f"Respaldo guardado en Storage (bucket privado `{BUCKET}`): `{m['carpeta']}`",
              f"- {_mb(m['tamano'])} en {len(m['partes'])} trozos, comprobados al bajarlos de nuevo",
              f"- sha256 `{m['sha256']}`"]
    try:
        borradas = podar(almacen, args.tipo)
        if borradas:
            lineas.append(f"- Se borraron {len(borradas)} respaldos semanales viejos (quedan los últimos {CONSERVAR})")
        usado = ocupado(almacen)
        lineas.append(f"- El bucket ocupa {_mb(usado)} de {_mb(CUOTA_GRATUITA)} del plan gratuito")
        # La próxima copia se sube antes de podar: durante la subida convive con todas las de ahora.
        if usado + m["tamano"] > AVISO * CUOTA_GRATUITA:
            lineas.append("- ⚠️ La próxima copia podría no caber: decidir ya si pasar a Pro o guardar menos semanas "
                          "(docs/OPERACION_Y_RECUPERACION.md §8)")
            registro.aviso("almacen_respaldos.espacio", RuntimeError(f"el bucket ocupa {_mb(usado)}"))
    except (RuntimeError, ValueError, KeyError) as e:
        registro.aviso("almacen_respaldos.podar", e)
        lineas.append("- No se pudo revisar ni podar los respaldos viejos (ver aviso en el registro); el nuevo sí quedó")
    _resumen("\n".join(lineas))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("subir", help="Sube el único .enc de la carpeta y lo comprueba")
    s.add_argument("--tipo", choices=TIPOS, required=True)
    s.add_argument("--carpeta", default="privado/respaldos")
    lst = sub.add_parser("listar", help="Respaldos guardados, del más viejo al más nuevo")
    lst.add_argument("--tipo", choices=TIPOS, default="semanal")
    b = sub.add_parser("bajar", help="Reúne un respaldo en un archivo .enc")
    b.add_argument("--respaldo", required=True, help="Por ejemplo semanal/2026-11-30_123456789")
    b.add_argument("--salida", required=True)
    args = p.parse_args(argv)
    almacen = Almacen()
    if args.orden == "subir":
        _subir_cli(args, almacen)
    elif args.orden == "listar":
        for carpeta in carpetas(almacen, args.tipo):
            m = leer_manifiesto(almacen, carpeta)
            estado = f"{_mb(m['tamano'])}  sha256 {m['sha256'][:12]}…" if m else "INCOMPLETO (no sirve)"
            print(f"{carpeta}  {estado}")
    else:
        m = bajar(almacen, args.respaldo, args.salida)
        print(f"Respaldo reunido en {args.salida} ({_mb(m['tamano'])}, sha256 comprobado).")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
