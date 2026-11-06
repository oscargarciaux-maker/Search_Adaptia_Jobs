"""Formato común de una vacante y unión de copias del mismo aviso."""
import hashlib
from datetime import date

from buscador import calidad, enlaces, etiquetas, familias, normalizar, paises, tiempos

CAMPOS_PUBLICOS = ["id", "titulo", "empresa", "ubicacion", "familias", "paises", "confianza_pais", "modalidad",
                   "nota_pais", "idioma", "ingles", "nivel", "anos_min", "salario", "herramientas",
                   "fecha_publicacion", "fecha_estimada", "visto_primera_vez", "visto_ultima_vez", "fuente", "fuentes",
                   "enlace", "enlace_directo", "tipo_enlace", "resumen", "publicada_en", "detectada_en", "vista_en",
                   "verificacion", "rol_entrega_actual", "enlaces_alternativos", "duplicada_de", "ids_agrupados"]


def huella(empresa, titulo, enlace=""):
    from buscador.contrato import url_limpia
    clave = normalizar.empresa(empresa) + "|" + (url_limpia(enlace) if enlace else normalizar.texto(titulo))
    return hashlib.sha1(clave.encode("utf-8")).hexdigest()[:16]


def crear(titulo, empresa, enlace, fuente, ubicacion="", descripcion="", fecha="", remoto=None, enlace_directo="",
          hoy=None, consulta="", publicada_en="", capturada=None, fecha_origen=""):
    """Vacante en el formato común, con familias, países y etiquetas calculadas. Devuelve None si no sirve:
    sin título, sin enlace entregable o sin ninguna familia del mapa. En una búsqueda profunda de un cargo que no está
    en el mapa (`consulta`), también entra si su título contiene esas palabras."""
    hoy = hoy or date.today().isoformat()
    capturada = tiempos.instante(capturada) or tiempos.ahora()
    titulo = " ".join(str(titulo or "").split())
    empresa = " ".join(str(empresa or "").split()) or "Empresa confidencial"
    if not titulo:
        return None
    # El enlace principal es el de LinkedIn si lo hay; si no, el mejor que no sea agregador
    candidatos = [u for u in (enlace, enlace_directo) if u]
    principal = next((u for u in candidatos if enlaces.es_linkedin(u)), "") or enlaces.mejor(candidatos)
    if not principal:
        return None
    if calidad.motivo(titulo, principal, fuente):
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
        "id": huella(empresa, titulo, principal),
        "titulo": titulo, "empresa": empresa, "ubicacion": " ".join(str(ubicacion or "").split()),
        "familias": fams,
        "paises": lugar["paises"], "confianza_pais": lugar["confianza"], "modalidad": lugar["modalidad"],
        "nota_pais": lugar["nota"],
        "idioma": etiquetas.idioma(texto), "ingles": etiquetas.ingles(descripcion), "nivel": normalizar.nivel(titulo),
        "anos_min": etiquetas.anos_min(descripcion), "salario": etiquetas.salario(descripcion),
        "herramientas": familias.herramientas_en(descripcion, [f["familia"] for f in fams]) if descripcion else [],
        "fecha_publicacion": (fecha or "")[:10], "fecha_estimada": not fecha,
        "publicada_en": tiempos.instante(publicada_en or fecha),
        "detectada_en": capturada, "vista_en": capturada,
        "_fecha_publicacion_origen": fecha_origen,
        "visto_primera_vez": hoy, "visto_ultima_vez": hoy,
        "fuente": fuente, "fuentes": [fuente],
        "enlace": principal, "enlace_directo": directo, "tipo_enlace": enlaces.tipo(directo or principal),
        "resumen": " ".join(str(descripcion or "").split())[:300],
        "_descripcion": str(descripcion or "")[:30000],
    }


def reetiquetar(v):
    """Vuelve a leer de la descripción guardada las etiquetas de texto, así un arreglo en `etiquetas` también llega a
    las vacantes de noches anteriores."""
    desc = v.get("_descripcion", "")
    v["familias"] = familias.clasificar(v["titulo"], desc)
    if desc:
        v["ingles"], v["anos_min"], v["salario"] = etiquetas.ingles(desc), etiquetas.anos_min(desc), etiquetas.salario(desc)
    if "greenhouse" in v.get("fuente", "").lower() and not v.get("_fecha_publicacion_origen"):
        # Las versiones anteriores confundían updated_at con publicación. No certificar esa fecha histórica.
        v["fecha_publicacion"], v["publicada_en"], v["fecha_estimada"] = "", "", True
    lugar = paises.elegibles(v["titulo"], v.get("ubicacion", ""), desc,
                             True if v.get("modalidad") == "remoto" else None)
    v.update(paises=lugar["paises"], modalidad=lugar["modalidad"], confianza_pais=lugar["confianza"], nota_pais=lugar["nota"])
    return v


def _rango_enlace(v):
    return enlaces.TIPOS.index(v["tipo_enlace"]) if v["tipo_enlace"] in enlaces.TIPOS else 9


