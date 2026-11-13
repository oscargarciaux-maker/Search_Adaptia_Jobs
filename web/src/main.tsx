import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  Upload,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Archive,
  BriefcaseBusiness,
  CalendarClock,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  Clipboard,
  Clock3,
  Code2,
  Compass,
  Copy,
  Ellipsis,
  ExternalLink,
  Globe2,
  LayoutDashboard,
  ListFilter,
  Loader2,
  LogOut,
  Mail,
  MapPin,
  Megaphone,
  Menu,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  Users,
  Workflow,
  X,
} from "lucide-react";
import { api, ErrorAPI } from "./api";
import type {
  Cargo,
  Cliente,
  Configuracion,
  EstadoConfig,
  Perfil,
  Resultados,
  Sesion,
  Ejecucion,
  Vacante,
  EstimacionCargo,
  Borrador,
  Contacto,
  Embudo,
  EstimacionEnVivo,
  EstimacionPerfil,
  VistaPrevia,
  Revision,
  Revisiones,
  Regla,
} from "./types";
import "./style.css";

const uid = () => crypto.randomUUID();
const colores = ["#2b7863", "#516e88", "#836641", "#766491", "#965a63"]; // ≥4,5:1 sobre su fondo tenue
const fecha = (v: string) =>
  new Date(v + "T12:00:00").toLocaleDateString("es-CO", {
    day: "numeric",
    month: "long",
  });
