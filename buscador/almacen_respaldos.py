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

import requests

from buscador import registro, supabase

BUCKET = "respaldos"
TROZO = 40 * 1024 * 1024        # bajo el máximo de 50 MB por archivo del plan gratuito
LIMITE_BUCKET = 50 * 1000 * 1000  # el bucket rechaza cualquier archivo mayor
CONSERVAR = 4                    # semanales válidos que se guardan (decisión de Oscar, 27 nov)
AVISO_TOTAL = 800 * 1000 * 1000  # aviso antes de llegar al 1 GB del plan gratuito
TIPOS = ("semanal", "antes-de-limpiar")
PODABLES = ("semanal",)
MANIFIESTO = "manifiesto.json"
_CARPETA = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Za-z0-9-]+$")


class Almacen:
    def __init__(self, url=None, clave=None, sesion=None, pausa=5):
        if url is None:
            url, clave = supabase.credenciales()
        if not url or not clave:
            raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY: no se puede guardar el respaldo.")
        self.url = url.rstrip("/") + "/storage/v1"
        self.cabeceras = {"apikey": clave}
        if clave.startswith("eyJ"):  # clave antigua service_role; la nueva (sb_secret_) va solo en apikey
            self.cabeceras["Authorization"] = f"Bearer {clave}"
        self.sesion = sesion or requests.Session()
        self.pausa = pausa

    # ------------------------------------------------------------ HTTP
    def _pedir(self, metodo, ruta, que, aceptar=(), **k):
        """Tres intentos ante red o 5xx; un 4xx no se repite. Los estados de `aceptar` se devuelven sin error."""
        causa = ""
        for intento in range(3):
            try:
                r = self.sesion.request(metodo, self.url + ruta, headers={**self.cabeceras, **k.pop("headers", {})},
                                        timeout=600, **k)
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
        self._pedir("POST", f"/object/{BUCKET}/{self._ruta(nombre)}", f"subir {nombre}", data=datos,
                    headers={"Content-Type": "application/octet-stream", "x-upsert": "false"})

    def bajar_objeto(self, nombre, faltante=False):
        """Bytes del objeto. Con `faltante=True` devuelve None si no existe (400/404); otro error siempre lanza."""
        r = self._pedir("GET", f"/object/authenticated/{BUCKET}/{self._ruta(nombre)}", f"bajar {nombre}",
                        aceptar=(400, 404) if faltante else ())
        return None if r.status_code in (400, 404) else r.content

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


def subir(almacen, archivo, tipo, ejecucion, ahora=None):
    """Sube, comprueba (vuelve a bajar cada trozo) y deja el manifiesto. Devuelve el manifiesto. Cualquier fallo lanza."""
    if tipo not in TIPOS:
        raise RuntimeError(f"Tipo de respaldo desconocido: {tipo}.")
    ejecucion = re.sub(r"[^A-Za-z0-9-]", "", str(ejecucion or "")) or "local"
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
        datos = almacen.bajar_objeto(f"{carpeta}/{p['nombre']}")
        if len(datos) != p["tamano"] or _sha(datos) != p["sha256"]:
            raise RuntimeError(f"El trozo {p['nombre']} de {carpeta} no coincide al bajarlo (tamaño o sha256).")


def leer_manifiesto(almacen, carpeta):
    """None si la carpeta no tiene manifiesto (respaldo incompleto). Un fallo de red lanza: así nunca se confunde un
    respaldo bueno con uno incompleto al podar."""
    datos = almacen.bajar_objeto(f"{carpeta}/{MANIFIESTO}", faltante=True)
    if datos is None:
        return None
    try:
        return json.loads(datos)
    except ValueError:
        return None


def carpetas(almacen, tipo):
    """Carpetas de respaldo del tipo, de la más vieja a la más nueva (el nombre empieza por la fecha)."""
    return sorted(f"{tipo}/{e['name']}" for e in almacen.listar(tipo + "/")
                  if not e.get("id") and _CARPETA.match(e["name"]))


