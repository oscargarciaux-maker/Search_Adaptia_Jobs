"""Borradores diarios de WhatsApp por cliente (contrato v10). Nada se envía solo: el operador abre el chat con el
mensaje ya escrito (enlace wa.me), lo revisa y lo envía. Textos por plantillas, sin IA, sin enumerar filtros."""
import argparse
from datetime import date, timedelta
import hashlib
import hmac
import os
import re
import secrets
from urllib.parse import quote

from panel.repositorio import hoy

MINIMO = 5
MAXIMO = 10
POR_EMPRESA = 2  # contrato v31: variedad en el mensaje, como en la entrega diaria
SALUDOS = ("Hola {nombre} 👋", "¡Hola, {nombre}!", "Hola {nombre}, ¿cómo vas?", "¡Buen día, {nombre}!")
INTROS = ("Hoy encontré {n} vacantes de {cargo} que creo que te pueden interesar:",
          "Te comparto {n} oportunidades de {cargo} que vi hoy y encajan con lo que buscas:",
          "Estas son {n} vacantes de {cargo} que salieron y pueden servirte:",
          "Te dejo {n} vacantes nuevas de {cargo} para que les eches un vistazo:")
# Contrato v46: si alguna vacante es de días anteriores, el mensaje no dice «hoy» ni «nuevas».
INTROS_ANTERIORES = ("Te comparto {n} vacantes de {cargo} que siguen abiertas y pueden interesarte:",
                     "Estas son {n} vacantes de {cargo} que siguen abiertas y encajan con lo que buscas:",
                     "Te dejo {n} vacantes de {cargo}, todavía abiertas, para que les eches un vistazo:")
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
        # Contrato v28: si la ubicación se dedujo o no se pudo confirmar, el mensaje lo dice.
        nota = {"deducida": " (ubicación deducida, confírmala)",
                "sin_confirmar": " (no dice dónde es: pregúntalo)"}.get(v.get("post_ubicacion", ""), "")
        return (f"{i}. 📣 Post · {titulo} · {empresa}{nota}\nEscríbele por mensaje a quien publicó: {v['enlace']}"
                + (f"\nO al correo: {correo}" if correo else ""))
    modo = MODOS.get(v.get("modalidad", ""), "")
    return f"{i}. {titulo} · {empresa}" + (f" ({modo})" if modo else "") + f"\n{v['enlace']}"


def _empresa(v):
    return " ".join(str(v.get("empresa") or "").casefold().split())


def texto(nombre, grupos, fecha, cliente_id="", mas=0, todas_de_hoy=True):
    """Mensaje humano: saludo, una frase con el cargo, la lista corta y un cierre. `grupos`: [(cargo, [vacantes])].
    `mas` (contrato v31): cuántas otras vacantes listas quedaron fuera del tope de 10.
    `todas_de_hoy` (contrato v46): False si alguna viene de días anteriores (la frase no dice «hoy»)."""
    semilla = f"{fecha}:{cliente_id}"
    n = sum(len(vs) for _, vs in grupos)
    nombre = " ".join(str(nombre or "").split()) or "¿cómo estás?"
    saludo = _elegir(SALUDOS, semilla + "s").format(nombre=nombre) if nombre != "¿cómo estás?" else "¡Hola! 👋"
    intros = INTROS if todas_de_hoy else INTROS_ANTERIORES
    partes = [saludo, _elegir(intros, semilla + "i").format(n=n, cargo=_lista([c for c, _ in grupos]))]
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
    if mas > 0:
        partes.append(f"Tengo {mas} vacante{'s' if mas != 1 else ''} más para ti; si quieres, te las paso.")
    partes.append(_elegir(CIERRES, semilla + "c"))
    return "\n\n".join(partes)


