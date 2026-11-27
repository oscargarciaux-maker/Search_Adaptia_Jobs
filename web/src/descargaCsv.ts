// Descarga del CSV: general o de un cliente, del día elegido o de toda la base.
import { useState } from "react";
import type { Cliente } from "./types";
import { hoyBogota } from "./comunes";

// Nombre de archivo sin tildes ni espacios: el CSV solo queda en el equipo del operador.
function slug(texto: string) {
  return (
    texto
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "cliente"
  );
}

export function useDescargaCsv(
  clientes: Cliente[],
  notify: (s: string, error?: boolean) => void,
) {
  const [descargandoBase, setDescargandoBase] = useState(false);
  // Reunión del 14 nov: CSV general o de un cliente, del día elegido o de toda la base, con el formato del contrato.
  const [csvFecha, setCsvFecha] = useState(hoyBogota());
  const [csvTodo, setCsvTodo] = useState(false);
  const [csvCliente, setCsvCliente] = useState("");
  async function descargarBase(soloCliente?: string) {
    // Desde el detalle de un cliente (paso 8): las de hoy de ese cliente.
    const cliente = soloCliente ?? csvCliente,
      todo = soloCliente ? false : csvTodo,
      dia = soloCliente ? hoyBogota() : csvFecha;
    setDescargandoBase(true);
    try {
      const q = new URLSearchParams();
      if (todo) q.set("todo", "true");
      else q.set("fecha", dia);
      if (cliente) q.set("cliente", cliente);
      const r = await fetch("/api/base.csv?" + q.toString(), {
        credentials: "same-origin",
      });
      if (!r.ok)
        throw new Error("No se pudo descargar el CSV. Inténtalo de nuevo.");
      const incluidas = r.headers.get("X-Incluidas") || "?";
      const omitidas = Number(r.headers.get("X-Omitidas-Sin-Confirmar") || 0);
      const sinFila = Number(r.headers.get("X-Sin-Fila") || 0);
      const nombreCliente = clientes.find((c) => c.id === cliente)?.nombre;
      const url = URL.createObjectURL(await r.blob());
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download =
        "vacantes-" +
        (todo ? "base" : dia) +
        "-" +
        (nombreCliente ? slug(nombreCliente) : "todas") +
        ".csv";
      enlace.click();
      URL.revokeObjectURL(url);
      const notas = [
        omitidas ? `${omitidas} sin confirmar quedaron fuera` : "",
        sinFila ? `${sinFila} sin ficha en la base (posts)` : "",
      ].filter(Boolean);
      notify(
        `CSV descargado: ${incluidas} vacantes${notas.length ? " (" + notas.join("; ") + ")" : ""}.`,
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setDescargandoBase(false);
    }
  }
  return {
    descargandoBase,
    csvFecha,
    setCsvFecha,
    csvTodo,
    setCsvTodo,
    csvCliente,
    setCsvCliente,
    descargarBase,
  };
}
