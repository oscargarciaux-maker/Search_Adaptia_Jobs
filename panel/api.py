"""Servidor del operador. Demostración explícita; producción cerrada sin autenticación."""
import argparse
from collections import defaultdict, deque
import os
from pathlib import Path
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import ValidationError
import requests

from buscador import paises
from panel import servicio
from panel.modelos import Credenciales, Expansion, Guardar, Publicar
from panel.repositorio import ErrorRepositorio, RepositorioDemo, RepositorioSupabase
from panel.terminos import sugerir

RAIZ = Path(__file__).resolve().parent.parent


def crear_app(demo=False, repositorio=None, origen=None, operadores=None):
    app = FastAPI(title="Adaptia · Control de búsqueda", docs_url=None, redoc_url=None, openapi_url=None)
    origen = (origen or os.environ.get("PANEL_ORIGIN", "")).rstrip("/")
    operadores = operadores if operadores is not None else [x.strip().casefold() for x in os.environ.get("PANEL_OPERATOR_EMAILS", "").split(",") if x.strip()]
    if not demo and (not origen.startswith("https://") or not operadores):
        raise RuntimeError("El acceso real permanece cerrado: configura origen HTTPS y operador autorizado.")
    repo = repositorio or (RepositorioDemo(os.environ.get("PANEL_DEMO_FILE", "/tmp/adaptia-panel-demo/config.json")) if demo else RepositorioSupabase())
    intentos = defaultdict(deque)
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
                "paises": [{"codigo": p["codigo"], "nombre": p["nombre"]} for p in paises.datos()["paises"]]}

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
        return repo.config()

    @app.put("/api/config")
    def guardar(body: Guardar):
        return repo.guardar(body.revision, body.configuracion.model_dump(mode="json"))

    @app.post("/api/config/publicar")
    def publicar(body: Publicar):
        return repo.publicar(body.revision)

    @app.post("/api/cargos/expandir")
    def expandir(body: Expansion):
        return sugerir(body.cargo)

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
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(crear_app(demo=args.demo), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
