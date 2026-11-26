"""InfoJobs (España): portal donde se postula en el mismo sitio. Contrato v50 §3: España no tenía ninguna fuente local.
Sin sesión ni cookies.

La página de búsqueda trae cada aviso completo dentro de sus datos (`window.__INITIAL_PROPS__` → `offers`): título,
empresa, ciudad, modalidad, fecha, enlace y descripción. La ficha de cada aviso pide captcha y nunca se abre. Por eso
(decisión de Oscar del 26 nov, como Indeed en v41) un aviso que la búsqueda mostró hoy con su descripción cuenta como
comprobado 24 h: `VISTAS`.

Límite medido el 26 nov: InfoJobs muestra unas cinco páginas de búsqueda por visita y después pide captcha, aunque se
vaya despacio. Ese control se respeta: una página por nombre, pocas por corrida (`infojobs_busquedas`) y por día
(`TOPE_DIA`), con pausa, y al primer captcha la fuente se detiene hasta la corrida siguiente. No se reinicia la visita
para seguir.
Nada se inventa: lo que el aviso no dice queda vacío, y una página sin esos datos cuenta como bloqueo.

Modo API (la vía estable): si existen los secretos `INFOJOBS_CLIENT_ID` e `INFOJOBS_CLIENT_SECRET` (una aplicación
registrada en developer.infojobs.net; guía en docs/ACTIVAR_INFOJOBS_API.md), se usa la API oficial en lugar de la
página: búsqueda `/api/9/offer` y ficha `/api/7/offer/{id}`, que trae la descripción, la fecha de creación y si el
aviso sigue activo. Con clave, el enlace se comprueba con esa ficha (`estado_del_aviso`). Las claves solo viajan en la
cabecera de autenticación: nunca en direcciones, estadísticas ni registros."""
import base64
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

from buscador import cobertura, normalizar, paises

NOMBRE = "InfoJobs"
BUSQUEDA = "https://www.infojobs.net/jobsearch/search-results/list.xhtml"
PAISES = {"ES"}
TOPE_DIA = 15                # páginas por día entre todas las corridas (la del día, la segunda pasada, «Buscar ahora»…)
MIN_DESCRIPCION = 200        # sin tanto texto no se sabe el idioma ni cuenta como vista
_DATOS = re.compile(r"window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\(\s*")
_AVISO = re.compile(r"^(?:https?:)?//www\.infojobs\.net/([^/?#\s]+/[^/?#\s]+/of-i([a-z0-9]+))")
API_BUSQUEDA = "https://api.infojobs.net/api/9/offer"
API_FICHA = "https://api.infojobs.net/api/7/offer/"
POR_PAGINA_API = 50          # el máximo que su documentación recomienda
CONTADOR = "~paginas_hoy"    # {fecha, paginas} en el estado de la fuente
_MODALIDAD = {"solo teletrabajo": (True, " (Remoto)"), "hibrido": (None, " (Híbrido)"), "presencial": (None, " (Presencial)")}

# Avisos que la búsqueda mostró en esta corrida (enlace → comprobación).
VISTAS = {}
# Modo API: avisos cuya ficha se leyó en esta corrida (enlace → comprobación: activa o cerrada), como las de LinkedIn.
FICHAS = {}


def credenciales():
    """(Client ID, Client secret) de la aplicación registrada en InfoJobs, o None si no están configuradas."""
    cid, secreto = os.environ.get("INFOJOBS_CLIENT_ID", "").strip(), os.environ.get("INFOJOBS_CLIENT_SECRET", "").strip()
    return (cid, secreto) if cid and secreto else None


def _cabeceras(cred):
    return {"Authorization": "Basic " + base64.b64encode(f"{cred[0]}:{cred[1]}".encode()).decode(),
            "Accept": "application/json"}


def aviso_de(url):
    """El identificador del aviso si la dirección es una ficha de InfoJobs; si no, ""."""
    m = _AVISO.match(str(url or ""))
    return m.group(2) if m else ""


def datos(pagina):
    """Los datos que la página de búsqueda trae para dibujarse, o None si no los trae (bloqueo, captcha u otro diseño)."""
    m = _DATOS.search(pagina or "")
    try:
        # El texto va entre comillas dentro de JSON.parse("…"): se lee como JSON hasta su comilla de cierre (una
        # descripción puede traer «");» y no es el final).
        d = json.loads(json.JSONDecoder().raw_decode(pagina, m.end())[0]) if m else None
    except (ValueError, TypeError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("offers"), list) else None


