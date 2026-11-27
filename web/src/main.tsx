import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  Upload,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Archive,
  BriefcaseBusiness,
  Moon,
  Sun,
  Check,
  CheckCheck,
  Clock3,
  Code2,
  Copy,
  Globe2,
  Loader2,
  LogOut,
  MapPin,
  MessageCircle,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Target,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { api } from "./api";
import { delSistema, guardarTema, temaElegido, type Tema } from "./tema";
import type {
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
  Revisiones,
  ResumenClientes,
} from "./types";
import {
  Ayuda,
  Dialog,
  Empty,
  Plegable,
  colores,
  fecha,
  fijarLugares,
  fijarMundo,
  hoyBogota,
  modos,
  nombrePais,
} from "./comunes";
import { PorConfirmar } from "./vistas/PorConfirmar";
import { BuscarAhora } from "./vistas/BuscarAhora";
import { Mensajes } from "./vistas/Mensajes";
import { CargoDialog } from "./vistas/CargoDialog";
import { ClienteDetalle } from "./vistas/ClienteDetalle";
import { ClienteDialog } from "./vistas/ClienteFormulario";
import { conMetas, perfilSinCiudad } from "./perfiles";
import { useVistaPrevia, type EstadoPrevia } from "./vistaPrevia";
import { ListaVacantes } from "./vistas/Vacantes";
import {
  DistintivoComunidad,
  TarjetasResumen,
  resumenDeClientes,
} from "./vistas/Resumen";
import {
  ImportarClientes,
  BorrarClienteDialog,
} from "./vistas/ImportarClientes";
import { Historial, AvisoUltimaBusqueda } from "./vistas/Historial";
import "./style.css";

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
// Por qué no hay vacantes: sin configuración, a la espera de la primera búsqueda o sin coincidencias.
function vacioVacantes(estado: EstadoConfig | null, r: Resultados | null) {
  if (!estado?.publicada)
    return {
      title: "Aplica la configuración para empezar",
      texto:
        "Las vacantes de cada cliente aparecen después de la primera búsqueda (6:30 a. m.) con su configuración. Revisa «Clientes» y «Cargos y metas» y pulsa «Aplicar cambios».",
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
      <Target size={12} />
      {/* Lista grande (17 nov): cuántos días alcanza lo guardado, en vez de «≈ 136 guardadas sin entregar». */}
      {!info.cupo ? (
        textoEstadoCargo[info.estado]
      ) : info.disponibles >= info.cupo ? (
        <>
          Alcanza para{" "}
          <b>
            ~{Math.floor(info.disponibles / info.cupo)}{" "}
            {Math.floor(info.disponibles / info.cupo) === 1 ? "día" : "días"}
          </b>
        </>
      ) : (
        <>
          No alcanza para mañana: faltan <b>{info.cupo - info.disponibles}</b>
        </>
      )}
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
        Hay {info.disponibles} vacantes ya guardadas, aún no entregadas, que
        cumplen algún perfil de este cargo, y su meta es de {info.cupo} al día.
        Cada noche la búsqueda trae más.
        {!!info.solapes?.length &&
          " Las que sirven a dos cargos se reparten por turnos según lo que le falta a cada uno. Mejor un solo cargo con varios perfiles."}
      </Ayuda>
    </div>
  );
}

