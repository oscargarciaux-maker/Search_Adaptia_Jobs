// Vista previa del mensaje de WhatsApp de un cliente, para copiarlo entero o por partes. Copiar no envía nada.
import { CheckCheck, Copy, MessageCircle } from "lucide-react";
import { Dialog } from "../comunes";

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
