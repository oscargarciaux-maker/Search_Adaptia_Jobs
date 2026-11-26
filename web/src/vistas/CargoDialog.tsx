// Crear o editar un cargo (nombres, funciones y opciones avanzadas).
import React, { useEffect, useRef, useState } from "react";
import {
  Check,
  Compass,
  Loader2,
  Plus,
  Sparkles,
  Workflow,
  X,
} from "lucide-react";
import { api } from "../api";
import { Ayuda, Plegable, Dialog, TagInput } from "../comunes";
import type { Cargo } from "../types";
import { uid } from "../perfiles";

// POST /api/cargos/expandir (contrato v44: `terminos_es` en español y `terminos_base`, el oficio más amplio).
type Sugerencias = {
  terminos_exactos: string[];
  terminos_similares: string[];
  terminos_cercanos?: string[];
  terminos_es?: string[];
  // Contrato v50: nombres en español que el cargo usa solos, sin añadirlos (los del mapa y los del glosario).
  hermanos_es?: string[];
  terminos_base?: string[];
  fuentes: string[];
  requiere_revision: boolean;
};

export function CargoDialog({
  cargo,
  onClose,
  onSave,
  notify,
}: {
  cargo: Cargo | null;
  onClose: () => void;
  // Contrato v49: puede devolver una promesa (guardar y aplicar); mientras, el botón dice «Aplicando…». Con
  // `false` no se guardó y el formulario sigue abierto.
  onSave: (c: Cargo) => void | Promise<boolean>;
  notify: (s: string, error?: boolean) => void;
}) {
  const [c, setC] = useState<Cargo>(
    cargo
      ? structuredClone(cargo)
      : {
          id: uid(),
          nombre: "",
          cupo: 0,
          activo: true,
          terminos_exactos: [],
          terminos_similares: [],
          terminos_excluidos: [],
          terminos_cercanos: [],
        },
  );
  const [busy, setBusy] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [sugeridos, setSugeridos] = useState<string[]>([]);
  // Contrato v44: nombres en español (del mapa o armados con el glosario) y el oficio base más amplio, aparte.
  const [enEspanol, setEnEspanol] = useState<string[]>([]);
  const [amplios, setAmplios] = useState<string[]>([]);
  // Contrato v50: nombres en español que se buscan y se reconocen solos; «No usar» los pasa a «Excluir».
  const [solos, setSolos] = useState<string[]>([]);
  // 18 nov (Oscar seguía sin ver los grupos): se muestran siempre que hay sugerencias pedidas, y si un grupo queda
  // vacío dice por qué (ya los tiene / no hay uno más amplio). Si la carga falla, se dice y se puede reintentar.
  const [estadoSug, setEstadoSug] = useState<
    "cargando" | "error" | "listo" | null
  >(null);
  const fallo = useRef<"abrir" | "completa">("abrir"); // qué pedido repetir con «Reintentar»
  const [conocidos, setConocidos] = useState({ es: 0, base: 0 }); // cuántos sabe el servidor (para el «ya los tiene»)
  function anadir(terminos: string[]) {
    setC((v) => ({
      ...v,
      terminos_similares: Array.from(
        new Set([...v.terminos_similares, ...terminos]),
      ),
    }));
    setSugeridos((s) => s.filter((x) => !terminos.includes(x)));
    setEnEspanol((s) => s.filter((x) => !terminos.includes(x)));
    setAmplios((s) => s.filter((x) => !terminos.includes(x)));
  }
  // La lista de excluidos está en «Opciones avanzadas», que puede estar plegada: se dice dónde quedó el nombre.
  const [dejado, setDejado] = useState("");
  function noUsar(termino: string) {
    setC((v) => ({
      ...v,
      terminos_excluidos: Array.from(
        new Set([...v.terminos_excluidos, termino]),
      ),
    }));
    setDejado(termino);
  }
  // Un nombre que contiene un término excluido ya no se usa (misma regla que el servidor).
  const solosVisibles = solos.filter(
    (t) =>
      !c.terminos_excluidos.some(
        (e) => e.trim() && t.toLowerCase().includes(e.trim().toLowerCase()),
      ),
  );
  const [nota, setNota] = useState("");
  // Cada pedido lleva un número: solo se muestra la respuesta del último (la carga al abrir no pisa a la completa).
  const ultimoPedido = useRef(0);
  function pedirSugerencias(rapido: boolean) {
    return api<Sugerencias>("/cargos/expandir", {
      method: "POST",
      body: JSON.stringify({ cargo: c.nombre, rapido }),
    });
  }
  // Sesión de prueba (17 nov): los nombres principales entran solos; los afines quedan como fichas para añadir con un
  // clic. Lo que ya tiene el cargo (y `principales`, que entran solos) no se ofrece otra vez como ficha.
  function mostrar(r: Sugerencias, principales: string[]) {
    const ya = new Set(
      [...c.terminos_exactos, ...c.terminos_similares, ...principales].map(
        (x) => x.toLowerCase(),
      ),
    );
    const hermanos = (r.hermanos_es || []).filter(
      (x) => !ya.has(x.toLowerCase()),
    );
    const deHermanos = new Set(hermanos.map((x) => x.toLowerCase()));
    setSolos(hermanos);
    // Lo que ya se usa solo no se ofrece para añadir.
    const es = (r.terminos_es || []).filter(
      (x) => !ya.has(x.toLowerCase()) && !deHermanos.has(x.toLowerCase()),
    );
    const enEs = new Set([...es, ...hermanos].map((x) => x.toLowerCase()));
    setEnEspanol(es);
    setSugeridos(
      r.terminos_similares.filter(
        (x) => !ya.has(x.toLowerCase()) && !enEs.has(x.toLowerCase()),
      ),
    );
    const base = r.terminos_base || [];
    setAmplios(base.filter((x) => !ya.has(x.toLowerCase())));
    setConocidos({
      es: (r.terminos_es || []).length + hermanos.length,
      base: base.length,
    });
    setEstadoSug("listo");
  }
  // «Buscar denominaciones afines»: añade los nombres principales y muestra las fichas.
  async function expandir() {
    const n = ++ultimoPedido.current;
    setBusy(true);
    try {
      const r = await pedirSugerencias(false);
      if (n !== ultimoPedido.current) return;
      setC((v) => ({
        ...v,
        terminos_exactos: Array.from(
          new Set([...v.terminos_exactos, ...r.terminos_exactos]),
        ),
        terminos_cercanos: r.terminos_cercanos?.length
          ? r.terminos_cercanos
          : v.terminos_cercanos || [],
      }));
      mostrar(r, r.terminos_exactos);
      setNota(
        r.fuentes.join(" · ") +
          (r.requiere_revision
            ? ". No encontramos afines fiables; puedes añadirlos aquí."
            : ". Revisa y ajusta las sugerencias."),
      );
    } catch (e) {
      notify((e as Error).message, true);
      if (n === ultimoPedido.current) {
        fallo.current = "completa";
        setEstadoSug("error");
      }
    } finally {
      setBusy(false);
    }
  }
  // Al abrir un cargo existente (18 nov, Oscar no veía los grupos nuevos): solo las fichas, sin ESCO, sin cambiar sus
  // nombres ni bloquear el formulario. Si falla, lo dice con «Reintentar».
  function cargarAlAbrir() {
    const n = ++ultimoPedido.current;
    setEstadoSug("cargando");
    pedirSugerencias(true)
      .then((r) => n === ultimoPedido.current && mostrar(r, []))
      .catch(() => {
        if (n !== ultimoPedido.current) return;
        fallo.current = "abrir";
        setEstadoSug("error");
      });
  }
  useEffect(() => {
    if (cargo && cargo.nombre.trim().length >= 2) cargarAlAbrir();
    // Solo al abrir el cargo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Contrato v25: proponer la huella de funciones con el catálogo (sin IA).
  const [proponiendo, setProponiendo] = useState(false);
  async function proponerFunciones() {
    setProponiendo(true);
    try {
      const r = await api<{ funciones: string[]; motivo: string }>(
        "/cargos/funciones",
        { method: "POST", body: JSON.stringify(c) },
      );
      if (r.funciones.length)
        setC((v) => ({
          ...v,
          funciones: Array.from(
            new Set([...(v.funciones || []), ...r.funciones]),
          ),
        }));
      notify(
        r.funciones.length
          ? `Se propusieron ${r.funciones.length} funciones. Revisa y quita las que no correspondan.`
          : r.motivo,
        !r.funciones.length,
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setProponiendo(false);
    }
  }
  return (
    <Dialog
      titulo={cargo ? "Editar cargo" : "Añadir un cargo"}
      subtitulo="Un mismo cargo sirve a varios clientes; cuántas vacantes recibe lo dicen las metas de sus perfiles."
      onClose={onClose}
    >
      <form
        className="form-cargo"
        onSubmit={async (e) => {
          e.preventDefault();
          if (c.nombre.trim().length < 2 || busy || aplicando) return;
          if (
            !cargo &&
            !c.terminos_exactos.length &&
            !c.terminos_similares.length
          ) {
            await expandir();
            return;
          }
          const r = onSave({
            ...c,
            nombre: c.nombre.trim(),
            terminos_exactos: c.terminos_exactos.length
              ? c.terminos_exactos
              : [c.nombre.trim()],
          });
          if (r instanceof Promise) {
            setAplicando(true);
            try {
              await r;
            } finally {
              setAplicando(false);
            }
          }
        }}
      >
        <fieldset disabled={busy}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="cargo-nombre">Cargo</label>
              <input
                id="cargo-nombre"
                autoFocus
                required
                minLength={2}
                maxLength={120}
                value={c.nombre}
                placeholder="Por ejemplo, Frontend"
                onChange={(e) => setC({ ...c, nombre: e.target.value })}
              />
            </div>
          </div>
          <div className="info-line">
            <Compass size={18} />
            <span>
              La búsqueda incluye las denominaciones que definas a continuación.
            </span>
          </div>
          <button
            className="button secondary full"
            type="button"
            disabled={c.nombre.trim().length < 2 || busy}
            onClick={() => expandir()}
          >
            {busy ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <Workflow size={16} />
            )}
            Buscar denominaciones afines
          </button>
          {nota && <p className="helper note">{nota}</p>}
          {estadoSug === "cargando" && (
            <p className="helper note" role="status">
              <Loader2 className="spin" size={14} /> Cargando nombres en español
              y sugeridos…
            </p>
          )}
          {estadoSug === "error" && (
            <p className="helper note" role="alert">
              No se pudieron cargar las sugerencias.{" "}
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  fallo.current === "completa" ? expandir() : cargarAlAbrir()
                }
              >
                Reintentar
              </button>
            </p>
          )}
          {estadoSug === "listo" &&
            (
              [
                [
                  "En español",
                  "Nombres en español",
                  enEspanol,
                  conocidos.es
                    ? solos.length
                      ? "Los nombres en español que conocemos ya se usan solos (abajo)."
                      : `Ya tiene los ${conocidos.es} nombres en español que conocemos.`
                    : "No conocemos nombres en español para este cargo: escríbelos abajo en «Nombres del cargo».",
                ],
                [
                  "Sugeridos",
                  "Nombres sugeridos",
                  sugeridos,
                  "Ya tiene todos los nombres sugeridos.",
                ],
                [
                  "Más amplio, sin el modificador: solo si también le sirven",
                  "Nombres más amplios",
                  amplios,
                  conocidos.base
                    ? "Ya tiene el oficio más amplio."
                    : "Es el oficio general: no hay uno más amplio.",
                ],
              ] as const
            ).map(([titulo, etiqueta, lista, vacio]) => (
              <div
                key={etiqueta}
                className="sugeridos-grupo"
                role="group"
                aria-label={etiqueta}
              >
                <div className="sugeridos-cabeza">
                  <span className="sugeridos-titulo">
                    {titulo}
                    {lista.length > 0 && " · toca para añadir"}
                  </span>
                  {lista.length > 0 && (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => anadir([...lista])}
                    >
                      Añadir todas
                    </button>
                  )}
                </div>
                {lista.length > 0 ? (
                  <div className="sugeridos">
                    {lista.map((t) => (
                      <button
                        type="button"
                        className="chip-sugerido"
                        key={t}
                        aria-label={"Añadir " + t}
                        onClick={() => anadir([t])}
                      >
                        <Plus size={12} />
                        {t}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="sugeridos-vacio">{vacio}</p>
                )}
              </div>
            ))}
          {dejado && (
            <p className="helper note" role="status">
              «{dejado}» ya no se usa. Quedó en «Excluir estos términos»
              (Opciones avanzadas).
            </p>
          )}
          {estadoSug === "listo" && solosVisibles.length > 0 && (
            <div
              className="sugeridos-grupo"
              role="group"
              aria-label="Nombres en español que se usan solos"
            >
              <div className="sugeridos-cabeza">
                <span className="sugeridos-titulo">
                  En español, se usan solos · toca para dejar de usar
                </span>
              </div>
              <div className="sugeridos">
                {solosVisibles.map((t) => (
                  <button
                    type="button"
                    className="chip-sugerido"
                    key={t}
                    aria-label={"No usar " + t}
                    onClick={() => noUsar(t)}
                  >
                    <X size={12} />
                    {t}
                  </button>
                ))}
              </div>
              <p className="sugeridos-vacio">
                Se buscan y se reconocen sin añadirlos. Si las funciones del
                aviso no acompañan, la vacante va al final o a «Por confirmar».
              </p>
            </div>
          )}
          {/* Paso 7 (reunión 14 nov): una sola lista visible. Por dentro se conserva la diferencia: lo que ya era
              principal sigue siéndolo y lo nuevo entra como afín. */}
          <div className="cargo-nombres">
            <TagInput
              label="Nombres del cargo"
              values={Array.from(
                new Set([...c.terminos_exactos, ...c.terminos_similares]),
              )}
              onChange={(v) => {
                const exactos = c.terminos_exactos.filter((x) => v.includes(x));
                setC({
                  ...c,
                  terminos_exactos: exactos,
                  terminos_similares: v.filter((x) => !exactos.includes(x)),
                });
              }}
            />
            <p className="helper">
              Todas las formas en que las empresas llaman a este cargo, en
              español o inglés. Escríbelas una a una con Enter o pégalas
              separadas por comas.
            </p>
          </div>
          <Plegable
            className="opciones-cargo"
            inicial={Boolean(
              (c.terminos_cercanos || []).length ||
              c.terminos_excluidos.length ||
              (c.funciones || []).length,
            )}
            mostrar={
              "Opciones avanzadas" +
              ((c.funciones || []).length
                ? ` · ${(c.funciones || []).length} funciones`
                : "")
            }
            ocultar="Ocultar opciones avanzadas"
          >
            <TagInput
              label="Funciones del cargo"
              values={c.funciones || []}
              onChange={(v) => setC({ ...c, funciones: v })}
            />
            <div className="funciones-acciones">
              <button
                type="button"
                className="button secondary small"
                disabled={proponiendo || c.nombre.trim().length < 2}
                onClick={proponerFunciones}
              >
                <Sparkles size={15} />
                {proponiendo ? "Buscando…" : "Proponer funciones"}
              </button>
              <Ayuda etiqueta="Funciones del cargo">
                Tareas y herramientas típicas del cargo. Si una vacante tiene
                otro título pero su descripción menciona varias de estas
                funciones, llega a «Por confirmar» como «Coincide por
                funciones». Se proponen comparando las vacantes del cargo con
                las de otros cargos; revisa y ajusta la lista.
              </Ayuda>
            </div>
            <TagInput
              label="Cargos cercanos (solo si faltan vacantes)"
              values={c.terminos_cercanos || []}
              onChange={(v) => setC({ ...c, terminos_cercanos: v })}
            />
            <p className="helper">
              Si un cliente no llega a 5 vacantes en el día, se completan
              primero con avisos que no dicen años o inglés y luego con estos
              oficios vecinos. En «Vacantes» aparecen marcadas como «Ampliada».
            </p>
            <TagInput
              label="Excluir estos términos"
              values={c.terminos_excluidos}
              onChange={(v) => setC({ ...c, terminos_excluidos: v })}
            />
          </Plegable>
          <p className="helper">
            No dependes de un listado cerrado. Puedes crear cualquier cargo y
            revisar sus términos sin modificar código.
          </p>
        </fieldset>
        <div className="dialog-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={busy || aplicando} className="button primary">
            {aplicando
              ? "Aplicando…"
              : cargo
                ? "Aplicar cambios"
                : "Añadir cargo"}
            {aplicando ? (
              <Loader2 size={15} className="spin" />
            ) : (
              <Check size={15} />
            )}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
