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
  Download,
  Moon,
  Sun,
  CalendarClock,
  Check,
  CheckCheck,
  Clock3,
  Code2,
  Compass,
  Copy,
  Globe2,
  Loader2,
  LogOut,
  MapPin,
  MessageCircle,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  Users,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import { api, ErrorAPI } from "./api";
import { delSistema, guardarTema, temaElegido, type Tema } from "./tema";
import type {
  Restriccion,
  Cargo,
  Cliente,
  Configuracion,
  EstadoConfig,
  Perfil,
  Resultados,
  Sesion,
  Ejecucion,
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
  ResumenClientes,
  PreviaImportacion,
} from "./types";
import {
  Ayuda,
  Dialog,
  Empty,
  Plegable,
  REGIONES,
  SelectorPaises,
  fecha,
  fijarMundo,
  modos,
  nombrePais,
  paisesMundo,
} from "./comunes";
import { PorConfirmar } from "./vistas/PorConfirmar";
import { ListaVacantes } from "./vistas/Vacantes";
import "./style.css";

const uid = () => crypto.randomUUID();
// Sistema de Adaptia: un color por cargo, con su valor en claro y en oscuro (≥4,5:1 sobre su fondo tenue).
const colores = [1, 2, 3, 4, 5].map((n) => `var(--cargo-${n})`);
const vacio: Configuracion = { clientes: [], cargos: [], perfiles: [] };
// Nombre de archivo sin tildes ni espacios: el CSV solo queda en el equipo del operador.
function slug(texto: string) {
  return (
    texto
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "cliente"
  );
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
        "Las vacantes de cada cliente aparecen después de la primera búsqueda (6:30 a. m.) con su configuración. Ve a «Cargos y metas» y pulsa «Programar para mañana».",
    };
  const desde = estado.publicada.vigente_desde;
  if (!r?.ejecucion || r.ejecucion.fecha < desde)
    return {
      title: "Aún no hay búsqueda para este cliente",
      texto:
        "La primera búsqueda con tu configuración será el " +
        fecha(desde) +
        " a las 6:30 a. m. (hora Colombia). Después aparecerán aquí sus vacantes.",
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
    ciudades: [],
    puede_trabajar_en: [],
    acepta_horario: [],
    antiguedad_dias: 14,
    idiomas: ["es", "en"],
    ingles_maximo: "sin_filtro",
    experiencia_min: null,
    experiencia_max: null,
    experiencia_anos: null,
    aceptar_experiencia_sin_dato: false,
    aceptar_ingles_sin_dato: false,
    meta_diaria: META_POR_DEFECTO,
    margen_experiencia: 3,
    restricciones: [],
    sectores_preferidos: [],
    palabras_preferidas: [],
  };
}

// Contrato v21: cada perfil tiene su meta diaria y el día tiene un techo. Mismo cálculo que el servidor
// (panel/modelos.py, aplicar_metas): un perfil antiguo sin meta recibe su parte del cupo anterior del cargo; el cupo
// de cada cargo es la suma de las metas reales más la parte de Comunidad que cabe bajo el techo.
const META_POR_DEFECTO = 10;
function conMetas(cfg: Configuracion) {
  const techo = cfg.techo_diario ?? 120;
  const clientes = new Map(
    cfg.clientes.filter((c) => c.activo).map((c) => [c.id, c]),
  );
  const cargosActivos = new Set(
    cfg.cargos.filter((c) => c.activo).map((c) => c.id),
  );
  const activos = cfg.perfiles.filter(
    (p) =>
      p.activo && clientes.has(p.cliente_id) && cargosActivos.has(p.cargo_id),
  );
  const repartida = new Map<string, number>();
  for (const c of cfg.cargos) {
    const sinMeta = activos.filter(
      (p) => p.cargo_id === c.id && p.meta_diaria == null,
    );
    sinMeta.forEach((p, i) =>
      repartida.set(
        p.id,
        Math.floor(c.cupo / sinMeta.length) +
          (i < c.cupo % sinMeta.length ? 1 : 0),
      ),
    );
  }
  const metaDe = (p: Perfil) => p.meta_diaria ?? repartida.get(p.id) ?? 0;
  const esComunidad = (p: Perfil) => !!clientes.get(p.cliente_id)?.comunidad;
  const suma = (ps: Perfil[]) => ps.reduce((s, p) => s + metaDe(p), 0);
  const reales = suma(activos.filter((p) => !esComunidad(p)));
  const comunidad = suma(activos.filter(esComunidad));
  const factor = comunidad
    ? Math.min(1, Math.max(0, techo - reales) / comunidad)
    : 0;
  const cargos = cfg.cargos.map((c) => {
    const delCargo = activos.filter((p) => p.cargo_id === c.id);
    return {
      ...c,
      cupo: c.activo
        ? suma(delCargo.filter((p) => !esComunidad(p))) +
          Math.floor(suma(delCargo.filter(esComunidad)) * factor)
        : 0,
    };
  });
  const cabe = Math.min(comunidad, Math.max(0, techo - reales));
  return {
    cargos,
    techo,
    reales,
    comunidad,
    cabe,
    libre: Math.max(0, techo - reales - cabe),
    metaDe,
    total: cargos.filter((c) => c.activo).reduce((s, c) => s + c.cupo, 0),
  };
}

const SEPARADORES = /[,;\n]/;
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
  // Contrato v25: proponer la huella de funciones con el catálogo (sin IA).
  const [proponiendo, setProponiendo] = useState(false);
  async function proponerFunciones() {
    setProponiendo(true);
    try {
      const r = await api<{ funciones: string[]; motivo: string }>(
        "/cargos/funciones",
        { method: "POST", body: JSON.stringify(c) },
      );
      if (r.funciones.length)
        setC((v) => ({
          ...v,
          funciones: Array.from(
            new Set([...(v.funciones || []), ...r.funciones]),
          ),
        }));
      notify(
        r.funciones.length
          ? `Se propusieron ${r.funciones.length} funciones. Revisa y quita las que no correspondan.`
          : r.motivo,
        !r.funciones.length,
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setProponiendo(false);
    }
  }
  return (
    <Dialog
      titulo={cargo ? "Editar cargo" : "Añadir un cargo"}
      subtitulo="Un mismo cargo sirve a varios clientes; cuántas vacantes recibe lo dicen las metas de sus perfiles."
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
          {/* Paso 7 (reunión 14 nov): una sola lista visible. Por dentro se conserva la diferencia: lo que ya era
              principal sigue siéndolo y lo nuevo entra como afín. */}
          <TagInput
            label="Nombres del cargo"
            values={Array.from(
              new Set([...c.terminos_exactos, ...c.terminos_similares]),
            )}
            onChange={(v) => {
              const exactos = c.terminos_exactos.filter((x) => v.includes(x));
              setC({
                ...c,
                terminos_exactos: exactos,
                terminos_similares: v.filter((x) => !exactos.includes(x)),
              });
            }}
          />
          <p className="helper">
            Todas las formas en que las empresas llaman a este cargo, en español
            o inglés. Escríbelas una a una con Enter o pégalas separadas por
            comas.
          </p>
          <Plegable
            className="opciones-cargo"
            inicial={Boolean(
              (c.terminos_cercanos || []).length ||
                c.terminos_excluidos.length ||
                (c.funciones || []).length,
            )}
            mostrar={
              "Opciones avanzadas" +
              ((c.funciones || []).length
                ? ` · ${(c.funciones || []).length} funciones`
                : "")
            }
            ocultar="Ocultar opciones avanzadas"
          >
            <TagInput
              label="Funciones del cargo"
              values={c.funciones || []}
              onChange={(v) => setC({ ...c, funciones: v })}
            />
            <div className="funciones-acciones">
              <button
                type="button"
                className="button secondary small"
                disabled={proponiendo || c.nombre.trim().length < 2}
                onClick={proponerFunciones}
              >
                <Sparkles size={15} />
                {proponiendo ? "Buscando…" : "Proponer funciones"}
              </button>
              <Ayuda etiqueta="Funciones del cargo">
                Tareas y herramientas típicas del cargo. Si una vacante tiene
                otro título pero su descripción menciona varias de estas
                funciones, llega a «Por confirmar» como «Coincide por
                funciones». Se proponen comparando las vacantes del cargo con
                las de otros cargos; revisa y ajusta la lista.
              </Ayuda>
            </div>
            <TagInput
              label="Cargos cercanos (solo si faltan vacantes)"
              values={c.terminos_cercanos || []}
              onChange={(v) => setC({ ...c, terminos_cercanos: v })}
            />
            <p className="helper">
              Si un cliente no llega a 5 vacantes en el día, se completan
              primero con avisos que no dicen años o inglés y luego con estos
              oficios vecinos. En «Vacantes» aparecen marcadas como «Ampliada».
            </p>
            <TagInput
              label="Excluir estos términos"
              values={c.terminos_excluidos}
              onChange={(v) => setC({ ...c, terminos_excluidos: v })}
            />
          </Plegable>
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
  const [motivo, setMotivo] = useState("");
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
          setMotivo(r.motivo || "");
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
  return { datos, estado, motivo };
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
  motivo,
  pendiente,
  onAjustar,
}: {
  info?: EstimacionPerfil;
  estado: EstadoPrevia;
  motivo?: string;
  pendiente?: string;
  onAjustar: (cambio: Partial<Perfil>) => void;
}) {
  if (pendiente)
    return (
      <p className="preview muted-preview" role="status">
        Aún no se puede estimar este perfil: {pendiente}
      </p>
    );
  if (estado === "incompleto")
    return (
      <p className="preview muted-preview" role="status">
        Aún no se puede estimar: {motivo || "revisa los campos del perfil."}
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

// Por qué falló la petición, para que el operador sepa si esperar, volver a entrar o revisar el registro (13 nov).
function motivoFalloEnVivo(e: unknown) {
  if (e instanceof DOMException && e.name === "TimeoutError")
    return "La búsqueda tardó más de un minuto y se canceló. Inténtalo de nuevo en un rato.";
  if (e instanceof ErrorAPI) {
    if (e.status === 401)
      return "Tu sesión se cerró: vuelve a entrar al panel.";
    if (e.status === 403)
      return "El panel rechazó la petición. Recarga la página y vuelve a intentarlo.";
    if (e.status === 422) return "Aún no se puede buscar: " + e.message;
    if (e.status >= 502)
      return "El servidor del panel no respondió a tiempo (puede estar despertando). Espera un minuto y vuelve a intentarlo.";
    return "La búsqueda falló por un error del servidor. Inténtalo de nuevo en un minuto.";
  }
  return "No hubo conexión con el panel. Revisa tu internet y vuelve a intentarlo.";
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
        signal: AbortSignal.timeout(75000),
      });
      if (x.incompleto)
        setError(
          "Aún no se puede buscar: " +
            (x.motivo || "revisa los campos del perfil."),
        );
      else if (x.ocupado || x.espera || x.error)
        setError(x.nota || x.error || "");
      else setR(x);
    } catch (e) {
      setError(motivoFalloEnVivo(e));
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
      {!cargando && (
        <span className="live-gratis">
          No gasta Apify: solo LinkedIn público y Get on Board, sin cuentas.
        </span>
      )}
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
    >
      <Target size={12} />≈ {info.disponibles} guardadas sin entregar ·{" "}
      {textoEstadoCargo[info.estado]}
      {!!info.solapes?.length && (
        <span className="overlap">
          {" "}
          · comparte{" "}
          {info.solapes
            .map((s) => s.vacantes + " con «" + s.cargo + "»")
            .join(", ")}
        </span>
      )}
      <Ayuda etiqueta="vacantes del cargo">
        Vacantes ya guardadas, aún no entregadas, que cumplen los filtros de
        algún perfil de este cargo.
        {!!info.solapes?.length &&
          " Las que sirven a dos cargos se reparten por turnos según lo que le falta a cada uno. Mejor un solo cargo con varios perfiles."}
      </Ayuda>
    </div>
  );
}

