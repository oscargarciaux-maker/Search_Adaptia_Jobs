// Piezas compartidas del panel (lista grande, PR 3): ayudas, diálogos, vacíos, países y formatos.
import React, { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, Info, Plus, X } from "lucide-react";

export const fecha = (v: string) =>
  new Date(v + "T12:00:00").toLocaleDateString("es-CO", {
    day: "numeric",
    month: "long",
  });
export const modos: Record<string, string> = {
  remoto: "Remoto",
  hibrido: "Híbrido",
  presencial: "Presencial",
};
export const grados: Record<string, string> = {
  exact: "Cargo exacto",
  similar: "Cargo afín",
  close: "Cargo cercano",
};

export function iniciales(nombre: string) {
  return nombre
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((x) => x[0])
    .join("")
    .toUpperCase();
}

// Sección 6 (13 nov): explicación a demanda (ⓘ). Se ve al pasar el ratón, al enfocar con teclado o al tocar; Escape la
// cierra. Así las explicaciones no ocupan pantalla todo el tiempo.
export function Ayuda({
  etiqueta,
  children,
}: {
  etiqueta: string;
  children: React.ReactNode;
}) {
  const id = useId();
  return (
    <span className="ayuda">
      <button
        type="button"
        className="ayuda-boton"
        aria-label={"Más información: " + etiqueta}
        aria-describedby={id}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault(); // cierra la ayuda, no el diálogo
            e.stopPropagation();
            e.currentTarget.blur();
          }
        }}
      >
        <Info size={15} aria-hidden="true" />
      </button>
      <span role="tooltip" id={id} className="ayuda-texto">
        {children}
      </span>
    </span>
  );
}

// Sección 7a (13 nov): en vez de los desplegables con triángulo, un botón que dice qué muestra y qué oculta.
export function Plegable({
  mostrar,
  ocultar,
  className,
  inicial = false,
  children,
}: {
  mostrar: string;
  ocultar: string;
  className?: string;
  inicial?: boolean;
  children: React.ReactNode;
}) {
  const [abierto, setAbierto] = useState(inicial);
  const id = useId();
  return (
    <div className={"plegable " + (className || "")}>
      <button
        type="button"
        className="plegable-boton"
        aria-expanded={abierto}
        aria-controls={id}
        onClick={() => setAbierto(!abierto)}
      >
        <ChevronDown size={16} className={abierto ? "girado" : ""} />
        {abierto ? ocultar : mostrar}
      </button>
      {abierto && (
        <div id={id} className="plegable-contenido">
          {children}
        </div>
      )}
    </div>
  );
}

