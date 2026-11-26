// 18 nov (pedido de Oscar): «Buscar ahora» en el Resumen, para no tener que ir a GitHub el día que GitHub no lanza la
// búsqueda de las 6:30. El servidor la lanza con su propia llave de GitHub (panel/acciones.py); sin esa llave el botón
// no aparece. Mientras hay una en cola o corriendo, o si otra tarea ocupa el turno, el botón no deja lanzar y dice por
// qué (aria-disabled: sigue enfocable y el foco no se pierde al cerrar el diálogo).
// Contrato v49: el mismo botón en el detalle de un cliente (`cliente`): busca solo para sus perfiles que no llegan a
// su meta (o, si hoy aún no hay búsqueda, hace la del día con sus perfiles primero). El servidor decide y guarda los
// perfiles; el navegador solo manda el cliente.
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { api } from "../api";
import { Dialog, horaBogota } from "../comunes";

type Corrida = {
  estado:
    "en_cola" | "corriendo" | "success" | "failure" | "cancelled" | string;
  creada: string;
};
// Contrato v45: qué hará el botón, decidido por el servidor (un solo botón para los tres casos). v49: «pedido» es el
// de un cliente cuando hoy ya hay lote.
type Plan = {
  tipo: "completa" | "faltantes" | "pedido" | "nada";
  motivo: string;
  detalle?: string; // qué pasa después de pedirla (texto del servidor)
  faltan: {
    perfil_id: string;
    cliente: string;
    cargo: string;
    hoy: number;
    meta: number;
  }[];
};
type EstadoBusqueda = {
  disponible: boolean;
  en_curso?: Corrida | null;
  ocupado?: string | null;
  ultima_pedida?: Corrida | null;
  plan: Plan; // siempre viene cuando `disponible`
};

const ESPERA_PEDIDA = 180_000; // ms: GitHub tarda unos segundos (o más) en listar la corrida pedida

