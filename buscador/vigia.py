"""Vigía de avisos (P-13.1, 28 nov): un solo canal para que los fallos y los límites le lleguen a UNA persona.

Hasta ahora ningún fallo le llegaba a nadie: no había ningún secreto `AVISO_*` y las corridas que lanza el Reloj tienen
como autor a `github-actions[bot]`, así que GitHub no avisa a ninguna persona. El Vigía no busca nada ni escribe en la
base: una vez al día (lo pide el Reloj, `arranque.toca_vigia`, y tiene un horario de respaldo) mira

- las últimas corridas de la Bodega, la Captura horaria, el Reloj y la Copia semanal en la rama principal: si la
  última terminó en rojo, si hace demasiado que no termina bien o si el flujo está desactivado;
- el tamaño de la base (`pg_database_size`, como `inventario.py`) contra los 500 MB del plan gratuito;
- lo que ocupan las copias en el bucket `respaldos` (`almacen_respaldos.ocupado`) contra 1 GB;
- el archivo más grande de la rama `publicado` contra los 100 MB por archivo que admite GitHub;
- los días desde el último commit de `main` (GitHub apaga los horarios de un repo público a los 60 días sin
  actividad);
- `datos/caducidades.yaml`: fines de soporte y caducidad de claves (solo nombres y fechas, nunca valores).

Umbrales: aviso al 80 % y urgente al 95 %; 30 días sin commits; caducidades 180 días antes (soporte) o 30 (claves).

Avisa en GitHub, sin cuentas nuevas (decisión de Oscar, 28 nov): mantiene UN solo issue abierto «Atención: Adaptia»
(etiqueta `vigia`). Si hay avisos nuevos lo abre o le añade un comentario que menciona a la persona de la variable de
repositorio `AVISO_GITHUB_USUARIO` (sin la variable, no menciona a nadie y lo dice en el registro); cuando todo vuelve
a estar en orden comenta «todo en orden» y lo cierra. Los mismos avisos de ayer no se repiten (`firma`).

**Privacidad:** el repo es PÚBLICO y el issue también. El texto se arma solo con plantillas fijas de este archivo (lista blanca
`PLANTILLAS`), cifras enteras, fechas `AAAA-MM-DD`, los nombres fijos de los flujos y el texto revisado de
`datos/caducidades.yaml`. Ningún mensaje de error, nombre de cliente, lugar, cargo, URL ni valor de secreto entra
nunca: `texto_seguro` comprueba cada línea contra la lista blanca y, si una no encaja, la cambia por una genérica.

Uso (vigia.yml): `python -m buscador.vigia --datos CARPETA`, con los JSON de `gh` que reúne el flujo.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import sys
from typing import NamedTuple

import requests
import yaml

from buscador import almacen_respaldos, inventario, migraciones, supabase
from buscador.arranque import BOGOTA, _instante, _leer_json

RAIZ = Path(__file__).resolve().parent.parent
CADUCIDADES = RAIZ / "datos" / "caducidades.yaml"

AVISO, URGENTE = 0.80, 0.95
LIMITE_BASE = inventario.LIMITE_GRATIS_MB * 1_048_576
LIMITE_PUBLICADO = 100 * 1_048_576       # GitHub rechaza el push de un archivo de más de 100 MiB
DIAS_SIN_COMMIT, DIAS_URGENTE_COMMIT = 30, 50  # GitHub apaga los horarios a los 60
ANTELACION = {"soporte": 180, "clave": 30}
URGENTE_DIAS = 30                        # una caducidad a 30 días o menos es urgente
FALLO = {"failure", "timed_out", "startup_failure"}
VENTANA_ROJO = 24                        # horas: un rojo de la Bodega que no tapó una búsqueda real posterior
ESPERA_STORAGE = 30                      # segundos por petición a Storage (el job tiene 15 minutos)

SOPORTE = "Avisa a soporte técnico con el enlace de este issue."
PRO = "Entra en Supabase → Organization → Billing y cambia el plan a Pro (o pide a soporte técnico el traspaso a la cuenta Pro del cliente)."


class Flujo(NamedTuple):
    archivo: str
    nombre: str           # el que se ve en GitHub → Actions
    horas: int            # sin terminar bien más de esto: «parado»
    seguidos: int         # rojos seguidos para avisar
    urgente: bool         # su rojo o su parada es urgente
    paso: str
    tapable: bool = False  # hay corridas que terminan en verde sin trabajar (respaldos de la Bodega)


FLUJOS = {
    "bodega": Flujo("bodega.yml", "Bodega nocturna", 30, 1, True,
                    "Entra en el panel y pulsa «Buscar ahora»; si vuelve a salir en rojo, avisa a soporte técnico "
                    "con el enlace de este issue.", tapable=True),
    "captura": Flujo("incremental.yml", "Captura horaria", 6, 2, False, SOPORTE),
    "reloj": Flujo("reloj.yml", "Reloj", 3, 3, False, "Entra en GitHub → Actions → Reloj y pulsa «Run workflow»."),
    "respaldo": Flujo("respaldo.yml", "Copia de seguridad semanal", 8 * 24, 1, True,
                      "Entra en GitHub → Actions → Copia de seguridad semanal y pulsa «Run workflow»."),
}
NO_MEDIDO = {"corridas": "el estado de las corridas", "flujos": "si los flujos están activos",
             "base": "el tamaño de la base", "storage": "el espacio de las copias",
             "publicado": "el tamaño de la rama «publicado»", "commit": "el último cambio de «main»",
             "caducidades": "la lista de caducidades"}

# Lista blanca: lo único que puede salir. {n}/{pct}/{dias} = cifra entera, {fecha} = AAAA-MM-DD, {flujo} = nombre de
# FLUJOS, {paso_flujo} = su paso, {que} = valor de NO_MEDIDO, {nombre}/{paso} = texto de caducidades.yaml que cumple
# TEXTO_LIBRE.
PLANTILLAS = {
    "flujo_rojo": ("«{flujo}» terminó en rojo.", "{paso_flujo}"),
    "flujo_parado": ("«{flujo}» lleva más de {n} horas sin terminar bien.", "{paso_flujo}"),
    "flujo_desactivado": ("«{flujo}» está desactivado en GitHub.",
                          "Entra en GitHub → Actions → {flujo} y pulsa «Enable workflow»."),
    "base": ("La base de Supabase ocupa el {pct} % de sus 500 MB.", PRO),
    "storage": ("Las copias de seguridad ocupan el {pct} % de 1 GB de Storage.", PRO),
    "publicado": ("El archivo más grande de la rama «publicado» ocupa el {pct} % de los 100 MB que admite GitHub.",
                  SOPORTE),
    "commit": ("Hace {dias} días que no hay cambios en «main»: a los 60 GitHub apaga los horarios.",
               "Entra en GitHub → datos/caducidades.yaml → lápiz, cambia «revisado» por la fecha de hoy y pulsa "
               "«Commit changes»."),
    "caduca": ("«{nombre}» caduca el {fecha} (faltan {dias} días).", "{paso}"),
    "caducado": ("«{nombre}» caducó el {fecha}.", "{paso}"),
    "no_medido": ("No se pudo comprobar {que}.", SOPORTE),
}
TEXTO_LIBRE = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,;:()«»→_\-]{1,160}"  # sin @ ni «/»: ni correos ni enlaces
GENERICO = "AVISO: el Vigía encontró algo que no sabe describir. Paso: " + SOPORTE


class Aviso:
    """Un aviso: su código de PLANTILLAS, si es urgente y los valores que la plantilla rellena."""
    __slots__ = ("codigo", "urgente", "valores")

    def __init__(self, codigo, urgente=False, **valores):
        self.codigo, self.urgente, self.valores = codigo, urgente, valores

    def __repr__(self):
        return f"Aviso({self.codigo!r}, urgente={self.urgente}, {self.valores})"


# ---------------------------------------------------------------- comprobaciones (puras)
def por_uso(codigo, usado, limite):
    """Aviso desde el 80 % del límite; urgente desde el 95 %."""
    fraccion = usado / limite
    if fraccion < AVISO:
        return []
    return [Aviso(codigo, fraccion >= URGENTE, pct=int(100 * fraccion))]


def de_corridas(clave, corridas, rama, ahora):
    """Avisos de un flujo a partir de `gh run list --json …` (solo estados y fechas).
    En la Bodega (`tapable`) los horarios de respaldo terminan en verde sin trabajar cuando la de la mañana ya publicó,
    aunque esa haya terminado en rojo: un rojo de las últimas 24 horas solo lo tapa una corrida pedida
    (`workflow_dispatch`: «Buscar ahora» o el Reloj, que siempre trabajan) que terminó bien después."""
    f = FLUJOS[clave]
    lista = [c for c in corridas if isinstance(c, dict) and c.get("headBranch") == rama]
    terminadas = sorted((c for c in lista if c.get("status") == "completed"
                         and c.get("conclusion") not in ("cancelled", "skipped")),
                        key=lambda c: c.get("createdAt") or "", reverse=True)
    if f.tapable:
        rojas = [c for c in terminadas if c.get("conclusion") in FALLO
                 and (_instante(c.get("createdAt")) or ahora) > ahora - timedelta(hours=VENTANA_ROJO)]
        rojo = bool(rojas) and not any(c.get("conclusion") == "success" and c.get("event") == "workflow_dispatch"
                                       and (c.get("createdAt") or "") > (rojas[0].get("createdAt") or "")
                                       for c in terminadas)
    else:
        ultimas = terminadas[:f.seguidos]
        rojo = len(ultimas) == f.seguidos and all(c.get("conclusion") in FALLO for c in ultimas)
    if rojo:
        return [Aviso("flujo_rojo", f.urgente, flujo=clave)]  # si ya está en rojo, un solo aviso basta
    buenas = [i for i in (_instante(c.get("createdAt")) for c in terminadas if c.get("conclusion") == "success") if i]
    if not buenas or (ahora - max(buenas)).total_seconds() > f.horas * 3600:
        return [Aviso("flujo_parado", f.urgente, flujo=clave, n=f.horas)]
    return []


def de_flujos(flujos):
    """`gh workflow list --all --json path,state`: los flujos clave que no están activos (p. ej. `disabled_inactivity`)."""
    estados = {Path(str(f.get("path", ""))).name: f.get("state") for f in flujos if isinstance(f, dict)}
    return [Aviso("flujo_desactivado", True, flujo=clave) for clave, f in FLUJOS.items()
            if f.archivo in estados and estados[f.archivo] != "active"]


def de_commit(fecha, ahora):
    instante = _instante(fecha) if fecha else None
    if instante is None:
        return [Aviso("no_medido", que="commit")]
    dias = (ahora - instante).days
    return [Aviso("commit", dias >= DIAS_URGENTE_COMMIT, dias=dias)] if dias >= DIAS_SIN_COMMIT else []


def de_publicado(tamanos):
    return por_uso("publicado", max(tamanos), LIMITE_PUBLICADO) if tamanos else []


def _fecha(valor):
    """Una fecha de YAML (también si alguien le puso hora) o un texto AAAA-MM-DD."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def de_caducidades(datos, hoy):
    """Avisos de `datos/caducidades.yaml`. Una entrada con texto fuera de TEXTO_LIBRE o sin fecha válida no se usa:
    se avisa de que la lista no se pudo comprobar (así nunca sale un texto no revisado)."""
    salida, rota = [], False
    for e in (datos or {}).get("caducidades") or []:
        try:
            nombre, paso, tipo = str(e["nombre"]), str(e["paso"]), str(e["tipo"])
            faltan = (_fecha(e["fecha"]) - hoy).days
            fecha = _fecha(e["fecha"]).isoformat()
            antelacion = int(e.get("aviso_dias", ANTELACION[tipo]))
        except (KeyError, TypeError, ValueError, AttributeError):
            rota = True
            continue
        if not (re.fullmatch(TEXTO_LIBRE, nombre) and re.fullmatch(TEXTO_LIBRE, paso)):
            rota = True
            continue
        if faltan < 0:
            salida.append(Aviso("caducado", True, nombre=nombre, fecha=fecha, paso=paso))
        elif faltan <= antelacion:
            salida.append(Aviso("caduca", faltan <= URGENTE_DIAS, nombre=nombre, fecha=fecha, dias=faltan, paso=paso))
    if rota:
        salida.append(Aviso("no_medido", que="caducidades"))
    return salida


