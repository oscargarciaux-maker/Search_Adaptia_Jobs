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
  await expect(dialog.getByText("PERFIL 1")).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Añadir otro perfil" }),
  ).toBeVisible();
  // WhatsApp: el número aparece solo al marcar la casilla.
  await expect(dialog.getByLabel("Número con código de país")).toHaveCount(0);
  await dialog.getByLabel("Aceptó recibir vacantes por WhatsApp").check();
  await expect(dialog.getByLabel("Número con código de país")).toBeVisible();
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
  await expect(
    dialog.getByText("Busca vacantes que pidan de 1 a 7 años."),
  ).toBeVisible();
  // Contrato v8: país de residencia y varias modalidades, sin las 21 casillas.
  await dialog
    .getByLabel("País de residencia del perfil 1")
    .selectOption({ label: "México" });
  await expect(dialog.getByText("Seleccionar LATAM y España")).toHaveCount(0);
  await dialog.getByLabel("Presencial en el perfil 1").check();
  // La explicación de las modalidades está en su ayuda, no a la vista.
  await expect(dialog.getByText(/solo con oficina en su país/)).toBeHidden();
  await dialog
    .getByRole("button", { name: "Más información: modalidades" })
    .hover();
  await expect(dialog.getByText(/solo con oficina en su país/)).toBeVisible();
  await expect(dialog.getByText("También se mudaría a…")).toBeVisible();
  // Países a los que se mudaría: botón claro y «Seleccionar todos / Quitar todos».
  await dialog.getByRole("button", { name: "Mostrar países" }).click();
  await dialog.getByRole("button", { name: "Seleccionar todos" }).click();
  const paisesMudanza = dialog.locator(".country-grid input");
  expect(await paisesMudanza.count()).toBeGreaterThan(10);
  await expect(dialog.locator(".country-grid input:not(:checked)")).toHaveCount(
    0,
  );
  await dialog.getByRole("button", { name: "Quitar todos" }).click();
  await expect(dialog.locator(".country-grid input:checked")).toHaveCount(0);
  // Estimación en vivo: en demostración usa avisos ficticios y no sale a internet.
  await expect(dialog.getByText(/No gasta Apify/)).toBeVisible();
  await dialog
    .getByRole("button", { name: "Estimar con búsqueda en vivo" })
    .click();
  await expect(
    dialog.getByText(/encontradas? ahora en las fuentes cumplen?/),
  ).toBeVisible();
  await expect(dialog.getByText(/Es una muestra/)).toBeVisible();
  // Vista previa: estima con el catálogo y permite admitir datos no informados.
  // La estimación en vivo también dice «cumple(n) este perfil»: buscar la frase propia de la vista previa.
  await expect(
    dialog.getByText(/guardadas? aún no entregadas? cumplen? este perfil/),
  ).toBeVisible();
  const aplicar = dialog.getByRole("button", { name: "Aplicar", exact: true });
  if (await aplicar.count()) {
    await aplicar.first().click();
    await expect(
      dialog.getByLabel("Admitir experiencia no informada"),
    ).toBeChecked();
  }
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
  await page.getByLabel("Techo del día", { exact: true }).fill("130");
  await expect(page.getByText(/pasan el techo/)).toHaveCount(0);
  await expect(page.getByText("Meta del día:").first()).toBeVisible();
  await expect(page.getByText(/guardadas sin entregar/).first()).toBeVisible();
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
  await expect(page.locator(".vacancy")).toHaveCount(50);
  // Sección 9: al menos 3 vacantes por fila a 1366 px; «Recargar lista» y las ayudas explican qué hace cada cosa.
  await page.setViewportSize({ width: 1366, height: 900 });
  const arriba = await page
    .locator(".vacancy")
    .evaluateAll((els) =>
      els.slice(0, 3).map((e) => Math.round(e.getBoundingClientRect().top)),
    );
  expect(new Set(arriba).size).toBe(1);
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
  await expect(embudo.getByText("Enlace comprobado")).toBeVisible();
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
  await expect(page.locator(".revision")).toHaveCount(4);
  const primera = page.locator(".revision").first();
  await expect(primera.locator(".revision-pista")).toBeVisible();
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
  await expect(page.locator(".revision")).toHaveCount(3);
  const otra = page.locator(".revision").first();
  await otra.focus();
  await page.keyboard.press("4");
  await expect(page.getByText("Apartada por ahora.")).toBeVisible();
  await expect(page.locator(".revision")).toHaveCount(2);
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
  const fondo = await page
    .locator(".resumen-derecha")
    .evaluate((e) => e.getBoundingClientRect().bottom);
  expect(fondo).toBeLessThanOrEqual(768);
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
  await expect(page.locator(".vacancy").first()).toBeVisible();
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
  await expect(
    dialog.getByText(/de 2 a 10 años\. No recibe vacantes junior/),
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

test("contrato v23: residencia en el mundo, permiso de trabajo, horario y ciudades", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ir(page, "Clientes");
  await page
    .getByRole("button", { name: "Editar Cliente de ejemplo 01", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("País de residencia del perfil 1")
    .selectOption({ label: "Alemania" });
  await dialog.getByLabel("Presencial en el perfil 1").check();
  const ciudades = dialog.getByLabel(
    "Ciudades donde trabajaría (la suya y a las que se mudaría), perfil 1",
  );
  await ciudades.fill("Berlín");
  await ciudades.press("Enter");
  await dialog
    .getByRole("button", { name: "Permiso de trabajo y horario (opcional)" })
    .click();
  const permiso = dialog.getByLabel("Puede trabajar legalmente en… (perfil 1)");
  await permiso.fill("Estados Unidos");
  await permiso.press("Enter");
  await expect(
    dialog.getByRole("button", { name: "Quitar Estados Unidos" }),
  ).toBeVisible();
  await dialog.getByLabel("Horario EE. UU. Este en el perfil 1").check();
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
  expect(perfil.acepta_horario).toEqual(["us_este"]);
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
  await page.route("**/api/revisiones", async (route) => {
    const r = await route.fetch();
    const j = await r.json();
    if (!decidida) {
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
  await expect(page).toHaveURL(/#vacantes$/);
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
  expect(columnas).toBe(2);
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
  await expect(page.locator(".flow-pill")).toHaveText(/Programado desde el/);

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
