// Pruebas del motor de la página: node --test pruebas/
const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../web/motor.js");

const MAPA = M.prepararMapa([
  { id: "diseno-producto-ux", nombre: "Diseño de producto y UX/UI", area: "Diseño",
    exactos: ["product designer", "product design", "diseñador ux/ui", "ux designer", "ui designer"],
    similares: ["interaction designer", "ux researcher"], cercanos: ["product owner"] },
  { id: "ux-research", nombre: "UX Research", area: "Diseño", exactos: ["ux researcher"], similares: [], cercanos: ["product designer"] },
  { id: "edicion-video", nombre: "Edición de video", area: "Video y audio", exactos: ["editor de video", "video editor"],
    similares: ["editor de reels", "motion graphics"], cercanos: [] },
  { id: "backend", nombre: "Desarrollo backend", area: "Desarrollo", exactos: ["backend developer", "desarrollador backend"],
    similares: ["java developer"], cercanos: [] },
]);

const V = (o) => ({ id: o.id, titulo: o.titulo, empresa: o.empresa || "Acme", paises: o.paises || ["CO"], modalidad: o.modalidad || "presencial",
  confianza_pais: o.confianza || "alta", familias: o.familias || [], fecha_publicacion: o.fecha || "2026-10-27", visto_primera_vez: "2026-10-27",
  idioma: o.idioma || "es", ingles: o.ingles || "", nivel: o.nivel || "", tipo_enlace: o.tipo || "portal",
  enlace: `https://www.linkedin.com/jobs/view/${o.id}`, ubicacion: o.ubicacion || "Bogotá, Colombia", fuentes: ["LinkedIn"] });

const VACANTES = [
  V({ id: "1", titulo: "Senior Product Designer", familias: [{ familia: "diseno-producto-ux", coincidencia: "exacto" }], nivel: "senior" }),
  V({ id: "2", titulo: "Product Owner", familias: [{ familia: "diseno-producto-ux", coincidencia: "cercano" }], fecha: "2026-10-28" }),
  V({ id: "3", titulo: "Interaction Designer", modalidad: "remoto", paises: ["CO", "VE", "MX"],
    familias: [{ familia: "diseno-producto-ux", coincidencia: "similar" }], ingles: "avanzado", idioma: "en" }),
  V({ id: "4", titulo: "Editor de video", paises: ["VE"], ubicacion: "Caracas, Venezuela", familias: [{ familia: "edicion-video", coincidencia: "exacto" }] }),
  V({ id: "5", titulo: "Product Designer", fecha: "2026-09-10", familias: [{ familia: "diseno-producto-ux", coincidencia: "exacto" }] }),
  V({ id: "6", titulo: "Diseñador Webflow", familias: [] }),
];

test("normaliza como el Python: sin tildes, sin nivel", () => {
  assert.equal(M.base("Diseñador(a) UX/UI Senior"), "disenador a ux/ui");
  assert.equal(M.base("Lead Product Designer - Remote"), "product designer");
  assert.ok(M.contieneFrase("senior ux designer", "ux designer"));
  assert.ok(!M.contieneFrase("linux engineer", "ux"));
});

test("sugiere la familia por cualquier término", () => {
  assert.equal(M.sugerir("product design", MAPA)[0].id, "diseno-producto-ux");
  assert.equal(M.sugerir("UX", MAPA)[0].id, "diseno-producto-ux");
  assert.equal(M.sugerir("ux researcher", MAPA)[0].id, "ux-research");
  assert.equal(M.sugerir("editor de video senior", MAPA)[0].id, "edicion-video");
  assert.equal(M.sugerir("motion", MAPA)[0].id, "edicion-video");
  assert.equal(M.sugerir("desarrollador backend", MAPA)[0].id, "backend");
  assert.deepEqual(M.sugerir("cocinero", MAPA), []);
});

