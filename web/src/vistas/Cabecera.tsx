// Cabecera de cada sección: aviso de demostración, volver, título y su explicación,
// «Aplicar cambios», «Buscar ahora», tema claro u oscuro, cerrar sesión y por qué no se aplicó lo guardado.
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  Loader2,
  LogOut,
  Moon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { api } from "../api";
import { delSistema, guardarTema, temaElegido, type Tema } from "../tema";
import type { EstadoConfig, Sesion } from "../types";
import { BuscarAhora } from "./BuscarAhora";

export function Cabecera({
  sesion,
  setSesion,
  setEstado,
  tab,
  go,
  estado,
  busy,
  noAplica,
  pendienteDeAplicar,
  aplicar,
  aplicarPendientes,
  notify,
  recargarResumen,
}: {
  sesion: Sesion;
  setSesion: (s: Sesion) => void;
  setEstado: (e: null) => void;
  tab: string;
  go: (t: string) => void;
  estado: EstadoConfig | null;
  busy: boolean;
  noAplica: string;
  pendienteDeAplicar: boolean;
  aplicar: () => Promise<unknown>;
  aplicarPendientes: () => Promise<boolean>;
  notify: (s: string, error?: boolean) => void;
  recargarResumen: () => void;
}) {
  return (
    <>
      {sesion.demo && (
        <div className="demo-notice">
          <ShieldCheck size={15} />
          <span>
            Estás usando datos ficticios. Los cambios de esta demostración no
            modifican Supabase ni ejecutan búsquedas reales.
          </span>
        </div>
      )}
      {tab !== "Resumen" && (
        <div className="page-top">
          <button className="text-button volver" onClick={() => go("Resumen")}>
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
              ? "Organiza tus clientes y prepara sus oportunidades de cada día."
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
                className={"flow-pill" + (pendienteDeAplicar ? " pending" : "")}
              >
                {pendienteDeAplicar
                  ? "Cambios sin aplicar"
                  : "En uso desde la próxima búsqueda"}
              </span>
              {tab === "Resumen" && (
                <BuscarAhora
                  sinAplicar={pendienteDeAplicar}
                  onAplicar={aplicarPendientes}
                  revision={estado?.publicada?.revision}
                  demo={Boolean(sesion.demo)}
                  onAviso={notify}
                  onTermino={recargarResumen}
                />
              )}
              {pendienteDeAplicar && (
                <button
                  className="button primary"
                  onClick={() => aplicar()}
                  disabled={busy}
                >
                  {busy ? (
                    <Loader2 size={16} className="spin" />
                  ) : (
                    <Check size={16} />
                  )}
                  {busy ? "Aplicando…" : "Aplicar cambios"}
                </button>
              )}
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
      {noAplica &&
        pendienteDeAplicar &&
        ["Resumen", "Clientes", "Cargos y metas"].includes(tab) && (
          <p className="form-error aviso-no-aplica" role="alert">
            <b>Tus cambios están guardados, pero la búsqueda aún no los usa.</b>{" "}
            {noAplica}
            {noAplica.includes("Aplicar cambios")
              ? ""
              : " Cuando lo arregles, pulsa «Aplicar cambios»."}
          </p>
        )}
    </>
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
