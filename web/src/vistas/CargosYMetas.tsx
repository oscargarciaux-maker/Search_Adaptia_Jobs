// «Cargos y metas» (dividido de main.tsx): el cupo diario, una tarjeta por cargo con sus cifras y los archivados.
import { useState } from "react";
import {
  Archive,
  BriefcaseBusiness,
  Code2,
  Pencil,
  Plus,
  RotateCcw,
  ShieldCheck,
  Target,
  Trash2,
  Users,
} from "lucide-react";
import type {
  Cargo,
  Configuracion,
  Ejecucion,
  EstimacionCargo,
} from "../types";
import { Ayuda, colores, hoyBogota } from "../comunes";
import type { conMetas } from "../perfiles";
import type { EstadoPrevia, useVistaPrevia } from "../vistaPrevia";

export function CargosYMetas({
  draft,
  cambiar,
  metas,
  excede,
  cargos,
  clientCount,
  previaCargos,
  runs,
  setEditCargo,
  setBorrarCargo,
  setArchive,
  setModal,
}: {
  draft: Configuracion;
  cambiar: (v: Configuracion) => void;
  metas: ReturnType<typeof conMetas>;
  excede: boolean;
  cargos: ReturnType<typeof conMetas>["cargos"];
  clientCount: (id: string) => number;
  previaCargos: ReturnType<typeof useVistaPrevia>;
  runs: Ejecucion[];
  setEditCargo: (c: Cargo | null) => void;
  setBorrarCargo: (c: Cargo) => void;
  setArchive: (a: {
    tipo: "cliente" | "cargo";
    id: string;
    nombre: string;
  }) => void;
  setModal: (m: "cargo" | "archivo") => void;
}) {
  return (
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
            ` · Comunidad hasta ${metas.comunidad}`} · {metas.libre} libres
          {excede &&
            " · Las metas de los clientes pasan el cupo diario: baja metas o sube el cupo"}
        </p>
        <Ayuda etiqueta="Cupo diario">
          Máximo de vacantes al día entre todos, para cuidar los consumos.
          Primero se llenan las metas de los clientes; el grupo «Comunidad»
          recibe después, de lo que sobre, y solo hasta su meta.
        </Ayuda>
        <div className="allocation-track">
          <span
            style={{
              width: Math.min((metas.reales / metas.techo) * 100, 100) + "%",
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
                      Solo busca «{c.nombre}». En «Editar», pulsa «Buscar
                      denominaciones afines» para sumar nombres en inglés y
                      parecidos.
                    </span>
                  )}
                </div>
                <CifrasCargo
                  meta={c.cupo}
                  llegaron={llegaronHoy(runs?.[0], c.nombre)}
                  disponibles={previaCargos.datos?.cargos?.[c.id]?.disponibles}
                />
                {clientCount(c.id) === 0 && (
                  <p className="role-warning">
                    Sin perfiles: este cargo no busca hasta que un cliente lo
                    tenga.{" "}
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
          Una vacante compartida con varios clientes cuenta una sola vez en el
          cupo de su cargo. Si no hay suficientes resultados válidos, se
          mostrará el faltante.
        </p>
      </div>
    </>
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