def validos(almacen, tipo):
    """[(carpeta, manifiesto)] de los respaldos completos, del más viejo al más nuevo."""
    salida = []
    for carpeta in carpetas(almacen, tipo):
        m = leer_manifiesto(almacen, carpeta)
        if isinstance(m, dict) and m.get("carpeta") == carpeta and m.get("partes"):
            salida.append((carpeta, m))
    return salida


def podar(almacen, tipo, conservar=CONSERVAR):
    """Borra los semanales más viejos que los últimos `conservar` válidos (y los incompletos anteriores al último
    válido). Nunca borra el último válido. Devuelve las carpetas borradas."""
    if tipo not in PODABLES:
        return []
    conservar = max(1, conservar)
    buenos = validos(almacen, tipo)
    if not buenos:
        return []
    quedan = {c for c, _ in buenos[-conservar:]}
    ultimo = buenos[-1][0]
    viejas = [c for c in carpetas(almacen, tipo) if c not in quedan and c < ultimo]
    borradas = []
    for carpeta in viejas:
        nombres = [f"{carpeta}/{e['name']}" for e in almacen.listar(carpeta + "/")]
        almacen.borrar(nombres)
        borradas.append(carpeta)
    return borradas


def ocupado(almacen):
    """Bytes que ocupan todos los respaldos del bucket."""
    total = 0
    for tipo in TIPOS:
        for carpeta in carpetas(almacen, tipo):
            total += sum((e.get("metadata") or {}).get("size") or 0 for e in almacen.listar(carpeta + "/"))
    return total


def bajar(almacen, carpeta, destino):
    """Reúne los trozos en `destino` (archivo nuevo), comprobando cada sha256 y el total. Devuelve el manifiesto."""
    m = leer_manifiesto(almacen, carpeta)
    if not isinstance(m, dict) or m.get("carpeta") != carpeta:
        raise RuntimeError(f"{carpeta} no tiene manifiesto válido: el respaldo está incompleto.")
    destino = Path(destino)
    total = hashlib.sha256()
    temporal = destino.with_name(destino.name + ".partial")
    try:
        with os.fdopen(os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as salida:
            for p in m["partes"]:
                datos = almacen.bajar_objeto(f"{carpeta}/{p['nombre']}")
                if len(datos) != p["tamano"] or _sha(datos) != p["sha256"]:
                    raise RuntimeError(f"El trozo {p['nombre']} no coincide con el manifiesto.")
                salida.write(datos)
                total.update(datos)
        if total.hexdigest() != m["sha256"]:
            raise RuntimeError("El respaldo reunido no coincide con el sha256 del manifiesto.")
        if destino.exists():
            raise RuntimeError(f"{destino} ya existe: no se sobrescribe.")
        temporal.replace(destino)
        return m
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise


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
    m = subir(almacen, _archivo_unico(args.carpeta), args.tipo, os.environ.get("GITHUB_RUN_ID", "local"))
    lineas = [f"Respaldo guardado en Storage (bucket privado `{BUCKET}`): `{m['carpeta']}`",
              f"- {_mb(m['tamano'])} en {len(m['partes'])} trozos, comprobados al bajarlos de nuevo",
              f"- sha256 `{m['sha256']}`"]
    try:
        borradas = podar(almacen, args.tipo)
        if borradas:
            lineas.append(f"- Se borraron {len(borradas)} respaldos semanales viejos (quedan los últimos {CONSERVAR})")
        usado = ocupado(almacen)
        lineas.append(f"- El bucket ocupa {_mb(usado)} de 1.000 MB del plan gratuito")
        if usado > AVISO_TOTAL:
            lineas.append("- ⚠️ Queda poco espacio: decidir si pasar a Pro o guardar menos semanas")
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
            estado = f"{_mb(m['tamano'])}  sha256 {m['sha256'][:12]}…" if isinstance(m, dict) else "INCOMPLETO"
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
