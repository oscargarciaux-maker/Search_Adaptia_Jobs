"""Vistas y texto para copiar; nunca se envía WhatsApp."""
from collections import Counter

from buscador import contrato, vacante
from panel.afinidad import enlace_utilizable, evaluar
from panel.repositorio import hoy
from panel.terminos import grado, sugerir

# Qué puede hacer el operador cuando un filtro, por sí solo, deja fuera vacantes. Sin sugerencia si no depende de él.
SUGERENCIAS = {
    "experiencia no informada": "Admitir experiencia no informada",
    "inglés requerido sin confirmar": "Admitir inglés no informado",
    "publicación fuera del plazo": "Ampliar la antigüedad de publicación",
    "país sin elegibilidad confirmada": "Añadir más países",
    "modalidad diferente": "Aceptar otra modalidad",
    "idioma del aviso diferente": "Aceptar avisos en español e inglés",
    "experiencia fuera del rango": "Ampliar el rango de experiencia",
    "inglés requerido superior al indicado": "Subir el nivel de inglés admitido",
}
SIN_DATO = {"experiencia no informada", "inglés requerido sin confirmar"}
_POR_CARGO = {}


def _del_cargo(catalogo, cargo):
    """Vacantes del catálogo que corresponden al cargo. Editar filtros de un perfil no cambia este resultado, así que se
    reutiliza mientras no cambien el catálogo ni los términos del cargo."""
    clave = (catalogo["actualizado"], len(catalogo["vacantes"]), cargo["nombre"], tuple(cargo["terminos_exactos"]),
             tuple(cargo["terminos_similares"]), tuple(cargo["terminos_excluidos"]))
    if clave not in _POR_CARGO:
        if len(_POR_CARGO) > 200:
            _POR_CARGO.clear()
        _POR_CARGO[clave] = [v for v in catalogo["vacantes"] if grado(v.get("titulo") or "", cargo)[0]]
    return _POR_CARGO[clave]


def vista_previa(repo, cfg, fecha=None):
    """Cuántas vacantes ya guardadas y aún no entregadas cumplirían hoy cada perfil y cargo del borrador.
    Es una estimación con las mismas reglas de la selección; no busca, no guarda y no devuelve vacantes ni clientes."""
    fecha = fecha or hoy()
    catalogo = repo.catalogo_vigente()
    clientes = {c.id for c in cfg.clientes if c.activo}
    perfiles, cargos = {}, {}
    for c in cfg.cargos:
        if not c.activo:
            continue
        raw = c.model_dump(mode="json")
        if not raw["terminos_exactos"]:  # igual que la captura dirigida
            raw["terminos_exactos"] = sugerir(c.nombre, consultar_esco=False)["terminos_exactos"]
        del_cargo = _del_cargo(catalogo, raw)
        disponibles = set()
        for p in cfg.perfiles:
            if not p.activo or p.cargo_id != c.id or p.cliente_id not in clientes:
                continue
            compatibles, solo = 0, Counter()
            for v in del_cargo:
                r = evaluar(v, p, fecha)
                if r["compatible"]:
                    compatibles += 1
                    disponibles.add(v["id"])
                elif len(r["motivos"]) == 1:
                    solo[r["motivos"][0]] += 1
                elif set(r["motivos"]) == SIN_DATO:  # muchos avisos no dicen ni años ni nivel de inglés
                    solo["ambos sin dato"] += 1
            limitantes = [{"motivo": m, "vacantes": n, "sugerencia": SUGERENCIAS[m]}
                          for m, n in solo.items() if m in SUGERENCIAS]
            if solo["ambos sin dato"]:
                limitantes.append({"motivo": "experiencia e inglés no informados",
                                   "vacantes": sum(solo[m] for m in (*SIN_DATO, "ambos sin dato")),
                                   "sugerencia": "Admitir experiencia e inglés no informados"})
            perfiles[str(p.id)] = {"compatibles": compatibles, "del_cargo": len(del_cargo),
                                   "limitantes": sorted(limitantes, key=lambda x: -x["vacantes"])[:3]}
        n = len(disponibles)
        estado = ("sin_cupo" if not c.cupo else "alcanza" if n >= c.cupo else "justo" if n * 2 >= c.cupo
                  else "insuficiente")
        cargos[str(c.id)] = {"disponibles": n, "del_cargo": len(del_cargo), "cupo": c.cupo, "estado": estado}
    return {"catalogo": {"vacantes": len(catalogo["vacantes"]), "actualizado": catalogo["actualizado"]},
            "perfiles": perfiles, "cargos": cargos,
            "nota": "Estimación con vacantes ya guardadas y aún no entregadas. La búsqueda dirigida de mañana "
                    "puede encontrar otras; un cargo nuevo empieza con pocas porque todavía no se ha buscado."}