const estadosMensaje: Record<Borrador["estado"], string> = {
  pendiente: "Por enviar",
  abierto: "Abierto en WhatsApp",
  enviado: "Enviado",
  descartado: "Descartado",
};

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
      const r = await api<{
        generados: number;
        conservados: number;
        sin_vacantes?: number;
        sin_contacto?: number;
        por_recomprobar?: number;
        clientes_activos?: number;
      }>("/borradores/generar", { method: "POST" });
      // Contrato v10: explicar por qué no salió nada, en lugar de un aviso genérico (13 nov).
      const razones: string[] = [];
      if (r.sin_contacto)
        razones.push(
          `${r.sin_contacto} de ${r.clientes_activos ?? r.sin_contacto} clientes sin WhatsApp o sin consentimiento (agrégalos en «Editar cliente»)`,
        );
      if (r.sin_vacantes)
        razones.push(
          `${r.sin_vacantes} clientes sin vacantes listas hoy` +
            (r.por_recomprobar
              ? ` (${r.por_recomprobar} esperan que se recompruebe su enlace; vuelve a intentarlo en una hora)`
              : ""),
        );
      if (r.conservados)
        razones.push(
          `${r.conservados} mensajes ya abiertos, enviados o editados no se tocaron`,
        );
      notify(
        r.generados
          ? `${r.generados} mensajes preparados.` +
              (razones.length ? " " + razones.join(". ") + "." : "")
          : "No se preparó ningún mensaje: " +
              (razones.join(". ") || "no hay vacantes listas nuevas") +
              ".",
        !r.generados,
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
        <h2>
          Mensajes de hoy{" "}
          <Ayuda etiqueta="mensajes">
            Para que una persona reciba su mensaje, en «Clientes» añade su
            WhatsApp y marca que aceptó recibir vacantes. Nada se envía solo:
            «Abrir en WhatsApp» abre su chat con el mensaje escrito para que lo
            revises y lo envíes.
          </Ayuda>
        </h2>
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
        <h2>
          Reglas de ubicación{" "}
          <Ayuda etiqueta="reglas de ubicación">
            Las del operador salen de «Aplicar a las iguales». Las aprendidas
            las crea el sistema solo, sin IA, cuando dos o más de tus decisiones
            coinciden en un lugar; si una decisión nueva las contradice, se
            desactivan solas. Solo resuelven ubicaciones dudosas: nunca cambian
            un país ya reconocido.
          </Ayuda>
        </h2>
      </div>
      <Plegable
        mostrar={
          "Ver reglas de ubicación" + (reglas ? ` (${reglas.length})` : "")
        }
        ocultar="Ocultar reglas de ubicación"
      >
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
                    · {r.origen === "aprendida"
                      ? "aprendida"
                      : "del operador"}{" "}
                    · usada {r.usos} {r.usos === 1 ? "vez" : "veces"}
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
      </Plegable>
    </section>
  );
}

const etapasEmbudo: [keyof Embudo, string][] = [
  ["encontradas", "Encontradas"],
  ["con_descripcion", "Con descripción"],
  ["entregables", "País e idioma confirmados"],
  ["nuevas", "Nuevas"],
  ["cumplen_filtros", "Cumplen filtros del cliente"],
  ["enlace_comprobado", "Enlace comprobado"],
  ["entregadas", "Entregadas"],
];

// Sección 8 (13 nov): una tarjeta por cargo en vez de una tabla ancha; cabe en el móvil sin scroll horizontal.
function EmbudoCargos({
  embudo,
  abierto = false,
}: {
  embudo: Record<string, Embudo>;
  abierto?: boolean;
}) {
  return (
    <Plegable
      className="funnel"
      inicial={abierto}
      mostrar="Ver dónde se pierden las vacantes"
      ocultar="Ocultar dónde se pierden las vacantes"
    >
      <div className="embudo-lista">
        {Object.entries(embudo).map(([cargo, e]) => {
          // La etapa que más vacantes pierde respecto a la anterior.
          let peor = -1,
            perdida = 0;
          etapasEmbudo.forEach(([k], n) => {
            if (n === 0) return;
            const caida =
              ((e[etapasEmbudo[n - 1][0]] as number) || 0) -
              ((e[k] as number) || 0);
            if (caida > perdida) {
              perdida = caida;
              peor = n;
            }
          });
          return (
            <section className="embudo-cargo" key={cargo}>
              <h4>
                <span>{cargo}</span>
                <span className="embudo-entregadas">
                  Entregadas {e.entregadas}
                </span>
              </h4>
              <ol className="embudo-etapas">
                {etapasEmbudo.map(([k, t], n) => (
                  <li key={k} className={n === peor ? "mayor-perdida" : ""}>
                    <strong>{e[k] as number}</strong>
                    <span>
                      {t}
                      {k === "entregadas" && (
                        <Ayuda etiqueta={"entregadas de " + cargo}>
                          Puede ser más que la etapa anterior: además de las
                          nuevas de esta búsqueda, incluye vacantes por
                          ampliación (para que cada persona llegue a 5) y
                          vacantes de días anteriores que esa persona aún no
                          había recibido.
                        </Ayuda>
                      )}
                    </span>
                    {k === "entregadas" && e.ampliadas > 0 && (
                      <span className="embudo-nota">
                        incluye {e.ampliadas} por ampliación
                      </span>
                    )}
                  </li>
                ))}
              </ol>
              {e.principal_perdida && (
                <p className="field-help">
                  Mayor pérdida: {e.principal_perdida}
                </p>
              )}
              {(e.de_su_busqueda ?? 0) + (e.de_la_amplia ?? 0) > 0 && (
                <p className="field-help">
                  Origen de las entregadas: {e.de_su_busqueda ?? 0} de su
                  búsqueda propia (LinkedIn por perfil) · {e.de_la_amplia ?? 0}{" "}
                  de la búsqueda amplia
                </p>
              )}
            </section>
          );
        })}
      </div>
    </Plegable>
  );
}