def unir(a, b):
    """Une dos copias del mismo aviso: LinkedIn como enlace principal, el original como directo, países sumados,
    la fecha más antigua conocida y la descripción más larga."""
    larga, corta = (a, b) if len(a.get("_descripcion", "")) >= len(b.get("_descripcion", "")) else (b, a)
    v = dict(larga)
    v["id"] = a["id"]  # conserva referencias existentes al completar una oferta
    todos = [x for x in (a["enlace"], a["enlace_directo"], b["enlace"], b["enlace_directo"]) if x]
    v["enlace"] = next((u for u in todos if enlaces.es_linkedin(u)), "") or enlaces.mejor(todos)
    v["enlace_directo"] = enlaces.mejor([u for u in todos if u != v["enlace"] and not enlaces.es_linkedin(u)])
    v["tipo_enlace"] = enlaces.tipo(v["enlace_directo"] or v["enlace"])
    v["paises"] = sorted(set(a["paises"]) | set(b["paises"]))
    confianzas = ["alta", "media", "baja"]
    v["confianza_pais"] = max(a["confianza_pais"], b["confianza_pais"], key=confianzas.index)
    if v["confianza_pais"] == "baja":
        v["nota_pais"] = "confirmar países: fuentes con ubicación incierta"
    v["_enlaces"] = sorted(set(todos + a.get("_enlaces", []) + b.get("_enlaces", [])))
    v["_ids_fusionados"] = sorted({a["id"], b["id"], *a.get("_ids_fusionados", []), *b.get("_ids_fusionados", [])})
    fechas = [x["fecha_publicacion"] for x in (a, b) if x["fecha_publicacion"] and not x.get("fecha_estimada")]
    if fechas:
        v["fecha_publicacion"], v["fecha_estimada"] = min(fechas), False
    else:
        v["fecha_publicacion"] = min(x["fecha_publicacion"] or "9999" for x in (a, b)).replace("9999", "")
    v["visto_primera_vez"] = min(a["visto_primera_vez"], b["visto_primera_vez"])
    v["visto_ultima_vez"] = max(a["visto_ultima_vez"], b["visto_ultima_vez"])
    v["detectada_en"] = min((x.get("detectada_en") for x in (a, b) if x.get("detectada_en")), default="")
    if not a.get("detectada_en") and a.get("visto_primera_vez", "") <= b.get("visto_primera_vez", ""):
        v["detectada_en"] = ""  # primera detección histórica sin hora: no inventarla al volver a ver el aviso
    v["vista_en"] = max(a.get("vista_en", ""), b.get("vista_en", ""))
    horas = [x.get("publicada_en") for x in (a, b) if x.get("publicada_en") and
             x.get("fecha_publicacion") == v.get("fecha_publicacion")]
    v["publicada_en"] = min(horas, default="")
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
    """Une por enlace compartido o contenido + empresa + título + ubicación iguales.

    Un nombre de cargo parecido no identifica una oferta. No recupera registros que el código anterior ya fusionó.
    """
    from buscador.contrato import url_limpia
    from buscador import identidad
    por_id = {}
    por_desc = {}
    por_url = {}
    por_grupo = {}
    for v in vacantes:
        if not v:
            continue
        clave_desc = None
        desc = normalizar.texto(v.get("_descripcion", ""))
        if len(desc) >= 200 and identidad.grupo(v):
            clave_desc = (normalizar.empresa(v["empresa"]), normalizar.texto(v["titulo"]),
                          normalizar.texto(v.get("ubicacion", "")), hashlib.sha256(desc.encode()).hexdigest())
        urls = {url_limpia(u) for u in [v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])] if u}
        coincidencias = {por_url[u] for u in urls if u in por_url}
        if clave_desc and clave_desc in por_desc:
            coincidencias.add(por_desc[clave_desc])
        grupo = identidad.grupo(v)
        if grupo:
            for identificador in por_grupo.get(grupo, []):
                if identificador in por_id and identidad.misma(por_id[identificador], v):
                    coincidencias.add(identificador)
        destino = next(iter(coincidencias), None)
        if len(coincidencias) > 1:
            # Una tercera fuente puede demostrar que dos grupos anteriores eran la misma oferta.
            destino = next(k for k in por_id if k in coincidencias)
            for otro in coincidencias - {destino}:
                por_id[destino] = unir(por_id[destino], por_id.pop(otro))
                for indice in (por_url, por_desc):
                    for k in [k for k, identificador in indice.items() if identificador == otro]:
                        indice[k] = destino
        if destino and destino in por_id:
            por_id[destino] = unir(por_id[destino], v)
        else:
            destino = v["id"]
            por_id[destino] = v
        if clave_desc:
            por_desc.setdefault(clave_desc, destino)
        for u in urls:
            por_url[u] = destino
        if grupo:
            por_grupo.setdefault(grupo, set()).add(destino)
    return list(por_id.values())


def publica(v):
    """La vacante sin los campos internos (la descripción completa no se publica)."""
    from buscador.contrato import url_limpia
    salida = {k: v.get(k) for k in CAMPOS_PUBLICOS}
    salida["enlaces_alternativos"] = sorted({url_limpia(u) for u in
        [v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])] if u})
    salida["ids_agrupados"] = sorted({v["id"], *v.get("_ids_fusionados", [])})
    return salida
