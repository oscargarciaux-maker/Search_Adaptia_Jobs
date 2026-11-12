"""Persistencia: Supabase para producción, fichero ficticio aislado para demostración."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
from threading import Lock, RLock, Thread
import time
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
        self._catalogo, self._lock_catalogo, self._lock_carga, self._refrescando = None, Lock(), Lock(), False

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

    def ajuste(self, clave, defecto=None):
        filas = self.pedir("GET", "panel_ajustes", params={"clave": "eq." + clave, "select": "valor", "limit": 1})
        return filas[0]["valor"] if filas else defecto

    def guardar_ajuste(self, clave, valor):
        self.pedir("POST", "panel_ajustes", params={"on_conflict": "clave"},
                   headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                   json={"clave": clave, "valor": valor, "actualizado_en": datetime.now(timezone.utc).isoformat()})
        return valor

    # Contrato v10: contactos de WhatsApp y borradores diarios (tablas privadas, solo credencial de servicio).
    def contactos(self):
        return self.pedir("GET", "panel_contactos", params={"select": "*", "limit": 1000}) or []

    def guardar_contacto(self, cliente_id, datos):
        fila = {"cliente_id": cliente_id, **datos, "actualizado_en": datetime.now(timezone.utc).isoformat()}
        self.pedir("POST", "panel_contactos", params={"on_conflict": "cliente_id"},
                   headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, json=fila)
        return fila

    def borrar_contacto(self, cliente_id):
        self.pedir("DELETE", "panel_contactos", params={"cliente_id": "eq." + cliente_id})

    def borradores(self, fecha=None, cliente_id=None):
        params = {"select": "*", "order": "fecha.desc,creado_en.desc", "limit": 500}
        if fecha:
            params["fecha"] = "eq." + fecha
        if cliente_id:
            params["cliente_id"] = "eq." + cliente_id
        return self.pedir("GET", "panel_borradores", params=params) or []

    def guardar_borrador(self, b):
        fila = {**b, "actualizado_en": datetime.now(timezone.utc).isoformat()}
        self.pedir("POST", "panel_borradores", params={"on_conflict": "fecha,cliente_id"},
                   headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, json=fila)
        return fila

    def actualizar_borrador(self, borrador_id, cambios):
        filas = self.pedir("PATCH", "panel_borradores", params={"id": "eq." + borrador_id},
                           headers={"Prefer": "return=representation"},
                           json={**cambios, "actualizado_en": datetime.now(timezone.utc).isoformat()})
        if not filas:
            raise ErrorRepositorio("Ese mensaje ya no existe. Recarga la lista.", 404)
        return filas[0]

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

    def _paginas(self, ruta, clave, params, tamano=500):
        ultimo = ""
        while True:
            lote = self.pedir("GET", ruta, params={**params, "order": clave, "limit": tamano,
                                                    **({clave: "gt." + ultimo} if ultimo else {})})
            yield from lote
            if len(lote) < tamano:
                return
            ultimo = lote[-1][clave]

    # Solo los campos que usan los filtros, leídos dentro de `datos`: ~1 MB en vez de descargar descripciones completas.
    CAMPOS_ESTIMACION = ("id,titulo:datos->>titulo,paises:datos->paises,confianza_pais:datos->>confianza_pais,"
        "modalidad:datos->>modalidad,idioma:datos->>idioma,publicada_en:datos->>publicada_en,"
        "fecha_publicacion:datos->>fecha_publicacion,fecha_estimada:datos->fecha_estimada,"
        "ids_agrupados:datos->ids_agrupados,anos_min:datos->anos_min,ingles:datos->>ingles,"
        "requisito_ingles:datos->requisito_ingles,duplicada_de:datos->>duplicada_de,"
        "verificacion:datos->verificacion->>estado,tipo:datos->>tipo")

    def _leer_catalogo(self):
        from panel.afinidad import ligera
        entregadas = {f["vacante_id"] for f in self._paginas("entregas_diarias", "vacante_id",
                                                             {"select": "vacante_id"}, 1000)}
        vacantes = []
        for d in self._paginas("catalogo_vacantes", "id", {"status": "eq.active", "select": self.CAMPOS_ESTIMACION}, 1000):
            if d.get("duplicada_de") or d.get("verificacion") == "rechazada" or d.get("tipo") == "post":
                continue  # un post (contrato v11) no es una vacante formal: no cuenta para estimar
            if {d["id"], *(d.get("ids_agrupados") or [])} & entregadas:
                continue
            vacantes.append(ligera(d))
        return {"vacantes": vacantes, "entregadas": entregadas,
                "actualizado": datetime.now(timezone.utc).isoformat(timespec="minutes")}

    def _refrescar(self):
        with self._lock_carga:  # una sola lectura a la vez; quien llega después usa el resultado
            try:
                actual = self._catalogo
                if actual and time.monotonic() - actual[0] < 60:
                    return actual[1]
                resultado = self._leer_catalogo()
                self._catalogo = (time.monotonic(), resultado)
                return resultado
            finally:
                self._refrescando = False

    def catalogo_vigente(self, vigencia=1800):
        """Vacantes activas, sin copias, sin enlaces rechazados y nunca entregadas; reducidas a lo que usan los filtros.
        Solo la primera lectura hace esperar: después se responde con la copia en memoria y, si tiene más de `vigencia`
        segundos, se renueva en segundo plano."""
        with self._lock_catalogo:
            actual = self._catalogo
            if actual and time.monotonic() - actual[0] >= vigencia and not self._refrescando:
                self._refrescando = True
                Thread(target=self._refrescar_silencioso, daemon=True).start()
        return actual[1] if actual else self._refrescar()

    def _refrescar_silencioso(self):
        try:
            self._refrescar()
        except Exception:  # se conserva la copia anterior; el siguiente uso lo reintenta
            pass

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
            "vive_en": "CO" if i != 1 else "ES", "modalidades": ["remoto"], "antiguedad_dias": 14,
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

    def ajuste(self, clave, defecto=None):
        with self.lock:
            return deepcopy(self.estado.get("ajustes", {}).get(clave, defecto))

    def guardar_ajuste(self, clave, valor):
        with self.lock:
            self.estado.setdefault("ajustes", {})[clave] = deepcopy(valor)
            self._guardar()
        return valor

    def contactos(self):
        with self.lock:
            if "contactos" not in self.estado:  # números ficticios para la demostración
                self.estado["contactos"] = {c["id"]: {"cliente_id": c["id"], "telefono": f"+5730000000{i:02}",
                                                      "nombre_saludo": ("Ana", "Luis", "Marta", "", "")[i],
                                                      "consentimiento": i < 3}
                                            for i, c in enumerate(configuracion_demo()["clientes"])}
            return deepcopy(list(self.estado["contactos"].values()))

    def guardar_contacto(self, cliente_id, datos):
        self.contactos()
        with self.lock:
            self.estado["contactos"][cliente_id] = {"cliente_id": cliente_id, **datos}
            self._guardar()
            return deepcopy(self.estado["contactos"][cliente_id])

    def borrar_contacto(self, cliente_id):
        self.contactos()
        with self.lock:
            self.estado["contactos"].pop(cliente_id, None)
            self._guardar()

    def borradores(self, fecha=None, cliente_id=None):
        with self.lock:
            return deepcopy([b for b in self.estado.get("borradores", [])
                             if (not fecha or b["fecha"] == fecha) and (not cliente_id or b["cliente_id"] == cliente_id)])

    def guardar_borrador(self, b):
        with self.lock:
            lista = self.estado.setdefault("borradores", [])
            previo = next((x for x in lista if x["fecha"] == b["fecha"] and x["cliente_id"] == b["cliente_id"]), None)
            fila = {**(previo or {"id": str(uuid5(NAMESPACE_DNS, "borrador" + b["fecha"] + b["cliente_id"]))}), **b}
            if previo:
                lista[lista.index(previo)] = fila
            else:
                lista.append(fila)
            self._guardar()
            return deepcopy(fila)

    def actualizar_borrador(self, borrador_id, cambios):
        with self.lock:
            for b in self.estado.get("borradores", []):
                if b["id"] == borrador_id:
                    b.update(cambios)
                    self._guardar()
                    return deepcopy(b)
        raise ErrorRepositorio("Ese mensaje ya no existe. Recarga la lista.", 404)

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

    def catalogo_vigente(self):
        """Catálogo ficticio estable con proporciones parecidas a las reales: pocos avisos dicen años o nivel de inglés."""
        from panel.afinidad import ligera
        if getattr(self, "_catalogo", None):
            return self._catalogo
        azar = random.Random(20261109)
        titulos = ["Product Designer", "UX Designer", "UI Designer", "Interaction Designer", "Senior Product Designer",
                   "Frontend Developer", "Frontend Engineer", "Desarrollador Frontend", "QA Engineer",
                   "Software Tester", "Analista de pruebas", "QA Automation Engineer", "Data Analyst",
                   "Backend Engineer", "Product Manager", "Editor de video", "Community Manager", "DevOps Engineer"]
        grupos = [["CO"], ["MX"], ["ES"], ["AR", "CL", "CO", "MX", "PE"], ["CO", "ES", "MX"], ["BR"]]
        base = datetime.fromisoformat(hoy())
        vacantes = []
        for n in range(900):
            anos = azar.choice([1, 2, 3, 4, 5, 6, 8]) if azar.random() < 0.26 else None
            nivel = azar.choice(["B1", "B2", "C1"]) if azar.random() < 0.12 else ""
            texto = (f"English {nivel} " + ("is a plus." if azar.random() < 0.3 else "required.")) if nivel else ""
            datos = {"id": uuid5(NAMESPACE_DNS, "adaptia.demo.catalogo." + str(n)).hex[:16],
                     "titulo": azar.choice(titulos), "paises": azar.choice(grupos),
                     "confianza_pais": azar.choice(["alta", "alta", "media", "baja"]),
                     "modalidad": azar.choice(["remoto", "remoto", "hibrido", "presencial"]),
                     "idioma": azar.choice(["es", "en", "en"]), "fecha_estimada": azar.random() < 0.1,
                     "fecha_publicacion": (base - timedelta(days=azar.randint(0, 29))).date().isoformat(),
                     "anos_min": anos, "ingles": ""}
            vacantes.append(ligera(datos, texto))
        self._catalogo = {"vacantes": vacantes, "actualizado": self.creada.isoformat(timespec="minutes")}
        return self._catalogo

    def fuentes_en_vivo(self, cargo, perfil, limite_segundos):
        """Demostración: avisos ficticios en vez de consultar LinkedIn o Get on Board (no sale a internet)."""
        azar = random.Random(cargo["nombre"] + perfil.vive_en + ",".join(perfil.modalidades))
        lugares = ["Remote - LATAM", "Remote - Worldwide", "Remoto, " + perfil.vive_en, "Remote - Brazil",
                   "Madrid, Spain", "Ciudad de México, México", "Bogotá, Colombia", "Remote - United States"]
        terminos = [cargo["nombre"], *cargo["terminos_exactos"], *cargo["terminos_similares"]][:4]
        crudas = []
        for n in range(azar.randint(18, 34)):
            descripcion = ("We require %d years of experience. " % azar.randint(1, 7) if azar.random() < 0.3 else "")
            descripcion += ("English B2 required. " if azar.random() < 0.15 else "") + "Equipo de producto digital. " * 3
            crudas.append({"titulo": azar.choice(terminos), "empresa": "Empresa ficticia %02d" % n,
                           "ubicacion": azar.choice(lugares), "descripcion": descripcion,
                           "fecha": (datetime.fromisoformat(hoy()) - timedelta(days=azar.randint(0, 25))).date().isoformat(),
                           "enlace": "https://www.linkedin.com/jobs/view/%d" % (4000000000 + azar.randint(0, 10**8)),
                           "remoto": True if azar.random() < 0.5 else None, "fuente": "Demostración"})
        return crudas, {"Demostración": {"avisos": len(crudas), "busquedas": 0, "fallidas": 0}}

    def ejecuciones(self):
        return [{"id": id_demo("ejecucion"), "fecha": hoy(), "revision": 1, "estado": "completa",
                 "iniciada_en": self.creada.isoformat(), "terminada_en": self.creada.isoformat(),
                 "resumen": {"vacantes": 120, "meta": 120, "por_cargo": {"Product Designer": 50, "Frontend": 40, "QA": 30},
                             "embudo": {n: {"encontradas": e, "con_descripcion": e * 6 // 10, "entregables": e // 2,
                                            "nuevas": e * 4 // 10, "enlace_comprobado": c + 12, "cumplen_filtros": c + 4,
                                            "entregadas": c, "ampliadas": 0,
                                            "principal_perdida": "sin descripción completa (no se sabe el idioma)"}
                                        for n, e, c in (("Product Designer", 840, 50), ("Frontend", 610, 40), ("QA", 520, 30))}}}]

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
            if cargo["nombre"] == "QA":
                # Contrato v11: un post ficticio para ver la etiqueta «Post» en la demostración. En producción solo
                # llega a perfiles con menos de 5 vacantes, así que el mensaje de WhatsApp de este perfil no lo incluye.
                url = "https://www.linkedin.com/posts/ejemplo_hiring-qa-activity-7000000000000000001"
                texto = ("Estamos contratando QA Engineer para trabajar remoto desde Colombia. Pruebas manuales y "
                         "automatizadas. Si te interesa, escríbeme por mensaje o envía tu CV.")
                v = {"id": "post-demo-qa", "tipo": "post", "titulo": "QA Engineer", "empresa": "Lumen",
                     "contacto": {"perfil": "https://www.linkedin.com/in/ejemplo"}, "ubicacion": "Colombia",
                     "paises": ["CO"], "confianza_pais": "alta", "modalidad": "remoto", "idioma": "es",
                     "fecha_publicacion": hoy(), "fecha_estimada": False, "anos_min": None, "_descripcion": texto,
                     "enlace": url, "enlace_directo": "", "enlaces_alternativos": [url],
                     "verificacion": {"estado": "verificada", "enlaces": [{"url": url, "estado": "verificada",
                        "comprobada_en": self.creada.isoformat()}]}}
                filas.append({"id": id_demo(p["id"] + v["id"]), "cliente_id": cliente_id, "perfil_id": p["id"],
                    "cargo_id": cargo["id"], "vacante_id": v["id"], "match_grade": "exact",
                    "explicacion": [{"tipo": "post"}, {"ampliacion": "sin_dato"}], "filtros": p,
                    "cargo_configuracion": cargo,
                    "catalogo_vacantes": {"id": v["id"], "status": "active", "datos": v, "description_full": texto}})
        return {"ejecucion": self.ejecuciones()[0], "filas": filas, "clientes": cfg["clientes"]}
