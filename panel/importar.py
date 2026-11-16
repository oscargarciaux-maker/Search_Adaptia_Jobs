"""Importar clientes desde un CSV (15 nov). Crea clientes, perfiles y cargos en el borrador exactamente como si el
operador los hubiera creado a mano en el panel: quedan guardados en Supabase y la búsqueda siguiente los usa. Nada
queda fijo en el código; los datos de los clientes solo viajan del archivo del operador a su base privada.

Una fila por perfil (un cliente con dos perfiles ocupa dos filas con el mismo nombre). Las listas van separadas por
«|». Una celda vacía toma el mismo valor por defecto que un perfil nuevo creado en el panel. Nunca se inventa un dato:
lo que no se entiende es un error de esa fila y no se guarda nada hasta corregirlo.
"""
import csv
import io
import re
from uuid import uuid4

from pydantic import ValidationError

from buscador import normalizar, paises
from panel import modelos
from panel.modelos import META_POR_DEFECTO, Configuracion, Contacto, Perfil
from panel.repositorio import ErrorRepositorio

COLUMNAS = ["nombre", "comunidad", "whatsapp", "nombre_saludo", "acepto_whatsapp", "cargo", "meta_diaria", "vive_en",
            "modalidades", "ciudades", "se_mudaria_a", "puede_trabajar_en", "acepta_horario", "idiomas",
            "antiguedad_dias", "experiencia_anos", "margen_experiencia", "ingles_maximo", "sectores_preferidos",
            "palabras_preferidas", "no_acepta_palabras", "salario_minimo", "no_acepta_contrato",
            "nombres_del_cargo", "funciones_del_cargo", "admitir_ingles_no_informado",
            "admitir_experiencia_no_informada", "nombre_anterior"]
OBLIGATORIAS = ("nombre", "cargo")
ACTUALES = ("mantener", "archivar", "borrar")

# Ejemplo ficticio para la plantilla (nunca datos reales).
PLANTILLA_EJEMPLO = {
    "nombre": "Persona de ejemplo", "comunidad": "no", "whatsapp": "+57 300 000 0000", "nombre_saludo": "Ana",
    "acepto_whatsapp": "sí", "cargo": "Product Designer", "meta_diaria": "10", "vive_en": "Colombia",
    "modalidades": "remoto|híbrido", "ciudades": "Bogotá", "se_mudaria_a": "España", "puede_trabajar_en": "",
    "acepta_horario": "EE. UU. Este", "idiomas": "español|inglés", "antiguedad_dias": "14", "experiencia_anos": "5",
    "margen_experiencia": "3", "ingles_maximo": "B2", "sectores_preferidos": "fintech", "palabras_preferidas": "Figma",
    "no_acepta_palabras": "call center", "salario_minimo": "2000 USD mes", "no_acepta_contrato": "prácticas",
    "admitir_ingles_no_informado": "sí", "admitir_experiencia_no_informada": "sí",
}

# Regiones que se pueden escribir en las listas de países (perfiles muy móviles: «Europa», «UE», «LATAM»…).
UE = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT",
      "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
EUROPA = UE + ["GB", "CH", "NO", "IS", "LI", "AD", "MC", "SM", "AL", "BA", "ME", "MK", "RS", "MD", "UA", "XK"]


def _regiones():
    from panel.revision import grupos_paises
    g = grupos_paises()
    latam = list(g["LATAM"])
    return {"europa": EUROPA, "europe": EUROPA, "ue": UE, "union europea": UE, "eu": UE, "european union": UE,
            "latam": latam, "latinoamerica": latam, "america latina": latam, "latam y espana": list(g["LATAM_ES"]),
            "norteamerica": ["US", "CA", "MX"], "north america": ["US", "CA", "MX"],
            "america": latam + ["US", "CA"], "americas": latam + ["US", "CA"], "toda america": latam + ["US", "CA"]}


