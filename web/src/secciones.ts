// Las secciones del panel y su dirección (#clientes…).
// Sección 5 (13 nov): sin menú propio; cada sección tiene su dirección y se abre desde las tarjetas del resumen.
export const secciones: Record<string, string> = {
  Resumen: "",
  Clientes: "clientes",
  "Cargos y metas": "cargos",
  Vacantes: "vacantes",
  "Por confirmar": "por-confirmar",
  Mensajes: "mensajes",
  Historial: "historial",
};
export function seccionDeHash() {
  // Contrato v29: «#vacantes/<id>» recuerda la vacante abierta; la sección es lo que va antes de la barra.
  const h = decodeURIComponent(location.hash.replace(/^#\/?/, "")).split(
    "/",
  )[0];
  // «#actividad» (nombre anterior de Historial) sigue abriendo la misma sección.
  const clave = h === "actividad" ? "historial" : h;
  return (
    Object.keys(secciones).find((t) => secciones[t] === clave) || "Resumen"
  );
}
