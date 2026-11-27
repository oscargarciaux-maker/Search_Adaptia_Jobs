// Resumen del panel: las tarjetas de inicio, la dona del cupo diario y los datos de cada
// cliente que muestran las tarjetas y su detalle.
import {
  ArrowRight,
  BriefcaseBusiness,
  Clock3,
  Plus,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import type {
  Borrador,
  Cargo,
  Configuracion,
  Ejecucion,
  ResumenClientes,
} from "../types";
import {
  colores,
  estadosEjecucion,
  fecha,
  horaBogota,
  hoyBogota,
  origenMensaje,
  DistintivoComunidad,
} from "../comunes";
import { conMetas, perfilSinCiudad } from "../perfiles";

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

export type ResumenCliente = {
  id: string;
  nombre: string;
  cargo: string;
  meta: number;
  recibidas: number | null;
  porConfirmar: number;
  comunidad: boolean;
  perfiles: { cargo: string; meta: number; sinCiudad: boolean }[];
};
// Paso 8: los datos de cada tarjeta de cliente (meta = suma de las metas de sus perfiles activos, como el servidor).
export function resumenDeClientes(
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
        sinCiudad: perfilSinCiudad(p),
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
const bajoMeta = (c: ResumenCliente) =>
  c.recibidas != null && c.meta > 0 && c.recibidas < c.meta / 2;
// Desde 9 clientes las tarjetas pasan a dos columnas (decisión de Oscar, 14 nov).
const CLIENTES_EN_GRILLA = 9;
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

export function TarjetasResumen({
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
          {/* 18 nov: título y cifras en una sola línea para que la dona suba. Contrato v43: Comunidad recibe de lo
              que sobra y hasta su meta, aunque no ocupe cupo. */}
          <span className="tarjeta-cabeza cupos-cabeza">
            <SlidersHorizontal size={17} />
            Cupo diario
            <span className="cupos-cifras">
              {"· "}
              <b>{reales}</b> a clientes
              {comunidad > 0 && (
                <>
                  {" "}
                  · Comunidad hasta <b>{comunidad}</b>
                </>
              )}
            </span>
          </span>
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
              // 18 nov (caso Juan: «0 de 10» y 7 en Mensajes): su mensaje de hoy puede llevar vacantes de días
              // anteriores que nunca recibió; la tarjeta lo dice para que las dos pantallas cuadren.
              const borrador = (borradores || []).find(
                (b) =>
                  b.cliente_id === c.id &&
                  (b.estado === "pendiente" || b.estado === "abierto"),
              );
              const porEnviar = borrador?.vacantes.length || 0;
              const origen = borrador ? origenMensaje(borrador) : "";
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    className={
                      "cliente-mini" +
                      (bajoMeta(c) ? " bajo" : "") +
                      (c.comunidad ? " es-comunidad" : "")
                    }
                    // WCAG 2.5.3 (axe 4.14): sin aria-label; el nombre accesible sale del texto visible, con las
                    // partes que solo oye el lector de pantalla en .sr-only (control por voz: se dice lo que se ve).
                    // Se oye: «Ana (Comunidad): Product Designer, 3 de 17, 1 por confirmar, bajo su meta. Ver detalle».
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
                          {c.comunidad && (
                            <>
                              <span className="sr-only"> (</span>
                              <DistintivoComunidad />
                              <span className="sr-only">)</span>
                            </>
                          )}
                        </strong>
                        <span className="sr-only">: </span>
                        <span>{c.cargo}</span>
                      </span>
                      <span className="sr-only">, </span>
                      {c.recibidas == null ? (
                        <>
                          <span className="cliente-cifra" aria-hidden="true">
                            {cifra}
                          </span>
                          <span className="sr-only">meta de {c.meta}</span>
                        </>
                      ) : (
                        <span className="cliente-cifra">{cifra}</span>
                      )}
                      <span className="sr-only">
                        {`, ${pendiente}${bajoMeta(c) ? ", bajo su meta" : ""}. Ver detalle`}
                      </span>
                    </span>
                    <span className="cliente-barra" aria-hidden="true">
                      <span style={{ width: pct + "%" }} />
                    </span>
                    {porEnviar > 0 && (
                      <span className="cliente-por-enviar">
                        <span className="sr-only">, </span>
                        {porEnviar} por enviar
                        {origen && ` (${origen})`}
                      </span>
                    )}
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