_SI = {"si", "s", "x", "true", "1", "yes", "y"}
_NO = {"no", "n", "false", "0", ""}
_MODALIDADES = {"remoto": "remoto", "remote": "remoto", "teletrabajo": "remoto", "hibrido": "hibrido",
                "hybrid": "hibrido", "mixto": "hibrido", "presencial": "presencial", "on site": "presencial",
                "onsite": "presencial", "oficina": "presencial", "en oficina": "presencial"}
_HORARIOS = {"ee uu este": "us_este", "eeuu este": "us_este", "us este": "us_este", "us east": "us_este",
             "est": "us_este", "us_este": "us_este", "este": "us_este",
             "ee uu pacifico": "us_pacifico", "eeuu pacifico": "us_pacifico", "us pacifico": "us_pacifico",
             "us pacific": "us_pacifico", "pst": "us_pacifico", "pacifico": "us_pacifico", "us_pacifico": "us_pacifico",
             "europa": "europa", "europe": "europa", "cet": "europa"}
_IDIOMAS = {"es": "es", "espanol": "es", "castellano": "es", "spanish": "es",
            "en": "en", "ingles": "en", "english": "en"}
_INGLES = {"": "sin_filtro", "sin filtro": "sin_filtro", "sin_filtro": "sin_filtro", "cualquiera": "sin_filtro",
           "a1": "A1", "a2": "A2", "b1": "B1", "b2": "B2", "c1": "C1", "c2": "C2",
           "nativo": "native", "native": "native", "bilingue": "native"}
_CONTRATOS = {"freelance": "freelance", "independiente": "freelance", "por proyecto": "freelance",
              "medio tiempo": "part_time", "part time": "part_time", "por horas": "part_time",
              "temporal": "contract", "contrato": "contract", "contract": "contract", "contractor": "contract",
              "practicas": "internship", "pasantia": "internship", "internship": "internship", "becario": "internship"}
_PERIODOS = {"mes": "month", "mensual": "month", "month": "month", "año": "year", "ano": "year", "anual": "year",
             "year": "year", "hora": "hour", "hour": "hour"}
_MONEDAS = set(modelos.MONEDAS.__args__)


def plantilla():
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=COLUMNAS, delimiter=";")
    escritor.writeheader()
    escritor.writerow(PLANTILLA_EJEMPLO)
    return "﻿" + salida.getvalue()


def _clave(texto):
    return "_".join(normalizar.texto(texto or "").replace("/", " ").split())


def _norm(texto):
    return normalizar.texto(texto or "")


def _lista(valor):
    return [x.strip() for x in str(valor or "").split("|") if x.strip()]


def leer(contenido):
    """Filas del CSV con las columnas normalizadas (acepta «;» o «,», tildes y mayúsculas en el encabezado)."""
    texto = contenido.lstrip("﻿").strip()
    if not texto:
        raise ErrorRepositorio("El archivo está vacío.", 422)
    primera = texto.splitlines()[0]
    separador = ";" if primera.count(";") >= primera.count(",") else ","
    lector = csv.DictReader(io.StringIO(texto), delimiter=separador)
    columnas = {c: _clave(c) for c in (lector.fieldnames or [])}
    faltan = [c for c in OBLIGATORIAS if c not in columnas.values()]
    if faltan:
        raise ErrorRepositorio("Al archivo le faltan las columnas: " + ", ".join(faltan) +
                               ". Descarga la plantilla para ver el formato.", 422)
    desconocidas = sorted(set(columnas.values()) - set(COLUMNAS) - {""})
    filas = []
    for n, fila in enumerate(lector, start=2):
        datos = {columnas[k]: (v or "").strip() for k, v in fila.items() if k in columnas}
        if any(datos.values()):
            filas.append((n, datos))
    if not filas:
        raise ErrorRepositorio("El archivo no tiene filas con clientes.", 422)
    if len(filas) > 1000:
        raise ErrorRepositorio("Como máximo 1000 filas por archivo.", 422)
    return filas, desconocidas


