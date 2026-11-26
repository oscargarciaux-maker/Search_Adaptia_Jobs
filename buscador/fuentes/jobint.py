"""Bumeran y su familia de portales: Bumeran (Argentina, México, Perú y Venezuela), Laborum (Chile), Multitrabajos
(Ecuador) y Konzerta (Panamá). Contrato v50: fuentes en español para cualquier país. Son la misma plataforma, con la
misma API pública que usa su página; se postula en el mismo portal. Sin sesión.

La búsqueda devuelve el aviso completo (título, empresa, lugar, modalidad, fecha y descripción), así que no hay fichas
que leer para guardarlo. La página del aviso se arma en el navegador: su vigencia se comprueba, como la de cualquier
otro enlace, antes de entregarlo, con la ficha de la misma API (`estado_del_aviso`), igual que la de LinkedIn se
comprueba con su ficha pública (v39). Verse en la búsqueda no cuenta como comprobación."""
import re
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape

from buscador import cobertura, normalizar, paises

# país → (dominio, identificador del sitio en la API, nombre de la fuente)
SITIOS = {
    "AR": ("www.bumeran.com.ar", "BMAR", "Bumeran"),
    "MX": ("www.bumeran.com.mx", "BMMX", "Bumeran"),
    "PE": ("www.bumeran.com.pe", "BMPE", "Bumeran"),
    "VE": ("www.bumeran.com.ve", "BMVE", "Bumeran"),
    "CL": ("www.laborum.cl", "BMCL", "Laborum"),
    "EC": ("www.multitrabajos.com", "BMEC", "Multitrabajos"),
    "PA": ("www.konzerta.com", "BMPA", "Konzerta"),
}
NOMBRE = "Bumeran y portales hermanos"  # nombre de la fuente en el reporte; cada vacante lleva el de su portal
POR_PAGINA = 100
NOMBRES, NOMBRES_ES = 3, 6  # nombres del cargo que se buscan por turno (generales y en español)
FALLOS_SEGUIDOS = 3         # tras tantos fallos seguidos de un portal, ese portal descansa el resto de la corrida
_POR_DOMINIO = {dominio: (pais, sitio, nombre) for pais, (dominio, sitio, nombre) in SITIOS.items()}
_AVISO = re.compile(r"^https://([a-z.]+)/empleos/[^/?#]*?-?(\d{6,})\.html$")

# Estados de la ficha que dicen que el aviso ya no recibe postulaciones. Cualquier otro (o ninguno) no decide nada.
ACTIVO = "activo"
CERRADOS = {"finalizado", "inactivo", "cerrado", "vencido", "eliminado"}


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(str(html or "")))).strip()


def _fecha(valor, hoy=""):
    """«24-11-2026» o «24-11-2026 10:20:32» → «2026-11-24». Sin fecha real, o posterior a `hoy` (el portal va en otra
    hora), "": lo que el aviso no dice queda vacío."""
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", str(valor or ""))
    try:
        fecha = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat() if m else ""
    except ValueError:
        return ""
    return "" if hoy and fecha > hoy else fecha


def enlace(dominio, titulo, aviso_id):
    """La dirección pública del aviso, como la arma el portal: /empleos/<título>-<id>.html."""
    base = re.sub(r"[^a-z0-9]+", "-", normalizar.sin_tildes(str(titulo or "")).lower()).strip("-") or "aviso"
    return f"https://{dominio}/empleos/{base}-{aviso_id}.html"


def aviso_de(url):
    """(dominio, sitio, id) si la dirección es un aviso de uno de estos portales; si no, None."""
    m = _AVISO.match(str(url or ""))
    if not m or m.group(1) not in _POR_DOMINIO:
        return None
    return m.group(1), _POR_DOMINIO[m.group(1)][1], m.group(2)


def _cabeceras(dominio, sitio):
    return {"x-site-id": sitio, "Accept": "application/json", "Referer": f"https://{dominio}/"}


def vacante(a, pais, nombres, hoy=""):
    """Vacante cruda desde un aviso de la búsqueda. La ubicación lleva el país del portal y la modalidad que declara."""
    dominio, _, nombre = SITIOS[pais]
    modalidad = normalizar.texto(a.get("modalidadTrabajo") or "")
    remoto = True if modalidad == "remoto" else None
    sufijo = " (Remoto)" if remoto else " (Híbrido)" if modalidad == "hibrido" else " (Presencial)" if modalidad == "presencial" else ""
    lugar = paises.lugar_del_portal(a.get("localizacion"), pais, nombres.get(pais, pais), remoto=bool(remoto))
    empresa = str(a.get("empresa") or "").strip()
    return {"titulo": str(a.get("titulo") or "").strip(), "empresa": "" if empresa.lower() == "confidencial" else empresa,
            "ubicacion": lugar + sufijo, "descripcion": _texto(a.get("detalle"))[:30000],
            "fecha": _fecha(a.get("fechaPublicacion"), hoy), "enlace": enlace(dominio, a.get("titulo"), a.get("id")),
            "enlace_directo": "", "remoto": remoto, "fuente": nombre}


def combinaciones(mapa, nombres):
    """(familia, consultas, lugar, {}) por cargo y país con portal. Como en Computrabajo (v44): los títulos en español
    tienen su propio turno («AR:ES») en los países de quienes aceptan avisos en español."""
    salida = []
    for f in mapa:
        es = list(f.get("consultas_es") or [])
        resto = [c for c in cobertura.consultas(f) if c not in es]
        for codigo in f.get("paises_objetivo", list(nombres)):
            if codigo not in SITIOS:
                continue
            if es and codigo in (f.get("paises_es") or []):
                salida.append((f["id"], es, codigo + ":ES", {}))
            if resto:
                salida.append((f["id"], resto, codigo, {}))
            elif es and codigo not in (f.get("paises_es") or []):
                salida.append((f["id"], es, codigo, {}))
    return salida


