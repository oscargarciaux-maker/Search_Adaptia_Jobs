// Actividad: embudo por cargo con soluciones (contrato v31) y reglas de ubicación aprendidas (v17).
import React, { useEffect, useState } from "react";
import { api } from "../api";
import { Ayuda, Plegable } from "../comunes";
import type { Embudo, Regla } from "../types";
import { HuecosPorPais, type HuecoPais } from "./HuecosPais";

// Contrato v17: reglas de ubicación. Las «aprendidas» las crea el código solo a partir de tus decisiones.
export function ReglasAprendidas({
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

// Contrato v31: nombres que se entienden sin conocer el código («enlace comprobado» confundía).
export const etapasEmbudo: [keyof Embudo, string][] = [
  ["encontradas", "Encontradas en las fuentes"],
  ["con_descripcion", "Con el aviso completo leído"],
  ["entregables", "Con país e idioma claros"],
  ["nuevas", "Que nadie había recibido"],
  ["cumplen_filtros", "Le sirven a algún cliente"],
  ["enlace_comprobado", "Abiertas y vigentes hoy"],
  ["entregadas", "Entregadas"],
];
// Qué hacer cuando una etapa es la que más vacantes pierde.
const SOLUCIONES: Partial<Record<keyof Embudo, string>> = {
  con_descripcion:
    "No hace falta hacer nada: cada noche se leen primero los avisos más nuevos de este cargo. Si se repite varios días, añade nombres del cargo en español para que entren Computrabajo y Elempleo, que traen el aviso completo.",
  entregables:
    "Revisa «Por confirmar»: las vacantes cuyo país no se pudo confirmar están ahí y, si dices que sirven, llegan hoy mismo.",
  nuevas:
    "Ya se entregó casi todo lo publicado de este cargo. Añade otros nombres del cargo («Nombres del cargo») o cargos cercanos para ampliar la búsqueda.",
  cumplen_filtros:
    "Revisa la ubicación y el idioma de los perfiles de este cargo: añade una ubicación (por ejemplo remoto en LATAM) o acepta avisos en inglés. Debajo dice qué filtro corta más.",
  enlace_comprobado:
    "No hace falta hacer nada: la segunda pasada de las 8:30 comprueba más enlaces, y lo que no alcance queda guardado para mañana.",
};

// La etapa que más vacantes pierde respecto a la anterior (índice en `etapasEmbudo`, o -1).
function peorEtapa(e: Embudo) {
  let peor = -1,
    perdida = 0;
  etapasEmbudo.forEach(([k], n) => {
    if (n === 0 || k === "entregadas") return;
    const caida =
      ((e[etapasEmbudo[n - 1][0]] as number) || 0) - ((e[k] as number) || 0);
    if (caida > perdida) {
      perdida = caida;
      peor = n;
    }
  });
  return peor;
}

function sumarEmbudos(embudo: Record<string, Embudo>): Embudo {
  const total = {
    encontradas: 0,
    con_descripcion: 0,
    entregables: 0,
    nuevas: 0,
    enlace_comprobado: 0,
    cumplen_filtros: 0,
    entregadas: 0,
    ampliadas: 0,
    principal_perdida: "",
  } as Embudo;
  for (const e of Object.values(embudo))
    for (const [k] of etapasEmbudo)
      (total[k] as number) += (e[k] as number) || 0;
  return total;
}

// El embudo de un cargo, con su «Qué hacer» (se abre desde la lista de cargos).
function EmbudoUnCargo({ cargo, e }: { cargo: string; e: Embudo }) {
  const peor = peorEtapa(e);
  return (
    <section className="embudo-cargo">
      <h4>
        <span>{cargo}</span>
        <span className="embudo-entregadas">Entregadas {e.entregadas}</span>
      </h4>
      <ol className="embudo-etapas">
        {etapasEmbudo.map(([k, t], n) => (
          <li key={k} className={n === peor ? "mayor-perdida" : ""}>
            <strong>{e[k] as number}</strong>
            <span>
              {t}
              {k === "entregadas" && (
                <Ayuda etiqueta={"entregadas de " + cargo}>
                  Puede ser más que la etapa anterior: además de las nuevas de
                  esta búsqueda, incluye vacantes por ampliación (para que cada
                  persona llegue a 5) y vacantes de días anteriores que esa
                  persona aún no había recibido.
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
        <p className="field-help">Mayor pérdida: {e.principal_perdida}</p>
      )}
      {peor > 0 && SOLUCIONES[etapasEmbudo[peor][0]] && (
        <p className="embudo-solucion">
          <strong>Qué hacer:</strong> {SOLUCIONES[etapasEmbudo[peor][0]]}
        </p>
      )}
      {(e.de_su_busqueda ?? 0) + (e.de_la_amplia ?? 0) > 0 && (
        <p className="field-help">
          Origen de las entregadas: {e.de_su_busqueda ?? 0} de su búsqueda
          propia (LinkedIn por perfil) · {e.de_la_amplia ?? 0} de la búsqueda
          amplia
        </p>
      )}
    </section>
  );
}

// 18 nov (pedido de Oscar): el Historial dice en una frase y en un solo embudo cómo se reducen las vacantes del día;
// el detalle por cargo se abre al tocarlo.
export function EmbudoDelDia({
  embudo,
  faltantes = {},
}: {
  embudo: Record<string, Embudo>;
  faltantes?: Record<string, number>;
}) {
  const total = sumarEmbudos(embudo);
  const peor = peorEtapa(total);
  const base = Math.max(1, total.encontradas);
  return (
    <div className="embudo-dia">
      {/* Thermos (18 nov): es la suma por cargo; una vacante que sirve a dos cargos cuenta en ambos. */}
      <p className="embudo-frase">
        Sumando tus cargos: de{" "}
        <b>{total.encontradas.toLocaleString("es-CO")}</b> vacantes encontradas
        llegaron <b>{total.entregadas.toLocaleString("es-CO")}</b> a tus
        clientes.
        {peor > 0 && (
          <>
            {" "}
            Donde más se pierden: <b>«{etapasEmbudo[peor][1]}»</b>.
          </>
        )}
      </p>
      <ol className="embudo-barras" aria-label="Cómo se reducen las vacantes">
        {etapasEmbudo.map(([k, t], n) => {
          const valor = (total[k] as number) || 0;
          const anterior =
            n === 0 ? valor : (total[etapasEmbudo[n - 1][0]] as number) || 0;
          return (
            <li key={k} className={n === peor ? "mayor-perdida" : ""}>
              <span className="embudo-barra-texto">{t}</span>
              <span className="embudo-barra-pista" aria-hidden="true">
                <span
                  style={{
                    width: Math.max(1.5, (100 * valor) / base) + "%",
                  }}
                />
              </span>
              <b>{valor.toLocaleString("es-CO")}</b>
              <small>
                {n === 0 || !anterior || k === "entregadas" || valor > anterior
                  ? ""
                  : `queda el ${Math.round((100 * valor) / anterior)} %`}
              </small>
            </li>
          );
        })}
      </ol>
      {peor > 0 && SOLUCIONES[etapasEmbudo[peor][0]] && (
        <p className="embudo-solucion">
          <strong>Qué hacer:</strong> {SOLUCIONES[etapasEmbudo[peor][0]]}
        </p>
      )}
      <h3 className="embudo-subtitulo">Por cargo</h3>
      <ul className="embudo-por-cargo">
        {Object.entries(embudo).map(([cargo, e]) => {
          const meta = e.entregadas + (faltantes[cargo] || 0);
          return (
            <li key={cargo}>
              <details>
                <summary>
                  <span className="cargo-nombre">{cargo}</span>
                  <span
                    className={"pill " + (faltantes[cargo] ? "amber" : "green")}
                  >
                    {e.entregadas} de {meta}
                  </span>
                  <span className="cargo-perdida">
                    {e.principal_perdida || "Sin pérdidas que revisar"}
                  </span>
                </summary>
                <EmbudoUnCargo cargo={cargo} e={e} />
              </details>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Contrato v37: cobertura por persona. Si hoy llegó al mínimo, cuántos de sus días lo logró (con el denominador),
// cuántas tiene listas y por qué le faltan. Solo lo medido; nunca una promesa.
type FilaCobertura = {
  perfil_id: string;
  cliente: string;
  cargo: string;
  vive_en: string;
  idiomas: string[];
  estado: "cubierto" | "pendiente" | "sin_datos";
  hoy: number;
  dias_con_minimo: number;
  dias_medidos: number;
  dias_seguidos_bajo: number;
  listas: number;
  por_comprobar: number;
  causa: string;
  busquedas_hoy?: Record<string, number>;
  pocas_fuentes?: boolean;
  // Contrato v44: qué hacer, con cuántas vacantes más le llegarían (de los últimos 30 días).
  que_hacer?: { clave: string; accion: string; detalle: string; mas: number }[];
};
type Grupo = {
  perfiles: number;
  dias_con_minimo: number;
  dias_medidos: number;
};
type Cobertura = {
  minimo: number;
  dias_ventana: number;
  perfiles: FilaCobertura[];
  grupos: Record<"cargo" | "pais" | "idioma", Record<string, Grupo>>;
  alertas: string[];
  nota: string;
  huecos?: HuecoPais[];
};
const ESTADO_COBERTURA: Record<FilaCobertura["estado"], [string, string]> = {
  cubierto: ["Mínimo cubierto", "green"],
  pendiente: ["Mínimo pendiente", "amber"],
  sin_datos: ["Aún sin datos", "neutral"],
};
const NOMBRE_GRUPO = {
  cargo: "Por cargo",
  pais: "Por país",
  idioma: "Por idioma",
};

// Contrato v40: páginas buscadas para la persona en la última búsqueda («LinkedIn 6 · Indeed 2»).
const FUENTES_BUSQUEDA: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  jobint: "Bumeran",
  infojobs: "InfoJobs",
  tecnoempleo: "Tecnoempleo",
};
function textoBusquedas(b?: Record<string, number>) {
  const partes = Object.entries(b || {})
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${FUENTES_BUSQUEDA[k] || k} ${n}`);
  return partes.length ? partes.join(" · ") : "—";
}

export function CoberturaPersonas({
  nombrePais,
}: {
  nombrePais: (codigo: string) => string;
}) {
  const [datos, setDatos] = useState<Cobertura | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Cobertura>("/cobertura")
      .then(setDatos)
      .catch((e) => setError((e as Error).message));
  }, []);
  const pct = (g: { dias_con_minimo: number; dias_medidos: number }) =>
    g.dias_medidos
      ? Math.round((100 * g.dias_con_minimo) / g.dias_medidos) + " %"
      : "—";
  return (
    <section className="card activity cobertura" aria-labelledby="cob-titulo">
      <div className="section-title">
        <h2 id="cob-titulo">
          Cobertura por persona{" "}
          <Ayuda etiqueta="cobertura por persona">
            Para cada persona: cuántas vacantes recibió hoy, en cuántos de sus
            últimos días llegó a {datos?.minimo ?? 5} y cuántas hay listas para
            ella (con enlace comprobado y que nunca recibió). «Aún sin datos»:
            menos de 3 búsquedas con ese perfil.
          </Ayuda>
        </h2>
      </div>
      {error && (
        <p className="helper" role="alert">
          No se pudo leer la cobertura: {error}
        </p>
      )}
      {!datos && !error && <p className="helper">Cargando…</p>}
      {datos && (
        <>
          {datos.alertas.map((a) => (
            <p className="cobertura-alerta" role="status" key={a}>
              {a}
            </p>
          ))}
          <Plegable
            mostrar="Ver por cargo, país e idioma"
            ocultar="Ocultar por cargo, país e idioma"
          >
            <div className="cobertura-grupos">
              {(["cargo", "pais", "idioma"] as const).map((k) => (
                <div key={k}>
                  <h3>{NOMBRE_GRUPO[k]}</h3>
                  <ul>
                    {Object.entries(datos.grupos[k] || {}).map(([n, g]) => (
                      <li key={n}>
                        <span>
                          {k === "pais"
                            ? nombrePais(n)
                            : k === "idioma"
                              ? n === "es"
                                ? "Español"
                                : "Inglés"
                              : n}
                        </span>
                        <b>{pct(g)}</b>
                        <small>
                          {g.dias_con_minimo} de {g.dias_medidos}{" "}
                          {g.dias_medidos === 1 ? "día" : "días"}
                        </small>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </Plegable>
          <div className="tabla-cobertura">
            <table>
              <caption className="sr-only">
                Cobertura de cada persona en los últimos {datos.dias_ventana}{" "}
                días
              </caption>
              <thead>
                <tr>
                  <th scope="col">Persona</th>
                  <th scope="col">Cargo</th>
                  <th scope="col">Hoy / mínimo</th>
                  <th scope="col">Por qué le falta</th>
                </tr>
              </thead>
              <tbody>
                {datos.perfiles.map((f) => (
                  <tr key={f.perfil_id}>
                    <th scope="row">
                      {/* 18 nov: lo demás se ve al abrir la fila. */}
                      <details className="cobertura-mas">
                        <summary>{f.cliente}</summary>
                        <dl>
                          <dt>Estado</dt>
                          <dd>
                            <span
                              className={
                                "pill " + ESTADO_COBERTURA[f.estado][1]
                              }
                            >
                              {ESTADO_COBERTURA[f.estado][0]}
                            </span>
                          </dd>
                          <dt>Días con {datos.minimo}</dt>
                          <dd>
                            {f.dias_medidos
                              ? `${f.dias_con_minimo} de ${f.dias_medidos}`
                              : "—"}
                          </dd>
                          <dt>Listas</dt>
                          <dd>{f.listas}</dd>
                          <dt>Por comprobar</dt>
                          <dd>{f.por_comprobar}</dd>
                          <dt>Búsquedas hoy</dt>
                          <dd>{textoBusquedas(f.busquedas_hoy)}</dd>
                        </dl>
                      </details>
                    </th>
                    <td>{f.cargo}</td>
                    <td className="num">
                      <span
                        className={
                          "pill " + (f.hoy >= datos.minimo ? "green" : "amber")
                        }
                      >
                        {f.hoy} / {datos.minimo}
                      </span>
                    </td>
                    <td className="causa">
                      {f.causa || "—"}
                      {(f.que_hacer || []).length > 0 && (
                        <ul className="que-hacer" aria-label="Qué hacer">
                          {f.que_hacer!.map((q) => (
                            <li key={q.clave}>
                              <strong>{q.accion}</strong>
                              {q.mas > 0 && (
                                <span
                                  className="pill green"
                                  title={`${q.mas} vacantes más en los últimos 30 días`}
                                >
                                  +{q.mas}
                                  <span className="sr-only">
                                    {" "}
                                    vacantes más en los últimos 30 días
                                  </span>
                                </span>
                              )}
                              {q.detalle && (
                                <span className="que-hacer-detalle">
                                  {q.detalle}
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="helper">{datos.nota}</p>
          <HuecosPorPais filas={datos.huecos || []} minimo={datos.minimo} />
        </>
      )}
    </section>
  );
}
