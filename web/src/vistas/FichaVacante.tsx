// Contrato v29: el aviso completo a la derecha de la lista, sin salir del panel. La descripción llega en bloques de
// texto (párrafo, viñeta, subtítulo) y se pinta como texto: nunca HTML del sitio de origen.
import React, { useEffect, useState } from "react";
import {
  Briefcase,
  Check,
  Clock3,
  ExternalLink,
  Globe2,
  Languages,
  MapPin,
  Megaphone,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import { api } from "../api";
import { Ayuda, IdVacante, fecha, grados, iniciales, modos } from "../comunes";
import type { BloqueFicha, FichaVacante as Ficha, Vacante } from "../types";

// Las fichas ya leídas se recuerdan mientras el panel está abierto (el servidor también las guarda 10 minutos).
const leidas = new Map<string, Ficha>();

export function useFicha(id: string) {
  const [ficha, setFicha] = useState<Ficha | null>(leidas.get(id) || null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!id) return;
    let vigente = true;
    const guardada = leidas.get(id);
    setFicha(guardada || null);
    setError("");
    if (guardada) return;
    api<Ficha>("/vacantes/" + encodeURIComponent(id) + "/ficha")
      .then((f) => {
        leidas.set(id, f);
        if (vigente) setFicha(f);
      })
      .catch((e) => vigente && setError((e as Error).message));
    return () => {
      vigente = false;
    };
  }, [id]);
  return { ficha, error };
}

export function textoExperiencia(anos: number | null | undefined) {
  if (anos === null || anos === undefined) return "Experiencia no informada";
  if (anos === 0) return "Sin años exigidos";
  return anos === 1 ? "1 año exigido" : anos + " años exigidos";
}

export function etiquetaEstado(v: Vacante) {
  if (v.estado === "lista") return v.tipo === "post" ? "Vigente" : "Verificada";
  if (v.estado === "retirada") return "Retirada";
  if (v.estado === "entregada")
    return `Entregada el ${fecha(v.entregada_el || "")}`;
  return "Por confirmar";
}

export function claseEstado(v: Vacante) {
  return v.estado === "lista"
    ? "green"
    : v.estado === "entregada"
      ? "neutral"
      : "amber";
}

export function etiquetaPost(v: { post_ubicacion?: string }) {
  return v.post_ubicacion === "deducida"
    ? "Post · ubicación deducida"
    : v.post_ubicacion === "sin_confirmar"
      ? "Post · ubicación sin confirmar"
      : "Post";
}

// Contrato v34: las negritas del aviso llegan entre «**» y se pintan en negrita (texto, nunca HTML).
export function ConNegritas({ texto }: { texto: string }) {
  const partes = texto.split(/\*\*([^*]+)\*\*/g);
  return (
    <>
      {partes.map((p, i) =>
        i % 2 ? <strong key={i}>{p}</strong> : p.replace(/\*\*/g, ""),
      )}
    </>
  );
}

// Lo que se sabe del aviso, igual en «Vacantes» y en «Por confirmar» (contrato v34).
export function DatosAviso({
  ubicacion,
  modalidad,
  salario,
  publicada,
  idioma,
  ingles,
  extra,
}: {
  ubicacion?: string;
  modalidad?: string;
  salario?: string;
  publicada?: string;
  idioma?: string;
  ingles?: string;
  extra?: React.ReactNode;
}) {
  return (
    <ul className="ficha-datos">
      <li>
        <MapPin size={14} />
        {ubicacion || "Ubicación no informada"}
      </li>
      <li>
        <Globe2 size={14} />
        {(modalidad && modos[modalidad]) ||
          modalidad ||
          "Modalidad no informada"}
      </li>
      {salario && (
        <li>
          <Wallet size={14} />
          {salario}
        </li>
      )}
      <li>
        <Clock3 size={14} />
        {publicada ? "Publicada el " + fecha(publicada) : "Fecha por confirmar"}
      </li>
      {extra}
      {idioma && (
        <li>
          <Languages size={14} />
          {idioma === "es" ? "Aviso en español" : "Aviso en inglés"}
          {ingles ? " · inglés " + ingles : ""}
        </li>
      )}
    </ul>
  );
}

// Viñetas seguidas van juntas en una lista.
function agrupar(bloques: BloqueFicha[]) {
  const grupos: (BloqueFicha | BloqueFicha[])[] = [];
  for (const b of bloques) {
    const ultimo = grupos.at(-1);
    if (b.tipo === "li" && Array.isArray(ultimo)) ultimo.push(b);
    else grupos.push(b.tipo === "li" ? [b] : b);
  }
  return grupos;
}

