// Importar clientes desde un CSV y eliminar del todo un cliente archivado.
import { useEffect, useState } from "react";
import { Upload } from "lucide-react";
import { api } from "../api";
import type { EstadoConfig, PreviaImportacion } from "../types";
import { Dialog, nombrePais } from "../comunes";
import { avisosCobertura } from "../configuracion";

// Importar clientes desde un CSV (15 nov): vista previa sin guardar y luego importación todo o nada. Los clientes
// quedan guardados como si se hubieran creado a mano; la búsqueda los usa desde que se pulsa «Aplicar cambios».
export function ImportarClientes({
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
        avisos_cobertura?: string[];
      }>("/clientes/importar", {
        method: "POST",
        body: JSON.stringify({ contenido, actuales, revision, confirmacion }),
      });
      onListo(r.estado);
      notify(
        `${r.actualizados} ${r.actualizados === 1 ? "cliente actualizado" : "clientes actualizados"} (conservan lo que recibieron), ${r.nuevos} ${r.nuevos === 1 ? "nuevo" : "nuevos"}` +
          (r.borrados ? `, ${r.borrados} borrados` : "") +
          (r.archivados ? `, ${r.archivados} archivados` : "") +
          ". Revísalos y pulsa «Aplicar cambios»." +
          avisosCobertura(r.avisos_cobertura),
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
                vacantes que ya recibieron y las configuraciones anteriores se
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
            Tienes cambios sin aplicar. Pulsa «Aplicar cambios» o recarga antes
            de importar.
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
                {previa.metas.techo}: antes de aplicar, sube el cupo o baja
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