# ---------------------------------------------------------------- texto (lista blanca)
_TIPOS = {"n": r"\d+", "pct": r"\d+", "dias": r"\d+", "fecha": r"\d{4}-\d{2}-\d{2}",
          "flujo": "|".join(re.escape(f.nombre) for f in FLUJOS.values()),
          "paso_flujo": "|".join(re.escape(f.paso) for f in FLUJOS.values()),
          "que": "|".join(re.escape(v) for v in NO_MEDIDO.values()),
          "nombre": TEXTO_LIBRE, "paso": TEXTO_LIBRE}


def _patron(plantilla):
    trozos = re.split(r"\{(\w+)\}", plantilla)
    return "".join(re.escape(t) if i % 2 == 0 else f"(?:{_TIPOS[t]})" for i, t in enumerate(trozos))


PATRONES = [re.compile(p) for p in (
    [r"Adaptia · Vigía \d{4}-\d{2}-\d{2}: (?:todo en orden|\d+ avisos?)\."]
    + [f"(?:AVISO|URGENTE): {_patron(que)} Paso: {_patron(paso)}" for que, paso in PLANTILLAS.values()]
    + [re.escape(GENERICO)])]


def _valores(aviso):
    """Solo tipos permitidos: cifras enteras, fechas y textos de las listas fijas. Lo demás lanza ValueError."""
    salida = {}
    for clave, valor in aviso.valores.items():
        if clave in ("n", "pct", "dias"):
            if not isinstance(valor, int) or isinstance(valor, bool):
                raise ValueError(clave)
            salida[clave] = str(valor)
        elif clave == "flujo":
            salida[clave], salida["paso_flujo"] = FLUJOS[valor].nombre, FLUJOS[valor].paso
        elif clave == "que":
            salida[clave] = NO_MEDIDO[valor]
        elif clave in ("fecha", "nombre", "paso"):
            salida[clave] = str(valor)
        else:
            raise ValueError(clave)
    return salida