def generar(repo, fecha=None, dias_atras=3, resultados=None):
    """Crea o actualiza el borrador del día de cada cliente activo con teléfono y consentimiento.
    Solo vacantes con enlace comprobado para compartir; completa hasta MINIMO con días anteriores sin repetir nada que
    ya le haya ido en otro borrador. No toca borradores abiertos, enviados, descartados o editados a mano."""
    from panel import servicio
    from concurrent.futures import ThreadPoolExecutor
    fecha = fecha or hoy()
    # 18 nov (velocidad): el servidor pasa sus copias en memoria de los resultados (cliente, día).
    resultados = resultados or (lambda cliente_id, f: servicio.resultados(repo, cliente_id, f))
    contactos = {c["cliente_id"]: c for c in repo.contactos() if c.get("consentimiento") and c.get("telefono")}
    # Conteos para explicar un resultado vacío en el panel (13 nov: «Preparar mensajes» no decía por qué).
    resultado = {"generados": 0, "con_pocas": 0, "sin_vacantes": 0, "conservados": 0, "sin_contacto": 0,
                 "por_recomprobar": 0, "clientes_activos": 0}
    # Solo la lista de clientes de la búsqueda del día: sin leer las vacantes de ninguno.
    lista = repo.clientes_de(fecha) if hasattr(repo, "clientes_de") else servicio.resultados(repo, None, fecha).get("clientes", [])
    clientes = {c["id"]: c for c in lista if c.get("activo", True)}
    resultado["clientes_activos"] = len(clientes)
    resultado["sin_contacto"] = sum(1 for cid in clientes if cid not in contactos)
    if not contactos:
        return resultado
    existentes = {b["cliente_id"]: b for b in repo.borradores(fecha=fecha)}
    por_hacer = []
    for cliente_id, contacto in contactos.items():
        if cliente_id not in clientes:
            continue
        actual = existentes.get(cliente_id)
        if actual and (actual.get("estado") != "pendiente" or actual.get("editado")):
            resultado["conservados"] += 1
            continue
        por_hacer.append((cliente_id, contacto))
    # Cada cliente es independiente: se calculan de a cuatro a la vez (antes uno tras otro), pero se guardan aquí, en
    # el orden de siempre (`ex.map` conserva el orden), para que la lista de mensajes no cambie de orden entre días.
    with ThreadPoolExecutor(4) as ex:
        for parcial, fila in ex.map(lambda par: _uno(repo, fecha, dias_atras, resultados, *par), por_hacer):
            for k, n in parcial.items():
                resultado[k] += n
            if fila:
                repo.guardar_borrador(fila)
    return resultado


def _uno(repo, fecha, dias_atras, resultados, cliente_id, contacto):
    """Borrador del día de un cliente, sin guardarlo. Devuelve (conteos que suma a `generar`, fila o None)."""
    resultado = {"generados": 0, "con_pocas": 0, "sin_vacantes": 0, "por_recomprobar": 0}
    ya = {vid for b in repo.borradores(cliente_id=cliente_id) if b.get("fecha") != fecha for vid in b.get("vacantes", [])}
    elegidas, vistos, sobran, empresas, de_hoy = [], set(ya), set(), {}, set()
    for dia in range(dias_atras + 1):
        if len(elegidas) >= MAXIMO or (dia and len(elegidas) >= MINIMO):
            break
        f = (date.fromisoformat(fecha) - timedelta(days=dia)).isoformat()
        for v in resultados(cliente_id, f)["vacantes"]:
            if not dia and v["estado"] == "por_confirmar":
                resultado["por_recomprobar"] += 1  # del día, con el enlace aún por recomprobar
            if v["estado"] != "lista" or v["id"] in vistos:
                continue
            vistos.add(v["id"])
            # Contrato v31: hasta 10 y máximo 2 de la misma empresa; las que quedan fuera se ofrecen («Tengo más…»).
            if len(elegidas) < MAXIMO and (es_post(v) or empresas.get(_empresa(v), 0) < POR_EMPRESA):
                empresas[_empresa(v)] = empresas.get(_empresa(v), 0) + 1
                elegidas.append(v)
                if not dia:
                    de_hoy.add(v["id"])
            else:
                sobran.add(v["id"])
    elegidas = con_posts(elegidas)
    if not elegidas:
        resultado["sin_vacantes"] += 1
        return resultado, None
    nombres = {}
    for v in elegidas:
        nombres.setdefault(v.get("cargo_nombre") or "tu perfil", []).append(v)
    grupos = list(nombres.items())
    # Solo el nombre que el operador eligió para saludar: la referencia interna del cliente no va en el mensaje.
    cuerpo = texto(contacto.get("nombre_saludo") or "", grupos, fecha, cliente_id, mas=len(sobran),
                   todas_de_hoy=all(v["id"] in de_hoy for v in elegidas))
    resultado["generados"] += 1
    resultado["con_pocas"] += len(elegidas) < MINIMO
    return resultado, {"fecha": fecha, "cliente_id": cliente_id, "texto": cuerpo, "vacantes": [v["id"] for v in elegidas],
                       "cargos": [c for c, _ in grupos], "estado": "pendiente", "editado": False}


