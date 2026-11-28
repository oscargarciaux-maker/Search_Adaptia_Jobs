"""Huecos por país (sección 8.1, decisiones del cliente del 27 nov), solo para el operador.

- Riesgo (aviso temprano): un perfil activo cuyo país —donde vive, o donde acepta híbrido/presencial— no tiene fuente
  local: solo lo buscan LinkedIn, los portales de empresas y Get on Board. La remota mundial no crea país.
- Hueco (medido): tras una búsqueda, un perfil bajo el mínimo de 5 cuya causa es la falta de vacantes en las fuentes, no
  su cargo (sin vacantes en ningún sitio), ni enlaces por comprobar, ni listas que aún no recibió, ni un ajuste del perfil.
- El pedido para un chat de Claude Code lleva SOLO país, idiomas, familias de cargo y modalidades: un país con un solo
  perfil delataría a un cliente, así que nada de esto sale del panel privado (ni mensajes, ni logs, ni `publicado`).
Sin IA: sale de las listas de cada fuente (`ejecutor.fuentes_en`) y de las causas que ya calcula `servicio.cobertura`.
"""
from buscador import paises
from panel.contenido import familia_del_mapa
from panel.ejecutor import _region_de, fuentes_en

# Fuentes que buscan en cualquier país del mundo (contrato §9, v44): no cuentan como fuente local.
GENERICAS = ("LinkedIn", "Portales de empresas", "Get on Board (remotas)")
MODOS = ("remoto", "hibrido", "presencial")
NOMBRE_MODO = {"remoto": "remoto", "hibrido": "híbrido", "presencial": "presencial"}

# Causas de `servicio.cobertura` que significan «faltan vacantes en las fuentes». Si cambian allí, la prueba
# `test_las_causas_que_se_leen_existen_en_cobertura` avisa.
CAUSA_POCAS_VACANTES = "Pocas vacantes nuevas en las fuentes revisadas"
# Todas las vacantes del cargo son de otro país: no hay ninguna donde trabajaría (falta una fuente de ese país).
MOTIVO_OTRO_PAIS = "«oficina en otro país»"


def fuentes_locales(pais):
    return [f for f in fuentes_en(pais) if f not in GENERICAS]


def paises_del_perfil(p):
    """{país: modalidades} de un perfil: donde vive (con todas sus modalidades de esa fila; «remoto en su país» cuenta)
    y los países donde acepta híbrido o presencial. Una fila de región (Europa, LATAM…) se busca como región y no crea
    países sueltos; la remota en otros países o en cualquier parte tampoco."""
    salida = {p.vive_en: set()}
    for fila in p.filas:
        oficina = {"hibrido", "presencial"} & set(fila.modalidades)
        if p.vive_en in fila.paises:
            salida[p.vive_en] |= set(fila.modalidades)
        if oficina and not _region_de(fila.paises):
            for c in fila.paises:
                salida.setdefault(c, set()).update(oficina)
    if not salida[p.vive_en]:
        salida[p.vive_en] = set(p.modalidades)
    return salida


def _nombres():
    return {x["codigo"]: x["nombre"] for x in paises.mundo()["lista"]}


def _familia(nombre_cargo):
    f, _ = familia_del_mapa(nombre_cargo or "")
    return f["nombre"] if f else "sin familia en el mapa (añádela antes con la skill nueva-familia)"


def aviso_al_guardar(anterior, nueva):
    """Contrato §15 (8.1): al guardar, por cada país NUEVO de un perfil activo (perfil nuevo, reactivado o con otro país)
    que no tiene fuente local: «<país>: sin fuente local; riesgo de quedar bajo 5». No bloquea el guardado. `anterior` y
    `nueva` son configuraciones crudas (dict); lo que no valida no se mira."""
    from panel.modelos import Perfil

    def mapa(cfg):
        salida = {}
        for crudo in (cfg or {}).get("perfiles") or []:
            if not isinstance(crudo, dict) or not crudo.get("activo", True):
                continue
            try:
                p = Perfil.model_validate(crudo)
            except ValueError:
                continue
            salida[str(p.id)] = set(paises_del_perfil(p))
        return salida
    antes, ahora = mapa(anterior), mapa(nueva)
    nombres = _nombres()
    nuevos = sorted({c for pid, cs in ahora.items() for c in cs - antes.get(pid, set()) if not fuentes_locales(c)},
                    key=lambda c: nombres.get(c, c))
    return [f"{nombres.get(c, c)}: sin fuente local; riesgo de quedar bajo 5." for c in nuevos]