def linea(aviso):
    try:
        que, paso = PLANTILLAS[aviso.codigo]
        valores = _valores(aviso)
        return f"{'URGENTE' if aviso.urgente else 'AVISO'}: {que.format(**valores)} Paso: {paso.format(**valores)}"
    except (KeyError, ValueError, IndexError):
        return GENERICO


def texto_seguro(lineas):
    """Cada línea debe encajar entera en un patrón de la lista blanca; si no, se cambia por la genérica."""
    return [t if any(p.fullmatch(t) for p in PATRONES) else GENERICO for t in lineas]


def componer(avisos, hoy):
    avisos = sorted(avisos, key=lambda a: not a.urgente)
    cabecera = (f"Adaptia · Vigía {hoy.isoformat()}: "
                + (f"{len(avisos)} aviso{'s' if len(avisos) != 1 else ''}." if avisos else "todo en orden."))
    return "\n".join(texto_seguro([cabecera] + [linea(a) for a in avisos]))


def firma(avisos):
    """Qué avisos hay (sin las cifras, que cambian cada día): vacía si no hay ninguno. Solo un sha256 corto."""
    if not avisos:
        return ""
    claves = sorted(f"{a.codigo}:{a.urgente}:{a.valores.get('flujo') or a.valores.get('que') or a.valores.get('nombre') or ''}"
                    for a in avisos)
    return hashlib.sha256("\n".join(claves).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- mediciones con servicios
def tamano_base(conn):
    """Bytes de la base, en una transacción de solo lectura. La consulta es la de inventario.py; no se llama a
    `inventario.consultar` porque lanza todas las demás (tablas, índices, permisos) y el Vigía solo necesita esta."""
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute("set local statement_timeout = '30s'")
        return int(conn.execute(inventario.CONSULTAS["tamano"]).fetchone()[0])


def medir_base():
    url = supabase.base(os.environ.get("SUPABASE_URL", ""))
    with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""), url) as conn:
        return tamano_base(conn)


