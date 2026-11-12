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
from threading import BoundedSemaphore
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
    r"(?:esta )?(?:vacante|oferta) (?:ha sido cerrada|ya no está disponible)|vaga (?:encerrada|não está mais disponível)", re.I)
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
_APLICAR = re.compile(r"^(?:apply(?: now| for (?:this )?(?:job|position))?|postular(?:me)?|aplicar(?: ahora)?|"
                       r"candidatar(?:-se)?|inscrever-se|solicitar (?:este )?empleo)$", re.I)


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
        while True:
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
                destino = siguiente
                continue
            return resultado(estado, motivo)
    except (requests.RequestException, ValueError, OSError):
        return resultado("pendiente", "error de conexión o URL no comprobable")
    finally:
        if propia:
            sesion.close()


def urls(v):
    return list(dict.fromkeys(u for u in (v.get("enlace"), v.get("enlace_directo")) if u))


def vigente(r, titulo, ahora):
    try:
        edad = (ahora - datetime.fromisoformat(r["comprobada_en"].replace("Z", "+00:00"))).total_seconds()
        return r.get("_titulo") == titulo and 0 <= edad < (1800 if r["estado"] == "pendiente" else 21600)
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


def auditar(vacantes, cache, *, maximo=240, segundos=240, hilos=6, comprobar_url=None, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    comprobar_url = comprobar_url or comprobar
    plazo = time.monotonic() + segundos
    escogidas, peticiones = [], {}
    for v in vacantes:
        pendientes = [u for u in urls(v) if not vigente(cache.get(u, {}), v["titulo"], ahora)]
        if pendientes and len(escogidas) < maximo:
            escogidas.append(v)
            for u in pendientes:
                peticiones.setdefault((u, v["titulo"]), None)
    semaforos = {enlaces.host(u): BoundedSemaphore(2) for u, _ in peticiones}
    def tarea(clave):
        u, titulo = clave
        if time.monotonic() >= plazo:
            return None
        semaforo = semaforos[enlaces.host(u)]
        if not semaforo.acquire(timeout=max(0, plazo - time.monotonic())):
            return None
        try:
            return comprobar_url(u, titulo, ahora=ahora, plazo=plazo)
        finally:
            semaforo.release()
    with ThreadPoolExecutor(hilos) as ex:
        futuros = {ex.submit(tarea, clave): clave for clave in peticiones}
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


def preparar(vacantes, entregadas, hoy, cache, *, lote=None, incremental=False, cfg=None):
    """Comprueba candidatas antes de la selección; lo no revisado nunca se da por aprobado."""
    from buscador import entrega
    cfg = cfg or {}
    maximo = cfg.get("vacantes_por_captura", 40) if incremental else cfg.get("vacantes_por_corrida", 300)
    segundos = cfg.get("segundos_captura", 90) if incremental else cfg.get("segundos_corrida", 240)
    plazo = time.monotonic() + segundos
    for v in vacantes:
        anotar(v, cache)
    por_id = {v["id"]: v for v in vacantes}
    iniciales = (lote or {}).get("elegidas", {}) if (lote or {}).get("fecha") == hoy else {}
    historicas = [por_id.get(v["id"], dict(v)) for lista in iniciales.values() for v, _ in lista]
    ids_iniciales = {v["id"] for lista in iniciales.values() for v, _ in lista}
    hora = datetime.now(timezone.utc).hour
    if incremental and historicas:
        inicio = hora * maximo % len(historicas)
        historicas = historicas[inicio:] + historicas[:inicio]
    revisadas = set()
    revisadas_n = 0
    for ronda in range(4):
        disponibles = [v for v in vacantes if v["id"] not in revisadas or v["verificacion"]["estado"] == "verificada"]
        seleccion, _ = entrega.elegir(disponibles, entregadas, hoy, iniciales=iniciales, omitir_verificacion=True)
        # `elegir` devuelve también los objetos del lote ya registrado: se auditan solo sus copias (`historicas`) para
        # no reescribir el snapshot canónico, que Supabase exige intacto al completar el día.
        candidatas = [v for lista in seleccion.values() for v, _ in lista if v["id"] not in ids_iniciales]
        if incremental:
            recientes = sorted(vacantes, key=lambda v: v.get("publicada_en") or v.get("visto_primera_vez", ""), reverse=True)
            inicio = hora * maximo % len(recientes) if recientes else 0
            candidatas += recientes[:maximo // 2] + recientes[inicio:] + recientes[:inicio]
        grupo = list({v["id"]: v for v in historicas + candidatas if v["id"] not in revisadas}.values())
        if not grupo or revisadas_n >= maximo or time.monotonic() >= plazo:
            break
        n = auditar(grupo, cache, maximo=maximo - revisadas_n, segundos=max(0, plazo - time.monotonic()))
        revisadas_n += n
        revisadas.update(v["id"] for v in grupo if all(vigente(cache.get(u, {}), v["titulo"], datetime.now(timezone.utc)) for u in urls(v)))
        if incremental or n == 0:
            break
    for v in vacantes:
        anotar(v, cache)
    actuales = [por_id.get(v["id"], v) for v in historicas]
    for v in actuales:
        anotar(v, cache)
    return dict(resumen(vacantes), candidatas_programadas=revisadas_n, seleccion_del_dia=resumen(actuales))


def main():
    p = argparse.ArgumentParser(description="Auditoría de solo lectura de un lote diario, sin Supabase ni Apify")
    p.add_argument("--lote", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--maximo", type=int, default=120)
    a = p.parse_args()
    lote = json.loads(Path(a.lote).read_text())
    vs = list({v["id"]: v for lista in lote["elegidas"].values() for v, _ in lista}.values())
    cache = {}
    auditar(vs, cache, maximo=a.maximo, segundos=240)
    Path(a.salida).write_text(json.dumps({"resumen": resumen(vs), "resultados": cache}, ensure_ascii=False, indent=2))
    print(json.dumps(resumen(vs), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
