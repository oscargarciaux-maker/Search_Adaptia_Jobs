// «Clientes»: buscador, importar, una tarjeta por cliente y los archivados.
import {
  Archive,
  ArrowUpRight,
  BriefcaseBusiness,
  Clock3,
  Globe2,
  MapPin,
  Pencil,
  Plus,
  Search,
  Upload,
  Users,
} from "lucide-react";
import type {
  Cargo,
  Cliente,
  Configuracion,
  EstadoConfig,
  Perfil,
  Sesion,
} from "../types";
import {
  Empty,
  Plegable,
  modos,
  nombrePais,
  DistintivoComunidad,
} from "../comunes";
import { perfilSinCiudad } from "../perfiles";

import { ImportarClientes } from "./ImportarClientes";
import { BorrarClienteDialog, type Archivo } from "./DialogosArchivo";

export function Clientes({
  draft,
  cambiar,
  estado,
  dirty,
  sesion,
  clientes,
  profiles,
  search,
  setSearch,
  importando,
  setImportando,
  aBorrar,
  setABorrar,
  recibirEstado,
  notify,
  setEditCliente,
  setSelectedClient,
  setArchive,
  setModal,
  go,
}: {
  draft: Configuracion;
  cambiar: (v: Configuracion) => void;
  estado: EstadoConfig | null;
  dirty: boolean;
  sesion: Sesion;
  clientes: Cliente[];
  profiles: (id: string) => Perfil[];
  search: string;
  setSearch: (s: string) => void;
  importando: boolean;
  setImportando: (v: boolean) => void;
  aBorrar: Cliente | null;
  setABorrar: (c: Cliente | null) => void;
  recibirEstado: (e: EstadoConfig) => void;
  notify: (s: string, error?: boolean) => void;
  setEditCliente: (c: Cliente | null) => void;
  setSelectedClient: (id: string) => void;
  setArchive: (a: Archivo) => void;
  setModal: (m: "cliente" | "archivo") => void;
  go: (t: string) => void;
}) {
  return (
    <>
      <div className="toolbar">
        <div className="search-input">
          <Search size={17} />
          <input
            aria-label="Buscar cliente"
            placeholder="Buscar un cliente…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button
          className="button secondary"
          onClick={() => setImportando(true)}
        >
          <Upload size={16} />
          Importar clientes
        </button>
        <button
          className="button primary"
          onClick={() => {
            setEditCliente(null);
            setModal("cliente");
          }}
        >
          <Plus size={17} />
          Nuevo cliente
        </button>
      </div>
      {importando && (
        <ImportarClientes
          revision={estado?.revision ?? 0}
          dirty={dirty}
          notify={notify}
          onListo={recibirEstado}
          onClose={() => setImportando(false)}
        />
      )}
      {aBorrar && (
        <BorrarClienteDialog
          cliente={aBorrar}
          revision={estado?.revision ?? 0}
          dirty={dirty}
          notify={notify}
          onListo={recibirEstado}
          onClose={() => setABorrar(null)}
        />
      )}
      <div className="client-grid">
        {clientes
          .filter((c) => c.nombre.toLowerCase().includes(search.toLowerCase()))
          .map((c, i) => (
            <ClientCard
              key={c.id}
              c={c}
              index={i}
              perfiles={profiles(c.id)}
              cargos={draft.cargos}
              paises={sesion.paises}
              onEdit={() => {
                setEditCliente(c);
                setModal("cliente");
              }}
              onResults={() => {
                setSelectedClient(c.id);
                go("Vacantes");
              }}
              onArchive={() => {
                setArchive({
                  tipo: "cliente",
                  id: c.id,
                  nombre: c.nombre,
                });
                setModal("archivo");
              }}
            />
          ))}
      </div>
      {!clientes.length && (
        <Empty
          icon={Users}
          title="Todavía no tienes clientes"
          texto="Añade tu primer cliente para preparar sus criterios."
          action={() => {
            setEditCliente(null);
            setModal("cliente");
          }}
          label="Nuevo cliente"
        />
      )}
      {draft.clientes.some((c) => !c.activo) && (
        <Plegable
          className="archived"
          mostrar={
            "Ver archivados (" +
            draft.clientes.filter((c) => !c.activo).length +
            ")"
          }
          ocultar="Ocultar archivados"
        >
          {draft.clientes
            .filter((c) => !c.activo)
            .map((c) => (
              <div key={c.id}>
                {c.nombre}
                <button
                  className="text-button"
                  onClick={() =>
                    cambiar({
                      ...draft,
                      clientes: draft.clientes.map((x) =>
                        x.id === c.id ? { ...x, activo: true } : x,
                      ),
                    })
                  }
                >
                  Reactivar
                </button>
                <button
                  className="text-button peligro"
                  onClick={() => setABorrar(c)}
                >
                  Eliminar definitivamente
                </button>
              </div>
            ))}
        </Plegable>
      )}
    </>
  );
}

