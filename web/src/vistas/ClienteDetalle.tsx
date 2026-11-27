// Detalle de un cliente desde el Resumen.
import React, { useEffect, useState } from "react";
import {
  BriefcaseBusiness,
  Download,
  MapPin,
  MessageCircle,
  Pencil,
} from "lucide-react";
import { api } from "../api";
import type {
  Configuracion,
  Ejecucion,
  Revisiones,
  ResumenClientes,
  Revision,
} from "../types";
import { Dialog, REGIONES, diaCorto, fecha, nombrePais } from "../comunes";
import { TarjetaPorConfirmar } from "./TarjetaPorConfirmar";
import type { ResumenCliente } from "./TarjetasResumen";

// Paso 8 (variante B): el detalle de un cliente desde el Resumen, con sus 7 días, lo que más le corta, su CSV y sus
// «por confirmar» para decidir ahí mismo.
export function ClienteDetalle({
  cliente: c,
  dias,
  ultima,
  notify,
  onCerrar,
  onCambio,
  onVacantes,
  onRevisar,
  onCsv,
  onEditar,
  descargando,
  buscarAhora,
}: {
  cliente: ResumenCliente;
  cfg: Configuracion;
  dias: ResumenClientes["dias"];
  ultima?: Ejecucion;
  notify: (s: string, error?: boolean) => void;
  onCerrar: () => void;
  onCambio: () => void;
  // Contrato v48: con `dia`, abre Vacantes en ese día para copiar su mensaje de WhatsApp.
  onVacantes: (dia?: string) => void;
  onRevisar: () => void;
  onCsv: () => void;
  onEditar: () => void;
  descargando: boolean;
  // Contrato v49: «Buscar ahora» para este cliente (no aparece sin la llave de GitHub).
  buscarAhora?: React.ReactNode;
}) {
  const [ocupado, setOcupado] = useState("");
  // Contrato v29: sus «por confirmar» se piden al servidor, con su total real.
  const [pendientes, setPendientes] = useState<Revisiones | null>(null);
  function cargarPendientes() {
    api<Revisiones>(
      "/revisiones?pagina=1&por_pagina=8&cliente_id=" +
        encodeURIComponent(c.id),
    )
      .then(setPendientes)
      .catch(() =>
        setPendientes({ pendientes: [], total: 0, ayudan_faltantes: 0 }),
      );
  }
  useEffect(cargarPendientes, [c.id]);
  const serie = dias.map((d) => ({ fecha: d.fecha, n: d.clientes[c.id] || 0 }));
  const tope = Math.max(c.meta, 1, ...serie.map((d) => d.n));
  const faltan =
    c.recibidas == null ? c.meta : Math.max(0, c.meta - c.recibidas);
  const cortes = [...new Set(c.perfiles.map((p) => p.cargo))]
    .map((cargo) => ({
      cargo,
      texto: ultima?.resumen.embudo?.[cargo]?.principal_perdida || "",
    }))
    .filter((x) => x.texto);
  const nombreLugar = (codigo: string) =>
    REGIONES.find((r) => r.codigo === codigo)?.nombre || nombrePais(codigo);
  const paisesDe = (r: Revision) =>
    r.funciones
      ? []
      : r.paises_sugeridos?.length
        ? r.paises_sugeridos
        : r.sugerencia[0]
          ? [r.sugerencia[0]]
          : null;
  async function decidir(r: Revision, decision: "sirve" | "no_sirve") {
    setOcupado(r.vacante_id);
    try {
      const res = await api<{ asignadas: number }>(
        "/revisiones/" + encodeURIComponent(r.vacante_id),
        {
          method: "POST",
          body: JSON.stringify({
            decision,
            paises: decision === "sirve" ? paisesDe(r) || [] : [],
            aplicar_a_iguales: false,
          }),
        },
      );
      notify(
        decision === "sirve"
          ? `Confirmada: se asignó a ${res.asignadas} cliente(s).`
          : "Descartada.",
      );
      onCambio();
      cargarPendientes();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado("");
    }
  }
  const visibles = pendientes?.pendientes || [];
  const totalPendientes = pendientes?.total ?? c.porConfirmar;
  return (
    <Dialog titulo={c.nombre} subtitulo={c.cargo} onClose={onCerrar} ancho>
      {/* Lista grande del 16 nov: datos a la izquierda y sus «por confirmar» a la derecha, sin salir del detalle. */}
      <div className="detalle-dos-paneles">
        <div className="detalle-izquierda">
          <div className="detalle-cifras">
            <div>
              <b>{c.recibidas ?? "—"}</b>
              <span>
                {c.recibidas == null
                  ? "Sin búsquedas aún"
                  : `recibidas de ${c.meta}`}
              </span>
            </div>
            <div className={c.porConfirmar ? "ambar" : ""}>
              <b>{c.porConfirmar}</b>
              <span>por confirmar</span>
            </div>
            <div>
              <b>{faltan}</b>
              <span>{faltan === 1 ? "falta" : "faltan"} para su meta</span>
            </div>
          </div>

          {serie.length > 0 && (
            <section className="detalle-seccion">
              <h3>Últimos {serie.length} días</h3>
              <div
                className="dias-barras"
                role="img"
                aria-label={
                  "Recibidas por día: " +
                  serie.map((d) => `${fecha(d.fecha)}, ${d.n}`).join("; ")
                }
              >
                {serie.map((d) => (
                  <div key={d.fecha} aria-hidden="true">
                    <b>{d.n}</b>
                    <i
                      className={"barra" + (d.n < c.meta / 2 ? " bajo" : "")}
                      style={{ height: Math.max(4, (d.n / tope) * 100) + "%" }}
                    />
                    <span>{diaCorto(d.fecha)}</span>
                  </div>
                ))}
              </div>
              {serie.some((d) => d.n > 0) && (
                <div
                  className="dias-tomar"
                  role="group"
                  aria-label="Tomar las vacantes de un día para enviarlas por WhatsApp"
                >
                  {serie
                    .filter((d) => d.n > 0)
                    .map((d) => (
                      <button
                        key={d.fecha}
                        type="button"
                        className="button secondary"
                        aria-label={`Tomar las ${d.n} vacantes del ${fecha(d.fecha)}`}
                        onClick={() => onVacantes(d.fecha)}
                      >
                        <MessageCircle size={14} aria-hidden="true" />
                        Tomar vacantes · {diaCorto(d.fecha)}
                      </button>
                    ))}
                </div>
              )}
            </section>
          )}

          <section className="detalle-seccion">
            <h3>Sus perfiles</h3>
            <ul className="detalle-lista">
              {c.perfiles.map((p, i) => (
                <li key={i}>
                  {p.cargo} · meta de {p.meta} al día
                  {p.sinCiudad && (
                    <>
                      {" "}
                      <span className="falta-ciudad">
                        <MapPin size={13} aria-hidden="true" />
                        Falta la ciudad
                      </span>
                    </>
                  )}
                </li>
              ))}
              {!c.perfiles.length && <li>Aún no tiene perfiles activos.</li>}
            </ul>
            {c.perfiles.some((p) => p.sinCiudad) && (
              <p className="field-help">
                Tiene presencial o híbrido sin ciudad: sin ciudad no le llegan
                presenciales ni híbridas. Escríbela en «Editar perfil».
              </p>
            )}
          </section>

          {cortes.length > 0 && (
            <section className="detalle-seccion">
              <h3>Lo que más corta en su cargo</h3>
              <ul className="detalle-lista">
                {cortes.map((x) => (
                  <li key={x.cargo}>
                    <b>{x.cargo}:</b> {x.texto}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="button secondary editar-perfil"
                onClick={onEditar}
              >
                <Pencil size={15} />
                Editar perfil
              </button>
              <p className="field-help">
                En el perfil verás cuántas vacantes cumplen hoy y qué ajuste
                añadiría más.
              </p>
            </section>
          )}

          <div className="detalle-acciones">
            <button
              type="button"
              className="button primary"
              onClick={() => onVacantes()}
            >
              <BriefcaseBusiness size={16} />
              Ver sus vacantes
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={onCsv}
              disabled={descargando}
            >
              <Download size={16} />
              {descargando ? "Descargando…" : "Descargar su CSV de hoy"}
            </button>
            {buscarAhora}
            {!cortes.length && (
              <button
                type="button"
                className="button secondary"
                onClick={onEditar}
              >
                <Pencil size={15} />
                Editar perfil
              </button>
            )}
          </div>
        </div>

        <section className="detalle-seccion detalle-derecha">
          <h3>Por confirmar ({totalPendientes})</h3>
          {pendientes && !totalPendientes && (
            <p className="field-help">Nada pendiente para este cliente.</p>
          )}
          {visibles.map((r) => {
            const paises = paisesDe(r);
            return (
              <TarjetaPorConfirmar
                key={r.vacante_id}
                r={r}
                sugeridos={
                  paises === null
                    ? null
                    : paises.slice(0, 3).map(nombreLugar).join(", ") +
                      (paises.length > 3 ? ` y ${paises.length - 3} más` : "")
                }
                ocupado={ocupado === r.vacante_id}
                onSirve={() => decidir(r, "sirve")}
                onNoSirve={() => decidir(r, "no_sirve")}
                onElegirPais={onRevisar}
              />
            );
          })}
          {totalPendientes > visibles.length && (
            <button type="button" className="text-button" onClick={onRevisar}>
              Ver las {totalPendientes} en Por confirmar
            </button>
          )}
        </section>
      </div>
    </Dialog>
  );
}
