"""Elempleo (Colombia): portal donde se postula en el mismo sitio. Sin sesión ni cookies. PR 1b (16 nov).

Se leen solo rutas públicas que su robots.txt no bloquea: la búsqueda `/co/ofertas-empleo/trabajo-<cargo>` y la ficha
`/co/ofertas-trabajo/...`. La lista sale del `ItemList` (schema.org) de la búsqueda y cada ficha trae su `JobPosting`:
fecha real de publicación (`datePosted`), cierre (`validThrough`), empresa, ciudad, si es remota (`TELECOMMUTE`),
desde qué país se postula (`applicantLocationRequirements`) y salario. Nada se inventa: lo que la ficha no dice queda
vacío. Como Computrabajo, rota las familias y cada corrida toma las que hace más tiempo no se revisan.
"""
import html
import json
import re
import time
from datetime import datetime, timezone

from buscador import cobertura
from buscador.fuentes.computrabajo import slug

NOMBRE = "Elempleo"
BASE = "https://www.elempleo.com"
PAISES = {"CO"}
_LDJSON = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_PERIODO = {"MONTH": "mensual", "YEAR": "anual", "HOUR": "por hora"}


def _bloques(pagina):
    for crudo in _LDJSON.findall(pagina or ""):
        try:
            datos = json.loads(crudo)
        except ValueError:
            continue
        yield from datos if isinstance(datos, list) else [datos]


def _texto(fragmento):
    limpio = re.sub(r"<(br|/p|/li)\s*/?>", "\n", str(fragmento or ""), flags=re.I)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", limpio))).strip()


def tarjetas(pagina):
    """[(enlace sin parámetros, título)] del `ItemList` de una página de resultados."""
    salida = []
    for b in _bloques(pagina):
        if b.get("@type") != "ItemList":
            continue
        for elemento in b.get("itemListElement") or []:
            item = (elemento or {}).get("item") or {}
            enlace = str(item.get("@id") or "").split("?")[0]
            if "/ofertas-trabajo/" in enlace and item.get("name"):
                salida.append((enlace, html.unescape(str(item["name"])).strip()))
    return salida


def _salario(base):
    valor = (base or {}).get("value") or {}
    moneda = (base or {}).get("currency") or ""
    minimo, maximo = valor.get("minValue"), valor.get("maxValue")
    periodo = _PERIODO.get(str(valor.get("unitText") or "").upper(), "")
    if not moneda or not (minimo or maximo) or not periodo:
        return ""
    cifra = lambda x: f"{int(float(x)):,}".replace(",", ".")
    rango = f"{cifra(minimo)} - {cifra(maximo)}" if minimo and maximo else cifra(minimo or maximo)
    return f"Salario: {moneda} {rango} {periodo}"


def _fecha(valor):
    """«2026-10-6» o «2026-10-06T…» → «2026-10-06»; otra cosa → ""."""
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})", str(valor or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def ficha(pagina, hoy):
    """Datos del `JobPosting` de la ficha, o None si no lo trae. `cerrada` si `validThrough` ya pasó."""
    posting = next((b for b in _bloques(pagina) if b.get("@type") == "JobPosting"), None)
    if not posting:
        return None
    direccion = ((posting.get("jobLocation") or {}).get("address")) or {}
    ciudad = str(direccion.get("addressLocality") or "").strip()
    remota = str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE"
    requisito = posting.get("applicantLocationRequirements") or {}
    pais_postula = str(requisito.get("name") or "").strip() if isinstance(requisito, dict) else ""
    fecha, hasta = _fecha(posting.get("datePosted")), _fecha(posting.get("validThrough"))
    descripcion = _texto(posting.get("description"))
    salario = _salario(posting.get("baseSalary"))
    if remota:
        ubicacion = f"{pais_postula or 'Colombia'} (Remoto)"
    else:
        ubicacion = ", ".join(x for x in (ciudad, "Colombia") if x)
    return {"titulo": html.unescape(str(posting.get("title") or "")).strip(),
            "empresa": str(((posting.get("hiringOrganization") or {}).get("name")) or "").strip(),
            "ubicacion": ubicacion, "remoto": True if remota else None,
            "descripcion": "\n".join(x for x in (descripcion, salario) if x)[:30000],
            "fecha": fecha if fecha and fecha <= hoy else "", "cerrada": bool(hasta) and hasta < hoy}


def buscar(cliente, mapa, estado, presupuesto, hoy=None, max_fichas=80, reloj=time.monotonic, limite_segundos=None,
           prioritarias=()):
    """Familias del panel con algún perfil en Colombia (o todas en modo heredado). Devuelve (vacantes crudas,
    estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    # Portal en español: con títulos en español del cargo (perfiles solo en español) se rota solo entre ellos.
    todas = [(f["id"], f.get("consultas_es") or cobertura.consultas(f), "CO", {}) for f in mapa
             if not f.get("paises_objetivo") or PAISES & set(f["paises_objetivo"])]
    todas = cobertura.repartir(todas, estado, hoy, prioritarias)
    avisos, vistos = [], set()
    hechas = fallidas = seguidas = 0
    for familia, consultas, _, _ in todas:
        if hechas >= presupuesto or seguidas >= 4 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        consulta = cobertura.rotar(consultas, hoy, 1)[0]
        r = cliente.get(f"{BASE}/co/ofertas-empleo/trabajo-{slug(consulta)}")
        hechas += 1
        if r is None or r.status_code != 200:
            fallidas += 1
            seguidas += 1
            continue
        seguidas = 0
        for enlace, titulo in tarjetas(r.text):
            if enlace not in vistos:
                vistos.add(enlace)
                avisos.append({"enlace": enlace, "titulo": titulo, "familia": familia})
        estado[f"{familia}@CO"] = hoy
    avisos.sort(key=lambda a: a["familia"] not in prioritarias)
    crudas, con_ficha, cerradas = [], 0, 0
    for a in avisos[:max_fichas]:
        if seguidas >= 4 or (limite_segundos and reloj() - inicio > limite_segundos):
            break
        r = cliente.get(a["enlace"])
        if r is None or r.status_code != 200:
            seguidas += 1 if r is not None and r.status_code in (403, 429) else 0
            continue
        seguidas = 0
        datos = ficha(r.text, hoy)
        if not datos:
            continue
        con_ficha += 1
        if datos.pop("cerrada"):
            cerradas += 1
            continue
        crudas.append(dict(datos, titulo=datos["titulo"] or a["titulo"], enlace=a["enlace"], enlace_directo="",
                           fuente=NOMBRE))
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(avisos), "con_descripcion": con_ficha,
                    "cerradas": cerradas, "combinaciones_total": len(todas)}
