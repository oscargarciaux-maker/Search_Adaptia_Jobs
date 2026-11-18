// Crear o editar un cargo (nombres, funciones y opciones avanzadas).
import React, { useEffect, useState } from "react";
import {
  Check,
  Compass,
  Loader2,
  Plus,
  Sparkles,
  Workflow,
} from "lucide-react";
import { api } from "../api";
import { Ayuda, Plegable, Dialog, TagInput } from "../comunes";
import type { Cargo } from "../types";
import { uid } from "../perfiles";

export function CargoDialog({
  cargo,
  onClose,
  onSave,
  notify,
}: {
  cargo: Cargo | null;
  onClose: () => void;
  onSave: (c: Cargo) => void;
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
  const [sugeridos, setSugeridos] = useState<string[]>([]);
  // Contrato v44: nombres en español (del mapa o armados con el glosario) y el oficio base más amplio, aparte.
  const [enEspanol, setEnEspanol] = useState<string[]>([]);
  const [amplios, setAmplios] = useState<string[]>([]);
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
  const [nota, setNota] = useState("");
  // `tocarNombres` = false al abrir un cargo existente: solo se muestran las fichas (en español, sugeridas y más
  // amplias), sin cambiar sus nombres ni bloquear el formulario (18 nov, Oscar no veía los grupos nuevos).
  async function expandir(tocarNombres = true) {
    if (tocarNombres) setBusy(true);
    try {
      const r = await api<{
        terminos_exactos: string[];
        terminos_similares: string[];
        terminos_cercanos?: string[];
        terminos_es?: string[];
        terminos_base?: string[];
        fuentes: string[];
        requiere_revision: boolean;
      }>("/cargos/expandir", {
        method: "POST",
        body: JSON.stringify({ cargo: c.nombre, rapido: !tocarNombres }),
      });
      // Sesión de prueba (17 nov): los nombres principales entran solos; los afines quedan como fichas para
      // añadir con un clic (antes entraban todos y había que quitar los que no servían).
      // Lo que ya tiene el cargo y los nombres principales, que entran solos: no se ofrecen otra vez como fichas.
      const ya = new Set(
        [
          ...c.terminos_exactos,
          ...c.terminos_similares,
          ...(tocarNombres ? r.terminos_exactos : []),
        ].map((x) => x.toLowerCase()),
      );
      if (tocarNombres)
        setC((v) => ({
          ...v,
          terminos_exactos: Array.from(
            new Set([...v.terminos_exactos, ...r.terminos_exactos]),
          ),
          terminos_cercanos: r.terminos_cercanos?.length
            ? r.terminos_cercanos
            : v.terminos_cercanos || [],
        }));
      const es = (r.terminos_es || []).filter((x) => !ya.has(x.toLowerCase()));
      const enEs = new Set(es.map((x) => x.toLowerCase()));
      setEnEspanol(es);
      setSugeridos(
        r.terminos_similares.filter(
          (x) => !ya.has(x.toLowerCase()) && !enEs.has(x.toLowerCase()),
        ),
      );
      setAmplios(
        (r.terminos_base || []).filter((x) => !ya.has(x.toLowerCase())),
      );
      if (tocarNombres)
        setNota(
          r.fuentes.join(" · ") +
            (r.requiere_revision
              ? ". No encontramos afines fiables; puedes añadirlos aquí."
              : ". Revisa y ajusta las sugerencias."),
        );
    } catch (e) {
      if (tocarNombres) notify((e as Error).message, true);
    } finally {
      if (tocarNombres) setBusy(false);
    }
  }
  useEffect(() => {
    if (cargo && cargo.nombre.trim().length >= 2) void expandir(false);
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
          if (c.nombre.trim().length < 2 || busy) return;
          if (
            !cargo &&
            !c.terminos_exactos.length &&
            !c.terminos_similares.length
          ) {
            await expandir();
            return;
          }
          onSave({
            ...c,
            nombre: c.nombre.trim(),
            terminos_exactos: c.terminos_exactos.length
              ? c.terminos_exactos
              : [c.nombre.trim()],
          });
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
          {/* Paso 7 (reunión 14 nov): una sola lista visible. Por dentro se conserva la diferencia: lo que ya era
              principal sigue siéndolo y lo nuevo entra como afín. */}
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
          {(
            [
              ["En español", "Nombres en español", enEspanol],
              ["Sugeridos", "Nombres sugeridos", sugeridos],
              [
                "Más amplio, sin el modificador: solo si también le sirven",
                "Nombres más amplios",
                amplios,
              ],
            ] as const
          ).map(
            ([titulo, etiqueta, lista]) =>
              lista.length > 0 && (
                <div
                  key={etiqueta}
                  className="sugeridos-grupo"
                  role="group"
                  aria-label={etiqueta}
                >
                  <div className="sugeridos-cabeza">
                    <span className="sugeridos-titulo">
                      {titulo} · toca para añadir
                    </span>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => anadir([...lista])}
                    >
                      Añadir todas
                    </button>
                  </div>
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
                </div>
              ),
          )}
          <p className="helper">
            Todas las formas en que las empresas llaman a este cargo, en español
            o inglés. Escríbelas una a una con Enter o pégalas separadas por
            comas.
          </p>
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
          <button disabled={busy} className="button primary">
            {cargo ? "Aplicar cambios" : "Añadir cargo"}
            <Check size={15} />
          </button>
        </div>
      </form>
    </Dialog>
  );
}
