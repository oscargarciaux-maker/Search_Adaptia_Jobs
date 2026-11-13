import { test, expect } from "@playwright/test";

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
    page.getByRole("heading", { name: "Cada búsqueda, con propósito." }),
  ).toBeVisible();
  await expect(page.getByText("Mi espacio de trabajo")).toHaveCount(0);
  await expect(page.getByText("Menos ruido.")).toHaveCount(0);
  await expect(
    page.getByText(/guarda tus cambios y los aplica desde la búsqueda/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clientes", exact: true }).click();
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Nombre o referencia del cliente")
    .fill("Prueba operadora");
  await dialog
    .getByRole("button", { name: "Añadir perfil de búsqueda" })
    .click();
  await dialog.getByLabel("Cargo del perfil 1").selectOption({ label: "QA" });
  await dialog.getByLabel("Antigüedad del perfil 1").selectOption("7");
  await dialog.getByLabel("Experiencia máxima del perfil 1").fill("4");
  // Contrato v8: país de residencia y varias modalidades, sin las 21 casillas.
  await dialog
    .getByLabel("País de residencia del perfil 1")
    .selectOption({ label: "México" });
  await expect(
    dialog.getByText(/Remoto incluye vacantes de LATAM/),
  ).toBeVisible();
  await expect(dialog.getByText("Seleccionar LATAM y España")).toHaveCount(0);
  await dialog.getByLabel("Presencial en el perfil 1").check();
  await expect(dialog.getByText("También se mudaría a…")).toBeVisible();
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
  await page
    .getByRole("button", { name: "Guardar borrador", exact: true })
    .click();
  await expect(
    page.getByText("Borrador guardado.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Clientes", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Prueba operadora" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Archivar Prueba operadora", exact: true })
    .click();
  await dialog.getByRole("button", { name: "Archivar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Prueba operadora" }),
  ).toHaveCount(0);
  await page.getByText("Clientes archivados (1)").click();
  await page.getByRole("button", { name: "Reactivar", exact: true }).click();
  await page
    .getByRole("button", { name: "Cargos y cupos", exact: true })
    .click();
  await page.getByLabel("Vacantes de QA", { exact: true }).fill("29");
  await expect(
    page.getByRole("button", { name: "Programar para mañana", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Vacantes de QA", { exact: true }).fill("30");
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
  ).toBe(120);
  await page.getByRole("button", { name: "Vacantes", exact: true }).click();
  await expect(page.locator(".vacancy")).toHaveCount(50);
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
  await page.getByRole("button", { name: "Mensajes", exact: true }).click();
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
  await page.getByRole("button", { name: "Actividad", exact: true }).click();
  // Sin avisos por correo: el operador no quiere servicios externos (13 nov).
  await expect(page.getByText("Avisos por correo")).toHaveCount(0);
  await page.getByText("Dónde se pierden las vacantes de cada cargo").click();
  await expect(
    page.getByRole("columnheader", { name: "Enlace comprobado" }),
  ).toBeVisible();
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
    page.getByRole("heading", { name: "Cada búsqueda, con propósito." }),
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
  await page.getByRole("button", { name: "Abrir menú" }).click();
  await page.getByRole("button", { name: "Clientes", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Personas, no búsquedas genéricas." }),
  ).toBeVisible();
});

test("bandeja Por confirmar: un clic confirma, atajo 4 aparta y el contador baja", async ({
  page,
}) => {
  const errores: string[] = [];
  page.on("pageerror", (e) => errores.push(e.message));
  await page.goto("/");
  const menu = page.getByRole("button", { name: "Por confirmar", exact: true });
  await expect(menu).toContainText("3");
  await menu.click();
  await expect(
    page.getByRole("heading", {
      name: "Unos segundos para no perder vacantes.",
    }),
  ).toBeVisible();
  await expect(page.locator(".revision")).toHaveCount(3);
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
  await expect(page.locator(".revision")).toHaveCount(2);
  await expect(menu).toContainText("2");
  const otra = page.locator(".revision").first();
  await otra.focus();
  await page.keyboard.press("4");
  await expect(page.getByText("Apartada por ahora.")).toBeVisible();
  await expect(page.locator(".revision")).toHaveCount(1);
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
  expect(errores).toEqual([]);
});

test("revisión masiva por CSV y reglas aprendidas sin IA", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Por confirmar", exact: true })
    .click();
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
  await page.getByRole("button", { name: "Actividad", exact: true }).click();
  const regla = page.locator(".reglas-lista li", { hasText: "«granada»" });
  await expect(regla).toContainText("España");
  await regla.getByRole("button", { name: "Desactivar" }).click();
  await expect(page.getByText("Regla desactivada.")).toBeVisible();
  await expect(regla.getByRole("button", { name: "Activar" })).toBeVisible();
  // Descarga de la base desde Vacantes, con el conteo a la vista.
  await page.getByRole("button", { name: "Vacantes", exact: true }).click();
  await page.getByRole("button", { name: "Descargar base (CSV)" }).click();
  await expect(page.getByText(/Base descargada: 1 vacantes/)).toBeVisible();
});
