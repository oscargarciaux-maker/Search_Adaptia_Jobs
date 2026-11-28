// 8.1 (decisiones del cliente, 27 nov): huecos por país, solo para el operador. «Riesgo»: un país de algún perfil sin
// fuente local (solo LinkedIn, portales de empresas y Get on Board). «Hueco»: medido tras la búsqueda, un perfil quedó
// bajo el umbral de aviso (`minimo`, 10 = la meta; P-11.3) porque faltan vacantes en las fuentes. El pedido copiado
// lleva solo país, idiomas, familias y modalidades.
import { useState } from "react";
import { Copy } from "lucide-react";
import { Ayuda } from "../comunes";

export type HuecoPais = {
  pais: string;
  nombre: string;
  perfiles: number;
  bajo_minimo: number;
  fuentes: string[];
  fuentes_locales: number;
  estado: "cubierto" | "riesgo" | "hueco";
  pedido: string;
};

const ESTADO: Record<HuecoPais["estado"], [string, string]> = {
  hueco: ["Hueco", "red"],
  riesgo: ["Riesgo", "amber"],
  cubierto: ["Cubierto", "green"],
};

export function HuecosPorPais({
  filas,
  minimo,
}: {
  filas: HuecoPais[];
  minimo: number;
}) {
  const [copiado, setCopiado] = useState("");
  if (!filas.length) return null;
  async function copiar(f: HuecoPais) {
    try {
      await navigator.clipboard.writeText(f.pedido);
      setCopiado(
        `Pedido de ${f.nombre} copiado: pégalo en un chat de Claude Code.`,
      );
    } catch {
      setCopiado("No se pudo copiar; selecciona el texto del pedido.");
    }
  }
  return (
    <div className="huecos-pais">
      <h3 id="huecos-titulo">
        Huecos por país{" "}
        <Ayuda etiqueta="huecos por país">
          «Riesgo»: en ese país solo buscan LinkedIn, los portales de empresas y
          Get on Board. «Hueco»: tras la última búsqueda, alguien de ese país
          quedó bajo {minimo} porque faltan vacantes en las fuentes (no por su
          cargo, ni por enlaces por comprobar). El pedido sirve para añadir una
          fuente nueva hoy; ver «Fuente nueva el mismo día» en la guía del
          panel.
        </Ayuda>
      </h3>
      <div className="tabla-huecos">
        <table aria-labelledby="huecos-titulo">
          <thead>
            <tr>
              <th scope="col">País</th>
              <th scope="col">Perfiles</th>
              <th scope="col">Bajo {minimo} hoy</th>
              <th scope="col">Fuentes que lo buscan</th>
              <th scope="col">Estado</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.pais}>
                <th scope="row">{f.nombre}</th>
                <td className="num">{f.perfiles}</td>
                <td className="num">{f.bajo_minimo}</td>
                <td>{f.fuentes.join(", ")}</td>
                <td>
                  <span className={"pill " + ESTADO[f.estado][1]}>
                    {ESTADO[f.estado][0]}
                  </span>
                  {f.pedido && (
                    <button
                      type="button"
                      className="button secondary"
                      aria-label={`Copiar pedido de fuente nueva para ${f.nombre}`}
                      onClick={() => copiar(f)}
                    >
                      <Copy size={14} /> Copiar pedido de fuente nueva
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="helper" role="status">
        {copiado}
      </p>
    </div>
  );
}
