// Contrato v16 y v29 (lista grande, PR 3): «Por confirmar» con todas las pendientes, por páginas, en vista dividida.
// A la izquierda la lista (con el total real y el filtro por cliente); a la derecha la decisión y el aviso completo.
// Atajos con el panel de decisión enfocado: Enter acepta la sugerencia · 1 Sirve · 2 Otro país · 3 No sirve · 4 Saltar.
import React, { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  MapPin,
  RefreshCw,
  Upload,
  X,
} from "lucide-react";
import { api } from "../api";
import {
  Ayuda,
  Empty,
  ETIQUETA_SUGERIDA,
  IdVacante,
  REGIONES,
  SelectorPaises,
  fecha,
  iniciales,
  modos,
  nombrePais,
} from "../comunes";
import type { Revision, Revisiones, Sesion } from "../types";
import { DatosAviso, Descripcion } from "./FichaVacante";
import { teclasLista } from "./Vacantes";

const POR_PAGINA = 25;

export function PorConfirmar({
  paises,
  clientes,
  notify,
  onCambio,
}: {
  paises: Sesion["paises"];
  clientes: { id: string; nombre: string }[];
  notify: (s: string, error?: boolean) => void;
  onCambio: (total: number) => void;
}) {
  const [datos, setDatos] = useState<Revisiones | null>(null);
  const [pagina, setPagina] = useState(1);
  const [cliente, setCliente] = useState("");
  const [elegida, setElegida] = useState("");
  const [verDecision, setVerDecision] = useState(false);
  const [elegido, setElegido] = useState<Record<string, string>>({});
  const [extras, setExtras] = useState<Record<string, string[]>>({});
  const [iguales, setIguales] = useState<Record<string, boolean>>({});
  const [ocupado, setOcupado] = useState("");
  const panel = useRef<HTMLElement>(null);
  async function cargar(p = pagina, c = cliente, indice = -1) {
    try {
      const q = new URLSearchParams({
        pagina: String(p),
        por_pagina: String(POR_PAGINA),
      });
      if (c) q.set("cliente_id", c);
      let r = await api<Revisiones>("/revisiones?" + q);
      // Si la página quedó vacía (se decidió la última), volver a la anterior.
      if (!r.pendientes.length && p > 1) {
        q.set("pagina", String(p - 1));
        r = await api<Revisiones>("/revisiones?" + q);
        p -= 1;
      }
      setDatos(r);
      setPagina(p);
      onCambio(r.en_espera ?? r.total);
      if (indice >= 0 && r.pendientes.length)
        setElegida(
          r.pendientes[Math.min(indice, r.pendientes.length - 1)].vacante_id,
        );
    } catch (e) {
      notify((e as Error).message, true);
      setDatos({ pendientes: [], total: 0, ayudan_faltantes: 0 });
    }
  }
  useEffect(() => {
    cargar(1, "");
  }, []);
  const nombre = (codigo: string) =>
    paises.find((p) => p.codigo === codigo)?.nombre ||
    REGIONES.find((r) => r.codigo === codigo)?.nombre ||
    nombrePais(codigo);
  async function decidir(r: Revision, decision: string, codigos?: string[]) {
    const pais = elegido[r.vacante_id] ?? r.sugerencia[0] ?? "";
    // Contrato v23: etiquetas adicionales (por ejemplo LATAM y Estados Unidos a la vez).
    const mas = extras[r.vacante_id] || [];
    if (decision === "sirve" && !codigos?.length && mas.length)
      codigos = [...(pais ? [pais] : []), ...mas];
    if (decision === "sirve" && !pais && !codigos?.length && !r.funciones) {
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
              decision === "sirve" && r.funciones
                ? []
                : decision === "sirve"
                  ? codigos?.length
                    ? codigos
                    : [pais]
                  : [],
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
      // Pasa sola a la siguiente: la que queda en el mismo lugar de la lista.
      const indice = datos?.pendientes.findIndex(
        (x) => x.vacante_id === r.vacante_id,
      );
      const conTeclado = panel.current?.contains(document.activeElement);
      await cargar(pagina, cliente, indice ?? 0);
      if (conTeclado) requestAnimationFrame(() => panel.current?.focus());
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
              : e.avance.leidas
                ? `Cargando… ${e.avance.leidas} revisadas`
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
  if (!datos.pendientes.length && !cliente)
    return (
      <Empty
        icon={CheckCheck}
        title="Todo al día"
        texto="No hay vacantes por confirmar en la bandeja. La búsqueda diaria trae las que ayudan a tus clientes; para depurar toda la base ahora, carga todas las dudosas."
        action={ocupado === "todas" ? undefined : cargarTodas}
        label="Cargar todas las dudosas de la base"
      />
    );
  const r =
    datos.pendientes.find((x) => x.vacante_id === elegida) ||
    datos.pendientes[0];
  const paginas = datos.paginas || 1;
  const pais = r ? (elegido[r.vacante_id] ?? r.sugerencia[0] ?? "") : "";
  return (
    <section className="revisiones">
      {masiva}
      <div className="revision-barra">
        {/* Contrato v34: el filtro «Para» va primero y las páginas siempre ocupan su lugar: nada se mueve. */}
        <div className="field revision-filtro">
          <label htmlFor="revision-cliente">Para</label>
          <select
            id="revision-cliente"
            value={cliente}
            onChange={(e) => {
              setCliente(e.target.value);
              cargar(1, e.target.value, 0);
            }}
          >
            <option value="">Todos los clientes</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
                {datos.por_cliente?.[c.id] !== undefined
                  ? ` (${datos.por_cliente[c.id]})`
                  : ""}
              </option>
            ))}
          </select>
        </div>
        <p className="helper revision-ayuda">
          <strong>
            {datos.total} {datos.total === 1 ? "pendiente" : "pendientes"}
          </strong>
          {cliente ? " de este cliente" : ""}
          {datos.ayudan_faltantes
            ? ` · ${datos.ayudan_faltantes} ayudan a clientes con menos de 5 vacantes`
            : ""}{" "}
          <Ayuda etiqueta="cómo decidir">
            <strong>Una sola pregunta:</strong> ¿puede postularse alguien que
            vive en LATAM o en España? Cada vacante trae la respuesta sugerida y
            por qué; corrige solo si la ves mal. Atajos con el panel de la
            derecha seleccionado: Enter acepta la sugerencia · 1 Sirve · 2 Otro
            país · 3 No sirve · 4 Saltar. En la lista, ↑/↓ cambian de vacante.
            «Más útil hoy» marca las 10 que más ayudan a tus clientes.
          </Ayuda>
        </p>
        <nav className="paginas" aria-label="Páginas de Por confirmar">
          <button
            type="button"
            className="icon"
            aria-label="Página anterior"
            disabled={pagina <= 1}
            onClick={() => cargar(pagina - 1, cliente, 0)}
          >
            <ChevronLeft size={16} />
          </button>
          <span>
            Página {pagina} de {paginas}
          </span>
          <button
            type="button"
            className="icon"
            aria-label="Página siguiente"
            disabled={pagina >= paginas}
            onClick={() => cargar(pagina + 1, cliente, 0)}
          >
            <ChevronRight size={16} />
          </button>
        </nav>
      </div>
      {!r ? (
        <p className="helper">Este cliente no tiene vacantes por confirmar.</p>
      ) : (
        <div className={"dividida" + (verDecision ? " ver-ficha" : "")}>
          <ul
            className="dividida-lista"
            aria-label={`Por confirmar: página ${pagina} de ${paginas}`}
          >
            {datos.pendientes.map((x) => (
              <li key={x.vacante_id}>
                <button
                  type="button"
                  data-id={x.vacante_id}
                  className={
                    "item-vacante item-revision" +
                    (x.vacante_id === r.vacante_id ? " elegida" : "")
                  }
                  aria-current={
                    x.vacante_id === r.vacante_id ? "true" : undefined
                  }
                  onClick={() => {
                    setElegida(x.vacante_id);
                    setVerDecision(true);
                  }}
                  onKeyDown={(e) =>
                    teclasLista(
                      e,
                      datos.pendientes.map((y) => y.vacante_id),
                      r.vacante_id,
                      setElegida,
                    )
                  }
                >
                  <span className="item-titulo">{x.titulo}</span>
                  <span className="item-empresa">
                    {x.empresa}
                    <IdVacante numero={x.numero} />
                  </span>
                  <span className="item-lugar">
                    <MapPin size={12} />
                    {[
                      x.ubicacion || "Ubicación no informada",
                      modos[x.modalidad] || x.modalidad,
                      x.publicada ? fecha(x.publicada) : "",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                  <span className="item-etiquetas">
                    {(x.paises || []).slice(0, 2).map((c) => (
                      <span key={c} className="pill neutral pais-leido">
                        {nombre(c)}
                      </span>
                    ))}
                    {(x.paises || []).length > 2 && (
                      <span className="pill neutral pais-leido">
                        +{(x.paises || []).length - 2}
                      </span>
                    )}
                    {x.mas_util && (
                      <span className="pill green">Más útil hoy</span>
                    )}
                    {x.ayuda_faltantes && (
                      <span className="pill amber">Ayuda a faltantes</span>
                    )}
                    {x.funciones && (
                      <span className="pill">
                        {x.otro_oficio ? "Otro oficio" : "Por funciones"}
                      </span>
                    )}
                    {x.sugerida && (
                      <span className="item-sugerencia">
                        Sugerencia: {ETIQUETA_SUGERIDA[x.sugerida]}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="dividida-detalle">
            {/* Atajos de teclado de la bandeja (1–4, Enter): el panel recibe el foco a propósito. */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
            <article
              className="card revision ficha"
              key={r.vacante_id}
              ref={panel}
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
              tabIndex={0}
              aria-label={`${r.titulo} en ${r.empresa}`}
              onKeyDown={(e) => {
                if ((e.target as HTMLElement).tagName === "SELECT") return;
                if ((e.target as HTMLElement).tagName === "INPUT") return;
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
              <button
                type="button"
                className="text-button solo-movil"
                onClick={() => setVerDecision(false)}
              >
                <ArrowLeft size={15} />
                Volver a la lista
              </button>
              <div className="vacancy-top">
                <span className="company-avatar">{iniciales(r.empresa)}</span>
                <div>
                  <span className="company-name">
                    {r.empresa}
                    <IdVacante numero={r.numero} />
                  </span>
                  <h2>{r.titulo}</h2>
                </div>
                {r.ayuda_faltantes && (
                  <span className="pill amber">
                    Ayuda a clientes con faltantes
                  </span>
                )}
              </div>
              {r.por_que && (
                <div
                  className={"revision-sugerencia " + (r.sugerida || "leer")}
                >
                  <p>
                    <strong>
                      {r.sugerida
                        ? `Sugerencia: ${ETIQUETA_SUGERIDA[r.sugerida]}`
                        : "Para leer"}
                    </strong>{" "}
                    — {r.por_que}
                  </p>
                </div>
              )}
              <DatosAviso
                ubicacion={r.ubicacion}
                modalidad={r.modalidad}
                salario={r.salario}
                publicada={r.publicada}
                idioma={r.idioma}
              />
              {(r.paises || []).length > 0 && (
                <p className="revision-paises-leidos">
                  <span className="helper">Países que leyó el sistema:</span>
                  {(r.paises || []).map((c) => (
                    <span key={c} className="pill neutral pais-leido">
                      {nombre(c)}
                    </span>
                  ))}
                </p>
              )}
              {(r.frase ?? r.pista) && (
                <blockquote className="revision-pista">
                  {r.frase ?? r.pista}
                </blockquote>
              )}
              <p className="helper">
                Le serviría a: {r.clientes.join(", ") || "—"}
              </p>
              {r.funciones && !r.otro_oficio && (
                <p className="revision-funciones">
                  <span className="pill">Coincide por funciones</span> El título
                  es otro, pero la descripción coincide con las funciones del
                  cargo. Si sirve, desde mañana este título entra solo.
                </p>
              )}
              {r.otro_oficio && (
                <p className="revision-funciones">
                  <span className="pill">Funciones de otro oficio</span> El
                  título coincide con el cargo, pero la descripción no nombra
                  sus funciones y parece otro oficio. Si sirve, desde mañana
                  este título entra solo; si no, no se le ofrece más a ese
                  cargo.
                </p>
              )}
              <div className="revision-acciones">
                {!r.funciones && (
                  <>
                    <label className="revision-pais">
                      País
                      <select
                        aria-label={`País de ${r.titulo} en ${r.empresa}`}
                        value={pais}
                        onChange={(e) =>
                          setElegido({
                            ...elegido,
                            [r.vacante_id]: e.target.value,
                          })
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
                    <div className="revision-extras">
                      <SelectorPaises
                        etiqueta={`Otras etiquetas de ${r.titulo}`}
                        valores={extras[r.vacante_id] || []}
                        onChange={(v) =>
                          setExtras({ ...extras, [r.vacante_id]: v })
                        }
                        excluir={[pais]}
                        extra={REGIONES}
                      />
                    </div>
                  </>
                )}
              </div>
              {/* Sesión de prueba (17 nov): las decisiones juntas, con ✓ y ✗ parejos. */}
              <div className="revision-decisiones">
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
                  onClick={() => decidir(r, "no_sirve")}
                >
                  <X size={15} />
                  No sirve
                </button>
                {!r.funciones && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={ocupado === r.vacante_id}
                    onClick={() => decidir(r, "otro_pais")}
                  >
                    <X size={15} />
                    Solo para otro país
                  </button>
                )}
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
              <section className="ficha-seccion">
                <h3>Descripción del aviso</h3>
                <Descripcion id={r.vacante_id} enlace={r.enlace} />
              </section>
            </article>
          </div>
        </div>
      )}
    </section>
  );
}
