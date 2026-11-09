"""Vistas y texto para copiar; nunca se envía WhatsApp."""
from buscador import contrato, vacante
from panel.afinidad import enlace_utilizable, evaluar
from panel.repositorio import hoy
from panel.terminos import grado


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
