export type Cliente = { id: string; nombre: string; activo: boolean };
export type Cargo = {
  id: string;
  nombre: string;
  cupo: number;
  activo: boolean;
  terminos_exactos: string[];
  terminos_similares: string[];
  terminos_excluidos: string[];
};
export type Perfil = {
  id: string;
  cliente_id: string;
  cargo_id: string;
  activo: boolean;
  paises: string[];
  modalidad: string;
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
  explicacion: (string | { regla: string; termino?: string })[];
  cargo_id: string;
  enlace: string;
  estado: string;
  motivos: string[];
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