function ClientCard({
  c,
  perfiles,
  cargos,
  paises,
  onEdit,
  onResults,
  onArchive,
}: {
  c: Cliente;
  index?: number;
  perfiles: Perfil[];
  cargos: Cargo[];
  paises: Sesion["paises"];
  onEdit: () => void;
  onResults: () => void;
  onArchive?: () => void;
}) {
  // Sección 7a (13 nov): más baja, sin foto ni «Activo»; editar y vacantes a la vista.
  const p = perfiles[0],
    cargo = cargos.find((x) => x.id === p?.cargo_id);
  // Contrato v49: perfiles con presencial o híbrido sin ciudad (no les llegan esas vacantes).
  const sinCiudad = perfiles.filter(perfilSinCiudad).length;
  return (
    <article className="client-card card">
      <div className="client-top">
        <div className="client-title">
          <h3>
            {c.nombre}
            {c.comunidad && <DistintivoComunidad />}
          </h3>
          <span>
            {cargo?.nombre || "Sin perfil"}
            {perfiles.length > 1 ? " + " + (perfiles.length - 1) : ""}
          </span>
        </div>
        {p && (
          <div className="client-lugar">
            <span>
              {paises.find((x) => x.codigo === p.vive_en)?.nombre ||
                nombrePais(p.vive_en)}
              {p.paises_presenciales_extra.length > 0 &&
                " +" + p.paises_presenciales_extra.length}
            </span>
            <span>{p.modalidades.map((m) => modos[m]).join(" · ")}</span>
          </div>
        )}
      </div>
      <div className="client-details">
        <div>
          <Clock3 size={14} />
          <span>Publicadas en los últimos {p?.antiguedad_dias || 14} días</span>
        </div>
        <div>
          <BriefcaseBusiness size={14} />
          <span>
            {p?.experiencia_anos != null
              ? `${p.experiencia_anos} años · busca de ${p.experiencia_min} a ${p.experiencia_max}`
              : p?.experiencia_min === null && p?.experiencia_max === null
                ? "Sin filtro de experiencia"
                : (p?.experiencia_min ?? 0) +
                  "–" +
                  (p?.experiencia_max ?? 40) +
                  " años exigidos"}
          </span>
        </div>
        <div>
          <Globe2 size={14} />
          <span>
            {p?.idiomas
              .map((x) => (x === "es" ? "Español" : "Inglés"))
              .join(" / ") || "Sin idioma configurado"}
            {p?.ingles_maximo && p.ingles_maximo !== "sin_filtro"
              ? " · Inglés hasta " + p.ingles_maximo
              : ""}
          </span>
        </div>
        {sinCiudad > 0 && (
          <div className="falta-ciudad">
            <MapPin size={14} aria-hidden="true" />
            <span>
              Falta la ciudad
              {perfiles.length > 1
                ? ` en ${sinCiudad} ${sinCiudad === 1 ? "perfil" : "perfiles"}`
                : ""}
              : sin ciudad no llegan presenciales ni híbridas.
            </span>
          </div>
        )}
      </div>
      <div className="client-bottom">
        <button
          className="text-button editar"
          aria-label={"Editar " + c.nombre}
          onClick={onEdit}
        >
          <Pencil size={14} />
          Editar
        </button>
        {onArchive && (
          <button
            className="icon peligro"
            aria-label={"Archivar " + c.nombre}
            title="Archivar"
            onClick={onArchive}
          >
            <Archive size={15} />
          </button>
        )}
        {!(cargo?.activo && perfiles.some((p) => (p.meta_diaria ?? 1) > 0)) && (
          <span className="pill amber sin-cupo">Sin meta</span>
        )}
        <button className="button secondary small vacantes" onClick={onResults}>
          Vacantes
          <ArrowUpRight size={14} />
        </button>
      </div>
    </article>
  );
}
