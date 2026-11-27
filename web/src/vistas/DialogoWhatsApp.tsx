// El mensaje de WhatsApp de un cliente (dividido de main.tsx): prepararlo, copiarlo entero o por partes, y su
// vista previa. Copiar no envía nada.
import { useState } from "react";
import { CheckCheck, Copy, MessageCircle } from "lucide-react";
import { api } from "../api";
import { Dialog } from "../comunes";

export function useWhatsApp(
  selectedClient: string,
  resultDate: string,
  notify: (s: string, error?: boolean) => void,
  setModal: (m: "whatsapp") => void,
) {
  const [mensaje, setMensaje] = useState("");
  const [copiado, setCopiado] = useState(false);
  // Contrato v43 (regla 7): el operador elige cuántas copiar; con más de 10 se copia en partes.
  const [cuantasWhats, setCuantasWhats] = useState("10");
  const [partesWhats, setPartesWhats] = useState<string[]>([]);
  const [parteCopiada, setParteCopiada] = useState<number | null>(null);
  const [notaWhats, setNotaWhats] = useState("");
  const [abriendoWhatsApp, setAbriendoWhatsApp] = useState(false);
  async function abrirWhatsApp() {
    // 18 nov: la carga se ve en el botón; el resto de la página sigue usable.
    setAbriendoWhatsApp(true);
    try {
      const consulta = new URLSearchParams({
        cuantas: String(Math.max(1, Math.round(Number(cuantasWhats)) || 10)),
        ...(resultDate ? { fecha: resultDate } : {}),
      });
      const r = await api<{
        texto: string;
        vacantes: number;
        partes?: string[];
        nota?: string;
      }>("/whatsapp/" + selectedClient + "?" + consulta.toString());
      if (!r.texto) {
        notify(
          r.nota || "No hay vacantes con comprobación vigente para copiar.",
          true,
        );
        return;
      }
      setNotaWhats(r.nota || "");
      setMensaje(r.texto);
      setPartesWhats(r.partes?.length ? r.partes : [r.texto]);
      setParteCopiada(null);
      setCopiado(false);
      setModal("whatsapp");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setAbriendoWhatsApp(false);
    }
  }
  async function copiar(texto = mensaje, parte: number | null = null) {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(parte === null);
      setParteCopiada(parte);
      notify(
        parte === null
          ? "Mensaje copiado. Ya puedes pegarlo en WhatsApp."
          : `Parte ${parte + 1} copiada. Pégala en WhatsApp y vuelve por la siguiente.`,
      );
    } catch {
      notify(
        "El navegador bloqueó el portapapeles. Selecciona el mensaje y cópialo manualmente.",
        true,
      );
    }
  }
  return {
    mensaje,
    copiado,
    cuantasWhats,
    setCuantasWhats,
    partesWhats,
    parteCopiada,
    notaWhats,
    abriendoWhatsApp,
    abrirWhatsApp,
    copiar,
  };
}

export function DialogoWhatsApp({
  notaWhats,
  partesWhats,
  parteCopiada,
  mensaje,
  copiado,
  copiar,
  setModal,
}: {
  notaWhats: string;
  partesWhats: string[];
  parteCopiada: number | null;
  mensaje: string;
  copiado: boolean;
  copiar: (texto?: string, parte?: number | null) => void;
  setModal: (m: null) => void;
}) {
  return (
    <Dialog
      ancho
      titulo="Un mensaje, más oportunidades"
      subtitulo="Revisa el mensaje antes de copiarlo y compartirlo en WhatsApp."
      onClose={() => setModal(null)}
    >
      {notaWhats && (
        <p className="aviso-busqueda" role="status">
          {notaWhats}
        </p>
      )}
      {partesWhats.length > 1 ? (
        // Más de 10: se copia por partes (2 por empresa; el resto va en «Tengo N más»).
        partesWhats.map((parte, i) => (
          <div className="whatsapp-preview whatsapp-parte" key={i}>
            <div>
              <MessageCircle size={18} />
              <strong>
                Parte {i + 1} de {partesWhats.length}
              </strong>
              <button
                type="button"
                className="button whatsapp"
                onClick={() => copiar(parte, i)}
              >
                {parteCopiada === i ? (
                  <CheckCheck size={16} />
                ) : (
                  <Copy size={16} />
                )}
                {parteCopiada === i ? "Copiada" : "Copiar esta parte"}
              </button>
            </div>
            <textarea
              aria-label={`Parte ${i + 1} del mensaje de WhatsApp`}
              readOnly
              value={parte}
              onFocus={(e) => e.currentTarget.select()}
            />
          </div>
        ))
      ) : (
        <div className="whatsapp-preview">
          <div>
            <MessageCircle size={18} />
            <strong>Vista previa del mensaje</strong>
          </div>
          <textarea
            aria-label="Mensaje de WhatsApp"
            readOnly
            value={mensaje}
            onFocus={(e) => e.currentTarget.select()}
          />
        </div>
      )}
      <p className="helper">
        Los enlaces se vuelven a contrastar al preparar el mensaje. Copiar no
        envía nada ni confirma una postulación.
      </p>
      <div className="dialog-actions">
        <button className="button secondary" onClick={() => setModal(null)}>
          Cerrar
        </button>
        {partesWhats.length <= 1 && (
          <button className="button whatsapp" onClick={() => copiar()}>
            {copiado ? <CheckCheck size={17} /> : <Copy size={17} />}
            {copiado ? "Mensaje copiado" : "Copiar el mensaje"}
          </button>
        )}
      </div>
    </Dialog>
  );
}
