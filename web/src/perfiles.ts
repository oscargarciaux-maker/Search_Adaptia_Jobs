// Perfiles nuevos y metas diarias (contrato v21), compartidos por el panel y el formulario.
import type { Configuracion, Perfil, Ubicacion } from "./types";

export const uid = () => crypto.randomUUID();

export function perfilNuevo(cliente: string, cargo: string): Perfil {
  return {
    id: uid(),
    cliente_id: cliente,
    cargo_id: cargo,
    activo: true,
    vive_en: "CO",
    modalidades: ["remoto"],
    paises_presenciales_extra: [],
    ciudades: [],
    puede_trabajar_en: [],
    acepta_horario: [],
    ubicaciones: [{ paises: ["CO"], ciudades: [], modalidades: ["remoto"] }],
    antiguedad_dias: 14,
    idiomas: ["es", "en"],
    ingles_maximo: "sin_filtro",
    experiencia_min: null,
    experiencia_max: null,
    experiencia_anos: null,
    aceptar_experiencia_sin_dato: false,
    aceptar_ingles_sin_dato: false,
    meta_diaria: META_POR_DEFECTO,
    margen_experiencia: 3,
    restricciones: [],
    sectores_preferidos: [],
    palabras_preferidas: [],
  };
}

// Contrato v21: cada perfil tiene su meta diaria y el día tiene un techo. Mismo cálculo que el servidor
// (panel/modelos.py, aplicar_metas): un perfil antiguo sin meta recibe su parte del cupo anterior del cargo; el cupo
// de cada cargo es la suma de las metas reales más la parte de Comunidad que cabe bajo el techo.
export const META_POR_DEFECTO = 10;
export function conMetas(cfg: Configuracion) {
  const techo = cfg.techo_diario ?? 120;
  const clientes = new Map(
    cfg.clientes.filter((c) => c.activo).map((c) => [c.id, c]),
  );
  const cargosActivos = new Set(
    cfg.cargos.filter((c) => c.activo).map((c) => c.id),
  );
  const activos = cfg.perfiles.filter(
    (p) =>
      p.activo && clientes.has(p.cliente_id) && cargosActivos.has(p.cargo_id),
  );
  const repartida = new Map<string, number>();
  for (const c of cfg.cargos) {
    const sinMeta = activos.filter(
      (p) => p.cargo_id === c.id && p.meta_diaria == null,
    );
    sinMeta.forEach((p, i) =>
      repartida.set(
        p.id,
        Math.floor(c.cupo / sinMeta.length) +
          (i < c.cupo % sinMeta.length ? 1 : 0),
      ),
    );
  }
  const metaDe = (p: Perfil) => p.meta_diaria ?? repartida.get(p.id) ?? 0;
  const esComunidad = (p: Perfil) => !!clientes.get(p.cliente_id)?.comunidad;
  const suma = (ps: Perfil[]) => ps.reduce((s, p) => s + metaDe(p), 0);
  const reales = suma(activos.filter((p) => !esComunidad(p)));
  const comunidad = suma(activos.filter(esComunidad));
  const factor = comunidad
    ? Math.min(1, Math.max(0, techo - reales) / comunidad)
    : 0;
  const cargos = cfg.cargos.map((c) => {
    const delCargo = activos.filter((p) => p.cargo_id === c.id);
    return {
      ...c,
      cupo: c.activo
        ? suma(delCargo.filter((p) => !esComunidad(p))) +
          Math.floor(suma(delCargo.filter(esComunidad)) * factor)
        : 0,
    };
  });
  const cabe = Math.min(comunidad, Math.max(0, techo - reales));
  return {
    cargos,
    techo,
    reales,
    comunidad,
    cabe,
    libre: Math.max(0, techo - reales - cabe),
    metaDe,
    total: cargos.filter((c) => c.activo).reduce((s, c) => s + c.cupo, 0),
  };
}

// Contrato v30: las filas de ubicación. Un perfil anterior se muestra en filas con el mismo resultado (como
// `Perfil.filas` en panel/modelos.py). El servidor manda las filas y recalcula los demás campos al guardar.
const MODOS = ["remoto", "hibrido", "presencial"];
export function filasDe(p: Perfil): Ubicacion[] {
  if (p.ubicaciones?.length) return p.ubicaciones;
  const filas: Ubicacion[] = [
    {
      paises: [p.vive_en],
      ciudades: p.ciudades || [],
      modalidades: p.modalidades,
    },
  ];
  const presencial = p.modalidades.filter((m) => m !== "remoto");
  if (p.paises_presenciales_extra.length && presencial.length)
    filas.push({
      paises: p.paises_presenciales_extra,
      ciudades: p.ciudades || [],
      modalidades: presencial,
    });
  if (p.puede_trabajar_en?.length && p.modalidades.includes("remoto"))
    filas.push({
      paises: p.puede_trabajar_en,
      ciudades: [],
      modalidades: ["remoto"],
    });
  return filas;
}
// Los campos de siempre, calculados desde las filas (las regiones como «LATAM» solo las convierte el servidor).
export function conFilas(
  p: Perfil,
  filas: Ubicacion[],
  regiones: string[] = [],
): Partial<Perfil> {
  const vive = filas[0]?.paises.find((c) => !regiones.includes(c)) || p.vive_en;
  const unicos = (xs: string[]) =>
    [...new Set(xs)].filter((c) => c !== vive && !regiones.includes(c));
  return {
    ubicaciones: filas,
    vive_en: vive,
    modalidades: MODOS.filter((m) =>
      filas.some((f) => f.modalidades.includes(m)),
    ),
    ciudades: [...new Set(filas.flatMap((f) => f.ciudades))].slice(0, 10),
    paises_presenciales_extra: unicos(
      filas
        .filter((f) => f.modalidades.some((m) => m !== "remoto"))
        .flatMap((f) => f.paises),
    ),
    puede_trabajar_en: unicos(
      filas
        .filter((f) => f.modalidades.includes("remoto"))
        .flatMap((f) => f.paises),
    ),
  };
}

// Contrato v49 (decisión de Oscar): sin ciudad no llegan presenciales ni híbridas (el motor lo descarta con «falta
// la ciudad en el perfil»). El formulario lo pide en cada fila y el panel avisa en los perfiles que ya existen.
export const SIN_CIUDAD =
  "Escribe la ciudad: sin ciudad no llegan presenciales ni híbridas.";
export function filaSinCiudad(f: Ubicacion) {
  return f.modalidades.some((m) => m !== "remoto") && !f.ciudades.length;
}
export function perfilSinCiudad(p: Perfil) {
  return filasDe(p).some(filaSinCiudad);
}
