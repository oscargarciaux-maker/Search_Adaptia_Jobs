"""Persistencia: Supabase para producción, fichero ficticio aislado para demostración."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from threading import RLock
from uuid import NAMESPACE_DNS, uuid5
from zoneinfo import ZoneInfo

import requests

from buscador import supabase
from panel.modelos import Configuracion


def hoy():
    return datetime.now(ZoneInfo("America/Bogota")).date().isoformat()


class ErrorRepositorio(Exception):
    def __init__(self, mensaje="No se pudo confirmar la operación. Vuelve a intentarlo.", estado=503):
        self.mensaje, self.estado = mensaje, estado
        super().__init__(mensaje)


class RepositorioSupabase:
    def __init__(self, sesion=None):
        self.url, clave = supabase.credenciales()
        if not self.url or not clave:
            raise RuntimeError("Configura Supabase en el servidor; nunca en el navegador.")
        self.sesion = sesion or requests.Session()
        self.cabeceras = {"apikey": clave, "Content-Type": "application/json"}
        if clave.startswith("eyJ"):
            self.cabeceras["Authorization"] = "Bearer " + clave

    def pedir(self, metodo, ruta, **op):
        try:
            r = self.sesion.request(metodo, self.url + "/rest/v1/" + ruta, headers={**self.cabeceras, **(op.pop("headers", None) or {})}, timeout=45, **op)
            if r.status_code == 409 or r.status_code == 500 and r.json().get("code") == "40001":
                raise ErrorRepositorio("La configuración cambió en otra ventana. Recarga antes de guardar.", 409)
            if not 200 <= r.status_code < 300:
                raise ErrorRepositorio()
            return r.json() if r.content else None
        except (requests.RequestException, ValueError, AttributeError):
            raise ErrorRepositorio() from None

    def config(self):
        filas = self.pedir("GET", "panel_configuracion", params={"id": "eq.principal", "limit": 1})
        if not filas:
            filas = [{"id":"principal","revision":0,"borrador":{"clientes":[],"cargos":[],"perfiles":[]}}]
        versiones = self.pedir("GET", "panel_versiones", params={"order": "vigente_desde.desc,revision.desc", "limit": 1})
        return {**filas[0], "publicada": versiones[0] if versiones else None}

    def guardar(self, revision, configuracion):
        return self.pedir("POST", "rpc/panel_guardar", json={"p_revision": revision, "p_configuracion": configuracion})

    def publicar(self, revision):
        actual = self.config()
        if actual["revision"] != revision:
            raise ErrorRepositorio("La configuración cambió. Recarga antes de programar.", 409)
        Configuracion.model_validate(actual["borrador"]).validar_publicacion()
        return self.pedir("POST", "rpc/panel_publicar", json={"p_revision": revision})

    def operativa(self, fecha):
        filas = self.pedir("GET", "panel_versiones", params={"vigente_desde": "lte." + fecha, "order": "vigente_desde.desc,revision.desc", "limit": 1})
        return filas[0] if filas else None

    def ejecuciones(self):
        return self.pedir("GET", "panel_ejecuciones", params={"order": "fecha.desc", "limit": 30})

    def resultados(self, cliente_id, fecha=None):
        ejecuciones = self.pedir("GET", "panel_ejecuciones",
            params={**({"fecha": "eq." + fecha} if fecha else {}), "order": "fecha.desc", "limit": 1})
        if not ejecuciones:
            return {"ejecucion": None, "filas": [], "clientes": []}
        e = ejecuciones[0]
        versiones = self.pedir("GET", "panel_versiones", params={"revision": "eq." + str(e["revision"]), "limit": 1})
        cfg = versiones[0]["configuracion"]
        if not cliente_id:
            cliente_id = next((c["id"] for c in cfg["clientes"] if c["activo"]), "")
        filas = []
        if cliente_id:
            for inicio in range(0, 30000, 500):
                lote = self.pedir("GET", "panel_asignaciones", params={"ejecucion_id": "eq." + e["id"],
                    "cliente_id": "eq." + cliente_id, "select": "*,catalogo_vacantes(*)",
                    "order": "creada_en,id", "offset": inicio, "limit": 500})
                filas.extend(lote)
                if len(lote) < 500:
                    break
        return {"ejecucion": e, "filas": filas, "clientes": cfg["clientes"]}


def id_demo(nombre):
    return str(uuid5(NAMESPACE_DNS, "adaptia.demostracion." + nombre))


def configuracion_demo():
    cargos = [{"id": id_demo(n), "nombre": n, "cupo": q, "activo": True, "terminos_exactos": [n],
               "terminos_similares": ts, "terminos_excluidos": []}
              for n, q, ts in [("Product Designer", 50, ["UX Designer", "UI Designer", "Interaction Designer"]),
                               ("Frontend", 40, ["Frontend Developer", "Frontend Engineer", "Desarrollador Frontend"]),
                               ("QA", 30, ["QA Engineer", "Software Tester", "Analista de pruebas"])]]
    clientes = [{"id": id_demo("cliente" + str(i)), "nombre": "Cliente de ejemplo " + f"{i:02}",
                 "activo": True} for i in range(1, 6)]
    perfiles = []
    for i, c in enumerate(clientes):
        cargo = cargos[0 if i < 3 else i - 2]
        perfiles.append({"id": id_demo("perfil" + str(i)), "cliente_id": c["id"], "cargo_id": cargo["id"],
            "paises": ["CO"] if i != 1 else ["ES"], "modalidad": "remoto", "antiguedad_dias": 14,
            "idiomas": ["es", "en"], "ingles_maximo": "B2", "experiencia_min": 0, "experiencia_max": 5,
            "aceptar_experiencia_sin_dato": False, "aceptar_ingles_sin_dato": False, "activo": True})
    return Configuracion(clientes=clientes, cargos=cargos, perfiles=perfiles).model_dump(mode="json")


class RepositorioDemo:
    def __init__(self, archivo=None):
        self.archivo = Path(archivo) if archivo else None
        self.lock = RLock()
        self.estado = {"revision": 1, "borrador": configuracion_demo(), "publicada": None}
        if self.archivo and self.archivo.exists():
            self.estado = json.loads(self.archivo.read_text())
            Configuracion.model_validate(self.estado["borrador"])
        self.creada = datetime.now(timezone.utc)

    def config(self):
        with self.lock:
            return deepcopy(self.estado)

    def _guardar(self):
        if self.archivo:
            self.archivo.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.archivo.with_suffix(".partial")
            tmp.write_text(json.dumps(self.estado, ensure_ascii=False))
            os.chmod(tmp, 0o600)
            tmp.replace(self.archivo)

    def guardar(self, revision, configuracion):
        cfg = Configuracion.model_validate(configuracion)
        with self.lock:
            if revision != self.estado["revision"]:
                raise ErrorRepositorio("La configuración cambió. Recarga antes de guardar.", 409)
            self.estado.update(revision=revision + 1, borrador=cfg.model_dump(mode="json"))
            self._guardar()
            return self.config()

    def publicar(self, revision):
        with self.lock:
            if revision != self.estado["revision"]:
                raise ErrorRepositorio("La configuración cambió. Recarga antes de programar.", 409)
            Configuracion.model_validate(self.estado["borrador"]).validar_publicacion()
            if self.estado["publicada"] and self.estado["publicada"]["revision"] == revision:
                return {k:self.estado["publicada"][k] for k in ("revision","vigente_desde")}
            manana = (datetime.fromisoformat(hoy()) + timedelta(days=1)).date().isoformat()
            self.estado["publicada"] = {"revision": revision, "vigente_desde": manana,
                                        "configuracion": deepcopy(self.estado["borrador"])}
            self._guardar()
            return {"revision": revision, "vigente_desde": manana}

    def ejecuciones(self):
        return [{"id": id_demo("ejecucion"), "fecha": hoy(), "revision": 1, "estado": "completa",
                 "iniciada_en": self.creada.isoformat(), "terminada_en": self.creada.isoformat(),
                 "resumen": {"vacantes": 120, "meta": 120, "por_cargo": {"Product Designer": 50, "Frontend": 40, "QA": 30}}}]

    def resultados(self, cliente_id, fecha=None):
        from panel.afinidad import evaluar
        # La muestra es fija; editar hoy no altera los resultados de una captura anterior.
        cfg = configuracion_demo()
        cliente_id = cliente_id or cfg["clientes"][0]["id"]
        filas = []
        for p in cfg["perfiles"]:
            if p["cliente_id"] != cliente_id:
                continue
            cargo = next(c for c in cfg["cargos"] if c["id"] == p["cargo_id"])
            for n in range(cargo["cupo"]):
                identificador = uuid5(NAMESPACE_DNS, cargo["id"] + str(n)).hex[:16]
                url = "https://example.org/empleos/" + identificador
                dias = n % 10
                publicada = (datetime.fromisoformat(hoy()) - timedelta(days=dias)).date().isoformat()
                titulo = ({"Product Designer": ["Product Designer", "UX Designer", "Interaction Designer"],
                           "Frontend": ["Frontend Developer", "Frontend Engineer", "Desarrollador Frontend"],
                           "QA": ["QA Engineer", "Software Tester", "Analista de pruebas"]}[cargo["nombre"]])[n % 3]
                v = {"id": identificador, "titulo": titulo, "empresa": ["Estudio Norte", "Orbita", "Forma", "Nexo", "Lumen"][n % 5],
                     "ubicacion": "Remote - Worldwide", "paises": ["CO", "ES"], "confianza_pais": "alta",
                     "modalidad": "remoto", "idioma": "en" if n % 2 else "es", "fecha_publicacion": publicada,
                     "fecha_estimada": False, "anos_min": n % 5, "ingles": "intermedio",
                     "_descripcion": (f"English B2 required. We require {n % 5} years of experience. We build digital products with a collaborative team. " * 5),
                     "enlace": url, "enlace_directo": "", "enlaces_alternativos": [url],
                     "verificacion": {"estado": "verificada", "enlaces": [{"url": url, "estado": "verificada",
                        "comprobada_en": self.creada.isoformat()}]}}
                coincidencia = evaluar(v, p, hoy())
                if coincidencia["compatible"]:
                    filas.append({"id": id_demo(p["id"] + identificador), "cliente_id": cliente_id,
                        "perfil_id": p["id"], "cargo_id": cargo["id"], "vacante_id": identificador,
                        "match_grade": "exact" if n % 3 == 0 else "similar",
                        "explicacion": coincidencia["pruebas"], "filtros": p, "cargo_configuracion": cargo,
                        "catalogo_vacantes": {"id": identificador, "status": "active", "datos": v,
                                             "description_full": v["_descripcion"]}})
        return {"ejecucion": self.ejecuciones()[0], "filas": filas, "clientes": cfg["clientes"]}
