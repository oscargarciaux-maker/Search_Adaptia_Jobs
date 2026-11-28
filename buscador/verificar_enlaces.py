"""Comprueba destinos públicos por GET; no inicia sesión ni envía postulaciones."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
from threading import BoundedSemaphore, Lock
import time
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from buscador import enlaces, normalizar, tiempos
from buscador.http import NAVEGADOR

RECHAZOS = {"enlace roto", "vacante cerrada", "postulación con cobro", "destino agregador o de pago",
            "ciclo de redirecciones", "demasiadas redirecciones", "página general sin vacante", "destino no público"}
_CERRADA = re.compile(r"no longer accepting applications|this (?:job|position) (?:is no longer available|has been filled)|"
    r"job (?:has expired|is no longer available)|ya no (?:acepta|se aceptan) (?:solicitudes|postulaciones)|"
    r"(?:esta )?(?:vacante|oferta) (?:ha sido cerrada|ya no está disponible|ha caducado|ha finalizado)|"
    r"oferta (?:caducada|finalizada)|vaga (?:encerrada|não está mais disponível)", re.I)
_COBRO = re.compile(r"(?:pay|payment|purchase|subscribe|subscription required).{0,70}(?:to apply|to submit (?:your |an )?application)|"
    r"(?:paga|pagar|pago obligatorio|suscr[ií]bete|suscripci[oó]n obligatoria).{0,70}(?:para (?:aplicar|postular|acceder a la oferta))|"
    r"(?:pague|pagamento obrigat[oó]rio).{0,60}para (?:se candidatar|candidatar)|"
    r"(?:application|processing) fee (?:of |is required)|(?:tarifa|cuota) (?:obligatoria )?(?:de postulaci[oó]n|para postular)", re.I)
_NEGACION = re.compile(r"(?:never|not required|no fees|no payment|do not charge|will not|"
                       r"(?:do|should|must) not pay|(?:don|shouldn|mustn)['’]t pay|nunca|"
                       r"no cobramos|no (?:debes|debe|deberás|tienes que|es necesario) pagar|"
                       r"no (?:te )?pediremos|sin (?:coste|costo|pago)|não cobramos)", re.I)
_BLOQUEO = re.compile(r"captcha|verify (?:you are|you're) human|access denied|checking your browser|just a moment", re.I)
_LOGIN = re.compile(r"^(?:sign in|log in|iniciar sesi[oó]n|acceder|login)(?:\s|$)", re.I)
# El paso «Postular» de un portal que pide su propia cuenta (P-11.1): /login, /webpros/login, /users/sign_in…
_RUTA_LOGIN = re.compile(r"/(?:log-?in|sign[-_]?in|ingresar|iniciar[-_]sesion)(?:/|$)", re.I)
POSTULAR_CON_CUENTA = "ficha específica accesible; postular pide cuenta del portal"
_APLICAR = re.compile(r"^(?:apply(?: now| for (?:this )?(?:job|position))?|postular(?:me)?|aplicar(?: ahora)?|"
                       r"candidatar(?:-se)?|inscrever-se|solicitar (?:este )?empleo)$", re.I)


# Contrato v39: la ficha pública de LinkedIn (la misma que lee la búsqueda) en lugar de la página del aviso, que
# responde 429 cuando se le pregunta seguido (17 nov: 1.676 enlaces quedaron «bloqueados» y no se entregaron).
_LINKEDIN_AVISO = re.compile(r"^https?://(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/jobs/view/(?:[^/?#]*-)?(\d+)", re.I)
LINKEDIN_FICHA = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
_CERRADA_LINKEDIN = re.compile(r"closed-job|Ya no se aceptan solicitudes", re.I)
# Indeed responde 401 a cualquier comprobación: no se le pregunta; su vacante vale si el enlace directo está comprobado.
# Sitios cuya ficha no se puede abrir (Indeed responde 401; InfoJobs pide captcha): un aviso suyo cuenta como abierto
# solo el día que su propia búsqueda lo muestra (v41 para Indeed; v50, decisión de Oscar del 26 nov, para InfoJobs).
SIN_COMPROBACION_DIRECTA = ("indeed.com", "infojobs.net")
PAUSA_LINKEDIN = 1.5  # segundos entre comprobaciones de LinkedIn
BLOQUEOS_LINKEDIN = 3  # tras tantos 429 seguidos, LinkedIn descansa el resto de la ronda


def aviso_linkedin(url):
    m = _LINKEDIN_AVISO.match(url or "")
    return m.group(1) if m else ""


def ficha_linkedin(html, titulo):
    """Contrato v39: (estado, motivo) de la ficha pública de LinkedIn. Abierta solo si trae el título del aviso y su
    descripción; cerrada si dice que ya no recibe postulaciones. Un 200 sin el título (un aviso que ya no existe
    también responde 200) nunca aprueba."""
    if _CERRADA.search(html or "") or _CERRADA_LINKEDIN.search(html or ""):
        return "rechazada", "vacante cerrada"
    m = re.search(r"top-card-layout__title[^>]*>([\s\S]*?)</h[1-3]>", html or "")
    nombre = BeautifulSoup(m.group(1), "html.parser").get_text(" ", strip=True) if m else ""
    if not nombre or not _coincide(titulo, nombre):
        return "pendiente", "ficha específica sin confirmar"
    if "show-more-less-html__markup" not in html:
        return "pendiente", "contenido insuficiente"
    return "verificada", "ficha de LinkedIn abierta"


def de_dominio(url, dominio):
    """El enlace es de ese dominio o de un subdominio suyo («co.indeed.com»); nunca de uno que solo lo contiene o
    termina igual («notindeed.com», «indeed.com.otro.net»)."""
    h = enlaces.host(url)
    return h == dominio or h.endswith("." + dominio)


def sin_comprobacion_directa(url):
    """Un sitio de `SIN_COMPROBACION_DIRECTA`: su ficha nunca se pide. Con la clave de la API oficial de InfoJobs
    (contrato v50), sus avisos sí se comprueban: por la ficha de esa API, no por su página."""
    if de_dominio(url, "infojobs.net"):
        from buscador.fuentes import infojobs
        return not (infojobs.credenciales() and infojobs.aviso_de(url))
    return any(de_dominio(url, d) for d in SIN_COMPROBACION_DIRECTA)


# Así empieza el motivo de un enlace que vale por haberse visto hoy en la búsqueda de su sitio (v41 Indeed, v42 portales
# de empresa, v50 InfoJobs). La medición de la corrida los separa de los que se comprobaron abriendo la ficha.
VISTA_HOY = "vista hoy"


def vistas_en_portales(enlaces_vistos, ahora=None):
    """Contrato v42: los avisos que el portal de empleo de la propia empresa (Greenhouse, Lever, Ashby, Workable,
    SmartRecruiters, Recruitee) listó en esta corrida cuentan como abiertos 24 h. Esas API públicas solo listan avisos
    activos y son el mismo sitio donde se postula. Computrabajo y Get on Board no entran: sus listados pueden traer
    avisos viejos. Devuelve {enlace: comprobación} para `incorporar`."""
    hora = (ahora or datetime.now(timezone.utc)).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {u: {"estado": "verificada", "motivo": f"{VISTA_HOY} en el portal de la empresa", "comprobada_en": hora,
                "destino": u}
            for u in enlaces_vistos
            if u and enlaces.sirve(u) and not enlaces.es_linkedin(u) and not sin_comprobacion_directa(u)}


def incorporar(vacantes, cache, fichas):
    """Contrato v39: las fichas de LinkedIn que la búsqueda ya leyó hoy valen como comprobación (abierta o cerrada) del
    enlace, sin volver a preguntar. Contrato v41: también los avisos que la búsqueda de Indeed mostró hoy (Indeed solo
    lista avisos activos y responde 401 a cualquier comprobación directa). Contrato v42: y los que listó hoy el portal de
    la propia empresa (`vistas_en_portales`). Solo reemplaza una comprobación más
    antigua. Devuelve cuántas incorporó."""
    n = 0
    for v in vacantes:
        for u in urls(v):
            leida = fichas.get(u)
            if not leida:
                continue
            anterior = cache.get(u) or {}
            if anterior.get("_titulo") == v["titulo"] and (anterior.get("comprobada_en") or "") >= leida["comprobada_en"]:
                continue
            cache[u] = {"url": u, "destino": leida.get("destino") or LINKEDIN_FICHA + aviso_linkedin(u), "estado": leida["estado"],
                        "motivo": leida["motivo"], "comprobada_en": leida["comprobada_en"], "http": 200, "saltos": 0,
                        "ruta": [u], "_titulo": v["titulo"]}
            n += 1
    return n


def publica(url, resolver=socket.getaddrinfo):
    """Evita que una URL o redirección de los datos alcance servicios locales."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
            return False
        ips = {fila[4][0] for fila in resolver(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except ValueError:
        return False


def _coincide(titulo, candidato):
    def palabras(t):
        return set(normalizar.titulo_base(t).replace("/", " ").split()) - {"de", "en", "and", "the", "at", "para", "with", "con"}
    a, b = palabras(titulo), palabras(candidato)
    return bool(a) and len(a & b) >= min(2, len(a)) and len(a & b) / len(a) >= 0.65


def _jobs(valor):
    if isinstance(valor, list):
        return [j for v in valor for j in _jobs(v)]
    if not isinstance(valor, dict):
        return []
    tipo = valor.get("@type", [])
    if tipo == "JobPosting" or isinstance(tipo, list) and "JobPosting" in tipo:
        return [valor]
    return [j for v in valor.values() if isinstance(v, (dict, list)) for j in _jobs(v)]


def contenido(html, url, titulo, ahora):
    """Un HTTP 200 solo es candidato: exigir evidencia de una ficha específica."""
    sopa = BeautifulSoup(html, "html.parser")
    trabajos = []
    for s in sopa.find_all("script", type="application/ld+json"):
        try:
            trabajos.extend(_jobs(json.loads(s.string or s.get_text())))
        except (ValueError, RecursionError):
            pass
    refresh = sopa.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)})
    if refresh:
        m = re.search(r"url\s*=\s*(.+)$", refresh.get("content", ""), re.I)
        if m:
            return "redirigir", m.group(1).strip(" \"'"), ""
    for script in sopa.find_all("script"):
        m = re.fullmatch(r"\s*(?:window\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"'];?\s*", script.string or "")
        if m:
            return "redirigir", m.group(1), ""
    cabecera = " ".join(n.get_text(" ", strip=True) for n in sopa.select("h1"))
    page_title = sopa.title.get_text(" ", strip=True) if sopa.title else ""
    for n in sopa(["script", "style", "nav", "footer", "aside"]):
        n.decompose()
    cuerpo = sopa.find("main") or sopa.find("article") or sopa
    texto = cuerpo.get_text(" ", strip=True)
    propios = [j for j in trabajos if _coincide(titulo, j.get("title", ""))]
    texto += " " + " ".join(BeautifulSoup(str(j.get("description", "")), "html.parser").get_text(" ", strip=True) for j in propios)
    if _BLOQUEO.search(page_title) or len(texto) < 500 and _BLOQUEO.search(texto):
        return "pendiente", "acceso bloqueado", ""
    if _CERRADA.search(texto):
        return "rechazada", "vacante cerrada", ""
    sin_advertencias = " ".join(frase for frase in re.split(r"[.!?]", texto) if not _NEGACION.search(frase))
    if _COBRO.search(sin_advertencias):
        return "rechazada", "postulación con cobro", ""
    for j in propios:
        fin = j.get("validThrough")
        if fin:
            try:
                vencida = (datetime.fromisoformat(fin.replace("Z", "+00:00")) < ahora
                           if tiempos.instante(fin) else fin[:10] < ahora.date().isoformat())
                if vencida:
                    return "rechazada", "vacante cerrada", ""
            except (ValueError, TypeError):
                pass
    especifica = (len(trabajos) == 1 and bool(propios)) or _coincide(titulo, cabecera) or _coincide(titulo, page_title)
    if not especifica:
        if _LOGIN.search(page_title) or _LOGIN.search(cabecera):
            return "pendiente", "requiere iniciar sesión", ""
        generica = re.fullmatch(r"/(?:[a-z]{2}/)?(?:careers?|jobs?|for-developers|open-positions|talent-pool)?/?", urlparse(url).path or "/", re.I)
        if enlaces.host(url).endswith(("greenhouse.io", "lever.co", "ashbyhq.com")):
            generica = generica or re.fullmatch(r"/[^/]+/?", urlparse(url).path)
        return ("rechazada", "página general sin vacante", "") if generica else ("pendiente", "ficha específica sin confirmar", "")
    if len(texto) < 150 and not propios:
        return "pendiente", "contenido insuficiente", ""
    aplicar = ""
    for a in cuerpo.select("a[href]"):
        if _APLICAR.fullmatch(a.get_text(" ", strip=True)):
            candidata = urljoin(url, a["href"])
            if candidata.startswith(("http://", "https://")) and urldefrag(candidata)[0] != urldefrag(url)[0]:
                aplicar = candidata
                break
    return "verificada", "ficha específica accesible", aplicar


def _login_del_portal(destino, sitio_ficha, ruta=False):
    """El paso «Postular» de una ficha ya aprobada sigue en el mismo sitio (y, con `ruta`, su dirección es de login)."""
    return bool(sitio_ficha) and enlaces.host(destino) == sitio_ficha and (
        not ruta or bool(_RUTA_LOGIN.search(urlparse(destino).path)))


def comprobar(url, titulo, *, sesion=None, validar_url=publica, ahora=None, plazo=None, max_saltos=5, max_bytes=1_000_000):
    ahora = ahora or datetime.now(timezone.utc)
    propia = sesion is None
    sesion = sesion or requests.Session()
    ruta, visitadas, destino, codigo = [], set(), url, None
    pasos_aplicacion = 0
    def resultado(estado, motivo):
        return {"url": url, "destino": destino, "estado": estado, "motivo": motivo,
                "comprobada_en": ahora.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "http": codigo, "saltos": max(0, len(ruta) - 1), "ruta": ruta}
    try:
        if sin_comprobacion_directa(url):
            # Indeed responde 401 e InfoJobs pide captcha: su ficha no se pide desde ningún camino (v41, v50).
            return resultado("pendiente", "sin comprobación directa")
        if de_dominio(url, "infojobs.net"):
            # Con la clave de su API oficial: la ficha de la API dice si el aviso sigue activo (nunca su página).
            from buscador.fuentes import infojobs
            ruta.append(url)
            timeout = min(12, max(0.1, plazo - time.monotonic())) if plazo else 12
            estado, motivo, codigo = infojobs.estado_del_aviso(sesion, url, titulo, _coincide, timeout)
            return resultado(estado, motivo)
        if aviso_linkedin(url):
            ruta.append(url)
            timeout = min(12, max(0.1, plazo - time.monotonic())) if plazo else 12
            r = sesion.get(LINKEDIN_FICHA + aviso_linkedin(url), headers=NAVEGADOR, timeout=timeout)
            codigo = r.status_code
            if codigo in (404, 410):
                return resultado("rechazada", "enlace roto")
            if codigo != 200:
                return resultado("pendiente", "acceso bloqueado o fallo temporal")
            return resultado(*ficha_linkedin(r.text, titulo))
        from buscador.fuentes import jobint
        if jobint.aviso_de(url):
            # Contrato v50: Bumeran y sus portales hermanos arman la página en el navegador; el aviso se comprueba con
            # la ficha de la API pública del mismo portal (activo y con el mismo título).
            ruta.append(url)
            timeout = min(12, max(0.1, plazo - time.monotonic())) if plazo else 12
            estado, motivo, codigo = jobint.estado_del_aviso(sesion, url, titulo, _coincide, timeout, NAVEGADOR)
            return resultado(estado, motivo)
        sitio_ficha = ""  # el sitio de la ficha ya aprobada, cuando se sigue su paso de aplicación
        while True:
            if _login_del_portal(destino, sitio_ficha, ruta=True):
                # P-11.1 (decisión de Oscar del 28 nov): «Postular» lleva al inicio de sesión del mismo portal (Get on
                # Board pide su cuenta): la ficha ya abierta comprueba la vacante. En otro sitio, el login no cuenta.
                return resultado("verificada", POSTULAR_CON_CUENTA)
            if plazo and time.monotonic() >= plazo:
                return resultado("pendiente", "presupuesto de comprobación agotado")
            clave = urldefrag(destino)[0]
            if clave in visitadas:
                return resultado("rechazada", "ciclo de redirecciones")
            if len(ruta) > max_saltos:
                return resultado("rechazada", "demasiadas redirecciones")
            if not validar_url(destino):
                return resultado("rechazada", "destino no público")
            if enlaces.tipo(destino) == "agregador":
                return resultado("rechazada", "destino agregador o de pago")
            visitadas.add(clave)
            ruta.append(destino)
            timeout = min(12, max(0.1, plazo - time.monotonic())) if plazo else 12
            with sesion.get(destino, headers=NAVEGADOR, allow_redirects=False, stream=True, timeout=timeout) as r:
                codigo = r.status_code
                if codigo in (301, 302, 303, 307, 308):
                    if not r.headers.get("Location"):
                        return resultado("pendiente", "redirección sin destino")
                    destino = urljoin(destino, r.headers["Location"])
                    continue
                if codigo in (404, 410):
                    return resultado("rechazada", "enlace roto")
                if codigo == 402:
                    return resultado("rechazada", "postulación con cobro")
                if codigo in (401, 403, 429, 999) or codigo >= 500:
                    return resultado("pendiente", "acceso bloqueado o fallo temporal")
                if codigo != 200:
                    return resultado("pendiente", "respuesta no comprobable")
                datos = bytearray()
                for bloque in r.iter_content(16384):
                    if plazo and time.monotonic() >= plazo:
                        return resultado("pendiente", "presupuesto de comprobación agotado")
                    datos.extend(bloque)
                    if len(datos) > max_bytes:
                        return resultado("pendiente", "página demasiado grande")
                estado, motivo, siguiente = contenido(datos.decode(r.encoding or "utf-8", errors="replace"), destino, titulo, ahora)
            if estado == "redirigir":
                destino = urljoin(destino, motivo)
                continue
            if estado == "verificada" and siguiente and not pasos_aplicacion:
                # Solo un paso visible de aplicación, sin enviar formularios ni recorrer cuentas.
                pasos_aplicacion += 1
                sitio_ficha = enlaces.host(destino)
                destino = siguiente
                continue
            if _login_del_portal(destino, sitio_ficha) and motivo == "requiere iniciar sesión":
                return resultado("verificada", POSTULAR_CON_CUENTA)
            return resultado(estado, motivo)
    except (requests.RequestException, ValueError, OSError):
        return resultado("pendiente", "error de conexión o URL no comprobable")
    finally:
        if propia:
            sesion.close()


def urls(v):
    return list(dict.fromkeys(u for u in (v.get("enlace"), v.get("enlace_directo")) if u))


# Una comprobación positiva o un cierre sirven 24 h para decidir la selección: las capturas de cada hora van llenando el
# pool que se entregará por la noche. Lo que se comparte (copiar a WhatsApp) exige 6 h y el lote del día se vuelve a
# comprobar con ese plazo. Un bloqueo o fallo temporal solo cuenta 30 min.
VIGENCIA_SELECCION = 24 * 3600
VIGENCIA_COMPARTIR = 6 * 3600
VIGENCIA_PENDIENTE = 1800


def vigente(r, titulo, ahora, vigencia=VIGENCIA_SELECCION):
    try:
        edad = (ahora - datetime.fromisoformat(r["comprobada_en"].replace("Z", "+00:00"))).total_seconds()
        return r.get("_titulo") == titulo and 0 <= edad < (VIGENCIA_PENDIENTE if r["estado"] == "pendiente" else vigencia)
    except (KeyError, ValueError, TypeError):
        return False


def anotar(v, cache, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    resultados = []
    for u in urls(v):
        r = cache.get(u, {})
        resultados.append({k: val for k, val in r.items() if not k.startswith("_")} if vigente(r, v["titulo"], ahora)
            else {"url": u, "estado": "pendiente", "motivo": "sin comprobación vigente", "comprobada_en": "",
                  "destino": "", "http": None, "saltos": 0, "ruta": []})
    buenas = [r for r in resultados if r["estado"] == "verificada"]
    estado = "verificada" if buenas else "rechazada" if resultados and all(r["estado"] == "rechazada" for r in resultados) else "pendiente"
    elegido = buenas[0] if buenas else next((r for r in resultados if r["estado"] == "pendiente"), resultados[0] if resultados else {})
    v["verificacion"] = {"estado": estado, "comprobada_en": elegido.get("comprobada_en", ""),
        "motivo": elegido.get("motivo", "sin enlace"), "url_utilizable": elegido.get("url", "") if buenas else "",
        "enlaces": resultados}
    return v["verificacion"]


def auditar(vacantes, cache, *, maximo=240, segundos=240, hilos=6, comprobar_url=None, ahora=None,
            vigencia=VIGENCIA_SELECCION, linkedin_aparte=False):
    """Comprueba hasta `maximo` vacantes y devuelve cuántas escogió. `linkedin_aparte` (contrato v50, la cola por
    persona): `maximo` cuenta solo los sitios que se comprueban en paralelo, y LinkedIn, que va de una en una, se
    limita solo por su tiempo; se devuelven las dos sumadas. Antes compartían el máximo y los avisos de Computrabajo,
    Elempleo o Get on Board (casi todo en español) perdían el turno frente a los de LinkedIn."""
    ahora = ahora or datetime.now(timezone.utc)
    comprobar_url = comprobar_url or comprobar
    plazo = time.monotonic() + segundos
    escogidas, peticiones = [], {}
    # Contrato v41: LinkedIn va de una en una con pausa; no se le asignan más enlaces de los que alcanza en el tiempo, y
    # el resto del cupo queda para los demás sitios (antes Computrabajo y Get on Board casi nunca tenían turno).
    cupo_linkedin, de_linkedin, de_otros = int(segundos / max(PAUSA_LINKEDIN, 0.5)) + 1, 0, 0
    for v in vacantes:
        pendientes = [u for u in urls(v) if not vigente(cache.get(u, {}), v["titulo"], ahora, vigencia)
                      and not sin_comprobacion_directa(u)]
        es_linkedin = bool(pendientes) and all(aviso_linkedin(u) for u in pendientes)
        usadas = de_otros if linkedin_aparte and not es_linkedin else 0 if linkedin_aparte else de_otros + de_linkedin
        if pendientes and usadas < maximo and not (es_linkedin and de_linkedin >= cupo_linkedin):
            escogidas.append(v)
            de_linkedin += es_linkedin
            de_otros += not es_linkedin
            for u in pendientes:
                peticiones.setdefault((u, v["titulo"]), None)
    # Contrato v39: LinkedIn de una en una y con pausa; tras varios bloqueos seguidos deja el tiempo a los demás sitios.
    semaforos = {enlaces.host(u): BoundedSemaphore(1 if aviso_linkedin(u) else 2) for u, _ in peticiones}
    linkedin = {"ultima": 0.0, "bloqueos": 0, "lock": Lock()}
    def tarea(clave):
        u, titulo = clave
        if time.monotonic() >= plazo:
            return None
        semaforo = semaforos[enlaces.host(u)]
        if not semaforo.acquire(timeout=max(0, plazo - time.monotonic())):
            return None
        try:
            if aviso_linkedin(u):
                if linkedin["bloqueos"] >= BLOQUEOS_LINKEDIN:
                    return None
                espera = linkedin["ultima"] + PAUSA_LINKEDIN - time.monotonic()
                if espera > 0:
                    time.sleep(min(espera, max(0, plazo - time.monotonic())))
                linkedin["ultima"] = time.monotonic()
            r = comprobar_url(u, titulo, ahora=ahora, plazo=plazo)
            if aviso_linkedin(u) and r:
                with linkedin["lock"]:
                    linkedin["bloqueos"] = linkedin["bloqueos"] + 1 if r.get("http") == 429 else 0
            return r
        finally:
            semaforo.release()
    # Contrato v41: LinkedIn en su propia fila (un hilo) y los demás sitios con todos los hilos; antes las de LinkedIn
    # ocupaban los hilos esperando su turno y los demás sitios casi no avanzaban.
    with ThreadPoolExecutor(1) as solo_linkedin, ThreadPoolExecutor(hilos) as ex:
        futuros = {(solo_linkedin if aviso_linkedin(clave[0]) else ex).submit(tarea, clave): clave for clave in peticiones}
        for futuro in as_completed(futuros):
            u, titulo = futuros[futuro]
            try:
                r = futuro.result()
            except Exception:  # un fallo de un candidato nunca aprueba ni aborta los restantes
                r = None
            if r:
                cache[u] = dict(r, _titulo=titulo)
    for v in vacantes:
        anotar(v, cache, ahora)
    return len(escogidas)


def resumen(vacantes):
    estados = Counter((v.get("verificacion") or {}).get("estado", "pendiente") for v in vacantes)
    motivos = Counter((v.get("verificacion") or {}).get("motivo", "sin comprobación") for v in vacantes
                      if (v.get("verificacion") or {}).get("estado") != "verificada")
    return {"vacantes": len(vacantes), "estados": dict(estados), "motivos": dict(motivos)}


def cola_de_seleccion(vacantes, entregadas, hoy, cache, iniciales, maximo, ahora=None, limite=None):
    """Candidatas en el orden en que las elegiría la selección (con los filtros del panel si está activo), más allá del
    cupo: si las primeras fallan, ya estarán comprobadas las siguientes. Solo cuenta las que necesitan comprobación.
    `limite` (contrato v48, «Buscar ahora»): instante de `time.monotonic()` en que se deja de ordenar y se devuelve lo
    que haya."""
    from buscador import contrato, entrega
    ahora = ahora or datetime.now(timezone.utc)
    ids_iniciales = {v["id"] for lista in iniciales.values() for v, _ in lista}
    # Reducir una sola vez a lo que la selección podría tomar (mismas reglas que `elegir`); las rondas son baratas.
    # El inventario ya llega sin copias (`limpiar`); `elegir` vuelve a juntar solo este subconjunto.
    cfg = entrega.config()
    idiomas = tuple(cfg.get("idiomas", ["es", "en"]))
    vacantes = [v for v in vacantes
                if entrega.rol_de(v, cfg["roles"])[0] and not any(h in entregadas for h in entrega.huellas(v))
                and not contrato.entregable(dict(v, verificacion=None), idiomas)]
    cola, vistas, por_comprobar = [], set(ids_iniciales), 0
    duracion = 0.0
    for _ in range(12):
        # Con límite, no se empieza otra selección que no alcanzaría a terminar antes (la anterior da la medida).
        if limite is not None and time.monotonic() + duracion >= limite:
            break
        inicio = time.monotonic()
        disponibles = [v for v in vacantes if v["id"] not in vistas]
        seleccion, _ = entrega.elegir(disponibles, entregadas, hoy, iniciales=iniciales, omitir_verificacion=True)
        duracion = time.monotonic() - inicio
        # `elegir` devuelve también los objetos del lote ya registrado: nunca se auditan aquí (ver `historicas`).
        nuevas = [v for lista in seleccion.values() for v, _ in lista if v["id"] not in vistas]
        if not nuevas:
            break
        for v in nuevas:
            vistas.add(v["id"])
            cola.append(v)
            por_comprobar += any(not vigente(cache.get(u, {}), v["titulo"], ahora) for u in urls(v))
        if por_comprobar >= maximo:
            break
    return cola


def cola_por_necesidad(vacantes, hoy):
    """Contrato v49 (solo modo panel): las candidatas de cada persona, por turnos y primero quien tiene menos
    candidatas con el enlace comprobado (P-11.1), hasta `entrega.POR_PLAZA` por plaza de su meta. Antes la cola salía
    solo de lo que elegiría el lote: de 21 remotas en español abiertas a Colombia para un cargo, 1 tenía el enlace
    comprobado, y sin enlace comprobado no se completa a nadie."""
    from buscador import entrega
    return entrega.colas_por_persona(vacantes, hoy)[0]


def preparar(vacantes, entregadas, hoy, cache, *, lote=None, incremental=False, cfg=None, medir=None):
    """Comprueba candidatas antes de la selección; lo no revisado nunca se da por aprobado.
    Orden: el lote ya registrado hoy (plazo para compartir), las que elegiría la selección en su orden y, en las
    capturas horarias, lo reciente con el presupuesto que sobre."""
    cfg = cfg or {}
    from contextlib import nullcontext
    medir = medir or (lambda texto, **cifras: nullcontext(cifras))  # P-12.3: solo para medir, texto fijo y cifras
    maximo = cfg.get("vacantes_por_captura", 40) if incremental else cfg.get("vacantes_por_corrida", 300)
    segundos = cfg.get("segundos_captura", 90) if incremental else cfg.get("segundos_corrida", 240)
    plazo = time.monotonic() + segundos
    # Contrato v48: en «Buscar ahora» (faltantes) ordenar también cuenta en el plazo; la noche no cambia.
    contar_orden = bool(cfg.get("contar_orden"))
    for v in vacantes:
        anotar(v, cache)
    por_id = {v["id"]: v for v in vacantes}
    iniciales = (lote or {}).get("elegidas", {}) if (lote or {}).get("fecha") == hoy else {}
    # Copias: auditar nunca debe tocar los objetos del lote registrado (Supabase exige su snapshot intacto).
    historicas = [dict(por_id.get(v["id"], v)) for lista in iniciales.values() for v, _ in lista]
    hora = datetime.now(timezone.utc).hour
    if incremental and historicas:
        inicio = hora * maximo % len(historicas)
        historicas = historicas[inicio:] + historicas[:inicio]
    revisadas_n = 0
    if historicas:
        with medir("Comprobar enlaces: lote del día", candidatas=len(historicas)) as cifras:
            n_lote = auditar(historicas, cache, maximo=maximo // 3 if incremental else maximo,
                             segundos=max(0, plazo - time.monotonic()), vigencia=VIGENCIA_COMPARTIR)
            cifras["abiertas"] = n_lote
        revisadas_n += n_lote
    revisadas = set()
    por_necesidad = 0
    # Contrato v49: primero las candidatas de cada persona, con la mitad del presupuesto que queda. Contrato v50: esa
    # mitad es para los sitios en paralelo; las de LinkedIn van aparte, hasta donde alcance su parte del tiempo.
    # P-11.1 (28 nov): detrás del tope de cada persona va el resto de sus candidatas por abrir. LinkedIn, de una en una,
    # se come todo el tiempo de cada fase y los demás sitios solo avanzan con lo que esté en la misma fase: la Bodega
    # del 27 abrió 213 enlaces con cupo de 800 y 600 s, y Computrabajo, Bumeran, Laborum o Magneto casi nunca.
    try:
        from buscador import entrega
        con_tope, resto = entrega.colas_por_persona(vacantes, hoy)
        necesidad = con_tope + resto
        if necesidad and revisadas_n < maximo:
            parte = 3 if incremental else 2
            cupo = max(1, (maximo - revisadas_n) // parte)
            with medir("Comprobar enlaces: por necesidad de cada persona", candidatas=len(necesidad)) as cifras:
                por_necesidad = auditar(necesidad, cache, maximo=cupo,
                                        segundos=max(0, plazo - time.monotonic()) / parte, linkedin_aparte=True)
                cifras["abiertas"] = por_necesidad
            revisadas_n += min(por_necesidad, cupo)  # las de LinkedIn, que van aparte, no le quitan cupo al lote
    except Exception as e:  # noqa: BLE001 — sin esta cola, la comprobación sigue con la del lote, como antes
        from buscador import registro
        registro.aviso("verificar_enlaces:necesidad", e)
    antes = revisadas_n
    with medir("Comprobar enlaces: selección del día y resto", candidatas=len(vacantes)) as cifras:
        for _ronda in range(4):
            if revisadas_n >= maximo or time.monotonic() >= plazo:
                break
            disponibles = [v for v in vacantes if v["id"] not in revisadas or v["verificacion"]["estado"] == "verificada"]
            t0 = time.monotonic()
            # Con `contar_orden`, ordenar usa como mucho la mitad de lo que queda: la otra mitad es para abrir enlaces.
            limite = t0 + max(0, plazo - t0) / 2 if contar_orden else None
            candidatas = cola_de_seleccion(disponibles, entregadas, hoy, cache, iniciales, maximo - revisadas_n,
                                           limite=limite)
            if not contar_orden:
                plazo += time.monotonic() - t0  # el presupuesto de segundos es para comprobar enlaces, no para ordenar
            if incremental:
                recientes = sorted(vacantes, key=lambda v: v.get("publicada_en") or v.get("visto_primera_vez", ""), reverse=True)
                inicio = hora * maximo % len(recientes) if recientes else 0
                candidatas += recientes[:maximo // 2] + recientes[inicio:] + recientes[:inicio]
            grupo = list({v["id"]: v for v in candidatas if v["id"] not in revisadas}.values())
            from buscador import cobertura  # contrato v41: primero lo que le sirve a quien va corto (o es nuevo)
            grupo.sort(key=lambda v: not cobertura.sirve_a_corta(v))
            if not grupo:
                break
            n = auditar(grupo, cache, maximo=maximo - revisadas_n, segundos=max(0, plazo - time.monotonic()))
            revisadas_n += n
            revisadas.update(v["id"] for v in grupo if all(vigente(cache.get(u, {}), v["titulo"], datetime.now(timezone.utc)) for u in urls(v)))
            if incremental or n == 0:
                break
        cifras["abiertas"] = revisadas_n - antes
    for v in vacantes:
        anotar(v, cache)
    actuales = [dict(por_id.get(v["id"], v)) for lista in iniciales.values() for v, _ in lista]
    for v in actuales:
        anotar(v, cache)
    return dict(resumen(vacantes), candidatas_programadas=revisadas_n, por_necesidad=por_necesidad,
                seleccion_del_dia=resumen(actuales))


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # el JSON lleva tildes: en Windows la salida redirigida es cp1252
    p = argparse.ArgumentParser(description="Auditoría de solo lectura de un lote diario, sin Supabase ni Apify")
    p.add_argument("--lote", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--maximo", type=int, default=120)
    a = p.parse_args()
    lote = json.loads(Path(a.lote).read_text(encoding="utf-8"))
    vs = list({v["id"]: v for lista in lote["elegidas"].values() for v, _ in lista}.values())
    cache = {}
    auditar(vs, cache, maximo=a.maximo, segundos=240)
    Path(a.salida).write_text(json.dumps({"resumen": resumen(vs), "resultados": cache}, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(json.dumps(resumen(vs), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
