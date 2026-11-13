"""Validación del mismo contrato para API, demostración y ejecutor."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from buscador import paises


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cliente(Modelo):
    id: UUID
    nombre: str = Field(min_length=1, max_length=100)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, v):
        if not v.strip():
            raise ValueError("Escribe un nombre.")
        return v.strip()


class Cargo(Modelo):
    id: UUID
    nombre: str = Field(min_length=2, max_length=120)
    cupo: int = Field(default=20, ge=0, le=120, strict=True)
    activo: bool = True
    terminos_exactos: list[str] = Field(default_factory=list, max_length=30)
    terminos_similares: list[str] = Field(default_factory=list, max_length=30)
    terminos_excluidos: list[str] = Field(default_factory=list, max_length=30)
    terminos_cercanos: list[str] = Field(default_factory=list, max_length=30)  # contrato v9: solo para ampliar

    @field_validator("nombre")
    @classmethod
    def nombre_cargo(cls, v):
        v = " ".join(v.split())
        if len(v) < 2 or "@" in v or "://" in v:
            raise ValueError("Escribe un cargo, sin enlaces ni datos de contacto.")
        return v

    @field_validator("terminos_exactos", "terminos_similares", "terminos_excluidos", "terminos_cercanos")
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


class Perfil(Modelo):
    id: UUID
    cliente_id: UUID
    cargo_id: UUID
    activo: bool = True
    # Contrato v8: dónde vive y qué modalidades acepta (docs/CONTRATO_DATOS_v8.md).
    vive_en: str = "CO"
    modalidades: list[Literal["remoto", "hibrido", "presencial"]] = Field(default_factory=lambda: ["remoto"],
                                                                        min_length=1, max_length=3)
    paises_presenciales_extra: list[str] = Field(default_factory=list, max_length=21)
    antiguedad_dias: int = Field(default=14, ge=1, le=30)
    idiomas: list[Literal["es", "en"]] = Field(default_factory=lambda: ["es", "en"], min_length=1, max_length=2)
    ingles_maximo: Literal["sin_filtro", "A1", "A2", "B1", "B2", "C1", "C2", "native"] = "sin_filtro"
    experiencia_min: int | None = Field(default=None, ge=0, le=40)
    experiencia_max: int | None = Field(default=None, ge=0, le=40)
    aceptar_experiencia_sin_dato: bool = False
    aceptar_ingles_sin_dato: bool = False

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
        if v not in paises.datos()["reconocidos"]:  # un perfil guardado con Brasil se sigue leyendo (contrato v12)
            raise ValueError("La cobertura actual es LATAM y España.")
        return v

    @field_validator("paises_presenciales_extra")
    @classmethod
    def cobertura(cls, vs):
        if not set(vs) <= set(paises.datos()["reconocidos"]):
            raise ValueError("La cobertura actual es LATAM y España.")
        return list(dict.fromkeys(vs))

    @field_validator("modalidades")
    @classmethod
    def sin_repetir(cls, vs):
        return list(dict.fromkeys(vs))

    @property
    def paises_oficina(self):
        """Países donde aceptaría trabajo híbrido o presencial."""
        return list(dict.fromkeys([self.vive_en, *self.paises_presenciales_extra]))

    @model_validator(mode="after")
    def rango(self):
        if self.experiencia_min is not None and self.experiencia_max is not None and self.experiencia_min > self.experiencia_max:
            raise ValueError("El mínimo de experiencia no puede superar al máximo.")
        self.paises_presenciales_extra = [c for c in self.paises_presenciales_extra if c != self.vive_en]
        return self


class Configuracion(Modelo):
    clientes: list[Cliente] = Field(default_factory=list, max_length=250)
    cargos: list[Cargo] = Field(default_factory=list, max_length=100)
    perfiles: list[Perfil] = Field(default_factory=list, max_length=1000)

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
        if self.total > 120:
            raise ValueError("Los cupos activos no pueden superar las 120 vacantes.")
        return self

    @property
    def total(self):
        return sum(c.cupo for c in self.cargos if c.activo)

    def perfiles_activos(self, cargo_id=None):
        clientes = {c.id for c in self.clientes if c.activo}
        cargos = {c.id for c in self.cargos if c.activo and c.cupo > 0}
        return [p for p in self.perfiles if p.activo and p.cliente_id in clientes and p.cargo_id in cargos
                and (cargo_id is None or str(p.cargo_id) == str(cargo_id))]

    def validar_publicacion(self):
        if self.total != 120:
            raise ValueError("Reparte exactamente 120 vacantes antes de programar la búsqueda.")
        if any(not self.perfiles_activos(c.id) for c in self.cargos if c.activo and c.cupo):
            raise ValueError("Cada cargo con cupo necesita al menos un perfil de cliente activo.")
        return self


_MOTIVOS_CAMPO = {
    ("clientes", "nombre"): "Escribe el nombre del cliente.",
    ("cargos", "nombre"): "Escribe el nombre del cargo (al menos 2 letras).",
    ("cargos", "cupo"): "El cupo de cada cargo va de 0 a 120.",
    ("perfiles", "modalidades"): "Elige al menos una modalidad: remoto, híbrido o presencial.",
    ("perfiles", "idiomas"): "Elige al menos un idioma de los avisos: español o inglés.",
    ("perfiles", "experiencia_min"): "Los años de experiencia van de 0 a 40.",
    ("perfiles", "experiencia_max"): "Los años de experiencia van de 0 a 40.",
    ("perfiles", "antiguedad_dias"): "La antigüedad de publicación va de 1 a 30 días.",
    ("perfiles", "vive_en"): "Elige en qué país vive: LATAM o España.",
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
    return Configuracion.model_construct(clientes=list(clientes.values()), cargos=list(cargos.values()),
                                         perfiles=list(perfiles.values())), incompletos


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


class AjustesAlertas(Modelo):
    """Contrato v10: a quién y qué alertas por correo. Se guarda aparte de la configuración versionada."""
    destinatarios: list[str] = Field(default_factory=list, max_length=5)
    tipos: list[Literal["exito", "pocas_vacantes", "fallo"]] = Field(
        default_factory=lambda: ["exito", "pocas_vacantes", "fallo"])

    @model_validator(mode="after")
    def correos(self):
        from buscador.alertas import configuracion_valida
        limpio = configuracion_valida(self.model_dump())
        self.destinatarios, self.tipos = limpio["destinatarios"], limpio["tipos"]
        return self


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


class EstadoRegla(Modelo):
    texto: str = Field(min_length=2, max_length=300)
    activa: bool
