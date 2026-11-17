"""Servidor del operador. Demostración explícita; producción cerrada sin autenticación."""
import argparse
from collections import defaultdict, deque
import os
from pathlib import Path
import time
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import ValidationError
import requests

from buscador import paises
from buscador.fuentes.publicaciones_apify import PREFIJOS
from buscador import registro
from panel import servicio
from panel.modelos import AjusteOperador, BorrarCliente, ImportarClientes, CambioBorrador, Configuracion, Contacto, DecisionRevision, EstadoRegla, SubirRevision, Credenciales, EnVivo, Expansion, Guardar, Perfil, Publicar, VistaPrevia, explicar, parcial, solo_perfil
from panel.repositorio import ErrorRepositorio, RepositorioDemo, RepositorioSupabase, hoy
from panel.terminos import sugerir

RAIZ = Path(__file__).resolve().parent.parent
COOKIE_SESION, COOKIE_RENOVAR = "adaptia_session", "adaptia_renovar"
DIAS_RENOVACION = 30
# Hora estándar de países de fuera de la tabla propia donde suelen vivir clientes (EE. UU. y Canadá por la costa este).
UTC_FUERA = {"US": -5, "CA": -5, "GB": 0, "IE": 0, "PT": 0, "DE": 1, "FR": 1, "IT": 1, "NL": 1, "BE": 1, "CH": 1,
             "AT": 1, "AU": 10, "NZ": 12}


def _ciudades_por_pais():
    """{país: [ciudades]} con las principales de la tabla propia y las áreas metropolitanas (sin repetir)."""
    salida = {}
    for p in paises.datos()["paises"]:
        salida.setdefault(p["codigo"], []).extend(p.get("ciudades") or [])
    for ciudad, codigo in paises.areas_metropolitanas().items():
        salida.setdefault(codigo, []).append(ciudad)
    ruido = ("district", "distrito", "metropolitan", "metropolitana", "gran ", "greater", "caba", "area ")

    def limpias(nombres):
        unicas = sorted({x for x in nombres if len(x) > 2 and not any(r in x for r in ruido)}, key=len)
        # «bogota d c» sobra si ya está «bogota».
        return sorted(x.title() for i, x in enumerate(unicas) if not any(x.startswith(y + " ") for y in unicas[:i]))
    return {c: limpias(v)[:40] for c, v in salida.items()}


PREFIJOS_MOSTRAR = {"1": "US", "44": "GB", "49": "DE", "33": "FR", "39": "IT", "351": "PT", "55": "BR", "31": "NL",
                    "41": "CH", "353": "IE", "61": "AU", "1809": "DO", "1829": "DO", "1849": "DO", "1787": "PR"}


def a_v8(estado):
    """Perfiles guardados con el contrato v6 se muestran ya convertidos a v8 (país de residencia y modalidades)."""
    for cfg in (estado.get("borrador"), (estado.get("publicada") or {}).get("configuracion")):
        if isinstance(cfg, dict) and cfg.get("perfiles"):
            try:
                # Contrato v30: el formulario edita filas; las de un perfil anterior se le entregan ya armadas.
                validados = [Perfil.model_validate(p) for p in cfg["perfiles"]]
                cfg["perfiles"] = [dict(p.model_dump(mode="json"), ubicaciones=[f.model_dump(mode="json") for f in p.filas])
                                   for p in validados]
            except ValueError:
                pass  # se devuelve tal cual: el panel lo marcará como incompleto
    return estado


