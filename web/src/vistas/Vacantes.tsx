// Contrato v29 (lista grande, PR 3): Vacantes en vista dividida, como LinkedIn. Lista compacta a la izquierda y el
// aviso completo a la derecha. ↑/↓ (o J/K) cambian de vacante; en el celular la ficha ocupa la pantalla.
import React, { useEffect, useRef, useState } from "react";
import { ArrowLeft, Megaphone } from "lucide-react";
import { modos } from "../comunes";
import type { Vacante } from "../types";
import {
  FichaVacante,
  claseEstado,
  etiquetaEstado,
  etiquetaPost,
} from "./FichaVacante";

function idDeHash() {
  const partes = decodeURIComponent(location.hash.replace(/^#\/?/, "")).split(
    "/",
  );
  return partes[0] === "vacantes" ? partes[1] || "" : "";
}

// Mover la elección con el teclado en cualquier lista dividida (también «Por confirmar»).
export function teclasLista(
  e: React.KeyboardEvent,
  ids: string[],
  actual: string,
  elegir: (id: string) => void,
) {
  const paso = { ArrowDown: 1, j: 1, ArrowUp: -1, k: -1 }[e.key];
  if (!paso || !ids.length) return;
  e.preventDefault();
  const i = Math.max(0, ids.indexOf(actual));
  const siguiente = ids[Math.min(ids.length - 1, Math.max(0, i + paso))];
  elegir(siguiente);
  const lista = (e.currentTarget as HTMLElement).closest("ul");
  requestAnimationFrame(() =>
    lista
      ?.querySelector<HTMLElement>(`[data-id="${CSS.escape(siguiente)}"]`)
      ?.focus(),
  );
}

export function ListaVacantes({ vacantes }: { vacantes: Vacante[] }) {
  const [elegida, setElegida] = useState(idDeHash);
  // En el celular la ficha se abre solo al tocar una vacante.
  const [verFicha, setVerFicha] = useState(false);
  const detalle = useRef<HTMLDivElement>(null);
  const actual = vacantes.find((v) => v.id === elegida) || vacantes[0];
  useEffect(() => {
    if (!actual) return;
    const h = "#vacantes/" + encodeURIComponent(actual.id);
    if (location.hash !== h) history.replaceState(null, "", h);
  }, [actual?.id]);
  function elegir(id: string, abrir = false) {
    setElegida(id);
    detalle.current?.scrollTo({ top: 0 });
    if (abrir) setVerFicha(true);
  }
  if (!actual) return null;
  const ids = vacantes.map((v) => v.id);
  return (
    <div className={"dividida" + (verFicha ? " ver-ficha" : "")}>
      <ul className="dividida-lista" aria-label={`${vacantes.length} vacantes`}>
        {vacantes.map((v) => (
          <li key={v.id}>
            <button
              type="button"
              data-id={v.id}
              className={
                "item-vacante" +
                (v.id === actual.id ? " elegida" : "") +
                (v.estado !== "lista" ? " no-disponible" : "")
              }
              aria-current={v.id === actual.id ? "true" : undefined}
              onClick={() => elegir(v.id, true)}
              onKeyDown={(e) =>
                teclasLista(e, ids, actual.id, (id) => elegir(id))
              }
            >
              <span className="item-titulo">{v.titulo}</span>
              <span className="item-empresa">{v.empresa}</span>
              <span className="item-lugar">
                {[v.ubicacion, modos[v.modalidad] || v.modalidad]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              <span className="item-etiquetas">
                <span className={"pill " + claseEstado(v)}>
                  {etiquetaEstado(v)}
                </span>
                {v.tipo === "post" && (
                  <span className="post-tag">
                    <Megaphone size={12} />
                    {etiquetaPost(v)}
                  </span>
                )}
                {(v.avisos || []).slice(0, 2).map((a) => (
                  <span key={a} className="no-cumple">
                    {a}
                  </span>
                ))}
                {(v.avisos || []).length > 2 && (
                  <span className="no-cumple">
                    +{(v.avisos || []).length - 2}
                  </span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="dividida-detalle" ref={detalle}>
        <FichaVacante
          key={actual.id}
          v={actual}
          volver={
            <button
              type="button"
              className="text-button solo-movil"
              onClick={() => setVerFicha(false)}
            >
              <ArrowLeft size={15} />
              Volver a la lista
            </button>
          }
        />
      </div>
    </div>
  );
}
