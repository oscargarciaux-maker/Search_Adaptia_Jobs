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

from buscador import normalizar
from buscador import registro
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


# Mensajes de las funciones SQL del panel. Los de SQL 009 (exigen 120 exactos) indican que la base aún no tiene
# SQL 015 (contrato v21, metas por perfil): se explica cómo instalarla en lugar de un error genérico.
_SIN_015 = ("Reparte exactamente 120 vacantes", "Los cupos superan 120")


def _mensaje_sql(mensaje):
    if "panel_publicar_hoy" in mensaje:  # contrato v27: la función de SQL 016 aún no está instalada
        return ("La base todavía no tiene «Aplicar hoy» (SQL 016). En GitHub → Actions, corre «Preparar Supabase» y "
                "vuelve a intentarlo. Mientras tanto, «Programar para mañana» sigue funcionando.")
    if any(m in mensaje for m in _SIN_015):
        return ("La base todavía no tiene la actualización de metas por perfil (SQL 015). En GitHub → Actions, corre "
                "«Preparar Supabase» y vuelve a intentarlo.")
    return mensaje[:240] or "No se pudo confirmar la operación. Vuelve a intentarlo."


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
                cuerpo = r.json() if r.content else {}
                if isinstance(cuerpo, dict) and cuerpo.get("code") == "P0001":  # `raise exception` de las funciones SQL
                    raise ErrorRepositorio(_mensaje_sql(cuerpo.get("message") or ""), 422)
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

    def borrar_borradores(self, cliente_id):
        """Borrar del todo a un cliente (15 nov): sus mensajes preparados de WhatsApp."""
        self.pedir("DELETE", "panel_borradores", params={"cliente_id": "eq." + cliente_id})

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

    # Contrato v16: bandeja «Por confirmar» y reglas de ubicación (tablas privadas, SQL 014).
    # Patrón sin espacios (los «*» son comodines de PostgREST): un texto con espacios en la URL puede no llegar igual
    # a Supabase, y la consulta devolvía 0 aunque el catálogo tenía cientos de dudosas (13 nov).
    RAZON_POR_CONFIRMAR = "like.elegibilidad*regional*por*confirmar"

    def descripciones(self, ids):
        """Contrato v25: {id: descripción completa} del catálogo, por grupos de 100."""
        salida = {}
        ids = list(ids)
        for inicio in range(0, len(ids), 100):
            grupo = ",".join(ids[inicio:inicio + 100])
            for r in self.pedir("GET", "catalogo_vacantes", params={"id": f"in.({grupo})",
                                                                   "select": "id,description_full"}) or []:
                salida[r["id"]] = r.get("description_full") or ""
        return salida

    def filas_catalogo(self, ids):
        """Contrato v34: {id: fila del catálogo con descripción} para las filas de la bandeja que aún no tienen
        resumen (por grupos de 100)."""
        salida = {}
        ids = list(ids)
        for inicio in range(0, len(ids), 100):
            grupo = ",".join(ids[inicio:inicio + 100])
            for r in self.pedir("GET", "catalogo_vacantes", params={
                    "id": f"in.({grupo})", "select": "id,datos,description_full,status,reason"}) or []:
                salida[r["id"]] = r
        return salida

    def vacante(self, vacante_id):
        """Contrato v29: una fila del catálogo para la ficha del panel, o None."""
        filas = self.pedir("GET", "catalogo_vacantes", params={"id": "eq." + vacante_id,
                                                               "select": "id,datos,description_full,status,reason"})
        return filas[0] if filas else None

    def guardar_descripcion(self, vacante_id, texto):
        """Contrato v29: la descripción traída de la ficha original, solo si el catálogo no tenía ninguna."""
        self.pedir("PATCH", "catalogo_vacantes",
                   params={"id": "eq." + vacante_id, "or": "(description_full.is.null,description_full.eq.)"},
                   headers={"Prefer": "return=minimal"}, json={"description_full": texto[:30000]})

    def candidatas_por_funciones(self, desde=None):
        """Contrato v25: vacantes activas que coinciden con un cargo solo por funciones."""
        params = {"status": "eq.active", "datos->familias": 'cs.[{"coincidencia":"funciones"}]',
                  "select": "id,datos,description_full"}
        if desde:
            params["observed_at"] = "gte." + desde
        return self._paginas("catalogo_vacantes", "id", params, 500)

    def candidatas_por_confirmar(self, desde=None):
        params = {"reason": self.RAZON_POR_CONFIRMAR, "select": "id,datos,description_full"}
        if desde:
            params["observed_at"] = "gte." + desde
        # Contrato v34: páginas de 100 (traen descripciones) que se recorren sin guardarlas todas en memoria.
        return self._paginas("catalogo_vacantes", "id", params, 100)

    def base_ofertas(self):
        """Todas las filas de `ofertas` con la razón y la confianza de país de su vacante en el catálogo."""
        try:
            params = {"select": "*,catalogo_vacantes(reason,status,confianza:datos->>confianza_pais)"}
            return list(self._paginas("ofertas", "id", params, 500))
        except ErrorRepositorio:
            # Respaldo: sin el campo calculado de `datos`; la razón del catálogo basta para omitir las sin confirmar.
            return list(self._paginas("ofertas", "id", {"select": "*,catalogo_vacantes(reason,status)"}, 500))

    SELECCION_OFERTAS = "*,catalogo_vacantes(reason,status,confianza:datos->>confianza_pais)"

    def ofertas_de(self, fecha=None, vacante_ids=None):
        """Filas de `ofertas` entregadas un día (`delivery_date`) o de unas vacantes concretas, con lo que hace falta
        para omitir las sin confirmar. Por páginas y en grupos de 100 ids para no pasar el largo de la dirección."""
        if fecha:
            return list(self._paginas("ofertas", "id", {"select": self.SELECCION_OFERTAS,
                                                        "delivery_date": "eq." + fecha}, 500))
        salida = []
        ids = list(vacante_ids or [])
        for inicio in range(0, len(ids), 100):
            grupo = ",".join('"%s"' % i.replace('"', "") for i in ids[inicio:inicio + 100])
            salida += list(self._paginas("ofertas", "id", {"select": self.SELECCION_OFERTAS,
                                                           "vacante_id": "in.(" + grupo + ")"}, 500))
        return salida

    def vacantes_asignadas(self, fecha=None, cliente_id=None):
        """Ids de las vacantes que el panel asignó: las de la ejecución de `fecha` (si se da) y de `cliente_id` (si se
        da). Sin ejecución ese día, nada."""
        params = {"select": "id,vacante_id"}
        if fecha:
            ejecucion = self.pedir("GET", "panel_ejecuciones", params={"fecha": "eq." + fecha, "select": "id",
                                                                       "limit": 1})
            if not ejecucion:
                return set()
            params["ejecucion_id"] = "eq." + ejecucion[0]["id"]
        if cliente_id:
            params["cliente_id"] = "eq." + cliente_id
        return {r["vacante_id"] for r in self._paginas("panel_asignaciones", "id", params, 1000)}

    def contar(self, tabla, params):
        """Cuántas filas cumplen el filtro (cabecera Content-Range con count=exact); None si no se pudo contar."""
        try:
            r = self.sesion.get(self.url + "/rest/v1/" + tabla, params={**params, "select": "id", "limit": 1},
                                headers={**self.cabeceras, "Prefer": "count=exact"}, timeout=45)
            total = (r.headers.get("Content-Range") or "").rsplit("/", 1)[-1]
            return int(total) if 200 <= r.status_code < 300 and total.isdigit() else None
        except (requests.RequestException, ValueError):
            return None

    def contar_por_confirmar(self, desde=None):
        """Contrato v34: cuántas leerá la carga, para mostrar el avance sin traerlas todas antes."""
        return self.contar("catalogo_vacantes", {"reason": self.RAZON_POR_CONFIRMAR,
                                                 **({"observed_at": "gte." + desde} if desde else {})})

    def conteo_dudosas(self):
        """Solo conteos, para explicar una carga vacía: total del catálogo, por razón y por confianza baja."""
        return {"catalogo": self.contar("catalogo_vacantes", {}),
                "por_confirmar": self.contar("catalogo_vacantes", {"reason": self.RAZON_POR_CONFIRMAR}),
                "confianza_baja": self.contar("catalogo_vacantes", {"datos->>confianza_pais": "eq.baja"})}

    def archivar_catalogo(self, vacante_id, razon):
        self.pedir("PATCH", "catalogo_vacantes", params={"id": "eq." + vacante_id},
                   headers={"Prefer": "return=minimal"}, json={"status": "archived", "reason": razon})

    def recibidas(self, perfil_ids):
        salida = {}
        for inicio in range(0, len(perfil_ids), 50):
            ids = ",".join(perfil_ids[inicio:inicio + 50])
            if ids:
                for r in self._paginas("panel_asignaciones", "id", {"perfil_id": f"in.({ids})",
                                                                     "select": "id,perfil_id,vacante_id"}, 1000):
                    salida.setdefault(r["perfil_id"], set()).add(r["vacante_id"])
        return salida

    def con_resumen(self):
        """Contrato v34: si la bandeja ya tiene la columna `resumen` (SQL 018). Se pregunta una vez por instancia."""
        if getattr(self, "_con_resumen", None) is None:
            try:
                self.pedir("GET", "panel_revisiones", params={"select": "resumen", "limit": 1})
                self._con_resumen = True
            except ErrorRepositorio:
                self._con_resumen = False
        return self._con_resumen

    def resumir_revisiones(self, resumenes):
        """Contrato v34: guarda el resumen de varias filas de la bandeja (una petición por fila; solo las que faltan)."""
        for vid, resumen in resumenes.items():
            self.pedir("PATCH", "panel_revisiones", params={"vacante_id": "eq." + vid},
                       headers={"Prefer": "return=minimal"}, json={"resumen": resumen})

    def revisiones(self, estado=None, vacante_id=None, ligera=False, sin_descripcion=False):
        # `sin_descripcion` (contrato v34): con el catálogo pero sin descripciones, para armar la cola sin traer miles
        # de textos largos a la vez (la carga completa agotaba la memoria del alojamiento gratuito).
        # `ligera` (contrato v29): sin la descripción completa, para ordenar y contar todas las pendientes; la
        # descripción se pide después solo para la página que se muestra. Contrato v34: con la columna `resumen`
        # (SQL 018) la lista ligera ni siquiera lee el catálogo; las filas sin resumen se completan después.
        descripcion = "" if ligera or sin_descripcion else "description_full,"
        params = {"select": f"*,catalogo_vacantes(id,datos,{descripcion}status,reason)"}
        if ligera and self.con_resumen():
            params = {"select": "vacante_id,estado,motivo,pista,ubicacion,sugerencia,paises,perfiles,prioridad,"
                                "creada_en,resumen"}
        if estado:
            params["estado"] = "eq." + estado
        if vacante_id:
            return self.pedir("GET", "panel_revisiones", params={**params, "vacante_id": "eq." + vacante_id}) or []
        # Por páginas: la depuración completa puede guardar miles (contrato v17).
        filas = list(self._paginas("panel_revisiones", "vacante_id", params, 200))
        return sorted(filas, key=lambda r: -(r.get("prioridad") or 0))

    def guardar_revisiones(self, filas):
        ahora = datetime.now(timezone.utc).isoformat()
        filas = list(filas)
        for inicio in range(0, len(filas), 200):  # contrato v34: la carga completa puede guardar miles
            self.pedir("POST", "panel_revisiones", params={"on_conflict": "vacante_id"},
                       headers={"Prefer": "resolution=ignore-duplicates,return=minimal"},
                       json=[{**f, "actualizada_en": ahora} for f in filas[inicio:inicio + 200]])

    def actualizar_revision(self, vacante_id, cambios):
        self.pedir("PATCH", "panel_revisiones", params={"vacante_id": "eq." + vacante_id},
                   headers={"Prefer": "return=minimal"},
                   json={**cambios, "actualizada_en": datetime.now(timezone.utc).isoformat()})

    def vencer_revisiones(self, vacante_ids, motivo=""):
        """Pasa a «vencida» varias pendientes en pocas peticiones (lotes de 100)."""
        cambios = {"estado": "vencida", **({"motivo": motivo} if motivo else {}),
                   "actualizada_en": datetime.now(timezone.utc).isoformat()}
        ids = list(vacante_ids)
        for i in range(0, len(ids), 100):
            self.pedir("PATCH", "panel_revisiones", params={"vacante_id": "in.(" + ",".join(ids[i:i + 100]) + ")",
                                                          "estado": "eq.pendiente"},
                       headers={"Prefer": "return=minimal"}, json=cambios)

    def reglas(self):
        return self.pedir("GET", "panel_reglas_ubicacion", params={"select": "*", "limit": 5000}) or []

    def guardar_regla(self, fila):
        self.pedir("POST", "panel_reglas_ubicacion", params={"on_conflict": "texto"},
                   headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                   json={**fila, "actualizada_en": datetime.now(timezone.utc).isoformat()})

    # Contrato v17: decisiones para aprender y cambios de reglas.
    def decisiones_ubicacion(self):
        return self._paginas("panel_revisiones", "vacante_id", {"estado": "in.(confirmada,descartada)",
                             "select": "vacante_id,estado,motivo,ubicacion,paises"}, 1000)

    def actualizar_regla(self, texto, cambios):
        from urllib.parse import quote  # «%20» viaja intacto; un espacio como «+» podía no coincidir (13 nov)
        self.pedir("PATCH", "panel_reglas_ubicacion?texto=eq." + quote(texto, safe=""),
                   headers={"Prefer": "return=minimal"},
                   json={**cambios, "actualizada_en": datetime.now(timezone.utc).isoformat()})

    def ejecucion(self, fecha):
        filas = self.pedir("GET", "panel_ejecuciones", params={"fecha": "eq." + fecha, "limit": 1})
        return filas[0] if filas else None

    def conteo_asignaciones(self, ejecucion_id, perfil_ids):
        if not perfil_ids:
            return Counter()
        filas = self._paginas("panel_asignaciones", "id", {"ejecucion_id": "eq." + ejecucion_id,
                              "perfil_id": "in.(" + ",".join(perfil_ids) + ")", "select": "id,perfil_id"}, 1000)
        return Counter(r["perfil_id"] for r in filas)

    def historial_ejecuciones(self, dias=7):
        """Las búsquedas de los últimos días, la más reciente primero (una por fecha, SQL 009)."""
        return self.ejecuciones()[:dias]

    def asignaciones_por_cliente(self, ejecucion_ids):
        """Paso 8 (Resumen por cliente): cuántas vacantes recibió cada cliente en cada búsqueda."""
        if not ejecucion_ids:
            return Counter()
        filas = self._paginas("panel_asignaciones", "id", {"ejecucion_id": "in.(" + ",".join(ejecucion_ids) + ")",
                              "select": "id,ejecucion_id,cliente_id"}, 1000)
        return Counter((r["ejecucion_id"], r["cliente_id"]) for r in filas)

    def crear_asignaciones(self, filas):
        self.pedir("POST", "panel_asignaciones", params={"on_conflict": "ejecucion_id,perfil_id,vacante_id"},
                   headers={"Prefer": "resolution=ignore-duplicates"}, json=filas)

    def actualizar_catalogo_datos(self, vacante_id, datos):
        self.pedir("PATCH", "catalogo_vacantes", params={"id": "eq." + vacante_id},
                   headers={"Prefer": "return=minimal"}, json={"datos": datos})

    def publicar(self, revision):
        actual = self.config()
        if actual["revision"] != revision:
            raise ErrorRepositorio("La configuración cambió. Recarga antes de programar.", 409)
        Configuracion.model_validate(actual["borrador"]).validar_publicacion()
        return self.pedir("POST", "rpc/panel_publicar", json={"p_revision": revision})

    def publicar_hoy(self, revision):
        """Contrato v27: el borrador rige desde hoy para las búsquedas que faltan hoy (SQL 016)."""
        actual = self.config()
        if actual["revision"] != revision:
            raise ErrorRepositorio("La configuración cambió. Recarga antes de aplicar.", 409)
        Configuracion.model_validate(actual["borrador"]).validar_publicacion()
        return self.pedir("POST", "rpc/panel_publicar_hoy", json={"p_revision": revision})

    def operativa(self, fecha):
        filas = self.pedir("GET", "panel_versiones", params={"vigente_desde": "lte." + fecha, "order": "vigente_desde.desc,revision.desc", "limit": 1})
        return filas[0] if filas else None

    def ejecuciones(self):
        return self.pedir("GET", "panel_ejecuciones", params={"order": "fecha.desc", "limit": 30})

    def _paginas(self, ruta, clave, params, tamano=500):
        ultimo = ""
        while True:
            lote = self.pedir("GET", ruta, params={**params, "order": clave, "limit": tamano,
                                                    **({clave: "gt." + str(ultimo)} if ultimo else {})})
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
        "verificacion:datos->verificacion->>estado,tipo:datos->>tipo,salario:datos->>salario")

    def _leer_catalogo(self):
        from panel.afinidad import ligera
        entregadas = {f["vacante_id"] for f in self._paginas("entregas_diarias", "vacante_id",
                                                             {"select": "vacante_id"}, 1000)}
        vacantes, ya_dadas = [], []
        for d in self._paginas("catalogo_vacantes", "id", {"status": "eq.active", "select": self.CAMPOS_ESTIMACION}, 1000):
            if d.get("duplicada_de") or d.get("verificacion") == "rechazada" or d.get("tipo") == "post":
                continue  # un post (contrato v11) no es una vacante formal: no cuenta para estimar
            if {d["id"], *(d.get("ids_agrupados") or [])} & entregadas:
                ya_dadas.append(ligera(d))  # contrato v35: cuentan para «últimos 30 días», no para «sin entregar»
                continue
            vacantes.append(ligera(d))
        return {"vacantes": vacantes, "entregadas": entregadas, "entregadas_vacantes": ya_dadas,
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
        except Exception as e:  # se conserva la copia anterior; el siguiente uso lo reintenta
            registro.aviso("repositorio:391", e)

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
                    "cliente_id": "eq." + cliente_id, "select": "*,catalogo_vacantes(id,datos,description_full,status,reason)",
                    "order": "creada_en,id", "offset": inicio, "limit": 500})
                filas.extend(lote)
                if len(lote) < 500:
                    break
        return {"ejecucion": e, "filas": filas, "clientes": cfg["clientes"]}


