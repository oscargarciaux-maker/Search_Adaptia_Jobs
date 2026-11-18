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
  Download,
  Moon,
  Sun,
  CalendarClock,
  Check,
  CheckCheck,
  Clock3,
  Code2,
  Copy,
  Globe2,
  Loader2,
  LogOut,
  MessageCircle,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
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
  Revision,
  Revisiones,
  ResumenClientes,
  PreviaImportacion,
} from "./types";
import {
  Ayuda,
  Dialog,
  Empty,
  Plegable,
  REGIONES,
  fecha,
  fijarLugares,
  fijarMundo,
  modos,
  nombrePais,
} from "./comunes";
import { PorConfirmar } from "./vistas/PorConfirmar";
import { TarjetaPorConfirmar } from "./vistas/TarjetaPorConfirmar";
import { BuscarAhora } from "./vistas/BuscarAhora";
import { Mensajes } from "./vistas/Mensajes";
import {
  CoberturaPersonas,
  EmbudoDelDia,
  ReglasAprendidas,
} from "./vistas/Actividad";
import { CargoDialog } from "./vistas/CargoDialog";
import { ClienteDialog } from "./vistas/ClienteFormulario";
import { conMetas } from "./perfiles";
import { useVistaPrevia, type EstadoPrevia } from "./vistaPrevia";
import { ListaVacantes } from "./vistas/Vacantes";
import "./style.css";

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
// Por qué no hay vacantes: sin configuración, a la espera de la primera búsqueda o sin coincidencias.
function vacioVacantes(estado: EstadoConfig | null, r: Resultados | null) {
  if (!estado?.publicada)
    return {
      title: "Programa la configuración para empezar",
      texto:
        "Las vacantes de cada cliente aparecen después de la primera búsqueda (6:30 a. m.) con su configuración. Ve a «Cargos y metas» y pulsa «Confirmar y aplicar».",
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
const estadosEjecucion: Record<string, string> = {
  completa: "Completada",
  parcial: "Con faltantes",
  fallida: "Requiere revisión",
  en_curso: "En curso",
};

// Resumen con jerarquía (13 nov, pedido de Oscar): Clientes y Cargos y cupos mandan; Vacantes, Por confirmar y
// Mensajes acompañan; Actividad es una franja tipo «entrada de evento» con la próxima búsqueda. La rejilla no es
// uniforme a propósito: tamaños distintos y una franja desplazada guían la mirada de lo más usado a lo demás.
// La próxima búsqueda de hoy en palabras: la de las 8:30 a. m. si aún no pasó; si no, la próxima de cada hora.
function textoProximaDeHoy(ahora = new Date()) {
  const ochoYMedia = new Date(
    Date.UTC(
      ahora.getUTCFullYear(),
      ahora.getUTCMonth(),
      ahora.getUTCDate(),
      13,
      30,
    ),
  );
  const seisYMedia = new Date(ochoYMedia.getTime() - 2 * 3600 * 1000);
  if (ahora < seisYMedia) return "la de las 6:30 a. m.";
  if (ahora < ochoYMedia) return "la de las 8:30 a. m.";
  return "la próxima captura de cada hora (a los 23 minutos)";
}

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
      title="Grupo de WhatsApp: recibe solo lo que sobra del cupo diario, después de los clientes"
    >
      <Users size={11} aria-hidden="true" />
      Comunidad
    </span>
  );
}