test("filtra por familia, grado, país, modalidad y antigüedad", () => {
  const base = { familias: ["diseno-producto-ux"], hoy: "2026-10-28", dias: 30 };
  assert.deepEqual(M.filtrar(VACANTES, base).map(v => v.id), ["1", "2", "3"]);           // la 5 tiene 48 días
  assert.deepEqual(M.filtrar(VACANTES, { ...base, grados: ["exacto", "similar"] }).map(v => v.id), ["1", "3"]);
  assert.deepEqual(M.filtrar(VACANTES, { ...base, pais: "VE" }).map(v => v.id), ["3"]);
  assert.deepEqual(M.filtrar(VACANTES, { ...base, remotas: false }).map(v => v.id), ["1", "2"]);
  assert.deepEqual(M.filtrar(VACANTES, { ...base, presenciales: false }).map(v => v.id), ["3"]);
  assert.deepEqual(M.filtrar(VACANTES, { ...base, ingles: "hasta-intermedio" }).map(v => v.id), ["1", "2"]);
  assert.deepEqual(M.filtrar(VACANTES, { ...base, excluir: ["owner"] }).map(v => v.id), ["1", "3"]);
  assert.deepEqual(M.filtrar(VACANTES, { ...base, enviadas: new Set(["1"]), ocultarEnviadas: true }).map(v => v.id), ["2", "3"]);
  assert.equal(M.filtrar(VACANTES, base)[2]._grado, "similar");
});

test("busca por palabras sueltas cuando el cargo no está en el mapa", () => {
  const r = M.filtrar(VACANTES, { palabras: ["webflow"], hoy: "2026-10-28", dias: 30 });
  assert.deepEqual(r.map(v => v.id), ["6"]);
  assert.equal(r[0]._grado, "palabra");
});

test("ordena por coincidencia y fecha, sin más de 3 seguidas de la misma empresa", () => {
  const r = M.ordenar(M.filtrar(VACANTES, { familias: ["diseno-producto-ux"], hoy: "2026-10-28", dias: 30 }));
  assert.deepEqual(r.map(v => v.id), ["1", "3", "2"]);
  const muchas = ["a", "b", "c", "d"].map((x, i) => ({ ...V({ id: x, titulo: "UX Designer", empresa: "Repetida" }), _grado: "exacto" }))
    .concat([{ ...V({ id: "z", titulo: "UX Designer", empresa: "Otra", fecha: "2026-10-01" }), _grado: "exacto" }]);
  assert.deepEqual(M.ordenar(muchas).map(v => v.empresa), ["Repetida", "Repetida", "Repetida", "Otra", "Repetida"]);
});

test("texto para WhatsApp en mensajes de 15", () => {
  const nombres = { CO: "Colombia", VE: "Venezuela", MX: "México" };
  const lista = M.filtrar(VACANTES, { familias: ["diseno-producto-ux"], hoy: "2026-10-28", dias: 30 });
  const [msg] = M.textoWhatsApp(lista, { titulo: "Product Designer", lugar: "Colombia y remoto", fecha: "28 oct", hoy: "2026-10-28", nombres, totalPaises: 20 });
  assert.ok(msg.startsWith("*Vacantes de Product Designer · Colombia y remoto · 28 oct*"));
  assert.ok(msg.includes("*Interaction Designer* — Acme\nRemoto · Colombia, Venezuela y México · Inglés avanzado · ayer"));
  assert.ok(msg.includes("https://www.linkedin.com/jobs/view/1"));
  const muchas = Array.from({ length: 31 }, (_, i) => V({ id: String(i), titulo: "UX Designer" }));
  assert.equal(M.textoWhatsApp(muchas, { titulo: "UX", fecha: "28 oct", hoy: "2026-10-28" }).length, 3);
});

test("filas del Excel con encabezados en español", () => {
  const filas = M.filasExcel(M.filtrar(VACANTES, { familias: ["edicion-video"], hoy: "2026-10-28", dias: 30 }), { VE: "Venezuela" }, 20);
  assert.equal(filas[0][0], "Cargo");
  assert.equal(filas[1][0], "Editor de video");
  assert.equal(filas[1][3], "Venezuela");
  assert.equal(filas[1][13], "https://www.linkedin.com/jobs/view/4");
});

test("fechas relativas", () => {
  assert.equal(M.fechaRelativa("2026-10-28", "2026-10-28"), "hoy");
  assert.equal(M.fechaRelativa("2026-10-27", "2026-10-28"), "ayer");
  assert.equal(M.fechaRelativa("2026-10-20", "2026-10-28"), "hace 8 días");
  assert.equal(M.fechaRelativa("", "2026-10-28"), "fecha sin confirmar");
});