export function Descripcion({ id, enlace }: { id: string; enlace?: string }) {
  const { ficha, error } = useFicha(id);
  if (error)
    return (
      <p className="helper" role="alert">
        No se pudo leer el aviso: {error}
      </p>
    );
  if (!ficha)
    return (
      <p className="helper" role="status">
        Cargando el aviso…
      </p>
    );
  if (!ficha.bloques.length)
    return (
      <p className="helper">
        Este aviso no trae descripción; ábrelo en el sitio para leerlo completo.
        {(enlace || ficha.enlace) && (
          <>
            {" "}
            <a
              href={enlace || ficha.enlace}
              target="_blank"
              rel="noopener noreferrer"
              className="text-button"
            >
              Abrir en el sitio
              <ExternalLink size={14} />
            </a>
          </>
        )}
      </p>
    );
  return (
    <div className="ficha-descripcion">
      {agrupar(ficha.bloques).map((g, i) =>
        Array.isArray(g) ? (
          <ul key={i}>
            {g.map((b, j) => (
              <li key={j}>
                <ConNegritas texto={b.texto} />
              </li>
            ))}
          </ul>
        ) : g.tipo === "h" ? (
          <h4 key={i}>{g.texto}</h4>
        ) : (
          <p key={i}>
            <ConNegritas texto={g.texto} />
          </p>
        ),
      )}
      {ficha.origen === "traida" && (
        <p className="helper">Descripción leída hoy de la ficha original.</p>
      )}
    </div>
  );
}

export function FichaVacante({
  v,
  volver,
}: {
  v: Vacante;
  volver?: React.ReactNode;
}) {
  const { ficha } = useFicha(v.id);
  const explicacion = v.explicacion.filter(
    (e) => typeof e === "string" || Boolean(e.termino || e.regla),
  );
  return (
    <article className="ficha card" aria-labelledby={"ficha-" + v.id}>
      {volver}
      <header className="ficha-cabecera">
        <span className="company-avatar">{iniciales(v.empresa)}</span>
        <div>
          <span className="company-name">
            {v.empresa}
            <IdVacante numero={v.numero} />
          </span>
          <h2 id={"ficha-" + v.id}>{v.titulo}</h2>
        </div>
        <span className={"pill " + claseEstado(v)}>{etiquetaEstado(v)}</span>
      </header>
      <DatosAviso
        ubicacion={v.ubicacion}
        modalidad={v.modalidad}
        salario={ficha?.salario}
        publicada={v.publicada}
        idioma={v.idioma}
        ingles={ficha?.ingles}
        extra={
          <li>
            <Briefcase size={14} />
            {textoExperiencia(v.experiencia)}
          </li>
        }
      />
      <div className="vacancy-tags">
        <span>{grados[v.match_grade] || v.match_grade}</span>
        {v.tipo === "post" && (
          <span
            className="post-tag"
            title="Publicación de LinkedIn de quien contrata, sin ficha formal. Completa el mínimo de 5 y se contacta por mensaje o correo."
          >
            <Megaphone size={13} />
            {etiquetaPost(v)}
          </span>
        )}
        {(v.avisos || []).map((a) => (
          <span
            key={a}
            className="no-cumple"
            title="No cumple esto del perfil. Llega igual porque solo la ubicación y el idioma descartan; va después de las que encajan en todo."
          >
            {a}
          </span>
        ))}
        {v.ampliacion && (
          <span
            className="amplified"
            title="Entró para completar el mínimo de 5 vacantes de este perfil, aunque no es lo que pidió. Va en el mensaje de WhatsApp, al final y sin esta marca."
          >
            Ampliada: {v.ampliacion}
          </span>
        )}
      </div>
      <div className="ficha-acciones">
        <span className="ficha-comprobacion">
          <ShieldCheck size={13} />
          {v.estado === "entregada"
            ? "Ya entregada ese día; no se vuelve a compartir"
            : v.estado !== "lista"
              ? "No se incluirá en el mensaje"
              : v.tipo === "post"
                ? "Post leído en las últimas 24 h"
                : "Enlace con comprobación vigente"}
          {v.estado === "lista" && v.tipo !== "post" && (
            <Ayuda etiqueta="comprobación del enlace">
              El enlace se abrió hace menos de 24 horas y la vacante seguía
              publicada. Es la comprobación más reciente, no una garantía: la
              empresa puede cerrarla después sin avisar.
            </Ayuda>
          )}
        </span>
        {v.enlace && (
          <a
            href={v.enlace}
            target="_blank"
            rel="noopener noreferrer"
            className="button primary"
          >
            {v.tipo === "post"
              ? "Contactar a quien publicó"
              : "Ver vacante en el sitio"}
            <ExternalLink size={15} />
          </a>
        )}
      </div>
      {explicacion.length > 0 && (
        <section className="ficha-seccion">
          <h3>Por qué coincide</h3>
          <ul className="ficha-coincide">
            {explicacion.map((e, i) => (
              <li key={i}>
                <Check size={12} />
                {typeof e === "string"
                  ? e
                  : e.termino
                    ? "Cargo: " + e.termino
                    : e.regla}
              </li>
            ))}
          </ul>
          {v.motivos.length > 0 && (
            <p className="helper">Revisar: {v.motivos.join(" · ")}</p>
          )}
          {v.tipo === "post" && v.contacto?.correo && (
            <p className="helper">Correo en el post: {v.contacto.correo}</p>
          )}
        </section>
      )}
      <section className="ficha-seccion">
        <h3>
          {v.tipo === "post" ? "Texto del post" : "Descripción del aviso"}
        </h3>
        <Descripcion id={v.id} enlace={v.enlace} />
      </section>
    </article>
  );
}
