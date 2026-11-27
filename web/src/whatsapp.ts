// El mensaje de WhatsApp de un cliente: prepararlo con sus vacantes y copiarlo entero o por partes. Copiar no
// envía nada.
import { useState } from "react";
import { api } from "./api";

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
