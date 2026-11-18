// 18 nov (pedido de Oscar): una vacante «por confirmar» como tarjeta para decidir rápido en el detalle del cliente.
// Toma de Open Seat solo la estructura (título, empresa, fichas, resumen corto y un botón grande); los colores, bordes
// y tipografía son los del panel, en modo claro y oscuro.
import { Check, ExternalLink, X } from "lucide-react";
import { iniciales, modos } from "../comunes";
import type { Revision } from "../types";

const IDIOMAS: Record<string, string> = { es: "Español", en: "Inglés" };
const NIVELES: Record<string, string> = {
  trainee: "Prácticas",
  junior: "Junior",
  "semi senior": "Semi senior",
  senior: "Senior",
  lead: "Líder",
};

export function hace(publicada: string, hoy = new Date()) {
  if (!publicada) return "";
  const dias = Math.round(
    (hoy.getTime() - new Date(publicada.slice(0, 10) + "T12:00:00").getTime()) /
      86400000,
  );
  if (dias <= 0) return "Hoy";
  if (dias === 1) return "Hace 1 día";
  return `Hace ${dias} días`;
}

export function TarjetaPorConfirmar({
  r,
  sugeridos,
  ocupado,
  onSirve,
  onNoSirve,
  onElegirPais,
}: {
  r: Revision;
  sugeridos: string | null; // países sugeridos en palabras; null = hay que elegirlos en la bandeja
  ocupado: boolean;
  onSirve: () => void;
  onNoSirve: () => void;
  onElegirPais: () => void;
}) {
  const fichas = [
    ...(r.cargos || []),
    NIVELES[r.nivel || ""] || "",
    modos[r.modalidad] || r.modalidad,
    r.ubicacion,
    IDIOMAS[r.idioma] ? "Aviso en " + IDIOMAS[r.idioma].toLowerCase() : "",
    hace(r.publicada),
  ].filter(Boolean);
  const resumen = r.extracto || r.frase || "";
  return (
    <article
      className="tarjeta-confirmar"
      aria-label={`${r.titulo} en ${r.empresa}`}
    >
      <div className="tarjeta-confirmar-cabeza">
        <span className="company-avatar" aria-hidden="true">
          {iniciales(r.empresa)}
        </span>
        <div>
          <h4>{r.titulo}</h4>
          <span className="tarjeta-confirmar-empresa">{r.empresa}</span>
        </div>
      </div>
      {fichas.length > 0 && (
        <ul className="tarjeta-confirmar-fichas" aria-label="Datos del aviso">
          {fichas.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}
      {resumen && <p className="tarjeta-confirmar-resumen">{resumen}</p>}
      <p className="tarjeta-confirmar-pais">
        {sugeridos
          ? `País sugerido: ${sugeridos}`
          : r.motivo || "País por confirmar"}
      </p>
      <div className="tarjeta-confirmar-acciones">
        {sugeridos !== null ? (
          <button
            type="button"
            className="button primary grande"
            disabled={ocupado}
            onClick={onSirve}
          >
            <Check size={16} />
            Sí, sirve
          </button>
        ) : (
          <button
            type="button"
            className="button primary grande"
            onClick={onElegirPais}
          >
            Elegir país en Por confirmar
          </button>
        )}
        <button
          type="button"
          className="button secondary"
          disabled={ocupado}
          onClick={onNoSirve}
        >
          <X size={15} />
          No sirve
        </button>
        {r.enlace.startsWith("http") && (
          <a
            className="text-button"
            href={r.enlace}
            target="_blank"
            rel="noopener noreferrer"
          >
            Ver aviso
            <ExternalLink size={14} />
          </a>
        )}
      </div>
    </article>
  );
}