// El techo del día como dona (lista grande, 17 nov): cada cargo es un tramo con su color; el centro dice lo usado.
function DonaTecho({
  partes,
  total,
  usado,
}: {
  partes: { valor: number; color: string }[];
  total: number;
  usado: number;
}) {
  const r = 42;
  const largo = 2 * Math.PI * r;
  // Dónde empieza cada tramo: la suma de los anteriores (calculada antes de pintar).
  const tramos = partes.map((p) => (largo * p.valor) / Math.max(1, total));
  const inicios = tramos.map((_, i) =>
    tramos.slice(0, i).reduce((a, b) => a + b, 0),
  );
  return (
    <svg
      className="dona-techo"
      viewBox="0 0 104 104"
      role="img"
      aria-label={`Cupo diario: ${usado} de ${total} repartidas por cargo`}
    >
      <circle cx="52" cy="52" r={r} className="dona-fondo" />
      {partes.map((p, i) => (
        <circle
          key={i}
          cx="52"
          cy="52"
          r={r}
          stroke={p.color}
          strokeDasharray={`${Math.max(0, tramos[i] - 2)} ${largo}`}
          strokeDashoffset={-inicios[i]}
          transform="rotate(-90 52 52)"
        />
      ))}
      <text x="52" y="55" textAnchor="middle" className="dona-cifra">
        {usado}
      </text>
      <text x="52" y="70" textAnchor="middle" className="dona-sub">
        de {total}
      </text>
    </svg>
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
  reales,
  comunidad,
  ultima,
  porConfirmar,
  borradores,
  go,
  onNuevoCliente,
}: {
  clientes: ResumenCliente[];
  diaConteo?: string;
  onCliente: (id: string) => void;
  perfiles: number;
  cargos: Cargo[];
  total: number;
  techo: number;
  reales: number;
  comunidad: number;
  ultima?: Ejecucion;
  porConfirmar: number;
  borradores: Borrador[] | null;
  go: (t: string) => void;
  onNuevoCliente: () => void;
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
    <section className="resumen-grid resumen-b" aria-label="Resumen del panel">
      <div className="resumen-arriba">
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
            Cupo diario
          </span>
          <div className="cupos-fila">
            <strong className="tarjeta-numero">
              {total}
              <small> / {techo}</small>
            </strong>
            <span className="tarjeta-detalle">
              {/* Contrato v43: Comunidad recibe de lo que sobra y hasta su meta, aunque no ocupe cupo. */}
              {reales} a clientes
              {comunidad > 0 && ` · Comunidad hasta ${comunidad}`}
            </span>
          </div>
          <span className="cupos-dona-fila">
            <DonaTecho
              partes={conCupo.map((c, i) => ({
                valor: c.cupo,
                color: colores[i % 5],
              }))}
              total={Math.max(total, techo)}
              usado={total}
            />
            <span className="cupos-leyenda">
              {conCupo.map((c, i) => (
                <span key={c.id}>
                  <i style={{ background: colores[i % 5] }} />
                  {c.nombre} <b>{c.cupo}</b>
                </span>
              ))}
            </span>
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
            {ultima ? (r.vacantes_vigentes ?? r.vacantes ?? 0) : "—"}
            {ultima && r.meta ? <small> / {r.meta}</small> : null}
          </strong>
          <span className="tarjeta-detalle">
            {ultima
              ? `Del cupo, en la búsqueda del ${fecha(ultima.fecha)}` +
                (ultima.terminada_en
                  ? ` · actualizada ${horaBogota(ultima.terminada_en)}`
                  : "")
              : "Sin búsquedas aún"}
          </span>
          {ultima && (r.vacantes_anteriores ?? 0) > 0 && (
            <span className="tarjeta-detalle">
              +{r.vacantes_anteriores} de cargos que ya cambiaste hoy
            </span>
          )}
          <span className="tarjeta-accion">
            Ver vacantes
            <ArrowRight size={14} />
          </span>
        </button>

        <button
          type="button"
          className="tarjeta-resumen tarjeta-actividad"
          onClick={() => go("Historial")}
        >
          <span className="evento-fecha" aria-hidden="true">
            <b>{dia}</b>
            <span>{mes}</span>
          </span>
          <span className="evento-texto">
            <span className="tarjeta-cabeza">
              <Clock3 size={15} />
              Historial
            </span>
            <span className="evento-titulo">
              Próxima búsqueda: {semana} {dia} de {mes} · 6:30 a. m.
            </span>
            <span className="tarjeta-detalle">
              {ultima
                ? `Última, del ${fecha(ultima.fecha)}: ${r.vacantes_vigentes ?? r.vacantes ?? 0} vacantes` +
                  (diaConteo && bajos
                    ? ` · ${bajos} ${bajos === 1 ? "cliente" : "clientes"} bajo su meta`
                    : "")
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
            Ver historial
            <ArrowRight size={14} />
          </span>
        </button>
        {/* 18 nov: los 3 pasos del día, uno sobre otro, a la derecha del historial. */}
        <ol className="pasos-dia" aria-label="Tu día en 3 pasos">
          <li>
            <button
              type="button"
              className={"paso-dia" + (porConfirmar ? " pendiente" : "")}
              onClick={() => go("Por confirmar")}
            >
              <span className="paso-numero" aria-hidden="true">
                1
              </span>
              <span className="paso-texto">
                <strong>Revisa las dudosas</strong>
                <span>
                  {porConfirmar
                    ? `${porConfirmar} por confirmar`
                    : "Nada por confirmar"}
                </span>
              </span>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={
                "paso-dia" +
                (vivos.length && enviados < vivos.length ? " pendiente" : "")
              }
              onClick={() => go("Mensajes")}
            >
              <span className="paso-numero" aria-hidden="true">
                2
              </span>
              <span className="paso-texto">
                <strong>Envía los mensajes</strong>
                <span>
                  {!borradores
                    ? "Ábrelos para prepararlos"
                    : vivos.length
                      ? `${vivos.length - enviados} por enviar de ${vivos.length}`
                      : "Aún no hay mensajes de hoy"}
                </span>
              </span>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={"paso-dia" + (bajos ? " pendiente" : "")}
              onClick={() => go("Clientes")}
            >
              <span className="paso-numero" aria-hidden="true">
                3
              </span>
              <span className="paso-texto">
                <strong>Ajusta clientes y cargos</strong>
                <span>
                  {diaConteo && bajos
                    ? `${bajos} ${bajos === 1 ? "cliente bajo su meta" : "clientes bajo su meta"}`
                    : "Solo cuando haga falta"}
                </span>
              </span>
            </button>
          </li>
        </ol>
      </div>
      <div className="tarjeta-resumen tarjeta-clientes">
        <span className="tarjeta-cabeza clientes-cabeza">
          <span>
            <Users size={18} />
            Clientes
          </span>
          <button
            type="button"
            className="button secondary nuevo-cliente"
            onClick={onNuevoCliente}
          >
            <Plus size={16} />
            Nuevo cliente
          </button>
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
                  ? `— de ${c.meta}`
                  : `${c.recibidas} de ${c.meta}`;
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
                    {/* 18 nov: la cifra grande arriba a la derecha; «por confirmar» como alerta con su número. */}
                    <span className="cliente-arriba">
                      <span className="cliente-texto">
                        <strong>
                          {c.nombre}
                          {c.porConfirmar > 0 && (
                            <span
                              className="cliente-alerta"
                              title={pendiente}
                              aria-hidden="true"
                            >
                              {c.porConfirmar}
                            </span>
                          )}
                          {c.comunidad && <DistintivoComunidad />}
                        </strong>
                        <span>{c.cargo}</span>
                      </span>
                      <span className="cliente-cifra" aria-hidden="true">
                        {cifra}
                      </span>
                    </span>
                    <span className="cliente-barra" aria-hidden="true">
                      <span style={{ width: pct + "%" }} />
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
          {clientes.length === 1
            ? "Ver el cliente"
            : `Ver los ${clientes.length} clientes`}
          <ArrowRight size={15} />
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
              <TarjetaPorConfirmar
                key={r.vacante_id}
                r={r}
                sugeridos={
                  paises === null
                    ? null
                    : paises.slice(0, 3).map(nombreLugar).join(", ") +
                      (paises.length > 3 ? ` y ${paises.length - 3} más` : "")
                }
                ocupado={ocupado === r.vacante_id}
                onSirve={() => decidir(r, "sirve")}
                onNoSirve={() => decidir(r, "no_sirve")}
                onElegirPais={onRevisar}
              />
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
          ". Revísalos y pulsa «Confirmar y aplicar».",
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
                Las metas suman {previa.metas.reales} y el cupo diario es{" "}
                {previa.metas.techo}: antes de programar, sube el cupo o baja
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
    [toast, setToast] = useState<{ texto: string; error: boolean } | null>(
      null,
    ),
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
  // Lista grande (17 nov): hay cambios solo si el borrador es distinto del guardado. Si deshaces lo que cambiaste,
  // vuelve a «sin cambios» y no pide guardar ni programar otra vez.
  const dirty = useMemo(
    () => marcado && mismoContenido(draft, estado?.borrador) === false,
    [marcado, draft, estado?.borrador],
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
      fijarLugares(s.ciudades_por_pais, s.utc_paises);
      setSesion(s);
      if (s.sesion) {
        cargarContactos();
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
  async function programar() {
    setBusy(true);
    try {
      const e = dirty ? await guardar() : estado;
      if (!e) return;
      // Contrato v43: «Confirmar y aplicar» rige desde hoy: la próxima búsqueda ya la usa; lo entregado no cambia.
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
        r.vigente_desde > hoyBogota()
          ? "Configuración programada para el " + fecha(r.vigente_desde) + "."
          : "Configuración aplicada. La próxima búsqueda ya la usa.",
      );
    } catch (e) {
      notify((e as Error).message, true);
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
      }>("/whatsapp/" + selectedClient + "?" + consulta.toString());
      if (!r.texto) {
        notify("No hay vacantes con comprobación vigente para copiar.", true);
        return;
      }
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
                  ? "Organiza tus clientes y prepara las oportunidades de mañana."
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
                  <Ayuda etiqueta="Guardar y aplicar">
                    <strong>Guardar borrador</strong> conserva tus cambios sin
                    tocar la próxima búsqueda.{" "}
                    <strong>Confirmar y aplicar</strong> los guarda y los usa
                    desde la próxima búsqueda, aunque sea dentro de unos
                    minutos. Lo que ya se entregó hoy no cambia.
                  </Ayuda>
                  <button
                    className="button secondary"
                    onClick={guardarClick}
                    disabled={!dirty || busy}
                  >
                    <Save size={16} />
                    {busy ? "Guardando…" : "Guardar borrador"}
                  </button>
                  {tab === "Resumen" && (
                    <BuscarAhora
                      hoyCorrio={
                        runs?.[0]?.fecha ===
                        new Date().toLocaleDateString("en-CA", {
                          timeZone: "America/Bogota",
                        })
                          ? new Date(runs[0].iniciada_en).toLocaleTimeString(
                              "es-CO",
                              {
                                hour: "numeric",
                                minute: "2-digit",
                                timeZone: "America/Bogota",
                              },
                            )
                          : null
                      }
                      sinConfirmar={
                        dirty ||
                        Boolean(
                          estado?.revision &&
                            estado.publicada?.revision !== estado.revision,
                        )
                      }
                      demo={Boolean(sesion.demo)}
                      onAviso={notify}
                      onTermino={recargarResumen}
                    />
                  )}
                  <button
                    className="button primary"
                    onClick={() => setModal("publicar")}
                    disabled={busy || total < 1 || excede}
                  >
                    <CalendarClock size={16} />
                    Confirmar y aplicar
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
                    <strong>{results?.listas || 0}</strong>
                    <span>listas para compartir</span>
                  </div>
                  <label className="cuantas-whatsapp">
                    Cuántas
                    <input
                      type="number"
                      min={1}
                      max={Math.max(1, results?.listas || 1)}
                      value={cuantasWhats}
                      // Thermos (18 nov): el campo se puede vaciar mientras se escribe; vacío vale 10.
                      onChange={(e) => setCuantasWhats(e.target.value)}
                    />
                  </label>
                  <button
                    className="button whatsapp"
                    disabled={
                      !selectedClient ||
                      !results?.listas ||
                      busy ||
                      loadingResults ||
                      abriendoWhatsApp
                    }
                    aria-busy={abriendoWhatsApp || undefined}
                    onClick={abrirWhatsApp}
                  >
                    <MessageCircle size={18} />
                    {abriendoWhatsApp ? "Preparando…" : "Copiar WhatsApp"}
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
          {tab === "Historial" && <AvisoUltimaBusqueda ultima={runs?.[0]} />}
          {tab === "Historial" && (
            <section className="card activity">
              <div className="section-title">
                <h2>La última búsqueda</h2>
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
                  texto="Confirma tu configuración. La primera búsqueda con esos criterios aparecerá aquí."
                />
              ) : (
                <>
                  {/* 18 nov: la última búsqueda en una frase y un solo embudo; lo demás se abre al tocarlo. */}
                  <div className="run-cabeza">
                    <h3>
                      {sesion.demo
                        ? "Captura de demostración"
                        : "Búsqueda dirigida"}{" "}
                      · {fecha(runs[0].fecha)}
                    </h3>
                    <span
                      className={
                        "pill " +
                        (runs[0].estado === "completa" ? "green" : "amber")
                      }
                    >
                      {estadosEjecucion[runs[0].estado] || runs[0].estado}
                    </span>
                  </div>
                  {runs[0].resumen.embudo ? (
                    <EmbudoDelDia
                      embudo={runs[0].resumen.embudo}
                      faltantes={runs[0].resumen.faltantes}
                    />
                  ) : (
                    <p>
                      {runs[0].resumen.vacantes_vigentes ??
                        runs[0].resumen.vacantes ??
                        0}{" "}
                      vacantes de {runs[0].resumen.meta || 0} previstas.
                    </p>
                  )}
                </>
              )}
            </section>
          )}
          {tab === "Historial" && runs.length > 1 && (
            <section className="card activity" aria-labelledby="anteriores">
              <h2 id="anteriores">Búsquedas anteriores</h2>
              <ul className="runs-anteriores">
                {runs.slice(1).map((r) => (
                  <li key={r.id}>
                    <details>
                      <summary>
                        <span>{fecha(r.fecha)}</span>
                        <span>
                          {r.resumen.vacantes_vigentes ??
                            r.resumen.vacantes ??
                            0}{" "}
                          de {r.resumen.meta || 0}
                        </span>
                        <span
                          className={
                            "pill " +
                            (r.estado === "completa" ? "green" : "amber")
                          }
                        >
                          {estadosEjecucion[r.estado] || r.estado}
                        </span>
                      </summary>
                      {r.resumen.embudo ? (
                        <EmbudoDelDia
                          embudo={r.resumen.embudo}
                          faltantes={r.resumen.faltantes}
                        />
                      ) : (
                        <p className="helper">Sin detalle de esta búsqueda.</p>
                      )}
                    </details>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {tab === "Historial" && sesion?.sesion && (
            <CoberturaPersonas
              nombrePais={(c) =>
                sesion.paises.find((x) => x.codigo === c)?.nombre ||
                nombrePais(c)
              }
            />
          )}
          {tab === "Historial" && <ReglasAprendidas notify={notify} />}
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
                " Pulsa «Confirmar y aplicar» para usarlo en la próxima búsqueda.",
            );
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
                " Pulsa «Confirmar y aplicar» para usarlo en la próxima búsqueda.",
            );
          }}
        />
      )}
      {modal === "publicar" && (
        <Dialog
          titulo="Confirmar y aplicar"
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
          {/* Contrato v43: una sola opción; rige desde la próxima búsqueda. */}
          <p className="helper">
            Se usa desde la próxima búsqueda: <b>{textoProximaDeHoy()}</b>. Lo
            que ya se entregó hoy no cambia.
          </p>
          {!estado?.publicada && (
            <p className="helper note">
              Es tu primera configuración: desde entonces dejan de buscarse los
              seis cargos fijos anteriores; solo se buscarán los cargos de esta
              lista.
            </p>
          )}
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
              onClick={() => programar()}
            >
              {busy ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <CalendarClock size={16} />
              )}
              Confirmar y aplicar
            </button>
          </div>
        </Dialog>
      )}
      {borrarCargo && (
        <Dialog
          titulo={"Eliminar " + borrarCargo.nombre}
          subtitulo="Se quita del borrador para siempre. Lo ya entregado y el historial se conservan."
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
                Se aplica al pulsar «Confirmar y aplicar».
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
                notify(`«${borrarCargo.nombre}» se eliminó del borrador.`);
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
        ? "Revisa «Historial»; la siguiente búsqueda lo intentará de nuevo."
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

// «3:32 p. m.» en hora de Colombia, de la hora en que terminó la última búsqueda.
function horaBogota(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("es-CO", {
      hour: "numeric",
      minute: "2-digit",
      timeZone: "America/Bogota",
    });
  } catch {
    return "";
  }
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
  if (!estado?.revision) return "Sin configuración confirmada";
  const p = estado.publicada;
  if (!p || p.revision !== estado.revision) return "Hay cambios sin confirmar";
  return p.vigente_desde > hoyBogota()
    ? "Lista: se usa desde la búsqueda de mañana"
    : "En uso desde la próxima búsqueda";
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