def resultados(repo, cliente_id=None, fecha=None):
    r = repo.resultados(cliente_id, fecha)
    salida, vistas = [], {}
    for row in r["filas"]:
        v = row.get("catalogo_vacantes") or {}
        datos = v.get("datos") or {}
        # Los datos públicos no traen las observaciones de ubicación ni el origen de la fecha: conservar lo que calculó
        # la bodega en vez de rehacerlo con menos evidencia.
        actual = vacante.reetiquetar(dict(datos, _descripcion=v.get("description_full") or datos.get("_descripcion", "")),
                                     publicada=True)
        filtros = evaluar(actual, row["filtros"], hoy())
        afinidad_cargo,_ = grado(actual["titulo"],row["cargo_configuracion"])
        if not afinidad_cargo:
            filtros["compatible"] = False
            filtros["motivos"].append("el título actual no corresponde al cargo configurado")
        enlace = enlace_utilizable(row) if filtros["compatible"] and not contrato.entregable(actual) else ""
        clave = row["vacante_id"]
        if clave in vistas and (vistas[clave]["estado"] == "lista" or not enlace):
            continue
        ficha = {"id": clave, "titulo": datos.get("titulo", ""), "empresa": datos.get("empresa", ""),
            "ubicacion": datos.get("ubicacion", ""), "modalidad": datos.get("modalidad", ""),
            "idioma": datos.get("idioma", ""), "publicada": datos.get("fecha_publicacion", ""),
            "experiencia": datos.get("anos_min"), "match_grade": row["match_grade"],
            "explicacion": row["explicacion"], "cargo_id": row["cargo_id"], "enlace": enlace,
            "estado": "lista" if enlace else "retirada" if v.get("status") != "active" else "por_confirmar",
            "motivos": filtros["motivos"]}
        if clave in vistas:
            salida[salida.index(vistas[clave])] = ficha
        else:
            salida.append(ficha)
        vistas[clave] = ficha
    return {**{k: r[k] for k in ("ejecucion", "clientes")}, "vacantes": salida,
            "listas": sum(v["estado"] == "lista" for v in salida)}


def whatsapp(repo, cliente_id, fecha=None):
    r = resultados(repo, cliente_id, fecha)
    listas = [v for v in r["vacantes"] if v["estado"] == "lista"]
    if not listas:
        return {"texto": "", "vacantes": 0, "nota": "No hay vacantes con filtros y enlace vigentes para copiar."}
    texto = "Hola, el día de hoy te traigo estas vacantes que pueden ser de tu interés. Te las comparto para que puedas aplicar lo más pronto posible:\n\n"
    texto += "\n\n".join(f"{i}. {' '.join(v['titulo'].split())} · {' '.join(v['empresa'].split())}\n{v['enlace']}"
                          for i, v in enumerate(listas, 1))
    texto += "\n\nRevisa los requisitos y postúlate directamente en cada enlace. ¡Mucho éxito!"
    return {"texto": texto, "vacantes": len(listas)}