class _SesionCorta(requests.Session):
    """`almacen_respaldos` espera hasta 600 s por petición (subidas de 40 MiB). Para listar basta mucho menos: así un
    Storage colgado no agota el tope del job y el aviso del día sale igual (con «no se pudo comprobar»)."""

    def request(self, *a, **k):
        k["timeout"] = min(k.get("timeout") or ESPERA_STORAGE, ESPERA_STORAGE)
        return super().request(*a, **k)


def medir_storage(almacen=None):
    return almacen_respaldos.ocupado(almacen or almacen_respaldos.Almacen(sesion=_SesionCorta(), pausa=2))


def _medir(codigo, funcion, limite, avisos):
    try:
        avisos += por_uso(codigo, funcion(), limite)
    except Exception as e:  # noqa: BLE001 — nunca se cae ni imprime el error: solo su tipo
        print(f"::warning::No se pudo medir {codigo} ({type(e).__name__}).", file=sys.stderr)
        avisos.append(Aviso("no_medido", que=codigo))


# ---------------------------------------------------------------- aviso en GitHub (un issue)
TITULO, ETIQUETA = "Atención: Adaptia", "vigia"
API = "https://api.github.com"
_USUARIO = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")  # reglas de nombres de usuario de GitHub
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class ErrorGitHub(RuntimeError):
    """La API de GitHub no respondió como se esperaba. Solo lleva el estado HTTP o el tipo de error, nunca el token."""


