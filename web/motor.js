/* Motor de la página: búsqueda, filtros, orden, texto para WhatsApp y filas del Excel.
 * Funciones puras (sin DOM): se usan en el navegador (window.Motor) y en las pruebas (node --test pruebas/). */
(function (raiz) {
  "use strict";

  const GRADOS = ["exacto", "similar", "cercano"];
  const NIVELES = ["trainee", "junior", "semi senior", "senior", "lead"];
  const INGLES_ORDEN = ["", "basico", "intermedio", "avanzado", "fluido", "nativo"];
  const QUITAR = /\b(trainee|intern|internship|pasante|practicante|junior|jr|semi senior|semisenior|ssr|mid|senior|sr|lead|staff|principal|remote|remoto|remota|hibrido|hybrid)\b/g;

  function normalizar(texto) {
    return String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9+#./ ]+/g, " ").replace(/(^|\s)[./]+|[./]+(\s|$)/g, " ").replace(/\s+/g, " ").trim();
  }

  function base(texto) {
    return normalizar(texto).replace(/\//g, " / ").replace(QUITAR, " ").replace(/\s+/g, " ")
      .replace(/ \/ /g, "/").replace(/^[\s/]+|[\s/]+$/g, "");
  }

  function contieneFrase(haystack, frase) {
    if (!frase) return false;
    const i = haystack.indexOf(frase);
    if (i < 0) return false;
    // Palabras completas: "ux" no coincide dentro de "linux"
    let desde = 0;
    while (true) {
      const j = haystack.indexOf(frase, desde);
      if (j < 0) return false;
      const antes = j === 0 ? " " : haystack[j - 1];
      const despues = j + frase.length >= haystack.length ? " " : haystack[j + frase.length];
      if (!/[a-z0-9]/.test(antes) && !/[a-z0-9]/.test(despues)) return true;
      desde = j + 1;
    }
  }

  /** Prepara el mapa de la página: títulos normalizados por grado. */
  function prepararMapa(mapa) {
    return mapa.map(f => ({
      ...f,
      _n: { exacto: (f.exactos || []).map(base), similar: (f.similares || []).map(base), cercano: (f.cercanos || []).map(base) },
      _nombre: base(f.nombre),
    }));
  }

  /** Familias que coinciden con lo que se escribió, de la más probable a la menos. */
  function sugerir(consulta, mapaPreparado, maximo = 8) {
    const q = base(consulta);
    if (!q) return [];
    const palabrasQ = q.split(/[\s/]+/).filter(Boolean);
    const salida = [];
    for (const f of mapaPreparado) {
      let puntos = 0, motivo = "";
      if (f._nombre === q || contieneFrase(f._nombre, q)) { puntos = 95; motivo = f.nombre; }
      for (const [grado, peso] of [["exacto", 30], ["similar", 15], ["cercano", 5]]) {
        for (let k = 0; k < f._n[grado].length; k++) {
          const t = f._n[grado][k];
          let p = 0;
          if (t === q) p = 70 + peso;
          else if (contieneFrase(t, q) || contieneFrase(q, t)) p = 50 + peso;
          else {
            const palabrasT = t.split(/[\s/]+/);
            const comunes = palabrasQ.filter(w => palabrasT.includes(w) || palabrasT.some(x => x.startsWith(w) && w.length >= 3)).length;
            if (comunes) p = Math.round(40 * comunes / Math.max(palabrasQ.length, palabrasT.length)) + peso / 3;
          }
          if (p > puntos) { puntos = p; motivo = f[grado === "exacto" ? "exactos" : grado === "similar" ? "similares" : "cercanos"][k]; }
        }
      }
      if (puntos >= 30) salida.push({ id: f.id, nombre: f.nombre, area: f.area, puntos, motivo });
    }
    return salida.sort((a, b) => b.puntos - a.puntos || a.nombre.localeCompare(b.nombre)).slice(0, maximo);
  }

  function diasEntre(desde, hasta) {
    if (!desde || !hasta) return 0;
    return Math.round((Date.parse(hasta + "T00:00:00Z") - Date.parse(desde.slice(0, 10) + "T00:00:00Z")) / 864e5);
  }

  function fechaDe(v) { return v.fecha_publicacion || v.visto_primera_vez || ""; }

  /**
   * Vacantes que cumplen la búsqueda. op:
   *  familias: ids elegidos · grados: grados activos · palabras: frases extra (el título contiene alguna)
   *  excluir: frases que sacan una vacante · pais: código o "" · remotas / presenciales: modalidades
   *  confianzaAlta · dias · hoy · enviadas (Set de ids) · ocultarEnviadas · nivel · idioma · ingles ("", "hasta-intermedio", "avanzado-o-mas")
   * Cada resultado lleva `_grado` (el mejor entre las familias elegidas, o "palabra").
   */
  function filtrar(vacantes, op) {
    const familias = new Set(op.familias || []);
    const grados = new Set(op.grados || GRADOS);
    const palabras = (op.palabras || []).map(base).filter(Boolean);
    const excluir = (op.excluir || []).map(base).filter(Boolean);
    const salida = [];
    for (const v of vacantes) {
      const titulo = base(v.titulo);
      let grado = null;
      if (familias.size) {
        for (const f of v.familias || []) {
          if (familias.has(f.familia) && grados.has(f.coincidencia) &&
              (grado === null || GRADOS.indexOf(f.coincidencia) < GRADOS.indexOf(grado))) grado = f.coincidencia;
        }
      }
      if (grado === null && palabras.some(p => contieneFrase(titulo, p))) grado = "palabra";
      if (grado === null && !familias.size && !palabras.length) grado = "todas";
      if (grado === null) continue;
      if (excluir.some(p => contieneFrase(titulo, p))) continue;
      if (op.pais && !(v.paises || []).includes(op.pais)) continue;
      const remota = v.modalidad === "remoto";
      if (remota && op.remotas === false) continue;
      if (!remota && op.presenciales === false) continue;
      if (op.confianzaAlta && v.confianza_pais === "baja") continue;
      if (op.dias && op.hoy && diasEntre(fechaDe(v), op.hoy) > op.dias) continue;
      if (op.ocultarEnviadas && op.enviadas && op.enviadas.has(v.id)) continue;
      if (op.nivel && (v.nivel || "sin dato") !== op.nivel) continue;
      if (op.idioma && v.idioma !== op.idioma) continue;
      if (op.ingles === "hasta-intermedio" && INGLES_ORDEN.indexOf(v.ingles || "") > 2) continue;
      if (op.ingles === "avanzado-o-mas" && INGLES_ORDEN.indexOf(v.ingles || "") < 3) continue;
      salida.push({ ...v, _grado: grado });
    }
    return salida;
  }

  const RANGO_ENLACE = { original: 0, portal: 1, desconocido: 2 };
  const RANGO_GRADO = { exacto: 0, palabra: 0, todas: 1, similar: 1, cercano: 2 };

  /** Orden: por relevancia (coincidencia, fecha, tipo de enlace, sin más de 3 seguidas de una empresa) o por fecha. */
  function ordenar(lista, modo = "relevancia") {
    const porFecha = (a, b) => fechaDe(b).localeCompare(fechaDe(a));
    if (modo === "fecha") return [...lista].sort(porFecha);
    const orden = [...lista].sort((a, b) => (RANGO_GRADO[a._grado] ?? 3) - (RANGO_GRADO[b._grado] ?? 3) || porFecha(a, b) ||
      (RANGO_ENLACE[a.tipo_enlace] ?? 3) - (RANGO_ENLACE[b.tipo_enlace] ?? 3));
    const salida = [], pendientes = [...orden];
    while (pendientes.length) {
      const ultimas = salida.slice(-3).map(v => normalizar(v.empresa));
      const repetida = ultimas.length === 3 && ultimas.every(e => e === ultimas[0]) ? ultimas[0] : null;
      let i = repetida ? pendientes.findIndex(v => normalizar(v.empresa) !== repetida) : 0;
      if (i < 0) i = 0;
      salida.push(pendientes.splice(i, 1)[0]);
    }
    return salida;
  }

  function conteos(lista) {
    const c = { total: lista.length, exacto: 0, similar: 0, cercano: 0, palabra: 0 };
    for (const v of lista) if (c[v._grado] !== undefined) c[v._grado]++;
    return c;
  }

  function fechaRelativa(fecha, hoy) {
    if (!fecha) return "fecha sin confirmar";
    const d = diasEntre(fecha, hoy);
    if (d <= 0) return "hoy";
    if (d === 1) return "ayer";
    return `hace ${d} días`;
  }

  const MODALIDAD = { remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial", "sin dato": "Modalidad sin confirmar" };
  const INGLES = { basico: "Inglés básico", intermedio: "Inglés intermedio", avanzado: "Inglés avanzado", fluido: "Inglés fluido", nativo: "Inglés nativo" };

  /** "Toda LATAM", "Colombia" o "Colombia, México y Perú" (con más de 3: "Colombia y 6 países más"). */
  function dondeAplica(v, nombres, totalPaises) {
    const p = v.paises || [];
    if (totalPaises && p.length >= totalPaises) return "Toda LATAM";
    const n = p.map(c => nombres[c] || c);
    if (n.length <= 1) return n[0] || "";
    if (n.length <= 3) return n.slice(0, -1).join(", ") + " y " + n[n.length - 1];
    return `${n[0]} y ${n.length - 1} países más`;
  }

  /** Mensajes listos para pegar en WhatsApp (uno cada `porMensaje` vacantes). */
  function textoWhatsApp(lista, { titulo, lugar, fecha, hoy, nombres, totalPaises }, porMensaje = 15) {
    const bloques = lista.map(v => {
      const linea2 = [v.modalidad === "remoto" ? `Remoto · ${dondeAplica(v, nombres || {}, totalPaises)}` :
        `${MODALIDAD[v.modalidad] || ""} · ${v.ubicacion || dondeAplica(v, nombres || {}, totalPaises)}`,
      INGLES[v.ingles], fechaRelativa(fechaDe(v), hoy)].filter(Boolean).join(" · ");
      return `*${v.titulo}* — ${v.empresa}\n${linea2}\n${v.enlace}`;
    });
    const mensajes = [];
    for (let i = 0; i < bloques.length; i += porMensaje) {
      const parte = bloques.length > porMensaje ? ` (${i / porMensaje + 1}/${Math.ceil(bloques.length / porMensaje)})` : "";
      mensajes.push(`*Vacantes de ${titulo}${lugar ? " · " + lugar : ""} · ${fecha}*${parte}\n\n` + bloques.slice(i, i + porMensaje).join("\n\n"));
    }
    return mensajes;
  }

  const COLUMNAS_EXCEL = ["Cargo", "Coincidencia", "Empresa", "Dónde se puede aplicar", "Modalidad", "Ubicación del aviso",
    "Idioma del aviso", "Inglés que pide", "Nivel", "Años mínimos", "Salario", "Publicada", "Fuente", "Enlace",
    "Enlace directo de la empresa", "Resumen"];
  const IDIOMA = { es: "Español", en: "Inglés", pt: "Portugués" };
  const GRADO_TEXTO = { exacto: "Exacta", similar: "Similar", cercano: "Cercana", palabra: "Por palabra", todas: "" };

  function filasExcel(lista, nombres, totalPaises) {
    return [COLUMNAS_EXCEL].concat(lista.map(v => [v.titulo, GRADO_TEXTO[v._grado] || "", v.empresa,
      dondeAplica(v, nombres || {}, totalPaises) + (v.confianza_pais === "baja" ? " (confirmar)" : ""),
      MODALIDAD[v.modalidad] || "", v.ubicacion || "", IDIOMA[v.idioma] || "", (INGLES[v.ingles] || "No lo dice").replace("Inglés ", ""),
      v.nivel || "", v.anos_min ?? "", v.salario || "", fechaDe(v), (v.fuentes || [v.fuente]).join(", "), v.enlace,
      v.enlace_directo || "", v.resumen || ""]));
  }

  const Motor = { GRADOS, NIVELES, normalizar, base, contieneFrase, prepararMapa, sugerir, filtrar, ordenar, conteos,
    fechaRelativa, dondeAplica, textoWhatsApp, filasExcel, diasEntre, fechaDe, MODALIDAD, INGLES, IDIOMA, GRADO_TEXTO };
  if (typeof module !== "undefined" && module.exports) module.exports = Motor;
  else raiz.Motor = Motor;
})(typeof window !== "undefined" ? window : globalThis);
