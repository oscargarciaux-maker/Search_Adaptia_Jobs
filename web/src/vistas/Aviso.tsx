// El aviso que aparece abajo tras una acción (dividido de main.tsx), con su acción opcional.
import { Check, ShieldCheck, X } from "lucide-react";

export function Aviso({
  toast,
  setToast,
}: {
  toast: {
    texto: string;
    error: boolean;
    accion?: { texto: string; hacer: () => void };
  };
  setToast: (t: null) => void;
}) {
  return (
    <div
      className={"toast " + (toast.error ? "error" : "")}
      role={toast.error ? "alert" : "status"}
    >
      {toast.error ? <ShieldCheck size={18} /> : <Check size={18} />}
      <span>{toast.texto}</span>
      {toast.accion && (
        <button
          type="button"
          className="toast-accion"
          onClick={() => {
            const a = toast.accion;
            setToast(null);
            a?.hacer();
          }}
        >
          {toast.accion.texto}
        </button>
      )}
      <button aria-label="Cerrar aviso" onClick={() => setToast(null)}>
        <X size={15} />
      </button>
    </div>
  );
}