def _pais(valor, errores, campo):
    v = valor.strip()
    if len(v) == 2 and v.upper() in paises.mundo()["codigos"]:
        return v.upper()
    codigos = paises.mundo()["por_nombre"].get(_norm(v)) or set()
    if len(codigos) == 1:
        return next(iter(codigos))
    errores.append(f"{campo}: no reconozco el país «{v}».")
    return None


def _paises(valor, errores, campo):
    regiones, salida = _regiones(), []
    for v in _lista(valor):
        codigos = regiones.get(_norm(v)) or [_pais(v, errores, campo)]
        salida += [c for c in codigos if c and c in paises.mundo()["codigos"] and c not in salida]
    return salida


def _mapa(valor, tabla, errores, campo, permitidos):
    salida = []
    for v in _lista(valor):
        r = tabla.get(_norm(v).replace(".", " ").replace("  ", " ").strip())
        if r is None:
            errores.append(f"{campo}: «{v}» no es válido (usa {permitidos}).")
        elif r not in salida:
            salida.append(r)
    return salida


def _si_no(valor, errores, campo):
    v = _norm(valor)
    if v in _SI:
        return True
    if v in _NO:
        return False
    errores.append(f"{campo}: escribe «sí» o «no».")
    return False


def _entero(valor, errores, campo):
    if not valor:
        return None
    if not re.fullmatch(r"\d{1,3}", valor.strip()):
        errores.append(f"{campo}: escribe un número entero.")
        return None
    return int(valor)


def _salario(valor, errores):
    m = re.fullmatch(r"\s*([\d.,]+)\s*([A-Za-z]{3})\s*(?:(?:al|por|/|x)\s*)?([A-Za-zñÑáéíóú]+)?\s*", valor or "")
    if not m:
        errores.append("salario_minimo: usa el formato «2000 USD mes».")
        return None
    numero = m.group(1).replace(".", "").replace(",", "") if re.fullmatch(r"\d{1,3}([.,]\d{3})+", m.group(1)) \
        else m.group(1).replace(",", ".")
    moneda, periodo = m.group(2).upper(), _PERIODOS.get(_norm(m.group(3) or "mes"))
    if moneda not in _MONEDAS:
        errores.append(f"salario_minimo: la moneda «{moneda}» no está en la lista ({', '.join(sorted(_MONEDAS))}).")
        return None
    if not periodo:
        errores.append("salario_minimo: el periodo debe ser mes, año u hora.")
        return None
    try:
        return {"tipo": "salario_minimo", "monto": float(numero), "moneda": moneda, "periodo": periodo}
    except ValueError:
        errores.append("salario_minimo: el monto no es un número.")
        return None


def _telefono(valor, errores):
    v = re.sub(r"[\s().-]", "", valor or "")
    if v.startswith("00"):
        v = "+" + v[2:]
    if v and not v.startswith("+"):
        errores.append("whatsapp: escribe el número con el código de país (por ejemplo +57…).")
        return None
    return v or None


def _motivo(error):
    for e in error.errors():
        mensaje = e.get("msg", "")
        if mensaje.startswith("Value error, "):
            return mensaje.removeprefix("Value error, ")
        nombres = [x for x in e.get("loc", ()) if isinstance(x, str)]
        return modelos._MOTIVOS_CAMPO.get(("perfiles", nombres[-1]) if nombres else (), "Revisa los datos de la fila.")
    return "Revisa los datos de la fila."


