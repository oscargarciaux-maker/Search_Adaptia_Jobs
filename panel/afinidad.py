"""Filtros verificables por perfil. No infiere compatibilidad con un CV ni llama a una IA."""
from datetime import date

from buscador import contrato, enlaces, tiempos
from panel.modelos import Perfil

NIVELES = ["A1", "A2", "B1", "B2", "C1", "C2", "native"]
CAMPOS_FILTRO = ("id", "titulo", "paises", "confianza_pais", "modalidad", "idioma", "publicada_en",
                 "fecha_publicacion", "fecha_estimada", "ids_agrupados")


def ligera(datos, descripcion=""):
    """Solo lo que usan los filtros, con experiencia e inglés ya interpretados por las mismas funciones del motor.
    Permite estimar sobre miles de vacantes sin conservar descripciones ni enlaces."""
    v = {k: datos.get(k) for k in CAMPOS_FILTRO}
    v["_anos_minimos"] = contrato.anos(descripcion, datos.get("anos_min"))[0]
    v["_requisito_ingles"] = contrato.requisitos_idioma(descripcion, datos.get("ingles", ""))
    return v


def evaluar(v, perfil, hoy=None):
    p = perfil if isinstance(perfil, Perfil) else Perfil.model_validate(perfil)
    hoy = date.fromisoformat(hoy) if isinstance(hoy, str) else hoy or date.today()
    motivos, pruebas = [], []
    if not set(v.get("paises") or []) & set(p.paises) or v.get("confianza_pais") not in {"alta", "media"}:
        motivos.append("país sin elegibilidad confirmada")
    else:
        pruebas.append("Ubicación compatible")
    if p.modalidad != "cualquiera" and v.get("modalidad") != p.modalidad:
        motivos.append("modalidad diferente")
    if v.get("idioma") not in p.idiomas:
        motivos.append("idioma del aviso diferente")
    publicada = tiempos.instante(v.get("publicada_en"))
    try:
        fecha = date.fromisoformat((publicada or v.get("fecha_publicacion") or "")[:10])
        edad = (hoy - fecha).days
        if v.get("fecha_estimada") or not 0 <= edad <= p.antiguedad_dias:
            motivos.append("publicación fuera del plazo")
        else:
            pruebas.append(f"Publicada hace {edad} días")
    except (ValueError, TypeError):
        motivos.append("fecha de publicación sin confirmar")
    # La vista previa precalcula estos dos datos con las mismas funciones para no conservar descripciones.
    minimo = v["_anos_minimos"] if "_anos_minimos" in v else contrato.anos(v.get("_descripcion", ""), v.get("anos_min"))[0]
    if p.experiencia_min is not None or p.experiencia_max is not None:
        if minimo in ("", None):
            if not p.aceptar_experiencia_sin_dato:
                motivos.append("experiencia no informada")
            else:
                pruebas.append("Experiencia no informada, admitida por configuración")
        elif (p.experiencia_min is not None and minimo < p.experiencia_min) or (p.experiencia_max is not None and minimo > p.experiencia_max):
            motivos.append("experiencia fuera del rango")
        else:
            pruebas.append(f"Exige {minimo} años de experiencia")
    if p.ingles_maximo != "sin_filtro":
        requisito = v["_requisito_ingles"] if "_requisito_ingles" in v else contrato.requisitos_idioma(
            v.get("_descripcion", ""), v.get("ingles", ""))
        partes = requisito.split(":")
        nivel = partes[1] if len(partes) > 1 else ""
        obligatorio = len(partes) > 2 and partes[2] == "1"
        if nivel not in NIVELES:
            if not p.aceptar_ingles_sin_dato:
                motivos.append("inglés requerido sin confirmar")
            else:
                pruebas.append("Inglés no informado, admitido por configuración")
        elif obligatorio and NIVELES.index(nivel) > NIVELES.index(p.ingles_maximo):
            motivos.append("inglés requerido superior al indicado")
        else:
            pruebas.append(f"Inglés {nivel}" + (" deseable" if not obligatorio else " requerido"))
    return {"compatible": not motivos, "motivos": motivos, "pruebas": pruebas}


def enlace_utilizable(row, ahora=None):
    """Lee evidencia vigente, no convierte un HTTP 200 ni un estado histórico en disponibilidad."""
    from datetime import datetime, timezone
    ahora = ahora or datetime.now(timezone.utc)
    v = row.get("catalogo_vacantes") or {}
    datos = v.get("datos") or {}
    if v.get("status") != "active" or datos.get("duplicada_de"):
        return ""
    comprobaciones = (datos.get("verificacion") or {}).get("enlaces", [])
    for e in sorted(comprobaciones, key=lambda x: (not enlaces.es_linkedin(x.get("url", "")),
                                                   x.get("url") != datos.get("enlace"))):
        fecha = tiempos.instante(e.get("comprobada_en") or e.get("verificada_en") or e.get("checked_at"))
        if not fecha or e.get("estado") != "verificada":
            continue
        edad = (ahora - datetime.fromisoformat(fecha.replace("Z", "+00:00"))).total_seconds()
        if 0 <= edad < 6 * 3600:
            url = contrato.url_limpia(e.get("url", ""))
            originales = {contrato.url_limpia(x) for x in
                          [datos.get("enlace"), datos.get("enlace_directo"), *datos.get("enlaces_alternativos", [])] if x}
            if url in originales and enlaces.sirve(url):
                return url
    return ""
