// Estimación con el catálogo ya guardado mientras se edita (vista previa), compartida por clientes y cargos.
import { useEffect, useRef, useState } from "react";
import { api, ErrorAPI } from "./api";
import type { Configuracion, VistaPrevia } from "./types";

export type EstadoPrevia = "listo" | "cargando" | "incompleto" | "error";

// Estima con el catálogo ya guardado cuántas vacantes cumplirían el borrador. Espera a que se deje de editar.
export function useVistaPrevia(config: Configuracion | null) {
  const [datos, setDatos] = useState<VistaPrevia | null>(null);
  const [estado, setEstado] = useState<EstadoPrevia>("cargando");
  const [motivo, setMotivo] = useState("");
  const turno = useRef(0);
  const cuerpo = config ? JSON.stringify({ configuracion: config }) : "";
  useEffect(() => {
    if (!cuerpo) return;
    const mio = ++turno.current;
    setEstado("cargando");
    const espera = setTimeout(async () => {
      try {
        const r = await api<VistaPrevia>("/vista-previa", {
          method: "POST",
          body: cuerpo,
        });
        if (mio !== turno.current) return;
        if (r.incompleto) {
          setMotivo(r.motivo || "");
          setEstado("incompleto");
        } else {
          setDatos(r);
          setEstado("listo");
        }
      } catch (e) {
        if (mio === turno.current)
          setEstado(
            e instanceof ErrorAPI && e.status === 422 ? "incompleto" : "error",
          );
      }
    }, 450);
    return () => clearTimeout(espera);
  }, [cuerpo]);
  return { datos, estado, motivo };
}
