// Mensajes de WhatsApp del día (contratos v10 y v31): nada se envía solo.
import React, { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
} from "lucide-react";
import { api } from "../api";
import { Ayuda, Empty, origenMensaje } from "../comunes";
import type { Cliente, Borrador } from "../types";

export const estadosMensaje: Record<Borrador["estado"], string> = {
  pendiente: "Por enviar",
  abierto: "Abierto en WhatsApp",
  enviado: "Enviado",
  descartado: "Descartado",
};

export function Mensajes({
  clientes,
  notify,
}: {
  clientes: Cliente[];
  notify: (s: string, error?: boolean) => void;
}) {
  const [lista, setLista] = useState<Borrador[] | null>(null);
  const [soloPendientes, setSoloPendientes] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  async function cargar() {
    try {
      const r = await api<{ borradores: Borrador[] }>("/borradores");
      setLista(r.borradores);
    } catch (e) {
      notify((e as Error).message, true);
      setLista([]);
    }
  }
  useEffect(() => {
    cargar();
  }, []);
  // Contrato v31: el cambio se ve al momento; si el servidor lo rechaza, se deshace y se avisa.
  async function cambiar(b: Borrador, cambios: Partial<Borrador>) {
    const poner = (datos: Partial<Borrador>) =>
      setLista((l) =>
        (l || []).map((x) => (x.id === b.id ? { ...x, ...datos } : x)),
      );
    poner(cambios);
    try {
      const r = await api<Borrador>("/borradores/" + b.id, {
        method: "PATCH",
        body: JSON.stringify(cambios),
      });
      // El enlace de WhatsApp lo calcula la lista; la respuesta del cambio no lo trae.
      poner({ ...r, enlace: b.enlace, pocas: b.pocas });
    } catch (e) {
      poner(b);
      notify((e as Error).message, true);
    }
  }
  async function generar() {
    setOcupado(true);
    try {
      const r = await api<{
        generados: number;
        conservados: number;
        sin_vacantes?: number;
        sin_contacto?: number;
        por_recomprobar?: number;
        clientes_activos?: number;
      }>("/borradores/generar", { method: "POST" });
      // Contrato v10: explicar por qué no salió nada, en lugar de un aviso genérico (13 nov).
      const razones: string[] = [];
      if (r.sin_contacto)
        razones.push(
          `${r.sin_contacto} de ${r.clientes_activos ?? r.sin_contacto} clientes sin WhatsApp o sin consentimiento (agrégalos en «Editar cliente»)`,
        );
      if (r.sin_vacantes)
        razones.push(
          `${r.sin_vacantes} clientes sin vacantes listas hoy` +
            (r.por_recomprobar
              ? ` (${r.por_recomprobar} esperan que se recompruebe su enlace; vuelve a intentarlo en una hora)`
              : ""),
        );
      if (r.conservados)
        razones.push(
          `${r.conservados} mensajes ya abiertos, enviados o editados no se tocaron`,
        );
      notify(
        r.generados
          ? `${r.generados} mensajes preparados.` +
              (razones.length ? " " + razones.join(". ") + "." : "")
          : "No se preparó ningún mensaje: " +
              (razones.join(". ") || "no hay vacantes listas nuevas") +
              ".",
        !r.generados,
      );
      await cargar();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  }
  const nombre = (id: string) =>
    clientes.find((c) => c.id === id)?.nombre || "Cliente";
  const visibles = (lista || []).filter(
    (b) =>
      !soloPendientes || b.estado === "pendiente" || b.estado === "abierto",
  );
  return (
    <section className="card activity mensajes">
      <div className="section-title">
        <h2>
          Mensajes de hoy{" "}
          <Ayuda etiqueta="mensajes">
            Para que una persona reciba su mensaje, en «Clientes» añade su
            WhatsApp y marca que aceptó recibir vacantes. Nada se envía solo:
            «Abrir en WhatsApp» abre su chat con el mensaje escrito para que lo
            revises y lo envíes.
          </Ayuda>
        </h2>
        <div className="alerts-actions">
          <label className="check-line">
            <input
              type="checkbox"
              checked={soloPendientes}
              onChange={(e) => setSoloPendientes(e.target.checked)}
            />
            Solo pendientes
          </label>
          <button
            type="button"
            className="button secondary"
            disabled={ocupado}
            onClick={generar}
          >
            <RefreshCw size={14} /> Preparar mensajes
          </button>
        </div>
      </div>
      <ParaMi
        notify={notify}
        cambios={(lista || []).map((b) => b.id + b.estado).join()}
      />
      {!!lista?.some((b) => b.estado !== "descartado") && (
        <fieldset className="enviados">
          <legend>
            Enviados hoy: {lista.filter((b) => b.estado === "enviado").length}{" "}
            de {lista.filter((b) => b.estado !== "descartado").length}
          </legend>
          {lista
            .filter((b) => b.estado !== "descartado")
            .map((b) => (
              <label key={b.id} className="check-line">
                <input
                  type="checkbox"
                  checked={b.estado === "enviado"}
                  onChange={(e) =>
                    cambiar(b, {
                      estado: e.target.checked ? "enviado" : "abierto",
                    })
                  }
                />
                {nombre(b.cliente_id)}
              </label>
            ))}
        </fieldset>
      )}
      {lista === null ? (
        <p className="muted">
          <Loader2 size={14} className="spin" /> Cargando mensajes…
        </p>
      ) : !visibles.length ? (
        <Empty
          icon={MessageCircle}
          title="No hay mensajes por enviar"
          texto="Los mensajes se preparan solos cada mañana tras la búsqueda. También puedes pulsar «Preparar mensajes»."
        />
      ) : (
        // Lista grande (17 nov, opción B): las tarjetas de mensaje de dos en dos, para ver más clientes a la vez.
        <div className="mensajes-columnas">
          {visibles.map((b) => (
            <article className="mensaje" key={b.id}>
              <div className="mensaje-lado">
                <div className="mensaje-top">
                  <div>
                    <h3>{nombre(b.cliente_id)}</h3>
                    <p className="muted">
                      {b.cargos.join(" · ")} · {b.vacantes.length}{" "}
                      {b.vacantes.length === 1 ? "vacante" : "vacantes"}
                      {/* Contrato v46: de qué día son (caso Juan: «0 de 10» en el Resumen y 7 aquí). */}
                      {origenMensaje(b) && ` · ${origenMensaje(b)}`}
                      {b.pocas && !b.anteriores && " · hoy hubo menos de 5"}
                    </p>
                  </div>
                  <span
                    className={
                      "pill " + (b.estado === "enviado" ? "green" : "amber")
                    }
                  >
                    {estadosMensaje[b.estado]}
                  </span>
                </div>
              </div>
              <label className="sr-only" htmlFor={"texto-" + b.id}>
                Mensaje para {nombre(b.cliente_id)}
              </label>
              <textarea
                id={"texto-" + b.id}
                defaultValue={b.texto}
                rows={8}
                onBlur={(e) =>
                  e.target.value !== b.texto &&
                  cambiar(b, { texto: e.target.value })
                }
              />
              <div className="alerts-actions">
                <button
                  type="button"
                  className="text-button"
                  onClick={() => cambiar(b, { estado: "descartado" })}
                >
                  Descartar
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(b.texto);
                      notify("Mensaje copiado.");
                    } catch {
                      notify("No se pudo copiar; selecciona el texto.", true);
                    }
                  }}
                >
                  <Copy size={14} /> Copiar
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => cambiar(b, { estado: "enviado" })}
                >
                  <Check size={14} /> Marcar como enviado
                </button>
                {b.enlace && (
                  <a
                    className="button primary"
                    href={b.enlace}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() =>
                      b.estado === "pendiente" &&
                      cambiar(b, { estado: "abierto" })
                    }
                  >
                    <MessageCircle size={14} /> Abrir en WhatsApp
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

type ParaOperador = { texto: string; enlace: string; clientes: number };

// Contrato v46 (decisión de Oscar, 18 nov): «Mandarme todos a mi WhatsApp» es UN mensaje a su propio chat, con un
// enlace corto por cliente, y un solo clic. El enlace se prepara solo al abrir Mensajes y cada vez que cambian los
// mensajes, así el botón es un enlace de verdad (sin ventanas bloqueadas). Nada se envía solo.
function ParaMi({
  notify,
  cambios,
}: {
  notify: (s: string, error?: boolean) => void;
  cambios: string; // cambia cuando cambian los mensajes del día
}) {
  const [numero, setNumero] = useState("");
  const [guardado, setGuardado] = useState("");
  const [paraMi, setParaMi] = useState<ParaOperador | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<{ telefono: string }>("/ajustes/operador")
      .then((r) => {
        // Si ya se escribió algo mientras cargaba, se respeta.
        setNumero((actual) => actual || r.telefono);
        setGuardado(r.telefono);
      })
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!guardado) return;
    let vigente = true;
    api<ParaOperador>("/borradores/para-mi")
      .then((r) => {
        if (!vigente) return;
        setParaMi(r);
        setError("");
      })
      .catch((e) => vigente && setError((e as Error).message));
    return () => {
      vigente = false;
    };
  }, [guardado, cambios]);
  async function guardar() {
    try {
      const r = await api<{ telefono: string }>("/ajustes/operador", {
        method: "PUT",
        body: JSON.stringify({ telefono: numero }),
      });
      setNumero(r.telefono);
      setGuardado(r.telefono);
      if (!r.telefono) setParaMi(null);
      notify(r.telefono ? "Tu número quedó guardado." : "Número borrado.");
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  const listo = Boolean(guardado && paraMi?.enlace);
  const motivo = !guardado
    ? "Guarda primero tu número."
    : error ||
      (paraMi && !paraMi.clientes
        ? "No hay mensajes por enviar con WhatsApp del cliente."
        : "Preparando…");
  return (
    <div className="para-mi">
      <div className="field">
        <label htmlFor="operador-telefono">Mi número</label>
        <div className="para-mi-numero">
          <input
            id="operador-telefono"
            type="tel"
            inputMode="tel"
            autoComplete="off"
            placeholder="+57 300 123 4567"
            value={numero}
            onChange={(e) => setNumero(e.target.value)}
          />
          <button
            type="button"
            className="button secondary"
            disabled={numero === guardado}
            onClick={guardar}
          >
            Guardar
          </button>
        </div>
      </div>
      {listo ? (
        <a
          className="button primary"
          href={paraMi!.enlace}
          target="_blank"
          rel="noreferrer"
        >
          <Send size={15} />
          Mandarme todos a mi WhatsApp
        </a>
      ) : (
        <button
          type="button"
          className="button primary"
          aria-disabled="true"
          onClick={() => notify(motivo, true)}
        >
          <Send size={15} />
          Mandarme todos a mi WhatsApp
        </button>
      )}
      {listo && (
        <span className="muted para-mi-cuantos">
          Un solo mensaje con {paraMi!.clientes}{" "}
          {paraMi!.clientes === 1 ? "cliente" : "clientes"}
        </span>
      )}
      <Ayuda etiqueta="mandarme todos">
        Abre tu propio WhatsApp con un solo mensaje listo: un enlace corto por
        cliente. Lo envías, y desde el teléfono tocas cada enlace: se abre el
        chat del cliente con su mensaje y lo envías. Los enlaces valen solo hoy
        y mientras el mensaje no esté enviado.
      </Ayuda>
    </div>
  );
}