export function Dialog({
  titulo,
  subtitulo,
  onClose,
  children,
  ancho = false,
}: {
  titulo: string;
  subtitulo?: string;
  onClose: () => void;
  children: React.ReactNode;
  ancho?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    // Al cerrar, el foco vuelve al botón que abrió la ventana (WCAG 2.4.3).
    const origen = document.activeElement as HTMLElement | null;
    const dialogo = ref.current;
    dialogo?.showModal();
    return () => {
      dialogo?.close();
      if (origen && document.contains(origen)) origen.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={ancho ? "dialog ancho" : "dialog"}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="dialog-head">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <p>{subtitulo}</p>}
        </div>
        <button className="icon" aria-label="Cerrar" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

// Contrato v19: regiones que se eligen de una vez (el servidor las convierte en sus países).
// Contrato v23: todos los países (llegan con la sesión). Se guardan aquí para no pasarlos por cada componente.
let MUNDO: { codigo: string; nombre: string }[] = [];
export function fijarMundo(lista: { codigo: string; nombre: string }[]) {
  MUNDO = lista;
}
export const paisesMundo = () => MUNDO;
export const nombrePais = (codigo: string) =>
  MUNDO.find((p) => p.codigo === codigo)?.nombre || codigo;
export const sinTildes = (t: string) =>
  t
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
export function SelectorPaises({
  etiqueta,
  valores,
  onChange,
  excluir = [],
  extra = [],
  visible,
  placeholder = "Escribe un país y pulsa Enter",
}: {
  etiqueta: string;
  valores: string[];
  onChange: (v: string[]) => void;
  excluir?: string[];
  extra?: { codigo: string; nombre: string }[];
  // Texto corto a la vista; `etiqueta` queda para lectores de pantalla (contrato v30, filas de ubicación).
  visible?: string;
  placeholder?: string;
}) {
  const [texto, setTexto] = useState("");
  const id = useId();
  const opciones = [...extra, ...MUNDO].filter(
    (o) => !valores.includes(o.codigo) && !excluir.includes(o.codigo),
  );
  const nombre = (c: string) =>
    extra.find((o) => o.codigo === c)?.nombre || nombrePais(c);
  function agregar(valor: string) {
    const t = sinTildes(valor);
    if (!t) return false;
    const o =
      opciones.find((x) => sinTildes(x.nombre) === t) ||
      opciones.find((x) => sinTildes(x.nombre).startsWith(t));
    if (!o) return false;
    onChange([...valores, o.codigo]);
    setTexto("");
    return true;
  }
  return (
    <div className="field">
      <label htmlFor={id}>
        {visible ? (
          <>
            <span aria-hidden="true">{visible}</span>
            <span className="visually-hidden">{etiqueta}</span>
          </>
        ) : (
          etiqueta
        )}
      </label>
      <div className="tagbox">
        {valores.map((c) => (
          <span className="term" key={c}>
            {nombre(c)}
            <button
              type="button"
              aria-label={"Quitar " + nombre(c)}
              onClick={() => onChange(valores.filter((x) => x !== c))}
            >
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          id={id}
          list={id + "-lista"}
          placeholder={placeholder}
          value={texto}
          onChange={(e) => {
            // Elegir de la lista desplegable lo añade al momento.
            if (
              opciones.some(
                (o) => sinTildes(o.nombre) === sinTildes(e.target.value),
              )
            )
              agregar(e.target.value);
            else setTexto(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              agregar(texto);
            }
          }}
        />
        <datalist id={id + "-lista"}>
          {opciones.map((o) => (
            <option key={o.codigo} value={o.nombre} />
          ))}
        </datalist>
      </div>
    </div>
  );
}
export const REGIONES: { codigo: string; nombre: string }[] = [
  { codigo: "LATAM", nombre: "LATAM (todos los países)" },
  { codigo: "SUD_CENTRO_MX", nombre: "Sudamérica, Centroamérica y México" },
  { codigo: "SUDAMERICA", nombre: "Sudamérica" },
  { codigo: "CENTROAMERICA", nombre: "Centroamérica" },
  { codigo: "LATAM_ES", nombre: "LATAM y España" },
  { codigo: "MUNDO", nombre: "Mundo (remoto en cualquier lugar)" },
];
export const ETIQUETA_SUGERIDA: Record<string, string> = {
  sirve: "sirve",
  otro_pais: "solo para otro país",
  no_sirve: "no sirve",
};

export function Empty({
  icon: Icon,
  title,
  texto,
  action,
  label,
  actionIcon: ActionIcon = Plus,
}: {
  icon: React.ComponentType<{ size: number }>;
  title: string;
  texto: string;
  action?: () => void;
  label?: string;
  actionIcon?: React.ComponentType<{ size: number }>;
}) {
  return (
    <div className="empty">
      <span>
        <Icon size={27} />
      </span>
      <h3>{title}</h3>
      <p>{texto}</p>
      {action && (
        <button className="button primary" onClick={action}>
          <ActionIcon size={16} />
          {label}
        </button>
      )}
    </div>
  );
}

export const SEPARADORES = /[,;\n]/;
export function TagInput({
  label,
  values,
  onChange,
  visible,
  placeholder = "Añade un término y pulsa Enter",
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  visible?: string;
  placeholder?: string;
}) {
  const id = useId();
  const [text, setText] = useState("");
  // Reunión del 14 nov: escribir o pegar «A, B; C» guardaba una sola cadena. Ahora cada parte es un término.
  function sumar(partes: string[]) {
    const salida = [...values];
    for (const bruto of partes) {
      const t = bruto.trim();
      if (t && !salida.some((x) => x.toLowerCase() === t.toLowerCase()))
        salida.push(t);
    }
    if (salida.length !== values.length) onChange(salida);
  }
  function add() {
    sumar(text.split(SEPARADORES));
    setText("");
  }
  return (
    <div className="field">
      <label htmlFor={id}>{visible || label}</label>
      <div className="tagbox">
        {values.map((t) => (
          <span className="term" key={t}>
            {t}
            <button
              type="button"
              aria-label={"Quitar " + t}
              onClick={() => onChange(values.filter((x) => x !== t))}
            >
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          id={id}
          aria-label={label}
          placeholder={placeholder}
          value={text}
          onChange={(e) => {
            const partes = e.target.value.split(SEPARADORES);
            if (partes.length > 1) {
              // Lo que va antes de la última coma ya es un término; lo último sigue escribiéndose.
              sumar(partes.slice(0, -1));
              setText(partes[partes.length - 1].trimStart());
            } else setText(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          onBlur={add}
        />
      </div>
    </div>
  );
}