def crear_app(demo=False, repositorio=None, origen=None, operadores=None):
    app = FastAPI(title="Adaptia · Control de búsqueda", docs_url=None, redoc_url=None, openapi_url=None)
    origen = (origen or os.environ.get("PANEL_ORIGIN", "")).rstrip("/")
    operadores = operadores if operadores is not None else [x.strip().casefold() for x in os.environ.get("PANEL_OPERATOR_EMAILS", "").split(",") if x.strip()]
    if not demo and (not origen.startswith("https://") or not operadores):
        raise RuntimeError("El acceso real permanece cerrado: configura origen HTTPS y operador autorizado.")
    repo = repositorio or (RepositorioDemo(os.environ.get("PANEL_DEMO_FILE", "/tmp/adaptia-panel-demo/config.json")) if demo else RepositorioSupabase())
    intentos = defaultdict(deque)
    if not demo and hasattr(repo, "catalogo_vigente"):
        # Preparar la estimación al arrancar para que la primera visita no espere la lectura del catálogo.
        def precargar():
            try:
                repo.catalogo_vigente()
            except Exception as e:
                registro.aviso("api:50", e)
        import threading
        threading.Thread(target=precargar, daemon=True).start()
    app.state.repo, app.state.demo = repo, demo
    # Contrato v29: copias cortas en memoria. Cualquier escritura del panel (POST/PUT/PATCH/DELETE) sube el sello e
    # invalida los resultados guardados; la búsqueda nocturna corre en otro proceso y la cubre la vigencia de 2 min.
    sello = [0]
    copias_resultados, copias_fichas = {}, {}

    def _usuario(token):
        r = repo.sesion.get(repo.url + "/auth/v1/user", headers={**repo.cabeceras, "Authorization": "Bearer " + token},
                            timeout=15)
        return r.json() if r.status_code == 200 else {}

    def _autorizado(usuario):
        return usuario.get("email", "").casefold() in operadores and bool(usuario.get("email_confirmed_at"))

    def _renovar(renovacion):
        """Contrato v31: tokens nuevos de Supabase con el token de renovación, o None."""
        if not renovacion or len(renovacion) > 512:
            return None
        r = repo.sesion.post(repo.url + "/auth/v1/token", params={"grant_type": "refresh_token"},
                             headers=repo.cabeceras, json={"refresh_token": renovacion}, timeout=15)
        datos = r.json() if r.status_code == 200 else {}
        return datos if datos.get("access_token") and datos.get("refresh_token") else None

    def _poner_cookies(response, datos):
        response.set_cookie(COOKIE_SESION, datos["access_token"],
                            max_age=min(int(datos.get("expires_in", 3600)), 3600),
                            httponly=True, secure=True, samesite="strict", path="/")
        # Solo viaja a /api/ y nunca la lee el navegador; dura 30 días o hasta «Cerrar sesión».
        response.set_cookie(COOKIE_RENOVAR, datos["refresh_token"], max_age=DIAS_RENOVACION * 86400,
                            httponly=True, secure=True, samesite="strict", path="/api/")

    @app.middleware("http")
    async def proteccion(request: Request, siguiente):
        if request.url.path.startswith("/api/"):
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                esperado = str(request.base_url).rstrip("/") if demo else origen
                if request.headers.get("origin", "") != esperado:
                    return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
                try:
                    longitud = int(request.headers.get("content-length", "0"))
                except ValueError:
                    return JSONResponse({"detail": "Petición no válida."}, status_code=400)
                if longitud > 1_000_000:
                    return JSONResponse({"detail": "La petición es demasiado grande."}, status_code=413)
        publicas = {"/api/session", "/api/auth/login", "/api/auth/logout", "/api/health"}
        renovada = None
        if request.url.path.startswith("/api/") and not demo and request.url.path not in publicas:
            token = request.cookies.get(COOKIE_SESION, "")
            try:
                usuario = await run_in_threadpool(_usuario, token) if token else {}
                if not _autorizado(usuario):
                    # Contrato v31: la sesión no vence a la hora; se renueva sola con el token de renovación hasta
                    # «Cerrar sesión». El usuario renovado se vuelve a comprobar (operador y correo confirmado).
                    renovada = await run_in_threadpool(_renovar, request.cookies.get(COOKIE_RENOVAR, ""))
                    if not renovada or not _autorizado(renovada.get("user") or {}):
                        texto = "Inicia sesión para continuar." if not token else "Sesión vencida o acceso no autorizado."
                        return JSONResponse({"detail": texto}, status_code=401)
            except (requests.RequestException, ValueError):
                return JSONResponse({"detail": "No se pudo verificar la sesión."}, status_code=503)
        escribe = request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}
        sello[0] += escribe
        response = await siguiente(request)
        sello[0] += escribe
        if renovada:
            _poner_cookies(response, renovada)
        response.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
            "X-Frame-Options": "DENY", "Cache-Control": "no-store" if request.url.path.startswith("/api/") else "no-cache",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
        if not demo:  # OWASP ASVS 14.4.5 (PR 1.5): el navegador usa siempre HTTPS con el panel real
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(ErrorRepositorio)
    async def error_repo(_, exc):
        return JSONResponse({"detail": exc.mensaje}, status_code=exc.estado)

    @app.exception_handler(ValueError)
    async def error_datos(_, exc):
        # Excepciones de validación propias: no incluir datos completos ni mensajes SQL.
        mensaje = str(exc) if not isinstance(exc, ValidationError) else "Revisa los campos indicados."
        return JSONResponse({"detail": mensaje[:240]}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def error_peticion(_, exc):
        errores = [{"campo": ".".join(map(str, e["loc"][1:])), "mensaje": e["msg"].removeprefix("Value error, ")}
                   for e in exc.errors()]
        return JSONResponse({"detail": "Revisa la configuración.", "errores": errores}, status_code=422)

    @app.get("/api/health")
    def salud():
        return {"estado": "ok", "modo": "demostracion" if demo else "privado"}

    @app.get("/api/session")
    def session(request: Request):
        # Contrato v31: con solo el token de renovación la sesión sigue abierta; la próxima consulta la renueva.
        return {"demo": demo, "sesion": demo or bool(request.cookies.get(COOKIE_SESION) or request.cookies.get(COOKIE_RENOVAR)),
                "paises": [{"codigo": p["codigo"], "nombre": p["nombre"]} for p in paises.datos()["cubiertos"]],
                # Contrato v23: todos los países, para residencia, mudanza y permiso legal.
                "paises_mundo": [{"codigo": x["codigo"], "nombre": x["nombre"]} for x in paises.mundo()["lista"]],
                # Contrato v30: la bandera junto al WhatsApp (solo para mostrar; +1 se muestra como EE. UU.).
                "prefijos": {**PREFIJOS, **PREFIJOS_MOSTRAR},
                # PR 3 de la sesión de prueba (17 nov): ciudades principales por país (primero el país, luego la
                # ciudad) y la hora de cada país para decir «2 h menos que donde vive».
                "ciudades_por_pais": _ciudades_por_pais(),
                "utc_paises": {**UTC_FUERA, **paises.datos()["utc"]}}

    @app.post("/api/auth/login")
    async def login(request: Request, body: Credenciales):
        if demo:
            return {"demo": True}
        ip = request.client.host if request.client else "desconocido"
        ahora = time.monotonic()
        cola = intentos[ip]
        while cola and ahora - cola[0] > 900:
            cola.popleft()
        if len(cola) >= 8:
            raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
        cola.append(ahora)
        email, password = body.email.strip(), body.password
        if email.casefold() not in operadores or not 1 <= len(password) <= 256:
            raise HTTPException(401, "No se pudo iniciar sesión.")
        try:
            r = await run_in_threadpool(repo.sesion.post, repo.url + "/auth/v1/token", params={"grant_type": "password"},
                headers=repo.cabeceras, json={"email": email, "password": password}, timeout=20)
            datos = r.json()
            if r.status_code != 200 or not datos.get("access_token") or not (datos.get("user") or {}).get("email_confirmed_at"):
                raise HTTPException(401, "No se pudo iniciar sesión.")
        except (requests.RequestException, ValueError):
            raise HTTPException(503, "No se pudo verificar el acceso.") from None
        response = JSONResponse({"sesion": True})
        if datos.get("refresh_token"):
            _poner_cookies(response, datos)
        else:
            response.set_cookie(COOKIE_SESION, datos["access_token"], max_age=min(int(datos.get("expires_in", 3600)), 3600),
                                httponly=True, secure=True, samesite="strict", path="/")
        return response

    @app.post("/api/auth/logout")
    def logout(request: Request):
        anulada = True
        if not demo:
            # Contrato v31: también se anula la renovación en Supabase (todas las sesiones de ese usuario). Si el
            # acceso ya venció, primero se obtiene uno nuevo con la renovación para poder anularla.
            token = request.cookies.get(COOKIE_SESION, "")
            renovacion = request.cookies.get(COOKIE_RENOVAR, "")
            try:
                if renovacion and (not token or not _usuario(token)):
                    token = (_renovar(renovacion) or {}).get("access_token", "")
                if token:
                    r = repo.sesion.post(repo.url + "/auth/v1/logout", params={"scope": "global"},
                                         headers={**repo.cabeceras, "Authorization": "Bearer " + token}, timeout=10)
                    anulada = r.status_code in (200, 204)
                else:
                    anulada = not renovacion
            except (requests.RequestException, ValueError) as e:
                anulada = False
                registro.aviso("api:logout", e)
            if not anulada:
                registro.aviso("api:logout", RuntimeError("no se pudo anular la renovación en Supabase"))
        response = JSONResponse({"sesion": False, "anulada": anulada})
        response.delete_cookie(COOKIE_SESION, path="/", secure=not demo, httponly=True, samesite="strict")
        response.delete_cookie(COOKIE_RENOVAR, path="/api/", secure=not demo, httponly=True, samesite="strict")
        return response

    @app.get("/api/config")
    def config():
        return a_v8(repo.config())

    @app.put("/api/config")
    def guardar(body: Guardar):
        return repo.guardar(body.revision, body.configuracion.model_dump(mode="json"))

    # Importar clientes desde un CSV (15 nov): vista previa sin guardar, e importación todo o nada.
    @app.get("/api/clientes/plantilla.csv")
    def plantilla_clientes():
        from fastapi.responses import Response
        from panel import importar
        return Response(importar.plantilla(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="plantilla-clientes.csv"'})

    @app.post("/api/clientes/importar/previa")
    def previa_importar(body: ImportarClientes):
        from panel import importar
        r = importar.previa(repo.config()["borrador"], body.contenido, body.actuales)
        return {k: v for k, v in r.items() if k not in ("configuracion", "contactos", "_borrados")}

    @app.post("/api/clientes/importar")
    def importar_clientes(body: ImportarClientes):
        from panel import importar
        if body.revision is None:
            raise HTTPException(422, "Falta la revisión de la configuración.")
        r = importar.importar(repo, body.revision, body.contenido, body.actuales, body.confirmacion)
        return {**r, "estado": a_v8(repo.config())}

    @app.post("/api/clientes/{cliente_id}/borrar")
    def borrar_cliente(cliente_id: UUID, body: BorrarCliente):
        from panel import importar
        if body.confirmacion.strip().upper() != "BORRAR":
            raise HTTPException(422, "Escribe BORRAR para confirmar.")
        importar.borrar_cliente(repo, body.revision, str(cliente_id))
        return {"borrado": True, "estado": a_v8(repo.config())}

    @app.post("/api/config/publicar")
    def publicar(body: Publicar):
        return repo.publicar(body.revision)

    @app.post("/api/config/aplicar-hoy")
    def aplicar_hoy(body: Publicar):
        return repo.publicar_hoy(body.revision)

    @app.get("/api/yo")
    def yo(request: Request):
        """Sesión de prueba (17 nov): el nombre de quien inició sesión, para mostrarlo arriba. Solo a esa persona."""
        if demo:
            return {"nombre": "Operador de prueba", "correo": ""}
        token = request.cookies.get(COOKIE_SESION, "")
        try:
            u = _usuario(token) if token else {}
        except (requests.RequestException, ValueError):
            u = {}
        datos = u.get("user_metadata") or {}
        correo = u.get("email", "")
        nombre = datos.get("full_name") or datos.get("name") or correo.split("@")[0].replace(".", " ").title()
        return {"nombre": nombre, "correo": correo}

    @app.get("/api/cobertura")
    def ver_cobertura():
        """Contrato v37: cobertura por persona (panel privado)."""
        return servicio.cobertura(repo, hoy())

    @app.post("/api/cargos/expandir")
    def expandir(body: Expansion):
        return sugerir(body.cargo)

    @app.post("/api/cargos/funciones")
    def proponer_funciones(body: dict):
        # Contrato v25: el cargo tal como está en el borrador (nombre y términos); no guarda nada.
        cargo = {"nombre": str(body.get("nombre") or "")[:120],
                 "terminos_exactos": [str(x)[:120] for x in body.get("terminos_exactos") or []][:30],
                 "terminos_similares": [str(x)[:120] for x in body.get("terminos_similares") or []][:30],
                 "terminos_excluidos": [str(x)[:120] for x in body.get("terminos_excluidos") or []][:30]}
        if len(cargo["nombre"].strip()) < 2:
            raise HTTPException(422, "Escribe el nombre del cargo.")
        return servicio.proponer_funciones(repo, cargo)

    @app.post("/api/vista-previa")
    def vista_previa(body: VistaPrevia):
        try:
            cfg = Configuracion.model_validate(body.configuracion)
        except ValueError as e:  # incluye ValidationError: borrador a medio editar
            # Se estima lo que sí está completo; cada perfil pendiente dice qué le falta (sección 7a, 13 nov).
            cfg, incompletos = parcial(body.configuracion)
            if cfg is None:
                return {"incompleto": True, "motivo": explicar(e)}
            return {**servicio.vista_previa(repo, cfg), "incompletos": incompletos}
        return servicio.vista_previa(repo, cfg)

    @app.post("/api/estimacion-en-vivo")
    def en_vivo(body: EnVivo):
        # Solo el perfil, su cliente y su cargo: el resto del borrador puede estar a medio editar (sección 4, 13 nov).
        try:
            cfg = solo_perfil(body.configuracion, body.perfil_id)
        except ValueError as e:  # incluye ValidationError
            return {"incompleto": True, "motivo": explicar(e)}
        return servicio.estimacion_en_vivo(repo, cfg, body.perfil_id)

    @app.get("/api/contactos")
    def leer_contactos():
        return {c["cliente_id"]: {k: c.get(k) for k in ("telefono", "nombre_saludo", "consentimiento")}
                for c in repo.contactos()}

    @app.put("/api/contactos/{cliente_id}")
    def guardar_contacto(cliente_id: UUID, body: Contacto):
        return repo.guardar_contacto(str(cliente_id), body.model_dump())

    @app.delete("/api/contactos/{cliente_id}")
    def borrar_contacto(cliente_id: UUID):
        repo.borrar_contacto(str(cliente_id))
        return {"borrado": True}

    @app.get("/api/borradores")
    def leer_borradores(fecha: str | None = None):
        from panel import borradores as b
        fecha = fecha or hoy()
        contactos = {c["cliente_id"]: c for c in repo.contactos()}
        salida = []
        for x in repo.borradores(fecha=fecha):
            c = contactos.get(x["cliente_id"])
            salida.append({**x, "enlace": b.enlace_whatsapp(c["telefono"], x["texto"]) if c else "",
                           "pocas": len(x.get("vacantes", [])) < b.MINIMO})
        return {"fecha": fecha, "borradores": salida}

    # Contrato v31: el número del operador y «Mandarme todos a mi WhatsApp».
    @app.get("/api/ajustes/operador")
    def leer_operador():
        return {"telefono": (repo.ajuste("operador", {}) or {}).get("telefono", "")}

    @app.put("/api/ajustes/operador")
    def guardar_operador(body: AjusteOperador):
        repo.guardar_ajuste("operador", body.model_dump())
        return body.model_dump()

    @app.get("/api/borradores/para-mi")
    def borradores_para_mi(fecha: str | None = None):
        from panel import borradores as b
        if fecha:
            from datetime import date
            date.fromisoformat(fecha)
        return b.para_operador(repo, fecha)

    @app.post("/api/borradores/generar")
    def generar_borradores():
        from panel import borradores as b
        return b.generar(repo)

    @app.patch("/api/borradores/{borrador_id}")
    def cambiar_borrador(borrador_id: UUID, body: CambioBorrador):
        cambios = body.model_dump(exclude_none=True)
        if "texto" in cambios:
            cambios["editado"] = True
        return repo.actualizar_borrador(str(borrador_id), cambios)

    # Contrato v16: bandeja «Por confirmar».
    @app.get("/api/revisiones")
    def leer_revisiones(pagina: int | None = None, por_pagina: int = 25, cliente_id: str | None = None):
        from panel import revision
        if cliente_id:
            UUID(cliente_id)
        if pagina is not None and (pagina < 1 or not 1 <= por_pagina <= 100):
            raise HTTPException(422, "Página no válida.")
        return revision.listar(repo, hoy(), pagina=pagina, por_pagina=por_pagina, cliente_id=cliente_id)

    @app.post("/api/revisiones/cargar")
    def cargar_revisiones():
        from panel import revision
        return revision.iniciar_carga(repo, hoy())  # en segundo plano: el panel consulta el avance

    @app.get("/api/revisiones/cargar")
    def avance_revisiones():
        from panel import revision
        return revision.estado_carga()

    @app.get("/api/revisiones.csv")
    def descargar_revisiones():
        from fastapi.responses import Response
        from panel import revision
        return Response(revision.exportar_csv(repo, hoy()), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="por-confirmar-{hoy()}.csv"'})

    @app.get("/api/base.csv")
    def descargar_base(fecha: str | None = None, cliente: str | None = None, todo: bool = False):
        """CSV con el formato del contrato (reunión del 14 nov): general o de un cliente, de un día (hoy en Bogotá por
        defecto) o de toda la base."""
        import re
        from fastapi.responses import Response
        from panel import revision
        if fecha and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            raise HTTPException(422, "La fecha debe tener el formato AAAA-MM-DD.")
        if cliente:
            UUID(cliente)  # un id que no es UUID responde 422 por el manejador de errores de validación
        dia = fecha or hoy()
        texto, incluidas, omitidas, sin_fila = revision.exportar_base(repo, fecha=dia, cliente_id=cliente, todo=todo)
        nombre = "vacantes-" + ("base" if todo else dia) + ("-cliente" if cliente else "-todas") + ".csv"
        return Response(texto, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                                 "X-Incluidas": str(incluidas), "X-Omitidas-Sin-Confirmar": str(omitidas),
                                 "X-Sin-Fila": str(sin_fila)})

    @app.post("/api/revisiones/csv")
    def subir_revisiones(body: SubirRevision):
        from panel import revision
        comprobar = None
        if not demo:
            from buscador import verificar_enlaces
            comprobar = verificar_enlaces.comprobar
        return revision.importar_csv(repo, body.contenido, comprobar=comprobar)

    @app.get("/api/reglas")
    def leer_reglas():
        from panel import revision
        return revision.listar_reglas(repo)

    @app.post("/api/reglas/estado")
    def cambiar_regla(body: EstadoRegla):
        repo.actualizar_regla(body.texto, {"activa": body.activa})
        return {"texto": body.texto, "activa": body.activa}

    @app.post("/api/revisiones/{vacante_id}")
    def decidir_revision(vacante_id: str, body: DecisionRevision):
        from panel import revision
        if not 3 <= len(vacante_id) <= 80:
            raise HTTPException(422, "Vacante no reconocida.")
        comprobar = None
        if not demo:
            from buscador import verificar_enlaces
            comprobar = verificar_enlaces.comprobar
        return revision.decidir(repo, vacante_id, body.decision, body.paises, body.aplicar_a_iguales,
                                comprobar=comprobar)

    @app.get("/api/ejecuciones")
    def ejecuciones():
        return repo.ejecuciones()

    @app.get("/api/resumen-clientes")
    def resumen_clientes():
        return servicio.resumen_clientes(repo)

    @app.get("/api/resultados")
    def resultados(cliente_id: str | None = None, fecha: str | None = None):
        if cliente_id:
            from uuid import UUID
            UUID(cliente_id)
        if fecha:
            from datetime import date
            date.fromisoformat(fecha)
        clave, actual = (cliente_id or "", fecha or ""), sello[0]
        guardado = copias_resultados.get(clave)
        if guardado and guardado[0] == actual and time.monotonic() - guardado[1] < 120:
            return guardado[2]
        valor = servicio.resultados(repo, cliente_id, fecha)
        if len(copias_resultados) > 200:
            copias_resultados.clear()
        copias_resultados[clave] = (actual, time.monotonic(), valor)
        return valor

    @app.get("/api/vacantes/{vacante_id}/ficha")
    def ficha_vacante(vacante_id: str):
        """Contrato v29: la ficha completa de una vacante (descripción en bloques, sin HTML)."""
        if not 3 <= len(vacante_id) <= 80:
            raise HTTPException(422, "Vacante no reconocida.")
        guardada = copias_fichas.get(vacante_id)
        if guardada and time.monotonic() - guardada[0] < 600:
            return guardada[1]
        valor = servicio.ficha(repo, vacante_id, traer=not demo)
        if len(copias_fichas) > 500:
            copias_fichas.clear()
        copias_fichas[vacante_id] = (time.monotonic(), valor)
        return valor

    @app.get("/api/whatsapp/{cliente_id}")
    def whatsapp(cliente_id: str, fecha: str | None = None):
        from uuid import UUID
        UUID(cliente_id)
        if fecha:
            from datetime import date
            date.fromisoformat(fecha)
        return servicio.whatsapp(repo, cliente_id, fecha)

    dist = RAIZ / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="panel")
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Solo datos ficticios, sin Supabase ni secretos")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int,
                        help="Puerto; por defecto PORT del alojamiento (Render, etc.) o 8000")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(crear_app(demo=args.demo), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
