export type Cliente = {
  id: string;
  nombre: string;
  activo: boolean;
  comunidad?: boolean;
};
export type Cargo = {
  id: string;
  nombre: string;
  cupo: number;
  activo: boolean;
  terminos_exactos: string[];
  terminos_similares: string[];
  terminos_excluidos: string[];
  terminos_cercanos?: string[];
  funciones?: string[];
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
  experiencia_anos?: number | null;
  aceptar_experiencia_sin_dato: boolean;
  aceptar_ingles_sin_dato: boolean;
  meta_diaria?: number | null;
  margen_experiencia?: 3 | 4;
  restricciones?: Restriccion[];
  sectores_preferidos?: string[];
  palabras_preferidas?: string[];
  ciudades?: string[];
  puede_trabajar_en?: string[];
  acepta_horario?: string[];
  // Contrato v30: dónde trabajaría, en filas; la primera es donde vive.
  ubicaciones?: Ubicacion[];
};
export type Ubicacion = {
  paises: string[];
  ciudades: string[];
  modalidades: string[];
};
// Contrato v22: «Este perfil NO acepta…». Cada regla descarta solo con evidencia clara en el aviso.
export type Restriccion =
  | { tipo: "salario_minimo"; monto: number; moneda: string; periodo: string }
  | { tipo: "palabras"; palabras: string[] }
  | { tipo: "contrato"; tipos: string[] };
export type Configuracion = {
  clientes: Cliente[];
  cargos: Cargo[];
  perfiles: Perfil[];
  techo_diario?: number;
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
  entregada_el?: string;
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
  avisos?: string[];
  ampliacion?: string;
  tipo?: string;
  post_ubicacion?: string;
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
  paises_mundo?: { codigo: string; nombre: string }[];
  // Contrato v30: prefijo telefónico → país, para mostrar la bandera del WhatsApp.
  prefijos?: Record<string, string>;
};
type Limitante = {
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
  motivo?: string;
  incompletos?: Record<string, string>;
  catalogo?: { vacantes: number; actualizado: string };
  perfiles?: Record<string, EstimacionPerfil>;
  cargos?: Record<string, EstimacionCargo>;
  nota?: string;
};
export type EstimacionEnVivo = {
  incompleto?: boolean;
  motivo?: string;
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
  filtros_que_cortan?: Record<string, number>;
  de_su_busqueda?: number;
  de_la_amplia?: number;
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
  // Ampliación v17: respuesta sugerida por código y su motivo ("" = hay que leerla).
  sugerida?: "" | "sirve" | "otro_pais" | "no_sirve";
  paises_sugeridos?: string[];
  por_que?: string;
  frase?: string;
  clientes: string[];
  cliente_ids?: string[];
  ayuda_faltantes: boolean;
  iguales: number;
  motivo?: string;
  funciones?: boolean;
  // Contrato v29: entre las 10 más útiles de hoy.
  mas_util?: boolean;
};
export type Revisiones = {
  pendientes: Revision[];
  total: number;
  en_espera?: number;
  ayudan_faltantes: number;
  // Contrato v29: todas las pendientes por páginas.
  pagina?: number;
  paginas?: number;
  por_pagina?: number;
  por_cliente?: Record<string, number>;
};
// Contrato v29: ficha de una vacante, con la descripción en bloques de texto (sin HTML).
export type BloqueFicha = { tipo: "p" | "li" | "h"; texto: string };
export type FichaVacante = {
  id: string;
  titulo: string;
  empresa: string;
  ubicacion: string;
  modalidad: string;
  salario: string;
  publicada: string;
  anos_min: number | null;
  ingles: string;
  nivel: string;
  enlace: string;
  enlace_directo: string;
  tipo: string;
  activa: boolean;
  bloques: BloqueFicha[];
  origen: "guardada" | "traida" | "sin_descripcion";
};
// Contrato v17: reglas de ubicación (del operador o aprendidas por código).
export type Regla = {
  texto: string;
  origen: string;
  activa: boolean;
  usos: number;
  conflictos: number;
  resultado: string;
  ejemplos: string[];
};
// Paso 8 (15 nov): recibidas de cada cliente en sus últimas búsquedas (solo conteos por id).
export type ResumenClientes = {
  fecha: string;
  busqueda_de_hoy: boolean;
  dias: { fecha: string; estado: string; clientes: Record<string, number> }[];
};
// Importar clientes desde un CSV (15 nov): la vista previa que devuelve el servidor (no guarda nada).
export type PreviaImportacion = {
  filas: {
    fila: number;
    cliente: string;
    cargo: string;
    vive_en: string;
    modalidades: string[];
    meta: number | null;
    estado: "actualiza" | "nuevo";
    errores: string[];
    avisos: string[];
  }[];
  errores: number;
  error_general: string;
  columnas_desconocidas: string[];
  clientes: number;
  perfiles: number;
  actualizados: string[];
  nuevos: string[];
  cargos_nuevos: string[];
  borrar: string[];
  archivar: string[];
  metas: { techo: number; reales: number } | null;
  excede_techo: boolean;
};