def vacante(a, hoy=""):
    """Vacante cruda desde un aviso de la búsqueda, o None si no trae título o enlace de aviso."""
    if not isinstance(a, dict) or not isinstance(a.get("title"), str) or not a["title"].strip():
        return None
    m = _AVISO.match(str(a.get("link") or ""))
    if not m:
        return None
    remoto, sufijo = _MODALIDAD.get(normalizar.texto(a.get("teleworking") or ""), (None, ""))
    publicada = str(a.get("publishedAt") or "")[:10]
    try:
        fecha = datetime.strptime(publicada, "%Y-%m-%d").date().isoformat()
    except ValueError:
        fecha = ""
    descripcion = a.get("description") if isinstance(a.get("description"), str) else ""
    empresa = a.get("companyName") if isinstance(a.get("companyName"), str) else ""
    return {"titulo": " ".join(a["title"].split()), "empresa": empresa.strip(),
            "ubicacion": paises.lugar_del_portal(a.get("city"), "ES", "España", remoto=bool(remoto)) + sufijo,
            "descripcion": descripcion.strip()[:30000], "fecha": "" if hoy and fecha > hoy else fecha,
            "enlace": "https://www.infojobs.net/" + m.group(1), "enlace_directo": "", "remoto": remoto, "fuente": NOMBRE}


def combinaciones(mapa):
    """(familia, consultas, lugar, {}) de los cargos con alguien que trabajaría en España (o todos en modo heredado).
    Como en Computrabajo: los títulos en español tienen su turno («ES:ES») si alguien de España acepta español."""
    salida = []
    for f in mapa:
        if "paises_objetivo" in f and not PAISES & set(f["paises_objetivo"] or []):
            continue  # nadie de ese cargo trabajaría en España (sin la clave, modo heredado: todos)
        es = list(f.get("consultas_es") or [])
        resto = [c for c in cobertura.consultas(f) if c not in es]
        if es and ("paises_es" not in f or PAISES & set(f["paises_es"])):
            salida.append((f["id"], es, "ES:ES", {}))
        elif es and not resto:
            salida.append((f["id"], es, "ES", {}))
        if resto:
            salida.append((f["id"], resto, "ES", {}))
    return salida


