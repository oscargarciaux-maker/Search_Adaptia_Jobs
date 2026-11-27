// «Vacantes» (dividido de main.tsx): elegir el cliente, copiar su WhatsApp, descargar el CSV y ver la lista del día.
import React from "react";
import {
  ArrowDownToLine,
  BriefcaseBusiness,
  MessageCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import type {
  Cliente,
  EstadoConfig,
  Resultados,
  Sesion,
  Vacante,
} from "../types";
import { Ayuda, Empty, fecha, hoyBogota } from "../comunes";
import { ListaVacantes } from "./Vacantes";

export function SeccionVacantes({
  sesion,
  estado,
  clientes,
  selectedClient,
  setSelectedClient,
  resultDate,
  setResultDate,
  diaResultados,
  results,
  shown,
  loadingResults,
  errorResultados,
  cargarResultados,
  search,
  setSearch,
  busy,
  paraCopiar,
  diaAnterior,
  cuantasWhats,
  setCuantasWhats,
  botonWhatsApp,
  abriendoWhatsApp,
  abrirWhatsApp,
  csvFecha,
  setCsvFecha,
  csvTodo,
  setCsvTodo,
  csvCliente,
  setCsvCliente,
  descargandoBase,
  descargarBase,
}: {
  sesion: Sesion;
  estado: EstadoConfig | null;
  clientes: Cliente[];
  selectedClient: string;
  setSelectedClient: (id: string) => void;
  resultDate: string;
  setResultDate: (d: string) => void;
  diaResultados: string;
  results: Resultados | null;
  shown: Vacante[];
  loadingResults: boolean;
  errorResultados: boolean;
  cargarResultados: () => void;
  search: string;
  setSearch: (s: string) => void;
  busy: boolean;
  paraCopiar: number;
  diaAnterior: boolean;
  cuantasWhats: string;
  setCuantasWhats: (s: string) => void;
  botonWhatsApp: React.RefObject<HTMLButtonElement | null>;
  abriendoWhatsApp: boolean;
  abrirWhatsApp: () => void;
  csvFecha: string;
  setCsvFecha: (d: string) => void;
  csvTodo: boolean;
  setCsvTodo: (v: boolean) => void;
  csvCliente: string;
  setCsvCliente: (id: string) => void;
  descargandoBase: boolean;
  descargarBase: (soloCliente?: string) => void;
}) {
  return (
    <>
      {/* Lista grande, PR 3: «Oportunidades para» más angosto y el CSV arriba a la derecha. */}
      <div className="vacantes-cabecera">
        <div className="results-control card">
          <div className="field">
            <label htmlFor="result-cliente">MOSTRAR OPORTUNIDADES PARA</label>
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
              Usa las columnas del contrato, listas para subir a la plataforma
              de los candidatos. Una fila por vacante; no incluye las que tienen
              el país sin confirmar.
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
              onChange={(e) => setCsvFecha(e.target.value || hoyBogota())}
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
          {resultDate && results && !loadingResults && !results.ejecucion && (
            <span className="fecha-sin-busqueda" role="status">
              Ese día no hubo búsqueda.
            </span>
          )}
          <button className="button secondary" onClick={cargarResultados}>
            <RefreshCw size={15} />
            Recargar lista
          </button>
          <Ayuda etiqueta="Recargar lista">
            Vuelve a leer las vacantes de este día desde la base. No busca
            vacantes nuevas ni vuelve a comprobar los enlaces: eso lo hacen las
            búsquedas de cada día.
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
        <Empty icon={BriefcaseBusiness} {...vacioVacantes(estado, results)} />
      )}
    </>
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
