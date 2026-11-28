import { test, expect, type Page } from "@playwright/test";
import { revisarContraste } from "./contraste";

// Sección 5 (13 nov): sin menú lateral; cada sección se abre desde su tarjeta del resumen.
const accion: Record<string, string> = {
  // Sesión de prueba (17 nov): «Ver los N clientes», los 3 pasos del día y «Historial».
  Clientes: "Ver (los \\d+ clientes|el cliente)",
  "Cargos y metas": "Editar cargos y metas",
  Vacantes: "Ver vacantes",
  "Por confirmar": "Revisa las dudosas",
  Mensajes: "Envía los mensajes",
  Historial: "Ver historial",
};
const tarjeta = (page: Page, seccion: string) =>
  page
    .getByRole("button", {
      name: new RegExp(
        ["Por confirmar", "Mensajes"].includes(seccion)
          ? "^\\d?\\s*" + accion[seccion]
          : accion[seccion] + "$",
      ),
    })
    .first();
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
  // Contrato v49: un solo «Aplicar cambios», que solo aparece cuando hay algo sin aplicar; sin «Guardar borrador».
  await expect(
    page.getByRole("button", { name: "Guardar borrador" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Confirmar y aplicar" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Más información: Guardar y aplicar" }),
  ).toHaveCount(0);
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
  await expect(dialog.getByLabel("País", { exact: true })).toHaveValue(
    /Colombia \+57/,
  );
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
  await dialog.getByLabel("Años de experiencia del perfil 1").selectOption("4");
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
  // Contrato v49: con presencial, la ciudad es obligatoria (sin ella no llegan presenciales ni híbridas).
  const ciudad1 = dialog.getByLabel("Ciudades de la ubicación 1, perfil 1");
  await expect(ciudad1).toHaveAttribute("aria-invalid", "true");
  await ciudad1.fill("Monterrey");
  await ciudad1.press("Enter");
  await expect(ciudad1).not.toHaveAttribute("aria-invalid", "true");
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
  // Contrato v49: «Añadir cliente» guarda y aplica. Con 130 de metas y techo 120 se guarda pero no queda en uso:
  // el panel dice por qué y qué hacer, y la cabecera queda con «Aplicar cambios».
  await expect(page.locator(".aviso-no-aplica")).toContainText(
    /guardados, pero la búsqueda aún no los usa.*baja algunas metas o sube el cupo diario/,
  );
  await expect(page.locator(".flow-pill")).toHaveText("Cambios sin aplicar");
  await page.reload();
  await ir(page, "Clientes");
  await expect(
    page.getByRole("heading", { name: "Prueba operadora" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Aplicar cambios", exact: true }),
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
  // La operadora suma 10 a los 120 de los demás: con techo 120 no se puede aplicar; con 130, sí.
  await expect(page.getByText(/pasan el cupo diario/)).toBeVisible();
  // Lista grande del 16 nov: el techo se puede borrar del todo y se valida al salir del campo.
  const techo = page.getByLabel("Cupo diario", { exact: true });
  await techo.fill("");
  await expect(techo).toHaveValue("");
  await techo.fill("130");
  await techo.blur();
  await expect(page.getByText(/pasan el cupo diario/)).toHaveCount(0);
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
  // Contrato v49: «Añadir cargo» también aplica, con el techo de 130 que estaba sin aplicar.
  await expect(
    page.getByText("Cambios aplicados: la próxima búsqueda los usa", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.locator(".flow-pill")).toHaveText(
    "En uso desde la próxima búsqueda",
  );
  await expect(
    page.getByRole("button", { name: "Aplicar cambios", exact: true }),
  ).toHaveCount(0);
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
  // Contrato v43: 10 por defecto (2 por empresa); el operador elige cuántas.
  expect((texto.match(/https:\/\//g) || []).length).toBe(10);
  await dialog
    .getByRole("button", { name: "Cerrar", exact: true })
    .last()
    .click();
  await page.getByLabel("Cuántas").fill("3");
  await page
    .getByRole("button", { name: "Copiar WhatsApp", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Copiar el mensaje", exact: true })
    .click();
  const tres = await page.evaluate(() => navigator.clipboard.readText());
  expect((tres.match(/https:\/\//g) || []).length).toBe(3);
  expect(tres).toContain("Tengo 47 vacantes más");
  // Contrato v48: cada vacante lleva su número corto, el mismo del panel y del CSV.
  expect(tres).toMatch(/\(ID \d+\)\nhttps:\/\//);
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
  await ir(page, "Historial");
  // Sin avisos por correo: el operador no quiere servicios externos (13 nov).
  await expect(page.getByText("Avisos por correo")).toHaveCount(0);
  // 18 nov: una frase y un solo embudo del día, con «Qué hacer» en la etapa que más pierde; sin desbordar.
  const embudo = page.locator(".embudo-dia").first();
  await expect(embudo.locator(".embudo-frase")).toContainText(
    /de [\d.]+ vacantes encontradas llegaron [\d.]+ a tus clientes/,
  );
  // Contrato v31: etapas con nombres claros y qué hacer en la que más pierde.
  await expect(
    embudo.locator(".embudo-barras").getByText("Abiertas y vigentes hoy"),
  ).toBeVisible();
  await expect(embudo.getByText("Qué hacer:").first()).toBeVisible();
  for (const ancho of [1366, 390]) {
    await page.setViewportSize({ width: ancho, height: 900 });
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <= innerWidth &&
          [...document.querySelectorAll(".embudo-dia")].every(
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
  await ir(page, "Historial");
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
  await expect(page.locator(".tarjeta-resumen")).toHaveCount(4);
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
  await page.goto("/#historial");
  await expect(
    page.getByRole("heading", { level: 1, name: "Historial" }),
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
  await expect(page.locator(".tarjeta-resumen")).toHaveCount(4);
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
    page.getByText("Aplica la configuración para empezar"),
  ).toHaveCount(0);
  await page.unroute(/\/api\/resultados/);
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.locator(".item-vacante").first()).toBeVisible();
  // H6: «1 año», nunca «1 años».
  await expect(page.getByText("1 años exigidos")).toHaveCount(0);
  // H8: la pestaña dice en qué sección estás.
  await expect(page).toHaveTitle("Vacantes · Scraper");
  // H2 y H4: sin «noche»; primero el resultado, luego las reglas.
  await page.goto("/#historial");
  await expect(page.getByText(/Cada noche|búsqueda nocturna/)).toHaveCount(0);
  const orden = await page
    .locator("main h2")
    .evaluateAll((hs) => hs.map((h) => h.textContent || ""));
  expect(orden[0]).toContain("La última búsqueda");
  // El detalle de cada cargo se abre al tocarlo.
  await page.locator(".embudo-por-cargo summary").first().click();
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
  await dialog.getByLabel("Años de experiencia del perfil 1").selectOption("6");
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
  // Contrato v49: «Aplicar cambios» del formulario guarda y deja en uso.
  await expect(
    page.getByText("Cambios aplicados: la próxima búsqueda los usa", {
      exact: false,
    }),
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
  // PR 3 de la sesión de prueba: la zona dice la diferencia con donde vive; primero el país, luego la ciudad.
  await expect(
    dialog
      .getByText(/hora que donde vive|h (más|menos) que donde vive/)
      .first(),
  ).toBeVisible();
  const fila = dialog.locator(".ubicacion-fila").first();
  await expect(fila.locator("label").nth(0)).toHaveText(/^Países/);
  await expect(fila.locator("datalist option").first()).toBeAttached();
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
  // Contrato v49: «Aplicar cambios» del formulario guarda y deja en uso.
  await expect(
    page.getByText("Cambios aplicados: la próxima búsqueda los usa", {
      exact: false,
    }),
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
  // Contrato v49: lo aplicado queda en uso y la demostración la comparten las pruebas: se deja el perfil como
  // estaba (vive en Colombia) para que las siguientes lo encuentren igual.
  const sinFilas = {
    ...perfil,
    vive_en: "CO",
    ubicaciones: [{ paises: ["CO"], ciudades: [], modalidades: ["remoto"] }],
  };
  const r = await request.put("/api/config", {
    headers: { Origin: "http://127.0.0.1:8001" },
    data: {
      revision: cfg.revision,
      configuracion: {
        ...cfg.borrador,
        perfiles: cfg.borrador.perfiles.map((p: { id: string }) =>
          p.id === perfil.id ? sinFilas : p,
        ),
      },
    },
  });
  expect(r.ok()).toBe(true);
  const publicar = await request.post("/api/config/publicar", {
    headers: { Origin: "http://127.0.0.1:8001" },
    data: { revision: (await r.json()).revision },
  });
  expect(publicar.ok()).toBe(true);
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
    lista.getByRole("button", { name: /^Cliente de ejemplo 02\s*:/ }),
  ).toHaveAccessibleName(/,\s*\d+ de 17\s*,\s*\d+ por confirmar, bajo su meta/);
  // Los que van peor van primero; el que está completo, después.
  const nombres = await lista.getByRole("button").allTextContents();
  expect(
    nombres.findIndex((t) => t.startsWith("Cliente de ejemplo 02")),
  ).toBeLessThan(
    nombres.findIndex((t) => t.startsWith("Cliente de ejemplo 04")),
  );

  const nombre = "Cliente de ejemplo 02";
  const boton02 = lista.getByRole("button", {
    name: /^Cliente de ejemplo 02\s*:/,
  });
  await expect(boton02).toHaveAccessibleName(/, [1-9]\d* por confirmar/);
  const pendientesAntes = Number(
    await boton02.locator(".cliente-alerta").textContent(),
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
    "#historial",
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
test("contrato v48: tomar las vacantes de un día desde el detalle y copiarlas con su ID", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Un cliente con vacantes en los últimos días (otros recorridos cambian la lista de la demostración).
  const resumen = await (
    await page.request.get("/api/resumen-clientes")
  ).json();
  const cfg = await (await page.request.get("/api/config")).json();
  const conVacantes = new Set(
    resumen.dias.flatMap((d: { clientes: Record<string, number> }) =>
      Object.keys(d.clientes).filter((id) => d.clientes[id] > 0),
    ),
  );
  const cliente = cfg.borrador.clientes.find(
    (c: { id: string; activo: boolean }) => c.activo && conVacantes.has(c.id),
  );
  await page.goto("/");
  const lista = page.getByRole("list", { name: "Clientes y su avance" });
  await lista
    .getByRole("button", { name: new RegExp("^" + cliente.nombre + "\\s*:") })
    .click();
  const detalle = page.locator("dialog[open]");
  const tomar = detalle
    .getByRole("group", { name: /Tomar las vacantes de un día/ })
    .getByRole("button");
  await expect(tomar.first()).toBeVisible();
  const nombre = (await tomar.first().getAttribute("aria-label")) || "";
  expect(nombre).toMatch(/^Tomar las \d+ vacantes del /);
  await tomar.first().click();
  await expect(page).toHaveURL(/#vacantes/);
  const dia = page.getByLabel("Día de la búsqueda");
  await expect(dia).toHaveAttribute("type", "date");
  // El calendario queda en el día del botón (el primero es el más antiguo con vacantes).
  const esperado = resumen.dias.find(
    (d: { clientes: Record<string, number> }) => d.clientes[cliente.id] > 0,
  ).fecha;
  await expect(dia).toHaveValue(esperado);
  const copiar = page.getByRole("button", {
    name: "Copiar WhatsApp",
    exact: true,
  });
  await expect(copiar).toBeFocused();
  // El número corto también se ve en la lista de vacantes.
  await expect(page.getByText(/^ID \d+$/).first()).toBeVisible();
  await copiar.click();
  const dialogo = page.locator("dialog[open]");
  await expect(dialogo.getByLabel("Mensaje de WhatsApp")).toHaveValue(
    /\(ID \d+\)/,
  );
  // Otro día en el calendario: si no hubo búsqueda, lo dice.
  await dialogo
    .getByRole("button", { name: "Cerrar", exact: true })
    .last()
    .click();
  // (La demostración tiene una sola muestra: se simula un día sin búsqueda.)
  await page.route(/\/api\/resultados\?.*fecha=2020-01-01/, (route) =>
    route.fulfill({
      json: { ejecucion: null, clientes: [], vacantes: [], listas: 0 },
    }),
  );
  await dia.fill("2020-01-01");
  await expect(page.getByText("Ese día no hubo búsqueda.")).toBeVisible();
  await expect(copiar).toBeDisabled();
});

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

  // Quedan guardados de verdad: al recargar siguen ahí y se pueden aplicar.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Persona Uno" }),
  ).toBeVisible();
  await page.goto("/");
  const lista = page.getByRole("list", { name: "Clientes y su avance" });
  await expect(lista.getByRole("button")).toHaveCount(4);
  // El cliente actualizado sigue mostrando lo que recibió hoy.
  await expect(
    lista.getByRole("button", { name: /^Cliente de ejemplo 02\s*:/ }),
  ).toHaveAccessibleName(/,\s*[1-9]\d* de 10/);
  // Contrato v49: lo importado queda guardado sin aplicar; un clic en la cabecera lo deja en uso, sin diálogo.
  await expect(page.locator(".flow-pill")).toHaveText("Cambios sin aplicar");
  await page
    .getByRole("button", { name: "Aplicar cambios", exact: true })
    .click();
  await expect(page.locator(".flow-pill")).toHaveText(
    /En uso desde la próxima búsqueda/,
  );
  await expect(
    page.getByRole("button", { name: "Aplicar cambios", exact: true }),
  ).toHaveCount(0);

  // Eliminar definitivamente un cliente archivado.
  await page.goto("/#clientes");
  await page.getByRole("button", { name: /^Archivar Persona Tres/ }).click();
  await page
    .locator("dialog[open]")
    .getByRole("button", { name: /Archivar/ })
    .last()
    .click();
  await page
    .getByRole("button", { name: "Aplicar cambios", exact: true })
    .click();
  await expect(page.locator(".flow-pill")).toHaveText(
    /En uso desde la próxima búsqueda/,
  );
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
  await dialog.getByLabel(/Es un grupo de WhatsApp/).check();
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(
    page.locator(".client-card h3", { hasText: "Cliente de ejemplo 02" }),
  ).toContainText("Comunidad");
  await expect(
    page.getByText("Cambios aplicados: la próxima búsqueda los usa", {
      exact: false,
    }),
  ).toBeVisible();
  const cfg = await (await request.get("/api/config")).json();
  const hoy = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Bogota",
  }).format(new Date());
  expect(cfg.publicada.vigente_desde).toBe(hoy);
  await page.getByRole("button", { name: "Volver al resumen" }).click();
  await expect(
    page.getByRole("button", {
      name: /Cliente de ejemplo 02\s*\(\s*Comunidad\s*\)/,
    }),
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
    "#historial",
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
  await expect(page.locator(".flow-pill")).toHaveText(
    /^(Cambios sin aplicar|En uso desde la próxima búsqueda)$/,
  );
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

  // Lista grande (17 nov): deshacer un cambio deja el panel «sin cambios» (no pide aplicar otra vez).
  await page.goto("/#cargos");
  const aplicarCabecera = page.getByRole("button", {
    name: "Aplicar cambios",
    exact: true,
  });
  if (await aplicarCabecera.count()) await aplicarCabecera.click(); // lo que dejaron pendiente otras pruebas
  await expect(aplicarCabecera).toHaveCount(0);
  const techoCampo = page.locator("#techo-diario");
  const original = await techoCampo.inputValue();
  await techoCampo.fill(String(Number(original) + 5));
  await techoCampo.blur();
  await expect(aplicarCabecera).toBeVisible();
  await expect(page.locator(".flow-pill")).toHaveText("Cambios sin aplicar");
  await techoCampo.fill(original);
  await techoCampo.blur();
  await expect(aplicarCabecera).toHaveCount(0);
  await expect(page.locator(".flow-pill")).toHaveText(
    "En uso desde la próxima búsqueda",
  );
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
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Aplicar cambios" })
    .click();
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
  // 18 nov: el país se escribe («esp», «+57») y aparece con su bandera y su código.
  await dialog.getByLabel("País", { exact: true }).fill("españa");
  await telefono.fill("600 111 222");
  await dialog.getByLabel("País", { exact: true }).fill("+57");
  await telefono.fill("300 111 2233");
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(dialog).toHaveCount(0, { timeout: 1500 });
  // Al volver a abrirlo, el número ya está (sin esperar a que el servidor responda).
  await editar.click();
  await expect(dialog.getByLabel("Número", { exact: true })).toHaveValue(
    "300 111 2233",
    { timeout: 1000 },
  );
  await expect(dialog.getByLabel("País", { exact: true })).toHaveValue(
    /Colombia \+57/,
  );
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
  const numero = page.getByLabel("Mi número");
  // Sin número guardado todavía no es un enlace (dice por qué al tocarlo).
  if (!(await numero.inputValue()))
    await expect(
      page.getByRole("button", { name: "Mandarme todos a mi WhatsApp" }),
    ).toHaveAttribute("aria-disabled", "true");
  await numero.fill("+57 311 222 3344");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Tu número quedó guardado.")).toBeVisible();
  await page.getByRole("button", { name: "Preparar mensajes" }).click();
  // Contrato v46: un solo enlace, listo sin pasos intermedios, con un enlace corto por cliente.
  const mandar = page.getByRole("link", {
    name: "Mandarme todos a mi WhatsApp",
  });
  await expect(mandar).toHaveAttribute(
    "href",
    /^https:\/\/wa\.me\/573112223344\?text=.*%2Fw%2F/,
  );
  await expect(page.getByText(/Un solo mensaje con \d+ cliente/)).toBeVisible();
  const href = (await mandar.getAttribute("href")) || "";
  const corto = decodeURIComponent(href.split("text=")[1]).match(
    /http:\/\/[^\s]+\/w\/[^\s]+/,
  )![0];
  const abierto = await page.request.get(corto, { maxRedirects: 0 });
  expect(abierto.status()).toBe(302);
  expect(abierto.headers()["location"]).toMatch(/^https:\/\/wa\.me\//);
  // «Copiar mensaje» deja en el portapapeles el mismo texto, con sus saltos de línea.
  await page
    .getByRole("button", { name: "Copiar mensaje", exact: true })
    .click();
  const copiado = await page.evaluate(() => navigator.clipboard.readText());
  expect(copiado).toBe(decodeURIComponent(href.split("text=")[1]));
  expect(copiado).toContain("\n\n");
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

test("sesión de prueba: nombres afines con un clic y explicación del 0", async ({
  page,
}) => {
  await page.goto("/");
  await ir(page, "Cargos y metas");
  await page.getByRole("button", { name: "Añadir cargo", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Cargo", { exact: true }).fill("UX Designer");
  await dialog
    .getByRole("button", { name: "Buscar denominaciones afines" })
    .click();
  const sugerido = dialog.locator(".chip-sugerido").first();
  await expect(sugerido).toBeVisible();
  const nombre = ((await sugerido.textContent()) || "").trim();
  await sugerido.click();
  await expect(
    dialog.getByRole("button", { name: "Quitar " + nombre }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
});

test("18 nov: «Buscar ahora» lanza la búsqueda desde el Resumen y se bloquea mientras corre", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.goto("/");
  await page.getByRole("heading", { level: 1, name: "Resumen" }).waitFor();
  await page.getByRole("button", { name: "Buscar ahora" }).click();
  const dialog = page.getByRole("dialog");
  // v45: un solo botón que decide. En la demo la búsqueda de hoy ya corrió y hay perfiles que no llegan a su meta
  // (cuáles depende de lo que aplicaron las pruebas anteriores: desde v49 lo aplicado queda en uso en la demo).
  await expect(dialog).toContainText("no llegan a su meta");
  await expect(
    dialog.getByRole("list", { name: "Quiénes no llegan a su meta" }),
  ).toContainText(/ · .+\d+ de \d+/);
  await expect(dialog).toContainText("Demostración");
  await dialog.getByRole("button", { name: "Buscar ahora" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Búsqueda pedida")).toBeVisible();
  const enCurso = page.getByRole("button", { name: /^(En cola|Buscando)/ });
  // Bloqueado pero enfocable (aria-disabled): el foco vuelve a él al cerrar el diálogo y explica por qué.
  await expect(enCurso).toHaveAttribute("aria-disabled", "true");
  await expect(enCurso).toBeFocused();
  await enCurso.click({ force: true }); // Playwright no hace clic solo en un botón aria-disabled
  await expect(page.getByText("Ya hay una búsqueda")).toBeVisible();
  // Otras pestañas no lo muestran: solo el Resumen.
  await ir(page, "Cargos y metas");
  await expect(
    page.getByRole("button", { name: /Buscar ahora|Buscando|En cola/ }),
  ).toHaveCount(0);
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  expect(errores).toEqual([]);
});

test("contrato v50: los nombres en español de «AI Product Manager» se usan solos y se pueden dejar de usar", async ({
  page,
}) => {
  await page.goto("/");
  await ir(page, "Cargos y metas");
  await page.getByRole("button", { name: "Añadir cargo", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Cargo", { exact: true }).fill("AI Product Manager");
  await dialog
    .getByRole("button", { name: "Buscar denominaciones afines" })
    .click();
  // Antes (v44) había que añadirlos uno a uno; ahora se buscan y se reconocen sin añadirlos.
  const solos = dialog.getByRole("group", {
    name: "Nombres en español que se usan solos",
  });
  const hermano = solos.getByRole("button", {
    name: "No usar Gerente de Producto de IA",
  });
  await expect(hermano).toBeVisible();
  await expect(
    dialog.getByRole("group", { name: "Nombres en español", exact: true }),
  ).toContainText("ya se usan solos");
  // El oficio más amplio sigue siendo una sugerencia que se añade a mano.
  const amplios = dialog.getByRole("group", { name: "Nombres más amplios" });
  await expect(
    amplios.getByRole("button", { name: "Añadir Gerente de Producto" }),
  ).toBeVisible();
  // «No usar» lo pasa a los términos excluidos y deja de mostrarse como usado.
  await hermano.click();
  await expect(hermano).toHaveCount(0);
  await expect(page.getByText("ya no se usa")).toBeVisible();
  await dialog.getByRole("button", { name: /Opciones avanzadas/ }).click();
  await expect(
    dialog.getByRole("button", { name: "Quitar Gerente de Producto de IA" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
});

test("18 nov: al editar un cargo los grupos en español aparecen solos y el contenido va en el color fuerte", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await ir(page, "Cargos y metas");
  await page.getByRole("button", { name: "Editar QA", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("group", { name: "Nombres en español", exact: true }),
  ).toBeVisible();
  // Lo escrito y las fichas de nombres en blanco (modo oscuro); el texto de ejemplo, gris.
  const ficha = dialog.locator(".term").first();
  await expect(ficha).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(dialog.getByLabel("Cargo", { exact: true })).toHaveCSS(
    "color",
    "rgb(255, 255, 255)",
  );
  // Los tres grupos se ven siempre; si uno queda vacío dice por qué (QA es el oficio general).
  const amplio = dialog.getByRole("group", { name: "Nombres más amplios" });
  await expect(amplio).toContainText(/no hay uno más amplio|Ya tiene/);
  // Van antes de «Nombres del cargo», a la vista al abrir.
  const yGrupo = (await amplio.boundingBox())!.y;
  const yNombres = (await dialog
    .getByText("Nombres del cargo", { exact: true })
    .boundingBox())!.y;
  expect(yGrupo).toBeLessThan(yNombres);
  await page.keyboard.press("Escape");
});

test("18 nov: Cupo diario en una línea y «Ver historial» al pie de su tarjeta", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const cabeza = page.locator(".cupos-cabeza");
  await expect(cabeza).toContainText(/Cupo diario\s*· \d+ a clientes/);
  const alto = (await cabeza.boundingBox())!.height;
  expect(alto).toBeLessThan(30); // una sola línea
  const pie = async (texto: string) => {
    const enlace = page.locator(".tarjeta-accion", { hasText: texto });
    const tarjeta = enlace.locator("xpath=ancestor::button[1]");
    const e = (await enlace.boundingBox())!;
    const t = (await tarjeta.boundingBox())!;
    return t.y + t.height - (e.y + e.height);
  };
  expect(await pie("Ver historial")).toBeLessThan(24);
  expect(
    Math.abs((await pie("Ver historial")) - (await pie("Ver vacantes"))),
  ).toBeLessThan(6);
});

// ── Contrato v49 (26 nov, pedido de Oscar): un solo «Aplicar cambios», «Buscar ahora» por cliente y ciudad ─────────
async function sinPendientes(page: Page) {
  const boton = page.getByRole("button", {
    name: "Aplicar cambios",
    exact: true,
  });
  if (await boton.count()) await boton.click();
  await expect(boton).toHaveCount(0);
}

test("contrato v49: «Aplicar cambios» del formulario de cliente deja la configuración en uso", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Clientes");
  await sinPendientes(page);
  await expect(page.locator(".flow-pill")).toHaveText(
    "En uso desde la próxima búsqueda",
  );
  await page
    .getByRole("button", { name: /^Editar / })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Años de experiencia del perfil 1").selectOption("5");
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(dialog).toBeHidden();
  await expect(
    page.getByText("Cambios aplicados: la próxima búsqueda los usa", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.locator(".flow-pill")).toHaveText(
    "En uso desde la próxima búsqueda",
  );
  await expect(
    page.getByRole("button", { name: "Aplicar cambios", exact: true }),
  ).toHaveCount(0);
  const cfg = await (await request.get("/api/config")).json();
  expect(cfg.publicada.revision).toBe(cfg.revision);
  // Un cambio en línea (el cupo diario) deja el botón de la cabecera pendiente hasta aplicarlo.
  await ir(page, "Cargos y metas");
  const techo = page.locator("#techo-diario");
  const original = await techo.inputValue();
  await techo.fill(String(Number(original) + 1));
  await techo.blur();
  await expect(page.locator(".flow-pill")).toHaveText("Cambios sin aplicar");
  await page
    .getByRole("button", { name: "Aplicar cambios", exact: true })
    .click();
  await expect(page.locator(".flow-pill")).toHaveText(
    "En uso desde la próxima búsqueda",
  );
  expect(await page.evaluate(revisarContraste)).toEqual([]);
});

test("contrato v49: «Buscar ahora» desde el detalle de un cliente busca solo para él", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.goto("/");
  await page.getByRole("heading", { level: 1, name: "Resumen" }).waitFor();
  await sinPendientes(page);
  await page
    .getByRole("list", { name: "Clientes y su avance" })
    .getByRole("button", { name: /^Cliente de ejemplo 02/ })
    .click();
  const detalle = page.getByRole("dialog");
  const boton = detalle.getByRole("button", {
    name: /^Buscar ahora para Cliente de ejemplo 02$/,
  });
  // Si otra prueba dejó una búsqueda de la demostración corriendo (20 s), el botón espera a que termine.
  await expect(boton).toBeVisible({ timeout: 40_000 });
  await boton.click();
  const pedir = page
    .locator("dialog[open]")
    .filter({ hasText: "Busca solo lo que le falta hoy a este cliente" })
    .last(); // va dentro del detalle del cliente
  await expect(pedir).toContainText("Buscar ahora para Cliente de ejemplo 02");
  await expect(pedir).toContainText("no llega a su meta");
  await expect(
    pedir.getByRole("list", { name: "Quiénes no llegan a su meta" }),
  ).toContainText(/\d+ de \d+/);
  await expect(pedir).toContainText("Demostración");
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  await pedir.getByRole("button", { name: "Buscar ahora" }).click();
  await expect(
    page.getByText("Búsqueda pedida para Cliente de ejemplo 02"),
  ).toBeVisible();
  await expect(
    detalle.getByRole("button", { name: /^(En cola|Buscando)/ }),
  ).toHaveAttribute("aria-disabled", "true");
  expect(errores).toEqual([]);
});

test("contrato v49: una fila presencial o híbrida sin ciudad no se aplica y el panel lo avisa", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Nombre o referencia del cliente").fill("Sin ciudad");
  await dialog.getByLabel("Híbrido en la ubicación 1 del perfil 1").check();
  const ciudades = dialog.getByLabel("Ciudades de la ubicación 1, perfil 1");
  await expect(ciudades).toHaveAttribute("aria-invalid", "true");
  await expect(ciudades).toHaveAccessibleDescription(
    "Escribe la ciudad: sin ciudad no llegan presenciales ni híbridas.",
  );
  await dialog
    .getByRole("button", { name: "Añadir cliente", exact: true })
    .click();
  await expect(dialog.locator(".form-error[role=alert]")).toContainText(
    "Falta la ciudad",
  );
  await expect(dialog).toBeVisible(); // no se aplicó
  expect(await page.evaluate(revisarContraste)).toEqual([]);
  await ciudades.fill("Medellín");
  await ciudades.press("Enter");
  await expect(ciudades).not.toHaveAttribute("aria-invalid", "true");
  await dialog.getByRole("button", { name: "Cancelar" }).click();

  // Un perfil que ya existía con presencial sin ciudad: aviso en su tarjeta y en su detalle (sin bloquear).
  const estado = await (await request.get("/api/config")).json();
  const cfg = estado.borrador;
  const cliente = cfg.clientes.find((c: { activo: boolean }) => c.activo);
  const perfil = cfg.perfiles.find(
    (p: { cliente_id: string; activo: boolean }) =>
      p.cliente_id === cliente.id && p.activo,
  );
  perfil.ubicaciones = [
    { paises: [perfil.vive_en], ciudades: [], modalidades: ["presencial"] },
  ];
  const r = await request.put("/api/config", {
    headers: { Origin: "http://127.0.0.1:8001" },
    data: { revision: estado.revision, configuracion: cfg },
  });
  expect(r.ok()).toBe(true);
  await page.reload();
  await ir(page, "Clientes");
  await expect(
    page.locator(".client-card", { hasText: cliente.nombre }),
  ).toContainText("Falta la ciudad");
  await page.goto("/");
  await page
    .getByRole("list", { name: "Clientes y su avance" })
    .getByRole("button", { name: new RegExp("^" + cliente.nombre) })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Falta la ciudad");
  expect(await page.evaluate(revisarContraste)).toEqual([]);
});

// 8.1: un perfil en un país sin fuente local avisa al guardar y aparece en «Huecos por país» con su pedido.
test("huecos por país: aviso al aplicar, tabla y copiar pedido de fuente nueva", async ({
  page,
  request,
}) => {
  const cab = { Origin: "http://127.0.0.1:8001" };
  const estado = await (await request.get("/api/config")).json();
  const cfg = structuredClone(estado.borrador);
  // Otras pruebas pueden dejar perfiles a medio editar: aquí todos quedan en remoto, y el primero vive en Ghana.
  cfg.perfiles = cfg.perfiles.map((p: Record<string, unknown>) => ({
    ...p,
    ubicaciones: [],
    modalidades: ["remoto"],
    ciudades: [],
  }));
  cfg.perfiles[0].vive_en = "GH";
  const r = await request.put("/api/config", {
    headers: cab,
    data: { revision: estado.revision, configuracion: cfg },
  });
  expect(r.ok()).toBe(true);
  const guardado = await r.json();
  expect(guardado.avisos_cobertura).toEqual([
    "Ghana: sin fuente local; riesgo de quedar bajo 10.",
  ]);
  const publicar = await request.post("/api/config/publicar", {
    headers: cab,
    data: { revision: guardado.revision },
  });
  expect(publicar.ok()).toBe(true);
  await page.goto("/#historial");
  const tabla = page.locator(".huecos-pais");
  await expect(
    tabla.getByRole("heading", { name: /Huecos por país/ }),
  ).toBeVisible();
  const fila = tabla.getByRole("row", { name: /Ghana/ });
  await expect(fila).toContainText("Riesgo");
  await expect(fila).toContainText(
    "LinkedIn, Portales de empresas, Get on Board (remotas)",
  );
  await expect(tabla.getByRole("row", { name: /Colombia/ })).toContainText(
    "Cubierto",
  );
  await fila
    .getByRole("button", { name: "Copiar pedido de fuente nueva para Ghana" })
    .click();
  await expect(tabla.getByText("Pedido de Ghana copiado")).toBeVisible();
  const texto = await page.evaluate(() => navigator.clipboard.readText());
  expect(texto).toMatch(/^Usa la skill nueva-fuente para Ghana: idioma\(s\) /);
  expect(texto).toContain("Es para hoy: deja el PR listo para revisar.");
  expect(texto).not.toMatch(/Cliente de ejemplo|\d/);
  // El aviso también sale en el mensaje de «Aplicar cambios» del panel (no bloquea el guardado).
  await page.route("**/api/config", async (route) => {
    if (route.request().method() !== "PUT") return route.fallback();
    const resp = await route.fetch();
    const json = await resp.json();
    await route.fulfill({
      response: resp,
      json: {
        ...json,
        avisos_cobertura: [
          "Kenia: sin fuente local; riesgo de quedar bajo 10.",
        ],
      },
    });
  });
  await page.goto("/");
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Editar Cliente de ejemplo 02", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const grupo = dialog.getByLabel(/Es un grupo de WhatsApp/);
  await grupo.setChecked(!(await grupo.isChecked())); // otra prueba pudo dejarla marcada
  await dialog.getByRole("button", { name: "Aplicar cambios" }).click();
  await expect(
    page.getByText(/Aviso de cobertura: Kenia: sin fuente local/),
  ).toBeVisible();
});