def buscar(cliente, mapa, estado, presupuesto, hoy=None, max_dias=30, reloj=time.monotonic, limite_segundos=None,
           prioritarias=()):
    """Recorre los cargos con sus nombres hasta gastar el presupuesto de páginas o hasta que InfoJobs pida captcha.
    Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    desde = (datetime.fromisoformat(hoy) - timedelta(days=max_dias)).date().isoformat()
    todas = cobertura.repartir(combinaciones(mapa), estado, hoy, prioritarias)
    # Un nombre por búsqueda, cada uno con su clave: el primero de cada combinación, luego el segundo… Lo ya buscado
    # hoy no se repite (la segunda pasada del día sigue con los nombres siguientes).
    turnos = [(k, c) for c in todas for k in range(len(c[1]))]
    turnos.sort(key=lambda t: t[0])  # estable: dentro de cada vuelta, el orden del reparto
    hora = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    contador = estado.get(CONTADOR) if isinstance(estado.get(CONTADOR), dict) else {}
    del_dia = int(contador.get("paginas") or 0) if contador.get("fecha") == hoy else 0
    crudas, vistos, hechas, bloqueada = [], set(), 0, False
    for k, (familia, consultas, lugar, _) in turnos:
        if hechas >= presupuesto or del_dia + hechas >= TOPE_DIA or bloqueada or (
                limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        b = cobertura.siguiente_busqueda(consultas, hoy, 1, f"{familia}@{lugar}", estado, desfase=k, paginada=False)
        if b is None or estado.get(b.clave_terminos) == hoy:  # ya se buscó hoy con ese nombre
            continue
        # Una página por nombre, de lo más reciente a lo más antiguo (20 avisos).
        r = cliente.get(BUSQUEDA, params={"keyword": b.terminos[0], "sortBy": "PUBLICATION_DATE"}, reintentar_429=False)
        hechas += 1
        d = datos(r.text) if r is not None and r.status_code == 200 else None
        if d is None:  # captcha, bloqueo u otro diseño: no se insiste en esta corrida
            bloqueada = True
            break
        cobertura.anotar_busqueda("infojobs", familia, lugar)
        cobertura.anotar_hecha(estado, b, hoy)
        for a in d["offers"]:
            v = vacante(a, hoy)
            if v is None or (v["fecha"] and v["fecha"] < desde):
                continue
            if len(v["descripcion"]) >= MIN_DESCRIPCION and v["fecha"]:
                VISTAS[v["enlace"]] = {"estado": "verificada", "motivo": "vista hoy en la búsqueda de InfoJobs",
                                       "comprobada_en": hora, "destino": v["enlace"]}
            if v["enlace"] not in vistos:
                vistos.add(v["enlace"])
                crudas.append(v)
    estado[CONTADOR] = {"fecha": hoy, "paginas": del_dia + hechas}
    return crudas, {"modo": "pagina", "busquedas": hechas, "bloqueada": bloqueada, "avisos": len(crudas),
                    "vistas": len(VISTAS), "combinaciones_total": len(todas)}


def _valor(campo):
    """El texto de un campo de la API, que puede venir como texto o como {"id": …, "value": …}."""
    if isinstance(campo, dict):
        campo = campo.get("value")
    return campo.strip() if isinstance(campo, str) else ""


def _fecha_api(valor, hoy=""):
    """«2026-11-20T10:00:00.000Z» → «2026-11-20»; imposible o futura, ""."""
    try:
        fecha = datetime.strptime(str(valor or "")[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""
    return "" if hoy and fecha > hoy else fecha


def _estado_de(ficha):
    """«abierta», «cerrada» o "" (no se sabe) según la ficha de la API. Solo cierran los avisos archivados o borrados."""
    if not isinstance(ficha, dict):
        return ""
    if ficha.get("deleted") is True or ficha.get("archived") is True:
        return "cerrada"
    return "abierta" if ficha.get("active") is True else ""


def vacante_api(resumen, ficha, hoy=""):
    """Vacante cruda desde un aviso de la búsqueda de la API (`resumen`) y su ficha. None si falta el título o el
    enlace. La fecha es la de creación del aviso (la de la lista puede ser la de una republicación)."""
    if not isinstance(resumen, dict) or not isinstance(ficha, dict):
        return None
    titulo = ficha.get("title") if isinstance(ficha.get("title"), str) else resumen.get("title")
    m = _AVISO.match(str(resumen.get("link") or ficha.get("link") or ""))
    if not isinstance(titulo, str) or not titulo.strip() or not m:
        return None
    remoto, sufijo = _MODALIDAD.get(normalizar.texto(_valor(resumen.get("teleworking")) or _valor(ficha.get("teleworking"))),
                                    (None, ""))
    empresa = (ficha.get("profile") or {}).get("name") if isinstance(ficha.get("profile"), dict) else ""
    empresa = empresa or ((resumen.get("author") or {}).get("name") if isinstance(resumen.get("author"), dict) else "")
    partes = [ficha.get(k) for k in ("description", "minRequirements", "desiredRequirements")]
    externo = ficha.get("externalUrlForm") if isinstance(ficha.get("externalUrlForm"), str) else ""
    ciudad = ficha.get("city") if isinstance(ficha.get("city"), str) else resumen.get("city")
    return {"titulo": " ".join(titulo.split()), "empresa": empresa.strip() if isinstance(empresa, str) else "",
            "ubicacion": paises.lugar_del_portal(ciudad, "ES", "España", remoto=bool(remoto)) + sufijo,
            "descripcion": "\n".join(x.strip() for x in partes if isinstance(x, str) and x.strip())[:30000],
            "fecha": _fecha_api(ficha.get("creationDate"), hoy),
            "enlace": "https://www.infojobs.net/" + m.group(1),
            "enlace_directo": externo.strip() if externo.strip().startswith("https://") else "",
            "remoto": remoto, "fuente": NOMBRE}


def buscar_api(cliente, cred, mapa, estado, presupuesto, max_fichas, hoy=None, max_dias=30, reloj=time.monotonic,
               limite_segundos=None, prioritarias=()):
    """Como `buscar`, con la API oficial: una búsqueda por nombre y la ficha de cada título de un cargo buscado.
    Devuelve (vacantes crudas, estadísticas). Si la clave no vale (401/403) o hay tres fallos seguidos, se detiene."""
    from buscador import familias
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    desde = (datetime.fromisoformat(hoy) - timedelta(days=max_dias)).date().isoformat()
    cabeceras = _cabeceras(cred)
    todas = cobertura.repartir(combinaciones(mapa), estado, hoy, prioritarias)
    turnos = [(k, c) for c in todas for k in range(len(c[1]))]
    turnos.sort(key=lambda t: t[0])  # estable: el primer nombre de cada combinación, luego el segundo…
    hora = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    resumenes, hechas, fallidas, seguidas, error = {}, 0, 0, 0, ""

    def agotada():
        return bool(error) or seguidas >= 3 or (limite_segundos is not None and reloj() - inicio >= limite_segundos)

    def pedir(url, params=None):
        nonlocal fallidas, seguidas, error
        r = cliente.get(url, params=params, headers=cabeceras, reintentar_429=False)
        codigo = getattr(r, "status_code", None)
        if codigo in (401, 403):
            error = f"InfoJobs rechazó la clave ({codigo}); revisar los secretos"
            return None
        try:
            datos = r.json() if codigo == 200 else None
        except ValueError:
            datos = None
        if not isinstance(datos, dict):
            fallidas += 1
            seguidas += 1
            return None
        seguidas = 0
        return datos
    for k, (familia, consultas, lugar, _) in turnos:
        if hechas >= presupuesto or agotada():
            break
        b = cobertura.siguiente_busqueda(consultas, hoy, 1, f"{familia}@{lugar}", estado, desfase=k, paginada=False)
        if b is None or estado.get(b.clave_terminos) == hoy:
            continue
        hechas += 1
        datos = pedir(API_BUSQUEDA, {"q": b.terminos[0], "country": "espana", "maxResults": str(POR_PAGINA_API)})
        if datos is None:
            continue
        cobertura.anotar_busqueda("infojobs", familia, lugar)
        cobertura.anotar_hecha(estado, b, hoy)
        for a in datos.get("offers") if isinstance(datos.get("offers"), list) else []:
            if isinstance(a, dict) and isinstance(a.get("title"), str) and aviso_de(a.get("link")) \
                    and aviso_de(a["link"]) not in resumenes:
                resumenes[aviso_de(a["link"])] = dict(a, _familia=familia)
    del_cargo = [a for a in resumenes.values() if familias.clasificar(a["title"])]
    del_cargo.sort(key=lambda a: a["_familia"] not in prioritarias)  # estable
    crudas, fichas, cerradas = [], 0, 0
    for a in del_cargo:
        if fichas >= max_fichas or agotada():
            break
        fichas += 1
        ficha = pedir(API_FICHA + aviso_de(a["link"]))
        v = vacante_api(a, ficha, hoy) if ficha is not None else None
        if v is None:
            continue
        situacion = _estado_de(ficha)
        if situacion == "cerrada":
            cerradas += 1
            FICHAS[v["enlace"]] = {"estado": "rechazada", "motivo": "vacante cerrada", "comprobada_en": hora,
                                   "destino": v["enlace"]}
            continue
        if v["fecha"] and v["fecha"] < desde:
            continue
        if situacion == "abierta" and len(v["descripcion"]) >= MIN_DESCRIPCION:
            FICHAS[v["enlace"]] = {"estado": "verificada", "motivo": "ficha específica accesible",
                                   "comprobada_en": hora, "destino": v["enlace"]}
        crudas.append(v)
    stats = {"modo": "api", "busquedas": hechas, "fallidas": fallidas, "avisos": len(resumenes),
             "del_cargo": len(del_cargo), "fichas": fichas, "cerradas": cerradas, "con_descripcion": len(crudas),
             "combinaciones_total": len(todas)}
    return crudas, dict(stats, error=error) if error else stats


def estado_del_aviso(sesion, url, titulo, coincide, timeout=12):
    """(estado, motivo, código HTTP) de un aviso de InfoJobs leyendo su ficha en la API oficial. Solo con clave."""
    cred = credenciales()
    aviso_id = aviso_de(url)
    if not cred or not aviso_id:
        return "pendiente", "sin comprobación directa", None
    r = sesion.get(API_FICHA + aviso_id, headers=_cabeceras(cred), timeout=timeout)
    if r.status_code in (404, 410):
        return "rechazada", "enlace roto", r.status_code
    if r.status_code != 200:
        return "pendiente", "acceso bloqueado o fallo temporal", r.status_code
    try:
        ficha = r.json()
    except ValueError:
        return "pendiente", "respuesta no comprobable", r.status_code
    situacion = _estado_de(ficha)
    if situacion == "cerrada":
        return "rechazada", "vacante cerrada", r.status_code
    if situacion != "abierta" or not isinstance(ficha.get("title"), str) or not coincide(titulo, ficha["title"]):
        return "pendiente", "ficha específica sin confirmar", r.status_code
    return "verificada", "ficha específica accesible", r.status_code
