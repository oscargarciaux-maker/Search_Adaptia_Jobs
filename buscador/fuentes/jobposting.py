"""Lector común del `JobPosting` (schema.org) de una ficha de empleo. Contrato v44: lo comparten Elempleo, Hireline y
Magneto. Lee con cuidado: un portal puede escribir la dirección, la empresa o el salario como texto, lista o diccionario,
y una ficha rara no debe tumbar la fuente. Nada se inventa: lo que la ficha no dice queda vacío."""
import html
import json
import re

from buscador import normalizar, paises

_LDJSON = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_PERIODO = {"MONTH": "mensual", "YEAR": "anual", "HOUR": "por hora"}


def bloques(pagina):
    """Todos los objetos JSON-LD de la página (incluidos los de `@graph`)."""
    for crudo in _LDJSON.findall(pagina or ""):
        try:
            datos = json.loads(crudo.strip())
        except ValueError:
            continue
        for b in datos if isinstance(datos, list) else (datos.get("@graph") or [datos]) if isinstance(datos, dict) else []:
            if isinstance(b, dict):
                yield b


def texto(fragmento):
    limpio = re.sub(r"<(br|/p|/li)\s*/?>", "\n", str(fragmento or ""), flags=re.I)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", limpio))).strip()


def fecha(valor):
    """«2026-10-6» o «2026-10-06T…» → «2026-10-06»; otra cosa → ""."""
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})", str(valor or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _dic(valor):
    valor = valor[0] if isinstance(valor, list) and valor else valor
    return valor if isinstance(valor, dict) else {}


def _uno(valor):
    return str((valor[0] if valor else "") if isinstance(valor, list) else (valor or "")).strip()


def salario(base):
    base = _dic(base)
    valor = _dic(base.get("value"))
    moneda = str(base.get("currency") or "")
    periodo = _PERIODO.get(str(valor.get("unitText") or "").upper(), "")

    def cifra(x):
        try:
            return f"{int(float(x)):,}".replace(",", ".")
        except (TypeError, ValueError):
            return ""
    minimo, maximo = cifra(valor.get("minValue")), cifra(valor.get("maxValue"))
    if not moneda or not (minimo or maximo) or not periodo:
        return ""
    rango = f"{minimo} - {maximo}" if minimo and maximo else (minimo or maximo)
    return f"Salario: {moneda} {rango} {periodo}"


def _nombre_pais(codigo):
    return next((p["nombre"] for p in paises.mundo()["lista"] if p["codigo"] == codigo), codigo)


def ficha(pagina, hoy, pais_defecto):
    """Datos del primer `JobPosting`, o None si la ficha no lo trae. `cerrada` si `validThrough` ya pasó.
    `pais_defecto`: código del país del portal, si la ficha no dice el suyo."""
    posting = next((b for b in bloques(pagina) if b.get("@type") == "JobPosting"), None)
    if not posting:
        return None
    lugar = _dic(posting.get("jobLocation"))
    direccion = lugar.get("address")
    direccion = _dic(direccion) if not isinstance(direccion, str) else {"addressLocality": direccion}
    ciudad = _uno(direccion.get("addressLocality"))
    crudo = _uno(direccion.get("addressCountry"))
    if len(crudo) == 2 and crudo.isalpha():
        pais = _nombre_pais(crudo.upper())
    else:
        pais = crudo.title() if crudo else _nombre_pais(pais_defecto)
    titulo = html.unescape(str(posting.get("title") or "")).strip()
    t = normalizar.texto(titulo)
    remota = str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE" or bool(
        re.search(r"\b(remot[oa]|home office|teletrabajo)\b", t))
    hibrida = bool(re.search(r"\bhibrid[oa]\b", t))
    requisitos = posting.get("applicantLocationRequirements") or []
    requisitos = requisitos if isinstance(requisitos, list) else [requisitos]
    postula = [_uno(r.get("name")) for r in requisitos if isinstance(r, dict) and r.get("name")]
    if remota:
        ubicacion = f"{', '.join(postula) or pais} (Remoto)"
    else:
        ubicacion = ", ".join(x for x in (ciudad, pais) if x) + (" (Híbrido)" if hibrida else "")
    empresa = posting.get("hiringOrganization")
    empresa = empresa if isinstance(empresa, str) else _dic(empresa).get("name")
    publicada, hasta = fecha(posting.get("datePosted")), fecha(posting.get("validThrough"))
    return {"titulo": titulo, "empresa": str(empresa or "").strip(), "ubicacion": ubicacion,
            "remoto": True if remota else None,
            "descripcion": "\n".join(x for x in (texto(posting.get("description")), salario(posting.get("baseSalary")))
                                     if x)[:30000],
            "fecha": publicada if publicada and publicada <= hoy else "", "cerrada": bool(hasta) and hasta < hoy}


def leer_fichas(cliente, avisos, hoy, fuente, max_fichas, reloj, inicio, limite_segundos=None):
    """Lee las fichas de `avisos` [(enlace, título de respaldo, país)] con su presupuesto. Una ficha que no se puede
    leer se salta (no tumba la fuente). Devuelve (vacantes crudas, {con_descripcion, cerradas, errores})."""
    crudas, stats, seguidas = [], {"con_descripcion": 0, "cerradas": 0, "errores": 0}, 0
    for enlace, titulo, pais in avisos[:max_fichas]:
        if seguidas >= 4 or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        r = cliente.get(enlace)
        if r is None or r.status_code != 200:
            seguidas += 1 if r is not None and r.status_code in (403, 429) else 0
            continue
        seguidas = 0
        try:
            datos = ficha(r.text, hoy, pais)
        except (AttributeError, TypeError, ValueError):
            stats["errores"] += 1
            continue
        if not datos:
            continue
        stats["con_descripcion"] += 1
        if datos.pop("cerrada"):
            stats["cerradas"] += 1
            continue
        crudas.append(dict(datos, titulo=datos["titulo"] or titulo, enlace=enlace, enlace_directo="", fuente=fuente))
    return crudas, stats
