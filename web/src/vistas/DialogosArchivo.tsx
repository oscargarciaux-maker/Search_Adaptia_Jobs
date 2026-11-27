// Diálogos para archivar un cliente o un cargo y para eliminar un cargo archivado (dividido de main.tsx). Los dos
// cambian el borrador; la búsqueda los usa al pulsar «Aplicar cambios».
import { Archive, Trash2 } from "lucide-react";
import type { Cargo, Configuracion } from "../types";
import { Dialog } from "../comunes";

export function EliminarCargoDialog({
  borrarCargo,
  setBorrarCargo,
  draft,
  cambiar,
  notify,
}: {
  borrarCargo: Cargo;
  setBorrarCargo: (c: Cargo | null) => void;
  draft: Configuracion;
  cambiar: (v: Configuracion) => void;
  notify: (s: string, error?: boolean) => void;
}) {
  return (
    <Dialog
      titulo={"Eliminar " + borrarCargo.nombre}
      subtitulo="Se quita de la configuración para siempre. Lo ya entregado y el historial se conservan."
      onClose={() => setBorrarCargo(null)}
    >
      {(() => {
        const suyos = draft.perfiles.filter(
          (p) => p.cargo_id === borrarCargo.id,
        ).length;
        return (
          <p className="helper">
            {suyos
              ? `También se quitan ${suyos} ${suyos === 1 ? "perfil de cliente que buscaba" : "perfiles de clientes que buscaban"} este cargo; sus clientes conservan los demás perfiles.`
              : "Ningún cliente busca este cargo."}{" "}
            Se aplica al pulsar «Aplicar cambios».
          </p>
        );
      })()}
      <div className="dialog-actions">
        <button
          className="button secondary"
          onClick={() => setBorrarCargo(null)}
        >
          Cancelar
        </button>
        <button
          className="button danger-button"
          onClick={() => {
            const id = borrarCargo.id;
            cambiar({
              ...draft,
              cargos: draft.cargos.filter((x) => x.id !== id),
              perfiles: draft.perfiles.filter((p) => p.cargo_id !== id),
            });
            notify(
              `«${borrarCargo.nombre}» se eliminó. Pulsa «Aplicar cambios» para que la búsqueda lo use.`,
            );
            setBorrarCargo(null);
          }}
        >
          <Trash2 size={16} />
          Eliminar definitivamente
        </button>
      </div>
    </Dialog>
  );
}

export function ArchivarDialog({
  archive,
  clientCount,
  setModal,
  draft,
  cambiar,
  notify,
}: {
  archive: { tipo: "cliente" | "cargo"; id: string; nombre: string };
  clientCount: (id: string) => number;
  setModal: (m: null) => void;
  draft: Configuracion;
  cambiar: (v: Configuracion) => void;
  notify: (s: string, error?: boolean) => void;
}) {
  return (
    <Dialog titulo={"Archivar " + archive.tipo} onClose={() => setModal(null)}>
      <p className="dialog-copy">
        {archive.tipo === "cliente"
          ? `Cuando pulses «Aplicar cambios», «${archive.nombre}» deja de recibir vacantes desde la próxima búsqueda. Las vacantes que ya recibió se conservan y puedes reactivarlo cuando quieras.`
          : `Cuando pulses «Aplicar cambios», se deja de buscar «${archive.nombre}» desde la próxima búsqueda. Las vacantes ya entregadas se conservan.`}
      </p>
      {archive.tipo === "cargo" && clientCount(archive.id) > 0 && (
        <p className="role-warning" role="alert">
          Atención: {clientCount(archive.id)}{" "}
          {clientCount(archive.id) === 1 ? "cliente tiene" : "clientes tienen"}{" "}
          este cargo. Dejarán de recibir sus vacantes hasta que vuelvas a
          activarlo o les asignes otro.
        </p>
      )}
      <div className="dialog-actions">
        <button className="button secondary" onClick={() => setModal(null)}>
          Cancelar
        </button>
        <button
          className="button danger-button"
          onClick={() => {
            cambiar(
              archive.tipo === "cliente"
                ? {
                    ...draft,
                    clientes: draft.clientes.map((c) =>
                      c.id === archive.id ? { ...c, activo: false } : c,
                    ),
                  }
                : {
                    ...draft,
                    cargos: draft.cargos.map((c) =>
                      c.id === archive.id ? { ...c, activo: false } : c,
                    ),
                  },
            );
            setModal(null);
            notify(
              "Archivado. Sus vacantes ya recibidas se conservan. Pulsa «Aplicar cambios» para que la búsqueda lo use.",
            );
          }}
        >
          <Archive size={16} />
          Archivar
        </button>
      </div>
    </Dialog>
  );
}
