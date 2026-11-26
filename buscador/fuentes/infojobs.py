"""InfoJobs (España): portal donde se postula en el mismo sitio. Contrato v50 §3: España no tenía ninguna fuente local.
Sin sesión ni cookies.

La página de búsqueda trae cada aviso completo dentro de sus datos (`window.__INITIAL_PROPS__` → `offers`): título,
empresa, ciudad, modalidad, fecha, enlace y descripción. La ficha de cada aviso pide captcha y nunca se abre. Por eso
(decisión de Oscar del 26 nov, como Indeed en v41) un aviso que la búsqueda mostró hoy con su descripción cuenta como
comprobado 24 h: `VISTAS`.

Límite medido el 26 nov: InfoJobs muestra unas cinco páginas de búsqueda por visita y después pide captcha, aunque se
vaya despacio. Ese control se respeta: una página por nombre, pocas por corrida (`infojobs_busquedas`), con pausa, y
al primer captcha la fuente se detiene hasta la corrida siguiente. No se reinicia la visita para seguir.
Nada se inventa: lo que el aviso no dice queda vacío, y una página sin esos datos cuenta como bloqueo."""
import json
import re
import time
from datetime import datetime, timedelta, timezone

from buscador import cobertura, normalizar, paises

NOMBRE = "InfoJobs"
BUSQUEDA = "https://www.infojobs.net/jobsearch/search-results/list.xhtml"
PAISES = {"ES"}
NOMBRES, NOMBRES_ES = 2, 4   # nombres del cargo que se buscan por turno (generales y en español)
MIN_DESCRIPCION = 200        # sin tanto texto no se sabe el idioma ni cuenta como vista
_DATOS = re.compile(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\((".*?")\);', re.S)
_AVISO = re.compile(r"^(?:https?:)?//www\.infojobs\.net/([a-z0-9-]+/[a-z0-9-]+/of-i[a-z0-9]+)")
_MODALIDAD = {"solo teletrabajo": (True, " (Remoto)"), "hibrido": (None, " (Híbrido)"), "presencial": (None, " (Presencial)")}

# Avisos que la búsqueda mostró en esta corrida (enlace → comprobación).
VISTAS = {}


def datos(pagina):
    """Los datos que la página de búsqueda trae para dibujarse, o None si no los trae (bloqueo, captcha u otro diseño)."""
    m = _DATOS.search(pagina or "")
    try:
        d = json.loads(json.loads(m.group(1))) if m else None
    except ValueError:
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
            "ubicacion": paises.lugar_del_portal(a.get("city"), "ES", "España") + sufijo,
            "descripcion": descripcion.strip()[:30000], "fecha": "" if hoy and fecha > hoy else fecha,
            "enlace": "https://www.infojobs.net/" + m.group(1), "enlace_directo": "", "remoto": remoto, "fuente": NOMBRE}


def combinaciones(mapa):
    """(familia, consultas, lugar, {}) de los cargos con alguien que trabajaría en España (o todos en modo heredado).
    Como en Computrabajo: los títulos en español tienen su turno («ES:ES») si alguien de España acepta español."""
    salida = []
    for f in mapa:
        if f.get("paises_objetivo") and not PAISES & set(f["paises_objetivo"]):
            continue
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
    # Varios nombres por combinación, cada uno con su clave: el primero de cada una, luego el segundo…
    turnos = [(k, c) for c in todas
              for k in range(min(len(c[1]), NOMBRES_ES if cobertura.es_espanol(c[2]) else NOMBRES))]
    turnos.sort(key=lambda t: t[0])  # estable: dentro de cada vuelta, el orden del reparto
    hora = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    crudas, vistos, hechas, bloqueada = [], set(), 0, False
    for k, (familia, consultas, lugar, _) in turnos:
        if hechas >= presupuesto or bloqueada or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        b = cobertura.siguiente_busqueda(consultas, hoy, 1, f"{familia}@{lugar}", estado, desfase=k, paginada=False)
        if b is None:  # contrato v47: ya se buscaron hoy todos sus nombres
            continue
        # Una página por nombre, de lo más reciente a lo más antiguo (20 avisos).
        r = cliente.get(BUSQUEDA, params={"keyword": b.terminos[0], "sortBy": "PUBLICATION_DATE"}, reintentar_429=False)
        hechas += 1
        cobertura.anotar_busqueda("infojobs", familia, lugar)
        d = datos(r.text) if r is not None and r.status_code == 200 else None
        if d is None:  # captcha, bloqueo u otro diseño: no se insiste en esta corrida
            bloqueada = True
            break
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
    return crudas, {"busquedas": hechas, "bloqueada": bloqueada, "avisos": len(crudas), "vistas": len(VISTAS),
                    "combinaciones_total": len(todas)}