export function BuscarAhora({
  sinAplicar,
  onAplicar,
  revision,
  cliente,
  demo,
  onAviso,
  onTermino,
}: {
  sinAplicar: boolean; // hay cambios que la búsqueda no va a usar
  // Contrato v49: aplicar los cambios antes de buscar (true si quedaron en uso).
  onAplicar?: () => Promise<boolean>;
  revision?: number; // versión en uso: al cambiar, se vuelve a pedir el plan
  cliente?: { id: string; nombre: string };
  demo: boolean;
  onAviso: (texto: string, error?: boolean) => void;
  onTermino: () => void;
}) {
  const [estado, setEstado] = useState<EstadoBusqueda | null>(null);
  const [pedidaEn, setPedidaEn] = useState<number | null>(null);
  const [abierto, setAbierto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const corria = useRef(false); // el servidor la vio en cola o corriendo
  const avisada = useRef(""); // corrida cancelada ya avisada
  const callbacks = useRef({ onTermino, onAviso });
  useEffect(() => {
    callbacks.current = { onTermino, onAviso };
  }, [onTermino, onAviso]);
  const clienteId = cliente?.id || "";

  const leer = useCallback(() => {
    api<EstadoBusqueda>(
      "/busqueda" +
        (clienteId ? "?cliente_id=" + encodeURIComponent(clienteId) : ""),
    )
      .then((e) => {
        if (e.en_curso) setPedidaEn(null);
        if (corria.current && !e.en_curso) callbacks.current.onTermino();
        corria.current = Boolean(e.en_curso);
        const c = e.ultima_pedida;
        if (
          !e.en_curso &&
          c?.estado === "cancelled" &&
          avisada.current !== c.creada
        ) {
          avisada.current = c.creada;
          callbacks.current.onAviso(
            `GitHub canceló la búsqueda pedida a las ${horaBogota(c.creada)} (otra tarea tomó su turno). Puedes volver a pedirla.`,
            true,
          );
        }
        setEstado(e);
      })
      .catch(() =>
        setEstado(
          (v) =>
            v ?? {
              disponible: false,
              plan: { tipo: "completa", motivo: "", faltan: [] },
            },
        ),
      );
  }, [clienteId]);
  useEffect(leer, [leer, revision]);

  // La corrida pedida se muestra «En cola» hasta que GitHub la liste, como mucho ESPERA_PEDIDA.
  useEffect(() => {
    if (pedidaEn === null) return;
    const t = window.setTimeout(() => setPedidaEn(null), ESPERA_PEDIDA);
    return () => window.clearTimeout(t);
  }, [pedidaEn]);
  const esperandoLista = pedidaEn !== null;
  const enCurso: Corrida | null =
    estado?.en_curso ??
    (esperandoLista
      ? { estado: "en_cola", creada: new Date(pedidaEn!).toISOString() }
      : null);
  const activo = Boolean(enCurso);
  useEffect(() => {
    if (!activo) return;
    const t = window.setInterval(leer, demo || esperandoLista ? 5000 : 30000);
    return () => window.clearInterval(t);
  }, [activo, demo, esperandoLista, leer]);

  if (!estado?.disponible) return null;

  async function lanzar(aplicarAntes = false) {
    setEnviando(true);
    try {
      if (aplicarAntes && onAplicar && !(await onAplicar())) return;
      const r = await api<{ tipo: Plan["tipo"] }>("/busqueda", {
        method: "POST",
        body: JSON.stringify(clienteId ? { cliente_id: clienteId } : {}),
      });
      setAbierto(false);
      setPedidaEn(Date.now());
      onAviso(
        r.tipo === "faltantes"
          ? "Búsqueda pedida para quienes no llegan a su meta. Tarda unos 30 minutos; puedes cerrar el panel."
          : r.tipo === "pedido"
            ? `Búsqueda pedida para ${cliente?.nombre}. Tarda unos 30 minutos; puedes cerrar el panel.`
            : "Búsqueda del día pedida" +
              (cliente
                ? `, con los perfiles de ${cliente.nombre} primero`
                : "") +
              ". Empieza en unos minutos y tarda alrededor de una hora y media; puedes cerrar el panel.",
      );
    } catch (e) {
      onAviso((e as Error).message, true);
      leer();
    } finally {
      setEnviando(false);
    }
  }

  const plan = estado.plan;
  const bloqueo = enCurso
    ? `Ya hay una búsqueda ${enCurso.estado === "en_cola" ? "en cola" : "corriendo"}.`
    : estado.ocupado || (plan.tipo === "nada" ? plan.motivo : "");
  const titulo = cliente
    ? `Buscar ahora para ${cliente.nombre}`
    : "Buscar ahora";
  const etiqueta = enCurso
    ? `${enCurso.estado === "en_cola" ? "En cola" : "Buscando"} desde ${horaBogota(enCurso.creada)}`
    : titulo;
  const varios = plan.tipo === "faltantes" || plan.tipo === "pedido";
  return (
    <>
      <button
        type="button"
        className="button secondary"
        aria-disabled={Boolean(bloqueo) || enviando}
        title={
          bloqueo ||
          (cliente
            ? `Busca ahora vacantes para ${cliente.nombre}`
            : "Lanza ahora la búsqueda del día")
        }
        onClick={() => {
          if (bloqueo) onAviso(bloqueo, true);
          else if (!enviando) setAbierto(true);
        }}
      >
        {enCurso ? (
          <Loader2 size={16} className="spin" />
        ) : (
          <Search size={16} />
        )}
        {etiqueta}
      </button>
      {abierto && (
        <Dialog
          titulo={titulo}
          subtitulo={
            cliente
              ? "Busca solo lo que le falta hoy a este cliente."
              : "Revisa si hoy ya corrió la búsqueda y busca lo que haga falta."
          }
          onClose={() => !enviando && setAbierto(false)}
        >
          <p className="helper note">{plan.motivo}</p>
          {varios && (
            <ul
              className="faltan-lista"
              aria-label="Quiénes no llegan a su meta"
            >
              {plan.faltan.slice(0, 8).map((f) => (
                <li key={f.perfil_id}>
                  <span>{cliente ? f.cargo : `${f.cliente} · ${f.cargo}`}</span>
                  <strong>
                    {f.hoy} de {f.meta}
                  </strong>
                </li>
              ))}
              {plan.faltan.length > 8 && (
                <li>
                  <span>y {plan.faltan.length - 8} más</span>
                </li>
              )}
            </ul>
          )}
          {plan.detalle && <p className="helper">{plan.detalle}</p>}
          {sinAplicar && (
            <p className="helper note">
              Tienes cambios sin aplicar: la búsqueda usa la configuración en
              uso.
              {onAplicar
                ? " Pulsa «Aplicar y buscar» para que los use."
                : " Si quieres que los use, pulsa antes «Aplicar cambios»."}
            </p>
          )}
          {demo && (
            <p className="demo-inline">
              Demostración: no se lanza ninguna búsqueda real.
            </p>
          )}
          <div className="dialog-actions">
            <button
              type="button"
              className="button secondary"
              disabled={enviando}
              onClick={() => setAbierto(false)}
            >
              Cancelar
            </button>
            {sinAplicar && onAplicar && (
              <button
                type="button"
                className="button secondary"
                disabled={enviando}
                onClick={() => lanzar(true)}
              >
                Aplicar y buscar
              </button>
            )}
            <button
              type="button"
              className="button primary"
              disabled={enviando}
              onClick={() => lanzar()}
            >
              {enviando ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Search size={16} />
              )}
              {sinAplicar && onAplicar ? "Buscar sin aplicar" : "Buscar ahora"}
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
