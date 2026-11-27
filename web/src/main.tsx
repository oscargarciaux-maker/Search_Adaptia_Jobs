import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Check, Loader2, ShieldCheck, X } from "lucide-react";
import { api } from "./api";
import type {
  Cargo,
  Cliente,
  EstadoConfig,
  Resultados,
  Sesion,
  Ejecucion,
  Borrador,
  Contacto,
  Revisiones,
  ResumenClientes,
} from "./types";
import { fijarLugares, fijarMundo } from "./comunes";
import { PorConfirmar } from "./vistas/PorConfirmar";
import { Mensajes } from "./vistas/Mensajes";
import { CargoDialog } from "./vistas/CargoDialog";
import { ClienteDialog } from "./vistas/ClienteFormulario";
import { conMetas } from "./perfiles";
import { useVistaPrevia } from "./vistaPrevia";
import { Historial } from "./vistas/Historial";
import { CargosYMetas } from "./vistas/CargosYMetas";
import { Clientes } from "./vistas/Clientes";
import { SeccionVacantes } from "./vistas/SeccionVacantes";
import { useDescargaCsv } from "./descargaCsv";
import { useWhatsApp, DialogoWhatsApp } from "./vistas/DialogoWhatsApp";
import { EliminarCargoDialog, ArchivarDialog } from "./vistas/DialogosArchivo";
import { InicioSesion } from "./vistas/InicioSesion";
import { Cabecera } from "./vistas/Cabecera";
import { useConfiguracion } from "./configuracion";
import { SeccionResumen } from "./vistas/SeccionResumen";
import "./style.css";

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

function App() {
  const [sesion, setSesion] = useState<Sesion | null>(null),
    [tab, setTab] = useState(seccionDeHash),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [toast, setToast] = useState<{
      texto: string;
      error: boolean;
      accion?: { texto: string; hacer: () => void };
    } | null>(null),
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
    [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const {
    estado,
    setEstado,
    draft,
    setDraft,
    setDirty,
    dirty,
    busy,
    setBusy,
    noAplica,
    pendienteDeAplicar,
    aplicarPendientes,
    cambiar,
    aplicar,
  } = useConfiguracion(notify);
  const peticionResultados = useRef(0);
  // Contrato v48: al llegar desde «Tomar vacantes» del detalle, el foco queda en «Copiar WhatsApp».
  const enfocarWhatsApp = useRef(false);
  const botonWhatsApp = useRef<HTMLButtonElement>(null);
  const [focoWhatsApp, setFocoWhatsApp] = useState(0);
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
  const metas = conMetas(draft),
    total = metas.total,
    excede = metas.reales > metas.techo,
    clientes = draft.clientes.filter((c) => c.activo),
    cargos = metas.cargos.filter((c) => c.activo);
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
  const {
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
  } = useWhatsApp(selectedClient, resultDate, notify, setModal);
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
      <InicioSesion
        email={email}
        setEmail={setEmail}
        password={password}
        setPassword={setPassword}
        busy={busy}
        setBusy={setBusy}
        error={error}
        setError={setError}
        cargar={cargar}
      />
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
          <Cabecera
            sesion={sesion}
            setSesion={setSesion}
            setEstado={setEstado}
            tab={tab}
            go={go}
            estado={estado}
            busy={busy}
            noAplica={noAplica}
            pendienteDeAplicar={pendienteDeAplicar}
            aplicar={aplicar}
            aplicarPendientes={aplicarPendientes}
            notify={notify}
            recargarResumen={recargarResumen}
          />
          {tab === "Resumen" && (
            <SeccionResumen
              sesion={sesion}
              estado={estado}
              draft={draft}
              clientes={clientes}
              cargos={cargos}
              metas={metas}
              total={total}
              runs={runs}
              porCliente={porCliente}
              pendientesPorCliente={pendientesPorCliente}
              porConfirmar={porConfirmar}
              borradoresHoy={borradoresHoy}
              detalle={detalle}
              setDetalle={setDetalle}
              go={go}
              notify={notify}
              recargarResumen={recargarResumen}
              setEditCliente={setEditCliente}
              setModal={setModal}
              setSelectedClient={setSelectedClient}
              setResultDate={setResultDate}
              enfocarWhatsApp={enfocarWhatsApp}
              descargarBase={descargarBase}
              descargandoBase={descargandoBase}
              pendienteDeAplicar={pendienteDeAplicar}
              aplicarPendientes={aplicarPendientes}
            />
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
        <EliminarCargoDialog
          borrarCargo={borrarCargo}
          setBorrarCargo={setBorrarCargo}
          draft={draft}
          cambiar={cambiar}
          notify={notify}
        />
      )}
      {modal === "archivo" && archive && (
        <ArchivarDialog
          archive={archive}
          clientCount={clientCount}
          setModal={setModal}
          draft={draft}
          cambiar={cambiar}
          notify={notify}
        />
      )}
      {modal === "whatsapp" && (
        <DialogoWhatsApp
          notaWhats={notaWhats}
          partesWhats={partesWhats}
          parteCopiada={parteCopiada}
          mensaje={mensaje}
          copiado={copiado}
          copiar={copiar}
          setModal={setModal}
        />
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