def mencion(usuario):
    """`@usuario` si la variable es un nombre válido de GitHub; vacía (y aviso en el registro) si falta o no lo es."""
    usuario = (usuario or "").strip().lstrip("@")
    if _USUARIO.fullmatch(usuario):
        return f"@{usuario}"
    print("::warning::Falta la variable AVISO_GITHUB_USUARIO (o no es un usuario de GitHub): el issue del Vigía se "
          "abre sin mencionar a nadie. Ver docs/OPERACION_Y_RECUPERACION.md §1.", file=sys.stderr)
    return ""


def cuerpo(texto, arroba=""):
    """Markdown del issue: cada línea de la lista blanca como párrafo y, al final, la mención (si la hay)."""
    return "\n\n".join(texto.splitlines() + ([f"Para {arroba}."] if arroba else []))


class GitHub:
    def __init__(self, repo, token, sesion=None):
        if not _REPO.fullmatch(repo or "") or not token:
            raise ErrorGitHub("faltan GH_REPO o GH_TOKEN")
        self.repo, self.sesion = repo, sesion or requests.Session()
        self.cabeceras = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                          "X-GitHub-Api-Version": "2022-11-28"}

    def pedir(self, metodo, ruta, aceptar=(), **k):
        try:
            r = self.sesion.request(metodo, f"{API}/repos/{self.repo}{ruta}", headers=self.cabeceras, timeout=30, **k)
        except requests.RequestException as e:
            raise ErrorGitHub(type(e).__name__) from None
        if not (200 <= r.status_code < 300 or r.status_code in aceptar):
            raise ErrorGitHub(f"HTTP {r.status_code}")
        return r

    def abierto(self):
        """El número del issue abierto del Vigía (el más antiguo, si hubiera dos), o None."""
        lista = self.pedir("GET", "/issues", params={"state": "open", "labels": ETIQUETA, "per_page": 50,
                                                     "sort": "created", "direction": "asc"}).json()
        propios = [i for i in lista if isinstance(i, dict) and "pull_request" not in i and i.get("title") == TITULO]
        return propios[0]["number"] if propios else None

    def abrir(self, texto):
        self.pedir("POST", "/labels", aceptar=(422,),  # 422: la etiqueta ya existe
                   json={"name": ETIQUETA, "color": "d93f0b", "description": "Avisos del Vigía (buscador/vigia.py)"})
        return self.pedir("POST", "/issues", json={"title": TITULO, "body": texto, "labels": [ETIQUETA]}).json()["number"]

    def comentar(self, numero, texto):
        self.pedir("POST", f"/issues/{numero}/comments", json={"body": texto})

    def cerrar(self, numero):
        self.pedir("PATCH", f"/issues/{numero}", json={"state": "closed", "state_reason": "completed"})


