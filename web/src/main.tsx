import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  ArrowRight,
  Archive,
  Moon,
  Sun,
  Check,
  CheckCheck,
  Copy,
  Loader2,
  LogOut,
  MessageCircle,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { api } from "./api";
import { delSistema, guardarTema, temaElegido, type Tema } from "./tema";
import type {
  Cargo,
  Cliente,
  Configuracion,
  EstadoConfig,
  Resultados,
  Sesion,
  Ejecucion,
  Borrador,
  Contacto,
  Revisiones,
  ResumenClientes,
} from "./types";
import { Dialog, fijarLugares, fijarMundo } from "./comunes";
import { PorConfirmar } from "./vistas/PorConfirmar";
import { BuscarAhora } from "./vistas/BuscarAhora";
import { Mensajes } from "./vistas/Mensajes";
import { CargoDialog } from "./vistas/CargoDialog";
import { ClienteDetalle } from "./vistas/ClienteDetalle";
import { ClienteDialog } from "./vistas/ClienteFormulario";
import { conMetas } from "./perfiles";
import { useVistaPrevia } from "./vistaPrevia";
import { TarjetasResumen, resumenDeClientes } from "./vistas/Resumen";
import { Historial, AvisoUltimaBusqueda } from "./vistas/Historial";
import { CargosYMetas } from "./vistas/CargosYMetas";
import { Clientes } from "./vistas/Clientes";
import { SeccionVacantes } from "./vistas/SeccionVacantes";
import { useDescargaCsv } from "./descargaCsv";
import "./style.css";

const vacio: Configuracion = { clientes: [], cargos: [], perfiles: [] };
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
  const {
    descargandoBase,
    csvFecha,
    setCsvFecha,
    csvTodo,
    setCsvTodo,
    csvCliente,
    setCsvCliente,
    descargarBase,
  } = useDescargaCsv(clientes, notify);
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
            <Clientes
              draft={draft}
              cambiar={cambiar}
              estado={estado}
              dirty={dirty}
              sesion={sesion}
              clientes={clientes}
              profiles={profiles}
              search={search}
              setSearch={setSearch}
              importando={importando}
              setImportando={setImportando}
              aBorrar={aBorrar}
              setABorrar={setABorrar}
              recibirEstado={recibirEstado}
              notify={notify}
              setEditCliente={setEditCliente}
              setSelectedClient={setSelectedClient}
              setArchive={setArchive}
              setModal={setModal}
              go={go}
            />
          )}
          {tab === "Cargos y metas" && (
            <CargosYMetas
              draft={draft}
              cambiar={cambiar}
              metas={metas}
              excede={excede}
              cargos={cargos}
              clientCount={clientCount}
              previaCargos={previaCargos}
              runs={runs}
              setEditCargo={setEditCargo}
              setBorrarCargo={setBorrarCargo}
              setArchive={setArchive}
              setModal={setModal}
            />
          )}
          {tab === "Vacantes" && (
            <SeccionVacantes
              sesion={sesion}
              estado={estado}
              clientes={clientes}
              selectedClient={selectedClient}
              setSelectedClient={setSelectedClient}
              resultDate={resultDate}
              setResultDate={setResultDate}
              diaResultados={diaResultados}
              results={results}
              shown={shown}
              loadingResults={loadingResults}
              errorResultados={errorResultados}
              cargarResultados={cargarResultados}
              search={search}
              setSearch={setSearch}
              busy={busy}
              paraCopiar={paraCopiar}
              diaAnterior={diaAnterior}
              cuantasWhats={cuantasWhats}
              setCuantasWhats={setCuantasWhats}
              botonWhatsApp={botonWhatsApp}
              abriendoWhatsApp={abriendoWhatsApp}
              abrirWhatsApp={abrirWhatsApp}
              csvFecha={csvFecha}
              setCsvFecha={setCsvFecha}
              csvTodo={csvTodo}
              setCsvTodo={setCsvTodo}
              csvCliente={csvCliente}
              setCsvCliente={setCsvCliente}
              descargandoBase={descargandoBase}
              descargarBase={descargarBase}
            />
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
