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
  // Vista previa: estima con el catálogo y permite admitir datos no informados.
  await expect(dialog.getByText(/cumplen? este perfil/)).toBeVisible();
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
  expect(texto).toContain("Hola, el día de hoy");
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