def _perfil(datos, errores, avisos):
    """Los campos del perfil desde una fila; con los mismos valores por defecto que un perfil nuevo del panel."""
    p = {"activo": True}
    if datos.get("vive_en"):
        pais = _pais(datos["vive_en"], errores, "vive_en")
        if pais:  # si no se reconoce, el error ya quedó anotado una sola vez
            p["vive_en"] = pais
    else:
        avisos.append("Sin país de residencia: queda Colombia.")
    if datos.get("modalidades"):
        p["modalidades"] = _mapa(datos["modalidades"], _MODALIDADES, errores, "modalidades",
                                 "remoto, híbrido o presencial")
    else:
        avisos.append("Sin modalidad: queda solo remoto.")
    p["ciudades"] = _lista(datos.get("ciudades"))
    p["paises_presenciales_extra"] = _paises(datos.get("se_mudaria_a"), errores, "se_mudaria_a")
    p["puede_trabajar_en"] = _paises(datos.get("puede_trabajar_en"), errores, "puede_trabajar_en")
    p["acepta_horario"] = _mapa(datos.get("acepta_horario"), _HORARIOS, errores, "acepta_horario",
                                "EE. UU. Este, EE. UU. Pacífico o Europa")
    if datos.get("idiomas"):
        p["idiomas"] = _mapa(datos["idiomas"], _IDIOMAS, errores, "idiomas", "español o inglés")
    for campo, clave in (("antiguedad_dias", "antiguedad_dias"), ("experiencia_anos", "experiencia_anos"),
                         ("margen_experiencia", "margen_experiencia")):
        valor = _entero(datos.get(campo), errores, campo)
        if valor is not None:
            p[clave] = valor
    # La mayoría de los avisos no dice el nivel de inglés ni los años: sin admitirlos, un perfil con esos filtros
    # descarta casi todo (búsqueda del 15 nov). Vacío = como un perfil nuevo del panel (no admitidos).
    for campo, clave in (("admitir_ingles_no_informado", "aceptar_ingles_sin_dato"),
                         ("admitir_experiencia_no_informada", "aceptar_experiencia_sin_dato")):
        if datos.get(campo):
            p[clave] = _si_no(datos[campo], errores, campo)
    meta = _entero(datos.get("meta_diaria"), errores, "meta_diaria")
    p["meta_diaria"] = META_POR_DEFECTO if meta is None else meta
    ingles = _INGLES.get(_norm(datos.get("ingles_maximo")))
    if ingles is None:
        errores.append("ingles_maximo: usa A1, A2, B1, B2, C1, C2, nativo o déjalo vacío.")
    else:
        p["ingles_maximo"] = ingles
    p["sectores_preferidos"] = _lista(datos.get("sectores_preferidos"))
    p["palabras_preferidas"] = _lista(datos.get("palabras_preferidas"))
    restricciones = []
    if datos.get("no_acepta_palabras"):
        restricciones.append({"tipo": "palabras", "palabras": _lista(datos["no_acepta_palabras"])})
    if datos.get("salario_minimo"):
        s = _salario(datos["salario_minimo"], errores)
        if s:
            restricciones.append(s)
    if datos.get("no_acepta_contrato"):
        tipos = _mapa(datos["no_acepta_contrato"], _CONTRATOS, errores, "no_acepta_contrato",
                      "freelance, medio tiempo, temporal o prácticas")
        if tipos:
            restricciones.append({"tipo": "contrato", "tipos": tipos})
    p["restricciones"] = restricciones
    return p


def _nombre_cargo(texto):
    return " ".join(texto.casefold().replace("-", " ").split())


