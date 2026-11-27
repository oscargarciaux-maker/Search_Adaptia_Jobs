// Diálogos para archivar un cliente o un cargo, eliminar un cargo archivado y eliminar del todo un cliente archivado.
// Archivar y eliminar un cargo cambian el borrador: la búsqueda los usa al pulsar «Aplicar cambios».
import { Archive, Trash2 } from "lucide-react";
import type { Cargo, Configuracion, Cliente, EstadoConfig } from "../types";
import { Dialog } from "../comunes";
import { useState } from "react";
import { api } from "../api";

// El cliente o el cargo que se va a archivar.
export type Archivo = { tipo: "cliente" | "cargo"; id: string; nombre: string };

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
  archive: Archivo;
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

// «Eliminar definitivamente» un cliente archivado (15 nov): pide escribir BORRAR.
export function BorrarClienteDialog({
  cliente,
  revision,
  dirty,
  notify,
  onListo,
  onClose,
}: {
  cliente: Cliente;
  revision: number;
  dirty: boolean;
  notify: (s: string, error?: boolean) => void;
  onListo: (estado: EstadoConfig) => void;
  onClose: () => void;
}) {
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <Dialog titulo={`Eliminar «${cliente.nombre}»`} onClose={onClose}>
      <p className="dialog-copy">
        Se quita de la configuración junto con sus perfiles, su WhatsApp y sus
        mensajes preparados. No se puede deshacer. Las vacantes que ya recibió y
        las configuraciones anteriores se conservan en el historial.
      </p>
      {dirty && (
        <p className="importar-error" role="alert">
          Tienes cambios sin aplicar. Pulsa «Aplicar cambios» antes de eliminar.
        </p>
      )}
      <div className="field">
        <label htmlFor="borrar-confirmar">Escribe BORRAR para confirmar</label>
        <input
          id="borrar-confirmar"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          autoComplete="off"
        />
      </div>
      <div className="dialog-actions">
        <button type="button" className="button secondary" onClick={onClose}>
          Cancelar
        </button>
        <button
          type="button"
          className="button danger-button"
          disabled={dirty || ocupado || texto.trim().toUpperCase() !== "BORRAR"}
          onClick={async () => {
            setOcupado(true);
            try {
              const r = await api<{ estado: EstadoConfig }>(
                `/clientes/${cliente.id}/borrar`,
                {
                  method: "POST",
                  body: JSON.stringify({ revision, confirmacion: texto }),
                },
              );
              onListo(r.estado);
              notify(`«${cliente.nombre}» se eliminó definitivamente.`);
            } catch (e) {
              notify((e as Error).message, true);
            } finally {
              setOcupado(false);
            }
          }}
        >
          Eliminar definitivamente
        </button>
      </div>
    </Dialog>
  );
}