def es_hueco_por_fuentes(fila, minimo):
    """Un perfil de `cobertura()` que quedó bajo el mínimo en una búsqueda medida porque faltan vacantes en las fuentes."""
    if fila["hoy"] >= minimo or not fila["dias_medidos"] or fila["listas"] or fila["por_comprobar"]:
        return False
    causa = fila.get("causa") or ""
    return causa.startswith(CAUSA_POCAS_VACANTES) or MOTIVO_OTRO_PAIS in causa


def pedido(nombre_pais, idiomas, familias, modalidades):
    """El texto para un chat de Claude Code: solo país, idiomas, familias y modalidades (nada de personas ni conteos)."""
    return (f"Usa la skill nueva-fuente para {nombre_pais}: idioma(s) {', '.join(sorted(idiomas))}, familias de cargo "
            f"{', '.join(sorted(familias))}, modalidades {', '.join(NOMBRE_MODO[m] for m in MODOS if m in modalidades)}. "
            "Busca portales locales donde se postula ahí mismo, sin sesión. Es para hoy: deja el PR listo para revisar.")


def por_pais(cob, cfg):
    """Tabla «Huecos por país» a partir de `servicio.cobertura` y la configuración vigente (validada). Por país: perfiles,
    cuántos quedaron bajo el mínimo en la última búsqueda, fuentes que lo buscan, estado (cubierto / riesgo / hueco) y,
    en riesgo o hueco, el pedido de fuente nueva. Un hueco marca los países del perfil sin fuente local; si todos la
    tienen, el país donde vive (sus fuentes locales no alcanzan)."""
    if not cob.get("perfiles"):
        return []
    minimo = cob["minimo"]
    perfiles = {str(p.id): p for p in cfg.perfiles}
    cargos = {str(c.id): c for c in cfg.cargos}
    nombres = _nombres()
    filas = {}
    for f in cob["perfiles"]:
        p = perfiles.get(f["perfil_id"])
        if p is None:
            continue
        familia = _familia(cargos[str(p.cargo_id)].nombre if str(p.cargo_id) in cargos else f.get("cargo"))
        donde = paises_del_perfil(p)
        hueco = es_hueco_por_fuentes(f, minimo)
        marcados = [c for c in donde if not fuentes_locales(c)] or [p.vive_en]
        for codigo, modos in donde.items():
            g = filas.setdefault(codigo, {"pais": codigo, "nombre": nombres.get(codigo, codigo), "perfiles": 0,
                                          "bajo_minimo": 0, "huecos": 0, "_todos": [set(), set(), set()],
                                          "_hueco": [set(), set(), set()]})
            g["perfiles"] += 1
            if f["dias_medidos"] and f["hoy"] < minimo:
                g["bajo_minimo"] += 1
            for destino in [g["_todos"]] + ([g["_hueco"]] if hueco and codigo in marcados else []):
                destino[0].update(p.idiomas)
                destino[1].add(familia)
                destino[2].update(modos)
            if hueco and codigo in marcados:
                g["huecos"] += 1
    salida = []
    for codigo, g in filas.items():
        locales = fuentes_locales(codigo)
        estado = "hueco" if g["huecos"] else ("riesgo" if not locales else "cubierto")
        base = g["_hueco"] if estado == "hueco" else g["_todos"]
        salida.append({"pais": codigo, "nombre": g["nombre"], "perfiles": g["perfiles"],
                       "bajo_minimo": g["bajo_minimo"], "fuentes": fuentes_en(codigo), "fuentes_locales": len(locales),
                       "estado": estado, "pedido": pedido(g["nombre"], *base) if estado != "cubierto" else ""})
    orden = {"hueco": 0, "riesgo": 1, "cubierto": 2}
    salida.sort(key=lambda x: (orden[x["estado"]], -x["bajo_minimo"], x["nombre"]))
    return salida
