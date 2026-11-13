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
from panel import servicio
from panel.modelos import AjustesAlertas, CambioBorrador, Configuracion, Contacto, DecisionRevision, EstadoRegla, SubirRevision, Credenciales, EnVivo, Expansion, Guardar, Perfil, Publicar, VistaPrevia, explicar, parcial, solo_perfil
from panel.repositorio import ErrorRepositorio, RepositorioDemo, RepositorioSupabase, hoy
from panel.terminos import sugerir

RAIZ = Path(__file__).resolve().parent.parent


def a_v8(estado):
    """Perfiles guardados con el contrato v6 se muestran ya convertidos a v8 (país de residencia y modalidades)."""
    for cfg in (estado.get("borrador"), (estado.get("publicada") or {}).get("configuracion")):
        if isinstance(cfg, dict) and cfg.get("perfiles"):
            try:
                cfg["perfiles"] = [Perfil.model_validate(p).model_dump(mode="json") for p in cfg["perfiles"]]
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
            except Exception:
                pass
        import threading
        threading.Thread(target=precargar, daemon=True).start()
    app.state.repo, app.state.demo = repo, demo

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
            if not demo and request.url.path not in publicas:
                token = request.cookies.get("adaptia_session", "")
                if not token:
                    return JSONResponse({"detail": "Inicia sesión para continuar."}, status_code=401)
                try:
                    r = await run_in_threadpool(repo.sesion.get, repo.url + "/auth/v1/user", headers={**repo.cabeceras, "Authorization": "Bearer " + token}, timeout=15)
                    usuario = r.json() if r.status_code == 200 else {}
                    if usuario.get("email", "").casefold() not in operadores or not usuario.get("email_confirmed_at"):
                        return JSONResponse({"detail": "Sesión vencida o acceso no autorizado."}, status_code=401)
                except (requests.RequestException, ValueError):
                    return JSONResponse({"detail": "No se pudo verificar la sesión."}, status_code=503)
        response = await siguiente(request)
        response.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
            "X-Frame-Options": "DENY", "Cache-Control": "no-store" if request.url.path.startswith("/api/") else "no-cache",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
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
        return {"demo": demo, "sesion": demo or bool(request.cookies.get("adaptia_session")),
                "paises": [{"codigo": p["codigo"], "nombre": p["nombre"]} for p in paises.datos()["cubiertos"]]}

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
        response.set_cookie("adaptia_session", datos["access_token"], max_age=min(int(datos.get("expires_in", 3600)), 3600),
                            httponly=True, secure=True, samesite="strict", path="/")
        return response

    @app.post("/api/auth/logout")
    def logout():
        response = JSONResponse({"sesion": False})
        response.delete_cookie("adaptia_session", path="/", secure=not demo, httponly=True, samesite="strict")
        return response

    @app.get("/api/config")
    def config():
        return a_v8(repo.config())

    @app.put("/api/config")
    def guardar(body: Guardar):
        return repo.guardar(body.revision, body.configuracion.model_dump(mode="json"))

    @app.post("/api/config/publicar")
    def publicar(body: Publicar):
        return repo.publicar(body.revision)

    @app.post("/api/cargos/expandir")
    def expandir(body: Expansion):
        return sugerir(body.cargo)

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

    @app.get("/api/ajustes/alertas")
    def leer_alertas():
        valor = AjustesAlertas.model_validate(repo.ajuste("alertas", {}) or {}).model_dump()
        return {**valor, "envio_configurado": demo or bool(os.environ.get("RESEND_API_KEY") and
                                                             os.environ.get("ALERTAS_REMITENTE"))}

    @app.put("/api/ajustes/alertas")
    def guardar_alertas(body: AjustesAlertas):
        return repo.guardar_ajuste("alertas", body.model_dump())

    @app.post("/api/alertas/prueba")
    def probar_alertas():
        from buscador import alertas
        destinatarios = AjustesAlertas.model_validate(repo.ajuste("alertas", {}) or {}).destinatarios
        if not destinatarios:
            raise HTTPException(422, "Guarda al menos un correo antes de probar.")
        if demo:
            return {"enviado": False, "nota": "Demostración: no se envía ningún correo."}
        ok = alertas.enviar(destinatarios, "Adaptia · correo de prueba",
                            "<p>Las alertas de búsqueda llegarán a este correo.</p>",
                            "Las alertas de búsqueda llegarán a este correo.")
        if not ok:
            raise HTTPException(503, "No se pudo enviar: revisa RESEND_API_KEY y ALERTAS_REMITENTE en el alojamiento.")
        return {"enviado": True, "nota": f"Correo de prueba enviado a {len(destinatarios)} destinatario(s)."}

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
    def leer_revisiones():
        from panel import revision
        return revision.listar(repo, hoy())

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
    def descargar_base():
        from fastapi.responses import Response
        from panel import revision
        texto, incluidas, omitidas = revision.exportar_base(repo)
        return Response(texto, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="base-vacantes-{hoy()}.csv"',
                                 "X-Incluidas": str(incluidas), "X-Omitidas-Sin-Confirmar": str(omitidas)})

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

    @app.get("/api/resultados")
    def resultados(cliente_id: str | None = None, fecha: str | None = None):
        if cliente_id:
            from uuid import UUID
            UUID(cliente_id)
        if fecha:
            from datetime import date
            date.fromisoformat(fecha)
        return servicio.resultados(repo, cliente_id, fecha)

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