# ── Contrato v46: enlace corto por cliente para «Mandarme todos» en un solo mensaje ──────────────────────────────
_LLAVE_AL_AZAR = secrets.token_bytes(32)  # sin la credencial de servicio (demostración): vale hasta reiniciar


def _llave():
    """Llave de las firmas, derivada en el servidor de la credencial de servicio (no hay variable nueva). Nunca sale
    del servidor: ni al navegador, ni a los registros, ni a los enlaces (solo su firma)."""
    secreto = os.environ.get("SUPABASE_SECRET_KEY", "")
    return hashlib.sha256(b"adaptia-whatsapp-corto:" + secreto.encode()).digest() if secreto else _LLAVE_AL_AZAR


def firma(borrador_id, fecha):
    return hmac.new(_llave(), f"{borrador_id}|{fecha}".encode(), hashlib.sha256).hexdigest()[:16]


def ficha_corta(borrador_id, fecha):
    """Lo que va en la dirección corta: /w/<ficha>. Vale solo el día del borrador (Bogotá)."""
    return f"{borrador_id}.{firma(borrador_id, fecha)}"


def abrir_corto(repo, ficha, fecha=None):
    """El enlace wa.me del cliente con su mensaje actual (lo editado en el panel cuenta), o None si la ficha no es
    válida, no es de hoy, el mensaje ya se envió o descartó, o el cliente no tiene WhatsApp. Marca «abierto»."""
    fecha = fecha or hoy()
    borrador_id, _, recibida = str(ficha or "").partition(".")
    if not borrador_id or len(recibida) != 16 or not hmac.compare_digest(recibida, firma(borrador_id, fecha)):
        return None
    b = next((x for x in repo.borradores(fecha=fecha) if str(x.get("id")) == borrador_id), None)
    if not b or b.get("estado") not in ("pendiente", "abierto"):
        return None
    c = next((x for x in repo.contactos() if x.get("cliente_id") == b["cliente_id"]), None)
    if not c or not c.get("telefono"):
        return None
    if b.get("estado") == "pendiente":
        repo.actualizar_borrador(borrador_id, {"estado": "abierto"})
    return enlace_whatsapp(c["telefono"], b["texto"])


def para_operador(repo, base, fecha, contactos, borradores, nombres):
    """Contrato v46 (decisión de Oscar, 18 nov): «Mandarme todos a mi WhatsApp» en UN solo mensaje al número del
    operador, con un enlace corto por cliente (`base` + /w/<ficha>) que abre su chat con el mensaje escrito. Antes
    (v31) cada cliente llevaba su mensaje completo dentro del enlace y había que partirlo. No envía nada: el operador
    envía su mensaje y, desde su teléfono, toca cada cliente. `contactos`, `borradores` y `nombres` los pasa la API
    desde sus copias."""
    from panel.repositorio import ErrorRepositorio
    operador = (repo.ajuste("operador", {}) or {}).get("telefono", "")
    if not operador:
        raise ErrorRepositorio("Guarda primero tu número de WhatsApp en «Mi número».", 422)
    contactos = {c["cliente_id"]: c for c in contactos}
    lineas = []
    for b in borradores:
        c = contactos.get(b["cliente_id"])
        if b.get("estado") not in ("pendiente", "abierto") or not c or not c.get("telefono"):
            continue
        nombre = " ".join((nombres.get(b["cliente_id"]) or c.get("nombre_saludo") or "Cliente").split())
        n = len(b.get("vacantes", []))
        lineas.append(f"*{nombre}* ({n} vacante{'s' if n != 1 else ''}):\n{base.rstrip('/')}/w/{ficha_corta(b['id'], fecha)}")
    if not lineas:
        return {"texto": "", "enlace": "", "clientes": 0}
    cuerpo = ("Mensajes de hoy. Toca cada enlace para abrir el chat del cliente con su mensaje listo:\n\n"
              + "\n\n".join(lineas))
    return {"texto": cuerpo, "enlace": enlace_whatsapp(operador, cuerpo), "clientes": len(lineas)}


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
