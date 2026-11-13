"""Borradores diarios de WhatsApp por cliente (contrato v10). Nada se envía solo: el operador abre el chat con el
mensaje ya escrito (enlace wa.me), lo revisa y lo envía. Textos por plantillas, sin IA, sin enumerar filtros."""
import argparse
from datetime import date, timedelta
import hashlib
import re
from urllib.parse import quote

from panel.repositorio import hoy

MINIMO = 5
MAXIMO = 10
SALUDOS = ("Hola {nombre} 👋", "¡Hola, {nombre}!", "Hola {nombre}, ¿cómo vas?", "¡Buen día, {nombre}!")
INTROS = ("Hoy encontré {n} vacantes de {cargo} que creo que te pueden interesar:",
          "Te comparto {n} oportunidades de {cargo} que vi hoy y encajan con lo que buscas:",
          "Estas son {n} vacantes de {cargo} que salieron y pueden servirte:",
          "Te dejo {n} vacantes nuevas de {cargo} para que les eches un vistazo:")
CIERRES = ("Revisa los requisitos y postúlate directo en cada enlace. ¡Mucho éxito!",
           "Si alguna te gusta, postúlate pronto: estas vacantes se llenan rápido. ¡Éxitos!",
           "Cuéntame si te interesa alguna o si quieres que ajuste la búsqueda. ¡Un abrazo!",
           "Postúlate en las que más te llamen la atención y me cuentas cómo te va.")
MODOS = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}
TELEFONO = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalizar_telefono(texto):
    """+<código de país><número>, solo dígitos; ValueError con mensaje para el operador si no es válido."""
    crudo = str(texto or "").strip()
    if crudo.startswith("00"):
        crudo = "+" + crudo[2:]
    limpio = "+" + re.sub(r"\D", "", crudo) if crudo.startswith("+") else ""  # sin código de país no se adivina
    if not TELEFONO.match(limpio):
        raise ValueError("Escribe el número con el código de país, por ejemplo +57 300 123 4567.")
    return limpio


def enlace_whatsapp(telefono, texto):
    """Abre el chat de esa persona con el mensaje escrito; no envía nada."""
    return f"https://wa.me/{telefono.lstrip('+')}?text={quote(texto, safe='')}"


def _elegir(opciones, semilla):
    return opciones[int(hashlib.sha256(semilla.encode()).hexdigest(), 16) % len(opciones)]


def _lista(cargos):
    return cargos[0] if len(cargos) == 1 else ", ".join(cargos[:-1]) + " y " + cargos[-1]


NOTA_POSTS = ("Las marcadas con 📣 Post son publicaciones de LinkedIn de quien está contratando: escríbele por mensaje "
              "(o al correo, si lo deja) para postularte.")


def es_post(v):
    return v.get("tipo") == "post"


def con_posts(vacantes, minimo=MINIMO, maximo=None):
    """Contrato v11: primero las vacantes formales; los posts van al final y solo completan hasta el mínimo."""
    formales = [v for v in vacantes if not es_post(v)][:maximo]
    posts = [v for v in vacantes if es_post(v)][:max(0, minimo - len(formales))]
    return formales + posts


def _linea(i, v):
    titulo, empresa = " ".join(v["titulo"].split()), " ".join(v["empresa"].split())
    if es_post(v):
        correo = (v.get("contacto") or {}).get("correo", "")
        return (f"{i}. 📣 Post · {titulo} · {empresa}\nEscríbele por mensaje a quien publicó: {v['enlace']}"
                + (f"\nO al correo: {correo}" if correo else ""))
    modo = MODOS.get(v.get("modalidad", ""), "")
    return f"{i}. {titulo} · {empresa}" + (f" ({modo})" if modo else "") + f"\n{v['enlace']}"


