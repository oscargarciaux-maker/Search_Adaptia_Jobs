"""Validación del mismo contrato para API, demostración y ejecutor."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from buscador import paises


TECHO_MAXIMO = 600  # contrato v21: techo diario editable; protege los consumos (Apify, tiempo de búsqueda)


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cliente(Modelo):
    id: UUID
    nombre: str = Field(min_length=1, max_length=100)
    activo: bool = True
    # Contrato v21: el cliente «Comunidad» (grupo de WhatsApp) recibe después de los clientes reales, con lo que sobra
    # del techo diario.
    comunidad: bool = False

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, v):
        if not v.strip():
            raise ValueError("Escribe un nombre.")
        return v.strip()


class Cargo(Modelo):
    id: UUID
    nombre: str = Field(min_length=2, max_length=120)
    # Contrato v21: el cupo del cargo ya no se edita; se calcula con las metas de sus perfiles (`Configuracion`). Se
    # conserva el campo para leer configuraciones anteriores y para el motor, que sigue eligiendo por cargo.
    cupo: int = Field(default=20, ge=0, le=TECHO_MAXIMO, strict=True)
    activo: bool = True
    terminos_exactos: list[str] = Field(default_factory=list, max_length=30)
    terminos_similares: list[str] = Field(default_factory=list, max_length=30)
    terminos_excluidos: list[str] = Field(default_factory=list, max_length=30)
    terminos_cercanos: list[str] = Field(default_factory=list, max_length=30)  # contrato v9: solo para ampliar
    # Contrato v25: huella de funciones (tareas y herramientas) para reconocer vacantes con otro título.
    funciones: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("nombre")
    @classmethod
    def nombre_cargo(cls, v):
        v = " ".join(v.split())
        if len(v) < 2 or "@" in v or "://" in v:
            raise ValueError("Escribe un cargo, sin enlaces ni datos de contacto.")
        return v

    @field_validator("terminos_exactos", "terminos_similares", "terminos_excluidos", "terminos_cercanos", "funciones")
    @classmethod
    def terminos_validos(cls, vs):
        salida = []
        for v in vs:
            v = " ".join(v.split())
            if not 2 <= len(v) <= 120 or "@" in v or "://" in v:
                raise ValueError("Cada término debe tener entre 2 y 120 caracteres, sin enlaces.")
            if v.casefold() not in {x.casefold() for x in salida}:
                salida.append(v)
        return salida


RANGO_EXPERIENCIA = 3  # contrato v20: de 3 años menos a 3 años más (v22: margen editable, 3 o 4)
MONEDAS = Literal["USD", "EUR", "COP", "MXN", "ARS", "CLP", "PEN", "BRL", "UYU", "DOP", "GTQ", "CRC", "VES"]


class RestriccionSalario(BaseModel):
    """Contrato v22: no acepta vacantes con salario menor, si el aviso lo dice en la misma moneda."""
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["salario_minimo"]
    monto: float = Field(gt=0, le=100_000_000)
    moneda: MONEDAS
    periodo: Literal["month", "year", "hour"] = "month"


class RestriccionPalabras(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["palabras"]
    palabras: list[str] = Field(min_length=1, max_length=30)

    @field_validator("palabras")
    @classmethod
    def limpias(cls, vs):
        return _terminos(vs)


class RestriccionContrato(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["contrato"]
    tipos: list[Literal["freelance", "part_time", "contract", "internship"]] = Field(min_length=1, max_length=4)


def _terminos(vs):
    salida = []
    for v in vs:
        v = " ".join(str(v).split())
        if not 2 <= len(v) <= 60 or "@" in v or "://" in v:
            raise ValueError("Cada término debe tener entre 2 y 60 caracteres, sin enlaces.")
        if v.casefold() not in {x.casefold() for x in salida}:
            salida.append(v)
    return salida
META_POR_DEFECTO = 10  # contrato v21: meta diaria de un perfil nuevo


MODOS = ("remoto", "hibrido", "presencial")


class Ubicacion(Modelo):
    """Contrato v30: un lugar donde trabajaría (países y ciudades) y las modalidades que acepta ahí. La primera fila es
    donde vive. Reemplaza en el formulario a «se mudaría a» y «puede trabajar legalmente en»."""
    paises: list[str] = Field(default_factory=list, max_length=60)
    ciudades: list[str] = Field(default_factory=list, max_length=10)
    modalidades: list[Literal["remoto", "hibrido", "presencial"]] = Field(default_factory=lambda: ["remoto"],
                                                                        min_length=1, max_length=3)

    @field_validator("paises")
    @classmethod
    def paises_validos(cls, vs):
        from panel.revision import expandir  # regiones («LATAM», «Europa»…) → sus países
        vs = expandir(vs)
        validos = paises.mundo()["codigos"] | set(paises.datos()["reconocidos"])
        if not set(vs) <= validos:
            raise ValueError("Elige países de la lista en cada ubicación.")
        return vs[:60]

    @field_validator("ciudades")
    @classmethod
    def ciudades_limpias(cls, vs):
        return _terminos(vs)

    @field_validator("modalidades")
    @classmethod
    def sin_repetir(cls, vs):
        return list(dict.fromkeys(vs))

    @model_validator(mode="after")
    def con_lugar(self):
        if not self.paises and not self.ciudades:
            raise ValueError("Cada ubicación necesita al menos un país o una ciudad.")
        return self


class Perfil(Modelo):
    id: UUID
    cliente_id: UUID
    cargo_id: UUID
    activo: bool = True
    # Contrato v8: dónde vive y qué modalidades acepta (docs/CONTRATO_DATOS_v8.md).
    vive_en: str = "CO"
    modalidades: list[Literal["remoto", "hibrido", "presencial"]] = Field(default_factory=lambda: ["remoto"],
                                                                        min_length=1, max_length=3)
    paises_presenciales_extra: list[str] = Field(default_factory=list, max_length=60)
    antiguedad_dias: int = Field(default=14, ge=1, le=30)
    idiomas: list[Literal["es", "en"]] = Field(default_factory=lambda: ["es", "en"], min_length=1, max_length=2)
    ingles_maximo: Literal["sin_filtro", "A1", "A2", "B1", "B2", "C1", "C2", "native"] = "sin_filtro"
    experiencia_min: int | None = Field(default=None, ge=0, le=40)
    experiencia_max: int | None = Field(default=None, ge=0, le=40)
    # Contrato v20: años que tiene la persona; el rango buscado (±3) se calcula aquí. Vacío: sin filtro, o el rango
    # antiguo de un perfil guardado antes de v20.
    experiencia_anos: int | None = Field(default=None, ge=0, le=40)
    aceptar_experiencia_sin_dato: bool = False
    aceptar_ingles_sin_dato: bool = False
    # Contrato v21: cuántas vacantes al día busca este perfil. Vacío solo en configuraciones anteriores: se calcula
    # repartiendo el cupo antiguo del cargo entre sus perfiles activos.
    meta_diaria: int | None = Field(default=None, ge=0, le=120)
    # Contrato v22: margen de años, restricciones que descartan con evidencia y prioridades que solo ordenan.
    margen_experiencia: Literal[3, 4] = RANGO_EXPERIENCIA
    restricciones: list[RestriccionSalario | RestriccionPalabras | RestriccionContrato] = Field(
        default_factory=list, max_length=10)
    sectores_preferidos: list[str] = Field(default_factory=list, max_length=30)
    palabras_preferidas: list[str] = Field(default_factory=list, max_length=30)
    # Contrato v23: ciudades para presencial/híbrida, permiso legal para trabajar en otros países y horarios aceptados.
    ciudades: list[str] = Field(default_factory=list, max_length=10)
    puede_trabajar_en: list[str] = Field(default_factory=list, max_length=60)  # v26: perfiles muy móviles
    acepta_horario: list[Literal["us_este", "us_pacifico", "europa"]] = Field(default_factory=list, max_length=3)
    # Contrato v30: dónde trabajaría, en filas. Si viene, manda: los campos de arriba (vive_en, modalidades, ciudades,
    # paises_presenciales_extra, puede_trabajar_en) se calculan desde las filas para quien aún los lee (búsqueda por
    # lugares, admisión). Si no viene (perfiles anteriores, importador), `filas` las arma con esos campos.
    ubicaciones: list[Ubicacion] = Field(default_factory=list, max_length=10)

    @model_validator(mode="before")
    @classmethod
    def desde_v6(cls, datos):
        """Perfiles guardados con v6 (paises + modalidad) se leen como v8 sin migración SQL."""
        if not isinstance(datos, dict) or ("paises" not in datos and "modalidad" not in datos):
            return datos
        datos = dict(datos)
        antiguos = list(dict.fromkeys(datos.pop("paises", None) or []))
        modalidad = datos.pop("modalidad", None)
        if antiguos and "vive_en" not in datos:
            datos["vive_en"] = antiguos[0]
            datos.setdefault("paises_presenciales_extra", antiguos[1:])
        if modalidad and "modalidades" not in datos:
            datos["modalidades"] = ["remoto", "hibrido", "presencial"] if modalidad == "cualquiera" else [modalidad]
        return datos

    @field_validator("vive_en")
    @classmethod
    def residencia(cls, v):
        # Contrato v23: cualquier país de la tabla ISO mundial.
        if v not in paises.mundo()["codigos"] and v not in paises.datos()["reconocidos"]:
            raise ValueError("Elige un país de la lista.")
        return v

    @field_validator("paises_presenciales_extra", "puede_trabajar_en")
    @classmethod
    def cobertura(cls, vs):
        validos = paises.mundo()["codigos"] | set(paises.datos()["reconocidos"])
        if not set(vs) <= validos:
            raise ValueError("Elige países de la lista.")
        return list(dict.fromkeys(vs))

    @field_validator("ciudades")
    @classmethod
    def ciudades_limpias(cls, vs):
        return _terminos(vs)

    @field_validator("acepta_horario")
    @classmethod
    def horarios_sin_repetir(cls, vs):
        return list(dict.fromkeys(vs))

    @field_validator("modalidades")
    @classmethod
    def sin_repetir(cls, vs):
        return list(dict.fromkeys(vs))

    @field_validator("sectores_preferidos", "palabras_preferidas")
    @classmethod
    def preferidos(cls, vs):
        return _terminos(vs)

    @property
    def paises_oficina(self):
        """Países donde aceptaría trabajo híbrido o presencial."""
        return list(dict.fromkeys([self.vive_en, *self.paises_presenciales_extra]))

    @model_validator(mode="after")
    def rango(self):
        if self.experiencia_anos is not None:
            self.experiencia_min = max(0, self.experiencia_anos - self.margen_experiencia)
            self.experiencia_max = min(40, self.experiencia_anos + self.margen_experiencia)
        if self.experiencia_min is not None and self.experiencia_max is not None and self.experiencia_min > self.experiencia_max:
            raise ValueError("El mínimo de experiencia no puede superar al máximo.")
        self.paises_presenciales_extra = [c for c in self.paises_presenciales_extra if c != self.vive_en]
        if self.ubicaciones:
            self._campos_desde_filas()
        return self

    @property
    def filas(self):
        """Contrato v30: las filas de ubicación; las de un perfil anterior se arman con sus campos (sin guardarlas,
        para que quien edite esos campos siga viendo su efecto)."""
        return self.ubicaciones or self._filas_desde_campos()

    def _filas_desde_campos(self):
        """Contrato v30: un perfil anterior en filas, con el mismo resultado que tenía. Fila 1: donde vive, con sus
        modalidades y ciudades. Fila 2: los países a los que se mudaría (híbrido/presencial). Fila 3: los países donde
        puede trabajar legalmente (remoto)."""
        filas = [Ubicacion(paises=[self.vive_en], ciudades=self.ciudades, modalidades=self.modalidades)]
        presencial = [m for m in self.modalidades if m != "remoto"]
        if self.paises_presenciales_extra and presencial:
            filas.append(Ubicacion(paises=self.paises_presenciales_extra, ciudades=self.ciudades,
                                   modalidades=presencial))
        if self.puede_trabajar_en and "remoto" in self.modalidades:
            filas.append(Ubicacion(paises=self.puede_trabajar_en, modalidades=["remoto"]))
        return filas

    def _campos_desde_filas(self):
        primera = self.ubicaciones[0]
        if primera.paises:
            self.vive_en = primera.paises[0]
        self.modalidades = [m for m in MODOS if any(m in f.modalidades for f in self.ubicaciones)]
        self.ciudades = list(dict.fromkeys(c for f in self.ubicaciones for c in f.ciudades))[:10]
        self.paises_presenciales_extra = list(dict.fromkeys(
            c for f in self.ubicaciones if {"hibrido", "presencial"} & set(f.modalidades) for c in f.paises
            if c != self.vive_en))[:60]
        self.puede_trabajar_en = list(dict.fromkeys(
            c for f in self.ubicaciones if "remoto" in f.modalidades for c in f.paises if c != self.vive_en))[:60]


class Configuracion(Modelo):
    clientes: list[Cliente] = Field(default_factory=list, max_length=250)
    cargos: list[Cargo] = Field(default_factory=list, max_length=100)
    perfiles: list[Perfil] = Field(default_factory=list, max_length=1000)
    # Contrato v21: máximo de vacantes del día. Los clientes reales se llenan primero; lo que sobra va a Comunidad.
    techo_diario: int = Field(default=120, ge=1, le=TECHO_MAXIMO)

    @model_validator(mode="after")
    def coherencia(self):
        for filas in (self.clientes, self.cargos, self.perfiles):
            if len({v.id for v in filas}) != len(filas):
                raise ValueError("Hay identificadores repetidos.")
        clientes, cargos = {c.id for c in self.clientes}, {c.id for c in self.cargos}
        if any(p.cliente_id not in clientes or p.cargo_id not in cargos for p in self.perfiles):
            raise ValueError("Cada perfil debe pertenecer a un cliente y un cargo existentes.")
        nombres = [" ".join(c.nombre.casefold().replace("-", " ").split()) for c in self.cargos if c.activo]
        if len(nombres) != len(set(nombres)):
            raise ValueError("Usa un solo cargo compartido para los clientes del mismo oficio.")
        # Un borrador puede pasar el techo mientras se edita; programar no (`validar_publicacion`).
        return self.aplicar_metas()

    def _activos(self):
        clientes = {c.id: c for c in self.clientes if c.activo}
        cargos = {c.id for c in self.cargos if c.activo}
        return [p for p in self.perfiles if p.activo and p.cliente_id in clientes and p.cargo_id in cargos], clientes

    def aplicar_metas(self):
        """Contrato v21. 1) Perfil sin meta (configuración anterior): reparte el cupo antiguo de su cargo entre los
        perfiles activos de ese cargo que no tienen meta. 2) El cupo de cada cargo pasa a ser la suma de las metas de
        sus perfiles reales más la parte de Comunidad que cabe bajo el techo. El motor sigue eligiendo por cargo."""
        activos, clientes = self._activos()
        ids_activos = {p.id for p in activos}
        for c in self.cargos:
            sin_meta = [p for p in activos if p.cargo_id == c.id and p.meta_diaria is None]
            if sin_meta:
                base, resto = divmod(c.cupo, len(sin_meta))
                for i, p in enumerate(sin_meta):
                    p.meta_diaria = base + (1 if i < resto else 0)
        for p in self.perfiles:
            if p.meta_diaria is None:
                p.meta_diaria = 0 if p.id not in ids_activos else META_POR_DEFECTO
        reales = sum(p.meta_diaria for p in activos if not clientes[p.cliente_id].comunidad)
        comunidad = sum(p.meta_diaria for p in activos if clientes[p.cliente_id].comunidad)
        factor = min(1.0, max(0, self.techo_diario - reales) / comunidad) if comunidad else 0
        for c in self.cargos:
            de_cargo = [p for p in activos if p.cargo_id == c.id]
            c.cupo = min(TECHO_MAXIMO, sum(p.meta_diaria for p in de_cargo if not clientes[p.cliente_id].comunidad) +
                         int(sum(p.meta_diaria for p in de_cargo if clientes[p.cliente_id].comunidad) * factor)) \
                if c.activo else 0
        return self

    def metas(self):
        """Sumas de metas activas: clientes reales, Comunidad, lo que Comunidad recibe bajo el techo y lo libre."""
        activos, clientes = self._activos()
        reales = sum(p.meta_diaria or 0 for p in activos if not clientes[p.cliente_id].comunidad)
        comunidad = sum(p.meta_diaria or 0 for p in activos if clientes[p.cliente_id].comunidad)
        cabe = min(comunidad, max(0, self.techo_diario - reales))
        return {"techo": self.techo_diario, "reales": reales, "comunidad": comunidad, "comunidad_cabe": cabe,
                "libre": max(0, self.techo_diario - reales - cabe)}

    @property
    def total(self):
        return sum(c.cupo for c in self.cargos if c.activo)

    def perfiles_activos(self, cargo_id=None):
        clientes = {c.id for c in self.clientes if c.activo}
        cargos = {c.id for c in self.cargos if c.activo}
        # Contrato v21: cuenta el perfil activo con meta; un cargo sin meta en ningún perfil no busca.
        return [p for p in self.perfiles if p.activo and p.cliente_id in clientes and p.cargo_id in cargos
                and (p.meta_diaria or 0) > 0
                and (cargo_id is None or str(p.cargo_id) == str(cargo_id))]

    def validar_publicacion(self):
        reales = self.metas()["reales"]
        if reales > self.techo_diario:
            raise ValueError(f"Las metas de los clientes suman {reales} y el techo diario es {self.techo_diario}: "
                             "baja algunas metas o sube el techo antes de programar.")
        if self.total <= 0:
            raise ValueError("Ningún perfil activo tiene meta diaria: da una meta a algún perfil antes de programar.")
        if self.total > self.techo_diario:
            raise ValueError(f"Las metas suman {self.total} y el techo diario es {self.techo_diario}.")
        return self


_MOTIVOS_CAMPO = {
    ("clientes", "nombre"): "Escribe el nombre del cliente.",
    ("cargos", "nombre"): "Escribe el nombre del cargo (al menos 2 letras).",
    ("cargos", "cupo"): "El cupo de cada cargo va de 0 a 600.",
    ("perfiles", "meta_diaria"): "La meta diaria de cada perfil va de 0 a 120 vacantes.",
    ("perfiles", "restricciones"): "Revisa las restricciones del perfil: monto mayor que 0, moneda y al menos una palabra o tipo.",
    ("perfiles", "sectores_preferidos"): "Cada sector preferido debe tener entre 2 y 60 caracteres.",
    ("perfiles", "palabras_preferidas"): "Cada palabra preferida debe tener entre 2 y 60 caracteres.",
    ("techo_diario",): "El techo diario va de 1 a 600 vacantes.",
    ("perfiles", "modalidades"): "Elige al menos una modalidad: remoto, híbrido o presencial.",
    ("perfiles", "idiomas"): "Elige al menos un idioma de los avisos: español o inglés.",
    ("perfiles", "experiencia_min"): "Los años de experiencia van de 0 a 40.",
    ("perfiles", "experiencia_max"): "Los años de experiencia van de 0 a 40.",
    ("perfiles", "experiencia_anos"): "Los años de experiencia van de 0 a 40.",
    ("perfiles", "antiguedad_dias"): "La antigüedad de publicación va de 1 a 30 días.",
    ("perfiles", "vive_en"): "Elige en qué país vive.",
    ("perfiles", "ciudades"): "Cada ciudad debe tener entre 2 y 60 caracteres.",
    ("perfiles", "puede_trabajar_en"): "Elige países de la lista donde puede trabajar.",
    ("perfiles", "paises"): "Elige países de la lista en cada ubicación.",
    ("perfiles", "ubicaciones"): "Revisa las ubicaciones del perfil: hasta 10 filas, cada una con país o ciudad.",
    ("perfiles", "cargo_id"): "Elige un cargo para el perfil.",
}


def explicar(error):
    """Qué falta en un borrador que no valida, en una frase para el operador (sección 4, 13 nov). Sin nombres de
    clientes: la respuesta solo repite reglas."""
    for e in error.errors() if isinstance(error, ValidationError) else []:
        mensaje = e.get("msg", "")
        if mensaje.startswith("Value error, "):  # mensajes propios, ya en español
            return mensaje.removeprefix("Value error, ")
        nombres = [x for x in e.get("loc", ()) if isinstance(x, str)]
        return _MOTIVOS_CAMPO.get((nombres[0], nombres[-1]) if nombres else (), "Revisa los campos del perfil.")
    return str(error) if isinstance(error, ValueError) and not isinstance(error, ValidationError) else \
        "Revisa los campos del perfil."


def solo_perfil(datos, perfil_id):
    """Configuración mínima con el perfil, su cliente y su cargo: para estimar un perfil no hace falta que el resto del
    borrador esté completo (cupos que aún no suman, otro cliente a medio escribir)."""
    datos = datos if isinstance(datos, dict) else {}
    perfil = next((p for p in datos.get("perfiles") or [] if isinstance(p, dict) and str(p.get("id")) == str(perfil_id)),
                  None)
    if perfil is None:
        raise ValueError("Este perfil no está en el borrador: vuelve a abrir el cliente.")
    cliente = [c for c in datos.get("clientes") or [] if isinstance(c, dict) and str(c.get("id")) == str(perfil.get("cliente_id"))]
    cargo = [c for c in datos.get("cargos") or [] if isinstance(c, dict) and str(c.get("id")) == str(perfil.get("cargo_id"))]
    if not cargo:
        raise ValueError("Elige un cargo para el perfil.")
    return Configuracion.model_validate({"clientes": cliente[:1], "cargos": cargo[:1], "perfiles": [perfil]})


def parcial(datos):
    """Sección 7a (13 nov): `(Configuracion, {perfil_id: motivo})` con lo que sí valida de un borrador a medio editar.
    Un dato pendiente en otro cliente o cargo ya no deja sin estimación a los perfiles completos. Cada cliente, cargo y
    perfil se valida por separado; la coherencia entre ellos se comprueba perfil a perfil con `solo_perfil`. Devuelve
    `None` como configuración si ningún perfil valida."""
    datos = datos if isinstance(datos, dict) else {}
    clientes, cargos, perfiles, incompletos = {}, {}, {}, {}
    for clase, filas, destino in ((Cliente, datos.get("clientes"), clientes), (Cargo, datos.get("cargos"), cargos)):
        for fila in filas or []:
            try:
                x = clase.model_validate(fila)
            except ValueError:
                continue
            destino.setdefault(x.id, x)
    for fila in datos.get("perfiles") or []:
        pid = str(fila.get("id", "")) if isinstance(fila, dict) else ""
        if not pid or pid in perfiles or pid in incompletos:
            continue
        try:
            mini = solo_perfil(datos, pid)
        except ValueError as e:
            incompletos[pid] = explicar(e)
            continue
        p = mini.perfiles[0]
        if p.cliente_id not in clientes or p.cargo_id not in cargos:
            incompletos[pid] = "Revisa el nombre del cliente y el cargo del perfil."
            continue
        perfiles[pid] = p
    if not perfiles:
        return None, incompletos
    techo = datos.get("techo_diario")
    cfg = Configuracion.model_construct(clientes=list(clientes.values()), cargos=list(cargos.values()),
                                        perfiles=list(perfiles.values()),
                                        techo_diario=techo if isinstance(techo, int) and 1 <= techo <= TECHO_MAXIMO else 120)
    return cfg.aplicar_metas(), incompletos


class Guardar(Modelo):
    revision: int = Field(ge=0, strict=True)
    configuracion: Configuracion


class Publicar(Modelo):
    revision: int = Field(ge=0, strict=True)


class EnVivo(Modelo):
    """Borrador sin guardar y el perfil que se quiere estimar con una búsqueda corta en las fuentes públicas."""
    configuracion: dict
    perfil_id: str = Field(min_length=1, max_length=64)


class VistaPrevia(Modelo):
    """Borrador sin guardar que se quiere estimar; no se persiste. Se valida en el endpoint: mientras se edita puede
    estar incompleto y eso no es un error del servidor."""
    configuracion: dict


class Expansion(Modelo):
    cargo: str = Field(min_length=2, max_length=120)

    @field_validator("cargo")
    @classmethod
    def sin_contactos(cls,v):
        return Cargo.nombre_cargo(v)


class Credenciales(Modelo):
    email: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=1,max_length=256)


class Contacto(Modelo):
    """Contrato v10: WhatsApp de un cliente. Fuera de la configuración versionada; tabla privada."""
    telefono: str = Field(max_length=25)
    nombre_saludo: str = Field(default="", max_length=60)
    consentimiento: bool = False

    @field_validator("telefono")
    @classmethod
    def telefono_valido(cls, v):
        from panel.borradores import normalizar_telefono
        return normalizar_telefono(v)

    @field_validator("nombre_saludo")
    @classmethod
    def saludo(cls, v):
        v = " ".join(v.split())
        if "@" in v or "://" in v:
            raise ValueError("Escribe solo el nombre con el que saludas.")
        return v


class CambioBorrador(Modelo):
    texto: str | None = Field(default=None, min_length=1, max_length=4000)
    estado: Literal["pendiente", "abierto", "enviado", "descartado"] | None = None


class DecisionRevision(Modelo):
    """Contrato v16: decisión del operador en la bandeja «Por confirmar»."""
    decision: Literal["sirve", "otro_pais", "no_sirve", "saltar"]
    paises: list[str] = Field(default_factory=list, max_length=21)
    aplicar_a_iguales: bool = False


class SubirRevision(Modelo):
    """Contrato v17: CSV de revisión masiva llenado por el operador."""
    contenido: str = Field(min_length=1, max_length=2_000_000)


class ImportarClientes(Modelo):
    """Importar clientes desde un CSV (15 nov): el archivo y qué hacer con los clientes actuales."""
    contenido: str = Field(min_length=1, max_length=2_000_000)
    actuales: Literal["mantener", "archivar", "borrar"] = "mantener"
    revision: int | None = Field(default=None, ge=0)
    confirmacion: str = Field(default="", max_length=20)


class BorrarCliente(Modelo):
    revision: int = Field(ge=0)
    confirmacion: str = Field(max_length=20)


class EstadoRegla(Modelo):
    texto: str = Field(min_length=2, max_length=300)
    activa: bool