def previa(borrador, contenido, actuales="mantener"):
    """Lo que quedaría en el borrador. No guarda nada.

    Quien ya está en el panel (mismo nombre, o el de la columna `nombre_anterior`) se **actualiza**: conserva su
    identidad y la de sus perfiles del mismo cargo, así no pierde lo que ya recibió ni se le repiten vacantes (16 nov).
    `actuales` decide qué pasa con los clientes que **no** están en el archivo: mantener, archivar o borrar."""
    if actuales not in ACTUALES:
        raise ErrorRepositorio("Elige qué hacer con los clientes que no están en el archivo.", 422)
    filas, desconocidas = leer(contenido)
    cfg = Configuracion.model_validate(borrador).model_dump(mode="json")
    existentes = {}
    for c in sorted(cfg["clientes"], key=lambda c: not c["activo"]):  # con nombres repetidos, primero el activo
        existentes.setdefault(_norm(c["nombre"]), c)

    def buscado(datos):
        return _norm(datos.get("nombre_anterior") or datos.get("nombre", ""))

    actualizados_ids = {existentes[k]["id"] for k in (buscado(d) for _, d in filas) if k in existentes}
    restantes = [c for c in cfg["clientes"] if c["id"] not in actualizados_ids]
    borrados = [c for c in restantes if actuales == "borrar"]
    archivados = [c for c in restantes if actuales == "archivar" and c["activo"]]
    ids_borrados = {c["id"] for c in borrados}
    cfg["clientes"] = [c for c in cfg["clientes"] if c["id"] not in ids_borrados]
    for c in archivados:
        c["activo"] = False
    # Los perfiles de quien se actualiza se reemplazan por los del archivo; sus ids se reutilizan por cargo.
    anteriores = {}
    for perfil in cfg["perfiles"]:
        if perfil["cliente_id"] in actualizados_ids:
            anteriores.setdefault((perfil["cliente_id"], perfil["cargo_id"]), []).append(perfil["id"])
    cfg["perfiles"] = [x for x in cfg["perfiles"]
                       if x["cliente_id"] not in ids_borrados and x["cliente_id"] not in actualizados_ids]
    cargos = {}
    for c in cfg["cargos"]:
        for nombre in [c["nombre"], *c.get("terminos_exactos", [])]:
            cargos.setdefault(_nombre_cargo(nombre), c)
    nuevos_cargos, clientes, contactos, resultado, actualizados, nuevos = [], {}, {}, [], [], []
    perfiles_de = {}
    for n, datos in filas:
        errores, avisos = [], []
        nombre = " ".join(datos.get("nombre", "").split())
        cargo_txt = " ".join(datos.get("cargo", "").split())
        if not nombre:
            errores.append("Falta el nombre.")
        if not cargo_txt:
            errores.append("Falta el cargo.")
        clave = _norm(nombre)
        cliente = clientes.get(clave)
        estado = "actualiza" if cliente and cliente["id"] in actualizados_ids else "nuevo"
        if nombre and not cliente:
            previo = existentes.get(buscado(datos))
            if datos.get("nombre_anterior") and not previo:
                errores.append(f"nombre_anterior: no hay en el panel un cliente llamado «{datos['nombre_anterior']}».")
            otro = existentes.get(clave)
            if previo and otro and otro["id"] != previo["id"] and otro["id"] not in ids_borrados:
                errores.append("Ya hay otro cliente en el panel con el nombre nuevo.")
            comunidad = _si_no(datos.get("comunidad"), errores, "comunidad") if datos.get("comunidad") else None
            if previo:
                cliente = previo
                cliente.update(nombre=nombre[:100], activo=True)
                if comunidad is not None:
                    cliente["comunidad"] = comunidad
                estado = "actualiza"
                actualizados.append(nombre)
            else:
                cliente = {"id": str(uuid4()), "nombre": nombre[:100], "activo": True, "comunidad": bool(comunidad)}
                cfg["clientes"].append(cliente)
                nuevos.append(nombre)
            if datos.get("whatsapp"):
                telefono = _telefono(datos["whatsapp"], errores)
                acepto = _si_no(datos.get("acepto_whatsapp"), errores, "acepto_whatsapp")
                if telefono:
                    try:
                        contactos[cliente["id"]] = Contacto(
                            telefono=telefono, consentimiento=acepto,
                            nombre_saludo=(datos.get("nombre_saludo") or nombre.split()[0])[:60]).model_dump()
                    except ValidationError:
                        errores.append("whatsapp: el número no es válido (código de país y 8 a 15 dígitos).")
                if not acepto:
                    avisos.append("No consta que aceptó WhatsApp: no tendrá mensaje diario hasta marcarlo.")
            elif estado == "nuevo":
                avisos.append("Sin WhatsApp: no tendrá mensaje diario.")
            clientes[clave] = cliente
        cargo = cargos.get(_nombre_cargo(cargo_txt)) if cargo_txt else None
        nuevo = False
        extra_nombres, extra_funciones = _lista(datos.get("nombres_del_cargo")), _lista(datos.get("funciones_del_cargo"))
        if cargo_txt and not cargo:
            cargo = {"id": str(uuid4()), "nombre": cargo_txt[:120], "cupo": 0, "activo": True,
                     "terminos_exactos": list(dict.fromkeys([cargo_txt[:120], *extra_nombres]))[:30],
                     "terminos_similares": [], "terminos_excluidos": [], "terminos_cercanos": [],
                     "funciones": extra_funciones[:40]}
            for nombre_cargo in cargo["terminos_exactos"]:
                cargos.setdefault(_nombre_cargo(nombre_cargo), cargo)
            cargos[_nombre_cargo(cargo_txt)] = cargo
            nuevos_cargos.append(cargo)
            nuevo = True
        if cargo and not cargo.get("activo", True):
            cargo["activo"] = True
            avisos.append(f"El cargo «{cargo['nombre']}» estaba archivado: se reactiva.")
        perfil = _perfil(datos, errores, avisos)
        if cliente and cargo:
            reutilizables = anteriores.get((cliente["id"], cargo["id"])) or []
            perfil.update(id=reutilizables.pop(0) if reutilizables else str(uuid4()),
                          cliente_id=cliente["id"], cargo_id=cargo["id"])
            if cargo["id"] in perfiles_de.setdefault(cliente["id"], set()):
                avisos.append(f"Este cliente ya tiene otro perfil de «{cargo['nombre']}» en el archivo.")
            perfiles_de[cliente["id"]].add(cargo["id"])
            try:
                perfil = Perfil.model_validate(perfil).model_dump(mode="json")
            except ValidationError as e:
                errores.append(_motivo(e))
        if nuevo:
            avisos.append(f"Cargo nuevo «{cargo['nombre']}»: revisa sus nombres y usa «Proponer funciones».")
        elif cargo and (extra_nombres or extra_funciones) and cargo not in nuevos_cargos:
            # Contrato v27: en un cargo que ya existe, los nombres y funciones del archivo se AÑADEN (nunca se quita ni
            # se reemplaza nada), para que encuentre más vacantes sin cambiar lo que ya buscaba.
            conocidos = {_nombre_cargo(t) for k in ("terminos_exactos", "terminos_similares", "terminos_excluidos",
                                                    "terminos_cercanos") for t in cargo.get(k, [])}
            nombres = [t[:120] for t in dict.fromkeys(extra_nombres) if _nombre_cargo(t) not in conocidos]
            nombres = nombres[:max(0, 30 - len(cargo.get("terminos_similares", [])))]
            funciones = [t for t in dict.fromkeys(extra_funciones) if t not in cargo.get("funciones", [])]
            funciones = funciones[:max(0, 40 - len(cargo.get("funciones", [])))]
            if nombres or funciones:
                cargo["terminos_similares"] = [*cargo.get("terminos_similares", []), *nombres]
                cargo["funciones"] = [*cargo.get("funciones", []), *funciones]
                avisos.append(f"Al cargo «{cargo['nombre']}» se le añaden {len(nombres)} nombres y {len(funciones)} "
                              "funciones; no se quita ninguno.")
        resultado.append({"fila": n, "cliente": nombre, "estado": estado,
                          "cargo": cargo["nombre"] if cargo else cargo_txt,
                          "vive_en": perfil.get("vive_en", ""), "modalidades": perfil.get("modalidades", []),
                          "meta": perfil.get("meta_diaria"), "errores": errores, "avisos": avisos,
                          "_perfil": perfil})
    hay_errores = any(r["errores"] for r in resultado)
    configuracion, metas, error_general = None, None, ""
    if not hay_errores:
        cfg["cargos"] += nuevos_cargos
        cfg["perfiles"] += [r["_perfil"] for r in resultado]
        try:
            final = Configuracion.model_validate(cfg)
            configuracion, metas = final.model_dump(mode="json"), final.metas()
        except ValidationError as e:
            error_general = modelos.explicar(e)
    for r in resultado:
        r.pop("_perfil")
    return {"filas": resultado, "errores": sum(len(r["errores"]) for r in resultado) + bool(error_general),
            "error_general": error_general, "columnas_desconocidas": desconocidas,
            "clientes": len(clientes), "perfiles": len(resultado),
            "actualizados": actualizados, "nuevos": nuevos,
            "cargos_nuevos": [c["nombre"] for c in nuevos_cargos],
            "borrar": [c["nombre"] for c in borrados], "archivar": [c["nombre"] for c in archivados],
            "metas": metas, "excede_techo": bool(metas and metas["reales"] > metas["techo"]),
            "configuracion": configuracion, "contactos": contactos, "_borrados": [c["id"] for c in borrados]}