def texto(nombre, grupos, fecha, cliente_id=""):
    """Mensaje humano: saludo, una frase con el cargo, la lista corta y un cierre. `grupos`: [(cargo, [vacantes])]."""
    semilla = f"{fecha}:{cliente_id}"
    n = sum(len(vs) for _, vs in grupos)
    nombre = " ".join(str(nombre or "").split()) or "¿cómo estás?"
    saludo = _elegir(SALUDOS, semilla + "s").format(nombre=nombre) if nombre != "¿cómo estás?" else "¡Hola! 👋"
    partes = [saludo, _elegir(INTROS, semilla + "i").format(n=n, cargo=_lista([c for c, _ in grupos]))]
    i = 0
    for cargo, vacantes in grupos:
        if len(grupos) > 1:
            partes.append(f"*{cargo}*")
        lineas = []
        for v in sorted(vacantes, key=es_post):  # los posts siempre al final
            i += 1
            lineas.append(_linea(i, v))
        partes.append("\n\n".join(lineas))
    if any(es_post(v) for _, vs in grupos for v in vs):
        partes.append(NOTA_POSTS)
    partes.append(_elegir(CIERRES, semilla + "c"))
    return "\n\n".join(partes)


def generar(repo, fecha=None, dias_atras=3):
    """Crea o actualiza el borrador del día de cada cliente activo con teléfono y consentimiento.
    Solo vacantes con enlace comprobado para compartir; completa hasta MINIMO con días anteriores sin repetir nada que
    ya le haya ido en otro borrador. No toca borradores abiertos, enviados, descartados o editados a mano."""
    from panel import servicio
    fecha = fecha or hoy()
    contactos = {c["cliente_id"]: c for c in repo.contactos() if c.get("consentimiento") and c.get("telefono")}
    # Conteos para explicar un resultado vacío en el panel (13 nov: «Preparar mensajes» no decía por qué).
    resultado = {"generados": 0, "con_pocas": 0, "sin_vacantes": 0, "conservados": 0, "sin_contacto": 0,
                 "por_recomprobar": 0, "clientes_activos": 0}
    hoy_r = servicio.resultados(repo, None, fecha)
    clientes = {c["id"]: c for c in hoy_r.get("clientes", []) if c.get("activo", True)}
    resultado["clientes_activos"] = len(clientes)
    resultado["sin_contacto"] = sum(1 for cid in clientes if cid not in contactos)
    if not contactos:
        return resultado
    existentes = {b["cliente_id"]: b for b in repo.borradores(fecha=fecha)}
    for cliente_id, contacto in contactos.items():
        if cliente_id not in clientes:
            continue
        actual = existentes.get(cliente_id)
        if actual and (actual.get("estado") != "pendiente" or actual.get("editado")):
            resultado["conservados"] += 1
            continue
        ya = {vid for b in repo.borradores(cliente_id=cliente_id) if b.get("fecha") != fecha for vid in b.get("vacantes", [])}
        elegidas, vistos = [], set(ya)
        for dia in range(dias_atras + 1):
            if len(elegidas) >= MAXIMO or (dia and len(elegidas) >= MINIMO):
                break
            f = (date.fromisoformat(fecha) - timedelta(days=dia)).isoformat()
            for v in servicio.resultados(repo, cliente_id, f)["vacantes"]:
                if not dia and v["estado"] == "por_confirmar":
                    resultado["por_recomprobar"] += 1  # del día, con el enlace aún por recomprobar
                if v["estado"] == "lista" and v["id"] not in vistos and len(elegidas) < MAXIMO:
                    vistos.add(v["id"])
                    elegidas.append(v)
        elegidas = con_posts(elegidas)
        if not elegidas:
            resultado["sin_vacantes"] += 1
            continue
        nombres = {}
        for v in elegidas:
            nombres.setdefault(v.get("cargo_nombre") or "tu perfil", []).append(v)
        grupos = list(nombres.items())
        # Solo el nombre que el operador eligió para saludar: la referencia interna del cliente no va en el mensaje.
        cuerpo = texto(contacto.get("nombre_saludo") or "", grupos, fecha, cliente_id)
        repo.guardar_borrador({"fecha": fecha, "cliente_id": cliente_id, "texto": cuerpo,
                               "vacantes": [v["id"] for v in elegidas], "cargos": [c for c, _ in grupos],
                               "estado": "pendiente", "editado": False})
        resultado["generados"] += 1
        resultado["con_pocas"] += len(elegidas) < MINIMO
    return resultado


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fecha")
    a = p.parse_args()
    from panel.repositorio import RepositorioSupabase
    r = generar(RepositorioSupabase(), a.fecha)
    print(f"Borradores: {r['generados']} generados ({r['con_pocas']} con menos de {MINIMO}), "
          f"{r['conservados']} conservados, {r['sin_vacantes']} sin vacantes listas.")


if __name__ == "__main__":
    main()
