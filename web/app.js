/* Pantalla del buscador. La lógica de búsqueda vive en motor.js (con pruebas); aquí solo se pinta y se reacciona. */
(function () {
  "use strict";
  const M = window.Motor;
  const CONFIG = window.BUSCADOR_CONFIG || {};
  const $ = (id) => document.getElementById(id);
  const POR_PAGINA = 50;
  const SEL_RAPIDA = 20;
  const hoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Bogota" });
  const fmt = new Intl.NumberFormat("es-CO");
  const fechaCorta = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short" }).replace(".", "");

  const estado = {
    vacantes: [], mapa: [], mapaPorId: {}, paises: [], nombres: {}, salud: null,
    familia: null, texto: "", grados: new Set(M.GRADOS), resultados: [], visibles: POR_PAGINA,
    seleccion: new Set(), enviadas: new Set(), remoto: false, sugerencias: [], activa: -1,
  };

  // ───────── Enviadas: en este navegador y, si existe la función de Cloudflare, compartidas entre equipos ─────────
  const CLAVE_ENVIADAS = "vacantes-latam:enviadas";
  function leerLocal() {
    try { return new Set(JSON.parse(localStorage.getItem(CLAVE_ENVIADAS) || "[]")); } catch (e) { return new Set(); }
  }
  function guardarLocal() {
    try { localStorage.setItem(CLAVE_ENVIADAS, JSON.stringify([...estado.enviadas])); } catch (e) { /* modo privado */ }
  }
  async function cargarEnviadasRemotas() {
    try {
      const r = await fetch("api/enviadas", { headers: { Accept: "application/json" } });
      if (!r.ok) return;
      const ids = await r.json();
      if (Array.isArray(ids)) { estado.remoto = true; ids.forEach(id => estado.enviadas.add(id)); guardarLocal(); }
    } catch (e) { /* sin función de Cloudflare: solo este navegador */ }
  }
  async function marcarEnviadas(ids) {
    ids.forEach(id => estado.enviadas.add(id));
    guardarLocal();
    if (estado.remoto) {
      try { await fetch("api/enviadas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ids) }); }
      catch (e) { avisar("Se guardaron en este equipo; no se pudieron compartir con los demás."); }
    }
  }

  // ───────── Datos ─────────
  async function leerJsonComprimido(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const bytes = new Uint8Array(await r.arrayBuffer());
    if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
      const flujo = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      return JSON.parse(await new Response(flujo).text());
    }
    return JSON.parse(new TextDecoder().decode(bytes));   // el servidor ya lo descomprimió
  }

  async function cargar() {
    pintarEsqueleto();
    try {
      const [vacantes, mapa, paises, salud] = await Promise.all([
        leerJsonComprimido("datos/vacantes.json.gz"),
        fetch("datos/mapa.json").then(r => r.json()),
        fetch("datos/paises.json").then(r => r.json()),
        fetch("datos/salud.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      estado.vacantes = vacantes;
      estado.mapa = M.prepararMapa(mapa);
      estado.mapa.forEach(f => { estado.mapaPorId[f.id] = f; });
      estado.paises = paises;
      paises.forEach(p => { estado.nombres[p.codigo] = p.nombre; });
      estado.salud = salud;
      const sel = $("pais");
      paises.slice().sort((a, b) => a.nombre.localeCompare(b.nombre, "es")).forEach(p => sel.add(new Option(p.nombre, p.codigo)));
      $("estado-datos").textContent = salud
        ? `${fmt.format(vacantes.length)} vacantes abiertas · actualizado el ${fechaCorta(salud.fecha)}`
        : `${fmt.format(vacantes.length)} vacantes abiertas`;
      leerHash();
      buscar();
      pintarSalud();
      pintarMapa();
    } catch (e) {
      $("estado-datos").textContent = "No se pudieron cargar las vacantes";
      $("lista").innerHTML = "";
      mostrarVacio("No se pudieron cargar las vacantes.",
        "Revisa tu conexión y recarga la página. Si sigue igual, la búsqueda de anoche pudo fallar: mira la pestaña Estado.");
    }
  }

  // ───────── Búsqueda ─────────
  function opciones() {
    const lista = (id) => $(id).value.split(",").map(s => s.trim()).filter(Boolean);
    const palabras = lista("palabras-extra");
    if (!estado.familia && estado.texto) palabras.push(estado.texto);
    return {
      familias: estado.familia ? [estado.familia] : [], grados: [...estado.grados], palabras, excluir: lista("palabras-excluir"),
      pais: $("pais").value, remotas: $("remotas").checked, presenciales: $("presenciales").checked,
      confianzaAlta: $("confianza").checked, dias: Number($("dias").value), hoy,
      enviadas: estado.enviadas, ocultarEnviadas: $("ocultar-enviadas").checked,
      nivel: $("nivel").value, idioma: $("idioma").value, ingles: $("ingles").value,
    };
  }

  function buscar() {
    const hayBusqueda = estado.familia || estado.texto || $("palabras-extra").value.trim();
    $("filtros").hidden = !hayBusqueda;
    $("barra-acciones").hidden = !hayBusqueda;
    if (!hayBusqueda) {
      estado.resultados = [];
      $("resultados-titulo").textContent = "Escribe un cargo para empezar";
      $("resumen").textContent = `Hay ${fmt.format(estado.vacantes.length)} vacantes de ${estado.mapa.length} tipos de cargo. ` +
        "Escribe uno (por ejemplo «UX», «desarrollador» o «editor de video») y elige de la lista.";
      $("lista").innerHTML = "";
      $("mas").hidden = true;
      $("vacio").hidden = true;
      pintarPalabras();
      return;
    }
    estado.resultados = M.ordenar(M.filtrar(estado.vacantes, opciones()), $("orden").value);
    estado.visibles = POR_PAGINA;
    estado.seleccion = new Set([...estado.seleccion].filter(id => estado.resultados.some(v => v.id === id)));
    pintarPalabras();
    pintarResultados();
    escribirHash();
  }

  function nombreBusqueda() {
    return estado.familia ? estado.mapaPorId[estado.familia].nombre : estado.texto || $("palabras-extra").value;
  }
  function lugarBusqueda() {
    const p = $("pais").value;
    const remotas = $("remotas").checked, presenciales = $("presenciales").checked;
    if (!p) return remotas && !presenciales ? "Remotas para LATAM" : "LATAM";
    return `${estado.nombres[p]}${remotas ? " y remoto" : ""}`;
  }

  // ───────── Pintar ─────────
  function el(tag, attrs = {}, ...hijos) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    hijos.flat().forEach(h => h !== null && h !== undefined && n.append(h.nodeType ? h : document.createTextNode(String(h))));
    return n;
  }

  function pintarEsqueleto() {
    const lista = $("lista");
    lista.innerHTML = "";
    for (let i = 0; i < 4; i++) lista.append(el("div", { class: "esqueleto", "aria-hidden": "true" }));
  }

  const ETIQUETA_GRADO = { exacto: "Exacta", similar: "Similar", cercano: "Cercana", palabra: "Por palabra", todas: "" };

  function pintarPalabras() {
    const caja = $("palabras");
    if (!estado.familia) { caja.hidden = !$("palabras-extra").value.trim() && !estado.texto; $("grados").innerHTML = ""; $("titulos").innerHTML = ""; $("ver-titulos").hidden = true; return; }
    caja.hidden = false;
    $("ver-titulos").hidden = false;
    const f = estado.mapaPorId[estado.familia];
    const base = M.filtrar(estado.vacantes, { ...opciones(), grados: M.GRADOS, nivel: "", idioma: "", ingles: "" });
    const c = M.conteos(base);
    const grados = $("grados");
    grados.innerHTML = "";
    const textos = { exacto: "Exactas", similar: "Similares", cercano: "Cercanas" };
    for (const g of M.GRADOS) {
      const id = `grado-${g}`;
      const input = el("input", { type: "checkbox", id, checked: estado.grados.has(g),
        onchange: (e) => { e.target.checked ? estado.grados.add(g) : estado.grados.delete(g); buscar(); } });
      grados.append(el("label", { class: "chip-check", for: id }, input,
        el("span", {}, `${textos[g]} · ${fmt.format(c[g])}`)));
    }
    const titulos = $("titulos");
    titulos.innerHTML = "";
    for (const [g, campo] of [["exacto", "exactos"], ["similar", "similares"], ["cercano", "cercanos"]]) {
      if (!(f[campo] || []).length) continue;
      titulos.append(el("div", {}, el("h3", { text: textos[g] }), el("ul", {}, f[campo].map(t => el("li", { text: t })))));
    }
  }

  function datoPais(v) {
    const donde = M.dondeAplica(v, estado.nombres, estado.paises.length);
    if (v.modalidad === "remoto") return `Remoto · ${donde}`;
    return `${M.MODALIDAD[v.modalidad] || ""} · ${v.ubicacion || donde}`;
  }

  function fila(v) {
    const id = `sel-${v.id}`;
    const elegida = estado.seleccion.has(v.id);
    const enviada = estado.enviadas.has(v.id);
    const check = el("input", { type: "checkbox", id, checked: elegida, "aria-label": `Elegir ${v.titulo} en ${v.empresa}`,
      onchange: (e) => { e.target.checked ? estado.seleccion.add(v.id) : estado.seleccion.delete(v.id);
        e.target.closest(".fila").classList.toggle("fila--elegida", e.target.checked); pintarBarra(); } });
    const datos = [
      el("span", {}, datoPais(v)),
      v.confianza_pais === "baja" ? el("span", { class: "confirmar" }, "Confirmar desde qué países") : null,
      el("span", {}, M.fechaRelativa(M.fechaDe(v), hoy)),
    ];
    const lado = [
      el("div", {}, [M.IDIOMA[v.idioma] ? `Aviso en ${M.IDIOMA[v.idioma].toLowerCase()}` : null,
        v.ingles ? M.INGLES[v.ingles] : null].filter(Boolean).join(" · ") || null),
      el("div", {}, [v.nivel ? `Nivel ${v.nivel}` : null, v.anos_min ? `${v.anos_min}+ años` : null, v.salario || null].filter(Boolean).join(" · ") || null),
      el("div", {}, `Fuente: ${(v.fuentes || [v.fuente]).join(", ")}`),
    ];
    const enlaces = [el("a", { href: v.enlace, target: "_blank", rel: "noopener" }, v.enlace.includes("linkedin.com") ? "Ver en LinkedIn" : "Ver vacante")];
    if (v.enlace_directo) enlaces.push(el("a", { href: v.enlace_directo, target: "_blank", rel: "noopener" }, "Postular en la empresa"));
    return el("article", { class: `fila${elegida ? " fila--elegida" : ""}${enviada ? " fila--enviada" : ""}`, role: "listitem" },
      el("label", { class: "fila__check", for: id }, check),
      el("div", { class: "fila__cuerpo" },
        el("div", { class: "fila__titulo" }, el("a", { href: v.enlace, target: "_blank", rel: "noopener" }, v.titulo)),
        el("div", { class: "fila__empresa" }, v.empresa),
        el("div", { class: "fila__datos" }, ETIQUETA_GRADO[v._grado] ? el("span", { class: `insignia insignia--${v._grado}` }, ETIQUETA_GRADO[v._grado]) : null,
          enviada ? el("span", { class: "insignia insignia--enviada" }, "Enviada") : null, datos),
        el("div", { class: "fila__enlaces" }, enlaces)),
      el("div", { class: "fila__lado" }, lado));
  }

  function pintarResultados() {
    const r = estado.resultados;
    const c = M.conteos(r);
    $("resultados-titulo").textContent = `${fmt.format(r.length)} ${r.length === 1 ? "vacante" : "vacantes"} de ${nombreBusqueda()}`;
    $("resumen").textContent = [`${lugarBusqueda()}, últimos ${$("dias").value} días.`,
      estado.familia ? `${fmt.format(c.exacto)} exactas, ${fmt.format(c.similar)} similares y ${fmt.format(c.cercano)} cercanas.` : ""].join(" ");
    const lista = $("lista");
    lista.innerHTML = "";
    r.slice(0, estado.visibles).forEach(v => lista.append(fila(v)));
    $("mas").hidden = r.length <= estado.visibles;
    $("ver-mas").textContent = `Ver ${fmt.format(Math.min(POR_PAGINA, r.length - estado.visibles))} más (quedan ${fmt.format(r.length - estado.visibles)})`;
    if (!r.length) {
      mostrarVacio(`No hay vacantes de ${nombreBusqueda()} con estos filtros.`,
        "Prueba con 30 días, con «Toda LATAM» o activando las cercanas. También puedes pedir una búsqueda en vivo:", true);
    } else {
      $("vacio").hidden = true;
    }
    pintarBarra();
  }

  function mostrarVacio(titulo, texto, conProfunda) {
    const v = $("vacio");
    v.innerHTML = "";
    v.append(el("strong", { text: titulo }), el("p", { text: texto }));
    if (conProfunda) v.append(botonProfunda());
    v.hidden = false;
  }

  function botonProfunda() {
    return el("button", { type: "button", class: "boton boton--secundario", onclick: busquedaProfunda }, "Buscar en vivo (tarda unos 15 minutos)");
  }

  async function busquedaProfunda() {
    const consulta = estado.familia ? estado.mapaPorId[estado.familia].nombre : (estado.texto || $("palabras-extra").value);
    const pais = $("pais").value;
    try {
      const r = await fetch("api/profunda", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consulta, pais }) });
      if (r.ok) { avisar("Listo: la búsqueda en vivo empezó. Recarga la página en unos 15 minutos."); return; }
    } catch (e) { /* sin función de Cloudflare */ }
    if (CONFIG.repo) {
      window.open(`https://github.com/${CONFIG.repo}/actions/workflows/profunda.yml`, "_blank", "noopener");
      avisar(`En GitHub toca «Run workflow», escribe «${consulta}»${pais ? " y el país " + pais : ""} y confirma.`, 9000);
    } else {
      avisar("La búsqueda en vivo se activa al conectar la página con GitHub (ver docs/INSTALACION.md).", 8000);
    }
  }

  function pintarBarra() {
    const n = estado.seleccion.size;
    const total = `${fmt.format(estado.resultados.length)} ${estado.resultados.length === 1 ? "vacante" : "vacantes"}`;
    $("cuenta-seleccion").textContent = n ? `${total} · ${fmt.format(n)} ${n === 1 ? "elegida" : "elegidas"}` : `${total} · elige las que vas a mandar`;
    ["copiar", "excel", "marcar"].forEach(id => { $(id).disabled = !n; });
    $("seleccionar").textContent = n ? "Quitar selección" : `Elegir las ${SEL_RAPIDA} primeras`;
  }

  function elegidas() {
    return estado.resultados.filter(v => estado.seleccion.has(v.id));
  }

  // ───────── Acciones ─────────
  let temporizador;
  function avisar(texto, ms = 4500) {
    const a = $("aviso");
    a.textContent = texto;
    a.hidden = false;
    clearTimeout(temporizador);
    temporizador = setTimeout(() => { a.hidden = true; }, ms);
  }

  async function copiar() {
    const lista = elegidas();
    const mensajes = M.textoWhatsApp(lista, { titulo: nombreBusqueda(), lugar: lugarBusqueda(), fecha: fechaCorta(hoy), hoy,
      nombres: estado.nombres, totalPaises: estado.paises.length });
    const texto = mensajes.join("\n\n");
    try {
      await navigator.clipboard.writeText(texto);
    } catch (e) {
      const area = el("textarea", { class: "sr" });
      area.value = texto;
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    avisar(`Copiadas ${lista.length} vacantes${mensajes.length > 1 ? ` en ${mensajes.length} bloques` : ""}. Pégalas en WhatsApp y luego toca «Marcar enviadas».`, 6000);
  }

  function cargarScript(src) {
    return new Promise((ok, mal) => { const s = el("script", { src, onload: ok, onerror: mal }); document.head.append(s); });
  }

  async function excel() {
    const filas = M.filasExcel(elegidas(), estado.nombres, estado.paises.length);
    const nombre = `vacantes_${M.base(nombreBusqueda()).replace(/[^a-z0-9]+/g, "-")}_${$("pais").value || "latam"}_${hoy}`;
    try {
      if (!window.XLSX) await cargarScript("https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js");
      const hoja = window.XLSX.utils.aoa_to_sheet(filas);
      hoja["!cols"] = filas[0].map((_, i) => ({ wch: [40, 12, 26, 28, 14, 28, 12, 14, 12, 10, 18, 12, 18, 45, 45, 60][i] || 16 }));
      const libro = window.XLSX.utils.book_new();
      window.XLSX.utils.book_append_sheet(libro, hoja, "Vacantes");
      window.XLSX.writeFile(libro, nombre + ".xlsx");
    } catch (e) {
      const csv = filas.map(f => f.map(c => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
      const a = el("a", { href: URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" })), download: nombre + ".csv" });
      a.click();
      avisar("Se descargó en CSV (se abre en Excel).");
    }
  }

  async function marcar() {
    const ids = [...estado.seleccion];
    await marcarEnviadas(ids);
    estado.seleccion.clear();
    avisar(`${ids.length} marcadas como enviadas${$("ocultar-enviadas").checked ? ": ya no aparecen en esta lista" : ""}.`);
    buscar();
    pintarEnviadas();
  }

  // ───────── Combo de cargo (teclado y ratón) ─────────
  function pintarSugerencias() {
    const ul = $("sugerencias");
    ul.innerHTML = "";
    const lista = estado.sugerencias;
    if (!lista.length) { ul.hidden = true; $("cargo").setAttribute("aria-expanded", "false"); return; }
    lista.forEach((s, i) => ul.append(el("li", { id: `sug-${i}`, role: "option", "aria-selected": i === estado.activa ? "true" : "false",
      onmousedown: (e) => { e.preventDefault(); elegirFamilia(s); } },
      el("span", { class: "nombre", text: s.nombre }), el("span", { class: "detalle", text: `${s.area} · incluye «${s.motivo}»` }))));
    const texto = $("cargo").value.trim();
    ul.append(el("li", { role: "option", id: "sug-texto", "aria-selected": estado.activa === lista.length ? "true" : "false",
      onmousedown: (e) => { e.preventDefault(); buscarTexto(texto); } },
      el("span", { class: "nombre", text: `Buscar «${texto}» tal cual` }), el("span", { class: "detalle", text: "En los títulos de todas las vacantes" })));
    ul.hidden = false;
    $("cargo").setAttribute("aria-expanded", "true");
    $("cargo").setAttribute("aria-activedescendant", estado.activa >= 0 ? (estado.activa === lista.length ? "sug-texto" : `sug-${estado.activa}`) : "");
  }

  function elegirFamilia(s) {
    estado.familia = s.id;
    estado.texto = "";
    estado.grados = new Set(M.GRADOS);
    estado.seleccion.clear();
    $("cargo").value = s.nombre;
    cerrarSugerencias();
    buscar();
  }
  function buscarTexto(texto) {
    estado.familia = null;
    estado.texto = texto;
    estado.seleccion.clear();
    cerrarSugerencias();
    buscar();
  }
  function cerrarSugerencias() { estado.sugerencias = []; estado.activa = -1; pintarSugerencias(); }

  // ───────── Enlace con la búsqueda (para guardarla o compartirla) ─────────
  function escribirHash() {
    const p = new URLSearchParams();
    if (estado.familia) p.set("cargo", estado.familia); else if (estado.texto) p.set("texto", estado.texto);
    if ($("pais").value) p.set("pais", $("pais").value);
    if ($("dias").value !== "30") p.set("dias", $("dias").value);
    history.replaceState(null, "", "#" + p.toString());
  }
  function leerHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    if (p.get("pais")) $("pais").value = p.get("pais");
    if (p.get("dias")) $("dias").value = p.get("dias");
    if (p.get("cargo") && estado.mapaPorId[p.get("cargo")]) { estado.familia = p.get("cargo"); $("cargo").value = estado.mapaPorId[estado.familia].nombre; }
    else if (p.get("texto")) { estado.texto = p.get("texto"); $("cargo").value = estado.texto; }
  }

  // ───────── Estado y cargos ─────────
  function pintarSalud() {
    const s = estado.salud, caja = $("salud");
    caja.innerHTML = "";
    if (!s) { caja.append(el("p", { text: "Todavía no hay reporte de la búsqueda nocturna." })); return; }
    caja.append(el("h2", { text: `Última búsqueda: ${fechaCorta(s.fecha)} (${s.minutos} min)` }));
    caja.append(el("div", { class: "metricas" },
      [["Vacantes abiertas", s.vacantes_en_bodega], ["Nuevas en esa búsqueda", s.nuevas_hoy], ["Leídas de las fuentes", s.crudas_hoy],
        ["Tipos de cargo con vacantes", Object.keys(s.por_familia || {}).length]]
        .map(([t, n]) => el("div", { class: "metrica" }, el("strong", { text: fmt.format(n || 0) }), el("span", { text: t })))));
    const filas = Object.entries(s.fuentes || {}).map(([nombre, d]) => el("tr", {},
      el("td", { text: nombre }),
      el("td", { text: d.error ? `Falló: ${d.error}` : d.omitida ? `No corrió: ${d.omitida}` : "Funcionó" }),
      el("td", { class: "num", text: d.avisos !== undefined ? fmt.format(d.avisos) : d.con_original !== undefined ? fmt.format(d.con_original) : d.portales_nuevos !== undefined ? `${fmt.format(d.portales_nuevos)} portales nuevos` : "—" }),
      el("td", { class: "num", text: d.segundos !== undefined ? `${Math.round(d.segundos / 60)} min` : "" })));
    caja.append(el("h3", { class: "area", text: "Fuentes" }),
      el("div", { class: "tabla-scroll" }, el("table", { class: "tabla" },
        el("thead", {}, el("tr", {}, el("th", { text: "Fuente" }), el("th", { text: "Estado" }), el("th", { class: "num", text: "Avisos" }), el("th", { class: "num", text: "Tiempo" }))),
        el("tbody", {}, filas))));
    const desc = Object.entries(s.descartes || {});
    if (desc.length) caja.append(el("h3", { class: "area", text: "Lo que se descartó" }),
      el("ul", {}, desc.map(([m, n]) => el("li", { text: `${m}: ${fmt.format(n)}` }))));
    const porPais = Object.entries(s.por_pais || {}).slice(0, 20);
    if (porPais.length) caja.append(el("h3", { class: "area", text: "Vacantes por país (incluye remotas)" }),
      el("p", { class: "nota", text: porPais.map(([c, n]) => `${estado.nombres[c] || c} ${fmt.format(n)}`).join(" · ") }));
    pintarEnviadas();
  }

  function pintarEnviadas() {
    $("enviadas-resumen").textContent = `${fmt.format(estado.enviadas.size)} vacantes marcadas como enviadas` +
      (estado.remoto ? " (compartidas entre tus equipos)." : " en este navegador. Exporta el historial para pasarlo a otro equipo.");
  }

  async function pintarMapa() {
    const caja = $("mapa"), cuenta = (estado.salud && estado.salud.por_familia) || {};
    caja.innerHTML = "";
    caja.append(el("h2", { text: `${estado.mapa.length} tipos de cargo` }),
      el("p", { class: "nota", text: "Cada búsqueda trae el cargo exacto, los similares y los cercanos, de todos los niveles. Para agregar un cargo o un título, pídeselo a Claude con la skill «nueva-familia»." }));
    const areas = {};
    estado.mapa.forEach(f => { (areas[f.area] = areas[f.area] || []).push(f); });
    for (const [area, fams] of Object.entries(areas)) {
      caja.append(el("section", { class: "area" }, el("h3", { text: area }), fams.map(f => el("details", { class: "familia" },
        el("summary", {}, el("span", { text: f.nombre }), el("span", { class: "nota", text: `${fmt.format(cuenta[f.id] || 0)} vacantes` })),
        el("p", { class: "nota" }, el("strong", { text: "Exactos: " }), (f.exactos || []).join(", ")),
        el("p", { class: "nota" }, el("strong", { text: "Similares: " }), (f.similares || []).join(", ") || "—"),
        el("p", { class: "nota" }, el("strong", { text: "Cercanos: " }), (f.cercanos || []).join(", ") || "—")))));
    }
    try {
      const csv = await fetch("datos/titulos_sin_familia.csv").then(r => r.ok ? r.text() : "");
      const filas = csv.trim().split("\n").slice(1, 41).map(l => l.split(","));
      if (filas.length && filas[0][0]) caja.append(el("section", { class: "area" },
        el("h3", { text: "Títulos que llegaron y no encajaron en ningún cargo" }),
        el("p", { class: "nota", text: "Si alguno debería entrar, pídele a Claude «revisa los títulos sin familia» (skill ampliar-mapa)." }),
        el("p", { class: "nota", text: filas.map(([t, n]) => `${t} (${n})`).join(" · ") })));
    } catch (e) { /* opcional */ }
  }

  // ───────── Eventos ─────────
  function pestanas() {
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const activar = (t) => {
      tabs.forEach(x => { const on = x === t; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1;
        $(`panel-${x.dataset.panel}`).hidden = !on; });
      $("barra-acciones").hidden = t.dataset.panel !== "buscar" || !estado.resultados.length && !estado.familia && !estado.texto;
      t.focus();
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => activar(t));
      t.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          activar(tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]);
        }
      });
    });
  }

  function eventos() {
    const cargo = $("cargo");
    cargo.addEventListener("input", () => {
      estado.sugerencias = M.sugerir(cargo.value, estado.mapa);
      estado.activa = estado.sugerencias.length ? 0 : -1;
      pintarSugerencias();
      if (!cargo.value.trim()) { estado.familia = null; estado.texto = ""; buscar(); }
    });
    cargo.addEventListener("keydown", (e) => {
      const n = estado.sugerencias.length;
      if (e.key === "ArrowDown" && n) { e.preventDefault(); estado.activa = Math.min(estado.activa + 1, n); pintarSugerencias(); }
      else if (e.key === "ArrowUp" && n) { e.preventDefault(); estado.activa = Math.max(estado.activa - 1, 0); pintarSugerencias(); }
      else if (e.key === "Enter") {
        e.preventDefault();
        if (n && estado.activa >= 0 && estado.activa < n) elegirFamilia(estado.sugerencias[estado.activa]);
        else if (cargo.value.trim()) buscarTexto(cargo.value.trim());
      } else if (e.key === "Escape") cerrarSugerencias();
    });
    cargo.addEventListener("blur", () => setTimeout(cerrarSugerencias, 150));
    $("form-busqueda").addEventListener("submit", (e) => e.preventDefault());
    ["pais", "dias", "remotas", "presenciales", "ocultar-enviadas", "confianza", "nivel", "idioma", "ingles", "orden"]
      .forEach(id => $(id).addEventListener("change", buscar));
    let espera;
    ["palabras-extra", "palabras-excluir"].forEach(id => $(id).addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscar, 300); }));
    $("ver-mas").addEventListener("click", () => { estado.visibles += POR_PAGINA; pintarResultados(); });
    $("ver-titulos").addEventListener("click", (e) => {
      const abierto = $("titulos").hidden;
      $("titulos").hidden = !abierto;
      e.target.setAttribute("aria-expanded", abierto);
      e.target.textContent = abierto ? "Ocultar los títulos" : "Ver todos los títulos";
    });
    $("seleccionar").addEventListener("click", () => {
      if (estado.seleccion.size) estado.seleccion.clear();
      else estado.resultados.filter(v => !estado.enviadas.has(v.id)).slice(0, SEL_RAPIDA).forEach(v => estado.seleccion.add(v.id));
      pintarResultados();
    });
    $("copiar").addEventListener("click", copiar);
    $("excel").addEventListener("click", excel);
    $("marcar").addEventListener("click", marcar);
    $("exportar-enviadas").addEventListener("click", () => {
      const a = el("a", { href: URL.createObjectURL(new Blob([JSON.stringify([...estado.enviadas])], { type: "application/json" })),
        download: `enviadas_${hoy}.json` });
      a.click();
    });
    $("importar-enviadas").addEventListener("change", async (e) => {
      const archivo = e.target.files[0];
      if (!archivo) return;
      try {
        const ids = JSON.parse(await archivo.text());
        if (!Array.isArray(ids)) throw new Error();
        await marcarEnviadas(ids.map(String));
        avisar(`Se importaron ${ids.length} vacantes enviadas.`);
        pintarEnviadas();
        buscar();
      } catch (err) { avisar("Ese archivo no es un historial de enviadas."); }
      e.target.value = "";
    });
    $("borrar-enviadas").addEventListener("click", () => {
      if (!confirm("¿Borrar el historial de enviadas de este navegador? Las vacantes volverán a aparecer.")) return;
      estado.enviadas.clear();
      guardarLocal();
      pintarEnviadas();
      buscar();
    });
  }

  estado.enviadas = leerLocal();
  pestanas();
  eventos();
  cargarEnviadasRemotas().finally(cargar);
})();