def buscar(cliente, mapa, paises_activos, estado, presupuesto, hoy=None, max_dias=30, reloj=time.monotonic,
           limite_segundos=None, prioritarias=(), pausa=0.6, dormir=time.sleep):
    """Recorre (cargo, país) menos recientes hasta gastar el presupuesto de búsquedas. `paises_activos`: [(código,
    nombre)]. Devuelve (vacantes crudas, estadísticas)."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    inicio = reloj()
    desde = (datetime.fromisoformat(hoy) - timedelta(days=max_dias)).date().isoformat()
    nombres = dict(paises_activos)
    todas = cobertura.repartir(combinaciones(mapa, nombres), estado, hoy, prioritarias)
    # La búsqueda es estricta (casi solo trae avisos con ese nombre) y barata: varios nombres por combinación, cada uno
    # con su clave. Primero el primer nombre de cada combinación, luego el segundo…
    turnos = [(k, c) for c in todas
              for k in range(min(len(c[1]), NOMBRES_ES if cobertura.es_espanol(c[2]) else NOMBRES))]
    turnos.sort(key=lambda t: t[0])  # estable: dentro de cada vuelta, el orden del reparto
    crudas, vistos, hechas, fallidas, por_pais = [], set(), 0, 0, {}
    seguidas = {}  # país → fallos seguidos: un portal caído (son siete sitios distintos) no corta a los demás
    for k, (familia, consultas, lugar, _) in turnos:
        if hechas >= presupuesto or (limite_segundos is not None and reloj() - inicio >= limite_segundos):
            break
        if seguidas.get(lugar.split(":")[0], 0) >= FALLOS_SEGUIDOS:
            continue
        b = cobertura.siguiente_busqueda(consultas, hoy, 1, f"{familia}@{lugar}", estado, desfase=k, paginada=False)
        if b is None:  # contrato v47: ya se buscaron hoy todos sus nombres ahí
            continue
        pais = lugar.split(":")[0]
        dominio, sitio, _ = SITIOS[pais]
        hechas += 1
        por_pais[pais] = por_pais.get(pais, 0) + 1
        cobertura.anotar_busqueda("jobint", familia, lugar)
        datos = cliente.post_json(f"https://{dominio}/api/avisos/searchV2?pageSize={POR_PAGINA}&page=0&sort=RECIENTES",
                                  {"filtros": [], "query": b.terminos[0]}, headers=_cabeceras(dominio, sitio))
        dormir(pausa)
        if not isinstance(datos, dict) or not isinstance(datos.get("content"), list):
            fallidas += 1
            seguidas[pais] = seguidas.get(pais, 0) + 1
            continue
        seguidas[pais] = 0
        cobertura.anotar_hecha(estado, b, hoy)
        for a in datos["content"]:
            if not isinstance(a, dict) or not a.get("id") or not a.get("titulo"):
                continue
            v = vacante(a, pais, nombres, hoy)
            if v["enlace"] in vistos or (v["fecha"] and v["fecha"] < desde):
                continue
            vistos.add(v["enlace"])
            crudas.append(v)  # sin `_busqueda`: el rendimiento por combinación (v40) mide solo LinkedIn e Indeed
    return crudas, {"busquedas": hechas, "fallidas": fallidas, "avisos": len(crudas), "por_pais": por_pais,
                    "portales_caidos": sorted(p for p, n in seguidas.items() if n >= FALLOS_SEGUIDOS),
                    "combinaciones_total": len(todas)}


def estado_del_aviso(sesion, url, titulo, coincide, timeout=12, cabeceras=None):
    """(estado, motivo, código HTTP) de un aviso de estos portales, leyendo su ficha en la API pública del portal.
    `coincide(título pedido, título hallado)` es la misma regla de títulos del resto de comprobaciones."""
    dominio, sitio, aviso_id = aviso_de(url)
    r = sesion.get(f"https://{dominio}/api/candidates/fichaAvisoNormalizada/{aviso_id}",
                   headers={**(cabeceras or {}), **_cabeceras(dominio, sitio)}, timeout=timeout)
    if r.status_code in (404, 410):
        return "rechazada", "enlace roto", r.status_code
    if r.status_code != 200:
        return "pendiente", "acceso bloqueado o fallo temporal", r.status_code
    try:
        datos = r.json()
    except ValueError:
        return "pendiente", "respuesta no comprobable", r.status_code
    aviso = datos.get("aviso") if isinstance(datos, dict) else None
    estado = aviso.get("estado") if isinstance(aviso, dict) else None
    if not isinstance(aviso, dict) or not isinstance(aviso.get("titulo"), str) or not aviso["titulo"].strip():
        return "pendiente", "contenido insuficiente", r.status_code
    estado = estado.strip().lower() if isinstance(estado, str) else ""
    if estado in CERRADOS:
        return "rechazada", "vacante cerrada", r.status_code
    # Sin estado, o con uno que no se conoce, no se aprueba ni se cierra (si la API cambia, no se cierra todo).
    if estado != ACTIVO or not coincide(titulo, aviso["titulo"]):
        return "pendiente", "ficha específica sin confirmar", r.status_code
    return "verificada", "ficha específica accesible", r.status_code