const modos: Record<string, string> = {
  remoto: "Remoto",
  hibrido: "Híbrido",
  presencial: "Presencial",
};
const grados: Record<string, string> = {
  exact: "Cargo exacto",
  similar: "Cargo afín",
  close: "Cargo cercano",
};
const vacio: Configuracion = { clientes: [], cargos: [], perfiles: [] };
function iniciales(nombre: string) {
  return nombre
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((x) => x[0])
    .join("")
    .toUpperCase();
}
function hoyBogota() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Bogota",
  }).format(new Date());
}
function manana() {
  const d = new Date(hoyBogota() + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
// Por qué no hay vacantes: sin configuración, a la espera de la primera búsqueda o sin coincidencias.
function vacioVacantes(estado: EstadoConfig | null, r: Resultados | null) {
  if (!estado?.publicada)
    return {
      title: "Programa la configuración para empezar",
      texto:
        "Las vacantes de cada cliente aparecen después de la primera búsqueda nocturna con su configuración. Ve a «Cargos y cupos» y pulsa «Programar para mañana».",
    };
  const desde = estado.publicada.vigente_desde;
  if (!r?.ejecucion || r.ejecucion.fecha < desde)
    return {
      title: "Aún no hay búsqueda para este cliente",
      texto:
        "La primera búsqueda con tu configuración será el " +
        fecha(desde) +
        " a la 1:17 a. m. (hora Colombia). Después aparecerán aquí sus vacantes.",
    };
  return {
    title: "La búsqueda no encontró vacantes para este cliente",
    texto:
      "La búsqueda del " +
      fecha(r.ejecucion.fecha) +
      " no trajo vacantes que cumplan los filtros de este cliente. Revisa sus filtros en «Clientes» con la estimación.",
  };
}

function perfilNuevo(cliente: string, cargo: string): Perfil {
  return {
    id: uid(),
    cliente_id: cliente,
    cargo_id: cargo,
    activo: true,
    vive_en: "CO",
    modalidades: ["remoto"],
    paises_presenciales_extra: [],
    antiguedad_dias: 14,
    idiomas: ["es", "en"],
    ingles_maximo: "sin_filtro",
    experiencia_min: null,
    experiencia_max: null,
    aceptar_experiencia_sin_dato: false,
    aceptar_ingles_sin_dato: false,
  };
}

function Dialog({
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
    ref.current?.showModal();
    return () => {
      ref.current?.close();
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
function TagInput({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
}) {
  const [text, setText] = useState("");
  function add() {
    const t = text.trim();
    if (t && !values.some((x) => x.toLowerCase() === t.toLowerCase()))
      onChange([...values, t]);
    setText("");
  }
  return (
    <div className="field">
      <label>{label}</label>
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
          aria-label={label}
          placeholder="Añade un término y pulsa Enter"
          value={text}
          onChange={(e) => setText(e.target.value)}
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
function CargoDialog({
  cargo,
  onClose,
  onSave,
  notify,
}: {
  cargo: Cargo | null;
  onClose: () => void;
  onSave: (c: Cargo) => void;
  notify: (s: string, error?: boolean) => void;
}) {
  const [c, setC] = useState<Cargo>(
    cargo
      ? structuredClone(cargo)
      : {
          id: uid(),
          nombre: "",
          cupo: 0,
          activo: true,
          terminos_exactos: [],
          terminos_similares: [],
          terminos_excluidos: [],
          terminos_cercanos: [],
        },
  );
  const [busy, setBusy] = useState(false);
  const [nota, setNota] = useState("");
  async function expandir() {
    setBusy(true);
    try {
      const r = await api<{
        terminos_exactos: string[];
        terminos_similares: string[];
        terminos_cercanos?: string[];
        fuentes: string[];
        requiere_revision: boolean;
      }>("/cargos/expandir", {
        method: "POST",
        body: JSON.stringify({ cargo: c.nombre }),
      });
      setC((v) => ({
        ...v,
        terminos_exactos: r.terminos_exactos,
        terminos_similares: r.terminos_similares,
        terminos_cercanos: r.terminos_cercanos?.length
          ? r.terminos_cercanos
          : v.terminos_cercanos || [],
      }));
      setNota(
        r.fuentes.join(" · ") +
          (r.requiere_revision
            ? ". No encontramos afines fiables; puedes añadirlos aquí."
            : ". Revisa y ajusta las sugerencias."),
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      titulo={cargo ? "Editar cargo y cupo" : "Añadir un cargo"}
      subtitulo="Un mismo cupo puede servir a varios clientes compatibles."
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (c.nombre.trim().length < 2 || busy) return;
          if (
            !cargo &&
            !c.terminos_exactos.length &&
            !c.terminos_similares.length
          ) {
            await expandir();
            return;
          }
          onSave({
            ...c,
            nombre: c.nombre.trim(),
            terminos_exactos: c.terminos_exactos.length
              ? c.terminos_exactos
              : [c.nombre.trim()],
          });
        }}
      >
        <fieldset disabled={busy}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="cargo-nombre">Cargo</label>
              <input
                id="cargo-nombre"
                autoFocus
                required
                minLength={2}
                maxLength={120}
                value={c.nombre}
                placeholder="Por ejemplo, Frontend"
                onChange={(e) => setC({ ...c, nombre: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="cargo-cupo">Vacantes diarias</label>
              <input
                id="cargo-cupo"
                type="number"
                min={0}
                max={120}
                required
                value={c.cupo}
                onChange={(e) => setC({ ...c, cupo: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="info-line">
            <Compass size={18} />
            <span>
              La búsqueda incluye las denominaciones que definas a continuación.
            </span>
          </div>
          <button
            className="button secondary full"
            type="button"
            disabled={c.nombre.trim().length < 2 || busy}
            onClick={expandir}
          >
            {busy ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <Workflow size={16} />
            )}
            Buscar denominaciones afines
          </button>
          {nota && <p className="helper note">{nota}</p>}
          <TagInput
            label="Denominaciones principales"
            values={c.terminos_exactos}
            onChange={(v) => setC({ ...c, terminos_exactos: v })}
          />
          <TagInput
            label="Cargos afines"
            values={c.terminos_similares}
            onChange={(v) => setC({ ...c, terminos_similares: v })}
          />
          <TagInput
            label="Cargos cercanos (solo si faltan vacantes)"
            values={c.terminos_cercanos || []}
            onChange={(v) => setC({ ...c, terminos_cercanos: v })}
          />
          <p className="helper">
            Si un cliente no llega a 5 vacantes en el día, se completan primero
            con avisos que no dicen años o inglés y luego con estos oficios
            vecinos. En «Vacantes» aparecen marcadas como «Ampliada».
          </p>
          <TagInput
            label="Excluir estos términos"
            values={c.terminos_excluidos}
            onChange={(v) => setC({ ...c, terminos_excluidos: v })}
          />
          <p className="helper">
            No dependes de un listado cerrado. Puedes crear cualquier cargo y
            revisar sus términos sin modificar código.
          </p>
        </fieldset>
        <div className="dialog-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={busy} className="button primary">
            {cargo ? "Aplicar cambios" : "Añadir cargo"}
            <Check size={15} />
          </button>
        </div>
      </form>
    </Dialog>
  );
}
type EstadoPrevia = "listo" | "cargando" | "incompleto" | "error";

// Estima con el catálogo ya guardado cuántas vacantes cumplirían el borrador. Espera a que se deje de editar.
function useVistaPrevia(config: Configuracion | null) {
  const [datos, setDatos] = useState<VistaPrevia | null>(null);
  const [estado, setEstado] = useState<EstadoPrevia>("cargando");
  const turno = useRef(0);
  const cuerpo = config ? JSON.stringify({ configuracion: config }) : "";
  useEffect(() => {
    if (!cuerpo) return;
    const mio = ++turno.current;
    setEstado("cargando");
    const espera = setTimeout(async () => {
      try {
        const r = await api<VistaPrevia>("/vista-previa", {
          method: "POST",
          body: cuerpo,
        });
        if (mio !== turno.current) return;
        if (r.incompleto) {
          setEstado("incompleto");
        } else {
          setDatos(r);
          setEstado("listo");
        }
      } catch (e) {
        if (mio === turno.current)
          setEstado(
            e instanceof ErrorAPI && e.status === 422 ? "incompleto" : "error",
          );
      }
    }, 450);
    return () => clearTimeout(espera);
  }, [cuerpo]);
  return { datos, estado };
}

const ajustesSinDato: Record<string, Partial<Perfil>> = {
  "experiencia no informada": { aceptar_experiencia_sin_dato: true },
  "inglés requerido sin confirmar": { aceptar_ingles_sin_dato: true },
  "experiencia e inglés no informados": {
    aceptar_experiencia_sin_dato: true,
    aceptar_ingles_sin_dato: true,
  },
  "idioma del aviso diferente": { idiomas: ["es", "en"] },
};

function PreviewPerfil({
  info,
  estado,
  onAjustar,
}: {
  info?: EstimacionPerfil;
  estado: EstadoPrevia;
  onAjustar: (cambio: Partial<Perfil>) => void;
}) {
  if (estado === "incompleto")
    return (
      <p className="preview muted-preview" role="status">
        Completa el perfil para ver cuántas vacantes lo cumplen.
      </p>
    );
  if (!info)
    return (
      <p className="preview muted-preview" role="status">
        {estado === "error" ? (
          "No se pudo estimar en este momento."
        ) : estado === "listo" ? (
          "Sin estimación para este perfil."
        ) : (
          <>
            <Loader2 size={13} className="spin" /> Calculando vacantes
            disponibles…
          </>
        )}
      </p>
    );
  return (
    <div
      className={
        "preview" +
        (info.compatibles === 0 ? " warn" : "") +
        (estado === "cargando" ? " stale" : "")
      }
      role="status"
      aria-live="polite"
    >
      <p className="preview-main">
        <Target size={15} />
        <span>
          <strong>≈ {info.compatibles}</strong>{" "}
          {info.compatibles === 1
            ? "vacante guardada aún no entregada"
            : "vacantes guardadas aún no entregadas"}{" "}
          cumple{info.compatibles === 1 ? "" : "n"} este perfil
          <span className="preview-sub">
            {" "}
            · {info.del_cargo} del cargo en el catálogo
            {info.compatibles < 5 && !!info.ampliables && (
              <> · +{info.ampliables} con ampliación hasta llegar a 5</>
            )}
          </span>
        </span>
      </p>
      {info.limitantes.length > 0 && (
        <ul className="preview-tips">
          {info.limitantes.slice(0, 2).map((l) => (
            <li key={l.motivo}>
              <span>
                {l.sugerencia}: <strong>+{l.vacantes}</strong>
              </span>
              {ajustesSinDato[l.motivo] && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => onAjustar(ajustesSinDato[l.motivo])}
                >
                  Aplicar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EnVivo({
  config,
  perfilId,
  onAjustar,
}: {
  config: Configuracion;
  perfilId: string;
  onAjustar: (cambio: Partial<Perfil>) => void;
}) {
  const [r, setR] = useState<EstimacionEnVivo | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  async function estimar() {
    setCargando(true);
    setError("");
    try {
      const x = await api<EstimacionEnVivo>("/estimacion-en-vivo", {
        method: "POST",
        body: JSON.stringify({ configuracion: config, perfil_id: perfilId }),
      });
      if (x.incompleto) setError("Completa el perfil antes de buscar.");
      else if (x.ocupado || x.espera || x.error)
        setError(x.nota || x.error || "");
      else setR(x);
    } catch {
      setError("No se pudo buscar en este momento. Inténtalo más tarde.");
    } finally {
      setCargando(false);
    }
  }
  const fallo =
    r?.fuentes &&
    Object.entries(r.fuentes)
      .filter(([, f]) => f.error || (f.busquedas && f.fallidas === f.busquedas))
      .map(([n]) => n);
  return (
    <div className="live">
      <button
        type="button"
        className="button secondary small"
        disabled={cargando}
        onClick={estimar}
      >
        {cargando ? (
          <Loader2 size={14} className="spin" />
        ) : (
          <Search size={14} />
        )}
        {cargando
          ? "Buscando en LinkedIn y Get on Board… (hasta 30 s)"
          : r
            ? "Repetir búsqueda en vivo"
            : "Estimar con búsqueda en vivo"}
      </button>
      {error && (
        <p className="live-note" role="status">
          {error}
        </p>
      )}
      {r && !cargando && (
        <div className="live-result" role="status" aria-live="polite">
          <p className="preview-main">
            <Target size={15} />
            <span>
              <strong>≈ {r.compatibles}</strong>{" "}
              {r.compatibles === 1
                ? "encontrada ahora en las fuentes cumple"
                : "encontradas ahora en las fuentes cumplen"}{" "}
              este perfil
              <span className="preview-sub">
                {" "}
                · {r.nuevas} aún no guardadas · {r.del_cargo} del cargo en{" "}
                {r.avisos} avisos revisados
                {r.ya_entregadas ? ` · ${r.ya_entregadas} ya entregadas` : ""}
              </span>
            </span>
          </p>
          {!!r.limitantes?.length && (
            <ul className="preview-tips">
              {r.limitantes.slice(0, 2).map((l) => (
                <li key={l.motivo}>
                  <span>
                    {l.sugerencia}: <strong>+{l.vacantes}</strong>
                  </span>
                  {ajustesSinDato[l.motivo] && (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => onAjustar(ajustesSinDato[l.motivo])}
                    >
                      Aplicar
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!!fallo?.length && (
            <p className="live-note">
              {fallo.join(" y ")} no respondió esta vez; el número puede quedar
              corto.
            </p>
          )}
          <p className="live-note">{r.nota}</p>
        </div>
      )}
    </div>
  );
}

const textoEstadoCargo: Record<EstimacionCargo["estado"], string> = {
  alcanza: "alcanza para el cupo",
  justo: "puede quedar corto",
  insuficiente: "probable faltante",
  sin_cupo: "sin cupo asignado",
};

function PreviewCargo({
  info,
  estado,
}: {
  info?: EstimacionCargo;
  estado: EstadoPrevia;
}) {
  if (!info || estado === "incompleto") return null;
  return (
    <div
      className={
        "preview-chip " + info.estado + (estado === "cargando" ? " stale" : "")
      }
      title="Vacantes ya guardadas, aún no entregadas, que cumplen los filtros de algún perfil de este cargo."
    >
      <Target size={12} />≈ {info.disponibles} guardadas sin entregar ·{" "}
      {textoEstadoCargo[info.estado]}
      {!!info.solapes?.length && (
        <span className="overlap">
          {" "}
          · comparte{" "}
          {info.solapes
            .map((s) => s.vacantes + " vacantes con «" + s.cargo + "»")
            .join(", ")}
          : se reparten por turnos según lo que le falta a cada uno. Mejor un
          solo cargo con varios perfiles.
        </span>
      )}
    </div>
  );
}

const estadosMensaje: Record<Borrador["estado"], string> = {
  pendiente: "Por enviar",
  abierto: "Abierto en WhatsApp",
  enviado: "Enviado",
  descartado: "Descartado",
};

// Contrato v19: regiones que se eligen de una vez (el servidor las convierte en sus países).
const REGIONES: { codigo: string; nombre: string }[] = [
  { codigo: "LATAM", nombre: "LATAM (todos los países)" },
  { codigo: "SUD_CENTRO_MX", nombre: "Sudamérica, Centroamérica y México" },
  { codigo: "SUDAMERICA", nombre: "Sudamérica" },
  { codigo: "CENTROAMERICA", nombre: "Centroamérica" },
  { codigo: "LATAM_ES", nombre: "LATAM y España" },
];
const ETIQUETA_SUGERIDA: Record<string, string> = {
  sirve: "sirve",
  otro_pais: "solo para otro país",
  no_sirve: "no sirve",
};
// Contrato v16: vacantes que le servirían a un cliente pero cuyo país no se pudo confirmar solo. Un clic por vacante.
function PorConfirmar({
  paises,
  notify,
  onCambio,
}: {
  paises: Sesion["paises"];
  notify: (s: string, error?: boolean) => void;
  onCambio: (total: number) => void;
}) {
  const [datos, setDatos] = useState<Revisiones | null>(null);
  const [elegido, setElegido] = useState<Record<string, string>>({});
  const [iguales, setIguales] = useState<Record<string, boolean>>({});
  const [ocupado, setOcupado] = useState("");
  async function cargar() {
    try {
      const r = await api<Revisiones>("/revisiones");
      setDatos(r);
      onCambio(r.total);
    } catch (e) {
      notify((e as Error).message, true);
      setDatos({ pendientes: [], total: 0, ayudan_faltantes: 0 });
    }
  }
  useEffect(() => {
    cargar();
  }, []);
  const nombre = (codigo: string) =>
    paises.find((p) => p.codigo === codigo)?.nombre ||
    REGIONES.find((r) => r.codigo === codigo)?.nombre ||
    codigo;
  async function decidir(r: Revision, decision: string, codigos?: string[]) {
    const pais = elegido[r.vacante_id] ?? r.sugerencia[0] ?? "";
    if (decision === "sirve" && !pais && !codigos?.length) {
      notify("Elige el país antes de confirmar.", true);
      return;
    }
    setOcupado(r.vacante_id);
    try {
      const res = await api<{ asignadas: number; iguales: number }>(
        "/revisiones/" + encodeURIComponent(r.vacante_id),
        {
          method: "POST",
          body: JSON.stringify({
            decision,
            paises:
              decision === "sirve" ? (codigos?.length ? codigos : [pais]) : [],
            aplicar_a_iguales: Boolean(iguales[r.vacante_id]),
          }),
        },
      );
      const extra = res.iguales
        ? ` También se decidieron ${res.iguales} con la misma ubicación.`
        : "";
      notify(
        decision === "sirve"
          ? `Confirmada: se asignó a ${res.asignadas} cliente(s).${extra}`
          : decision === "saltar"
            ? "Apartada por ahora."
            : `Descartada.${extra}`,
      );
      await cargar();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado("");
    }
  }
  async function subir(archivo: File) {
    setOcupado("csv");
    try {
      const contenido = await archivo.text();
      const r = await api<{
        aplicadas: number;
        omitidas: number;
        errores: { fila: number; motivo: string }[];
      }>("/revisiones/csv", {
        method: "POST",
        body: JSON.stringify({ contenido }),
      });
      notify(
        `Revisión aplicada: ${r.aplicadas} decididas, ${r.omitidas} sin llenar` +
          (r.errores.length
            ? `. Revisar fila ${r.errores
                .slice(0, 3)
                .map((e) => e.fila)
                .join(", ")}: ${r.errores[0].motivo}`
            : "."),
        r.errores.length > 0,
      );
      await cargar();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado("");
    }
  }
  type ResultadoCarga = {
    por_confirmar: number;
    agregadas?: number;
    resueltas_por_regla?: number;
    leidas_del_catalogo?: number;
    fuera_por_idioma?: number;
    ya_claras?: number;
    diagnostico?: {
      catalogo?: number | null;
      por_confirmar?: number | null;
      confianza_baja?: number | null;
    };
  };
  type EstadoCarga = {
    estado: "inactivo" | "en_curso" | "listo" | "error";
    avance: { leidas: number; total: number };
    resultado: ResultadoCarga | null;
    error: string;
  };
  const [avanceCarga, setAvanceCarga] = useState("");
  function avisarResultado(r: ResultadoCarga) {
    if (!r.por_confirmar) {
      notify(
        `No hay dudosas para revisar: el catálogo tiene ${r.leidas_del_catalogo ?? 0} vacantes con país por confirmar` +
          (r.ya_claras ? `, ${r.ya_claras} ya resueltas o cerradas` : "") +
          (r.fuera_por_idioma
            ? ` y ${r.fuera_por_idioma} quedan fuera por idioma`
            : "") +
          "." +
          (r.diagnostico && Object.keys(r.diagnostico).length
            ? ` Conteo directo en la base: ${r.diagnostico.catalogo ?? "?"} vacantes en total, ${r.diagnostico.por_confirmar ?? "?"} por confirmar, ${r.diagnostico.confianza_baja ?? "?"} con país dudoso.`
            : ""),
        true,
      );
    } else {
      notify(
        `Bandeja lista: ${r.por_confirmar} por confirmar` +
          (r.agregadas ? ` (${r.agregadas} nuevas)` : "") +
          (r.resueltas_por_regla
            ? `, ${r.resueltas_por_regla} resueltas solas por reglas`
            : "") +
          ".",
      );
    }
  }
  // Contrato v19: la carga corre en segundo plano en el servidor; aquí solo se consulta su avance.
  async function esperarCarga() {
    setOcupado("todas");
    try {
      for (;;) {
        const e = await api<EstadoCarga>("/revisiones/cargar");
        if (e.estado === "en_curso") {
          setAvanceCarga(
            e.avance.total
              ? `Cargando… ${e.avance.leidas} de ${e.avance.total}`
              : "Cargando…",
          );
          await new Promise((listo) => setTimeout(listo, 2000));
          continue;
        }
        if (e.estado === "error") notify(e.error, true);
        if (e.estado === "listo" && e.resultado) avisarResultado(e.resultado);
        break;
      }
      await cargar();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado("");
      setAvanceCarga("");
    }
  }
  async function cargarTodas() {
    setOcupado("todas");
    try {
      await api<EstadoCarga>("/revisiones/cargar", { method: "POST" });
    } catch (e) {
      notify((e as Error).message, true);
      setOcupado("");
      return;
    }
    await esperarCarga();
  }
  useEffect(() => {
    // Si una carga sigue corriendo (por ejemplo, tras recargar la página), retomar su avance.
    api<EstadoCarga>("/revisiones/cargar")
      .then((e) => {
        if (e.estado === "en_curso") esperarCarga();
      })
      .catch(() => undefined);
  }, []);
  const masiva = (
    <div className="revision-masiva">
      <button
        className="button secondary"
        onClick={cargarTodas}
        disabled={ocupado === "todas"}
      >
        <RefreshCw size={15} />
        {ocupado === "todas"
          ? avanceCarga || "Cargando…"
          : "Cargar todas las dudosas de la base"}
      </button>
      <a className="button secondary" href="/api/revisiones.csv" download>
        <ArrowDownToLine size={15} />
        Descargar todas (CSV)
      </a>
      <label className="button secondary">
        <Upload size={15} />
        Subir revisión
        <input
          type="file"
          accept=".csv,text/csv"
          className="visually-hidden"
          disabled={ocupado === "csv"}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) subir(f);
            e.target.value = "";
          }}
        />
      </label>
    </div>
  );
  if (!datos) return <div className="card loading-card">Cargando…</div>;
  if (!datos.pendientes.length)
    return (
      <Empty
        icon={CheckCheck}
        title="Todo al día"
        texto="No hay vacantes por confirmar en la bandeja. La búsqueda de la noche trae las que ayudan a tus clientes; para depurar toda la base ahora, carga todas las dudosas."
        action={ocupado === "todas" ? undefined : cargarTodas}
        label="Cargar todas las dudosas de la base"
      />
    );
  return (
    <section className="revisiones">
      {masiva}
      <p className="helper revision-ayuda">
        {datos.en_espera && datos.en_espera > datos.total
          ? `Mostrando las ${datos.total} más útiles de ${datos.en_espera}. Para revisar muchas de una vez, descarga el CSV, llena «decision» y «pais», y súbelo.`
          : `${datos.total} por confirmar`}
        {datos.ayudan_faltantes
          ? ` · ${datos.ayudan_faltantes} ayudan a clientes con menos de 5 vacantes`
          : ""}
        . Atajos con la tarjeta seleccionada: Enter acepta la sugerencia · 1
        Sirve · 2 Otro país · 3 No sirve · 4 Saltar.
      </p>
      <p className="revision-pregunta">
        <strong>Una sola pregunta:</strong> ¿puede postularse alguien que vive
        en LATAM o en España? Cada tarjeta trae la respuesta sugerida y por qué;
        corrige solo si la ves mal.
      </p>
      {datos.pendientes.map((r) => {
        const pais = elegido[r.vacante_id] ?? r.sugerencia[0] ?? "";
        return (
          <article
            className="card revision"
            key={r.vacante_id}
            tabIndex={0}
            aria-label={`${r.titulo} en ${r.empresa}`}
            onKeyDown={(e) => {
              if ((e.target as HTMLElement).tagName === "SELECT") return;
              if (
                e.key === "Enter" &&
                e.target === e.currentTarget &&
                r.sugerida &&
                !ocupado
              ) {
                e.preventDefault();
                decidir(r, r.sugerida, r.paises_sugeridos);
                return;
              }
              const accion = {
                "1": "sirve",
                "2": "otro_pais",
                "3": "no_sirve",
                "4": "saltar",
              }[e.key];
              if (accion && !ocupado) {
                e.preventDefault();
                decidir(r, accion);
              }
            }}
          >
            <div className="vacancy-top">
              <span className="company-avatar">{iniciales(r.empresa)}</span>
              <div>
                <span className="company-name">{r.empresa}</span>
                <h3>{r.titulo}</h3>
              </div>
              {r.ayuda_faltantes && (
                <span className="pill amber">
                  Ayuda a clientes con faltantes
                </span>
              )}
            </div>
            {r.por_que && (
              <div className={"revision-sugerencia " + (r.sugerida || "leer")}>
                <p>
                  <strong>
                    {r.sugerida
                      ? `Sugerencia: ${ETIQUETA_SUGERIDA[r.sugerida]}`
                      : "Para leer"}
                  </strong>{" "}
                  — {r.por_que}
                </p>
                {r.sugerida && (
                  <button
                    type="button"
                    className="button primary"
                    disabled={ocupado === r.vacante_id}
                    onClick={() =>
                      decidir(r, r.sugerida as string, r.paises_sugeridos)
                    }
                  >
                    <CheckCheck size={15} />
                    Aceptar sugerencia
                  </button>
                )}
              </div>
            )}
            <p className="revision-lugar">
              <MapPin size={14} />
              Ubicación del aviso: <strong>{r.ubicacion || "sin dato"}</strong>
            </p>
            {(r.frase ?? r.pista) && (
              <blockquote className="revision-pista">
                {r.frase ?? r.pista}
              </blockquote>
            )}
            <p className="helper">
              Le serviría a: {r.clientes.join(", ") || "—"}
            </p>
            <div className="revision-acciones">
              <label className="revision-pais">
                País
                <select
                  aria-label={`País de ${r.titulo} en ${r.empresa}`}
                  value={pais}
                  onChange={(e) =>
                    setElegido({ ...elegido, [r.vacante_id]: e.target.value })
                  }
                >
                  <option value="">Elige…</option>
                  <optgroup label="Regiones">
                    {REGIONES.map((g) => (
                      <option key={g.codigo} value={g.codigo}>
                        {g.nombre}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Países">
                    {paises.map((p) => (
                      <option key={p.codigo} value={p.codigo}>
                        {p.nombre}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </label>
              <button
                type="button"
                className={r.sugerida ? "button secondary" : "button primary"}
                disabled={ocupado === r.vacante_id}
                onClick={() => decidir(r, "sirve")}
              >
                <Check size={15} />
                {pais ? `Sirve para ${nombre(pais)}` : "Sirve"}
              </button>
              <button
                type="button"
                className="button secondary"
                disabled={ocupado === r.vacante_id}
                onClick={() => decidir(r, "otro_pais")}
              >
                Solo para otro país
              </button>
              <button
                type="button"
                className="button secondary"
                disabled={ocupado === r.vacante_id}
                onClick={() => decidir(r, "no_sirve")}
              >
                No sirve
              </button>
              <button
                type="button"
                className="text-button"
                disabled={ocupado === r.vacante_id}
                onClick={() => decidir(r, "saltar")}
              >
                Saltar
              </button>
            </div>
            <div className="revision-pie">
              {r.iguales > 0 && (
                <label className="check-line">
                  <input
                    type="checkbox"
                    checked={Boolean(iguales[r.vacante_id])}
                    onChange={(e) =>
                      setIguales({
                        ...iguales,
                        [r.vacante_id]: e.target.checked,
                      })
                    }
                  />
                  Aplicar a las {r.iguales} con esta misma ubicación
                </label>
              )}
              {r.enlace.startsWith("http") && (
                <a
                  href={r.enlace}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-button"
                >
                  Abrir aviso
                  <ExternalLink size={14} />
                </a>
              )}
            </div>
          </article>
        );
      })}
    </section>
  );
}

function Mensajes({
  clientes,
  notify,
}: {
  clientes: Cliente[];
  notify: (s: string, error?: boolean) => void;
}) {
  const [lista, setLista] = useState<Borrador[] | null>(null);
  const [soloPendientes, setSoloPendientes] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  async function cargar() {
    try {
      const r = await api<{ borradores: Borrador[] }>("/borradores");
      setLista(r.borradores);
    } catch (e) {
      notify((e as Error).message, true);
      setLista([]);
    }
  }
  useEffect(() => {
    cargar();
  }, []);
  async function cambiar(b: Borrador, cambios: Partial<Borrador>) {
    try {
      const r = await api<Borrador>("/borradores/" + b.id, {
        method: "PATCH",
        body: JSON.stringify(cambios),
      });
      setLista((l) =>
        (l || []).map((x) => (x.id === b.id ? { ...x, ...r } : x)),
      );
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  async function generar() {
    setOcupado(true);
    try {
      const r = await api<{ generados: number; conservados: number }>(
        "/borradores/generar",
        { method: "POST" },
      );
      notify(
        r.generados
          ? `${r.generados} mensajes preparados.`
          : "No hay vacantes listas nuevas para preparar mensajes.",
      );
      await cargar();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  }
  const nombre = (id: string) =>
    clientes.find((c) => c.id === id)?.nombre || "Cliente";
  const visibles = (lista || []).filter(
    (b) =>
      !soloPendientes || b.estado === "pendiente" || b.estado === "abierto",
  );
  return (
    <section className="card activity mensajes">
      <div className="section-title">
        <h2>Mensajes de hoy</h2>
        <div className="alerts-actions">
          <label className="check-line">
            <input
              type="checkbox"
              checked={soloPendientes}
              onChange={(e) => setSoloPendientes(e.target.checked)}
            />
            Solo pendientes
          </label>
          <button
            type="button"
            className="button secondary"
            disabled={ocupado}
            onClick={generar}
          >
            <RefreshCw size={14} /> Preparar mensajes
          </button>
        </div>
      </div>
      <p className="helper">
        Para que una persona reciba su mensaje, en «Clientes» añade su WhatsApp
        y marca que aceptó recibir vacantes. Nada se envía solo: «Abrir en
        WhatsApp» abre su chat con el mensaje escrito para que lo revises y lo
        envíes.
      </p>
      {lista === null ? (
        <p className="muted">
          <Loader2 size={14} className="spin" /> Cargando mensajes…
        </p>
      ) : !visibles.length ? (
        <Empty
          icon={MessageCircle}
          title="No hay mensajes por enviar"
          texto="Los mensajes se preparan solos cada mañana tras la búsqueda. También puedes pulsar «Preparar mensajes»."
        />
      ) : (
        visibles.map((b) => (
          <article className="mensaje" key={b.id}>
            <div className="mensaje-top">
              <div>
                <h3>{nombre(b.cliente_id)}</h3>
                <p className="muted">
                  {b.cargos.join(" · ")} · {b.vacantes.length}{" "}
                  {b.vacantes.length === 1 ? "vacante" : "vacantes"}
                  {b.pocas && " · hoy hubo menos de 5"}
                </p>
              </div>
              <span
                className={
                  "pill " + (b.estado === "enviado" ? "green" : "amber")
                }
              >
                {estadosMensaje[b.estado]}
              </span>
            </div>
            <label className="sr-only" htmlFor={"texto-" + b.id}>
              Mensaje para {nombre(b.cliente_id)}
            </label>
            <textarea
              id={"texto-" + b.id}
              defaultValue={b.texto}
              rows={8}
              onBlur={(e) =>
                e.target.value !== b.texto &&
                cambiar(b, { texto: e.target.value })
              }
            />
            <div className="alerts-actions">
              <button
                type="button"
                className="text-button"
                onClick={() => cambiar(b, { estado: "descartado" })}
              >
                Descartar
              </button>
              <button
                type="button"
                className="button secondary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(b.texto);
                    notify("Mensaje copiado.");
                  } catch {
                    notify("No se pudo copiar; selecciona el texto.", true);
                  }
                }}
              >
                <Copy size={14} /> Copiar
              </button>
              <button
                type="button"
                className="button secondary"
                onClick={() => cambiar(b, { estado: "enviado" })}
              >
                <Check size={14} /> Marcar como enviado
              </button>
              {b.enlace && (
                <a
                  className="button primary"
                  href={b.enlace}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() =>
                    b.estado === "pendiente" &&
                    cambiar(b, { estado: "abierto" })
                  }
                >
                  <MessageCircle size={14} /> Abrir en WhatsApp
                </a>
              )}
            </div>
          </article>
        ))
      )}
    </section>
  );
}

type AjustesAlertas = {
  destinatarios: string[];
  tipos: string[];
  envio_configurado?: boolean;
};
const tiposAlerta: [string, string][] = [
  ["exito", "Búsqueda completa"],
  ["pocas_vacantes", "Pocas vacantes"],
  ["fallo", "Fallos"],
];

// Contrato v17: reglas de ubicación. Las «aprendidas» las crea el código solo a partir de tus decisiones.
function ReglasAprendidas({
  notify,
}: {
  notify: (s: string, error?: boolean) => void;
}) {
  const [reglas, setReglas] = useState<Regla[] | null>(null);
  async function cargar() {
    try {
      setReglas((await api<{ reglas: Regla[] }>("/reglas")).reglas);
    } catch (e) {
      notify((e as Error).message, true);
      setReglas([]);
    }
  }
  useEffect(() => {
    cargar();
  }, []);
  async function cambiar(r: Regla) {
    try {
      await api("/reglas/estado", {
        method: "POST",
        body: JSON.stringify({ texto: r.texto, activa: !r.activa }),
      });
      notify(r.activa ? "Regla desactivada." : "Regla activada.");
      await cargar();
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  return (
    <section className="card activity reglas">
      <div className="section-title">
        <h2>Reglas de ubicación</h2>
      </div>
      <p className="helper">
        Las del operador salen de «Aplicar a las iguales». Las aprendidas las
        crea el sistema solo, sin IA, cuando dos o más de tus decisiones
        coinciden en un lugar; si una decisión nueva las contradice, se
        desactivan solas. Solo resuelven ubicaciones dudosas: nunca cambian un
        país ya reconocido.
      </p>
      {!reglas ? (
        <p className="helper">Cargando…</p>
      ) : !reglas.length ? (
        <p className="helper">
          Todavía no hay reglas. Aparecerán cuando confirmes vacantes en «Por
          confirmar».
        </p>
      ) : (
        <ul className="reglas-lista">
          {reglas.map((r) => (
            <li key={r.texto} className={r.activa ? "" : "inactiva"}>
              <div>
                <strong>«{r.texto}»</strong> → {r.resultado}
                <span className="helper">
                  {" "}
                  · {r.origen === "aprendida" ? "aprendida" : "del operador"} ·
                  usada {r.usos} {r.usos === 1 ? "vez" : "veces"}
                  {r.conflictos ? ` · ${r.conflictos} en conflicto` : ""}
                  {r.activa ? "" : " · desactivada"}
                </span>
              </div>
              <button
                type="button"
                className="text-button"
                onClick={() => cambiar(r)}
              >
                {r.activa ? "Desactivar" : "Activar"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AvisosCorreo({
  notify,
}: {
  notify: (s: string, error?: boolean) => void;
}) {
  const [a, setA] = useState<AjustesAlertas | null>(null);
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => {
    api<AjustesAlertas>("/ajustes/alertas")
      .then((r) => {
        setA(r);
        setTexto(r.destinatarios.join(", "));
      })
      .catch(() => setA({ destinatarios: [], tipos: [] }));
  }, []);
  if (!a) return null;
  async function guardar() {
    setOcupado(true);
    try {
      const r = await api<AjustesAlertas>("/ajustes/alertas", {
        method: "PUT",
        body: JSON.stringify({
          destinatarios: texto
            .split(/[,;\s]+/)
            .map((x) => x.trim())
            .filter(Boolean),
          tipos: a!.tipos,
        }),
      });
      setA({ ...a!, ...r });
      setTexto(r.destinatarios.join(", "));
      notify("Avisos por correo guardados.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  }
  async function probar() {
    setOcupado(true);
    try {
      const r = await api<{ nota: string }>("/alertas/prueba", {
        method: "POST",
      });
      notify(r.nota);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  }
  return (
    <section className="card activity alerts">
      <div className="section-title">
        <h2>
          <Mail size={18} /> Avisos por correo
        </h2>
      </div>
      <p className="helper">
        Recibe un correo cuando la búsqueda se completa, cuando quedan pocas
        vacantes (tras la pasada de la mañana) o si algo falla. No incluye datos
        de tus clientes.
      </p>
      <div className="field">
        <label htmlFor="alertas-correos">Correos que reciben los avisos</label>
        <input
          id="alertas-correos"
          type="text"
          inputMode="email"
          autoComplete="email"
          placeholder="nombre@example.com, otra@example.com"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
      <fieldset className="check-line">
        <legend className="sr-only">Qué avisos enviar</legend>
        {tiposAlerta.map(([v, t]) => (
          <label key={v}>
            <input
              type="checkbox"
              checked={a.tipos.includes(v)}
              onChange={(e) =>
                setA({
                  ...a,
                  tipos: e.target.checked
                    ? [...a.tipos, v]
                    : a.tipos.filter((x) => x !== v),
                })
              }
            />
            {t}
          </label>
        ))}
      </fieldset>
      {a.envio_configurado === false && (
        <p className="form-error">
          Falta configurar el envío (RESEND_API_KEY y ALERTAS_REMITENTE). Los
          correos guardados se usarán en cuanto esté listo.
        </p>
      )}
      <div className="alerts-actions">
        <button
          type="button"
          className="button secondary"
          disabled={ocupado || !a.destinatarios.length}
          onClick={probar}
        >
          Enviar correo de prueba
        </button>
        <button
          type="button"
          className="button primary"
          disabled={ocupado}
          onClick={guardar}
        >
          Guardar avisos
        </button>
      </div>
    </section>
  );
}

const etapasEmbudo: [keyof Embudo, string][] = [
  ["encontradas", "Encontradas"],
  ["con_descripcion", "Con descripción"],
  ["entregables", "País e idioma confirmados"],
  ["nuevas", "Nuevas"],
  ["enlace_comprobado", "Enlace comprobado"],
  ["cumplen_filtros", "Cumplen filtros"],
  ["entregadas", "Entregadas"],
];

function EmbudoCargos({ embudo }: { embudo: Record<string, Embudo> }) {
  return (
    <details className="funnel">
      <summary>Dónde se pierden las vacantes de cada cargo</summary>
      <div className="funnel-table">
        <table>
          <thead>
            <tr>
              <th>Cargo</th>
              {etapasEmbudo.map(([k, t]) => (
                <th key={k}>{t}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(embudo).map(([cargo, e]) => (
              <tr key={cargo}>
                <th scope="row">
                  {cargo}
                  {e.principal_perdida && (
                    <span className="muted">
                      Mayor pérdida: {e.principal_perdida}
                    </span>
                  )}
                </th>
                {etapasEmbudo.map(([k]) => (
                  <td key={k}>
                    {e[k] as number}
                    {k === "entregadas" && e.ampliadas > 0 && (
                      <span className="muted"> ({e.ampliadas} ampliadas)</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function ClienteDialog({
  cliente,
  config,
  paises,
  onClose,
  onSave,
}: {
  cliente: Cliente | null;
  config: Configuracion;
  paises: Sesion["paises"];
  onClose: () => void;
  onSave: (c: Cliente, p: Perfil[]) => void;
}) {
  const [c, setC] = useState<Cliente>(
    cliente ? { ...cliente } : { id: uid(), nombre: "", activo: true },
  );
  // WhatsApp del cliente: se guarda al momento en una tabla privada, fuera de la configuración programada.
  const vacioContacto: Contacto = {
    telefono: "",
    nombre_saludo: "",
    consentimiento: false,
  };
  const [ct, setCt] = useState<Contacto>(vacioContacto);
  const [teniaContacto, setTeniaContacto] = useState(false);
  useEffect(() => {
    if (!cliente) return;
    api<Record<string, Contacto>>("/contactos")
      .then((r) => {
        if (r[cliente.id]) {
          setCt(r[cliente.id]);
          setTeniaContacto(true);
        }
      })
      .catch(() => undefined);
  }, [cliente]);
  const [ps, setPs] = useState<Perfil[]>(
    cliente
      ? structuredClone(
          config.perfiles.filter((p) => p.cliente_id === cliente.id),
        )
      : [],
  );
  const [error, setError] = useState("");
  const cargos = config.cargos.filter((c) => c.activo);
  function patch(id: string, v: Partial<Perfil>) {
    setPs(ps.map((p) => (p.id === id ? { ...p, ...v } : p)));
  }
  const borrador: Configuracion = {
    ...config,
    clientes: [
      ...config.clientes.filter((x) => x.id !== c.id),
      { ...c, nombre: c.nombre.trim() || "Cliente", activo: true },
    ],
    perfiles: [...config.perfiles.filter((p) => p.cliente_id !== c.id), ...ps],
  };
  const previa = useVistaPrevia(borrador);
  return (
    <Dialog
      ancho
      titulo={cliente ? "Editar cliente" : "Nuevo cliente"}
      subtitulo="Define qué oportunidades son útiles para esta persona."
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!ps.length) {
            setError("Añade al menos un perfil de búsqueda.");
            return;
          }
          if (ps.some((p) => !p.modalidades.length || !p.idiomas.length)) {
            setError(
              "Selecciona al menos una modalidad y un idioma por perfil.",
            );
            return;
          }
          if (
            ps.some(
              (p) =>
                p.experiencia_min !== null &&
                p.experiencia_max !== null &&
                p.experiencia_min > p.experiencia_max,
            )
          ) {
            setError("Revisa el rango de experiencia.");
            return;
          }
          try {
            if (ct.telefono.trim()) {
              await api("/contactos/" + c.id, {
                method: "PUT",
                body: JSON.stringify(ct),
              });
            } else if (teniaContacto) {
              await api("/contactos/" + c.id, { method: "DELETE" });
            }
          } catch (err) {
            setError((err as Error).message);
            return;
          }
          onSave(c, ps);
        }}
      >
        <div className="field">
          <label htmlFor="cliente-nombre">
            Nombre o referencia del cliente
          </label>
          <input
            id="cliente-nombre"
            autoFocus
            required
            maxLength={100}
            value={c.nombre}
            placeholder="Nombre para identificar a tu cliente"
            onChange={(e) => setC({ ...c, nombre: e.target.value })}
          />
        </div>
        <fieldset className="whatsapp-contacto">
          <legend>WhatsApp (opcional)</legend>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="cliente-telefono">
                Número con código de país
              </label>
              <input
                id="cliente-telefono"
                type="tel"
                inputMode="tel"
                autoComplete="off"
                placeholder="+57 300 123 4567"
                value={ct.telefono}
                onChange={(e) => setCt({ ...ct, telefono: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="cliente-saludo">Nombre para saludar</label>
              <input
                id="cliente-saludo"
                maxLength={60}
                placeholder="Ana"
                value={ct.nombre_saludo}
                onChange={(e) =>
                  setCt({ ...ct, nombre_saludo: e.target.value })
                }
              />
            </div>
          </div>
          <label className="check-line">
            <input
              type="checkbox"
              checked={ct.consentimiento}
              onChange={(e) =>
                setCt({ ...ct, consentimiento: e.target.checked })
              }
            />
            Aceptó recibir vacantes por WhatsApp
          </label>
          <p className="field-help">
            Con número y aceptación, cada mañana tendrás su mensaje listo en
            «Mensajes». Nada se envía solo.
          </p>
        </fieldset>
        <div className="section-title">
          <h3>Perfiles de búsqueda</h3>
          <span className="muted">
            {ps.length} {ps.length === 1 ? "perfil" : "perfiles"}
          </span>
        </div>
        {ps.map((p, i) => (
          <section className="profile-editor" key={p.id}>
            <div className="profile-heading">
              <span className="tiny-kicker">PERFIL {i + 1}</span>
              <button
                type="button"
                className="text-button danger"
                onClick={() => setPs(ps.filter((x) => x.id !== p.id))}
              >
                Quitar perfil
              </button>
            </div>
            <div className="form-grid">
              <div className="field">
                <label>Cargo</label>
                <select
                  aria-label={"Cargo del perfil " + (i + 1)}
                  value={p.cargo_id}
                  onChange={(e) => patch(p.id, { cargo_id: e.target.value })}
                >
                  {cargos.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor={"vive-" + p.id}>¿En qué país vive?</label>
                <select
                  id={"vive-" + p.id}
                  aria-label={"País de residencia del perfil " + (i + 1)}
                  value={p.vive_en}
                  onChange={(e) =>
                    patch(p.id, {
                      vive_en: e.target.value,
                      paises_presenciales_extra:
                        p.paises_presenciales_extra.filter(
                          (x) => x !== e.target.value,
                        ),
                    })
                  }
                >
                  {paises.map((pais) => (
                    <option key={pais.codigo} value={pais.codigo}>
                      {pais.nombre}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <fieldset className="field plain">
              <legend>¿Qué modalidades acepta?</legend>
              <div className="check-line">
                {Object.entries(modos).map(([v, t]) => (
                  <label key={v}>
                    <input
                      type="checkbox"
                      aria-label={t + " en el perfil " + (i + 1)}
                      checked={p.modalidades.includes(v)}
                      onChange={(e) =>
                        patch(p.id, {
                          modalidades: e.target.checked
                            ? [...p.modalidades, v]
                            : p.modalidades.filter((x) => x !== v),
                        })
                      }
                    />
                    {t}
                  </label>
                ))}
              </div>
              <p className="field-help">
                {p.modalidades.includes("remoto")
                  ? "Remoto incluye vacantes de LATAM, España o del mundo abiertas a su país. "
                  : ""}
                {p.modalidades.some((m) => m !== "remoto")
                  ? "Híbrido y presencial: solo con oficina en su país o en los que elija abajo."
                  : ""}
              </p>
            </fieldset>
            {p.modalidades.some((m) => m !== "remoto") && (
              <details
                className="field mudanza"
                open={p.paises_presenciales_extra.length > 0}
              >
                <summary>
                  También se mudaría a…{" "}
                  <span className="muted">
                    {p.paises_presenciales_extra.length
                      ? p.paises_presenciales_extra.length +
                        (p.paises_presenciales_extra.length === 1
                          ? " país"
                          : " países")
                      : "opcional"}
                  </span>
                </summary>
                <div className="country-grid">
                  {paises
                    .filter((pais) => pais.codigo !== p.vive_en)
                    .map((pais) => (
                      <label
                        className={
                          "country " +
                          (p.paises_presenciales_extra.includes(pais.codigo)
                            ? "selected"
                            : "")
                        }
                        key={pais.codigo}
                      >
                        <input
                          type="checkbox"
                          checked={p.paises_presenciales_extra.includes(
                            pais.codigo,
                          )}
                          onChange={(e) =>
                            patch(p.id, {
                              paises_presenciales_extra: e.target.checked
                                ? [...p.paises_presenciales_extra, pais.codigo]
                                : p.paises_presenciales_extra.filter(
                                    (x) => x !== pais.codigo,
                                  ),
                            })
                          }
                        />
                        {pais.nombre}
                      </label>
                    ))}
                </div>
              </details>
            )}
            <div className="form-grid">
              <div className="field">
                <label>Antigüedad máxima de publicación</label>
                <select
                  aria-label={"Antigüedad del perfil " + (i + 1)}
                  value={p.antiguedad_dias}
                  onChange={(e) =>
                    patch(p.id, { antiguedad_dias: Number(e.target.value) })
                  }
                >
                  {[1, 3, 7, 14, 21, 30].map((n) => (
                    <option key={n} value={n}>
                      {n} {n === 1 ? "día" : "días"}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Idioma del aviso</label>
                <div className="check-line">
                  {[
                    ["es", "Español"],
                    ["en", "Inglés"],
                  ].map(([code, label]) => (
                    <label key={code}>
                      <input
                        type="checkbox"
                        checked={p.idiomas.includes(code)}
                        onChange={(e) =>
                          patch(p.id, {
                            idiomas: e.target.checked
                              ? [...p.idiomas, code]
                              : p.idiomas.filter((x) => x !== code),
                          })
                        }
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="form-grid three">
              <div className="field">
                <label>Experiencia mínima exigida</label>
                <input
                  aria-label={"Experiencia mínima del perfil " + (i + 1)}
                  type="number"
                  min={0}
                  max={40}
                  placeholder="Sin mínimo"
                  value={p.experiencia_min ?? ""}
                  onChange={(e) =>
                    patch(p.id, {
                      experiencia_min:
                        e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="field">
                <label>Experiencia máxima exigida</label>
                <input
                  aria-label={"Experiencia máxima del perfil " + (i + 1)}
                  type="number"
                  min={0}
                  max={40}
                  placeholder="Sin máximo"
                  value={p.experiencia_max ?? ""}
                  onChange={(e) =>
                    patch(p.id, {
                      experiencia_max:
                        e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="field">
                <label>Inglés requerido: hasta</label>
                <select
                  aria-label={"Inglés del perfil " + (i + 1)}
                  value={p.ingles_maximo}
                  onChange={(e) =>
                    patch(p.id, { ingles_maximo: e.target.value })
                  }
                >
                  <option value="sin_filtro">Sin filtro</option>
                  {["A1", "A2", "B1", "B2", "C1", "C2", "native"].map((n) => (
                    <option value={n} key={n}>
                      {n === "native" ? "Nativo" : n}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="helper">
              El rango filtra los años mínimos que exige la vacante. El inglés
              requerido es independiente del idioma en que está escrito el
              aviso.
            </p>
            <div className="missing-options">
              <label>
                <input
                  type="checkbox"
                  checked={p.aceptar_experiencia_sin_dato}
                  onChange={(e) =>
                    patch(p.id, {
                      aceptar_experiencia_sin_dato: e.target.checked,
                    })
                  }
                />
                Admitir experiencia no informada
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={p.aceptar_ingles_sin_dato}
                  onChange={(e) =>
                    patch(p.id, { aceptar_ingles_sin_dato: e.target.checked })
                  }
                />
                Admitir inglés no informado
              </label>
            </div>
            <PreviewPerfil
              info={previa.datos?.perfiles?.[p.id]}
              estado={previa.estado}
              onAjustar={(cambio) => patch(p.id, cambio)}
            />
            <EnVivo
              config={borrador}
              perfilId={p.id}
              onAjustar={(cambio) => patch(p.id, cambio)}
            />
          </section>
        ))}
        <button
          type="button"
          disabled={!cargos.length}
          className="button secondary full dashed"
          onClick={() => setPs([...ps, perfilNuevo(c.id, cargos[0].id)])}
        >
          <Plus size={16} />
          Añadir perfil de búsqueda
        </button>
        {!cargos.length && (
          <p className="helper">Primero añade un cargo en «Cargos y cupos».</p>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary">
            {cliente ? "Aplicar cambios" : "Añadir cliente"}
            <Check size={15} />
          </button>
        </div>
      </form>
    </Dialog>
  );
}
function App() {
  const [sesion, setSesion] = useState<Sesion | null>(null),
    [estado, setEstado] = useState<EstadoConfig | null>(null),
    [draft, setDraft] = useState<Configuracion>(vacio),
    [dirty, setDirty] = useState(false),
    [tab, setTab] = useState("Resumen"),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [toast, setToast] = useState<{ texto: string; error: boolean } | null>(
      null,
    ),
    [menu, setMenu] = useState(false),
    [modal, setModal] = useState<
      "cliente" | "cargo" | "publicar" | "archivo" | "whatsapp" | null
    >(null),
    [editCliente, setEditCliente] = useState<Cliente | null>(null),
    [editCargo, setEditCargo] = useState<Cargo | null>(null),
    [archive, setArchive] = useState<{
      tipo: "cliente" | "cargo";
      id: string;
      nombre: string;
    } | null>(null),
    [results, setResults] = useState<Resultados | null>(null),
    [selectedClient, setSelectedClient] = useState(""),
    [resultDate, setResultDate] = useState(""),
    [search, setSearch] = useState(""),
    [runs, setRuns] = useState<Ejecucion[]>([]),
    [mensaje, setMensaje] = useState(""),
    [copiado, setCopiado] = useState(false),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const peticionResultados = useRef(0);
  const [loadingResults, setLoadingResults] = useState(false);
  const [porConfirmar, setPorConfirmar] = useState(0);
  const previaCargos = useVistaPrevia(
    tab === "Cargos y cupos" && sesion?.sesion ? draft : null,
  );
  const total = draft.cargos
      .filter((c) => c.activo)
      .reduce((s, c) => s + c.cupo, 0),
    clientes = draft.clientes.filter((c) => c.activo),
    cargos = draft.cargos.filter((c) => c.activo);
  function notify(texto: string, error = false) {
    setToast({ texto, error });
  }
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), toast.error ? 8000 : 5000);
      return () => clearTimeout(t);
    }
  }, [toast]);
  async function cargar() {
    setLoading(true);
    setError("");
    try {
      const s = await api<Sesion>("/session");
      setSesion(s);
      if (s.sesion) {
        api<Revisiones>("/revisiones")
          .then((r) => setPorConfirmar(r.total))
          .catch(() => setPorConfirmar(0));
        const [c, e] = await Promise.all([
          api<EstadoConfig>("/config"),
          api<Ejecucion[]>("/ejecuciones"),
        ]);
        setEstado(c);
        setDraft(c.borrador);
        setRuns(e);
        setDirty(false);
        setSelectedClient(
          (v) => v || c.borrador.clientes.find((x) => x.activo)?.id || "",
        );
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    cargar();
    const vencer = () => {
      setSesion((s) => (s ? { ...s, sesion: false } : s));
      setError("Tu sesión venció. Inicia sesión otra vez.");
      setPassword("");
    };
    window.addEventListener("sesion-vencida", vencer);
    return () => window.removeEventListener("sesion-vencida", vencer);
  }, []);
  useEffect(() => {
    const alerta = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", alerta);
    return () => window.removeEventListener("beforeunload", alerta);
  }, [dirty]);
  async function cargarResultados() {
    const turno = ++peticionResultados.current;
    if (!sesion?.sesion) return;
    setLoadingResults(true);
    setResults(null);
    try {
      const r = await api<Resultados>(
        "/resultados?" +
          new URLSearchParams({
            ...(selectedClient ? { cliente_id: selectedClient } : {}),
            ...(resultDate ? { fecha: resultDate } : {}),
          }),
      );
      if (turno === peticionResultados.current) setResults(r);
    } catch (e) {
      if (turno === peticionResultados.current)
        notify((e as Error).message, true);
    } finally {
      if (turno === peticionResultados.current) setLoadingResults(false);
    }
  }
  useEffect(() => {
    cargarResultados();
  }, [selectedClient, resultDate, sesion?.sesion]);
  function cambiar(v: Configuracion) {
    setDraft(v);
    setDirty(true);
  }
  async function guardar() {
    if (!estado) return null;
    const r = await api<
      Partial<EstadoConfig> & { revision: number; borrador: Configuracion }
    >("/config", {
      method: "PUT",
      body: JSON.stringify({ revision: estado.revision, configuracion: draft }),
    });
    const next = { ...estado, ...r };
    setEstado(next);
    setDraft(next.borrador);
    setDirty(false);
    return next;
  }
  async function guardarClick() {
    setBusy(true);
    try {
      await guardar();
      notify("Borrador guardado. Puedes programarlo para mañana.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function programar() {
    setBusy(true);
    try {
      const e = dirty ? await guardar() : estado;
      if (!e) return;
      const r = await api<{ revision: number; vigente_desde: string }>(
        "/config/publicar",
        { method: "POST", body: JSON.stringify({ revision: e.revision }) },
      );
      setEstado({
        ...e,
        publicada: { ...r, configuracion: structuredClone(e.borrador) },
      });
      setModal(null);
      notify(
        "Configuración programada para el " + fecha(r.vigente_desde) + ".",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function abrirWhatsApp() {
    setBusy(true);
    try {
      const r = await api<{ texto: string; vacantes: number }>(
        "/whatsapp/" +
          selectedClient +
          (resultDate ? "?fecha=" + encodeURIComponent(resultDate) : ""),
      );
      if (!r.texto) {
        notify("No hay vacantes con comprobación vigente para copiar.", true);
        return;
      }
      setMensaje(r.texto);
      setCopiado(false);
      setModal("whatsapp");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function copiar() {
    try {
      await navigator.clipboard.writeText(mensaje);
      setCopiado(true);
      notify("Mensaje copiado. Ya puedes pegarlo en WhatsApp.");
    } catch {
      notify(
        "El navegador bloqueó el portapapeles. Selecciona el mensaje y cópialo manualmente.",
        true,
      );
    }
  }
  function go(t: string) {
    setTab(t);
    setMenu(false);
    setSearch("");
    setToast((x) => (x && !x.error ? null : x)); // un aviso no se arrastra a otra sección
  }
  if (loading)
    return (
      <div className="loading-page">
        <span className="brand-icon">a</span>
        <Loader2 className="spin" />
        <p>Cargando tu espacio de búsqueda…</p>
      </div>
    );
  if (!sesion?.sesion)
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="brand">
            <span className="brand-icon">a</span>adaptia
            <span className="brand-dot">.</span>
          </div>
          <span className="eyebrow">CONTROL DE BÚSQUEDA</span>
          <h1>
            Las oportunidades correctas,
            <br />
            para cada persona.
          </h1>
          <p>Accede al espacio privado de tu empresa.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api("/auth/login", {
                  method: "POST",
                  body: JSON.stringify({ email, password }),
                });
                setPassword("");
                await cargar();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="field">
              <label htmlFor="email">Correo del operador</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="password">Contraseña</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <button className="button primary full" disabled={busy}>
              {busy ? (
                <Loader2 className="spin" size={18} />
              ) : (
                <ArrowRight size={18} />
              )}
              Iniciar sesión
            </button>
          </form>
          <div className="secure-note">
            <ShieldCheck size={15} />
            Acceso exclusivo para el operador
          </div>
        </div>
      </div>
    );
  if (error && !estado)
    return (
      <div className="loading-page">
        <h2>No pudimos cargar el espacio</h2>
        <p>{error}</p>
        <button className="button primary" onClick={cargar}>
          Volver a intentar
        </button>
      </div>
    );
  const profiles = (id: string) =>
    draft.perfiles.filter((p) => p.cliente_id === id && p.activo);
  const clientCount = (id: string) =>
    new Set(
      draft.perfiles
        .filter(
          (p) =>
            p.cargo_id === id &&
            p.activo &&
            clientes.some((c) => c.id === p.cliente_id),
        )
        .map((p) => p.cliente_id),
    ).size;
  const shown =
    results?.vacantes.filter((v) =>
      (v.titulo + " " + v.empresa).toLowerCase().includes(search.toLowerCase()),
    ) || [];
  const nav = [
    { t: "Resumen", i: LayoutDashboard },
    { t: "Clientes", i: Users },
    { t: "Cargos y cupos", i: SlidersHorizontal },
    { t: "Vacantes", i: BriefcaseBusiness },
    { t: "Por confirmar", i: MapPin },
    { t: "Mensajes", i: MessageCircle },
    { t: "Actividad", i: Clock3 },
  ];
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (menu ? "open" : "")}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("Resumen");
          }}
        >
          <span className="brand-icon">a</span>adaptia
          <span className="brand-dot">.</span>
        </a>
        <nav>
          {nav.map(({ t, i: Icon }) => (
            <button
              className={tab === t ? "active" : ""}
              key={t}
              aria-label={t}
              onClick={() => go(t)}
            >
              <Icon size={19} />
              {t}
              {t === "Clientes" && <span>{clientes.length}</span>}
              {t === "Por confirmar" && porConfirmar > 0 && (
                <span aria-label={`${porConfirmar} por confirmar`}>
                  {porConfirmar}
                </span>
              )}
              {tab === t && <div className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="operator">
            <span className="avatar dark">OP</span>
            <div>
              <strong>Operador</strong>
              <span>
                {sesion.demo ? "Espacio de demostración" : "Acceso privado"}
              </span>
            </div>
            {!sesion.demo && (
              <button
                className="icon"
                aria-label="Cerrar sesión"
                onClick={async () => {
                  await api("/auth/logout", { method: "POST" });
                  setSesion({ ...sesion, sesion: false });
                  setEstado(null);
                }}
              >
                <LogOut size={17} />
              </button>
            )}
          </div>
        </div>
      </aside>
      {menu && <div className="nav-backdrop" onClick={() => setMenu(false)} />}
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon mobile-menu"
              aria-label="Abrir menú"
              onClick={() => setMenu(!menu)}
            >
              <Menu size={21} />
            </button>
            <strong>{tab}</strong>
          </div>
          <div className="topbar-right">
            {sesion.demo && (
              <span className="demo-badge">
                <span />
                Demostración
              </span>
            )}
            <span className="avatar small">OP</span>
          </div>
        </header>
        <main className="main" inert={modal || busy ? true : undefined}>
          {sesion.demo && (
            <div className="demo-notice">
              <ShieldCheck size={15} />
              <span>
                Estás usando datos ficticios. Los cambios de esta demostración
                no modifican Supabase ni ejecutan búsquedas reales.
              </span>
            </div>
          )}
          <div className="page-heading">
            <div>
              <div className="eyebrow">TU CENTRO DE OPORTUNIDADES</div>
              <h1>
                {tab === "Resumen"
                  ? "Cada búsqueda, con propósito."
                  : tab === "Clientes"
                    ? "Personas, no búsquedas genéricas."
                    : tab === "Cargos y cupos"
                      ? "Tú decides dónde buscar."
                      : tab === "Vacantes"
                        ? "Oportunidades para compartir."
                        : tab === "Por confirmar"
                          ? "Unos segundos para no perder vacantes."
                          : tab === "Mensajes"
                            ? "Mensajes listos para enviar."
                            : tab === "Actividad"
                              ? "Todo lo que ha pasado."
                              : "Tu espacio, bajo control."}
              </h1>
              <p>
                {tab === "Resumen"
                  ? "Organiza tus clientes y prepara las oportunidades de mañana."
                  : tab === "Clientes"
                    ? "Configura los criterios que hacen útil una vacante para cada cliente."
                    : tab === "Cargos y cupos"
                      ? "Reparte las 120 vacantes diarias entre los cargos que necesitas."
                      : tab === "Vacantes"
                        ? "Revisa las coincidencias de cada cliente y prepara su mensaje."
                        : tab === "Por confirmar"
                          ? "Vacantes que le servirían a tus clientes, pero cuyo país no se pudo confirmar solo. Decide con un clic: las que confirmes llegan hoy a sus clientes."
                          : tab === "Mensajes"
                            ? "Cada mañana cada persona tiene su mensaje con sus vacantes. Ábrelo en WhatsApp, revísalo y envíalo."
                            : tab === "Actividad"
                              ? "Cada noche: cuántas vacantes trajo la búsqueda con tu configuración y qué cargos quedaron cortos."
                              : "Información sobre la conexión y el funcionamiento del espacio."}
              </p>
            </div>
            {["Resumen", "Clientes", "Cargos y cupos"].includes(tab) && (
              <div className="heading-actions">
                <button
                  className="button secondary"
                  onClick={guardarClick}
                  disabled={!dirty || busy || total > 120}
                >
                  <Save size={16} />
                  {busy ? "Guardando…" : "Guardar borrador"}
                </button>
                <button
                  className="button primary"
                  onClick={() => setModal("publicar")}
                  disabled={busy || total !== 120}
                >
                  <CalendarClock size={16} />
                  Programar para mañana
                </button>
              </div>
            )}
          </div>
          {["Resumen", "Clientes", "Cargos y cupos"].includes(tab) && (
            <div className={"flow-status" + (dirty ? " pending" : "")}>
              <span className="flow-pill">
                {dirty
                  ? "Cambios sin guardar"
                  : estado?.publicada &&
                      estado.publicada.revision === estado.revision
                    ? "Programado desde el " +
                      fecha(estado.publicada.vigente_desde)
                    : estado?.revision
                      ? "Borrador guardado, sin programar"
                      : "Sin configuración programada"}
              </span>
              <span>
                <strong>Programar para mañana</strong> guarda tus cambios y los
                aplica desde la búsqueda de la 1:17 a. m. (hora Colombia).{" "}
                <strong>Guardar borrador</strong> solo los conserva, sin cambiar
                la próxima búsqueda.
              </span>
            </div>
          )}
          {tab === "Resumen" && (
            <>
              <section className="overview-top solo">
                <div className="quota-summary card">
                  <div className="card-label">
                    <span>OBJETIVO DIARIO</span>
                    <span
                      className={"pill " + (total === 120 ? "green" : "amber")}
                    >
                      {total === 120
                        ? "Distribución completa"
                        : "Por distribuir"}
                    </span>
                  </div>
                  <div className="quota-main">
                    <div className="quota-number">
                      {total}
                      <span> / 120</span>
                    </div>
                    <p>vacantes asignadas por cargo</p>
                  </div>
                  <div className="quota-track">
                    {cargos.map((c, i) => (
                      <span
                        key={c.id}
                        style={{
                          width: (c.cupo / Math.max(total, 120)) * 100 + "%",
                          background: colores[i % 5],
                        }}
                      />
                    ))}
                  </div>
                  <div className="quota-legend">
                    {cargos.map((c, i) => (
                      <div key={c.id}>
                        <span style={{ background: colores[i % 5] }} />
                        {c.nombre}
                        <strong>{c.cupo}</strong>
                      </div>
                    ))}
                  </div>
                  <button
                    className="text-button quota-link"
                    onClick={() => go("Cargos y cupos")}
                  >
                    Ajustar distribución
                    <ArrowRight size={15} />
                  </button>
                </div>
              </section>
              <section className="stat-grid">
                <div className="stat card">
                  <span className="stat-icon mint">
                    <Users size={21} />
                  </span>
                  <div>
                    <span>Clientes activos</span>
                    <strong>
                      {clientes.length}
                      <small>personas acompañadas</small>
                    </strong>
                  </div>
                </div>
                <div className="stat card">
                  <span className="stat-icon blue">
                    <BriefcaseBusiness size={21} />
                  </span>
                  <div>
                    <span>Cargos en búsqueda</span>
                    <strong>
                      {cargos.filter((c) => c.cupo > 0).length}
                      <small>búsquedas con foco</small>
                    </strong>
                  </div>
                </div>
                <div className="stat card">
                  <span className="stat-icon sand">
                    <CalendarClock size={21} />
                  </span>
                  <div>
                    <span>Configuración confirmada</span>
                    <strong className="date-stat">
                      {estado?.publicada
                        ? fecha(estado.publicada.vigente_desde)
                        : "Por programar"}
                      <small>
                        {estado?.publicada
                          ? "Vigente desde esta fecha"
                          : "Guarda y programa tus criterios"}
                      </small>
                    </strong>
                  </div>
                </div>
              </section>
              <section className="section-block">
                <div className="section-title">
                  <div>
                    <h2>
                      Tus clientes, de un vistazo{" "}
                      <span className="count-badge">{clientes.length}</span>
                    </h2>
                    <p>Cada perfil tiene sus propios criterios de búsqueda.</p>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => go("Clientes")}
                  >
                    Ver todos
                    <ArrowRight size={15} />
                  </button>
                </div>
                <div className="client-grid">
                  {clientes.slice(0, 3).map((c, i) => (
                    <ClientCard
                      key={c.id}
                      c={c}
                      index={i}
                      perfiles={profiles(c.id)}
                      cargos={draft.cargos}
                      paises={sesion.paises}
                      onEdit={() => {
                        setEditCliente(c);
                        setModal("cliente");
                      }}
                      onResults={() => {
                        setSelectedClient(c.id);
                        go("Vacantes");
                      }}
                    />
                  ))}
                  {!clientes.length && (
                    <Empty
                      icon={Users}
                      title="Tu primer cliente empieza aquí"
                      texto="Añade una persona y define su perfil de búsqueda."
                      action={() => {
                        setEditCliente(null);
                        setModal("cliente");
                      }}
                      label="Añadir cliente"
                    />
                  )}
                </div>
              </section>
            </>
          )}
          {tab === "Clientes" && (
            <>
              <div className="toolbar">
                <div className="search-input">
                  <Search size={17} />
                  <input
                    aria-label="Buscar cliente"
                    placeholder="Buscar un cliente…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <button
                  className="button primary"
                  onClick={() => {
                    setEditCliente(null);
                    setModal("cliente");
                  }}
                >
                  <Plus size={17} />
                  Nuevo cliente
                </button>
              </div>
              <div className="client-grid">
                {clientes
                  .filter((c) =>
                    c.nombre.toLowerCase().includes(search.toLowerCase()),
                  )
                  .map((c, i) => (
                    <ClientCard
                      key={c.id}
                      c={c}
                      index={i}
                      perfiles={profiles(c.id)}
                      cargos={draft.cargos}
                      paises={sesion.paises}
                      onEdit={() => {
                        setEditCliente(c);
                        setModal("cliente");
                      }}
                      onResults={() => {
                        setSelectedClient(c.id);
                        go("Vacantes");
                      }}
                      onArchive={() => {
                        setArchive({
                          tipo: "cliente",
                          id: c.id,
                          nombre: c.nombre,
                        });
                        setModal("archivo");
                      }}
                    />
                  ))}
              </div>
              {!clientes.length && (
                <Empty
                  icon={Users}
                  title="Todavía no tienes clientes"
                  texto="Añade tu primer cliente para preparar sus criterios."
                  action={() => {
                    setEditCliente(null);
                    setModal("cliente");
                  }}
                  label="Nuevo cliente"
                />
              )}
              {draft.clientes.some((c) => !c.activo) && (
                <details className="archived">
                  <summary>
                    Clientes archivados (
                    {draft.clientes.filter((c) => !c.activo).length})
                  </summary>
                  {draft.clientes
                    .filter((c) => !c.activo)
                    .map((c) => (
                      <div key={c.id}>
                        {c.nombre}
                        <button
                          className="text-button"
                          onClick={() =>
                            cambiar({
                              ...draft,
                              clientes: draft.clientes.map((x) =>
                                x.id === c.id ? { ...x, activo: true } : x,
                              ),
                            })
                          }
                        >
                          Reactivar
                        </button>
                      </div>
                    ))}
                </details>
              )}
            </>
          )}
          {tab === "Cargos y cupos" && (
            <>
              <div
                className={"allocation card " + (total > 120 ? "invalid" : "")}
              >
                <div>
                  <span className="tiny-kicker">DISTRIBUCIÓN DIARIA</span>
                  <h2>
                    {total}
                    <span> / 120 vacantes</span>
                  </h2>
                  <p>
                    {total === 120
                      ? "Tu distribución está completa. Puedes programar la búsqueda."
                      : total < 120
                        ? "Te faltan " +
                          (120 - total) +
                          " vacantes por distribuir."
                        : "Reduce " +
                          (total - 120) +
                          " vacantes para respetar el objetivo diario."}
                  </p>
                </div>
                <div className="allocation-right">
                  <div className="allocation-track">
                    <span
                      style={{
                        width: Math.min((total / 120) * 100, 100) + "%",
                      }}
                    />
                  </div>
                  <button
                    className="button secondary"
                    onClick={() => {
                      setEditCargo(null);
                      setModal("cargo");
                    }}
                  >
                    <Plus size={16} />
                    Añadir cargo
                  </button>
                </div>
              </div>
              <div className="role-list">
                {cargos.map((c, i) => (
                  <section className="role-card card" key={c.id}>
                    <div className="role-top">
                      <div
                        className="role-symbol"
                        style={{
                          color: colores[i % 5],
                          background: colores[i % 5] + "15",
                        }}
                      >
                        {c.nombre.toLowerCase().includes("front") ? (
                          <Code2 size={23} />
                        ) : (
                          <BriefcaseBusiness size={23} />
                        )}
                      </div>
                      <div className="role-info">
                        <h3>{c.nombre}</h3>
                        <span>
                          <Users size={13} />
                          {clientCount(c.id)}{" "}
                          {clientCount(c.id) === 1
                            ? "cliente compatible"
                            : "clientes con este cargo"}
                        </span>
                        <PreviewCargo
                          info={previaCargos.datos?.cargos?.[c.id]}
                          estado={previaCargos.estado}
                        />
                      </div>
                      <button
                        className="icon"
                        aria-label={"Editar " + c.nombre}
                        onClick={() => {
                          setEditCargo(c);
                          setModal("cargo");
                        }}
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        className="icon"
                        aria-label={"Archivar " + c.nombre}
                        onClick={() => {
                          setArchive({
                            tipo: "cargo",
                            id: c.id,
                            nombre: c.nombre,
                          });
                          setModal("archivo");
                        }}
                      >
                        <Archive size={16} />
                      </button>
                    </div>
                    <div className="role-terms">
                      <span>También buscará</span>
                      {c.terminos_similares.slice(0, 5).map((t) => (
                        <span className="term readonly" key={t}>
                          {t}
                        </span>
                      ))}
                      {!c.terminos_similares.length && (
                        <span className="helper">
                          Añade o descubre denominaciones afines.
                        </span>
                      )}
                    </div>
                    <div className="role-quota">
                      <label htmlFor={"cupo-" + c.id}>Cupo diario</label>
                      <input
                        id={"cupo-" + c.id}
                        type="range"
                        min={0}
                        max={120}
                        value={c.cupo}
                        onChange={(e) =>
                          cambiar({
                            ...draft,
                            cargos: draft.cargos.map((x) =>
                              x.id === c.id
                                ? { ...x, cupo: Number(e.target.value) }
                                : x,
                            ),
                          })
                        }
                      />
                      <div className="number-wrap">
                        <input
                          aria-label={"Vacantes de " + c.nombre}
                          type="number"
                          min={0}
                          max={120}
                          value={c.cupo}
                          onChange={(e) =>
                            cambiar({
                              ...draft,
                              cargos: draft.cargos.map((x) =>
                                x.id === c.id
                                  ? {
                                      ...x,
                                      cupo: Math.max(
                                        0,
                                        Math.min(120, Number(e.target.value)),
                                      ),
                                    }
                                  : x,
                              ),
                            })
                          }
                        />
                        <span>vacantes</span>
                      </div>
                    </div>
                    {c.cupo > 0 && clientCount(c.id) === 0 && (
                      <p className="role-warning">
                        Añade un perfil de cliente para poder programar este
                        cargo.
                      </p>
                    )}
                  </section>
                ))}
              </div>
              {previaCargos.datos?.nota && (
                <p className="helper note">{previaCargos.datos.nota}</p>
              )}
              <details className="archived">
                <summary>
                  Cargos archivados (
                  {draft.cargos.filter((c) => !c.activo).length})
                </summary>
                {draft.cargos
                  .filter((c) => !c.activo)
                  .map((c) => (
                    <div key={c.id}>
                      {c.nombre}
                      <button
                        className="text-button"
                        onClick={() =>
                          cambiar({
                            ...draft,
                            cargos: draft.cargos.map((x) =>
                              x.id === c.id ? { ...x, activo: true } : x,
                            ),
                          })
                        }
                      >
                        Reactivar
                      </button>
                    </div>
                  ))}
              </details>
              <div className="info-line bottom-info">
                <ShieldCheck size={18} />
                <p>
                  Una vacante compartida con varios clientes cuenta una sola vez
                  en el cupo de su cargo. Si no hay suficientes resultados
                  válidos, se mostrará el faltante.
                </p>
              </div>
            </>
          )}
          {tab === "Vacantes" && (
            <>
              <div className="results-control card">
                <div className="field">
                  <label htmlFor="result-cliente">
                    MOSTRAR OPORTUNIDADES PARA
                  </label>
                  <select
                    id="result-cliente"
                    value={selectedClient}
                    onChange={(e) => setSelectedClient(e.target.value)}
                  >
                    {Array.from(
                      new Map(
                        [...clientes, ...(results?.clientes || [])].map((c) => [
                          c.id,
                          c,
                        ]),
                      ).values(),
                    ).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="results-count">
                  <strong>{results?.listas || 0}</strong>
                  <span>listas para compartir</span>
                </div>
                <button
                  className="button whatsapp"
                  disabled={
                    !selectedClient ||
                    !results?.listas ||
                    busy ||
                    loadingResults
                  }
                  onClick={abrirWhatsApp}
                >
                  <MessageCircle size={18} />
                  Copiar WhatsApp
                </button>
              </div>
              <div className="toolbar">
                <div className="search-input">
                  <Search size={17} />
                  <input
                    placeholder="Buscar por cargo o empresa…"
                    aria-label="Buscar vacante"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <div className="results-tools">
                  <select
                    aria-label="Fecha de la captura"
                    value={resultDate}
                    onChange={(e) => setResultDate(e.target.value)}
                  >
                    <option value="">Última captura</option>
                    {runs.map((r) => (
                      <option key={r.id} value={r.fecha}>
                        {fecha(r.fecha)}
                      </option>
                    ))}
                  </select>
                  <button
                    className="button secondary"
                    onClick={cargarResultados}
                  >
                    <RefreshCw size={15} />
                    Actualizar estado
                  </button>
                </div>
              </div>
              {results?.ejecucion && (
                <div className="results-date">
                  {sesion.demo ? "Captura simulada" : "Captura del"}{" "}
                  {fecha(results.ejecucion.fecha)}
                  <span>·</span>Solo se copian enlaces con comprobación vigente
                </div>
              )}
              <div className="vacancy-grid">
                {shown.map((v) => (
                  <VacancyCard key={v.id} v={v} />
                ))}
              </div>
              {loadingResults && (
                <p role="status" className="helper">
                  Consultando vacantes…
                </p>
              )}
              {!loadingResults && !shown.length && (
                <Empty
                  icon={BriefcaseBusiness}
                  {...vacioVacantes(estado, results)}
                />
              )}
            </>
          )}
          {tab === "Por confirmar" && (
            <PorConfirmar
              paises={sesion.paises}
              notify={notify}
              onCambio={setPorConfirmar}
            />
          )}
          {tab === "Mensajes" && (
            <Mensajes clientes={draft.clientes} notify={notify} />
          )}
          {tab === "Actividad" && <AvisosCorreo notify={notify} />}
          {tab === "Actividad" && <ReglasAprendidas notify={notify} />}
          {tab === "Actividad" && (
            <section className="card activity">
              <div className="section-title">
                <h2>Resultado de cada búsqueda nocturna</h2>
                <button
                  className="icon"
                  aria-label="Actualizar actividad"
                  onClick={async () => {
                    try {
                      setRuns(await api("/ejecuciones"));
                    } catch (e) {
                      notify((e as Error).message, true);
                    }
                  }}
                >
                  <RefreshCw size={16} />
                </button>
              </div>
              {!runs.length ? (
                <Empty
                  icon={Clock3}
                  title="Aún no hay capturas dirigidas"
                  texto="Programa tu configuración. La primera búsqueda con esos criterios aparecerá aquí."
                />
              ) : (
                runs.map((r) => (
                  <div className="run" key={r.id}>
                    <span
                      className={
                        "run-dot " + (r.estado === "completa" ? "ok" : "")
                      }
                    >
                      <CheckCheck size={19} />
                    </span>
                    <div>
                      <h3>
                        {sesion.demo
                          ? "Captura de demostración"
                          : "Búsqueda dirigida"}{" "}
                        · {fecha(r.fecha)}
                      </h3>
                      <p>
                        {r.resumen.vacantes || 0} oportunidades distintas de{" "}
                        {r.resumen.meta || 120} previstas
                      </p>
                      {r.resumen.faltantes &&
                        Object.entries(r.resumen.faltantes).some(
                          ([, n]) => n > 0,
                        ) && (
                          <p className="form-error">
                            {Object.entries(r.resumen.faltantes)
                              .filter(([, n]) => n > 0)
                              .map(([c, n]) => c + ": faltan " + n)
                              .join(" · ")}
                          </p>
                        )}
                      {!!r.resumen.ampliadas && (
                        <p className="helper">
                          {r.resumen.ampliadas} asignaciones entraron por
                          ampliación para que cada cliente llegue a 5.
                        </p>
                      )}
                      {r.resumen.embudo && (
                        <EmbudoCargos embudo={r.resumen.embudo} />
                      )}
                    </div>
                    <span
                      className={
                        "pill " + (r.estado === "completa" ? "green" : "amber")
                      }
                    >
                      {(
                        {
                          completa: "Completada",
                          parcial: "Con faltantes",
                          fallida: "Requiere revisión",
                          en_curso: "En curso",
                        } as Record<string, string>
                      )[r.estado] || r.estado}
                    </span>
                  </div>
                ))
              )}
            </section>
          )}
          <footer className="footer">
            <span>
              adaptia<span className="brand-dot">.</span>{" "}
              <span>Oportunidades con dirección.</span>
            </span>
            <span>
              <ShieldCheck size={13} />
              {sesion.demo
                ? "Datos ficticios · Modo demostración"
                : "Control privado de búsqueda"}
            </span>
          </footer>
        </main>
      </div>
      {modal === "cargo" && (
        <CargoDialog
          cargo={editCargo}
          notify={notify}
          onClose={() => setModal(null)}
          onSave={(c) => {
            cambiar({
              ...draft,
              cargos: draft.cargos.some((x) => x.id === c.id)
                ? draft.cargos.map((x) => (x.id === c.id ? c : x))
                : [...draft.cargos, c],
            });
            const nuevo = !draft.cargos.some((x) => x.id === c.id);
            setModal(null);
            notify(
              (nuevo
                ? "Cargo añadido al borrador."
                : "Cargo actualizado en el borrador.") +
                " Prográmalo para que se aplique desde mañana.",
            );
          }}
        />
      )}
      {modal === "cliente" && (
        <ClienteDialog
          cliente={editCliente}
          config={draft}
          paises={sesion.paises}
          onClose={() => setModal(null)}
          onSave={(c, ps) => {
            cambiar({
              ...draft,
              clientes: draft.clientes.some((x) => x.id === c.id)
                ? draft.clientes.map((x) => (x.id === c.id ? c : x))
                : [...draft.clientes, c],
              perfiles: [
                ...draft.perfiles.filter((p) => p.cliente_id !== c.id),
                ...ps,
              ],
            });
            const nuevo = !draft.clientes.some((x) => x.id === c.id);
            setModal(null);
            notify(
              (nuevo
                ? "Cliente añadido al borrador."
                : "Cliente actualizado en el borrador.") +
                " Prográmalo para que se aplique desde mañana.",
            );
          }}
        />
      )}
      {modal === "publicar" && (
        <Dialog
          titulo="Preparar la búsqueda de mañana"
          subtitulo="Se confirmará esta distribución y los filtros actuales de los clientes."
          onClose={() => !busy && setModal(null)}
        >
          <div className="publish-list">
            {cargos
              .filter((c) => c.cupo > 0)
              .map((c, i) => (
                <div key={c.id}>
                  <span
                    className="color-dot"
                    style={{ background: colores[i % 5] }}
                  />
                  {c.nombre}
                  <strong>{c.cupo} vacantes</strong>
                </div>
              ))}
          </div>
          <div className="publish-total">
            <span>Objetivo total</span>
            <strong>{total} / 120</strong>
          </div>
          <p className="helper note">
            Al confirmar se guardan tus cambios y esta configuración se usa
            desde la búsqueda del <strong>{fecha(manana())}</strong> a la 1:17
            a. m. (hora Colombia). La de esta noche, si ya empezó, conserva la
            anterior.
            {!estado?.publicada &&
              " Es tu primera configuración: desde entonces dejan de buscarse los seis cargos fijos anteriores; solo se buscarán los cargos de esta lista."}{" "}
            Si las fuentes no ofrecen suficientes vacantes válidas, verás el
            faltante; no se rellena con duplicados ni con vacantes fuera de los
            filtros.
          </p>
          {sesion.demo && (
            <p className="demo-inline">
              Demostración: esta acción no programa una búsqueda real.
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setModal(null)}
            >
              Revisar
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={programar}
            >
              {busy ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <CalendarClock size={16} />
              )}
              Confirmar configuración
            </button>
          </div>
        </Dialog>
      )}
      {modal === "archivo" && archive && (
        <Dialog
          titulo={"Archivar " + archive.tipo}
          onClose={() => setModal(null)}
        >
          <p className="dialog-copy">
            «{archive.nombre}» dejará de participar en la próxima configuración.
            Su historial se conservará.
          </p>
          <div className="dialog-actions">
            <button className="button secondary" onClick={() => setModal(null)}>
              Cancelar
            </button>
            <button
              className="button danger-button"
              onClick={() => {
                cambiar(
                  archive.tipo === "cliente"
                    ? {
                        ...draft,
                        clientes: draft.clientes.map((c) =>
                          c.id === archive.id ? { ...c, activo: false } : c,
                        ),
                      }
                    : {
                        ...draft,
                        cargos: draft.cargos.map((c) =>
                          c.id === archive.id ? { ...c, activo: false } : c,
                        ),
                      },
                );
                setModal(null);
                notify("Archivado en el borrador. El historial se conserva.");
              }}
            >
              <Archive size={16} />
              Archivar
            </button>
          </div>
        </Dialog>
      )}
      {modal === "whatsapp" && (
        <Dialog
          ancho
          titulo="Un mensaje, más oportunidades"
          subtitulo="Revisa el mensaje antes de copiarlo y compartirlo en WhatsApp."
          onClose={() => setModal(null)}
        >
          <div className="whatsapp-preview">
            <div>
              <MessageCircle size={18} />
              <strong>Vista previa del mensaje</strong>
              <span>{results?.listas || 0} vacantes</span>
            </div>
            <textarea
              aria-label="Mensaje de WhatsApp"
              readOnly
              value={mensaje}
              onFocus={(e) => e.currentTarget.select()}
            />
          </div>
          <p className="helper">
            Los enlaces se vuelven a contrastar al preparar el mensaje. Copiar
            no envía nada ni confirma una postulación.
          </p>
          <div className="dialog-actions">
            <button className="button secondary" onClick={() => setModal(null)}>
              Cerrar
            </button>
            <button className="button whatsapp" onClick={copiar}>
              {copiado ? <CheckCheck size={17} /> : <Copy size={17} />}
              {copiado ? "Mensaje copiado" : "Copiar el mensaje"}
            </button>
          </div>
        </Dialog>
      )}
      {toast && (
        <div
          className={"toast " + (toast.error ? "error" : "")}
          role={toast.error ? "alert" : "status"}
        >
          {toast.error ? <ShieldCheck size={18} /> : <Check size={18} />}
          <span>{toast.texto}</span>
          <button aria-label="Cerrar aviso" onClick={() => setToast(null)}>
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
function Empty({
  icon: Icon,
  title,
  texto,
  action,
  label,
}: {
  icon: React.ComponentType<{ size: number }>;
  title: string;
  texto: string;
  action?: () => void;
  label?: string;
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
          <Plus size={16} />
          {label}
        </button>
      )}
    </div>
  );
}
function ClientCard({
  c,
  index,
  perfiles,
  cargos,
  paises,
  onEdit,
  onResults,
  onArchive,
}: {
  c: Cliente;
  index: number;
  perfiles: Perfil[];
  cargos: Cargo[];
  paises: Sesion["paises"];
  onEdit: () => void;
  onResults: () => void;
  onArchive?: () => void;
}) {
  const p = perfiles[0],
    cargo = cargos.find((x) => x.id === p?.cargo_id);
  return (
    <article className="client-card card">
      <div className="client-top">
        <span
          className="avatar"
          style={{
            background: colores[index % 5] + "18",
            color: colores[index % 5],
          }}
        >
          {iniciales(c.nombre)}
        </span>
        <div className="client-title">
          <h3>{c.nombre}</h3>
          <span>
            {cargo?.nombre || "Sin perfil"}
            {perfiles.length > 1 ? " + " + (perfiles.length - 1) : ""}
          </span>
        </div>
        <button
          className="icon"
          aria-label={"Editar " + c.nombre}
          onClick={onEdit}
        >
          <MoreHorizontal size={19} />
        </button>
      </div>
      <div className="client-tags">
        {p && (
          <>
            <span>
              <Globe2 size={12} />
              Vive en{" "}
              {paises.find((x) => x.codigo === p.vive_en)?.nombre || p.vive_en}
              {p.paises_presenciales_extra.length > 0 &&
                " · +" + p.paises_presenciales_extra.length}
            </span>
            <span>{p.modalidades.map((m) => modos[m]).join(" · ")}</span>
          </>
        )}
      </div>
      <div className="client-details">
        <div>
          <Clock3 size={14} />
          <span>Publicadas en los últimos {p?.antiguedad_dias || 14} días</span>
        </div>
        <div>
          <BriefcaseBusiness size={14} />
          <span>
            {p?.experiencia_min === null && p?.experiencia_max === null
              ? "Sin filtro de experiencia"
              : (p?.experiencia_min ?? 0) +
                "–" +
                (p?.experiencia_max ?? 40) +
                " años exigidos"}
          </span>
        </div>
        <div>
          <Globe2 size={14} />
          <span>
            {p?.idiomas
              .map((x) => (x === "es" ? "Español" : "Inglés"))
              .join(" / ") || "Sin idioma configurado"}
            {p?.ingles_maximo && p.ingles_maximo !== "sin_filtro"
              ? " · Inglés hasta " + p.ingles_maximo
              : ""}
          </span>
        </div>
      </div>
      <div className="client-bottom">
        <span className="status-active">
          <span />
          {cargo?.activo && cargo.cupo > 0 ? "Activo" : "Sin cupo"}
        </span>
        {onArchive && (
          <button
            className="icon"
            aria-label={"Archivar " + c.nombre}
            onClick={onArchive}
          >
            <Archive size={14} />
          </button>
        )}
        <button className="text-button" onClick={onResults}>
          Ver vacantes
          <ArrowUpRight size={15} />
        </button>
      </div>
    </article>
  );
}
function VacancyCard({ v }: { v: Vacante }) {
  return (
    <article
      className={"vacancy card " + (v.estado !== "lista" ? "unavailable" : "")}
    >
      <div className="vacancy-top">
        <span className="company-avatar">{iniciales(v.empresa)}</span>
        <div>
          <span className="company-name">{v.empresa}</span>
          <h3>{v.titulo}</h3>
        </div>
        <span className={"pill " + (v.estado === "lista" ? "green" : "amber")}>
          {v.estado === "lista"
            ? v.tipo === "post"
              ? "Vigente"
              : "Verificada"
            : v.estado === "retirada"
              ? "Retirada"
              : "Por confirmar"}
        </span>
      </div>
      <div className="vacancy-tags">
        <span>
          <Globe2 size={13} />
          {modos[v.modalidad] || v.modalidad}
        </span>
        <span>{v.idioma === "es" ? "Español" : "Inglés"}</span>
        <span>{grados[v.match_grade] || v.match_grade}</span>
        {v.tipo === "post" && (
          <span
            className="post-tag"
            title="Publicación de LinkedIn de quien contrata, sin ficha formal. Completa el mínimo de 5 y se contacta por mensaje o correo."
          >
            <Megaphone size={13} />
            Post
          </span>
        )}
        {v.ampliacion && (
          <span
            className="amplified"
            title="Entró para completar el mínimo de 5 vacantes de este perfil. No aparece en el mensaje de WhatsApp."
          >
            Ampliada: {v.ampliacion}
          </span>
        )}
      </div>
      <div className="vacancy-meta">
        <span>
          <Clock3 size={14} />
          {v.publicada ? fecha(v.publicada) : "Fecha por confirmar"}
        </span>
        <span>
          {v.experiencia !== null
            ? v.experiencia + " años exigidos"
            : "Experiencia no informada"}
        </span>
      </div>
      <details>
        <summary>
          Por qué coincide
          <ChevronDown size={13} />
        </summary>
        <ul>
          {v.explicacion
            .filter(
              (e) => typeof e === "string" || Boolean(e.termino || e.regla),
            )
            .map((e, i) => (
              <li key={i}>
                <Check size={12} />
                {typeof e === "string"
                  ? e
                  : e.termino
                    ? "Cargo: " + e.termino
                    : e.regla}
              </li>
            ))}
        </ul>
        {v.motivos.length > 0 && (
          <p className="helper">Revisar: {v.motivos.join(" · ")}</p>
        )}
        {v.tipo === "post" && v.contacto?.correo && (
          <p className="helper">Correo en el post: {v.contacto.correo}</p>
        )}
      </details>
      <div className="vacancy-bottom">
        <span>
          <ShieldCheck size={13} />
          {v.estado !== "lista"
            ? "No se incluirá en el mensaje"
            : v.tipo === "post"
              ? "Post leído en las últimas 24 h"
              : "Enlace con comprobación vigente"}
        </span>
        {v.enlace && (
          <a
            href={v.enlace}
            target="_blank"
            rel="noopener noreferrer"
            className="text-button"
          >
            {v.tipo === "post" ? "Contactar a quien publicó" : "Ver vacante"}
            <ExternalLink size={14} />
          </a>
        )}
      </div>
    </article>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
