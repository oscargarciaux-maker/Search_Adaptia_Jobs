// Los WhatsApp de los clientes (dividido de main.tsx).
import { useState } from "react";
import { api } from "./api";
import type { Contacto } from "./types";

export function useContactos(notify: (s: string, error?: boolean) => void) {
  // Sesión de prueba (17 nov): quién inició sesión, visible arriba.
  // Contrato v30: los WhatsApp se cargan con el panel para que el formulario del cliente abra sin esperar.
  const [contactos, setContactos] = useState<Record<string, Contacto>>({});
  function cargarContactos() {
    api<Record<string, Contacto>>("/contactos")
      .then(setContactos)
      .catch(() => undefined);
  }
  // Se guarda sin hacer esperar al formulario: se ve al momento y, si falla, se avisa y se vuelve a leer.
  function guardarContacto(id: string, ct: Contacto, tenia: boolean) {
    const borrar = !ct.telefono.trim();
    setContactos((actuales) => {
      const copia = { ...actuales };
      if (borrar) delete copia[id];
      else copia[id] = ct;
      return copia;
    });
    if (borrar && !tenia) return;
    api(
      "/contactos/" + id,
      borrar
        ? { method: "DELETE" }
        : { method: "PUT", body: JSON.stringify(ct) },
    ).catch((e) => {
      notify("No se guardó el WhatsApp: " + (e as Error).message, true);
      cargarContactos();
    });
  }
  return {
    contactos,
    cargarContactos,
    guardarContacto,
  };
}
