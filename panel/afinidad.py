"""Filtros verificables por perfil. No infiere compatibilidad con un CV ni llama a una IA."""
import re
from datetime import date

from buscador import contrato, enlaces, normalizar, tiempos
from panel.modelos import Perfil

NIVELES = ["A1", "A2", "B1", "B2", "C1", "C2", "native"]
CAMPOS_FILTRO = ("id", "titulo", "paises", "confianza_pais", "modalidad", "idioma", "publicada_en",
                 "fecha_publicacion", "fecha_estimada", "ids_agrupados", "salario")


def ligera(datos, descripcion=None):
    """Solo lo que usan los filtros, con experiencia e inglés ya interpretados por las mismas funciones del motor.
    Permite estimar sobre miles de vacantes sin conservar descripciones ni enlaces. Los años mínimos no dependen del
    texto; el inglés exigido viene calculado en el catálogo (contrato v7). Si falta y no hay descripción, se usa el
    nivel guardado tratándolo como obligatorio: la estimación puede quedar corta, nunca inflada."""
    v = {k: datos.get(k) for k in CAMPOS_FILTRO}
    v["_anos_minimos"] = contrato.anos("", datos.get("anos_min"))[0]
    if descripcion is None and datos.get("requisito_ingles") is not None:
        v["_requisito_ingles"] = datos["requisito_ingles"]
    else:
        v["_requisito_ingles"] = contrato.requisitos_idioma(descripcion or "", datos.get("ingles", ""))
    return v


# Contrato v9: niveles de ampliación para que cada perfil reciba un mínimo diario. País, idioma, plazo, enlace y los
# requisitos que el aviso sí declara nunca se amplían.
MINIMO_POR_PERFIL = 5
# Orden de uso; los dos últimos son el «último recurso» que aprobó Oscar el 12 nov (contrato v11).
AMPLIACIONES = ("sin_dato", "cargo_cercano", "remota_cercana", "experiencia_cercana", "empresa_4")
ETIQUETAS_AMPLIACION = {"sin_dato": "aviso sin años o inglés informados", "cargo_cercano": "cargo cercano",
                        "remota_cercana": "remota abierta a su país",
                        "experiencia_cercana": "experiencia cercana (±2 años)",
                        "empresa_4": "más vacantes de la misma empresa"}
TOPE_EMPRESA_AMPLIADO = 4


def relajado(perfil, nivel):
    """Copia del perfil con lo que admite el nivel de ampliación, o None si el nivel no aplica a ese perfil."""
    p = perfil if isinstance(perfil, Perfil) else Perfil.model_validate(perfil)
    cambio = {"aceptar_experiencia_sin_dato": True, "aceptar_ingles_sin_dato": True}
    if nivel == "remota_cercana":
        if "remoto" in p.modalidades:
            return None
        cambio["modalidades"] = [*p.modalidades, "remoto"]
    if nivel in ("experiencia_cercana", "empresa_4"):
        # El aviso sí dice años: se admiten hasta 2 de diferencia con el rango del perfil (nunca país, idioma ni plazo).
        if p.experiencia_min is not None:
            cambio["experiencia_min"] = max(0, p.experiencia_min - 2)
        if p.experiencia_max is not None:
            cambio["experiencia_max"] = min(40, p.experiencia_max + 2)
    return p.model_copy(update=cambio)


def evaluar_ampliada(v, perfil, hoy, nivel):
    """Evaluación con el perfil relajado del nivel; el título cercano lo decide quien llama (grado del cargo)."""
    p = relajado(perfil, nivel)
    return evaluar(v, p, hoy) if p else {"compatible": False, "motivos": ["ampliación no aplicable"], "pruebas": []}