// Contrato v22: prioridades que solo ordenan y restricciones que descartan con evidencia clara.
const MONEDAS = [
  "USD",
  "EUR",
  "COP",
  "MXN",
  "ARS",
  "CLP",
  "PEN",
  "BRL",
  "UYU",
  "DOP",
  "GTQ",
  "CRC",
];
const TIPOS_CONTRATO: [string, string][] = [
  ["freelance", "Freelance o por proyecto"],
  ["part_time", "Medio tiempo"],
  ["contract", "Temporal o por prestación"],
  ["internship", "Prácticas o pasantía"],
];
function FiltrosPerfil({
  p,
  i,
  patch,
}: {
  p: Perfil;
  i: number;
  patch: (id: string, v: Partial<Perfil>) => void;
}) {
  const restricciones = p.restricciones || [];
  const cambiar = (n: number, r: Restriccion) =>
    patch(p.id, {
      restricciones: restricciones.map((x, k) => (k === n ? r : x)),
    });
  const quitar = (n: number) =>
    patch(p.id, { restricciones: restricciones.filter((_, k) => k !== n) });
  const nueva = (tipo: string): Restriccion =>
    tipo === "salario_minimo"
      ? { tipo, monto: 0, moneda: "USD", periodo: "month" }
      : tipo === "palabras"
        ? { tipo, palabras: [] }
        : { tipo: "contrato", tipos: [] };
  return (
    <div className="filtros-perfil">
      <Plegable
        mostrar={
          "Prioridades (opcional)" +
          ((p.sectores_preferidos?.length || 0) +
          (p.palabras_preferidas?.length || 0)
            ? ` · ${(p.sectores_preferidos?.length || 0) + (p.palabras_preferidas?.length || 0)}`
            : "")
        }
        ocultar="Ocultar prioridades"
      >
        <p className="field-help">
          Solo ordenan: cuando hay más vacantes que la meta, primero las que
          mencionan estos sectores o palabras. Nunca descartan. Déjalas vacías
          si no ayudan (por ejemplo en QA).
        </p>
        <TagInput
          label={"Sectores preferidos del perfil " + (i + 1)}
          values={p.sectores_preferidos || []}
          onChange={(v) => patch(p.id, { sectores_preferidos: v })}
        />
        <TagInput
          label={"Palabras clave preferidas del perfil " + (i + 1)}
          values={p.palabras_preferidas || []}
          onChange={(v) => patch(p.id, { palabras_preferidas: v })}
        />
      </Plegable>
      <fieldset className="restricciones">
        <legend>Este perfil NO acepta…</legend>
        {restricciones.map((r, n) => (
          <div className="restriccion" key={n}>
            {r.tipo === "salario_minimo" && (
              <div className="restriccion-campos">
                <span>Salario menor a</span>
                <input
                  type="number"
                  min={1}
                  aria-label={`Salario mínimo del perfil ${i + 1}`}
                  value={r.monto || ""}
                  onChange={(e) =>
                    cambiar(n, { ...r, monto: Number(e.target.value) || 0 })
                  }
                />
                <select
                  aria-label={`Moneda del salario del perfil ${i + 1}`}
                  value={r.moneda}
                  onChange={(e) => cambiar(n, { ...r, moneda: e.target.value })}
                >
                  {MONEDAS.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
                <select
                  aria-label={`Periodo del salario del perfil ${i + 1}`}
                  value={r.periodo}
                  onChange={(e) =>
                    cambiar(n, { ...r, periodo: e.target.value })
                  }
                >
                  <option value="month">al mes</option>
                  <option value="year">al año</option>
                  <option value="hour">por hora</option>
                </select>
              </div>
            )}
            {r.tipo === "palabras" && (
              <TagInput
                label={`Vacantes que mencionan (perfil ${i + 1})`}
                values={r.palabras}
                onChange={(v) => cambiar(n, { ...r, palabras: v })}
              />
            )}
            {r.tipo === "contrato" && (
              <div className="restriccion-campos">
                <span>Contratos de tipo</span>
                {TIPOS_CONTRATO.map(([valor, texto]) => (
                  <label key={valor} className="chip-check">
                    <input
                      type="checkbox"
                      checked={r.tipos.includes(valor)}
                      onChange={(e) =>
                        cambiar(n, {
                          ...r,
                          tipos: e.target.checked
                            ? [...r.tipos, valor]
                            : r.tipos.filter((x) => x !== valor),
                        })
                      }
                    />
                    {texto}
                  </label>
                ))}
              </div>
            )}
            <button
              type="button"
              className="text-button"
              aria-label={`Quitar restricción ${n + 1} del perfil ${i + 1}`}
              onClick={() => quitar(n)}
            >
              Quitar
            </button>
          </div>
        ))}
        {restricciones.length < 10 && (
          <select
            className="nueva-restriccion"
            aria-label={`Añadir restricción al perfil ${i + 1}`}
            value=""
            onChange={(e) =>
              e.target.value &&
              patch(p.id, {
                restricciones: [...restricciones, nueva(e.target.value)],
              })
            }
          >
            <option value="">＋ Añadir restricción…</option>
            <option value="salario_minimo">Salario menor a…</option>
            <option value="palabras">Vacantes que mencionan…</option>
            <option value="contrato">Tipo de contrato…</option>
          </select>
        )}
        <p className="field-help">
          Cada regla descarta solo si el aviso lo dice claramente. El salario se
          compara también en otras monedas, con un margen del 10 %.
        </p>
      </fieldset>
    </div>
  );
}
type BorradorCliente = {
  c: Cliente;
  ps: Perfil[];
  ct: Contacto;
  guardado: number;
};
// localStorage puede no existir o fallar (ventana privada, sitio bloqueado): nunca rompe el panel.
function leerLocal<T>(clave: string): T | null {
  try {
    const v = window.localStorage.getItem(clave);
    return v ? (JSON.parse(v) as T) : null;
  } catch {
    return null;
  }
}
function guardarLocal(clave: string, valor: unknown) {
  try {
    window.localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    /* sin almacenamiento: se sigue sin borrador */
  }
}
function borrarLocal(clave: string) {
  try {
    window.localStorage.removeItem(clave);
  } catch {
    /* nada que borrar */
  }
}
function ClienteDialog({
  cliente,
  config,
  paises,
  onClose,
  onSave,
  onCrearCargo,
}: {
  cliente: Cliente | null;
  config: Configuracion;
  paises: Sesion["paises"];
  onClose: () => void;
  onSave: (c: Cliente, p: Perfil[]) => void;
  onCrearCargo: (c: Cargo) => void;
}) {
  // Sección 8 (13 nov): crear un cargo sin salir del cliente. `null` = cerrado; si no, el perfil que lo pidió.
  const [cargoPara, setCargoPara] = useState<string | null>(null);
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
          // Si ya se tocó el formulario mientras cargaba, se respeta lo escrito.
          setCt((actual) =>
            actual.telefono || actual.consentimiento ? actual : r[cliente.id],
          );
          setTeniaContacto(true);
        }
      })
      .catch(() => undefined);
  }, [cliente]);
  const [ps, setPs] = useState<Perfil[]>(() => {
    if (cliente)
      return structuredClone(
        config.perfiles.filter((p) => p.cliente_id === cliente.id),
      );
    // Un cliente nuevo empieza con un perfil listo para llenar (sección 7a).
    const primero = config.cargos.find((x) => x.activo);
    return primero ? [perfilNuevo(c.id, primero.id)] : [];
  });
  const [error, setError] = useState("");
  const cargos = config.cargos.filter((c) => c.activo);
  // Reunión del 14 nov: lo escrito se guarda solo en este navegador mientras se edita. Si algo falla (pantalla en
  // blanco, conexión), al volver a abrir el formulario se ofrece recuperarlo. Nada sale del navegador hasta guardar.
  const claveBorrador = "adaptia:borrador-cliente:" + (cliente?.id ?? "nuevo");
  const inicial = useRef(JSON.stringify({ c, ps, ct: vacioContacto }));
  const [recuperable, setRecuperable] = useState<BorradorCliente | null>(() => {
    const guardado = leerLocal<BorradorCliente>(claveBorrador);
    return guardado &&
      JSON.stringify({ c: guardado.c, ps: guardado.ps, ct: guardado.ct }) !==
        inicial.current
      ? guardado
      : null;
  });
  useEffect(() => {
    const actual = JSON.stringify({ c, ps, ct });
    if (actual !== inicial.current)
      guardarLocal(claveBorrador, { c, ps, ct, guardado: Date.now() });
  }, [c, ps, ct, claveBorrador]);
  function recuperar(b: BorradorCliente) {
    const activos = new Set(config.cargos.map((x) => x.id));
    setC(b.c);
    // Un cargo que ya no existe se cambia por el primero activo para que el perfil siga siendo válido.
    setPs(
      b.ps.map((p) =>
        activos.has(p.cargo_id) || !cargos.length
          ? p
          : { ...p, cargo_id: cargos[0].id },
      ),
    );
    setCt(b.ct);
    setRecuperable(null);
  }
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
  const metasBorrador = conMetas(borrador);
  return (
    <>
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
            borrarLocal(claveBorrador);
            // Una restricción a medio llenar (sin monto, sin palabras ni tipos) no se guarda.
            onSave(
              c,
              ps.map((p) => ({
                ...p,
                restricciones: (p.restricciones || []).filter((r) =>
                  r.tipo === "salario_minimo"
                    ? r.monto > 0
                    : r.tipo === "palabras"
                      ? r.palabras.length > 0
                      : r.tipos.length > 0,
                ),
              })),
            );
          }}
        >
          {recuperable && (
            <div className="recuperar" role="status">
              <span>
                Tienes cambios sin guardar de las{" "}
                {new Date(recuperable.guardado).toLocaleTimeString("es-CO", {
                  hour: "numeric",
                  minute: "2-digit",
                })}
                .
              </span>
              <div>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => recuperar(recuperable)}
                >
                  Recuperar lo que escribías
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    borrarLocal(claveBorrador);
                    setRecuperable(null);
                  }}
                >
                  Descartar
                </button>
              </div>
            </div>
          )}
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
          <label className="casilla-comunidad">
            <input
              type="checkbox"
              checked={!!c.comunidad}
              onChange={(e) => setC({ ...c, comunidad: e.target.checked })}
            />
            Es «Comunidad» (grupo de WhatsApp): recibe después de los clientes
            reales, con lo que sobra del techo del día
          </label>
          <fieldset className="whatsapp-contacto">
            <legend>WhatsApp (opcional)</legend>
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
            {ct.consentimiento && (
              <div className="whatsapp-datos">
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
                      onChange={(e) =>
                        setCt({ ...ct, telefono: e.target.value })
                      }
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
                <p className="field-help">
                  Con número y aceptación, cada mañana tendrás su mensaje listo
                  en «Mensajes». Nada se envía solo.
                </p>
              </div>
            )}
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
                  <label htmlFor={"cargo-" + p.id}>Cargo</label>
                  <select
                    id={"cargo-" + p.id}
                    aria-label={"Cargo del perfil " + (i + 1)}
                    value={p.cargo_id}
                    onChange={(e) =>
                      e.target.value === "__nuevo"
                        ? setCargoPara(p.id)
                        : patch(p.id, { cargo_id: e.target.value })
                    }
                  >
                    {cargos.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                    {config.cargos
                      .filter((c) => !c.activo)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nombre} (archivado: se reactiva al guardar)
                        </option>
                      ))}
                    <option value="__nuevo">＋ Añadir cargo nuevo…</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor={"meta-" + p.id}>Meta diaria</label>
                  <input
                    id={"meta-" + p.id}
                    aria-label={"Meta diaria del perfil " + (i + 1)}
                    type="number"
                    min={0}
                    max={120}
                    value={p.meta_diaria ?? metasBorrador.metaDe(p)}
                    onChange={(e) =>
                      patch(p.id, {
                        meta_diaria: Math.max(
                          0,
                          Math.min(120, Number(e.target.value) || 0),
                        ),
                      })
                    }
                  />
                  <p className="field-help">
                    Vacantes al día para este perfil.
                  </p>
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
                    <optgroup label="LATAM y España">
                      {paises.map((pais) => (
                        <option key={pais.codigo} value={pais.codigo}>
                          {pais.nombre}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Resto del mundo">
                      {paisesMundo()
                        .filter(
                          (x) => !paises.some((c) => c.codigo === x.codigo),
                        )
                        .map((pais) => (
                          <option key={pais.codigo} value={pais.codigo}>
                            {pais.nombre}
                          </option>
                        ))}
                    </optgroup>
                  </select>
                </div>
              </div>
              <fieldset className="field plain">
                <legend>
                  ¿Qué modalidades acepta?{" "}
                  <Ayuda etiqueta="modalidades">
                    Remoto: vacantes de LATAM, España o del mundo abiertas a su
                    país. Híbrido y presencial: solo con oficina en su país o en
                    los países a los que se mudaría (se eligen abajo).
                  </Ayuda>
                </legend>
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
              </fieldset>
              {p.modalidades.some((m) => m !== "remoto") && (
                <div className="field mudanza">
                  <span className="mudanza-titulo">
                    También se mudaría a…{" "}
                    <span className="muted">(opcional)</span>
                  </span>
                  <Plegable
                    inicial={p.paises_presenciales_extra.length > 0}
                    mostrar={
                      "Mostrar países" +
                      (p.paises_presenciales_extra.length
                        ? ` (${p.paises_presenciales_extra.length} ${p.paises_presenciales_extra.length === 1 ? "elegido" : "elegidos"})`
                        : "")
                    }
                    ocultar="Ocultar países"
                  >
                    <div className="mudanza-acciones">
                      <button
                        type="button"
                        className="text-button"
                        onClick={() =>
                          patch(p.id, {
                            paises_presenciales_extra: [
                              ...paises
                                .map((x) => x.codigo)
                                .filter((x) => x !== p.vive_en),
                              ...p.paises_presenciales_extra.filter(
                                (x) => !paises.some((c) => c.codigo === x),
                              ),
                            ],
                          })
                        }
                      >
                        Seleccionar todos
                      </button>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() =>
                          patch(p.id, { paises_presenciales_extra: [] })
                        }
                      >
                        Quitar todos
                      </button>
                    </div>
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
                                    ? [
                                        ...p.paises_presenciales_extra,
                                        pais.codigo,
                                      ]
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
                    <SelectorPaises
                      etiqueta={
                        "Otros países, fuera de LATAM y España (perfil " +
                        (i + 1) +
                        ")"
                      }
                      valores={p.paises_presenciales_extra.filter(
                        (x) => !paises.some((c) => c.codigo === x),
                      )}
                      onChange={(v) =>
                        patch(p.id, {
                          paises_presenciales_extra: [
                            ...p.paises_presenciales_extra.filter((x) =>
                              paises.some((c) => c.codigo === x),
                            ),
                            ...v,
                          ],
                        })
                      }
                      excluir={[p.vive_en, ...paises.map((c) => c.codigo)]}
                    />
                  </Plegable>
                  <TagInput
                    label={
                      "Ciudades donde trabajaría (la suya y a las que se mudaría), perfil " +
                      (i + 1)
                    }
                    values={p.ciudades || []}
                    onChange={(v) => patch(p.id, { ciudades: v })}
                  />
                  <p className="field-help">
                    Para presencial o híbrida. Una vacante en una de estas
                    ciudades le sirve aunque su país no esté arriba. Escribe
                    «Ciudad, País» si el nombre se repite en otros países.
                    Vacío: cualquier ciudad; un aviso sin ciudad no se descarta.
                  </p>
                </div>
              )}
              <Plegable
                className="otros-paises"
                inicial={
                  !!(p.puede_trabajar_en?.length || p.acepta_horario?.length)
                }
                mostrar={
                  "Permiso de trabajo y horario (opcional)" +
                  ((p.puede_trabajar_en?.length || 0) +
                  (p.acepta_horario?.length || 0)
                    ? ` · ${(p.puede_trabajar_en?.length || 0) + (p.acepta_horario?.length || 0)}`
                    : "")
                }
                ocultar="Ocultar permiso y horario"
              >
                <SelectorPaises
                  etiqueta={
                    "Puede trabajar legalmente en… (perfil " + (i + 1) + ")"
                  }
                  valores={p.puede_trabajar_en || []}
                  onChange={(v) => patch(p.id, { puede_trabajar_en: v })}
                  excluir={[p.vive_en]}
                />
                <p className="field-help">
                  Por visa o ciudadanía. Las remotas restringidas a esos países
                  también le llegan.
                </p>
                <fieldset className="field plain">
                  <legend>Acepta trabajar en horario de…</legend>
                  <div className="check-line">
                    {(
                      [
                        ["us_este", "EE. UU. Este"],
                        ["us_pacifico", "EE. UU. Pacífico"],
                        ["europa", "Europa"],
                      ] as [string, string][]
                    ).map(([v, t]) => (
                      <label key={v}>
                        <input
                          type="checkbox"
                          aria-label={`Horario ${t} en el perfil ${i + 1}`}
                          checked={(p.acepta_horario || []).includes(v)}
                          onChange={(e) =>
                            patch(p.id, {
                              acepta_horario: e.target.checked
                                ? [...(p.acepta_horario || []), v]
                                : (p.acepta_horario || []).filter(
                                    (x) => x !== v,
                                  ),
                            })
                          }
                        />
                        {t}
                      </label>
                    ))}
                  </div>
                  <p className="field-help">
                    La zona de su país siempre cuenta. Una remota que solo pide
                    horario le llega si cruza alguna de estas zonas.
                  </p>
                </fieldset>
              </Plegable>
              <div className="form-grid">
                <div className="field">
                  <label htmlFor={"antiguedad-" + p.id}>
                    Antigüedad máxima de publicación
                  </label>
                  <select
                    id={"antiguedad-" + p.id}
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
                <div
                  className="field"
                  role="group"
                  aria-labelledby={"idioma-" + p.id}
                >
                  <span className="campo-titulo" id={"idioma-" + p.id}>
                    Idioma del aviso
                  </span>
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
              <div className="form-grid">
                <div className="field">
                  <label htmlFor={"anos-" + p.id}>Años de experiencia</label>
                  <input
                    id={"anos-" + p.id}
                    aria-label={"Años de experiencia del perfil " + (i + 1)}
                    type="number"
                    min={0}
                    max={40}
                    placeholder={
                      p.experiencia_anos == null &&
                      (p.experiencia_min !== null || p.experiencia_max !== null)
                        ? `Hoy: ${p.experiencia_min ?? 0}–${p.experiencia_max ?? 40} años`
                        : "Sin filtro"
                    }
                    value={p.experiencia_anos ?? ""}
                    onChange={(e) => {
                      // Contratos v20 y v22: de N años menos a N más (el servidor hace la misma cuenta).
                      const n =
                        e.target.value === ""
                          ? null
                          : Math.max(0, Math.min(40, Number(e.target.value)));
                      const m = p.margen_experiencia ?? 3;
                      patch(p.id, {
                        experiencia_anos: n,
                        experiencia_min: n === null ? null : Math.max(0, n - m),
                        experiencia_max:
                          n === null ? null : Math.min(40, n + m),
                      });
                    }}
                  />
                  <select
                    className="margen"
                    aria-label={"Margen de años del perfil " + (i + 1)}
                    value={p.margen_experiencia ?? 3}
                    onChange={(e) => {
                      const m = Number(e.target.value) as 3 | 4;
                      const n = p.experiencia_anos;
                      patch(p.id, {
                        margen_experiencia: m,
                        ...(n != null
                          ? {
                              experiencia_min: Math.max(0, n - m),
                              experiencia_max: Math.min(40, n + m),
                            }
                          : {}),
                      });
                    }}
                  >
                    <option value={3}>Margen ±3 años</option>
                    <option value={4}>Margen ±4 años</option>
                  </select>
                  <p className="field-help">
                    {p.experiencia_anos != null
                      ? p.experiencia_anos <= 2
                        ? "Con 2 años o menos no se filtra por experiencia: entra cualquier vacante de entrada."
                        : `Busca vacantes que pidan de ${p.experiencia_min} a ${p.experiencia_max} años.` +
                          (p.experiencia_anos >= 5
                            ? " No recibe vacantes junior ni de prácticas."
                            : "")
                      : p.experiencia_min !== null || p.experiencia_max !== null
                        ? `Hoy filtra de ${p.experiencia_min ?? 0} a ${p.experiencia_max ?? 40} años. Si escribes sus años, buscará de 3 menos a 3 más.`
                        : "Vacío: sin filtro de experiencia. Con un valor, busca de 3 años menos a 3 más."}
                  </p>
                </div>
                <div className="field">
                  <label htmlFor={"ingles-" + p.id}>
                    Inglés requerido: hasta
                  </label>
                  <select
                    id={"ingles-" + p.id}
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
                  <p className="field-help">
                    Es el nivel que pide el aviso, aparte del idioma en que está
                    escrito.
                  </p>
                </div>
              </div>
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
              <FiltrosPerfil p={p} i={i} patch={patch} />
              <PreviewPerfil
                info={previa.datos?.perfiles?.[p.id]}
                estado={previa.estado}
                motivo={previa.motivo}
                pendiente={previa.datos?.incompletos?.[p.id]}
                onAjustar={(cambio) => patch(p.id, cambio)}
              />
              <EnVivo
                config={borrador}
                perfilId={p.id}
                onAjustar={(cambio) => patch(p.id, cambio)}
              />
            </section>
          ))}
          {ps.length ? (
            <button
              type="button"
              disabled={!cargos.length}
              className="text-button otro-perfil"
              onClick={() => setPs([...ps, perfilNuevo(c.id, cargos[0].id)])}
            >
              <Plus size={15} />
              Añadir otro perfil
            </button>
          ) : (
            <button
              type="button"
              disabled={!cargos.length}
              className="button secondary full dashed"
              onClick={() => setPs([...ps, perfilNuevo(c.id, cargos[0].id)])}
            >
              <Plus size={16} />
              Añadir perfil de búsqueda
            </button>
          )}
          {!cargos.length && (
            <button
              type="button"
              className="button secondary"
              onClick={() => setCargoPara("")}
            >
              <Plus size={16} />
              Añadir cargo
            </button>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => {
                borrarLocal(claveBorrador);
                onClose();
              }}
            >
              Cancelar
            </button>
            <button className="button primary">
              {cliente ? "Aplicar cambios" : "Añadir cliente"}
              <Check size={15} />
            </button>
          </div>
        </form>
      </Dialog>
      {cargoPara !== null && (
        <CargoDialog
          cargo={null}
          notify={() => undefined}
          onClose={() => setCargoPara(null)}
          onSave={(nuevo) => {
            onCrearCargo(nuevo);
            const destino = cargoPara;
            if (destino)
              setPs((actuales) =>
                actuales.map((x) =>
                  x.id === destino ? { ...x, cargo_id: nuevo.id } : x,
                ),
              );
            else
              setPs((actuales) => [...actuales, perfilNuevo(c.id, nuevo.id)]);
            setCargoPara(null);
          }}
        />
      )}
    </>
  );
}
// Sección 5 (13 nov): sin menú propio; cada sección tiene su dirección y se abre desde las tarjetas del resumen.
const secciones: Record<string, string> = {
  Resumen: "",
  Clientes: "clientes",
  "Cargos y metas": "cargos",
  Vacantes: "vacantes",
  "Por confirmar": "por-confirmar",
  Mensajes: "mensajes",
  Actividad: "actividad",
};
function seccionDeHash() {
  // Contrato v29: «#vacantes/<id>» recuerda la vacante abierta; la sección es lo que va antes de la barra.
  const h = decodeURIComponent(location.hash.replace(/^#\/?/, "")).split(
    "/",
  )[0];
  return Object.keys(secciones).find((t) => secciones[t] === h) || "Resumen";
}
const estadosEjecucion: Record<string, string> = {
  completa: "Completada",
  parcial: "Con faltantes",
  fallida: "Requiere revisión",
  en_curso: "En curso",
};

// Resumen con jerarquía (13 nov, pedido de Oscar): Clientes y Cargos y cupos mandan; Vacantes, Por confirmar y
// Mensajes acompañan; Actividad es una franja tipo «entrada de evento» con la próxima búsqueda. La rejilla no es
// uniforme a propósito: tamaños distintos y una franja desplazada guían la mirada de lo más usado a lo demás.
function proximaBusqueda(ahora = new Date()) {
  // 6:30 a. m. de Bogotá (UTC−5, sin horario de verano) = 11:30 UTC.
  const hoy = new Date(
    Date.UTC(
      ahora.getUTCFullYear(),
      ahora.getUTCMonth(),
      ahora.getUTCDate(),
      11,
      30,
    ),
  );
  if (ahora >= hoy) hoy.setUTCDate(hoy.getUTCDate() + 1);
  return hoy;
}

type ResumenCliente = {
  id: string;
  nombre: string;
  cargo: string;
  meta: number;
  recibidas: number | null;
  porConfirmar: number;
  comunidad: boolean;
  perfiles: { cargo: string; meta: number }[];
};
// Paso 8: los datos de cada tarjeta de cliente (meta = suma de las metas de sus perfiles activos, como el servidor).
function resumenDeClientes(
  cfg: Configuracion,
  conteo: ResumenClientes | null,
  pendientes: Record<string, number>,
): ResumenCliente[] {
  const m = conMetas(cfg);
  const cargosActivos = new Map(
    cfg.cargos.filter((c) => c.activo).map((c) => [c.id, c.nombre]),
  );
  const ultimo = conteo?.dias.at(-1);
  const lista = cfg.clientes
    .filter((c) => c.activo)
    .map((c) => {
      const ps = cfg.perfiles.filter(
        (p) =>
          p.activo && p.cliente_id === c.id && cargosActivos.has(p.cargo_id),
      );
      const perfiles = ps.map((p) => ({
        cargo: cargosActivos.get(p.cargo_id) || "",
        meta: m.metaDe(p),
      }));
      const nombres = [...new Set(perfiles.map((p) => p.cargo))];
      return {
        id: c.id,
        nombre: c.nombre,
        cargo: nombres.length
          ? nombres.length > 2
            ? "Varios cargos"
            : nombres.join(" · ")
          : "Sin perfil",
        meta: perfiles.reduce((s, p) => s + p.meta, 0),
        recibidas: ultimo ? ultimo.clientes[c.id] || 0 : null,
        porConfirmar: pendientes[c.id] || 0,
        comunidad: !!c.comunidad,
        perfiles,
      };
    });
  // Primero los que van peor; Comunidad siempre al final.
  const avance = (c: ResumenCliente) =>
    c.recibidas == null || !c.meta ? 1 : c.recibidas / c.meta;
  return lista.sort(
    (a, b) =>
      Number(a.comunidad) - Number(b.comunidad) ||
      avance(a) - avance(b) ||
      a.nombre.localeCompare(b.nombre, "es"),
  );
}
// Contrato v29: el Resumen pide una página corta; el total y el conteo por cliente cubren todas las pendientes.
const PENDIENTES_RESUMEN = "/revisiones?pagina=1&por_pagina=1";
const bajoMeta = (c: ResumenCliente) =>
  c.recibidas != null && c.meta > 0 && c.recibidas < c.meta / 2;
// Desde 9 clientes las tarjetas pasan a dos columnas (decisión de Oscar, 14 nov).
const CLIENTES_EN_GRILLA = 9;

// Contrato v27: el cliente «Comunidad» lleva un distintivo discreto para reconocerlo sin que llame toda la atención.
function DistintivoComunidad() {
  return (
    <span
      className="distintivo-comunidad"
      title="Recibe después de los clientes reales, con lo que sobra del techo"
    >
      <Users size={11} aria-hidden="true" />
      Comunidad
    </span>
  );
}

function TarjetasResumen({
  clientes,
  diaConteo,
  onCliente,
  perfiles,
  cargos,
  total,
  techo,
  comunidad,
  ultima,
  porConfirmar,
  borradores,
  go,
}: {
  clientes: ResumenCliente[];
  diaConteo?: string;
  onCliente: (id: string) => void;
  perfiles: number;
  cargos: Cargo[];
  total: number;
  techo: number;
  comunidad: number;
  ultima?: Ejecucion;
  porConfirmar: number;
  borradores: Borrador[] | null;
  go: (t: string) => void;
}) {
  const r = ultima?.resumen || {};
  const vivos = (borradores || []).filter((b) => b.estado !== "descartado");
  const enviados = vivos.filter((b) => b.estado === "enviado").length;
  const proxima = proximaBusqueda();
  const dia = proxima.toLocaleDateString("es-CO", {
    day: "numeric",
    timeZone: "America/Bogota",
  });
  const mes = proxima
    .toLocaleDateString("es-CO", { month: "short", timeZone: "America/Bogota" })
    .replace(".", "");
  const semana = proxima.toLocaleDateString("es-CO", {
    weekday: "long",
    timeZone: "America/Bogota",
  });
  const conCupo = cargos.filter((c) => c.cupo > 0);
  const bajos = clientes.filter(bajoMeta).length;
  const grilla = clientes.length >= CLIENTES_EN_GRILLA;
  const deHoy = diaConteo === hoyBogota();
  return (
    <section
      className={"resumen-grid" + (grilla ? " con-muchos" : "")}
      aria-label="Resumen del panel"
    >
      <div className="tarjeta-resumen tarjeta-clientes">
        <span className="tarjeta-cabeza">
          <Users size={18} />
          Clientes
        </span>
        <strong className="tarjeta-numero">
          {clientes.length}
          <small>
            {" "}
            {clientes.length === 1 ? "activo" : "activos"}
            {diaConteo
              ? ` · ${bajos} bajo su meta`
              : ` · ${perfiles} ${perfiles === 1 ? "perfil" : "perfiles"}`}
          </small>
        </strong>
        {diaConteo && (
          <span className="tarjeta-detalle">
            {deHoy
              ? "Recibidas hoy de su meta del día"
              : `Recibidas en la búsqueda del ${fecha(diaConteo)} (la de hoy aún no corre)`}
          </span>
        )}
        {clientes.length > 0 && (
          <ul
            className={"clientes-lista" + (grilla ? " en-grilla" : "")}
            aria-label="Clientes y su avance"
          >
            {clientes.map((c) => {
              const pct =
                c.recibidas == null || !c.meta
                  ? 0
                  : Math.min(100, Math.round((c.recibidas / c.meta) * 100));
              const cifra =
                c.recibidas == null
                  ? `— / ${c.meta}`
                  : `${c.recibidas}/${c.meta}`;
              const pendiente = `${c.porConfirmar} por confirmar`;
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    className={
                      "cliente-mini" +
                      (bajoMeta(c) ? " bajo" : "") +
                      (c.comunidad ? " es-comunidad" : "")
                    }
                    aria-label={
                      `${c.nombre}${c.comunidad ? " (Comunidad)" : ""}: ` +
                      (c.recibidas == null
                        ? `meta de ${c.meta}`
                        : `${c.recibidas} de ${c.meta}`) +
                      `, ${pendiente}` +
                      (bajoMeta(c) ? ", bajo su meta" : "") +
                      ". Ver detalle"
                    }
                    onClick={() => onCliente(c.id)}
                  >
                    <span className="cliente-texto">
                      <strong>
                        {c.nombre}
                        {c.comunidad && <DistintivoComunidad />}
                      </strong>
                      <span>
                        {c.cargo}
                        {!grilla && c.porConfirmar > 0 && (
                          <span className="solo-lista"> · {pendiente}</span>
                        )}
                      </span>
                    </span>
                    <span className="cliente-barra" aria-hidden="true">
                      <span style={{ width: pct + "%" }} />
                    </span>
                    <span className="cliente-pie">
                      <span className="cliente-cifra">{cifra}</span>
                      <span className="cliente-confirmar">{pendiente}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <button
          type="button"
          className="ver-todos"
          onClick={() => go("Clientes")}
        >
          Ver clientes
          <ArrowRight size={15} />
        </button>
      </div>

      <div className="resumen-derecha">
        <button
          type="button"
          className={
            "tarjeta-resumen tarjeta-cupos " +
            (total > 0 && total <= techo ? "green" : "amber")
          }
          onClick={() => go("Cargos y metas")}
        >
          <span className="tarjeta-cabeza">
            <SlidersHorizontal size={17} />
            Techo del día
          </span>
          <div className="cupos-fila">
            <strong className="tarjeta-numero">
              {total}
              <small> / {techo}</small>
            </strong>
            <span className="tarjeta-detalle">
              {total - comunidad} a clientes · {comunidad} a Comunidad
            </span>
          </div>
          <span className="cupos-barra" aria-hidden="true">
            {conCupo.map((c, i) => (
              <span
                key={c.id}
                style={{
                  width: (c.cupo / Math.max(total, techo)) * 100 + "%",
                  background: colores[i % 5],
                  animationDelay: 120 + i * 70 + "ms",
                }}
              />
            ))}
          </span>
          <span className="cupos-leyenda">
            {conCupo.map((c, i) => (
              <span key={c.id}>
                <i style={{ background: colores[i % 5] }} />
                {c.nombre} <b>{c.cupo}</b>
              </span>
            ))}
          </span>
          <span className="tarjeta-accion">
            Editar cargos y metas
            <ArrowRight size={15} />
          </span>
        </button>

        <button
          type="button"
          className="tarjeta-resumen tarjeta-chica tarjeta-vacantes"
          onClick={() => go("Vacantes")}
        >
          <span className="tarjeta-cabeza">
            <BriefcaseBusiness size={16} />
            Vacantes
          </span>
          <strong className="tarjeta-numero">
            {ultima ? (r.vacantes ?? 0) : "—"}
            {ultima && <small> / {r.meta ?? 120}</small>}
          </strong>
          <span className="tarjeta-detalle">
            {ultima
              ? `Búsqueda del ${fecha(ultima.fecha)}`
              : "Sin búsquedas aún"}
          </span>
          <span className="tarjeta-accion">
            Ver vacantes
            <ArrowRight size={14} />
          </span>
        </button>

        <button
          type="button"
          className={
            "tarjeta-resumen tarjeta-chica tarjeta-confirmar" +
            (porConfirmar ? " pendiente" : "")
          }
          onClick={() => go("Por confirmar")}
        >
          <span className="tarjeta-cabeza">
            <MapPin size={16} />
            Por confirmar
            {porConfirmar > 0 && (
              <span className="punto-vivo" aria-hidden="true" />
            )}
          </span>
          <strong className="tarjeta-numero">{porConfirmar}</strong>
          <span className="tarjeta-detalle">
            {porConfirmar ? "Esperan tu decisión" : "Nada pendiente"}
          </span>
          <span className="tarjeta-accion">
            Revisar
            <ArrowRight size={14} />
          </span>
        </button>

        <button
          type="button"
          className="tarjeta-resumen tarjeta-chica tarjeta-mensajes"
          onClick={() => go("Mensajes")}
        >
          <span className="tarjeta-cabeza">
            <MessageCircle size={16} />
            Mensajes de hoy
          </span>
          <strong className="tarjeta-numero">
            {borradores ? vivos.length : "—"}
          </strong>
          <span className="tarjeta-detalle">
            {!borradores
              ? "Ábrelos para prepararlos"
              : vivos.length
                ? `${enviados} ${enviados === 1 ? "enviado" : "enviados"} de ${vivos.length}`
                : "Aún no preparados"}
          </span>
          <span className="tarjeta-accion">
            Ver mensajes
            <ArrowRight size={14} />
          </span>
        </button>

        <button
          type="button"
          className="tarjeta-resumen tarjeta-actividad"
          onClick={() => go("Actividad")}
        >
          <span className="evento-fecha" aria-hidden="true">
            <b>{dia}</b>
            <span>{mes}</span>
          </span>
          <span className="evento-texto">
            <span className="tarjeta-cabeza">
              <Clock3 size={15} />
              Actividad
            </span>
            <span className="evento-titulo">
              Próxima búsqueda: {semana} {dia} de {mes} · 6:30 a. m.
            </span>
            <span className="tarjeta-detalle">
              {ultima
                ? `Última, del ${fecha(ultima.fecha)}: ${(estadosEjecucion[ultima.estado] || ultima.estado).toLowerCase()}`
                : "Aún no hay búsquedas registradas"}
            </span>
          </span>
          {ultima && (
            <span
              className={
                "pill " + (ultima.estado === "completa" ? "green" : "amber")
              }
            >
              {estadosEjecucion[ultima.estado] || ultima.estado}
            </span>
          )}
          <span className="tarjeta-accion">
            Ver actividad
            <ArrowRight size={14} />
          </span>
        </button>
      </div>
    </section>
  );
}

// Paso 8 (variante B): el detalle de un cliente desde el Resumen, con sus 7 días, lo que más le corta, su CSV y sus
// «por confirmar» para decidir ahí mismo.
function ClienteDetalle({
  cliente: c,
  dias,
  ultima,
  notify,
  onCerrar,
  onCambio,
  onVacantes,
  onRevisar,
  onCsv,
  onEditar,
  descargando,
}: {
  cliente: ResumenCliente;
  cfg: Configuracion;
  dias: ResumenClientes["dias"];
  ultima?: Ejecucion;
  notify: (s: string, error?: boolean) => void;
  onCerrar: () => void;
  onCambio: () => void;
  onVacantes: () => void;
  onRevisar: () => void;
  onCsv: () => void;
  onEditar: () => void;
  descargando: boolean;
}) {
  const [ocupado, setOcupado] = useState("");
  // Contrato v29: sus «por confirmar» se piden al servidor, con su total real.
  const [pendientes, setPendientes] = useState<Revisiones | null>(null);
  function cargarPendientes() {
    api<Revisiones>(
      "/revisiones?pagina=1&por_pagina=8&cliente_id=" +
        encodeURIComponent(c.id),
    )
      .then(setPendientes)
      .catch(() =>
        setPendientes({ pendientes: [], total: 0, ayudan_faltantes: 0 }),
      );
  }
  useEffect(cargarPendientes, [c.id]);
  const serie = dias.map((d) => ({ fecha: d.fecha, n: d.clientes[c.id] || 0 }));
  const tope = Math.max(c.meta, 1, ...serie.map((d) => d.n));
  const faltan =
    c.recibidas == null ? c.meta : Math.max(0, c.meta - c.recibidas);
  const cortes = [...new Set(c.perfiles.map((p) => p.cargo))]
    .map((cargo) => ({
      cargo,
      texto: ultima?.resumen.embudo?.[cargo]?.principal_perdida || "",
    }))
    .filter((x) => x.texto);
  const nombreLugar = (codigo: string) =>
    REGIONES.find((r) => r.codigo === codigo)?.nombre || nombrePais(codigo);
  const paisesDe = (r: Revision) =>
    r.funciones
      ? []
      : r.paises_sugeridos?.length
        ? r.paises_sugeridos
        : r.sugerencia[0]
          ? [r.sugerencia[0]]
          : null;
  async function decidir(r: Revision, decision: "sirve" | "no_sirve") {
    setOcupado(r.vacante_id);
    try {
      const res = await api<{ asignadas: number }>(
        "/revisiones/" + encodeURIComponent(r.vacante_id),
        {
          method: "POST",
          body: JSON.stringify({
            decision,
            paises: decision === "sirve" ? paisesDe(r) || [] : [],
            aplicar_a_iguales: false,
          }),
        },
      );
      notify(
        decision === "sirve"
          ? `Confirmada: se asignó a ${res.asignadas} cliente(s).`
          : "Descartada.",
      );
      onCambio();
      cargarPendientes();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado("");
    }
  }
  const visibles = pendientes?.pendientes || [];
  const totalPendientes = pendientes?.total ?? c.porConfirmar;
  return (
    <Dialog titulo={c.nombre} subtitulo={c.cargo} onClose={onCerrar} ancho>
      {/* Lista grande del 16 nov: datos a la izquierda y sus «por confirmar» a la derecha, sin salir del detalle. */}
      <div className="detalle-dos-paneles">
        <div className="detalle-izquierda">
          <div className="detalle-cifras">
            <div>
              <b>{c.recibidas ?? "—"}</b>
              <span>
                {c.recibidas == null
                  ? "Sin búsquedas aún"
                  : `recibidas de ${c.meta}`}
              </span>
            </div>
            <div className={c.porConfirmar ? "ambar" : ""}>
              <b>{c.porConfirmar}</b>
              <span>por confirmar</span>
            </div>
            <div>
              <b>{faltan}</b>
              <span>{faltan === 1 ? "falta" : "faltan"} para su meta</span>
            </div>
          </div>

          {serie.length > 0 && (
            <section className="detalle-seccion">
              <h3>Últimos {serie.length} días</h3>
              <div
                className="dias-barras"
                role="img"
                aria-label={
                  "Recibidas por día: " +
                  serie.map((d) => `${fecha(d.fecha)}, ${d.n}`).join("; ")
                }
              >
                {serie.map((d) => (
                  <div key={d.fecha} aria-hidden="true">
                    <b>{d.n}</b>
                    <i
                      className={"barra" + (d.n < c.meta / 2 ? " bajo" : "")}
                      style={{ height: Math.max(4, (d.n / tope) * 100) + "%" }}
                    />
                    <span>
                      {new Date(d.fecha + "T12:00:00")
                        .toLocaleDateString("es-CO", {
                          weekday: "short",
                          day: "numeric",
                        })
                        .replace(/[.,]/g, "")}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="detalle-seccion">
            <h3>Sus perfiles</h3>
            <ul className="detalle-lista">
              {c.perfiles.map((p, i) => (
                <li key={i}>
                  {p.cargo} · meta de {p.meta} al día
                </li>
              ))}
              {!c.perfiles.length && <li>Aún no tiene perfiles activos.</li>}
            </ul>
          </section>

          {cortes.length > 0 && (
            <section className="detalle-seccion">
              <h3>Lo que más corta en su cargo</h3>
              <ul className="detalle-lista">
                {cortes.map((x) => (
                  <li key={x.cargo}>
                    <b>{x.cargo}:</b> {x.texto}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="button secondary editar-perfil"
                onClick={onEditar}
              >
                <Pencil size={15} />
                Editar perfil
              </button>
              <p className="field-help">
                En el perfil verás cuántas vacantes cumplen hoy y qué ajuste
                añadiría más.
              </p>
            </section>
          )}

          <div className="detalle-acciones">
            <button
              type="button"
              className="button primary"
              onClick={onVacantes}
            >
              <BriefcaseBusiness size={16} />
              Ver sus vacantes
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={onCsv}
              disabled={descargando}
            >
              <Download size={16} />
              {descargando ? "Descargando…" : "Descargar su CSV de hoy"}
            </button>
            {!cortes.length && (
              <button
                type="button"
                className="button secondary"
                onClick={onEditar}
              >
                <Pencil size={15} />
                Editar perfil
              </button>
            )}
          </div>
        </div>

        <section className="detalle-seccion detalle-derecha">
          <h3>Por confirmar ({totalPendientes})</h3>
          {pendientes && !totalPendientes && (
            <p className="field-help">Nada pendiente para este cliente.</p>
          )}
          {visibles.map((r) => {
            const paises = paisesDe(r);
            return (
              <article key={r.vacante_id} className="detalle-pendiente">
                <small>
                  {r.motivo || "País por confirmar"}
                  {paises?.length
                    ? " · sugerido: " +
                      paises.slice(0, 3).map(nombreLugar).join(", ") +
                      (paises.length > 3 ? ` y ${paises.length - 3} más` : "")
                    : ""}
                </small>
                <strong>{r.titulo}</strong>
                <span className="tarjeta-detalle">
                  {[r.empresa, r.ubicacion].filter(Boolean).join(" · ")}
                </span>
                <div className="fila-botones">
                  {paises ? (
                    <button
                      type="button"
                      className="button primary"
                      disabled={ocupado === r.vacante_id}
                      onClick={() => decidir(r, "sirve")}
                    >
                      Sí, sirve
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button secondary"
                      onClick={onRevisar}
                    >
                      Elegir país en Por confirmar
                    </button>
                  )}
                  <button
                    type="button"
                    className="button secondary"
                    disabled={ocupado === r.vacante_id}
                    onClick={() => decidir(r, "no_sirve")}
                  >
                    No sirve
                  </button>
                  {r.enlace && (
                    <a
                      className="button secondary"
                      href={r.enlace}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Ver aviso
                    </a>
                  )}
                </div>
              </article>
            );
          })}
          {totalPendientes > visibles.length && (
            <button type="button" className="text-button" onClick={onRevisar}>
              Ver las {totalPendientes} en Por confirmar
            </button>
          )}
        </section>
      </div>
    </Dialog>
  );
}

function BotonTema() {
  const [elegido, setElegido] = useState(temaElegido);
  const [sistema, setSistema] = useState<Tema>(delSistema);
  useEffect(() => {
    let consulta: MediaQueryList;
    try {
      consulta = matchMedia("(prefers-color-scheme: dark)");
    } catch {
      return;
    }
    const seguir = () => setSistema(consulta.matches ? "oscuro" : "claro");
    consulta.addEventListener("change", seguir);
    return () => consulta.removeEventListener("change", seguir);
  }, []);
  const actual = elegido || sistema;
  const otro: Tema = actual === "oscuro" ? "claro" : "oscuro";
  return (
    <button
      type="button"
      className="button secondary boton-tema"
      aria-label={`Cambiar a modo ${otro}`}
      title={`Cambiar a modo ${otro}`}
      onClick={() => {
        guardarTema(otro);
        setElegido(otro);
      }}
    >
      {actual === "oscuro" ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}

// Importar clientes desde un CSV (15 nov): vista previa sin guardar y luego importación todo o nada. Los clientes
// quedan en el borrador como si se hubieran creado a mano; la búsqueda los usa al programar.
function ImportarClientes({
  revision,
  dirty,
  notify,
  onListo,
  onClose,
}: {
  revision: number;
  dirty: boolean;
  notify: (s: string, error?: boolean) => void;
  onListo: (estado: EstadoConfig) => void;
  onClose: () => void;
}) {
  const [contenido, setContenido] = useState("");
  const [actuales, setActuales] = useState<"mantener" | "archivar" | "borrar">(
    "mantener",
  );
  const [confirmacion, setConfirmacion] = useState("");
  const [previa, setPrevia] = useState<PreviaImportacion | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => {
    if (!contenido) return;
    let vigente = true;
    setError("");
    api<PreviaImportacion>("/clientes/importar/previa", {
      method: "POST",
      body: JSON.stringify({ contenido, actuales }),
    })
      .then((r) => vigente && setPrevia(r))
      .catch((e) => {
        if (!vigente) return;
        setPrevia(null);
        setError((e as Error).message);
      });
    return () => {
      vigente = false;
    };
  }, [contenido, actuales]);
  const hayQueBorrar = actuales === "borrar" && !!previa?.borrar.length;
  const listo =
    !!previa &&
    !previa.errores &&
    !dirty &&
    (!hayQueBorrar || confirmacion.trim().toUpperCase() === "BORRAR");
  async function importar() {
    setOcupado(true);
    try {
      const r = await api<{
        importados: number;
        actualizados: number;
        nuevos: number;
        borrados: number;
        archivados: number;
        estado: EstadoConfig;
      }>("/clientes/importar", {
        method: "POST",
        body: JSON.stringify({ contenido, actuales, revision, confirmacion }),
      });
      onListo(r.estado);
      notify(
        `${r.actualizados} ${r.actualizados === 1 ? "cliente actualizado" : "clientes actualizados"} (conservan lo que recibieron), ${r.nuevos} ${r.nuevos === 1 ? "nuevo" : "nuevos"}` +
          (r.borrados ? `, ${r.borrados} borrados` : "") +
          (r.archivados ? `, ${r.archivados} archivados` : "") +
          ". Revísalos y pulsa «Programar para mañana».",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setOcupado(false);
    }
  }
  const modos = {
    remoto: "Remoto",
    hibrido: "Híbrido",
    presencial: "Presencial",
  };
  return (
    <Dialog
      titulo="Importar clientes"
      subtitulo="Sube un CSV con una fila por perfil. Nada se guarda hasta que pulses «Importar»."
      onClose={onClose}
      ancho
    >
      <div className="importar">
        <p className="field-help">
          Usa la plantilla: las listas van separadas por «|» y una celda vacía
          toma el mismo valor que un perfil nuevo (meta 10, remoto, español e
          inglés, 14 días).{" "}
          <a
            className="text-button"
            href="/api/clientes/plantilla.csv"
            download
          >
            Descargar plantilla
          </a>
        </p>
        <div className="field">
          <label htmlFor="importar-archivo">Archivo CSV</label>
          <input
            id="importar-archivo"
            type="file"
            accept=".csv,text/csv"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              setContenido(await f.text());
            }}
          />
        </div>
        <fieldset className="importar-actuales">
          <legend>
            ¿Qué hago con los clientes que no están en el archivo?
          </legend>
          <label>
            <input
              type="radio"
              name="actuales"
              checked={actuales === "mantener"}
              onChange={() => setActuales("mantener")}
            />
            Mantenerlos como están
          </label>
          <label>
            <input
              type="radio"
              name="actuales"
              checked={actuales === "archivar"}
              onChange={() => setActuales("archivar")}
            />
            Archivarlos (dejan de recibir; se pueden reactivar)
          </label>
          <label>
            <input
              type="radio"
              name="actuales"
              checked={actuales === "borrar"}
              onChange={() => setActuales("borrar")}
            />
            Borrarlos del todo
          </label>
          {hayQueBorrar && (
            <div className="importar-borrar">
              <p>
                Se quitan de la configuración junto con sus perfiles, su
                WhatsApp y sus mensajes preparados. No se puede deshacer. Las
                vacantes que ya recibieron y las versiones ya programadas se
                conservan en el historial.
              </p>
              <div className="field">
                <label htmlFor="importar-confirmar">
                  Escribe BORRAR para confirmar
                </label>
                <input
                  id="importar-confirmar"
                  value={confirmacion}
                  onChange={(e) => setConfirmacion(e.target.value)}
                  autoComplete="off"
                />
              </div>
            </div>
          )}
        </fieldset>
        {dirty && (
          <p className="importar-error" role="alert">
            Tienes cambios sin guardar. Guárdalos o recarga antes de importar.
          </p>
        )}
        {error && (
          <p className="importar-error" role="alert">
            {error}
          </p>
        )}
        {previa && (
          <section className="importar-previa" aria-label="Vista previa">
            <p className="importar-resumen">
              <b>
                {previa.clientes}{" "}
                {previa.clientes === 1 ? "cliente" : "clientes"}
              </b>{" "}
              con {previa.perfiles}{" "}
              {previa.perfiles === 1 ? "perfil" : "perfiles"}
              {previa.errores
                ? ` · ${previa.errores} ${previa.errores === 1 ? "error" : "errores"} por corregir`
                : " · sin errores"}
            </p>
            <p className="importar-resumen">
              {previa.actualizados.length}{" "}
              {previa.actualizados.length === 1
                ? "se actualiza"
                : "se actualizan"}{" "}
              (conservan lo que ya recibieron) · {previa.nuevos.length}{" "}
              {previa.nuevos.length === 1 ? "nuevo" : "nuevos"}
            </p>
            {previa.borrar.length > 0 && (
              <p className="importar-aviso">
                Se borrarán del todo: {previa.borrar.join(", ")}.
              </p>
            )}
            {previa.archivar.length > 0 && (
              <p className="importar-aviso">
                Se archivarán: {previa.archivar.join(", ")}.
              </p>
            )}
            {previa.cargos_nuevos.length > 0 && (
              <p className="importar-aviso">
                Cargos nuevos: {previa.cargos_nuevos.join(", ")}. Revisa sus
                nombres y usa «Proponer funciones».
              </p>
            )}
            {previa.excede_techo && previa.metas && (
              <p className="importar-aviso">
                Las metas suman {previa.metas.reales} y el techo del día es{" "}
                {previa.metas.techo}: antes de programar, sube el techo o baja
                metas.
              </p>
            )}
            {previa.columnas_desconocidas.length > 0 && (
              <p className="importar-aviso">
                Columnas que no se usan:{" "}
                {previa.columnas_desconocidas.join(", ")}.
              </p>
            )}
            {previa.error_general && (
              <p className="importar-error">{previa.error_general}</p>
            )}
            <ul className="importar-filas">
              {previa.filas.map((f) => (
                <li
                  key={f.fila}
                  className={f.errores.length ? "con-error" : ""}
                >
                  <span className="importar-fila-cabeza">
                    <span>
                      <b>{f.cliente || "Sin nombre"}</b> ·{" "}
                      {f.cargo || "Sin cargo"}{" "}
                      <em className="importar-estado">
                        {f.estado === "actualiza" ? "Se actualiza" : "Nuevo"}
                      </em>
                    </span>
                    <small>
                      Fila {f.fila}
                      {f.vive_en ? " · " + nombrePais(f.vive_en) : ""}
                      {f.modalidades.length
                        ? " · " +
                          f.modalidades
                            .map((m) => modos[m as keyof typeof modos] || m)
                            .join(", ")
                        : ""}
                      {f.meta != null ? ` · meta ${f.meta}` : ""}
                    </small>
                  </span>
                  {f.errores.map((e, i) => (
                    <span key={"e" + i} className="importar-error">
                      {e}
                    </span>
                  ))}
                  {f.avisos.map((a, i) => (
                    <span key={"a" + i} className="importar-nota">
                      {a}
                    </span>
                  ))}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
      <div className="dialog-actions">
        <button type="button" className="button secondary" onClick={onClose}>
          Cancelar
        </button>
        <button
          type="button"
          className="button primary"
          disabled={!listo || ocupado}
          onClick={importar}
        >
          <Upload size={16} />
          {ocupado
            ? "Importando…"
            : previa
              ? `Importar ${previa.clientes} ${previa.clientes === 1 ? "cliente" : "clientes"}`
              : "Importar"}
        </button>
      </div>
    </Dialog>
  );
}

// «Eliminar definitivamente» un cliente archivado (15 nov): pide escribir BORRAR.
function BorrarClienteDialog({
  cliente,
  revision,
  dirty,
  notify,
  onListo,
  onClose,
}: {
  cliente: Cliente;
  revision: number;
  dirty: boolean;
  notify: (s: string, error?: boolean) => void;
  onListo: (estado: EstadoConfig) => void;
  onClose: () => void;
}) {
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <Dialog titulo={`Eliminar «${cliente.nombre}»`} onClose={onClose}>
      <p className="dialog-copy">
        Se quita de la configuración junto con sus perfiles, su WhatsApp y sus
        mensajes preparados. No se puede deshacer. Las vacantes que ya recibió y
        las versiones ya programadas se conservan en el historial.
      </p>
      {dirty && (
        <p className="importar-error" role="alert">
          Tienes cambios sin guardar. Guárdalos antes de eliminar.
        </p>
      )}
      <div className="field">
        <label htmlFor="borrar-confirmar">Escribe BORRAR para confirmar</label>
        <input
          id="borrar-confirmar"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          autoComplete="off"
        />
      </div>
      <div className="dialog-actions">
        <button type="button" className="button secondary" onClick={onClose}>
          Cancelar
        </button>
        <button
          type="button"
          className="button danger-button"
          disabled={dirty || ocupado || texto.trim().toUpperCase() !== "BORRAR"}
          onClick={async () => {
            setOcupado(true);
            try {
              const r = await api<{ estado: EstadoConfig }>(
                `/clientes/${cliente.id}/borrar`,
                {
                  method: "POST",
                  body: JSON.stringify({ revision, confirmacion: texto }),
                },
              );
              onListo(r.estado);
              notify(`«${cliente.nombre}» se eliminó definitivamente.`);
            } catch (e) {
              notify((e as Error).message, true);
            } finally {
              setOcupado(false);
            }
          }}
        >
          Eliminar definitivamente
        </button>
      </div>
    </Dialog>
  );
}

function App() {
  const [sesion, setSesion] = useState<Sesion | null>(null),
    [estado, setEstado] = useState<EstadoConfig | null>(null),
    [draft, setDraft] = useState<Configuracion>(vacio),
    [dirty, setDirty] = useState(false),
    [tab, setTab] = useState(seccionDeHash),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [toast, setToast] = useState<{ texto: string; error: boolean } | null>(
      null,
    ),
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
  const [errorResultados, setErrorResultados] = useState(false);
  const [porConfirmar, setPorConfirmar] = useState(0);
  const [pendientesPorCliente, setPendientesPorCliente] = useState<
    Record<string, number>
  >({});
  const [porCliente, setPorCliente] = useState<ResumenClientes | null>(null);
  const [detalle, setDetalle] = useState("");
  const [importando, setImportando] = useState(false);
  const [aBorrar, setABorrar] = useState<Cliente | null>(null);
  function recibirEstado(e: EstadoConfig) {
    setEstado(e);
    setDraft(e.borrador);
    setDirty(false);
    setImportando(false);
    setABorrar(null);
    setSelectedClient(e.borrador.clientes.find((x) => x.activo)?.id || "");
  }
  const [borradoresHoy, setBorradoresHoy] = useState<Borrador[] | null>(null);
  const previaCargos = useVistaPrevia(
    tab === "Cargos y metas" && sesion?.sesion ? draft : null,
  );
  const metas = conMetas(draft),
    total = metas.total,
    excede = metas.reales > metas.techo,
    clientes = draft.clientes.filter((c) => c.activo),
    cargos = metas.cargos.filter((c) => c.activo);
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
      fijarMundo(s.paises_mundo || []);
      setSesion(s);
      if (s.sesion) {
        api<Revisiones>(PENDIENTES_RESUMEN)
          .then((r) => {
            setPorConfirmar(r.en_espera ?? r.total);
            setPendientesPorCliente(r.por_cliente || {});
          })
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
  // Las tarjetas del resumen se refrescan al volver a él (los mensajes o la bandeja pudieron cambiar).
  useEffect(() => {
    if (tab !== "Resumen" || !sesion?.sesion) return;
    api<{ borradores: Borrador[] }>("/borradores")
      .then((r) => setBorradoresHoy(r.borradores))
      .catch(() => setBorradoresHoy(null));
    recargarResumen();
  }, [tab, sesion?.sesion]);
  // Paso 8: recibidas de cada cliente en sus últimos 7 días y sus «por confirmar».
  function recargarResumen() {
    api<Revisiones>(PENDIENTES_RESUMEN)
      .then((r) => {
        setPorConfirmar(r.en_espera ?? r.total);
        setPendientesPorCliente(r.por_cliente || {});
      })
      .catch(() => undefined);
    api<ResumenClientes>("/resumen-clientes")
      .then(setPorCliente)
      .catch(() => setPorCliente(null));
  }
  // Auditoría H8: la pestaña del navegador dice en qué sección estás.
  useEffect(() => {
    document.title = tab + " · Scraper";
  }, [tab]);
  useEffect(() => {
    const seguir = () => setTab(seccionDeHash());
    window.addEventListener("hashchange", seguir);
    window.addEventListener("popstate", seguir);
    return () => {
      window.removeEventListener("hashchange", seguir);
      window.removeEventListener("popstate", seguir);
    };
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
    setErrorResultados(false);
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
      if (turno === peticionResultados.current) {
        setErrorResultados(true);
        notify((e as Error).message, true);
      }
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
  async function programar(hoyMismo = false) {
    setBusy(true);
    try {
      const e = dirty ? await guardar() : estado;
      if (!e) return;
      // Contrato v27: «Aplicar hoy» rige para las búsquedas que faltan hoy; lo ya entregado no cambia.
      const r = await api<{ revision: number; vigente_desde: string }>(
        hoyMismo ? "/config/aplicar-hoy" : "/config/publicar",
        { method: "POST", body: JSON.stringify({ revision: e.revision }) },
      );
      setEstado({
        ...e,
        publicada: { ...r, configuracion: structuredClone(e.borrador) },
      });
      setModal(null);
      notify(
        hoyMismo
          ? "Configuración aplicada desde hoy. La próxima búsqueda de hoy ya la usa."
          : "Configuración programada para el " + fecha(r.vigente_desde) + ".",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  const [descargandoBase, setDescargandoBase] = useState(false);
  // Reunión del 14 nov: CSV general o de un cliente, del día elegido o de toda la base, con el formato del contrato.
  const [csvFecha, setCsvFecha] = useState(hoyBogota());
  const [csvTodo, setCsvTodo] = useState(false);
  const [csvCliente, setCsvCliente] = useState("");
  async function descargarBase(soloCliente?: string) {
    // Desde el detalle de un cliente (paso 8): las de hoy de ese cliente.
    const cliente = soloCliente ?? csvCliente,
      todo = soloCliente ? false : csvTodo,
      dia = soloCliente ? hoyBogota() : csvFecha;
    setDescargandoBase(true);
    try {
      const q = new URLSearchParams();
      if (todo) q.set("todo", "true");
      else q.set("fecha", dia);
      if (cliente) q.set("cliente", cliente);
      const r = await fetch("/api/base.csv?" + q.toString(), {
        credentials: "same-origin",
      });
      if (!r.ok)
        throw new Error("No se pudo descargar el CSV. Inténtalo de nuevo.");
      const incluidas = r.headers.get("X-Incluidas") || "?";
      const omitidas = Number(r.headers.get("X-Omitidas-Sin-Confirmar") || 0);
      const sinFila = Number(r.headers.get("X-Sin-Fila") || 0);
      const nombreCliente = clientes.find((c) => c.id === cliente)?.nombre;
      const url = URL.createObjectURL(await r.blob());
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download =
        "vacantes-" +
        (todo ? "base" : dia) +
        "-" +
        (nombreCliente ? slug(nombreCliente) : "todas") +
        ".csv";
      enlace.click();
      URL.revokeObjectURL(url);
      const notas = [
        omitidas ? `${omitidas} sin confirmar quedaron fuera` : "",
        sinFila ? `${sinFila} sin ficha en la base (posts)` : "",
      ].filter(Boolean);
      notify(
        `CSV descargado: ${incluidas} vacantes${notas.length ? " (" + notas.join("; ") + ")" : ""}.`,
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setDescargandoBase(false);
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
    // La sección va en la URL (#clientes…): el botón atrás del navegador vuelve al resumen (sección 5, 13 nov).
    const h = secciones[t] ?? "";
    if (location.hash.replace(/^#/, "").split("/")[0] !== h) {
      if (h) location.hash = h;
      else history.pushState(null, "", location.pathname + location.search);
    }
    window.scrollTo(0, 0);
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
  return (
    <div className="app-shell">
      <div className="main-shell">
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
          {tab !== "Resumen" && (
            <div className="page-top">
              <button
                className="text-button volver"
                onClick={() => go("Resumen")}
              >
                <ArrowLeft size={15} />
                Volver al resumen
              </button>
            </div>
          )}
          <div className="page-heading">
            <div>
              <h1>{tab}</h1>
              <p>
                {tab === "Resumen"
                  ? "Organiza tus clientes y prepara las oportunidades de mañana."
                  : tab === "Clientes"
                    ? "Configura los criterios que hacen útil una vacante para cada cliente."
                    : tab === "Cargos y metas"
                      ? "Cada perfil tiene su meta diaria; aquí defines el techo del día y los cargos."
                      : tab === "Vacantes"
                        ? "Revisa las coincidencias de cada cliente y prepara su mensaje."
                        : tab === "Por confirmar"
                          ? "Vacantes que le servirían a tus clientes, pero cuyo país no se pudo confirmar solo. Decide con un clic: las que confirmes llegan hoy a sus clientes."
                          : tab === "Mensajes"
                            ? "Cada mañana cada persona tiene su mensaje con sus vacantes. Ábrelo en WhatsApp, revísalo y envíalo."
                            : tab === "Actividad"
                              ? "Cada día: cuántas vacantes trajo la búsqueda con tu configuración y qué cargos quedaron cortos."
                              : "Información sobre la conexión y el funcionamiento del espacio."}
              </p>
            </div>
            <div className="heading-actions">
              {["Resumen", "Clientes", "Cargos y metas"].includes(tab) && (
                <>
                  <span
                    className={
                      "flow-pill" +
                      (dirty ||
                      (estado?.revision &&
                        estado.publicada?.revision !== estado.revision)
                        ? " pending"
                        : "")
                    }
                  >
                    {textoProgramacion(estado, dirty)}
                  </span>
                  <button
                    className="button secondary"
                    onClick={guardarClick}
                    disabled={!dirty || busy}
                  >
                    <Save size={16} />
                    {busy ? "Guardando…" : "Guardar borrador"}
                  </button>
                  <Ayuda etiqueta="Guardar y programar">
                    <strong>Guardar borrador</strong> conserva tus cambios sin
                    tocar la próxima búsqueda.{" "}
                    <strong>Programar para mañana</strong> los guarda y los usa
                    desde la búsqueda de las 6:30 a. m. (hora Colombia); en ese
                    mismo cuadro, <strong>Aplicar hoy</strong> los usa desde la
                    próxima búsqueda de hoy. Las búsquedas que ya empezaron
                    siguen con la configuración anterior.
                  </Ayuda>
                  <button
                    className="button primary"
                    onClick={() => setModal("publicar")}
                    disabled={busy || total < 1 || excede}
                  >
                    <CalendarClock size={16} />
                    Programar para mañana
                  </button>
                </>
              )}
              <BotonTema />
              {!sesion.demo && (
                <button
                  className="button secondary boton-tema cerrar-sesion"
                  aria-label="Cerrar sesión"
                  title="Cerrar sesión"
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
          {tab === "Resumen" && (
            <>
              <AvisoUltimaBusqueda ultima={runs?.[0]} soloFallo />
              <TarjetasResumen
                clientes={resumenDeClientes(
                  draft,
                  porCliente,
                  pendientesPorCliente,
                )}
                diaConteo={porCliente?.dias.at(-1)?.fecha}
                onCliente={setDetalle}
                perfiles={
                  draft.perfiles.filter(
                    (p) =>
                      p.activo && clientes.some((c) => c.id === p.cliente_id),
                  ).length
                }
                cargos={cargos}
                total={total}
                techo={metas.techo}
                comunidad={metas.cabe}
                ultima={runs?.[0]}
                porConfirmar={porConfirmar}
                borradores={borradoresHoy}
                go={go}
              />
              {detalle &&
                (() => {
                  const c = resumenDeClientes(
                    draft,
                    porCliente,
                    pendientesPorCliente,
                  ).find((x) => x.id === detalle);
                  return c ? (
                    <ClienteDetalle
                      cliente={c}
                      cfg={draft}
                      dias={porCliente?.dias || []}
                      ultima={runs?.[0]}
                      notify={notify}
                      onCerrar={() => setDetalle("")}
                      onCambio={recargarResumen}
                      onVacantes={() => {
                        setDetalle("");
                        setSelectedClient(c.id);
                        go("Vacantes");
                      }}
                      onRevisar={() => {
                        setDetalle("");
                        go("Por confirmar");
                      }}
                      onCsv={() => descargarBase(c.id)}
                      onEditar={() => {
                        setDetalle("");
                        setEditCliente(
                          draft.clientes.find((x) => x.id === c.id) || null,
                        );
                        setModal("cliente");
                      }}
                      descargando={descargandoBase}
                    />
                  ) : null;
                })()}
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
                  className="button secondary"
                  onClick={() => setImportando(true)}
                >
                  <Upload size={16} />
                  Importar clientes
                </button>
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
              {importando && (
                <ImportarClientes
                  revision={estado?.revision ?? 0}
                  dirty={dirty}
                  notify={notify}
                  onListo={recibirEstado}
                  onClose={() => setImportando(false)}
                />
              )}
              {aBorrar && (
                <BorrarClienteDialog
                  cliente={aBorrar}
                  revision={estado?.revision ?? 0}
                  dirty={dirty}
                  notify={notify}
                  onListo={recibirEstado}
                  onClose={() => setABorrar(null)}
                />
              )}
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
                <Plegable
                  className="archived"
                  mostrar={
                    "Ver archivados (" +
                    draft.clientes.filter((c) => !c.activo).length +
                    ")"
                  }
                  ocultar="Ocultar archivados"
                >
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
                        <button
                          className="text-button peligro"
                          onClick={() => setABorrar(c)}
                        >
                          Eliminar definitivamente
                        </button>
                      </div>
                    ))}
                </Plegable>
              )}
            </>
          )}
          {tab === "Cargos y metas" && (
            <>
              <div className={"allocation card " + (excede ? "invalid" : "")}>
                <div className="field techo-campo">
                  <label htmlFor="techo-diario">Techo del día</label>
                  <CampoTecho
                    key={metas.techo}
                    valor={metas.techo}
                    onCambio={(n) => cambiar({ ...draft, techo_diario: n })}
                  />
                </div>
                <p className="allocation-texto">
                  <strong>{metas.reales}</strong> a clientes · {metas.cabe} a
                  Comunidad · {metas.libre} libres
                  {excede &&
                    " · Las metas de los clientes pasan el techo: baja metas o sube el techo"}
                </p>
                <Ayuda etiqueta="Techo del día">
                  Máximo de vacantes al día, para cuidar los consumos. Primero
                  se llenan las metas de los clientes reales; lo que sobre va al
                  cliente «Comunidad».
                </Ayuda>
                <div className="allocation-track">
                  <span
                    style={{
                      width:
                        Math.min((metas.reales / metas.techo) * 100, 100) + "%",
                    }}
                  />
                </div>
                <button
                  className="button secondary small"
                  onClick={() => {
                    setEditCargo(null);
                    setModal("cargo");
                  }}
                >
                  <Plus size={16} />
                  Añadir cargo
                </button>
              </div>
              <div className="cargos-tablero">
                <div className="role-list">
                  {[...cargos]
                    .sort((a, b) => b.cupo - a.cupo)
                    .map((c, i) => (
                      <section
                        className="role-card card"
                        key={c.id}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("text/plain", c.id);
                          e.dataTransfer.effectAllowed = "move";
                        }}
                      >
                        <div className="role-top">
                          <div
                            className="role-symbol"
                            style={{
                              color: colores[i % 5],
                              background: `color-mix(in srgb, ${colores[i % 5]} 10%, transparent)`,
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
                        <PreviewCargo
                          info={previaCargos.datos?.cargos?.[c.id]}
                          estado={previaCargos.estado}
                        />
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
                        <CifrasCargo
                          meta={c.cupo}
                          llegaron={llegaronHoy(runs?.[0], c.nombre)}
                          disponibles={
                            previaCargos.datos?.cargos?.[c.id]?.disponibles
                          }
                        />
                        {clientCount(c.id) === 0 && (
                          <p className="role-warning">
                            Sin perfiles: este cargo no busca hasta que un
                            cliente lo tenga.{" "}
                            <button
                              type="button"
                              className="text-button"
                              onClick={() => {
                                setArchive({
                                  tipo: "cargo",
                                  id: c.id,
                                  nombre: c.nombre,
                                });
                                setModal("archivo");
                              }}
                            >
                              Archivarlo
                            </button>
                          </p>
                        )}
                      </section>
                    ))}
                </div>
                <aside
                  className="cargos-archivados card"
                  aria-label="Cargos archivados"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const c = draft.cargos.find(
                      (x) => x.id === e.dataTransfer.getData("text/plain"),
                    );
                    if (c?.activo) {
                      setArchive({ tipo: "cargo", id: c.id, nombre: c.nombre });
                      setModal("archivo");
                    }
                  }}
                >
                  <h3>
                    <Archive size={16} />
                    Archivados ({draft.cargos.filter((c) => !c.activo).length})
                  </h3>
                  <p className="field-help">
                    Arrastra un cargo aquí para archivarlo, o usa su botón de
                    archivar. Vuelve solo si le asignas un perfil.
                  </p>
                  <ul>
                    {draft.cargos
                      .filter((c) => !c.activo)
                      .map((c) => (
                        <li key={c.id}>
                          <span>{c.nombre}</span>
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
                        </li>
                      ))}
                  </ul>
                </aside>
              </div>
              {previaCargos.datos?.nota && (
                <p className="helper note">{previaCargos.datos.nota}</p>
              )}
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
              {/* Lista grande, PR 3: «Oportunidades para» más angosto y el CSV arriba a la derecha. */}
              <div className="vacantes-cabecera">
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
                          [...clientes, ...(results?.clientes || [])].map(
                            (c) => [c.id, c],
                          ),
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
                <div className="csv-descarga card">
                  <div className="csv-titulo">
                    <strong>Descargar CSV</strong>
                    <Ayuda etiqueta="Descargar CSV">
                      Usa las columnas del contrato, listas para subir a la
                      plataforma de los candidatos. Una fila por vacante; no
                      incluye las que tienen el país sin confirmar.
                    </Ayuda>
                  </div>
                  <div className="field">
                    <label htmlFor="csv-fecha">Fecha</label>
                    <input
                      id="csv-fecha"
                      type="date"
                      value={csvFecha}
                      max={hoyBogota()}
                      disabled={csvTodo}
                      onChange={(e) =>
                        setCsvFecha(e.target.value || hoyBogota())
                      }
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="csv-cliente">Clientes</label>
                    <select
                      id="csv-cliente"
                      value={csvCliente}
                      onChange={(e) => setCsvCliente(e.target.value)}
                    >
                      <option value="">Todos los clientes</option>
                      {clientes.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nombre}
                        </option>
                      ))}
                    </select>
                  </div>
                  <label className="csv-todo">
                    <input
                      type="checkbox"
                      checked={csvTodo}
                      onChange={(e) => setCsvTodo(e.target.checked)}
                    />
                    Toda la base
                  </label>
                  <button
                    className="button secondary"
                    onClick={() => descargarBase()}
                    disabled={descargandoBase}
                  >
                    <ArrowDownToLine size={16} />
                    {descargandoBase ? "Descargando…" : "Descargar CSV"}
                  </button>
                </div>
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
                    Recargar lista
                  </button>
                  <Ayuda etiqueta="Recargar lista">
                    Vuelve a leer las vacantes de este día desde la base. No
                    busca vacantes nuevas ni vuelve a comprobar los enlaces: eso
                    lo hacen las búsquedas programadas.
                  </Ayuda>
                </div>
              </div>
              {results?.ejecucion && (
                <div className="results-date">
                  {sesion.demo ? "Captura simulada" : "Captura del"}{" "}
                  {fecha(results.ejecucion.fecha)}
                  <span>·</span>Solo se copian enlaces con comprobación vigente
                </div>
              )}
              {!loadingResults && !errorResultados && shown.length > 0 && (
                <ListaVacantes vacantes={shown} />
              )}
              {loadingResults && (
                <p role="status" className="helper">
                  Consultando vacantes…
                </p>
              )}
              {/* Auditoría H1: un fallo no se confunde con «no hay vacantes». */}
              {!loadingResults && errorResultados && (
                <Empty
                  icon={BriefcaseBusiness}
                  title="No se pudieron cargar las vacantes"
                  texto="El panel no recibió respuesta del servidor. Revisa tu conexión y vuelve a intentarlo; tu configuración no cambió."
                  action={cargarResultados}
                  actionIcon={RefreshCw}
                  label="Reintentar"
                />
              )}
              {!loadingResults && !errorResultados && !shown.length && (
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
              clientes={draft.clientes.filter((c) => c.activo)}
              notify={notify}
              onCambio={setPorConfirmar}
            />
          )}
          {tab === "Mensajes" && (
            <Mensajes clientes={draft.clientes} notify={notify} />
          )}
          {tab === "Actividad" && <AvisoUltimaBusqueda ultima={runs?.[0]} />}
          {tab === "Actividad" && (
            <section className="card activity">
              <div className="section-title">
                <h2>Resultado de cada búsqueda diaria</h2>
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
                runs.map((r, n) => (
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
                        <EmbudoCargos
                          embudo={r.resumen.embudo}
                          abierto={n === 0}
                        />
                      )}
                    </div>
                    <span
                      className={
                        "pill " + (r.estado === "completa" ? "green" : "amber")
                      }
                    >
                      {estadosEjecucion[r.estado] || r.estado}
                    </span>
                  </div>
                ))
              )}
            </section>
          )}
          {tab === "Actividad" && <ReglasAprendidas notify={notify} />}
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
          onCrearCargo={(nuevo) =>
            cambiar({ ...draft, cargos: [...draft.cargos, nuevo] })
          }
          onSave={(c, ps) => {
            // Lista grande del 16 nov: un cargo archivado vuelve solo cuando se le asigna un perfil.
            const usados = new Set(
              ps.filter((p) => p.activo).map((p) => p.cargo_id),
            );
            cambiar({
              ...draft,
              cargos: draft.cargos.map((x) =>
                !x.activo && usados.has(x.id) ? { ...x, activo: true } : x,
              ),
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
            <span>Total del día</span>
            <strong>
              {total} / {metas.techo}
            </strong>
          </div>
          <p className="helper note">
            Al confirmar se guardan tus cambios y esta configuración se usa
            desde la búsqueda del <strong>{fecha(manana())}</strong> a las 6:30
            a. m. (hora Colombia). La de hoy, si ya empezó, conserva la
            anterior.
            {!estado?.publicada &&
              " Es tu primera configuración: desde entonces dejan de buscarse los seis cargos fijos anteriores; solo se buscarán los cargos de esta lista."}{" "}
            Si las fuentes no ofrecen suficientes vacantes válidas, verás el
            faltante; no se rellena con duplicados ni con vacantes fuera de los
            filtros.
          </p>
          <p className="helper note">
            <strong>Aplicar hoy</strong> la usa desde la próxima búsqueda de hoy
            (la manual, la de las 8:30 o la de cada hora). Lo que ya se entregó
            hoy no cambia.
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
              className="button secondary"
              disabled={busy}
              onClick={() => programar(true)}
            >
              <Zap size={16} />
              Aplicar hoy
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => programar()}
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
            {archive.tipo === "cliente"
              ? `Desde la próxima búsqueda programada, «${archive.nombre}» deja de recibir vacantes. Las vacantes que ya recibió se conservan y puedes reactivarlo cuando quieras.`
              : `Desde la próxima búsqueda programada se deja de buscar «${archive.nombre}». Las vacantes ya entregadas se conservan.`}
          </p>
          {archive.tipo === "cargo" && clientCount(archive.id) > 0 && (
            <p className="role-warning" role="alert">
              Atención: {clientCount(archive.id)}{" "}
              {clientCount(archive.id) === 1
                ? "cliente tiene"
                : "clientes tienen"}{" "}
              este cargo. Dejarán de recibir sus vacantes hasta que vuelvas a
              activarlo o les asignes otro.
            </p>
          )}
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
                notify(
                  "Archivado en el borrador. Sus vacantes ya recibidas se conservan.",
                );
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
// Avisos dentro del panel, sin correo ni servicios externos (decisión del operador, 13 nov).
// Lista grande del 16 nov: en el Resumen el aviso solo aparece si la búsqueda falló; lo demás vive en «Actividad».
function AvisoUltimaBusqueda({
  ultima,
  soloFallo = false,
}: {
  ultima?: Ejecucion;
  soloFallo?: boolean;
}) {
  if (!ultima || (soloFallo && ultima.estado !== "fallida")) return null;
  const r = ultima.resumen || {};
  const faltan = Object.entries(r.faltantes || {})
    .filter(([, n]) => n > 0)
    .map(([cargo]) => cargo);
  const corta =
    ultima.estado === "parcial" ||
    (r.meta !== undefined && (r.vacantes ?? 0) < r.meta);
  if (ultima.estado !== "fallida" && !corta) return null;
  return (
    <div className="aviso-busqueda" role="status">
      <strong>
        {ultima.estado === "fallida"
          ? `La búsqueda del ${fecha(ultima.fecha)} falló.`
          : `La búsqueda del ${fecha(ultima.fecha)} trajo ${r.vacantes ?? 0} de ${r.meta ?? 120} vacantes.`}
      </strong>{" "}
      {ultima.estado === "fallida"
        ? "Revisa «Actividad»; la siguiente búsqueda lo intentará de nuevo."
        : faltan.length
          ? `Faltan vacantes en ${faltan.join(", ")}: revisa los filtros de sus clientes en «Dónde se pierden las vacantes de cada cargo».`
          : ""}
    </div>
  );
}
// Lista grande del 16 nov: el techo se puede borrar del todo mientras se escribe; se valida al salir del campo.
function CampoTecho({
  valor,
  onCambio,
}: {
  valor: number;
  onCambio: (n: number) => void;
}) {
  // Se reinicia con `key` cuando cambia el valor guardado (sin efecto que copie el estado).
  const [texto, setTexto] = useState(String(valor));
  const confirmar = () => {
    const n = Math.round(Number(texto));
    if (!texto.trim() || !Number.isFinite(n)) return setTexto(String(valor));
    const limitado = Math.max(1, Math.min(600, n));
    setTexto(String(limitado));
    if (limitado !== valor) onCambio(limitado);
  };
  return (
    <input
      id="techo-diario"
      type="text"
      inputMode="numeric"
      pattern="[0-9]*"
      value={texto}
      onChange={(e) => setTexto(e.target.value.replace(/[^0-9]/g, ""))}
      onBlur={confirmar}
      onKeyDown={(e) => e.key === "Enter" && confirmar()}
    />
  );
}

function llegaronHoy(ultima: Ejecucion | undefined, cargo: string) {
  if (!ultima || ultima.fecha !== hoyBogota()) return undefined;
  return ultima.resumen?.embudo?.[cargo]?.entregadas;
}

// Lista grande del 16 nov: tres cifras por cargo, con su explicación a mano.
function CifrasCargo({
  meta,
  llegaron,
  disponibles,
}: {
  meta: number;
  llegaron?: number;
  disponibles?: number;
}) {
  return (
    <dl className="cifras-cargo">
      <div>
        <dt>
          Meta del día
          <Ayuda etiqueta="Meta del día">
            Suma de las metas diarias de los perfiles de este cargo.
          </Ayuda>
        </dt>
        <dd>{meta}</dd>
      </div>
      <div>
        <dt>
          Llegaron hoy
          <Ayuda etiqueta="Llegaron hoy">
            Vacantes de este cargo que entregó la búsqueda de hoy. Antes de las
            6:30 a. m. aparece «—».
          </Ayuda>
        </dt>
        <dd>{llegaron ?? "—"}</dd>
      </div>
      <div>
        <dt>
          Para mañana
          <Ayuda etiqueta="Disponibles para mañana">
            Estimación: vacantes ya guardadas, aún no entregadas, que cumplen
            algún perfil de este cargo. La búsqueda de mañana suma otras nuevas.
          </Ayuda>
        </dt>
        <dd>{disponibles ?? "—"}</dd>
      </div>
    </dl>
  );
}

// Lista grande del 16 nov: «Programado desde» confundía. Se dice qué pasa con la próxima búsqueda, en palabras.
function textoProgramacion(estado: EstadoConfig | null, dirty: boolean) {
  if (dirty) return "Cambios sin guardar";
  if (!estado?.revision) return "Sin configuración programada";
  const p = estado.publicada;
  if (!p || p.revision !== estado.revision) return "Hay cambios sin programar";
  return p.vigente_desde > hoyBogota()
    ? "Lista: se usa desde la búsqueda de mañana"
    : "En uso desde el " + fecha(p.vigente_desde);
}
function ClientCard({
  c,
  perfiles,
  cargos,
  paises,
  onEdit,
  onResults,
  onArchive,
}: {
  c: Cliente;
  index?: number;
  perfiles: Perfil[];
  cargos: Cargo[];
  paises: Sesion["paises"];
  onEdit: () => void;
  onResults: () => void;
  onArchive?: () => void;
}) {
  // Sección 7a (13 nov): más baja, sin foto ni «Activo»; editar y vacantes a la vista.
  const p = perfiles[0],
    cargo = cargos.find((x) => x.id === p?.cargo_id);
  return (
    <article className="client-card card">
      <div className="client-top">
        <div className="client-title">
          <h3>
            {c.nombre}
            {c.comunidad && <DistintivoComunidad />}
          </h3>
          <span>
            {cargo?.nombre || "Sin perfil"}
            {perfiles.length > 1 ? " + " + (perfiles.length - 1) : ""}
          </span>
        </div>
        {p && (
          <div className="client-lugar">
            <span>
              {paises.find((x) => x.codigo === p.vive_en)?.nombre ||
                nombrePais(p.vive_en)}
              {p.paises_presenciales_extra.length > 0 &&
                " +" + p.paises_presenciales_extra.length}
            </span>
            <span>{p.modalidades.map((m) => modos[m]).join(" · ")}</span>
          </div>
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
            {p?.experiencia_anos != null
              ? `${p.experiencia_anos} años · busca de ${p.experiencia_min} a ${p.experiencia_max}`
              : p?.experiencia_min === null && p?.experiencia_max === null
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
        <button
          className="text-button editar"
          aria-label={"Editar " + c.nombre}
          onClick={onEdit}
        >
          <Pencil size={14} />
          Editar
        </button>
        {onArchive && (
          <button
            className="icon peligro"
            aria-label={"Archivar " + c.nombre}
            title="Archivar"
            onClick={onArchive}
          >
            <Archive size={15} />
          </button>
        )}
        {!(cargo?.activo && perfiles.some((p) => (p.meta_diaria ?? 1) > 0)) && (
          <span className="pill amber sin-cupo">Sin meta</span>
        )}
        <button className="button secondary small vacantes" onClick={onResults}>
          Vacantes
          <ArrowUpRight size={14} />
        </button>
      </div>
    </article>
  );
}
// Reunión del 14 nov: un fallo al pintar dejaba la pantalla en blanco y se perdía lo escrito. Ahora se muestra qué
// pasó; el borrador del cliente sigue en este navegador y se ofrece al volver a abrir el formulario.
class Protector extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Fallo del panel:", error, info.componentStack);
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="fallo" role="alert">
        <h1>Algo falló al mostrar esta pantalla</h1>
        <p>
          Lo que estabas escribiendo de un cliente quedó guardado en este
          navegador: al abrir otra vez su formulario podrás recuperarlo.
        </p>
        <p className="fallo-detalle">Detalle: {this.state.error.message}</p>
        <button
          type="button"
          className="button primary"
          onClick={() => window.location.reload()}
        >
          Volver a cargar el panel
        </button>
      </main>
    );
  }
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Protector>
      <App />
    </Protector>
  </React.StrictMode>,
);
