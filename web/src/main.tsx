import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Loader2 } from "lucide-react";
import { api } from "./api";
import type {
  Cargo,
  Cliente,
  EstadoConfig,
  Sesion,
  Ejecucion,
  Borrador,
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
import { DialogoWhatsApp } from "./vistas/DialogoWhatsApp";
import { useWhatsApp } from "./whatsapp";
import { EliminarCargoDialog, ArchivarDialog } from "./vistas/DialogosArchivo";
import { InicioSesion } from "./vistas/InicioSesion";
import { Cabecera } from "./vistas/Cabecera";
import { useConfiguracion } from "./configuracion";
import { Resumen } from "./vistas/Resumen";
import { useResultados } from "./resultados";
import { useContactos } from "./contactos";
import { Protector } from "./vistas/Protector";
import { Aviso } from "./vistas/Aviso";
import { secciones, seccionDeHash } from "./secciones";
import "./style.css";

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
  const {
    results,
    enfocarWhatsApp,
    botonWhatsApp,
    loadingResults,
    errorResultados,
    cargarResultados,
    diaResultados,
    diaAnterior,
    paraCopiar,
  } = useResultados(sesion, selectedClient, resultDate, tab, notify);
  const { contactos, cargarContactos, guardarContacto } = useContactos(notify);
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
            <Resumen
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
      {toast && <Aviso toast={toast} setToast={setToast} />}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Protector>
      <App />
    </Protector>
  </React.StrictMode>,
);