// Contrato v22: prioridades que solo ordenan y restricciones que descartan con evidencia clara.
// Sección 5 (13 nov): sin menú propio; cada sección tiene su dirección y se abre desde las tarjetas del resumen.
const secciones: Record<string, string> = {
  Resumen: "",
  Clientes: "clientes",
  "Cargos y metas": "cargos",
  Vacantes: "vacantes",
  "Por confirmar": "por-confirmar",
  Mensajes: "mensajes",
  Historial: "historial",
};
function seccionDeHash() {
  // Contrato v29: «#vacantes/<id>» recuerda la vacante abierta; la sección es lo que va antes de la barra.
  const h = decodeURIComponent(location.hash.replace(/^#\/?/, "")).split(
    "/",
  )[0];
  // «#actividad» (nombre anterior de Historial) sigue abriendo la misma sección.
  const clave = h === "actividad" ? "historial" : h;
  return (
    Object.keys(secciones).find((t) => secciones[t] === clave) || "Resumen"
  );
}

// Contrato v29: el Resumen pide una página corta; el total y el conteo por cliente cubren todas las pendientes.
const PENDIENTES_RESUMEN = "/revisiones?pagina=1&por_pagina=1";

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

// Compara dos configuraciones por su contenido, sin importar el orden de las claves.
function ordenado(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(ordenado);
  if (v && typeof v === "object")
    return Object.fromEntries(
      Object.keys(v as Record<string, unknown>)
        .sort()
        .map((k) => [k, ordenado((v as Record<string, unknown>)[k])]),
    );
  return v;
}
function mismoContenido(a: unknown, b: unknown) {
  return JSON.stringify(ordenado(a)) === JSON.stringify(ordenado(b));
}

function App() {
  const [sesion, setSesion] = useState<Sesion | null>(null),
    [estado, setEstado] = useState<EstadoConfig | null>(null),
    [draft, setDraft] = useState<Configuracion>(vacio),
    [marcado, setDirty] = useState(false),
    [tab, setTab] = useState(seccionDeHash),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [toast, setToast] = useState<{
      texto: string;
      error: boolean;
      accion?: { texto: string; hacer: () => void };
    } | null>(null),
    // Contrato v49: por qué no se pudo dejar en uso lo guardado (se ve junto al botón hasta aplicar bien).
    [noAplica, setNoAplica] = useState(""),
    // Contrato v49: «Buscar ahora» disponible (el servidor tiene la llave de GitHub).
    [puedeBuscar, setPuedeBuscar] = useState(false),
    [modal, setModal] = useState<
      "cliente" | "cargo" | "publicar" | "archivo" | "whatsapp" | null
    >(null),
    [editCliente, setEditCliente] = useState<Cliente | null>(null),
    [editCargo, setEditCargo] = useState<Cargo | null>(null),
    [borrarCargo, setBorrarCargo] = useState<Cargo | null>(null),
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
    // Contrato v43 (regla 7): el operador elige cuántas copiar; con más de 10 se copia en partes.
    [cuantasWhats, setCuantasWhats] = useState("10"),
    [partesWhats, setPartesWhats] = useState<string[]>([]),
    [parteCopiada, setParteCopiada] = useState<number | null>(null),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const peticionResultados = useRef(0);
  // Contrato v48: al llegar desde «Tomar vacantes» del detalle, el foco queda en «Copiar WhatsApp».
  const enfocarWhatsApp = useRef(false);
  const botonWhatsApp = useRef<HTMLButtonElement>(null);
  const [focoWhatsApp, setFocoWhatsApp] = useState(0);
  const [notaWhats, setNotaWhats] = useState("");
  const [loadingResults, setLoadingResults] = useState(false);
  const [errorResultados, setErrorResultados] = useState(false);
  const [porConfirmar, setPorConfirmar] = useState(0);
  // Sesión de prueba (17 nov): quién inició sesión, visible arriba.
  // Contrato v30: los WhatsApp se cargan con el panel para que el formulario del cliente abra sin esperar.
  const [contactos, setContactos] = useState<Record<string, Contacto>>({});
  function cargarContactos() {
    api<Record<string, Contacto>>("/contactos")
      .then(setContactos)
      .catch(() => undefined);
  }
  // Se guarda sin hacer esperar al formulario: se ve al momento y, si falla, se avisa y se vuelve a leer.
  function guardarContacto(id: string, ct: Contacto, tenia: boolean) {
    const borrar = !ct.telefono.trim();
    setContactos((actuales) => {
      const copia = { ...actuales };
      if (borrar) delete copia[id];
      else copia[id] = ct;
      return copia;
    });
    if (borrar && !tenia) return;
    api(
      "/contactos/" + id,
      borrar
        ? { method: "DELETE" }
        : { method: "PUT", body: JSON.stringify(ct) },
    ).catch((e) => {
      notify("No se guardó el WhatsApp: " + (e as Error).message, true);
      cargarContactos();
    });
  }
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
  // Lista grande (17 nov): hay cambios solo si lo editado es distinto de lo guardado. Si deshaces lo que cambiaste,
  // vuelve a «sin cambios» y no pide aplicar otra vez.
  const dirty = useMemo(
    () => marcado && mismoContenido(draft, estado?.borrador) === false,
    [marcado, draft, estado?.borrador],
  );
  const metas = conMetas(draft),
    total = metas.total,
    excede = metas.reales > metas.techo,
    clientes = draft.clientes.filter((c) => c.activo),
    cargos = metas.cargos.filter((c) => c.activo);
  // Contrato v49: cambios que la próxima búsqueda aún no usa (sin guardar, o guardados pero sin aplicar porque algo
  // lo impidió, o importados). El botón «Aplicar cambios» de la cabecera solo aparece entonces.
  const pendienteDeAplicar =
    dirty ||
    Boolean(estado?.revision && estado.publicada?.revision !== estado.revision);
  async function aplicarPendientes() {
    return (await aplicar()).aplicado;
  }
  function notify(
    texto: string,
    error = false,
    accion?: { texto: string; hacer: () => void },
  ) {
    setToast({ texto, error, accion });
  }
  useEffect(() => {
    if (toast) {
      const t = setTimeout(
        () => setToast(null),
        toast.error || toast.accion ? 12000 : 5000,
      );
      return () => clearTimeout(t);
    }
  }, [toast]);
  async function cargar() {
    setLoading(true);
    setError("");
    try {
      const s = await api<Sesion>("/session");
      fijarMundo(s.paises_mundo || []);
      fijarLugares(s.ciudades_por_pais, s.utc_paises);
      setSesion(s);
      if (s.sesion) {
        cargarContactos();
        api<{ disponible: boolean }>("/busqueda")
          .then((b) => setPuedeBuscar(Boolean(b.disponible)))
          .catch(() => setPuedeBuscar(false));
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
    // 17 nov: una segunda búsqueda del día actualiza la de hoy; sin esto, el Resumen mostraba la de la mañana hasta
    // volver a cargar la página.
    api<Ejecucion[]>("/ejecuciones")
      .then(setRuns)
      .catch(() => undefined);
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
      if (turno === peticionResultados.current) {
        setResults(r);
        // Contrato v48: al llegar desde «Tomar vacantes», el foco va a «Copiar WhatsApp» con los datos de ese día.
        if (enfocarWhatsApp.current) setFocoWhatsApp((n) => n + 1);
      }
    } catch (e) {
      if (turno === peticionResultados.current) {
        setErrorResultados(true);
        notify((e as Error).message, true);
      }
    } finally {
      if (turno === peticionResultados.current) {
        setLoadingResults(false);
        enfocarWhatsApp.current = false;
      }
    }
  }
  // Contrato v46 (velocidad): las vacantes solo se piden en su pestaña; antes, entrar por #mensajes también las pedía.
  const enVacantes = tab === "Vacantes";
  useEffect(() => {
    if (enVacantes) cargarResultados();
  }, [selectedClient, resultDate, sesion?.sesion, enVacantes]);
  useEffect(() => {
    if (focoWhatsApp) botonWhatsApp.current?.focus();
  }, [focoWhatsApp]);
  // Contrato v48: el servidor dice si es de un día anterior y cuántas se pueden copiar.
  const diaResultados = (results?.ejecucion?.fecha || "").slice(0, 10);
  const diaAnterior = Boolean(results?.dia_anterior);
  const paraCopiar = results?.para_copiar ?? results?.listas ?? 0;
  function cambiar(v: Configuracion) {
    setDraft(v);
    setDirty(true);
  }
  // Contrato v49 (pedido de Oscar, 26 nov): un solo «Aplicar cambios» que guarda (PUT /config) y deja en uso
  // (POST /config/publicar, rige desde hoy: la próxima búsqueda ya lo usa; lo entregado no cambia). Si guardar
  // falla, nada cambia y se dice por qué. Si guarda pero no se puede dejar en uso (p. ej. metas por encima del
  // techo), los cambios quedan guardados, el motivo queda a la vista y el botón de la cabecera sigue pendiente.
  async function aplicar(
    config: Configuracion = draft,
    exito = "Cambios aplicados: la próxima búsqueda los usa.",
  ): Promise<{ guardado: boolean; aplicado: boolean; motivo: string }> {
    if (!estado)
      return { guardado: false, aplicado: false, motivo: "Recarga la página." };
    setBusy(true);
    let actual = estado;
    try {
      if (!mismoContenido(config, estado.borrador)) {
        const r = await api<
          Partial<EstadoConfig> & { revision: number; borrador: Configuracion }
        >("/config", {
          method: "PUT",
          body: JSON.stringify({
            revision: estado.revision,
            configuracion: config,
          }),
        });
        actual = { ...estado, ...r };
        setEstado(actual);
      }
      // También cuando lo pedido ya era lo guardado (p. ej. reactivar lo que se había archivado sin aplicar).
      setDraft(actual.borrador);
      setDirty(false);
    } catch (e) {
      const motivo = (e as Error).message;
      notify("No se guardaron los cambios: " + motivo, true);
      setBusy(false);
      return { guardado: false, aplicado: false, motivo };
    }
    try {
      // Lo que se sabe sin preguntar al servidor (el mismo cálculo que `validar_publicacion`).
      const m = conMetas(actual.borrador);
      if (m.reales > m.techo)
        throw new Error(
          `Las metas suman ${m.reales} y el cupo diario es ${m.techo}: baja algunas metas o sube el cupo diario en «Cargos y metas», y vuelve a pulsar «Aplicar cambios».`,
        );
      if (m.total < 1)
        throw new Error(
          "Ningún perfil activo tiene meta diaria: da una meta a algún perfil y vuelve a pulsar «Aplicar cambios».",
        );
      const r = await api<{ revision: number; vigente_desde: string }>(
        "/config/publicar",
        { method: "POST", body: JSON.stringify({ revision: actual.revision }) },
      );
      const primera = !actual.publicada;
      setEstado({
        ...actual,
        publicada: { ...r, configuracion: structuredClone(actual.borrador) },
      });
      setNoAplica("");
      notify(
        exito +
          (primera
            ? " Desde ahora solo se buscan los cargos de tu lista (no los seis fijos de antes)."
            : ""),
      );
      return { guardado: true, aplicado: true, motivo: "" };
    } catch (e) {
      const motivo = (e as Error).message;
      setNoAplica(motivo);
      notify(
        "Tus cambios quedaron guardados, pero la búsqueda todavía no los usa: " +
          motivo,
        true,
      );
      return { guardado: true, aplicado: false, motivo };
    } finally {
      setBusy(false);
    }
  }
  const [descargandoBase, setDescargandoBase] = useState(false);
  const [abriendoWhatsApp, setAbriendoWhatsApp] = useState(false);
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
          {/* Sesión de prueba (17 nov): un solo recorrido de lectura, marca → título → campos → botón. */}
          <h1>Inicia sesión</h1>
          <p>Las vacantes correctas para cada persona.</p>
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
              <label htmlFor="email">Correo electrónico</label>
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
            Solo entran las personas autorizadas.
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
                  ? "Organiza tus clientes y prepara sus oportunidades de cada día."
                  : tab === "Clientes"
                    ? "Configura los criterios que hacen útil una vacante para cada cliente."
                    : tab === "Cargos y metas"
                      ? "Cada perfil tiene su meta diaria; aquí defines el cupo diario y los cargos."
                      : tab === "Vacantes"
                        ? "Revisa las coincidencias de cada cliente y prepara su mensaje."
                        : tab === "Por confirmar"
                          ? "Vacantes que le servirían a tus clientes, pero cuyo país no se pudo confirmar solo. Decide con un clic: las que confirmes llegan hoy a sus clientes."
                          : tab === "Mensajes"
                            ? "Cada mañana cada persona tiene su mensaje con sus vacantes. Ábrelo en WhatsApp, revísalo y envíalo."
                            : tab === "Historial"
                              ? "Cada día: cuántas vacantes trajo la búsqueda con tu configuración y qué cargos quedaron cortos."
                              : "Información sobre la conexión y el funcionamiento del espacio."}
              </p>
            </div>
            <div className="heading-actions">
              {["Resumen", "Clientes", "Cargos y metas"].includes(tab) && (
                <>
                  <span
                    className={
                      "flow-pill" + (pendienteDeAplicar ? " pending" : "")
                    }
                  >
                    {pendienteDeAplicar
                      ? "Cambios sin aplicar"
                      : "En uso desde la próxima búsqueda"}
                  </span>
                  {tab === "Resumen" && (
                    <BuscarAhora
                      sinAplicar={pendienteDeAplicar}
                      onAplicar={aplicarPendientes}
                      revision={estado?.publicada?.revision}
                      demo={Boolean(sesion.demo)}
                      onAviso={notify}
                      onTermino={recargarResumen}
                    />
                  )}
                  {pendienteDeAplicar && (
                    <button
                      className="button primary"
                      onClick={() => aplicar()}
                      disabled={busy}
                    >
                      {busy ? (
                        <Loader2 size={16} className="spin" />
                      ) : (
                        <Check size={16} />
                      )}
                      {busy ? "Aplicando…" : "Aplicar cambios"}
                    </button>
                  )}
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
          {noAplica &&
            pendienteDeAplicar &&
            ["Resumen", "Clientes", "Cargos y metas"].includes(tab) && (
              <p className="form-error aviso-no-aplica" role="alert">
                <b>
                  Tus cambios están guardados, pero la búsqueda aún no los usa.
                </b>{" "}
                {noAplica}
                {noAplica.includes("Aplicar cambios")
                  ? ""
                  : " Cuando lo arregles, pulsa «Aplicar cambios»."}
              </p>
            )}
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
                reales={metas.reales}
                comunidad={metas.comunidad}
                ultima={runs?.[0]}
                porConfirmar={porConfirmar}
                borradores={borradoresHoy}
                go={go}
                onNuevoCliente={() => {
                  setEditCliente(null);
                  setModal("cliente");
                }}
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
                      onVacantes={(dia) => {
                        setDetalle("");
                        setSelectedClient(c.id);
                        if (dia) {
                          setResultDate(dia);
                          enfocarWhatsApp.current = true;
                        }
                        go("Vacantes");
                      }}
                      onRevisar={() => {
                        setDetalle("");
                        go("Por confirmar");
                      }}
                      onCsv={() => descargarBase(c.id)}
                      buscarAhora={
                        <BuscarAhora
                          cliente={{ id: c.id, nombre: c.nombre }}
                          sinAplicar={pendienteDeAplicar}
                          onAplicar={aplicarPendientes}
                          revision={estado?.publicada?.revision}
                          demo={Boolean(sesion.demo)}
                          onAviso={notify}
                          onTermino={recargarResumen}
                        />
                      }
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
                  <label htmlFor="techo-diario">Cupo diario</label>
                  <CampoTecho
                    key={metas.techo}
                    valor={metas.techo}
                    onCambio={(n) => cambiar({ ...draft, techo_diario: n })}
                  />
                </div>
                <p className="allocation-texto">
                  <strong>{metas.reales}</strong> a clientes
                  {metas.comunidad > 0 &&
                    ` · Comunidad hasta ${metas.comunidad}`}{" "}
                  · {metas.libre} libres
                  {excede &&
                    " · Las metas de los clientes pasan el cupo diario: baja metas o sube el cupo"}
                </p>
                <Ayuda etiqueta="Cupo diario">
                  Máximo de vacantes al día entre todos, para cuidar los
                  consumos. Primero se llenan las metas de los clientes; el
                  grupo «Comunidad» recibe después, de lo que sobre, y solo
                  hasta su meta.
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
                          {c.terminos_similares.slice(0, 1).map((t) => (
                            <span className="term readonly" key={t}>
                              {t}
                            </span>
                          ))}
                          {c.terminos_similares.length > 1 && (
                            <span
                              className="terminos-mas"
                              title={c.terminos_similares.slice(1).join(", ")}
                            >
                              +{c.terminos_similares.length - 1}{" "}
                              {c.terminos_similares.length === 2
                                ? "nombre más"
                                : "nombres más"}
                            </span>
                          )}
                          {!c.terminos_similares.length && (
                            <span className="solo-nombre">
                              Solo busca «{c.nombre}». En «Editar», pulsa
                              «Buscar denominaciones afines» para sumar nombres
                              en inglés y parecidos.
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
                  {/* 18 nov: cuarta columna a la derecha; arriba «Archivados» y debajo una tarjeta por cargo. */}
                  <div className="archivados-titulo">
                    <Archive size={15} />
                    Archivados ({draft.cargos.filter((c) => !c.activo).length})
                    <span className="archivados-ayuda">
                      Arrastra un cargo aquí para archivarlo.
                    </span>
                  </div>
                  {draft.cargos
                    .filter((c) => !c.activo)
                    .map((c) => (
                      <div className="archivado-ficha" key={c.id}>
                        <strong>{c.nombre}</strong>
                        <span className="archivado-acciones">
                          <button
                            type="button"
                            className="button secondary"
                            aria-label={"Reactivar " + c.nombre}
                            onClick={() =>
                              cambiar({
                                ...draft,
                                cargos: draft.cargos.map((x) =>
                                  x.id === c.id ? { ...x, activo: true } : x,
                                ),
                              })
                            }
                          >
                            <RotateCcw size={14} />
                            Reactivar
                          </button>
                          <button
                            type="button"
                            className="button secondary peligro"
                            aria-label={"Eliminar definitivamente " + c.nombre}
                            onClick={() => setBorrarCargo(c)}
                          >
                            <Trash2 size={14} />
                            Eliminar
                          </button>
                        </span>
                      </div>
                    ))}
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
                      {/* Lista grande (17 nov): solo los clientes de hoy; los de configuraciones anteriores (CSV viejo) ya no
                          aparecen con «pendiente». */}
                      {clientes.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nombre}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="results-count">
                    <strong>{paraCopiar}</strong>
                    <span>
                      {diaAnterior
                        ? "de ese día (se comprueban al copiar)"
                        : "listas para compartir"}
                    </span>
                  </div>
                  <label className="cuantas-whatsapp">
                    Cuántas
                    <input
                      type="number"
                      min={1}
                      max={Math.max(1, paraCopiar || 1)}
                      value={cuantasWhats}
                      // Thermos (18 nov): el campo se puede vaciar mientras se escribe; vacío vale 10.
                      onChange={(e) => setCuantasWhats(e.target.value)}
                    />
                  </label>
                  <button
                    ref={botonWhatsApp}
                    className="button whatsapp"
                    disabled={
                      !selectedClient ||
                      !paraCopiar ||
                      busy ||
                      loadingResults ||
                      abriendoWhatsApp
                    }
                    aria-busy={abriendoWhatsApp || undefined}
                    onClick={abrirWhatsApp}
                  >
                    <MessageCircle size={18} />
                    {abriendoWhatsApp
                      ? diaAnterior
                        ? "Comprobando enlaces…"
                        : "Preparando…"
                      : "Copiar WhatsApp"}
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
                  {/* Contrato v48: cualquier día en un calendario, como en la descarga del CSV. */}
                  <label className="fecha-resultados">
                    <span className="visually-hidden">Día de la búsqueda</span>
                    <input
                      type="date"
                      aria-label="Día de la búsqueda"
                      value={resultDate || diaResultados}
                      max={hoyBogota()}
                      onChange={(e) => setResultDate(e.target.value)}
                    />
                  </label>
                  {resultDate &&
                    results &&
                    !loadingResults &&
                    !results.ejecucion && (
                      <span className="fecha-sin-busqueda" role="status">
                        Ese día no hubo búsqueda.
                      </span>
                    )}
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
                    lo hacen las búsquedas de cada día.
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
          {tab === "Historial" && (
            <Historial
              runs={runs}
              setRuns={setRuns}
              sesion={sesion}
              notify={notify}
            />
          )}
        </main>
      </div>
      {modal === "cargo" && (
        <CargoDialog
          cargo={editCargo}
          notify={notify}
          onClose={() => setModal(null)}
          onSave={async (c) => {
            const nuevo = !draft.cargos.some((x) => x.id === c.id);
            // Contrato v49: «Aplicar cambios» del formulario guarda y deja en uso de verdad.
            const r = await aplicar(
              {
                ...draft,
                cargos: nuevo
                  ? [...draft.cargos, c]
                  : draft.cargos.map((x) => (x.id === c.id ? c : x)),
              },
              (nuevo ? "Cargo añadido." : "Cargo actualizado.") +
                " Cambios aplicados: la próxima búsqueda los usa.",
            );
            if (r.guardado) setModal(null);
            return r.guardado;
          }}
        />
      )}
      {modal === "cliente" && (
        <ClienteDialog
          cliente={editCliente}
          config={draft}
          contacto={editCliente ? contactos[editCliente.id] : undefined}
          onClose={() => setModal(null)}
          onGuardarContacto={guardarContacto}
          onCrearCargo={(nuevo) =>
            cambiar({ ...draft, cargos: [...draft.cargos, nuevo] })
          }
          onSave={async (c, ps) => {
            // Lista grande del 16 nov: un cargo archivado vuelve solo cuando se le asigna un perfil.
            const usados = new Set(
              ps.filter((p) => p.activo).map((p) => p.cargo_id),
            );
            const nuevo = !draft.clientes.some((x) => x.id === c.id);
            // Contrato v49: «Aplicar cambios» del formulario guarda y deja en uso de verdad.
            const r = await aplicar(
              {
                ...draft,
                cargos: draft.cargos.map((x) =>
                  !x.activo && usados.has(x.id) ? { ...x, activo: true } : x,
                ),
                clientes: nuevo
                  ? [...draft.clientes, c]
                  : draft.clientes.map((x) => (x.id === c.id ? c : x)),
                perfiles: [
                  ...draft.perfiles.filter((p) => p.cliente_id !== c.id),
                  ...ps,
                ],
              },
              (nuevo ? "Cliente añadido." : "Cliente actualizado.") +
                " Cambios aplicados: la próxima búsqueda los usa.",
            );
            if (!r.guardado) return r.motivo;
            setModal(null);
            // Contrato v49: al crear un cliente, ofrecer buscar ya para él (desde su detalle en el Resumen).
            if (nuevo && r.aplicado && puedeBuscar && c.activo)
              notify(
                `Cliente añadido. Cambios aplicados: la próxima búsqueda los usa. También puedes buscar ya para «${c.nombre}».`,
                false,
                {
                  texto: "Buscar ahora para este cliente",
                  hacer: () => {
                    go("Resumen");
                    setDetalle(c.id);
                  },
                },
              );
            return null;
          }}
        />
      )}
      {borrarCargo && (
        <Dialog
          titulo={"Eliminar " + borrarCargo.nombre}
          subtitulo="Se quita de la configuración para siempre. Lo ya entregado y el historial se conservan."
          onClose={() => setBorrarCargo(null)}
        >
          {(() => {
            const suyos = draft.perfiles.filter(
              (p) => p.cargo_id === borrarCargo.id,
            ).length;
            return (
              <p className="helper">
                {suyos
                  ? `También se quitan ${suyos} ${suyos === 1 ? "perfil de cliente que buscaba" : "perfiles de clientes que buscaban"} este cargo; sus clientes conservan los demás perfiles.`
                  : "Ningún cliente busca este cargo."}{" "}
                Se aplica al pulsar «Aplicar cambios».
              </p>
            );
          })()}
          <div className="dialog-actions">
            <button
              className="button secondary"
              onClick={() => setBorrarCargo(null)}
            >
              Cancelar
            </button>
            <button
              className="button danger-button"
              onClick={() => {
                const id = borrarCargo.id;
                cambiar({
                  ...draft,
                  cargos: draft.cargos.filter((x) => x.id !== id),
                  perfiles: draft.perfiles.filter((p) => p.cargo_id !== id),
                });
                notify(
                  `«${borrarCargo.nombre}» se eliminó. Pulsa «Aplicar cambios» para que la búsqueda lo use.`,
                );
                setBorrarCargo(null);
              }}
            >
              <Trash2 size={16} />
              Eliminar definitivamente
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
              ? `Cuando pulses «Aplicar cambios», «${archive.nombre}» deja de recibir vacantes desde la próxima búsqueda. Las vacantes que ya recibió se conservan y puedes reactivarlo cuando quieras.`
              : `Cuando pulses «Aplicar cambios», se deja de buscar «${archive.nombre}» desde la próxima búsqueda. Las vacantes ya entregadas se conservan.`}
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
                  "Archivado. Sus vacantes ya recibidas se conservan. Pulsa «Aplicar cambios» para que la búsqueda lo use.",
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
            Los enlaces se vuelven a contrastar al preparar el mensaje. Copiar
            no envía nada ni confirma una postulación.
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
      )}
      {toast && (
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
      )}
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

// «3:32 p. m.» en hora de Colombia, de la hora en que terminó la última búsqueda.

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
  // Contrato v49: perfiles con presencial o híbrido sin ciudad (no les llegan esas vacantes).
  const sinCiudad = perfiles.filter(perfilSinCiudad).length;
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
        {sinCiudad > 0 && (
          <div className="falta-ciudad">
            <MapPin size={14} aria-hidden="true" />
            <span>
              Falta la ciudad
              {perfiles.length > 1
                ? ` en ${sinCiudad} ${sinCiudad === 1 ? "perfil" : "perfiles"}`
                : ""}
              : sin ciudad no llegan presenciales ni híbridas.
            </span>
          </div>
        )}
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