# Contrato v29: secciones con viñetas para ver la ficha con su formato en la demostración.
DEMO_SECCIONES = ("\n\nResponsibilities:\n- Work with product and engineering on new features.\n"
                  "- Keep quality and consistency across the product.\n\nRequirements:\n"
                  "- Recent work samples or portfolio.\n- Clear written communication.")


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

    def borrar_borradores(self, cliente_id):
        with self.lock:
            self.estado["borradores"] = [b for b in self.estado.get("borradores", []) if b["cliente_id"] != cliente_id]
            self._guardar()

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

    # Contrato v16: bandeja «Por confirmar» ficticia (3 vacantes), sin red ni Supabase.
    def _revisiones(self):
        if "revisiones" not in self.estado:
            cfg = configuracion_demo()
            perfil = lambda i, faltan: {"perfil_id": cfg["perfiles"][i]["id"], "cliente_id": cfg["perfiles"][i]["cliente_id"],  # noqa: E731
                                        "cargo_id": cfg["perfiles"][i]["cargo_id"], "faltan": faltan}
            fecha = hoy()
            casos = [("QA Engineer", "Lumen", "Remote Remoto", "Preferably based in Colombia or Mexico.",
                      ["CO", "MX"], [perfil(4, True)], 160),
                     ("Product Designer", "Orbita", "Granada", "Trabajarás en nuestra oficina de Granada, España, dos "
                      "días por semana.", ["ES"], [perfil(1, False)], 40),
                     ("Product Designer", "Forma", "Remote Remoto", "Preferably located in Latin America.", [],
                      [perfil(0, True), perfil(2, True)], 230)]
            filas = []
            for n, (titulo, empresa, lugar, frase, sugerida, perfiles, prioridad) in enumerate(casos):
                vid = "rev-demo-" + str(n)
                url = "https://example.org/empleos/" + vid
                datos = {"id": vid, "titulo": titulo, "empresa": empresa, "ubicacion": lugar, "paises": [],
                         "confianza_pais": "baja", "nota_pais": "remoto: confirmar región", "modalidad": "remoto",
                         "idioma": "en" if n != 1 else "es", "fecha_publicacion": fecha, "fecha_estimada": False,
                         "anos_min": 2, "ingles": "intermedio", "enlace": url, "enlaces_alternativos": [url],
                         "verificacion": {"estado": "verificada", "enlaces": [{"url": url, "estado": "verificada",
                                          "comprobada_en": self.creada.isoformat()}]}}
                filas.append({"vacante_id": vid, "estado": "pendiente", "motivo": "ubicación por confirmar",
                              "pista": frase, "ubicacion": normalizar.texto(lugar), "sugerencia": sugerida,
                              "perfiles": perfiles, "prioridad": prioridad, "creada_en": self.creada.isoformat(),
                              "catalogo_vacantes": {"id": vid, "datos": datos, "status": "archived",
                                                    "reason": "elegibilidad regional por confirmar",
                                                    "description_full": frase + " " + ("We require 2 years of "
                                                        "experience. English B2 required. We build digital products. ") * 4}})
            # Contrato v25: una vacante con otro título que coincide por funciones con Product Designer.
            vid = "rev-demo-funciones"
            url = "https://example.org/empleos/" + vid
            texto = ("Responsabilidades: user research, wireframes, prototipos en Figma, design system y pruebas de "
                     "usabilidad con el equipo de producto. We require 2 years of experience. English B2 required. ") * 3
            datos = {"id": vid, "titulo": "Experience Lead", "empresa": "Nexo", "ubicacion": "Remote - Colombia",
                     "paises": ["CO"], "paises_mundo": ["CO"], "confianza_pais": "alta", "nota_pais": "",
                     "modalidad": "remoto", "idioma": "en", "fecha_publicacion": fecha, "fecha_estimada": False,
                     "anos_min": 2, "ingles": "intermedio", "enlace": url, "enlaces_alternativos": [url],
                     "familias": [{"familia": "cargo:" + cfg["cargos"][0]["id"], "coincidencia": "funciones"}],
                     "verificacion": {"estado": "verificada", "enlaces": [{"url": url, "estado": "verificada",
                                      "comprobada_en": self.creada.isoformat()}]}}
            filas.append({"vacante_id": vid, "estado": "pendiente", "motivo": "Coincide por funciones",
                          "pista": "Funciones encontradas: user research, wireframes, figma, design system",
                          "ubicacion": normalizar.texto(datos["ubicacion"]), "sugerencia": [],
                          "perfiles": [perfil(0, True)], "prioridad": 120, "creada_en": self.creada.isoformat(),
                          "catalogo_vacantes": {"id": vid, "datos": datos, "status": "active", "reason": None,
                                                "description_full": texto}})
            self.estado["revisiones"] = filas
        return self.estado["revisiones"]

    def revisiones(self, estado=None, vacante_id=None, ligera=False, sin_descripcion=False):
        with self.lock:
            return deepcopy([r for r in self._revisiones() if (not estado or r["estado"] == estado)
                             and (not vacante_id or r["vacante_id"] == vacante_id)])

    def guardar_revisiones(self, filas):
        with self.lock:
            existentes = {r["vacante_id"] for r in self._revisiones()}
            self.estado["revisiones"].extend(deepcopy(f) for f in filas if f["vacante_id"] not in existentes)
            self._guardar()

    def actualizar_revision(self, vacante_id, cambios):
        with self.lock:
            for r in self._revisiones():
                if r["vacante_id"] == vacante_id:
                    r.update(deepcopy(cambios))
            self._guardar()

    def con_resumen(self):
        return True

    def resumir_revisiones(self, resumenes):
        for vid, resumen in resumenes.items():
            self.actualizar_revision(vid, {"resumen": resumen})

    def filas_catalogo(self, ids):
        ids = set(ids)
        with self.lock:
            return {r["vacante_id"]: deepcopy(r["catalogo_vacantes"]) for r in self._revisiones()
                    if r["vacante_id"] in ids and r.get("catalogo_vacantes")}

    def vencer_revisiones(self, vacante_ids, motivo=""):
        for vid in vacante_ids:
            self.actualizar_revision(vid, {"estado": "vencida", **({"motivo": motivo} if motivo else {})})

    def reglas(self):
        with self.lock:
            return deepcopy(list(self.estado.get("reglas", {}).values()))

    def guardar_regla(self, fila):
        with self.lock:
            self.estado.setdefault("reglas", {})[fila["texto"]] = deepcopy(fila)
            self._guardar()

    def decisiones_ubicacion(self):
        with self.lock:
            return deepcopy([{k: r.get(k) for k in ("vacante_id", "estado", "motivo", "ubicacion", "paises")}
                             for r in self._revisiones() if r["estado"] in ("confirmada", "descartada")])

    def actualizar_regla(self, texto, cambios):
        with self.lock:
            regla = self.estado.setdefault("reglas", {}).get(texto)
            if regla:
                regla.update(deepcopy(cambios))
                self._guardar()

    def operativa(self, fecha):
        return {"revision": 1, "configuracion": configuracion_demo()}

    def ejecucion(self, fecha):
        return self.ejecuciones()[0]

    def recibidas(self, perfil_ids):
        with self.lock:
            salida = {}
            for a in self.estado.get("asignaciones_extra", []):
                salida.setdefault(a["perfil_id"], set()).add(a["vacante_id"])
            return salida

    def conteo_asignaciones(self, ejecucion_id, perfil_ids):
        return Counter()

    def historial_ejecuciones(self, dias=7):
        actual = self.ejecuciones()[0]
        base = datetime.fromisoformat(actual["fecha"]).date()
        return [actual] + [{"id": id_demo("ejecucion-" + str(n)), "fecha": (base - timedelta(days=n)).isoformat(),
                            "revision": 1, "estado": "completa", "resumen": {}} for n in range(1, dias)]

    # Recibidas de cada cliente de ejemplo: uno bajo su meta, otro cerca y el resto completos (números fijos).
    _RITMO_DEMO = (1.0, 0.18, 0.75, 1.0, 0.9)

    def asignaciones_por_cliente(self, ejecucion_ids):
        cfg = Configuracion.model_validate(configuracion_demo())
        metas = Counter()
        for p in cfg.perfiles:
            metas[str(p.cliente_id)] += p.meta_diaria or 0
        actual = self.ejecuciones()[0]["id"]
        salida = Counter()
        for n, e in enumerate(ejecucion_ids):
            for i, c in enumerate(cfg.clientes):
                ritmo = self._RITMO_DEMO[i % len(self._RITMO_DEMO)]
                variacion = 0 if e == actual else ((i * 7 + n * 3) % 5) - 2
                salida[(e, str(c.id))] = max(0, min(metas[str(c.id)], round(metas[str(c.id)] * ritmo) + variacion))
        with self.lock:
            for a in self.estado.get("asignaciones_extra", []):
                if actual in ejecucion_ids:
                    salida[(actual, a["cliente_id"])] += 1
        return salida

    def crear_asignaciones(self, filas):
        with self.lock:
            self.estado.setdefault("asignaciones_extra", []).extend(deepcopy(filas))
            self._guardar()

    def actualizar_catalogo_datos(self, vacante_id, datos):
        pass  # la demostración ya trae el enlace comprobado

    def archivar_catalogo(self, vacante_id, razon):
        with self.lock:
            for r in self._revisiones():
                if r["vacante_id"] == vacante_id and r.get("catalogo_vacantes"):
                    r["catalogo_vacantes"].update(status="archived", reason=razon)
            self._guardar()

    def candidatas_por_confirmar(self, desde=None):
        return []  # la demostración trae su bandeja ya preparada

    def candidatas_por_funciones(self, desde=None):
        return []

    def vacante(self, vacante_id):
        """Demostración: busca la vacante en los resultados de cada cliente y en la bandeja."""
        for r in self.revisiones():
            if r["vacante_id"] == vacante_id and r.get("catalogo_vacantes"):
                return deepcopy(r["catalogo_vacantes"])
        for c in configuracion_demo()["clientes"]:
            for fila in self.resultados(c["id"])["filas"]:
                if fila["vacante_id"] == vacante_id:
                    return deepcopy(fila["catalogo_vacantes"])
        return None

    def guardar_descripcion(self, vacante_id, texto):
        return None  # la demostración no lee sitios externos

    def descripciones(self, ids):
        """Demostración: descripciones ficticias según el título, para proponer funciones."""
        por_id = {v["id"]: v.get("titulo", "") for v in self.catalogo_vigente()["vacantes"]}
        temas = {"design": "user research, wireframes, prototipos en Figma, design system, pruebas de usabilidad, "
                           "journey maps y diseño de interacción con el equipo de producto.",
                 "qa": "casos de prueba, automatización con Playwright, pruebas de regresión, reporte de bugs y "
                       "pipelines de integración continua.",
                 "front": "React, TypeScript, componentes accesibles, rendimiento web y pruebas unitarias.",
                 "otro": "atención a clientes, reportes semanales, coordinación con proveedores y hojas de cálculo."}
        salida = {}
        for i in ids:
            t = (por_id.get(i) or "").lower()
            tema = "design" if "design" in t or "ux" in t or "ui " in t else "qa" if "qa" in t or "test" in t or \
                "prueba" in t else "front" if "front" in t else "otro"
            salida[i] = ("Responsabilidades: " + temas[tema] + " ") * 4
        return salida

    def base_ofertas(self):
        """Filas ficticias de `ofertas` para probar la descarga: dos de hoy (una confirmada y una por confirmar) y una de
        ayer que el panel asignó a un cliente."""
        ayer = (datetime.fromisoformat(hoy()) - timedelta(days=1)).date().isoformat()
        return [{"id": 1, "external_id": "demo-1", "vacante_id": "demo-v1", "delivery_date": hoy(),
                 "job_title": "Product Designer", "company_name": "Orbita",
                 "offer_url": "https://example.org/empleos/demo-1", "location": "Bogotá, Colombia",
                 "hire_countries": ["CO"], "catalogo_vacantes": {"reason": None, "status": "active", "confianza": "alta"}},
                {"id": 2, "external_id": "demo-2", "vacante_id": "demo-v2", "delivery_date": hoy(),
                 "job_title": "QA Engineer", "company_name": "Lumen",
                 "offer_url": "https://example.org/empleos/demo-2", "location": "Remote", "hire_countries": [],
                 "catalogo_vacantes": {"reason": "elegibilidad regional por confirmar", "status": "archived",
                                       "confianza": "baja"}},
                {"id": 3, "external_id": "demo-3", "vacante_id": "demo-v3", "delivery_date": ayer,
                 "job_title": "UX Designer", "company_name": "Forma",
                 "offer_url": "https://example.org/empleos/demo-3", "location": "Madrid, España",
                 "hire_countries": ["ES"], "catalogo_vacantes": {"reason": None, "status": "active", "confianza": "alta"}}]

    def ofertas_de(self, fecha=None, vacante_ids=None):
        if fecha:
            return [f for f in self.base_ofertas() if f["delivery_date"] == fecha]
        ids = set(vacante_ids or [])
        return [f for f in self.base_ofertas() if f["vacante_id"] in ids]

    def vacantes_asignadas(self, fecha=None, cliente_id=None):
        """Demostración: el primer cliente recibió hoy demo-v1 y ayer demo-v3; el segundo, hoy demo-v1 y demo-v2."""
        clientes = [c["id"] for c in configuracion_demo()["clientes"]]
        ayer = (datetime.fromisoformat(hoy()) - timedelta(days=1)).date().isoformat()
        asignaciones = [(clientes[0], hoy(), "demo-v1"), (clientes[0], ayer, "demo-v3"),
                        (clientes[1], hoy(), "demo-v1"), (clientes[1], hoy(), "demo-v2")]
        return {v for c, f, v in asignaciones if (not fecha or f == fecha) and (not cliente_id or c == cliente_id)}

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

    def publicar_hoy(self, revision):
        with self.lock:
            if revision != self.estado["revision"]:
                raise ErrorRepositorio("La configuración cambió. Recarga antes de aplicar.", 409)
            Configuracion.model_validate(self.estado["borrador"]).validar_publicacion()
            self.estado["publicada"] = {"revision": revision, "vigente_desde": hoy(),
                                        "configuracion": deepcopy(self.estado["borrador"])}
            self._guardar()
            return {"revision": revision, "vigente_desde": hoy()}

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
        vacantes, ya_dadas = [], []
        for n in range(1200):  # contrato v35: las 300 últimas cuentan como ya entregadas (solo «últimos 30 días»)
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
            (vacantes if n < 900 else ya_dadas).append(ligera(datos, texto))
        self._catalogo = {"vacantes": vacantes, "entregadas_vacantes": ya_dadas,
                          "actualizado": self.creada.isoformat(timespec="minutes")}
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
                anos = 7 if n % 7 == 6 else n % 5  # contrato v27: algunas piden más años y llegan con su etiqueta
                publicada = (datetime.fromisoformat(hoy()) - timedelta(days=dias)).date().isoformat()
                titulo = ({"Product Designer": ["Product Designer", "UX Designer", "Interaction Designer"],
                           "Frontend": ["Frontend Developer", "Frontend Engineer", "Desarrollador Frontend"],
                           "QA": ["QA Engineer", "Software Tester", "Analista de pruebas"]}[cargo["nombre"]])[n % 3]
                v = {"id": identificador, "titulo": titulo, "empresa": ["Estudio Norte", "Orbita", "Forma", "Nexo", "Lumen"][n % 5],
                     "ubicacion": "Remote - Worldwide", "paises": ["CO", "ES"], "confianza_pais": "alta",
                     "modalidad": "remoto", "idioma": "en" if n % 2 else "es", "fecha_publicacion": publicada,
                     "fecha_estimada": False, "anos_min": anos, "ingles": "intermedio",
                     "_descripcion": (f"English B2 required. We require {anos} years of experience. We build digital products with a collaborative team. " * 5) + DEMO_SECCIONES,
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
        # Contrato v16: las confirmadas en la bandeja aparecen en «Vacantes» de su cliente.
        catalogo = {r["vacante_id"]: r.get("catalogo_vacantes") for r in self.revisiones() if r.get("catalogo_vacantes")}
        with self.lock:
            for a in self.estado.get("asignaciones_extra", []):
                if a["cliente_id"] == cliente_id and a["vacante_id"] in catalogo:
                    filas.append({**deepcopy(a), "id": id_demo(a["perfil_id"] + a["vacante_id"]),
                                  "catalogo_vacantes": deepcopy(catalogo[a["vacante_id"]])})
        return {"ejecucion": self.ejecuciones()[0], "filas": filas, "clientes": cfg["clientes"]}
