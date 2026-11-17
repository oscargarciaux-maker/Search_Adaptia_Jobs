import { test, expect, type Page } from "@playwright/test";
import { revisarContraste } from "./contraste";

// Sección 5 (13 nov): sin menú lateral; cada sección se abre desde su tarjeta del resumen.
const accion: Record<string, string> = {
  Clientes: "Ver clientes",
  "Cargos y metas": "Editar cargos y metas",
  Vacantes: "Ver vacantes",
  "Por confirmar": "Revisar",
  Mensajes: "Ver mensajes",
  Actividad: "Ver actividad",
};
const tarjeta = (page: Page, seccion: string) =>
  page.getByRole("button", { name: new RegExp(accion[seccion] + "$") });
async function ir(page: Page, seccion: string) {
  await page.getByRole("heading", { level: 1 }).waitFor(); // tras recargar
  const volver = page.getByRole("button", { name: "Volver al resumen" });
  if (await volver.count()) await volver.click();
  await tarjeta(page, seccion).click();
  await expect(
    page.getByRole("heading", { level: 1, name: seccion, exact: true }),
  ).toBeVisible();
}

test("gestión completa: clientes, términos abiertos, cupos, programación y WhatsApp", async ({
  page,
  request,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errores.push(m.text());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Resumen" }),
  ).toBeVisible();
  await expect(page.getByText("Mi espacio de trabajo")).toHaveCount(0);
  await expect(page.getByText("Menos ruido.")).toHaveCount(0);
  // Sección 6: la explicación de Guardar / Programar va en una ayuda (ⓘ), no en una franja.
  const explicacion = page.getByText(/los guarda y los usa desde la búsqueda/);
  await expect(explicacion).toBeHidden();
  const ayuda = page.getByRole("button", {
    name: "Más información: Guardar y programar",
  });
  await ayuda.focus();
  await expect(explicacion).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(explicacion).toBeHidden();
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Nombre o referencia del cliente")
    .fill("Prueba operadora");
  // Sección 7a: el cliente nuevo ya trae su primer perfil; los demás, con un enlace discreto.
  await expect(dialog.getByText("PERFIL 1", { exact: true })).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Añadir otro perfil" }),
  ).toBeVisible();
  // WhatsApp: el número aparece solo al marcar la casilla (contrato v35: país en una lista y solo el número).
  await expect(dialog.getByLabel("Número", { exact: true })).toHaveCount(0);
  await dialog.getByLabel("Aceptó recibir vacantes por WhatsApp").check();
  await expect(dialog.getByLabel("Número", { exact: true })).toBeVisible();
  await expect(dialog.getByLabel("País", { exact: true })).toHaveValue("CO");
  await dialog.getByLabel("Aceptó recibir vacantes por WhatsApp").uncheck();
  // Sección 8: crear un cargo sin salir del cliente; el formulario conserva lo escrito.
  await dialog
    .getByLabel("Cargo del perfil 1")
    .selectOption({ label: "＋ Añadir cargo nuevo…" });
  const cargoNuevo = page.locator("dialog", { hasText: "Añadir un cargo" });
  await cargoNuevo.getByLabel("Cargo", { exact: true }).fill("UX Writer");
  await cargoNuevo
    .getByRole("button", { name: "Añadir cargo", exact: true })
    .click();
  await cargoNuevo
    .getByRole("button", { name: "Añadir cargo", exact: true })
    .click();
  await expect(cargoNuevo).toHaveCount(0);
  await expect(
    dialog.getByLabel("Cargo del perfil 1").locator("option:checked"),
  ).toHaveText("UX Writer");
  // Contrato v21: cada perfil tiene su meta diaria (10 por defecto).
  await expect(dialog.getByLabel("Meta diaria del perfil 1")).toHaveValue("10");
  await expect(
    dialog.getByLabel("Nombre o referencia del cliente"),
  ).toHaveValue("Prueba operadora");
  await dialog.getByLabel("Cargo del perfil 1").selectOption({ label: "QA" });
  await dialog.getByLabel("Antigüedad del perfil 1").selectOption("7");
  // Contrato v20: un solo campo de años; busca de 3 menos a 3 más.
  await dialog.getByLabel("Años de experiencia del perfil 1").fill("4");
  await dialog
    .getByRole("button", { name: "Más información: años de experiencia" })
    .first()
    .focus();
  await expect(
    dialog.getByText(/Busca vacantes que pidan de 1 a 7 años\./),
  ).toBeVisible();
  // Contrato v30: dónde trabajaría, en filas «Ciudades · Países · modalidades»; la primera es donde vive.
  await dialog.getByRole("button", { name: "Quitar Colombia" }).click();
  const paises1 = dialog.getByLabel("Países de la ubicación 1, perfil 1");
  await paises1.fill("México");
  await paises1.press("Enter");
  await dialog.getByLabel("Presencial en la ubicación 1 del perfil 1").check();
  // La explicación de las filas está en su ayuda, no a la vista.
  await expect(dialog.getByText(/Una fila por lugar/)).toBeHidden();
  await dialog
    .getByRole("button", { name: "Más información: ubicaciones" })
    .hover();
  await expect(dialog.getByText(/Una fila por lugar/)).toBeVisible();
  await dialog.getByRole("button", { name: "Añadir otra ubicación" }).click();
  const paises2 = dialog.getByLabel("Países de la ubicación 2, perfil 1");
  await paises2.fill("España");
  await paises2.press("Enter");
  await dialog
    .getByRole("button", { name: "Quitar la ubicación 2 del perfil 1" })
    .click();
  await expect(paises2).toHaveCount(0);
  // Sin las casillas antiguas: «se mudaría», países sueltos y «admitir no informado».
  await expect(dialog.getByText("También se mudaría a…")).toHaveCount(0);
  await expect(
    dialog.getByText("Admitir experiencia no informada"),
  ).toHaveCount(0);
  // «Inglés requerido» solo aparece si acepta avisos en inglés.
  await dialog.getByLabel("Inglés", { exact: true }).uncheck();
  await expect(dialog.getByLabel("Inglés del perfil 1")).toHaveCount(0);
  await dialog.getByLabel("Inglés", { exact: true }).check();
  await expect(dialog.getByLabel("Inglés del perfil 1")).toBeVisible();
  // Estimación en vivo: en demostración usa avisos ficticios y no sale a internet.
  await expect(dialog.getByText(/No gasta Apify/)).toBeVisible();
  await dialog
    .getByRole("button", { name: "Buscar en internet ahora" })
    .click();
  await expect(
    dialog.getByText(/encontradas? ahora en las fuentes cumplen?/),
  ).toBeVisible();
  await expect(dialog.getByText(/Es una muestra/)).toBeVisible();
  // Vista previa: la cifra se actualiza sola mientras se edita, con el catálogo guardado.
  // La estimación en vivo también dice «cumple(n) este perfil»: buscar la frase propia de la vista previa.
  // Contrato v35: la cifra principal son los últimos 30 días, con las que siguen sin entregar al lado.
  await expect(
    dialog.getByText(/cumplieron? este perfil en los últimos 30 días/),
  ).toBeVisible();
  await expect(dialog.getByText(/aún sin entregar/)).toBeVisible();
  await dialog
    .getByRole("button", { name: "Añadir cliente", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Prueba operadora" }),
  ).toBeVisible();
  // Tarjeta compacta: sin foto ni «Activo»; «Editar» y «Vacantes» a la vista.
  const tarjetaCliente = page.locator(".client-card", {
    hasText: "Prueba operadora",
  });
  await expect(tarjetaCliente.locator(".avatar")).toHaveCount(0);
  await expect(tarjetaCliente.getByText("Activo", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    tarjetaCliente.getByRole("button", { name: "Editar Prueba operadora" }),
  ).toBeVisible();
  await expect(
    tarjetaCliente.getByRole("button", { name: "Vacantes" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Guardar borrador", exact: true })
    .click();
  await expect(
    page.getByText("Borrador guardado.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await ir(page, "Clientes");
  await expect(
    page.getByRole("heading", { name: "Prueba operadora" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Archivar Prueba operadora", exact: true })
    .click();
  await expect(
    dialog.getByText(/Las vacantes que ya recibió se conservan/),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Archivar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Prueba operadora" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Ver archivados (1)" }).click();
  await page.getByRole("button", { name: "Reactivar", exact: true }).click();
  await ir(page, "Cargos y metas");
  // La operadora suma 10 a los 120 de los demás: con techo 120 no se puede programar; con 130, sí.
  await expect(page.getByText(/pasan el techo/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Programar para mañana", exact: true }),
  ).toBeDisabled();
  // Lista grande del 16 nov: el techo se puede borrar del todo y se valida al salir del campo.
  const techo = page.getByLabel("Techo del día", { exact: true });
  await techo.fill("");
  await expect(techo).toHaveValue("");
  await techo.fill("130");
  await techo.blur();
  await expect(page.getByText(/pasan el techo/)).toHaveCount(0);
  await expect(page.locator(".cifras-cargo").first()).toContainText(
    "Meta del día",
  );
  // Lista grande (17 nov): cada cargo dice para cuántos días alcanza lo guardado.
  await expect(
    page.getByText(/Alcanza para|No alcanza para mañana/).first(),
  ).toBeVisible();
  // Accesibilidad: al cerrar con Escape el foco vuelve al botón que abrió la ventana; ningún texto bajo 12 px.
  await page.getByRole("button", { name: "Añadir cargo", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Añadir cargo", exact: true }),
  ).toBeFocused();
  const pequenos = await page.evaluate(
    () =>
      [...document.querySelectorAll("main *, aside *")].filter(
        (el) =>
          [...el.childNodes].some(
            (n) => n.nodeType === 3 && n.textContent!.trim(),
          ) && parseFloat(getComputedStyle(el).fontSize) < 12,
      ).length,
  );
  expect(pequenos).toBe(0);
  await page.route("**/api/cargos/expandir", (route) =>
    route.fulfill({
      json: {
        terminos_exactos: ["Bioacoustics Analyst"],
        terminos_similares: ["Bioacoustics Researcher"],
        fuentes: ["Vocabulario de prueba"],
        requiere_revision: false,
      },
    }),
  );
  await page.getByRole("button", { name: "Añadir cargo", exact: true }).click();
  await dialog
    .getByLabel("Cargo", { exact: true })
    .fill("Bioacoustics Analyst");
  await dialog
    .getByRole("button", { name: "Añadir cargo", exact: true })
    .click();
  await expect(
    dialog.getByText("Bioacoustics Researcher", { exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Añadir cargo", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bioacoustics Analyst", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Programar para mañana", exact: true })
    .click();
  await dialog.getByRole("button", { name: "Confirmar configuración" }).click();
  await expect(
    page.getByText("Configuración programada para el", { exact: false }),
  ).toBeVisible();
  const cfg = await (await request.get("/api/config")).json();
  expect(
    cfg.publicada.configuracion.cargos.reduce(
      (s: number, c: { cupo: number }) => s + c.cupo,
      0,
    ),
  ).toBe(130);
  expect(cfg.publicada.configuracion.techo_diario).toBe(130);
  await ir(page, "Vacantes");
  await expect(page.locator(".item-vacante")).toHaveCount(50);
  // Contrato v29: a 1366 px, la lista y la ficha de la vacante elegida, lado a lado; «Recargar lista» y las ayudas
  // explican qué hace cada cosa.
  await page.setViewportSize({ width: 1366, height: 900 });
  const lista = await page.locator(".dividida-lista").boundingBox();
  const ficha = await page.locator(".dividida-detalle").boundingBox();
  expect(ficha!.x).toBeGreaterThan(lista!.x + lista!.width - 1);
  await expect(
    page.getByRole("button", { name: "Recargar lista", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Más información: Recargar lista" })
    .hover();
  await expect(page.getByText(/No\s+busca vacantes nuevas/)).toBeVisible();
  await expect(
    page
      .getByRole("button", {
        name: "Más información: comprobación del enlace",
      })
      .first(),
  ).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", { name: "Copiar WhatsApp", exact: true })
    .click();
  await expect(dialog.getByLabel("Mensaje de WhatsApp")).toHaveValue(
    /Product Designer/,
  );
  await dialog
    .getByRole("button", { name: "Copiar el mensaje", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Mensaje copiado", exact: true }),
  ).toBeVisible();
  const texto = await page.evaluate(() => navigator.clipboard.readText());
  expect(texto).toMatch(/Hola|Buen día/);
  expect(texto).toContain("Product Designer");
  expect((texto.match(/https:\/\//g) || []).length).toBe(50);
  await dialog
    .getByRole("button", { name: "Cerrar", exact: true })
    .last()
    .click();
  const estado = await (await request.get("/api/config")).json();
  const conflicto = await request.put("/api/config", {
    headers: { Origin: "http://127.0.0.1:8001" },
    data: { revision: estado.revision - 1, configuracion: estado.borrador },
  });
  expect(conflicto.status()).toBe(409);
  // Actividad: embudo por cargo para ver dónde se pierden las vacantes.
  // Mensajes: se preparan, se abren en WhatsApp con el texto y se marcan como enviados.
  await ir(page, "Mensajes");
  await page.getByRole("button", { name: "Preparar mensajes" }).click();
  const abrir = page.getByRole("link", { name: "Abrir en WhatsApp" }).first();
  await expect(abrir).toHaveAttribute("href", /^https:\/\/wa\.me\/\d+\?text=/);
  const antes = await page
    .getByRole("link", { name: "Abrir en WhatsApp" })
    .count();
  await page
    .getByRole("button", { name: "Marcar como enviado" })
    .first()
    .click();
  await expect(
    page.getByRole("link", { name: "Abrir en WhatsApp" }),
  ).toHaveCount(antes - 1);
  await ir(page, "Actividad");
  // Sin avisos por correo: el operador no quiere servicios externos (13 nov).
  await expect(page.getByText("Avisos por correo")).toHaveCount(0);
  // Sección 8: el embudo de la última búsqueda se ve abierto, en tarjetas y sin desbordar.
  const embudo = page.locator(".embudo-cargo").first();
  // Contrato v31: etapas con nombres claros y qué hacer en la que más pierde.
  await expect(embudo.getByText("Abiertas y vigentes hoy")).toBeVisible();
  await expect(embudo.getByText("Qué hacer:")).toBeVisible();
  for (const ancho of [1366, 390]) {
    await page.setViewportSize({ width: ancho, height: 900 });
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <= innerWidth &&
          [...document.querySelectorAll(".embudo-cargo")].every(
            (e) => e.scrollWidth <= e.clientWidth,
          ),
      ),
    ).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // El conflicto intencional se produce desde request, no desde la página.
  expect(errores).toEqual([]);
  await page.screenshot({
    path: "/tmp/adaptia-panel-vacantes.png",
    fullPage: false,
  });
});

test("móvil: navegación accesible y sin desbordamiento horizontal", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Resumen" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/adaptia-panel-movil.png",
    fullPage: true,
  });
  await ir(page, "Clientes");
});

test("bandeja Por confirmar: un clic confirma, atajo 4 aparta y el contador baja", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.goto("/");
  await expect(tarjeta(page, "Por confirmar")).toContainText("4"); // 3 de ubicación + 1 por funciones (v25)
  await ir(page, "Por confirmar");
  // Contrato v29: la lista con el total real a la izquierda y la decisión con el aviso completo a la derecha.
  await expect(page.locator(".item-revision")).toHaveCount(4);
  await expect(page.getByText("4 pendientes", { exact: true })).toBeVisible();
  const primera = page.locator("article.revision");
  await expect(primera.locator(".revision-pista")).toBeVisible();
  await expect(primera.locator(".ficha-descripcion")).toBeVisible();
  // Contrato v34: los mismos datos del aviso que en «Vacantes» (ubicación, modalidad, publicación, idioma).
  await expect(primera.locator(".ficha-datos")).toContainText("Publicada el");
  await expect(primera.locator(".ficha-datos")).toContainText("Aviso en");
  await expect(
    page
      .locator(".item-revision", { hasText: "Experience Lead" })
      .locator(".pais-leido"),
  ).toHaveText("Colombia");
  // Filtro por cliente: muestra solo las suyas y vuelve a todas.
  await page
    .locator("#revision-cliente")
    .selectOption({ label: "Cliente de ejemplo 01 (2)" }); // contrato v34: cuántas tiene cada cliente
  await expect(page.getByText(/de este cliente/)).toBeVisible();
  // Contrato v34: «Para» y las páginas no se mueven aunque haya una sola página.
  await expect(page.locator(".revision-barra > *").first()).toHaveClass(
    /revision-filtro/,
  );
  await expect(
    page.getByRole("navigation", { name: "Páginas de Por confirmar" }),
  ).toBeVisible();
  await page.locator("#revision-cliente").selectOption({ value: "" });
  await expect(page.locator(".item-revision")).toHaveCount(4);
  // Ampliación v17: cada tarjeta trae la respuesta sugerida y por qué; Enter la acepta.
  await expect(primera.locator(".revision-sugerencia")).toContainText(
    "Sugerencia: sirve",
  );
  await expect(
    primera.getByRole("button", { name: "Aceptar sugerencia" }),
  ).toBeVisible();
  await primera.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByText(/Confirmada: se asignó a \d+ cliente/),
  ).toBeVisible();
  await expect(page.locator(".item-revision")).toHaveCount(3);
  // Pasa sola a la siguiente y conserva el foco: el atajo sigue funcionando sin volver a hacer clic.
  await expect(page.locator(".item-revision").first()).toHaveAttribute(
    "aria-current",
    "true",
  );
  await expect(primera).toBeFocused();
  await page.keyboard.press("4");
  await expect(page.getByText("Apartada por ahora.")).toBeVisible();
  await expect(page.locator(".item-revision")).toHaveCount(2);
  const pequenos = await page.evaluate(
    () =>
      [...document.querySelectorAll("main *")].filter(
        (el) =>
          [...el.childNodes].some(
            (n) => n.nodeType === 3 && n.textContent!.trim(),
          ) && parseFloat(getComputedStyle(el).fontSize) < 12,
      ).length,
  );
  expect(pequenos).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/adaptia-por-confirmar.png",
    fullPage: true,
  });
  // Al volver, la tarjeta del resumen muestra el contador al día.
  await page.getByRole("button", { name: "Volver al resumen" }).click();
  await expect(tarjeta(page, "Por confirmar")).toContainText("2");
  expect(errores).toEqual([]);
});

test("revisión masiva por CSV y reglas aprendidas sin IA", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Por confirmar");
  await expect(
    page.getByRole("link", { name: "Descargar todas (CSV)" }),
  ).toHaveAttribute("href", "/api/revisiones.csv");
  expect(
    (await (await request.get("/api/revisiones.csv")).text()).split("\n")[0],
  ).toContain("decision,pais,por_que,cargo,empresa,ubicacion");
  // Descarga de la base para el cliente: sin las vacantes con país sin confirmar.
  const base = await (await request.get("/api/base.csv")).text();
  expect(base).toContain("demo-1");
  expect(base).not.toContain("demo-2");
  // Depuración completa (v17): un botón llena la bandeja sin esperar la búsqueda de la noche.
  await page
    .getByRole("button", { name: "Cargar todas las dudosas de la base" })
    .click();
  await expect(
    page.getByText(/Bandeja lista: \d+ por confirmar/),
  ).toBeVisible();
  // Basta con las columnas que se llenan; los demás datos del CSV descargado son para leer.
  const revisiones = await (await request.get("/api/revisiones")).json();
  const granada = revisiones.pendientes.find(
    (r: { ubicacion: string }) => r.ubicacion === "Granada",
  );
  const csvLlenado = `vacante_id;decision;pais;aplicar_a_iguales\n${granada.vacante_id};sí;España;sí\n`;
  await page.locator('input[type="file"]').setInputFiles({
    name: "revision.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csvLlenado),
  });
  await expect(page.getByText(/Revisión aplicada: 1 decididas/)).toBeVisible();
  await ir(page, "Actividad");
  // Auditoría H4: el resultado de la búsqueda va primero; las reglas, al final y plegadas.
  await page.getByRole("button", { name: /Ver reglas de ubicación/ }).click();
  const regla = page.locator(".reglas-lista li", { hasText: "«granada»" });
  await expect(regla).toContainText("España");
  await regla.getByRole("button", { name: "Desactivar" }).click();
  await expect(page.getByText("Regla desactivada.")).toBeVisible();
  await expect(regla.getByRole("button", { name: "Activar" })).toBeVisible();
  // Descarga de la base desde Vacantes, con el conteo a la vista.
  await ir(page, "Vacantes");
  await page
    .getByRole("button", { name: "Descargar CSV", exact: true })
    .click();
  await expect(
    page.getByText(
      /CSV descargado: 1 vacantes \(1 sin confirmar quedaron fuera\)/,
    ),
  ).toBeVisible();
});

test("resumen: tablero de una pantalla, sin menú propio, con dirección por sección", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Resumen" }),
  ).toBeVisible();
  await expect(page.locator(".tarjeta-resumen")).toHaveCount(6);
  await expect(page.locator("aside, header.topbar, footer")).toHaveCount(0);
  await expect(page.getByText("TU CENTRO DE OPORTUNIDADES")).toHaveCount(0);
  // Paso 8: la lista de clientes crece con ellos (Andrés maneja 15 o más); lo demás del tablero se ve sin bajar.
  await page.waitForTimeout(700); // termina la animación de entrada
  // Lista grande (17 nov, variante B): los indicadores y Actividad arriba se ven sin bajar; los clientes van debajo.
  const fondo = await page
    .locator(".resumen-arriba")
    .evaluate((e) => e.getBoundingClientRect().bottom);
  expect(fondo).toBeLessThanOrEqual(768);
  await expect(page.locator(".dona-techo")).toBeVisible();
  await page.screenshot({ path: "/tmp/adaptia-resumen.png" });
  await tarjeta(page, "Clientes").click();
  await expect(page).toHaveURL(/#clientes$/);
  await page.goBack();
  await expect(
    page.getByRole("heading", { level: 1, name: "Resumen" }),
  ).toBeVisible();
  await page.goto("/#actividad");
  await expect(
    page.getByRole("heading", { level: 1, name: "Actividad" }),
  ).toBeVisible();
  // Contrato v37: cobertura por persona, con su estado y por qué le faltan.
  await expect(
    page.getByRole("heading", { name: /Cobertura por persona/ }),
  ).toBeVisible();
  await expect(page.locator(".tabla-cobertura tbody tr").first()).toBeVisible();
  await expect(page.locator(".tabla-cobertura")).toContainText(
    /Mínimo cubierto|Aún sin datos|Mínimo pendiente/,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".tarjeta-resumen")).toHaveCount(6);
  const cajas = await page
    .locator(".tarjeta-resumen")
    .evaluateAll((els) => els.map((e) => e.getBoundingClientRect().left));
  expect(new Set(cajas).size).toBe(1); // una columna en el móvil
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("arreglos de la auditoría: error de carga, textos, título y botones táctiles", async ({
  page,
}) => {
  // H1: si el servidor falla, Vacantes lo dice y ofrece reintentar (no «Programa la configuración»).
  await page.route(/\/api\/resultados/, (r) =>
    r.fulfill({
      status: 500,
      contentType: "application/json",
      body: '{"detail":"x"}',
    }),
  );
  await page.goto("/#vacantes");
  await expect(
    page.getByText("No se pudieron cargar las vacantes"),
  ).toBeVisible();
  await expect(
    page.getByText("Programa la configuración para empezar"),
  ).toHaveCount(0);
  await page.unroute(/\/api\/resultados/);
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.locator(".item-vacante").first()).toBeVisible();
  // H6: «1 año», nunca «1 años».
  await expect(page.getByText("1 años exigidos")).toHaveCount(0);
  // H8: la pestaña dice en qué sección estás.
  await expect(page).toHaveTitle("Vacantes · Scraper");
  // H2 y H4: sin «noche»; primero el resultado, luego las reglas.
  await page.goto("/#actividad");
  await expect(page.getByText(/Cada noche|búsqueda nocturna/)).toHaveCount(0);
  const orden = await page
    .locator("main h2")
    .evaluateAll((hs) => hs.map((h) => h.textContent || ""));
  expect(orden[0]).toContain("Resultado de cada búsqueda diaria");
  // H3: «Entregadas» explica por qué puede superar a la etapa anterior.
  await expect(
    page
      .getByRole("button", { name: /Más información: entregadas de/ })
      .first(),
  ).toBeVisible();
  // H5: botones de texto con al menos 40 px de alto en el celular.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#clientes");
  await page.locator(".client-card").first().waitFor();
  for (const boton of [
    page.getByRole("button", { name: "Volver al resumen" }),
    page.getByRole("button", { name: /^Editar / }).first(),
  ]) {
    const caja = await boton.boundingBox();
    expect(caja!.height).toBeGreaterThanOrEqual(40);
  }
});

test("reunión 14 nov: comas separan términos y el cliente se recupera tras cerrar", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.goto("/");
  // Términos del cargo: escribir o pegar con comas crea una etiqueta por término.
  await ir(page, "Cargos y metas");
  await page.getByRole("button", { name: "Añadir cargo" }).first().click();
  const cargo = page.locator("dialog", { hasText: "Añadir un cargo" });
  const afines = cargo.getByLabel("Nombres del cargo");
  await afines.fill("UX Writer, Content Designer; Redactor UX");
  await afines.press("Enter");
  for (const t of ["UX Writer", "Content Designer", "Redactor UX"])
    await expect(
      cargo.getByRole("button", { name: "Quitar " + t }),
    ).toBeVisible();
  await expect(
    cargo.getByRole("button", { name: /Quitar UX Writer, Content/ }),
  ).toHaveCount(0);
  await cargo.getByRole("button", { name: "Cancelar" }).click();
  // Borrador del cliente: lo escrito vuelve al reabrir aunque el formulario se haya cerrado sin guardar.
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Nombre o referencia del cliente")
    .fill("Cliente a recuperar");
  await dialog.getByRole("button", { name: "Cerrar" }).click();
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Tienes cambios sin guardar")).toBeVisible();
  await dialog
    .getByRole("button", { name: "Recuperar lo que escribías" })
    .click();
  await expect(
    dialog.getByLabel("Nombre o referencia del cliente"),
  ).toHaveValue("Cliente a recuperar");
  // «Cancelar» descarta a propósito: la próxima vez no se ofrece nada.
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByText("Tienes cambios sin guardar"),
  ).toHaveCount(0);
  expect(errores).toEqual([]);
});

test("CSV por cliente o de todos, del día o de toda la base", async ({
  page,
}) => {
  await page.goto("/");
  await ir(page, "Vacantes");
  await expect(page.getByLabel("Fecha", { exact: true })).toBeEnabled();
  await page.getByLabel("Toda la base").check();
  await expect(page.getByLabel("Fecha", { exact: true })).toBeDisabled();
  const cliente = page.getByLabel("Clientes", { exact: true });
  await cliente.selectOption({ index: 1 });
  const nombre = (await cliente.locator("option:checked").textContent()) || "";
  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Descargar CSV", exact: true }).click(),
  ]);
  expect(descarga.suggestedFilename()).toMatch(
    /^vacantes-base-[a-z0-9-]+\.csv$/,
  );
  expect(descarga.suggestedFilename()).toContain(
    nombre
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, ""),
  );
  await expect(page.getByText(/CSV descargado: \d+ vacantes/)).toBeVisible();
});

test("contrato v22: restricciones, prioridades y margen de años en el perfil", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Editar Cliente de ejemplo 01", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Años de experiencia del perfil 1").fill("6");
  await dialog.getByLabel("Margen de años del perfil 1").selectOption("4");
  // Contrato v35: la explicación de los años está en el «ⓘ» junto al título.
  await dialog
    .getByRole("button", { name: "Más información: años de experiencia" })
    .first()
    .focus();
  await expect(
    dialog.getByText(/de 2 a 10 años\. Las junior o de prácticas van al final/),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Prioridades (opcional)" }).click();
  const sectores = dialog.getByLabel("Sectores preferidos del perfil 1");
  await sectores.fill("Fintech, B2B SaaS");
  await sectores.press("Enter");
  await expect(
    dialog.getByRole("button", { name: "Quitar B2B SaaS" }),
  ).toBeVisible();
  await dialog
    .getByLabel("Añadir restricción al perfil 1")
    .selectOption("palabras");
  const palabras = dialog.getByLabel("Vacantes que mencionan (perfil 1)");
  await palabras.fill("call center");
  await palabras.press("Enter");
  await dialog
    .getByLabel("Añadir restricción al perfil 1")
    .selectOption("salario_minimo"); // a medio llenar: no se guarda
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await page
    .getByRole("button", { name: "Guardar borrador", exact: true })
    .click();
  await expect(
    page.getByText("Borrador guardado.", { exact: false }),
  ).toBeVisible();
  const cfg = await (await request.get("/api/config")).json();
  const perfil = cfg.borrador.perfiles.find(
    (p: { cliente_id: string }) => p.cliente_id === cfg.borrador.clientes[0].id,
  );
  expect(perfil.margen_experiencia).toBe(4);
  expect(perfil.experiencia_min).toBe(2);
  expect(perfil.sectores_preferidos).toEqual(["Fintech", "B2B SaaS"]);
  expect(perfil.restricciones).toEqual([
    { tipo: "palabras", palabras: ["call center"] },
  ]);
});

test("contrato v23 y v30: ubicaciones en filas, permiso de trabajo, horario y ciudades", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Editar Cliente de ejemplo 01", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  // Contrato v30: primera fila en Alemania (Berlín, presencial) y otra fila de EE. UU. en remoto (antes «puede
  // trabajar legalmente en»).
  await dialog.getByRole("button", { name: "Quitar Colombia" }).click();
  const paises1 = dialog.getByLabel("Países de la ubicación 1, perfil 1");
  await paises1.fill("Alemania");
  await paises1.press("Enter");
  await dialog.getByLabel("Presencial en la ubicación 1 del perfil 1").check();
  const ciudades = dialog.getByLabel("Ciudades de la ubicación 1, perfil 1");
  await ciudades.fill("Berlín");
  await ciudades.press("Enter");
  await dialog.getByRole("button", { name: "Añadir otra ubicación" }).click();
  const paises2 = dialog.getByLabel("Países de la ubicación 2, perfil 1");
  await paises2.fill("Estados Unidos");
  await paises2.press("Enter");
  await expect(
    dialog.getByRole("button", { name: "Quitar Estados Unidos" }),
  ).toBeVisible();
  // Contrato v35: zonas horarias en una lista, con sus ciudades.
  await dialog
    .getByLabel("Añadir zona horaria al perfil 1")
    .selectOption("UTC-5");
  await expect(
    dialog.getByRole("button", {
      name: "Quitar UTC−5 · Bogotá, Lima, Nueva York del perfil 1",
    }),
  ).toBeVisible();
  // «Otra…» restricción en texto libre (solo ordena) y la cifra de 30 días que no asusta.
  await dialog
    .getByLabel("Añadir restricción al perfil 1")
    .selectOption("otra");
  await dialog
    .getByLabel("Otra restricción del perfil 1")
    .fill("agencias de reclutamiento");
  await expect(
    dialog.getByText(/cumplieron este perfil en los últimos 30 días/).first(),
  ).toBeVisible();
  await expect(dialog.getByText(/al día/).first()).toBeVisible();
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(
    page.locator(".client-card", { hasText: "Cliente de ejemplo 01" }),
  ).toContainText("Alemania");
  await page
    .getByRole("button", { name: "Guardar borrador", exact: true })
    .click();
  await expect(
    page.getByText("Borrador guardado.", { exact: false }),
  ).toBeVisible();
  const cfg = await (await request.get("/api/config")).json();
  const perfil = cfg.borrador.perfiles.find(
    (p: { cliente_id: string }) => p.cliente_id === cfg.borrador.clientes[0].id,
  );
  expect(perfil.vive_en).toBe("DE");
  expect(perfil.ciudades).toEqual(["Berlín"]);
  expect(perfil.puede_trabajar_en).toEqual(["US"]);
  expect(perfil.acepta_horario).toEqual(["UTC-5"]);
  expect(perfil.ubicaciones).toEqual([
    {
      paises: ["DE"],
      ciudades: ["Berlín"],
      modalidades: ["remoto", "presencial"],
    },
    { paises: ["US"], ciudades: [], modalidades: ["remoto"] },
  ]);
});

test("contrato v25: proponer funciones y confirmar una vacante que coincide por funciones", async ({
  page,
}) => {
  await page.goto("/");
  await ir(page, "Cargos y metas");
  await page
    .getByRole("button", { name: /^Editar Product Designer/ })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  // Paso 7: una sola lista visible; lo demás, plegado en «Opciones avanzadas».
  await expect(dialog.getByLabel("Nombres del cargo")).toBeVisible();
  await expect(dialog.getByLabel("Excluir estos términos")).toHaveCount(0);
  await dialog.getByRole("button", { name: /^Opciones avanzadas/ }).click();
  await expect(dialog.getByLabel("Excluir estos términos")).toBeVisible();
  await dialog.getByRole("button", { name: "Proponer funciones" }).click();
  await expect(page.getByText(/Se propusieron \d+ funciones/)).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Quitar user research" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  await ir(page, "Por confirmar");
  const tarjeta = page.locator("article", { hasText: "Experience Lead" });
  await expect(tarjeta.getByText("Coincide por funciones")).toBeVisible();
  await expect(tarjeta.getByText("Solo para otro país")).toHaveCount(0);
  await tarjeta.getByRole("button", { name: /^Sirve/ }).click();
  await expect(
    page.getByText(/Confirmada: se asignó a 1 cliente/),
  ).toBeVisible();
});

test("paso 8: una tarjeta por cliente, detalle con 7 días y dos columnas desde 9 clientes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  // Una «por confirmar» propia para «Cliente de ejemplo 02» (otros recorridos ya decidieron las de la demostración).
  const cfg = await (await page.request.get("/api/config")).json();
  const id02 = cfg.borrador.clientes.find(
    (c: { nombre: string }) => c.nombre === "Cliente de ejemplo 02",
  ).id;
  let decidida = "";
  // Contrato v29: el Resumen y el detalle piden páginas (`?pagina=…`); el total y el conteo por cliente vienen aparte.
  await page.route(/\/api\/revisiones(\?.*)?$/, async (route) => {
    const r = await route.fetch();
    const j = await r.json();
    const deOtro =
      new URL(route.request().url()).searchParams.get("cliente_id") || id02;
    if (!decidida && deOtro === id02) {
      j.pendientes.unshift({
        vacante_id: "prueba-paso-8",
        titulo: "Diseñador de producto (prueba)",
        empresa: "Empresa de prueba",
        ubicacion: "Remoto",
        modalidad: "remoto",
        idioma: "es",
        publicada: "",
        enlace: "",
        pista: "",
        sugerencia: ["ES"],
        sugerida: "sirve",
        paises_sugeridos: ["ES"],
        clientes: ["Cliente de ejemplo 02"],
        cliente_ids: [id02],
        ayuda_faltantes: true,
        iguales: 0,
      });
      j.total += 1;
      j.en_espera = (j.en_espera ?? 0) + 1;
      j.por_cliente = {
        ...j.por_cliente,
        [id02]: (j.por_cliente?.[id02] ?? 0) + 1,
      };
    }
    await route.fulfill({ response: r, json: j });
  });
  await page.route("**/api/revisiones/prueba-paso-8", async (route) => {
    decidida = route.request().postDataJSON().decision;
    await route.fulfill({ json: { asignadas: 0, iguales: 0 } });
  });
  await page.goto("/");
  const lista = page.getByRole("list", { name: "Clientes y su avance" });
  await expect(lista.getByRole("button").first()).toBeVisible();
  // Otros recorridos pueden haber añadido clientes a la demostración.
  const activos = await lista.getByRole("button").count();
  expect(activos).toBeGreaterThanOrEqual(5);
  expect(activos).toBeLessThan(9);
  await expect(page.getByText(/activos · \d+ bajo su meta/)).toBeVisible();
  await expect(lista).not.toHaveClass(/en-grilla/);
  await expect(
    lista.getByRole("button", { name: /^Cliente de ejemplo 02:/ }),
  ).toHaveAccessibleName(/: \d+ de 17, \d+ por confirmar, bajo su meta/);
  // Los que van peor van primero; el que está completo, después.
  const nombres = await lista.getByRole("button").allTextContents();
  expect(
    nombres.findIndex((t) => t.startsWith("Cliente de ejemplo 02")),
  ).toBeLessThan(
    nombres.findIndex((t) => t.startsWith("Cliente de ejemplo 04")),
  );

  const nombre = "Cliente de ejemplo 02";
  const boton02 = lista.getByRole("button", {
    name: /^Cliente de ejemplo 02:/,
  });
  await expect(boton02).toHaveAccessibleName(/, [1-9]\d* por confirmar/);
  const pendientesAntes = Number(
    /, (\d+) por confirmar/.exec(
      (await boton02.getAttribute("aria-label"))!,
    )![1],
  );
  await boton02.click();
  const detalle = page.locator("dialog[open]");
  await expect(detalle.getByRole("heading", { name: nombre })).toBeVisible();
  await expect(detalle.getByText("Últimos 7 días")).toBeVisible();
  await expect(
    detalle.getByRole("img", { name: /^Recibidas por día:/ }),
  ).toBeVisible();
  await expect(detalle.getByText("Lo que más corta en su cargo")).toBeVisible();
  await expect(
    detalle.getByText(`Por confirmar (${pendientesAntes})`),
  ).toBeVisible();
  const descarga = page.waitForEvent("download");
  await detalle
    .getByRole("button", { name: "Descargar su CSV de hoy" })
    .click();
  expect((await descarga).suggestedFilename()).toMatch(
    /^vacantes-\d{4}-\d{2}-\d{2}-cliente-de-ejemplo-02\.csv$/,
  );
  // Decidir ahí mismo: «No sirve» la saca de su lista.
  const tarjeta = detalle.locator("article", {
    hasText: "Diseñador de producto (prueba)",
  });
  await expect(tarjeta.getByText("sugerido: España")).toBeVisible();
  await tarjeta.getByRole("button", { name: "No sirve" }).click();
  await expect(
    detalle.getByText(`Por confirmar (${pendientesAntes - 1})`),
  ).toBeVisible();
  expect(decidida).toBe("no_sirve");
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await detalle.getByRole("button", { name: "Ver sus vacantes" }).click();
  await expect(page).toHaveURL(/#vacantes(\/[^/]+)?$/);
  await expect(page.locator("#result-cliente")).toHaveValue(
    await page
      .locator("#result-cliente option", { hasText: nombre })
      .getAttribute("value"),
  );

  // Con 12 clientes (Andrés maneja al menos 15): dos columnas, sin desbordar.
  await page.route("**/api/config", async (route) => {
    const r = await route.fetch();
    const j = await r.json();
    const cfg = j.borrador;
    const base = cfg.clientes[0];
    const perfil = cfg.perfiles.find(
      (p: { cliente_id: string }) => p.cliente_id === base.id,
    );
    for (let i = 0; i < 7; i++) {
      const id = `00000000-0000-4000-8000-00000000000${i}`;
      cfg.clientes.push({ ...base, id, nombre: `Cliente extra ${i + 1}` });
      cfg.perfiles.push({
        ...perfil,
        id: `00000000-0000-4000-9000-00000000000${i}`,
        cliente_id: id,
      });
    }
    await route.fulfill({ response: r, json: j });
  });
  await page.goto("/");
  await expect(lista.getByRole("button")).toHaveCount(activos + 7);
  await expect(lista).toHaveClass(/en-grilla/);
  const columnas = await lista.evaluate(
    (e) => getComputedStyle(e).gridTemplateColumns.split(" ").length,
  );
  // Lista grande (17 nov): los clientes ocupan todo el ancho, con 4 o más columnas en 1366 px.
  expect(columnas).toBeGreaterThanOrEqual(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await lista.evaluate(
      (e) => getComputedStyle(e).gridTemplateColumns.split(" ").length,
    ),
  ).toBe(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("paso 9: modo oscuro con botón, recordado, por la dirección o por el sistema, y con contraste AA", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.goto("/");
  const html = page.locator("html");
  await expect(html).not.toHaveAttribute("data-tema", /.+/);
  await page.getByRole("button", { name: "Cambiar a modo oscuro" }).click();
  await expect(html).toHaveAttribute("data-tema", "oscuro");
  await page.reload();
  await expect(html).toHaveAttribute("data-tema", "oscuro");
  const fondo = () =>
    page.evaluate(
      () => getComputedStyle(document.documentElement).backgroundColor,
    );
  expect(await fondo()).toBe("rgb(5, 7, 14)");

  // Contraste AA en oscuro, sección por sección (y con los formularios abiertos).
  const revisar = async (donde: string) => {
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.waitForTimeout(300);
    const fallos = await page.evaluate(revisarContraste);
    expect(fallos, donde).toEqual([]);
  };
  for (const h of [
    "",
    "#clientes",
    "#cargos",
    "#vacantes",
    "#por-confirmar",
    "#actividad",
    "#mensajes",
  ]) {
    await page.goto("/" + h);
    await revisar(h || "resumen");
  }
  await page.goto("/#clientes");
  await page
    .getByRole("button", { name: /^Editar / })
    .first()
    .click();
  await revisar("formulario de cliente");
  await page.keyboard.press("Escape");
  await page.goto("/");
  await page.locator(".cliente-mini").first().click();
  await revisar("detalle de cliente");
  await page.keyboard.press("Escape");

  // Volver a claro: se recuerda igual.
  await page.getByRole("button", { name: "Cambiar a modo claro" }).click();
  await expect(html).toHaveAttribute("data-tema", "claro");
  await page.reload();
  expect(await fondo()).toBe("rgb(240, 247, 255)");
  await revisar("resumen en claro");

  // Sin elección, sigue el modo del computador.
  await page.evaluate(() => localStorage.removeItem("tema"));
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await expect(html).not.toHaveAttribute("data-tema", /.+/);
  expect(await fondo()).toBe("rgb(5, 7, 14)");
  await expect(
    page.getByRole("button", { name: "Cambiar a modo claro" }),
  ).toBeVisible();

  // ?tema=oscuro (lo que mandaría Adaptia) manda sobre el sistema y no se guarda.
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?tema=oscuro");
  await expect(html).toHaveAttribute("data-tema", "oscuro");
  expect(await page.evaluate(() => localStorage.getItem("tema"))).toBeNull();
  await page.goto("/?tema=claro");
  await expect(html).toHaveAttribute("data-tema", "claro");
});

// Va al final: reemplaza a los clientes de la demostración.
test("importar clientes: vista previa con errores, borrar los actuales y programar con los nuevos", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/#clientes");
  await page.getByRole("button", { name: "Importar clientes" }).click();
  const dialogo = page.locator("dialog[open]");
  await expect(
    dialogo.getByRole("link", { name: "Descargar plantilla" }),
  ).toHaveAttribute("href", "/api/clientes/plantilla.csv");
  const subir = (texto: string) =>
    dialogo.getByLabel("Archivo CSV").setInputFiles({
      name: "clientes.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(texto),
    });
  await subir(
    "nombre;cargo;vive_en;modalidades\n" +
      "Persona Uno;Product Designer;Colombia;remoto\n" +
      "Persona Dos;Cargo Importado;Narnia;remoto\n",
  );
  await expect(
    dialogo.getByText("no reconozco el país «Narnia»"),
  ).toBeVisible();
  await expect(
    dialogo.getByRole("button", { name: /^Importar 2 clientes/ }),
  ).toBeDisabled();

  await subir(
    "nombre;cargo;vive_en;modalidades;whatsapp;acepto_whatsapp\n" +
      "Persona Uno;Product Designer;Colombia;remoto|híbrido;+57 300 111 2222;sí\n" +
      "Persona Dos;Cargo Importado;México;remoto;;\n" +
      "Persona Tres;QA;España;presencial;;\n" +
      "Cliente de ejemplo 02;Product Designer;Colombia;remoto;;\n",
  );
  await expect(dialogo.getByText("4 clientes con 4 perfiles")).toBeVisible();
  // Quien ya existe se actualiza y conserva lo que recibió (16 nov); los demás son nuevos.
  await expect(
    dialogo.getByText(
      /1 se actualiza \(conservan lo que ya recibieron\) · 3 nuevos/,
    ),
  ).toBeVisible();
  await expect(
    dialogo.getByText(/Cargos nuevos: Cargo Importado/),
  ).toBeVisible();
  await dialogo.getByLabel("Borrarlos del todo").check();
  await expect(
    dialogo.getByText(/Se borrarán del todo: Cliente de ejemplo/),
  ).toBeVisible();
  const importar = dialogo.getByRole("button", { name: "Importar 4 clientes" });
  await expect(importar).toBeDisabled(); // falta escribir BORRAR
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  await dialogo.getByLabel("Escribe BORRAR para confirmar").fill("BORRAR");
  await importar.click();
  await expect(
    page.getByText(/1 cliente actualizado .*3 nuevos, \d+ borrados/),
  ).toBeVisible();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await expect(page.getByText("Cliente de ejemplo 01")).toHaveCount(0);
  for (const n of ["Persona Uno", "Persona Dos", "Persona Tres"])
    await expect(page.getByRole("heading", { name: n })).toBeVisible();

  // Quedan guardados de verdad: al recargar siguen ahí y se pueden programar.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Persona Uno" }),
  ).toBeVisible();
  await page.goto("/");
  const lista = page.getByRole("list", { name: "Clientes y su avance" });
  await expect(lista.getByRole("button")).toHaveCount(4);
  // El cliente actualizado sigue mostrando lo que recibió hoy.
  await expect(
    lista.getByRole("button", { name: /^Cliente de ejemplo 02:/ }),
  ).toHaveAccessibleName(/: [1-9]\d* de 10/);
  await page
    .getByRole("button", { name: "Programar para mañana", exact: true })
    .click();
  await page
    .locator("dialog[open]")
    .getByRole("button", { name: "Confirmar configuración" })
    .click();
  await expect(page.locator(".flow-pill")).toHaveText(
    /se usa desde la búsqueda de mañana/,
  );

  // Eliminar definitivamente un cliente archivado.
  await page.goto("/#clientes");
  await page.getByRole("button", { name: /^Archivar Persona Tres/ }).click();
  await page
    .locator("dialog[open]")
    .getByRole("button", { name: /Archivar/ })
    .last()
    .click();
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await page.getByRole("button", { name: /Ver archivados/ }).click();
  await page.getByRole("button", { name: "Eliminar definitivamente" }).click();
  const borrar = page.locator("dialog[open]");
  await borrar.getByLabel("Escribe BORRAR para confirmar").fill("BORRAR");
  await borrar
    .getByRole("button", { name: "Eliminar definitivamente" })
    .click();
  await expect(
    page.getByText("«Persona Tres» se eliminó definitivamente."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Ver archivados/ }),
  ).toHaveCount(0);
});

test("contrato v27: aplicar hoy, etiquetas de lo que no cumple y distintivo de Comunidad", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Editar Cliente de ejemplo 02", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/Es «Comunidad»/).check();
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(
    page.locator(".client-card h3", { hasText: "Cliente de ejemplo 02" }),
  ).toContainText("Comunidad");
  await page
    .getByRole("button", { name: "Programar para mañana", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Aplicar hoy", exact: true })
    .click();
  await expect(
    page.getByText("Configuración aplicada desde hoy", { exact: false }),
  ).toBeVisible();
  const cfg = await (await request.get("/api/config")).json();
  const hoy = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Bogota",
  }).format(new Date());
  expect(cfg.publicada.vigente_desde).toBe(hoy);
  await page.getByRole("button", { name: "Volver al resumen" }).click();
  await expect(
    page.getByRole("button", { name: /Cliente de ejemplo 02 \(Comunidad\)/ }),
  ).toBeVisible();
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  // Una vacante que pide más años que el perfil llega igual, con su etiqueta.
  await ir(page, "Vacantes");
  await expect(
    page
      .locator(".no-cumple", { hasText: "Pide 7 años de experiencia" })
      .first(),
  ).toBeVisible();
  expect(await page.evaluate(revisarContraste)).toEqual([]);
});

// PR 1.5 (16 nov): accesibilidad automática con axe (WCAG 2.1 A y AA) en cada pantalla y en el formulario de cliente.
// Bloquea lo «serio» y lo «crítico»; el contraste lo mide también `revisarContraste`, en claro y en oscuro.
test("auditoría axe: sin fallos serios de accesibilidad en ninguna pantalla", async ({
  page,
}) => {
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  await page.emulateMedia({ reducedMotion: "reduce" }); // sin animaciones: axe mide los colores finales
  const graves = async (donde: string) => {
    const r = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const fallos = r.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.target}`);
    expect(fallos, donde).toEqual([]);
  };
  for (const h of [
    "",
    "#clientes",
    "#cargos",
    "#vacantes",
    "#por-confirmar",
    "#mensajes",
    "#actividad",
  ]) {
    await page.goto("/" + h);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.waitForTimeout(300);
    await graves(h || "#resumen");
  }
  await page.goto("/#clientes");
  // El estado de la demostración lo comparten las pruebas: se abre el primer cliente que haya.
  await page
    .getByRole("button", { name: /^Editar / })
    .first()
    .click();
  await page.getByRole("dialog").waitFor();
  await graves("formulario de cliente");
});

test("lista grande 16 nov: detalle en dos paneles, editar perfil y archivar cargos arrastrando", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await expect(page.locator(".flow-pill")).not.toHaveText(/Programado desde/);
  await page.locator(".cliente-mini").first().click();
  const detalle = page.getByRole("dialog");
  await expect(detalle.locator(".detalle-dos-paneles")).toBeVisible();
  await expect(detalle.locator(".detalle-derecha")).toContainText(
    "Por confirmar",
  );
  await detalle.getByRole("button", { name: "Editar perfil" }).first().click();
  await expect(
    page.getByRole("dialog").getByText("Editar cliente", { exact: false }),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  // Lista grande (17 nov): deshacer un cambio deja el panel «sin cambios» (no pide guardar otra vez).
  await page.goto("/#cargos");
  const techoCampo = page.locator("#techo-diario");
  const original = await techoCampo.inputValue();
  await techoCampo.fill(String(Number(original) + 5));
  await techoCampo.blur();
  await expect(
    page.getByRole("button", { name: "Guardar borrador" }),
  ).toBeEnabled();
  await techoCampo.fill(original);
  await techoCampo.blur();
  await expect(
    page.getByRole("button", { name: "Guardar borrador" }),
  ).toBeDisabled();
  // Ventana alta: la franja de archivados queda a la vista y el arrastre no desplaza la página a mitad de camino.
  await page.setViewportSize({ width: 1366, height: 1400 });
  await page.goto("/#cargos");
  const tarjeta = page.locator(".role-card").first();
  const nombre = (await tarjeta.locator("h3").textContent()) || "";
  await tarjeta.dragTo(page.locator(".cargos-archivados"));
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("Archivar cargo");
  await expect(dialogo.getByRole("alert")).toContainText("cliente");
  await dialogo.getByRole("button", { name: "Archivar", exact: true }).click();
  await expect(page.locator(".cargos-archivados")).toContainText(nombre);
  // Vuelve solo al asignárselo a un perfil.
  await page.goto("/#clientes");
  await page
    .getByRole("button", { name: /^Editar / })
    .first()
    .click();
  const cargo = page.getByLabel("Cargo del perfil 1");
  const valor = await cargo
    .locator("option", { hasText: nombre + " (archivado" })
    .getAttribute("value");
  await cargo.selectOption(valor || "");
  await page.getByRole("button", { name: "Aplicar cambios" }).click();
  await page.goto("/#cargos");
  await expect(
    page.locator(".role-card h3", { hasText: nombre }),
  ).toBeVisible();
  expect(await page.evaluate(revisarContraste)).toEqual([]);
});

test("contrato v29: vacantes en vista dividida, ficha completa, teclado y celular", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/#vacantes");
  const items = page.locator(".item-vacante");
  const ficha = page.locator(".dividida-detalle .ficha");
  await expect(items.first()).toHaveAttribute("aria-current", "true");
  await expect(ficha.getByRole("heading", { level: 2 })).toHaveText(
    (await items.first().locator(".item-titulo").textContent())!,
  );
  // La descripción llega con su formato (subtítulos y viñetas), sin HTML del sitio.
  await expect(ficha.locator(".ficha-descripcion h4").first()).toBeVisible();
  await expect(ficha.locator(".ficha-descripcion li").first()).toBeVisible();
  await expect(ficha.getByText("Descripción del aviso")).toBeVisible();
  // ↓ elige la siguiente, la dirección la recuerda y sobrevive a recargar.
  await items.first().focus();
  await page.keyboard.press("ArrowDown");
  await expect(items.nth(1)).toHaveAttribute("aria-current", "true");
  await expect(items.nth(1)).toBeFocused();
  const segunda = (await items.nth(1).getAttribute("data-id"))!;
  await expect(page).toHaveURL(new RegExp("#vacantes/" + segunda + "$"));
  await page.reload();
  await expect(
    page.locator(`.item-vacante[data-id="${segunda}"]`),
  ).toHaveAttribute("aria-current", "true");
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  // Celular: primero la lista; al tocar, la ficha a pantalla completa con «Volver a la lista».
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(ficha).toBeHidden();
  await items.nth(2).click();
  await expect(ficha).toBeVisible();
  await expect(items.first()).toBeHidden();
  await page.getByRole("button", { name: "Volver a la lista" }).click();
  await expect(items.first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errores).toEqual([]);
});

test("contrato v30: bandera del WhatsApp, contacto precargado y guardado sin esperar", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  // El servidor tarda en guardar el WhatsApp: el formulario no debe esperarlo.
  let guardado = "";
  await page.route(/\/api\/contactos\/[^/]+$/, async (route) => {
    if (route.request().method() === "PUT") {
      await new Promise((listo) => setTimeout(listo, 2500));
      guardado = route.request().postDataJSON().telefono;
    }
    await route.continue();
  });
  await page.goto("/");
  await ir(page, "Clientes");
  // Otros recorridos importan o archivan clientes: se usa el primero que haya.
  const editar = page
    .locator(".client-card")
    .first()
    .getByRole("button", { name: /^Editar / });
  await editar.click();
  const dialog = page.getByRole("dialog");
  const consentimiento = dialog.getByLabel(
    "Aceptó recibir vacantes por WhatsApp",
  );
  if (!(await consentimiento.isChecked())) await consentimiento.check();
  // Contrato v35: el país del número se elige en la lista y se escribe solo el número.
  const telefono = dialog.getByLabel("Número", { exact: true });
  await dialog.getByLabel("País", { exact: true }).selectOption("ES");
  await telefono.fill("600 111 222");
  await dialog.getByLabel("País", { exact: true }).selectOption("CO");
  await telefono.fill("300 111 2233");
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(dialog).toHaveCount(0, { timeout: 1500 });
  // Al volver a abrirlo, el número ya está (sin esperar a que el servidor responda).
  await editar.click();
  await expect(dialog.getByLabel("Número", { exact: true })).toHaveValue(
    "300 111 2233",
    { timeout: 1000 },
  );
  await expect(dialog.getByLabel("País", { exact: true })).toHaveValue("CO");
  await expect.poll(() => guardado, { timeout: 5000 }).toBe("+57 300 111 2233");
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  expect(errores).toEqual([]);
});

test("contrato v31: mi número, mandarme todos a mi WhatsApp y lista de enviados", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.goto("/");
  await ir(page, "Mensajes");
  const mandar = page.getByRole("button", {
    name: "Mandarme todos a mi WhatsApp",
  });
  const numero = page.getByLabel("Mi número");
  // Sin número guardado no se puede mandar.
  if (!(await numero.inputValue())) await expect(mandar).toBeDisabled();
  await numero.fill("+57 311 222 3344");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Tu número quedó guardado.")).toBeVisible();
  await page.getByRole("button", { name: "Preparar mensajes" }).click();
  await mandar.click();
  const parte = page
    .getByRole("link", { name: "Abrir en mi WhatsApp" })
    .first();
  await expect(parte).toHaveAttribute(
    "href",
    /^https:\/\/wa\.me\/573112223344\?text=/,
  );
  // Lista de enviados: marcar uno sube la cuenta.
  const enviados = page.locator("fieldset.enviados");
  const total = await enviados.locator("input").count();
  const antes = await enviados.locator("input:checked").count();
  const libre = enviados.locator("input:not(:checked)").first();
  await libre.check();
  await expect(enviados.locator("legend")).toHaveText(
    `Enviados hoy: ${antes + 1} de ${total}`,
  );
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  expect(errores).toEqual([]);
});
