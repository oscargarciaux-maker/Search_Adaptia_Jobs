// La sección Resumen (dividido de main.tsx): el aviso si la búsqueda falló, las tarjetas y el detalle del cliente
// elegido, con su «Buscar ahora».
import React from "react";
import type {
  Borrador,
  Cliente,
  Configuracion,
  Ejecucion,
  EstadoConfig,
  ResumenClientes,
  Sesion,
} from "../types";
import type { conMetas } from "../perfiles";
import { TarjetasResumen, resumenDeClientes } from "./Resumen";
import { ClienteDetalle } from "./ClienteDetalle";
import { AvisoUltimaBusqueda } from "./Historial";
import { BuscarAhora } from "./BuscarAhora";

export function SeccionResumen({
  sesion,
  estado,
  draft,
  clientes,
  cargos,
  metas,
  total,
  runs,
  porCliente,
  pendientesPorCliente,
  porConfirmar,
  borradoresHoy,
  detalle,
  setDetalle,
  go,
  notify,
  recargarResumen,
  setEditCliente,
  setModal,
  setSelectedClient,
  setResultDate,
  enfocarWhatsApp,
  descargarBase,
  descargandoBase,
  pendienteDeAplicar,
  aplicarPendientes,
}: {
  sesion: Sesion;
  estado: EstadoConfig | null;
  draft: Configuracion;
  clientes: Cliente[];
  cargos: ReturnType<typeof conMetas>["cargos"];
  metas: ReturnType<typeof conMetas>;
  total: number;
  runs: Ejecucion[];
  porCliente: ResumenClientes | null;
  pendientesPorCliente: Record<string, number>;
  porConfirmar: number;
  borradoresHoy: Borrador[] | null;
  detalle: string;
  setDetalle: (id: string) => void;
  go: (t: string) => void;
  notify: (s: string, error?: boolean) => void;
  recargarResumen: () => void;
  setEditCliente: (c: Cliente | null) => void;
  setModal: (m: "cliente") => void;
  setSelectedClient: (id: string) => void;
  setResultDate: (d: string) => void;
  enfocarWhatsApp: React.RefObject<boolean>;
  descargarBase: (soloCliente?: string) => void;
  descargandoBase: boolean;
  pendienteDeAplicar: boolean;
  aplicarPendientes: () => Promise<boolean>;
}) {
  return (
    <>
      <AvisoUltimaBusqueda ultima={runs?.[0]} soloFallo />
      <TarjetasResumen
        clientes={resumenDeClientes(draft, porCliente, pendientesPorCliente)}
        diaConteo={porCliente?.dias.at(-1)?.fecha}
        onCliente={setDetalle}
        perfiles={
          draft.perfiles.filter(
            (p) => p.activo && clientes.some((c) => c.id === p.cliente_id),
          ).length
        }
        cargos={cargos}
        total={total}
        techo={metas.techo}
        reales={metas.reales}
        comunidad={metas.comunidad}
        ultima={runs?.[0]}
        porConfirmar={porConfirmar}
        borradores={borradoresHoy}
        go={go}
        onNuevoCliente={() => {
          setEditCliente(null);
          setModal("cliente");
        }}
      />
      {detalle &&
        (() => {
          const c = resumenDeClientes(
            draft,
            porCliente,
            pendientesPorCliente,
          ).find((x) => x.id === detalle);
          return c ? (
            <ClienteDetalle
              cliente={c}
              cfg={draft}
              dias={porCliente?.dias || []}
              ultima={runs?.[0]}
              notify={notify}
              onCerrar={() => setDetalle("")}
              onCambio={recargarResumen}
              onVacantes={(dia) => {
                setDetalle("");
                setSelectedClient(c.id);
                if (dia) {
                  setResultDate(dia);
                  enfocarWhatsApp.current = true;
                }
                go("Vacantes");
              }}
              onRevisar={() => {
                setDetalle("");
                go("Por confirmar");
              }}
              onCsv={() => descargarBase(c.id)}
              buscarAhora={
                <BuscarAhora
                  cliente={{ id: c.id, nombre: c.nombre }}
                  sinAplicar={pendienteDeAplicar}
                  onAplicar={aplicarPendientes}
                  revision={estado?.publicada?.revision}
                  demo={Boolean(sesion.demo)}
                  onAviso={notify}
                  onTermino={recargarResumen}
                />
              }
              onEditar={() => {
                setDetalle("");
                setEditCliente(
                  draft.clientes.find((x) => x.id === c.id) || null,
                );
                setModal("cliente");
              }}
              descargando={descargandoBase}
            />
          ) : null;
        })()}
    </>
  );
}
