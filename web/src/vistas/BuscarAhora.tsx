// 18 nov (pedido de Oscar): «Buscar ahora» en el Resumen, para no tener que ir a GitHub el día que GitHub no lanza la
// búsqueda de las 6:30. El servidor la lanza con su propia llave de GitHub (panel/acciones.py); sin esa llave el botón
// no aparece. Mientras hay una en cola o corriendo, o si otra tarea ocupa el turno, el botón no deja lanzar y dice por
// qué (aria-disabled: sigue enfocable y el foco no se pierde al cerrar el diálogo).
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { api } from "../api";
import { Dialog, horaBogota, hoyBogota } from "../comunes";
import type { Ejecucion } from "../types";

type Corrida = {
  estado:
    "en_cola" | "corriendo" | "success" | "failure" | "cancelled" | string;
  creada: string;
};
type EstadoBusqueda = {
  disponible: boolean;
  en_curso?: Corrida | null;
  ocupado?: string | null;
  ultima_pedida?: Corrida | null;
};

const ESPERA_PEDIDA = 180_000; // ms: GitHub tarda unos segundos (o más) en listar la corrida pedida

export function BuscarAhora({
  ultima,
  sinConfirmar,
  demo,
  onAviso,
  onTermino,
}: {
  ultima: Ejecucion | undefined; // la última búsqueda registrada por el panel
  sinConfirmar: boolean; // hay cambios que la búsqueda no va a usar
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

  const leer = useCallback(() => {
    api<EstadoBusqueda>("/busqueda")
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
      .catch(() => setEstado((v) => v ?? { disponible: false }));
  }, []);
  useEffect(leer, [leer]);

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

  async function lanzar() {
    setEnviando(true);
    try {
      await api("/busqueda", { method: "POST", body: "{}" });
      setAbierto(false);
      setPedidaEn(Date.now());
      onAviso(
        "Búsqueda pedida. Empieza en unos minutos y tarda alrededor de una hora y media; puedes cerrar el panel.",
      );
    } catch (e) {
      onAviso((e as Error).message, true);
      leer();
    } finally {
      setEnviando(false);
    }
  }

  const bloqueo = enCurso
    ? `Ya hay una búsqueda ${enCurso.estado === "en_cola" ? "en cola" : "corriendo"}.`
    : estado.ocupado || "";
  const etiqueta = enCurso
    ? `${enCurso.estado === "en_cola" ? "En cola" : "Buscando"} desde ${horaBogota(enCurso.creada)}`
    : "Buscar ahora";
  const yaHoy =
    ultima?.fecha === hoyBogota() ? horaBogota(ultima.iniciada_en) : null;
  return (
    <>
      <button
        className="button secondary"
        aria-disabled={Boolean(bloqueo) || enviando}
        title={bloqueo || "Lanza ahora la búsqueda del día"}
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
          titulo="Buscar ahora"
          subtitulo="Lanza la búsqueda del día sin esperar a su horario."
          onClose={() => !enviando && setAbierto(false)}
        >
          {yaHoy ? (
            <p className="helper note">
              Hoy ya hubo una búsqueda ({yaHoy}). Esta completa lo que falte
              para cada cliente, sin repetir lo que ya se entregó.
            </p>
          ) : (
            <p className="helper">
              Hoy todavía no hay búsqueda: esta hace la del día.
            </p>
          )}
          <p className="helper">
            Empieza en unos minutos y tarda alrededor de una hora y media.
            Puedes cerrar el panel: sigue sola.
          </p>
          {sinConfirmar && (
            <p className="helper note">
              Tienes cambios sin confirmar: la búsqueda usa la última
              configuración confirmada. Si quieres que los use, pulsa antes
              «Confirmar y aplicar».
            </p>
          )}
          {demo && (
            <p className="demo-inline">
              Demostración: no se lanza ninguna búsqueda real.
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={enviando}
              onClick={() => setAbierto(false)}
            >
              Cancelar
            </button>
            <button
              className="button primary"
              disabled={enviando}
              onClick={lanzar}
            >
              {enviando ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Search size={16} />
              )}
              Buscar ahora
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
