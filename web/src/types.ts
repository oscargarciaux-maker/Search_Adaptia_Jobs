export type Cliente = { id: string; nombre: string; activo: boolean };
export type Cargo = {
  id: string;
  nombre: string;
  cupo: number;
  activo: boolean;
  terminos_exactos: string[];
  terminos_similares: string[];
  terminos_excluidos: string[];
  terminos_cercanos?: string[];
};
export type Perfil = {
  id: string;
  cliente_id: string;
  cargo_id: string;
  activo: boolean;
  vive_en: string;
  modalidades: string[];
  paises_presenciales_extra: string[];
  antiguedad_dias: number;
  idiomas: string[];
  ingles_maximo: string;
  experiencia_min: number | null;
  experiencia_max: number | null;
  aceptar_experiencia_sin_dato: boolean;
  aceptar_ingles_sin_dato: boolean;
};
export type Configuracion = {
  clientes: Cliente[];
  cargos: Cargo[];
  perfiles: Perfil[];
};
export type EstadoConfig = {
  revision: number;
  borrador: Configuracion;
  publicada: {
    revision: number;
    vigente_desde: string;
    configuracion: Configuracion;
  } | null;
};
export type Ejecucion = {
  id: string;
  fecha: string;
  estado: string;
  iniciada_en: string;
  terminada_en: string | null;
  resumen: {
    vacantes?: number;
    meta?: number;
    faltantes?: Record<string, number>;
    asignaciones?: number;
    ampliadas?: number;
    perfiles_bajo_minimo?: number;
    embudo?: Record<string, Embudo>;
  };
};
export type Vacante = {
  id: string;
  titulo: string;
  empresa: string;
  ubicacion: string;
  modalidad: string;
  idioma: string;
  publicada: string;
  experiencia: number | null;
  match_grade: string;
  explicacion: (
    | string
    | {
        regla?: string;
        termino?: string;
        ampliacion?: string;
        tipo?: string;
        reutilizada?: string;
      }
  )[];
  cargo_id: string;
  enlace: string;
  estado: string;
  motivos: string[];
  ampliacion?: string;
  tipo?: string;
  contacto?: { perfil?: string; correo?: string };
};
export type Resultados = {
  ejecucion: Ejecucion | null;
  clientes: Cliente[];
  vacantes: Vacante[];
  listas: number;
};
export type Sesion = {
  demo: boolean;
  sesion: boolean;
  paises: { codigo: string; nombre: string }[];
};
export type Limitante = {
  motivo: string;
  vacantes: number;
  sugerencia: string;
};
export type EstimacionPerfil = {
  compatibles: number;
  del_cargo: number;
  limitantes: Limitante[];
  ampliables?: number;
};
export type EstimacionCargo = {
  disponibles: number;
  del_cargo: number;
  cupo: number;
  estado: "alcanza" | "justo" | "insuficiente" | "sin_cupo";
  solapes?: { cargo: string; vacantes: number }[];
};
export type VistaPrevia = {
  incompleto?: boolean;
  catalogo?: { vacantes: number; actualizado: string };
  perfiles?: Record<string, EstimacionPerfil>;
  cargos?: Record<string, EstimacionCargo>;
  nota?: string;
};
export type EstimacionEnVivo = {
  incompleto?: boolean;
  ocupado?: boolean;
  espera?: number;
  error?: string;
  compatibles?: number;
  del_cargo?: number;
  nuevas?: number;
  ya_entregadas?: number;
  avisos?: number;
  limitantes?: Limitante[];
  fuentes?: Record<
    string,
    { avisos?: number; busquedas?: number; fallidas?: number; error?: boolean }
  >;
  segundos?: number;
  nota?: string;
};
export type Embudo = {
  encontradas: number;
  con_descripcion: number;
  entregables: number;
  nuevas: number;
  enlace_comprobado: number;
  cumplen_filtros: number;
  entregadas: number;
  ampliadas: number;
  principal_perdida: string;
};
export type Contacto = {
  telefono: string;
  nombre_saludo: string;
  consentimiento: boolean;
};
export type Borrador = {
  id: string;
  fecha: string;
  cliente_id: string;
  texto: string;
  vacantes: string[];
  cargos: string[];
  estado: "pendiente" | "abierto" | "enviado" | "descartado";
  editado: boolean;
  enlace: string;
  pocas: boolean;
};

// Contrato v16: bandeja «Por confirmar».
export type Revision = {
  vacante_id: string;
  titulo: string;
  empresa: string;
  ubicacion: string;
  modalidad: string;
  idioma: string;
  publicada: string;
  enlace: string;
  pista: string;
  sugerencia: string[];
  clientes: string[];
  ayuda_faltantes: boolean;
  iguales: number;
};
export type Revisiones = {
  pendientes: Revision[];
  total: number;
  ayudan_faltantes: number;
};