def avisar(github, texto, hay_avisos, nuevos, arroba=""):
    """Un solo issue abierto. Devuelve lo que hizo: «abierto», «comentado», «cerrado» o «nada».
    - con avisos y sin issue abierto: lo abre (con la mención);
    - con avisos e issue abierto: comenta solo si son avisos nuevos (`nuevos`), también con la mención;
    - sin avisos e issue abierto: comenta «todo en orden» y lo cierra; sin issue, nada."""
    numero = github.abierto()
    if hay_avisos:
        if numero is None:
            github.abrir(cuerpo(texto, arroba))
            return "abierto"
        if nuevos:
            github.comentar(numero, cuerpo(texto, arroba))
            return "comentado"
        return "nada"
    if numero is None:
        return "nada"
    github.comentar(numero, cuerpo(texto))
    github.cerrar(numero)
    return "cerrado"


# ---------------------------------------------------------------- línea de órdenes
def _texto(ruta):
    try:
        return Path(ruta).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def revisar(carpeta, ahora=None, base=medir_base, storage=medir_storage, caducidades=CADUCIDADES):
    """Todos los avisos de hoy. `carpeta` trae lo que reúne vigia.yml con `gh` (ver el flujo); `base` y `storage`
    miden en bytes (en las pruebas, funciones falsas)."""
    ahora = ahora or datetime.now(timezone.utc)
    hoy = ahora.astimezone(BOGOTA).date()
    carpeta, avisos = Path(carpeta), []
    rama = _texto(carpeta / "rama.txt") or "main"
    corridas = {clave: _leer_json(carpeta / f"corridas_{clave}.json") for clave in FLUJOS}
    if any(not isinstance(v, list) for v in corridas.values()):
        avisos.append(Aviso("no_medido", que="corridas"))
    for clave, lista in corridas.items():
        if isinstance(lista, list):
            avisos += de_corridas(clave, lista, rama, ahora)
    flujos = _leer_json(carpeta / "flujos.json")
    avisos += de_flujos(flujos) if isinstance(flujos, list) else [Aviso("no_medido", que="flujos")]
    avisos += de_commit(_texto(carpeta / "commit.txt"), ahora)
    publicado = _texto(carpeta / "publicado.txt")
    if publicado is None:
        avisos.append(Aviso("no_medido", que="publicado"))
    else:
        avisos += de_publicado([int(x) for x in publicado.split() if x.isdigit()])
    _medir("base", base, LIMITE_BASE, avisos)
    _medir("storage", storage, almacen_respaldos.CUOTA_GRATUITA, avisos)
    try:
        datos = yaml.safe_load(Path(caducidades).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        datos = None
    avisos += de_caducidades(datos, hoy) if isinstance(datos, dict) else [Aviso("no_medido", que="caducidades")]
    return avisos, hoy


def main(argv=None, ahora=None, sesion=None, base=medir_base, storage=medir_storage, caducidades=CADUCIDADES):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", required=True, help="Carpeta con lo que reúne vigia.yml (gh run list, etc.)")
    ap.add_argument("--firma", help="Archivo con la firma de los avisos de la corrida anterior; se reescribe con la de "
                    "hoy (vigia.yml lo guarda en la caché de Actions). Sin él, unos avisos con el issue abierto se "
                    "comentan siempre.")
    args = ap.parse_args(argv)
    avisos, hoy = revisar(args.datos, ahora, base=base, storage=storage, caducidades=caducidades)
    texto = componer(avisos, hoy)
    print(texto)
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write("## Vigía de avisos\n\n" + texto.replace("\n", "\n\n") + "\n")
    nueva = firma(avisos)
    anterior = _texto(args.firma) if args.firma else None  # None = no se sabe qué avisos había
    try:
        github = GitHub(os.environ.get("GH_REPO", ""), os.environ.get("GH_TOKEN", ""), sesion)
        hecho = avisar(github, texto, bool(avisos), anterior != nueva,
                       mencion(os.environ.get("AVISO_GITHUB_USUARIO")) if avisos else "")
    except (ErrorGitHub, KeyError, TypeError, ValueError) as e:
        # En rojo: es la única forma de que se vea en Actions que el aviso no llegó.
        print(f"::error::El Vigía no pudo dejar el aviso en GitHub ({e if isinstance(e, ErrorGitHub) else type(e).__name__}).",
              file=sys.stderr)
        sys.exit(1)
    print(f"::notice::Issue del Vigía: {hecho}.", file=sys.stderr)
    if args.firma:
        Path(args.firma).write_text(nueva, encoding="utf-8")


if __name__ == "__main__":
    main()
