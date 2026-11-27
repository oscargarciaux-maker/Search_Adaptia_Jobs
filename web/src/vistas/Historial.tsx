// Historial del panel: la última búsqueda, las anteriores, la cobertura y las reglas
// aprendidas, y el aviso de una búsqueda que falló o quedó corta.
import { Clock3, RefreshCw } from "lucide-react";
import { api } from "../api";
import type { Ejecucion, Sesion } from "../types";
import { Empty, estadosEjecucion, fecha, nombrePais } from "../comunes";
import { CoberturaPersonas, EmbudoDelDia, ReglasAprendidas } from "./Actividad";

export function Historial({
  runs,
  setRuns,
  sesion,
  notify,
}: {
  runs: Ejecucion[];
  setRuns: (runs: Ejecucion[]) => void;
  sesion: Sesion;
  notify: (s: string, error?: boolean) => void;
}) {
  return (
    <>
      <AvisoUltimaBusqueda ultima={runs?.[0]} />
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
                {sesion.demo ? "Captura de demostración" : "Búsqueda dirigida"}{" "}
                · {fecha(runs[0].fecha)}
              </h3>
              <span
                className={
                  "pill " + (runs[0].estado === "completa" ? "green" : "amber")
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
      {runs.length > 1 && (
        <section className="card activity" aria-labelledby="anteriores">
          <h2 id="anteriores">Búsquedas anteriores</h2>
          <ul className="runs-anteriores">
            {runs.slice(1).map((r) => (
              <li key={r.id}>
                <details>
                  <summary>
                    <span>{fecha(r.fecha)}</span>
                    <span>
                      {r.resumen.vacantes_vigentes ?? r.resumen.vacantes ?? 0}{" "}
                      de {r.resumen.meta || 0}
                    </span>
                    <span
                      className={
                        "pill " + (r.estado === "completa" ? "green" : "amber")
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
      {sesion?.sesion && (
        <CoberturaPersonas
          nombrePais={(c) =>
            sesion.paises.find((x) => x.codigo === c)?.nombre || nombrePais(c)
          }
        />
      )}
      <ReglasAprendidas notify={notify} />
    </>
  );
}

// Avisos dentro del panel, sin correo ni servicios externos (decisión del operador, 13 nov).
// Lista grande del 16 nov: en el Resumen el aviso solo aparece si la búsqueda falló; lo demás vive en «Actividad».
export function AvisoUltimaBusqueda({
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
