// Pruebas del motor de la página: node --test pruebas/
const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../web/motor.js");

test("la disponibilidad por rol caduca sin otra captura y separa el histórico", () => {
  const enlace = "https://jobs.lever.co/acme/1";
  const buena = { id: "1", afinidad_vigente: true, enlace, verificacion: { estado: "verificada", enlaces: [
    { url: enlace, estado: "verificada", comprobada_en: "2026-11-06T00:00:00Z" }] } };
  const seleccion = { roles: { qa: { nombre: "QA", meta: 20, vacantes: [buena,
    { ...buena, id: "2", afinidad_vigente: false },
    { id: "3", verificacion: { estado: "rechazada" } },
    { id: "4", afinidad_vigente: true, verificacion: { estado: "pendiente" } }] } } };
  const r = M.disponibilidadSeleccion(seleccion, "2026-11-06T05:59:59Z")[0];
  assert.deepEqual([r.seleccionadas, r.listas, r.porVerificar, r.retiradas, r.fueraPerfil, r.faltanVigentes], [4, 1, 1, 1, 1, 19]);
  const caducada = M.disponibilidadSeleccion(seleccion, "2026-11-06T06:00:00Z")[0];
  assert.equal(caducada.listas, 0);
  assert.equal(caducada.porVerificar, 2);
  assert.equal(M.disponibilidadSeleccion(seleccion, "2026-11-05T23:59:00Z")[0].listas, 0);
});

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

test("solo comparte el enlace comprobado y vigente, aunque el principal falle", () => {
  const ahora = "2026-11-05T12:00:00Z", bueno = "https://jobs.lever.co/acme/1";
  const v = { ...VACANTES[0], enlace_directo: bueno, verificacion: { estado: "verificada", enlaces: [
    { url: VACANTES[0].enlace, estado: "rechazada", comprobada_en: ahora },
    { url: bueno, estado: "verificada", comprobada_en: ahora }] } };
  assert.deepEqual(M.enlacesComprobados(v, ahora), [bueno]);
  const mensajes = M.textoWhatsApp([v], { titulo: "UX", hoy: "2026-11-05", ahora });
  assert.ok(mensajes[0].includes(bueno));
  assert.ok(!mensajes[0].includes(v.enlace));
  assert.deepEqual(M.enlacesComprobados(v, "2026-11-05T18:00:00Z"), []);
  assert.deepEqual(M.textoWhatsApp([v], { ahora: "2026-11-05T18:00:00Z" }), []);
});

test("pendientes no se comparten como enlaces comprobados y rechazadas no aparecen", () => {
  const pendiente = { ...VACANTES[0], verificacion: { estado: "pendiente", enlaces: [] } };
  assert.deepEqual(M.enlacesComprobados(VACANTES[0]), []);
  assert.deepEqual(M.textoWhatsApp([pendiente], {}), []);
  assert.equal(M.filtrar([pendiente], { soloVerificadas: true }).length, 0);
  assert.equal(M.filtrar([{ ...pendiente, verificacion: { estado: "rechazada" } }], {}).length, 0);
});

test("frescura horaria exige hora real, no primera detección ni fecha sin hora", () => {
  const exacta = { ...VACANTES[0], publicada_en: "2026-10-28T10:00:00Z" };
  const sinHora = { ...VACANTES[0], id: "sin-hora", fecha_publicacion: "2026-10-28" };
  const detectada = { ...VACANTES[0], id: "detectada", fecha_publicacion: "", fecha_estimada: true, detectada_en: "2026-10-28T11:45:00Z" };
  const op = { horas: 6, ahora: "2026-10-28T12:00:00Z" };
  assert.deepEqual(M.filtrar([exacta, sinHora, detectada], op).map(v => v.id), [exacta.id]);
  assert.equal(M.antiguedad(exacta, op.ahora, "2026-10-28"), "Publicada hace 2 h");
  assert.equal(M.antiguedad(detectada, op.ahora, "2026-10-28"), "Detectada hace 15 min");
  assert.ok(M.antiguedad(sinHora, op.ahora, "2026-10-28").includes("sin hora"));
});

test("prioriza remotas amplias sin ocultar cargos similares ni presentar países dudosos como confirmados", () => {
  const lista = M.filtrar(VACANTES, { familias: ["diseno-producto-ux"], hoy: "2026-10-28", dias: 30 });
  assert.deepEqual(M.ordenar(lista, "remotas").map(v => v.id), ["3", "1", "2"]);
  const dudosa = V({ id: "incierta", titulo: "UX Designer", modalidad: "remoto", confianza: "baja", paises: ["CO", "ES"] });
  assert.equal(M.dondeAplica(dudosa, { CO: "Colombia", ES: "España" }, 2), "Región por confirmar");
  const media = V({ id: "media", titulo: "UX Designer", confianza: "media" });
  assert.equal(M.filtrar([dudosa, media], { confianzaAlta: true }).length, 0);
});

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

test("fechas relativas", () => {
  assert.equal(M.fechaRelativa("2026-10-28", "2026-10-28"), "hoy");
  assert.equal(M.fechaRelativa("2026-10-27", "2026-10-28"), "ayer");
  assert.equal(M.fechaRelativa("2026-10-20", "2026-10-28"), "hace 8 días");
  assert.equal(M.fechaRelativa("", "2026-10-28"), "fecha sin confirmar");
});

test("dondeAplica distingue LATAM de LATAM y España", () => {
  const todos = ["AR", "BO", "CO", "ES"];
  assert.equal(M.dondeAplica({ paises: todos }, {}, 4), "LATAM y España");
  assert.equal(M.dondeAplica({ paises: ["AR", "BO", "CO"] }, {}, 4), "Toda LATAM");
  assert.equal(M.dondeAplica({ paises: ["ES"] }, { ES: "España" }, 4), "España");
});
