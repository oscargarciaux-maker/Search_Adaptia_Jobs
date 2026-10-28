"""Formato común de una vacante y unión de copias del mismo aviso."""
import hashlib
from datetime import date

from buscador import enlaces, etiquetas, familias, normalizar, paises

CAMPOS_PUBLICOS = ["id", "titulo", "empresa", "ubicacion", "familias", "paises", "confianza_pais", "modalidad",
                   "nota_pais", "idioma", "ingles", "nivel", "anos_min", "salario", "herramientas",
                   "fecha_publicacion", "fecha_estimada", "visto_primera_vez", "visto_ultima_vez", "fuente", "fuentes",
                   "enlace", "enlace_directo", "tipo_enlace", "resumen"]


def huella(empresa, titulo):
    clave = normalizar.empresa(empresa) + "|" + normalizar.titulo_base(titulo)
    return hashlib.sha1(clave.encode("utf-8")).hexdigest()[:16]


def crear(titulo, empresa, enlace, fuente, ubicacion="", descripcion="", fecha="", remoto=None, enlace_directo="",
          hoy=None, consulta=""):
    """Vacante en el formato común, con familias, países y etiquetas calculadas. Devuelve None si no sirve:
    sin título, sin enlace entregable o sin ninguna familia del mapa. En una búsqueda profunda de un cargo que no está
    en el mapa (`consulta`), también entra si su título contiene esas palabras."""
    hoy = hoy or date.today().isoformat()
    titulo = " ".join(str(titulo or "").split())
    empresa = " ".join(str(empresa or "").split()) or "Empresa confidencial"
    if not titulo:
        return None
    # El enlace principal es el de LinkedIn si lo hay; si no, el mejor que no sea agregador
    candidatos = [u for u in (enlace, enlace_directo) if u]
    principal = next((u for u in candidatos if enlaces.es_linkedin(u)), "") or enlaces.mejor(candidatos)
    if not principal:
        return None
    directo = enlaces.mejor([u for u in candidatos if u != principal and not enlaces.es_linkedin(u)])
    fams = familias.clasificar(titulo, descripcion)
    if not fams and consulta:
        frase = normalizar.titulo_base(consulta)
        if frase and normalizar.contiene_frase(normalizar.titulo_base(titulo), frase):
            fams = [{"familia": "busqueda:" + frase, "coincidencia": "exacto"}]
    if not fams:
        return None
    lugar = paises.elegibles(titulo, ubicacion, descripcion, remoto)
    texto = f"{titulo}\n{descripcion}"
    return {
        "id": huella(empresa, titulo),
        "titulo": titulo, "empresa": empresa, "ubicacion": " ".join(str(ubicacion or "").split()),
        "familias": fams,
        "paises": lugar["paises"], "confianza_pais": lugar["confianza"], "modalidad": lugar["modalidad"],
        "nota_pais": lugar["nota"],
        "idioma": etiquetas.idioma(texto), "ingles": etiquetas.ingles(descripcion), "nivel": normalizar.nivel(titulo),
        "anos_min": etiquetas.anos_min(descripcion), "salario": etiquetas.salario(descripcion),
        "herramientas": familias.herramientas_en(descripcion, [f["familia"] for f in fams]) if descripcion else [],
        "fecha_publicacion": (fecha or "")[:10], "fecha_estimada": not fecha,
        "visto_primera_vez": hoy, "visto_ultima_vez": hoy,
        "fuente": fuente, "fuentes": [fuente],
        "enlace": principal, "enlace_directo": directo, "tipo_enlace": enlaces.tipo(directo or principal),
        "resumen": " ".join(str(descripcion or "").split())[:300],
        "_descripcion": str(descripcion or "")[:8000],
    }


def _rango_enlace(v):
    return enlaces.TIPOS.index(v["tipo_enlace"]) if v["tipo_enlace"] in enlaces.TIPOS else 9


def unir(a, b):
    """Une dos copias del mismo aviso: LinkedIn como enlace principal, el original como directo, países sumados,
    la fecha más antigua conocida y la descripción más larga."""
    larga, corta = (a, b) if len(a.get("_descripcion", "")) >= len(b.get("_descripcion", "")) else (b, a)
    v = dict(larga)
    todos = [x for x in (a["enlace"], a["enlace_directo"], b["enlace"], b["enlace_directo"]) if x]
    v["enlace"] = next((u for u in todos if enlaces.es_linkedin(u)), "") or enlaces.mejor(todos)
    v["enlace_directo"] = enlaces.mejor([u for u in todos if u != v["enlace"] and not enlaces.es_linkedin(u)])
    v["tipo_enlace"] = enlaces.tipo(v["enlace_directo"] or v["enlace"])
    v["paises"] = sorted(set(a["paises"]) | set(b["paises"]))
    confianzas = ["alta", "media", "baja"]
    v["confianza_pais"] = min(a["confianza_pais"], b["confianza_pais"], key=confianzas.index)
    fechas = [x["fecha_publicacion"] for x in (a, b) if x["fecha_publicacion"] and not x.get("fecha_estimada")]
    if fechas:
        v["fecha_publicacion"], v["fecha_estimada"] = min(fechas), False
    else:
        v["fecha_publicacion"] = min(x["fecha_publicacion"] or "9999" for x in (a, b)).replace("9999", "")
    v["visto_primera_vez"] = min(a["visto_primera_vez"], b["visto_primera_vez"])
    v["visto_ultima_vez"] = max(a["visto_ultima_vez"], b["visto_ultima_vez"])
    v["fuentes"] = sorted(set(a["fuentes"]) | set(b["fuentes"]))
    grados = {}
    for f in a["familias"] + b["familias"]:
        actual = grados.get(f["familia"])
        if actual is None or familias.GRADOS.index(f["coincidencia"]) < familias.GRADOS.index(actual):
            grados[f["familia"]] = f["coincidencia"]
    v["familias"] = sorted(({"familia": k, "coincidencia": g} for k, g in grados.items()),
                           key=lambda x: familias.GRADOS.index(x["coincidencia"]))
    for campo in ("ingles", "salario", "anos_min", "nivel", "idioma"):
        if not v.get(campo) and corta.get(campo):
            v[campo] = corta[campo]
    return v


def juntar(vacantes):
    """Junta copias: mismo id (empresa + cargo sin ciudad ni nivel), o misma empresa y la misma descripción completa."""
    por_id = {}
    por_desc = {}
    for v in vacantes:
        if not v:
            continue
        clave_desc = None
        desc = normalizar.texto(v.get("_descripcion", ""))
        if len(desc) >= 200:
            clave_desc = normalizar.empresa(v["empresa"]) + "#" + hashlib.sha1(desc.encode()).hexdigest()
        destino = v["id"] if v["id"] in por_id else por_desc.get(clave_desc) if clave_desc else None
        if destino and destino in por_id:
            por_id[destino] = unir(por_id[destino], v)
        else:
            destino = v["id"]
            por_id[destino] = v
        if clave_desc:
            por_desc.setdefault(clave_desc, destino)
    return list(por_id.values())


def publica(v):
    """La vacante sin los campos internos (la descripción completa no se publica)."""
    return {k: v.get(k) for k in CAMPOS_PUBLICOS}