def importar(repo, revision, contenido, actuales="mantener", confirmacion=""):
    """Guarda el resultado de `previa` en el borrador (todo o nada) y después los contactos. Con «borrar», también
    borra los contactos y los mensajes preparados de los clientes anteriores."""
    estado = repo.config()
    if estado["revision"] != revision:
        raise ErrorRepositorio("La configuración cambió. Recarga antes de importar.", 409)
    r = previa(estado["borrador"], contenido, actuales)
    if r["errores"]:
        raise ErrorRepositorio("El archivo tiene errores: revisa la vista previa y corrígelos antes de importar.", 422)
    if r["_borrados"] and confirmacion.strip().upper() != "BORRAR":
        raise ErrorRepositorio("Escribe BORRAR para confirmar que se borran los clientes que no están en el archivo.", 422)
    guardado = repo.guardar(revision, r["configuracion"])
    for cliente_id in r["_borrados"]:
        repo.borrar_contacto(cliente_id)
        repo.borrar_borradores(cliente_id)
    for cliente_id, contacto in r["contactos"].items():
        repo.guardar_contacto(cliente_id, contacto)
    return {"importados": r["clientes"], "actualizados": len(r["actualizados"]), "nuevos": len(r["nuevos"]),
            "perfiles": r["perfiles"], "borrados": len(r["_borrados"]),
            "archivados": len(r["archivar"]), "cargos_nuevos": r["cargos_nuevos"], "estado": guardado}


def borrar_cliente(repo, revision, cliente_id):
    """«Eliminar definitivamente»: quita el cliente y sus perfiles del borrador y borra su contacto y sus mensajes
    preparados. Las versiones ya programadas y las vacantes ya entregadas se conservan (historial)."""
    estado = repo.config()
    if estado["revision"] != revision:
        raise ErrorRepositorio("La configuración cambió. Recarga antes de borrar.", 409)
    cfg = estado["borrador"]
    if not any(c["id"] == cliente_id for c in cfg.get("clientes", [])):
        raise ErrorRepositorio("Ese cliente ya no está en la configuración.", 404)
    cfg = {**cfg, "clientes": [c for c in cfg["clientes"] if c["id"] != cliente_id],
           "perfiles": [p for p in cfg.get("perfiles", []) if p["cliente_id"] != cliente_id]}
    guardado = repo.guardar(revision, Configuracion.model_validate(cfg).model_dump(mode="json"))
    repo.borrar_contacto(cliente_id)
    repo.borrar_borradores(cliente_id)
    return {"borrado": True, "estado": guardado}
