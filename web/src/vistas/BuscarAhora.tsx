// 18 nov (pedido de Oscar): «Buscar ahora» en el Resumen, para no tener que ir a GitHub el día que GitHub no lanza la
// búsqueda de las 6:30. El servidor la lanza con su propia llave de GitHub (panel/acciones.py); sin esa llave el botón
// no aparece. Mientras hay una en cola o corriendo, el botón queda bloqueado y dice desde cuándo.
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { api } from "../api";
import { Dialog } from "../comunes";

type Corrida = {
  estado: string;
  creada: string;
  manual: boolean;
  enlace: string;
};
export type EstadoBusqueda = {
  disponible: boolean;
  en_curso?: Corrida | null;
  ultima_hoy?: Corrida | null;
};

const hora = (iso: string) =>
  iso
    ? new Date(iso).toLocaleTimeString("es-CO", {
        hour: "numeric",
        minute: "2-digit",
        timeZone: "America/Bogota",
      })
    : "";

export function BuscarAhora({
  hoyCorrio,
  sinConfirmar,
  demo,
  onAviso,
  onTermino,
}: {
  hoyCorrio: string | null; // hora de la búsqueda de hoy según el panel, o null si hoy no hubo
  sinConfirmar: boolean; // hay cambios que la búsqueda no va a usar
  demo: boolean;
  onAviso: (texto: string, error?: boolean) => void;
  onTermino: () => void;
}) {
  const [estado, setEstado] = useState<EstadoBusqueda | null>(null);
  const [abierto, setAbierto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const corria = useRef(false);
  const alTerminar = useRef(onTermino);
  useEffect(() => {
    alTerminar.current = onTermino;
  }, [onTermino]);

  const leer = useCallback(() => {
    api<EstadoBusqueda>("/busqueda")
      .then((e) => {
        if (corria.current && !e.en_curso) alTerminar.current();
        corria.current = Boolean(e.en_curso);
        setEstado(e);
      })
      .catch(() => setEstado((v) => v ?? { disponible: false }));
  }, []);
  useEffect(leer, [leer]);
  const enCurso = estado?.en_curso;
  const corriendo = Boolean(enCurso);
  useEffect(() => {
    if (!corriendo) return;
    const t = window.setInterval(leer, demo ? 5000 : 30000);
    return () => window.clearInterval(t);
  }, [corriendo, demo, leer]);

  if (!estado?.disponible) return null;

  async function lanzar() {
    setEnviando(true);
    try {
      await api("/busqueda", { method: "POST", body: "{}" });
      setAbierto(false);
      onAviso(
        "Búsqueda pedida. Empieza en unos minutos y tarda alrededor de una hora y media; puedes cerrar el panel.",
      );
      corria.current = true;
      setEstado({
        ...estado!,
        en_curso: {
          estado: "en_cola",
          creada: new Date().toISOString(),
          manual: true,
          enlace: "",
        },
      });
      window.setTimeout(leer, 8000);
    } catch (e) {
      onAviso((e as Error).message, true);
      leer();
    } finally {
      setEnviando(false);
    }
  }

  const yaHoy =
    hoyCorrio ||
    (estado.ultima_hoy && estado.ultima_hoy.estado === "success"
      ? hora(estado.ultima_hoy.creada)
      : null);
  return (
    <>
      <button
        className="button secondary"
        disabled={Boolean(enCurso) || enviando}
        onClick={() => setAbierto(true)}
        title={
          enCurso
            ? "Ya hay una búsqueda " +
              (enCurso.estado === "en_cola" ? "en cola" : "corriendo")
            : "Lanza ahora la búsqueda del día"
        }
      >
        {enCurso ? (
          <Loader2 size={16} className="spin" />
        ) : (
          <Search size={16} />
        )}
        {enCurso
          ? (enCurso.estado === "en_cola" ? "En cola" : "Buscando") +
            (enCurso.creada ? " desde " + hora(enCurso.creada) : "…")
          : "Buscar ahora"}
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
