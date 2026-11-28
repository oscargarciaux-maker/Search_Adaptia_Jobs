// La configuración del panel: lo guardado, el borrador que se edita, si hay cambios sin
// aplicar y «Aplicar cambios», que guarda y deja en uso.
import { useMemo, useState } from "react";
import { api } from "./api";
import type { Configuracion, EstadoConfig } from "./types";
import { conMetas } from "./perfiles";

const vacio: Configuracion = { clientes: [], cargos: [], perfiles: [] };
// Compara dos configuraciones por su contenido, sin importar el orden de las claves.
function ordenado(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(ordenado);
  if (v && typeof v === "object")
    return Object.fromEntries(
      Object.keys(v as Record<string, unknown>)
        .sort()
        .map((k) => [k, ordenado((v as Record<string, unknown>)[k])]),
    );
  return v;
}
function mismoContenido(a: unknown, b: unknown) {
  return JSON.stringify(ordenado(a)) === JSON.stringify(ordenado(b));
}

// 8.1: el aviso temprano de cobertura, para añadir al mensaje de «Aplicar cambios».
export function avisosCobertura(avisos?: string[]) {
  return avisos?.length
    ? " Aviso de cobertura: " +
        avisos.join(" ") +
        " Mira «Huecos por país» en Historial para pedir una fuente nueva hoy."
    : "";
}

export function useConfiguracion(notify: (s: string, error?: boolean) => void) {
  const [estado, setEstado] = useState<EstadoConfig | null>(null),
    [draft, setDraft] = useState<Configuracion>(vacio),
    [marcado, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    // Contrato v49: por qué no se pudo dejar en uso lo guardado (se ve junto al botón hasta aplicar bien).
    [noAplica, setNoAplica] = useState("");
  // Lista grande (17 nov): hay cambios solo si lo editado es distinto de lo guardado. Si deshaces lo que cambiaste,
  // vuelve a «sin cambios» y no pide aplicar otra vez.
  const dirty = useMemo(
    () => marcado && mismoContenido(draft, estado?.borrador) === false,
    [marcado, draft, estado?.borrador],
  );
  // Contrato v49: cambios que la próxima búsqueda aún no usa (sin guardar, o guardados pero sin aplicar porque algo
  // lo impidió, o importados). El botón «Aplicar cambios» de la cabecera solo aparece entonces.
  const pendienteDeAplicar =
    dirty ||
    Boolean(estado?.revision && estado.publicada?.revision !== estado.revision);
  async function aplicarPendientes() {
    return (await aplicar()).aplicado;
  }
  function cambiar(v: Configuracion) {
    setDraft(v);
    setDirty(true);
  }
  // Contrato v49 (pedido de Oscar, 26 nov): un solo «Aplicar cambios» que guarda (PUT /config) y deja en uso
  // (POST /config/publicar, rige desde hoy: la próxima búsqueda ya lo usa; lo entregado no cambia). Si guardar
  // falla, nada cambia y se dice por qué. Si guarda pero no se puede dejar en uso (p. ej. metas por encima del
  // techo), los cambios quedan guardados, el motivo queda a la vista y el botón de la cabecera sigue pendiente.
  async function aplicar(
    config: Configuracion = draft,
    exito = "Cambios aplicados: la próxima búsqueda los usa.",
  ): Promise<{ guardado: boolean; aplicado: boolean; motivo: string }> {
    if (!estado)
      return { guardado: false, aplicado: false, motivo: "Recarga la página." };
    setBusy(true);
    let actual = estado;
    // 8.1: países nuevos sin fuente local (solo para el operador; no bloquea el guardado).
    let riesgo = "";
    try {
      if (!mismoContenido(config, estado.borrador)) {
        const r = await api<
          Partial<EstadoConfig> & {
            revision: number;
            borrador: Configuracion;
            avisos_cobertura?: string[];
          }
        >("/config", {
          method: "PUT",
          body: JSON.stringify({
            revision: estado.revision,
            configuracion: config,
          }),
        });
        const { avisos_cobertura, ...guardado } = r;
        riesgo = avisosCobertura(avisos_cobertura);
        actual = { ...estado, ...guardado };
        setEstado(actual);
      }
      // También cuando lo pedido ya era lo guardado (p. ej. reactivar lo que se había archivado sin aplicar).
      setDraft(actual.borrador);
      setDirty(false);
    } catch (e) {
      const motivo = (e as Error).message;
      notify("No se guardaron los cambios: " + motivo, true);
      setBusy(false);
      return { guardado: false, aplicado: false, motivo };
    }
    try {
      // Lo que se sabe sin preguntar al servidor (el mismo cálculo que `validar_publicacion`).
      const m = conMetas(actual.borrador);
      if (m.reales > m.techo)
        throw new Error(
          `Las metas suman ${m.reales} y el cupo diario es ${m.techo}: baja algunas metas o sube el cupo diario en «Cargos y metas», y vuelve a pulsar «Aplicar cambios».`,
        );
      if (m.total < 1)
        throw new Error(
          "Ningún perfil activo tiene meta diaria: da una meta a algún perfil y vuelve a pulsar «Aplicar cambios».",
        );
      const r = await api<{ revision: number; vigente_desde: string }>(
        "/config/publicar",
        { method: "POST", body: JSON.stringify({ revision: actual.revision }) },
      );
      const primera = !actual.publicada;
      setEstado({
        ...actual,
        publicada: { ...r, configuracion: structuredClone(actual.borrador) },
      });
      setNoAplica("");
      notify(
        exito +
          (primera
            ? " Desde ahora solo se buscan los cargos de tu lista (no los seis fijos de antes)."
            : "") +
          riesgo,
      );
      return { guardado: true, aplicado: true, motivo: "" };
    } catch (e) {
      const motivo = (e as Error).message;
      setNoAplica(motivo);
      notify(
        "Tus cambios quedaron guardados, pero la búsqueda todavía no los usa: " +
          motivo +
          riesgo,
        true,
      );
      return { guardado: true, aplicado: false, motivo };
    } finally {
      setBusy(false);
    }
  }
  return {
    estado,
    setEstado,
    draft,
    setDraft,
    setDirty,
    dirty,
    busy,
    setBusy,
    noAplica,
    pendienteDeAplicar,
    aplicarPendientes,
    cambiar,
    aplicar,
  };
}