def evaluar(v, perfil, hoy=None):
    p = perfil if isinstance(perfil, Perfil) else Perfil.model_validate(perfil)
    hoy = date.fromisoformat(hoy) if isinstance(hoy, str) else hoy or date.today()
    motivos, pruebas = [], []
    # Contrato v8: remoto → que admita postular desde su país; híbrido/presencial → oficina en su país o en los extra.
    modo, paises_v = v.get("modalidad"), set(v.get("paises") or [])
    todas = {"remoto", "hibrido", "presencial"} <= set(p.modalidades)
    if modo in ("remoto", "hibrido", "presencial") and modo not in p.modalidades or (modo not in ("remoto", "hibrido", "presencial") and not todas):
        motivos.append("modalidad diferente")
    if v.get("confianza_pais") not in {"alta", "media"}:
        motivos.append("país sin elegibilidad confirmada")
    elif modo in ("hibrido", "presencial") and not paises_v & set(p.paises_oficina):
        motivos.append("oficina en otro país")
    elif modo not in ("hibrido", "presencial") and p.vive_en not in paises_v:
        motivos.append("no admite postular desde su país")
    else:
        pruebas.append("Remota abierta a su país" if modo == "remoto" else "Ubicación compatible")
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
    # Contrato v22: con 2 años o menos, junior abierto (sin filtro de experiencia).
    junior_abierto = p.experiencia_anos is not None and p.experiencia_anos <= 2
    if (p.experiencia_min is not None or p.experiencia_max is not None) and not junior_abierto:
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
    titulo, descripcion = v.get("titulo") or "", v.get("_descripcion") or ""
    if p.experiencia_anos is not None and p.experiencia_anos >= 5 and (
            contrato.seniority(titulo) in ("intern", "junior") or contrato.tipo_contrato(titulo, descripcion) == "internship"):
        motivos.append("nivel inferior al del perfil")
    for r in p.restricciones:
        motivo = restriccion(v, r, titulo, descripcion)
        if motivo:
            motivos.append(motivo)
    return {"compatible": not motivos, "motivos": motivos, "pruebas": pruebas}


_POR_MES = {"month": 1, "year": 1 / 12}

# Contrato v22 (14 nov, pedido de Oscar): lo que el aviso pide solo como deseable no descarta. Marcas editables; se
# buscan como palabras completas en la línea u oración, o en el encabezado de la sección.
MARCAS_DESEABLE = ("deseable", "deseables", "valorable", "se valora", "se valorara", "valoraremos", "plus", "a plus",
                   "nice to have", "nice-to-have", "bonus", "bonus points", "preferred", "preferible", "preferiblemente",
                   "preferentemente", "ideally", "idealmente", "opcional", "optional", "would be great", "extra",
                   "not required", "no excluyente", "no es requisito")
_CORTE_ORACION = re.compile(r"(?<=[.;!?])\s+|\s+[•·▪◦\-–*]\s+")


def _deseable(texto_normalizado):
    return any(normalizar.contiene_frase(texto_normalizado, normalizar.texto(m)) for m in MARCAS_DESEABLE)


_VINETA = re.compile(r"^\s*([-–•·▪◦*]|\d+[.)])\s+")
SECCIONES = ("requirements", "requisitos", "responsabilidades", "responsibilities", "qualifications", "cualificaciones",
             "what you will do", "what you'll do", "que haras", "about you", "sobre ti", "perfil", "beneficios",
             "benefits", "funciones", "tareas", "must have", "must-have", "conocimientos", "skills", "habilidades",
             "experiencia", "experience", "we offer", "ofrecemos")


def menciones_obligatorias(descripcion, palabras):
    """True si la descripción menciona alguna palabra fuera de lo marcado como deseable.
    - Encabezado: «Algo:» al inicio de una línea (hasta 5 palabras antes de los dos puntos) o una línea corta con el
      nombre de una sección conocida. Si es de deseables («Nice to have», «Deseable», «Bonus»…), su sección no cuenta
      hasta el siguiente encabezado.
    - Dentro de cada línea, una oración con marca de deseable («Java is a plus», «idealmente…») no cuenta."""
    if not palabras or not descripcion:
        return False
    en_deseables = False
    for linea in str(descripcion)[:12000].splitlines():
        crudo = linea.strip()
        if not crudo:
            continue
        vineta = bool(_VINETA.match(crudo))
        prefijo, dos_puntos, resto = crudo.partition(":")
        normal = normalizar.texto(crudo)
        if not vineta and dos_puntos and 0 < len(normalizar.texto(prefijo).split()) <= 5:
            en_deseables = _deseable(normalizar.texto(prefijo))
            contenido = resto
        elif not vineta and len(normal.split()) <= 4 and not re.search(r"[.!?)]$", crudo) and (
                _deseable(normal) or any(normalizar.contiene_frase(normal, normalizar.texto(x)) for x in SECCIONES)):
            en_deseables = _deseable(normal)
            contenido = ""
        else:
            contenido = crudo
        if en_deseables or not contenido.strip():
            continue
        for oracion in _CORTE_ORACION.split(contenido):
            o = normalizar.texto(oracion)
            if not _deseable(o) and any(normalizar.contiene_frase(o, w) for w in palabras):
                return True
    return False


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
        # Contrato v11: un post se comprueba al leerlo y no tiene estado de cierre; vale 24 h para compartir.
        if 0 <= edad < (24 if datos.get("tipo") == "post" else 6) * 3600:
            url = contrato.url_limpia(e.get("url", ""))
            originales = {contrato.url_limpia(x) for x in
                          [datos.get("enlace"), datos.get("enlace_directo"), *datos.get("enlaces_alternativos", [])] if x}
            if url in originales and enlaces.sirve(url):
                return url
    return ""
