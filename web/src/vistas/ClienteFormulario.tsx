// Formulario del cliente y sus perfiles de búsqueda (contrato v30: ubicaciones en filas).
import React, { useEffect, useRef, useState } from "react";
import { Check, Loader2, Plus, Search, Target, X } from "lucide-react";
import { api, ErrorAPI } from "../api";
import {
  Ayuda,
  Plegable,
  Dialog,
  REGIONES,
  nombrePais,
  SelectorPaises,
  TagInput,
  ciudadesDe,
  utcDe,
} from "../comunes";
import type {
  Restriccion,
  Cargo,
  Cliente,
  Configuracion,
  Perfil,
  Contacto,
  EstimacionEnVivo,
  EstimacionPerfil,
  Ubicacion,
} from "../types";
import { conFilas, conMetas, filasDe, perfilNuevo, uid } from "../perfiles";
import { useVistaPrevia, type EstadoPrevia } from "../vistaPrevia";
import { CargoDialog } from "./CargoDialog";
import {
  CODIGOS,
  FRECUENTES,
  codigoDe,
  separarTelefono,
  unirTelefono,
} from "../telefonos";

const todosLosCodigos = [...new Set(CODIGOS.map((x) => x.pais))]
  .filter((x) => !FRECUENTES.includes(x))
  .sort((a, b) => nombrePais(a).localeCompare(nombrePais(b), "es"));

function OpcionCodigo({ pais }: { pais: string }) {
  return (
    <option value={pais}>
      {bandera(pais)} {nombrePais(pais)} +{codigoDe(pais)}
    </option>
  );
}

// Desde v27 solo descartan la ubicación y el idioma; el único ajuste que se aplica con un clic es el idioma.
export const ajustesSinDato: Record<string, Partial<Perfil>> = {
  "idioma del aviso diferente": { idiomas: ["es", "en"] },
};

export function PreviewPerfil({
  info,
  estado,
  motivo,
  pendiente,
  onAjustar,
}: {
  info?: EstimacionPerfil;
  estado: EstadoPrevia;
  motivo?: string;
  pendiente?: string;
  onAjustar: (cambio: Partial<Perfil>) => void;
}) {
  if (pendiente)
    return (
      <p className="preview muted-preview" role="status">
        Aún no se puede estimar este perfil: {pendiente}
      </p>
    );
  if (estado === "incompleto")
    return (
      <p className="preview muted-preview" role="status">
        Aún no se puede estimar: {motivo || "revisa los campos del perfil."}
      </p>
    );
  if (!info)
    return (
      <p className="preview muted-preview" role="status">
        {estado === "error" ? (
          "No se pudo estimar en este momento."
        ) : estado === "listo" ? (
          "Sin estimación para este perfil."
        ) : (
          <>
            <Loader2 size={13} className="spin" /> Calculando vacantes
            disponibles…
          </>
        )}
      </p>
    );
  const mes = info.ultimos_30 ?? info.compatibles;
  const porDia = info.por_dia ?? Math.round((mes / 30) * 10) / 10;
  return (
    <div
      className={
        "preview" +
        (mes === 0 ? " warn" : "") +
        (estado === "cargando" ? " stale" : "")
      }
      role="status"
      aria-live="polite"
    >
      {/* Contrato v35: la cifra principal son las que cumplieron el perfil en 30 días, con su promedio diario. */}
      <p className="preview-main">
        <Target size={15} />
        <span>
          <strong>{mes}</strong>{" "}
          {mes === 1 ? "vacante cumplió" : "vacantes cumplieron"} este perfil en
          los últimos 30 días{" "}
          <strong>· ≈ {String(porDia).replace(".", ",")} al día</strong>
          <span className="preview-sub">
            {" "}
            · {info.compatibles} aún sin entregar
            {info.compatibles < 5 && !!info.ampliables && (
              <> · +{info.ampliables} con ampliación hasta llegar a 5</>
            )}
          </span>
        </span>
      </p>
      {mes === 0 && (
        // Sesión de prueba (17 nov): un 0 asustaba («¿escribí mal Bogotá?»). Se dice por qué y qué hacer.
        <p className="preview-cero">
          No es un error de escritura: las tildes y las mayúsculas no importan.{" "}
          {info.del_cargo === 0
            ? "Aún no hay vacantes guardadas de este cargo: o es nuevo y la próxima búsqueda lo incluye, o se busca con pocos nombres (en «Cargos y metas», «Buscar denominaciones afines» suma más)."
            : `Hay ${info.del_cargo} vacantes del cargo, pero ninguna acepta su ubicación o su idioma.` +
              (info.limitantes.length
                ? " Abajo, lo que más sumaría:"
                : " Prueba con otra modalidad u otra ciudad.")}
        </p>
      )}
      {info.limitantes.length > 0 && (
        <ul className="preview-tips">
          {info.limitantes.slice(0, 2).map((l) => (
            <li key={l.motivo}>
              <span>
                {l.sugerencia}: <strong>+{l.vacantes}</strong>
              </span>
              {ajustesSinDato[l.motivo] && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => onAjustar(ajustesSinDato[l.motivo])}
                >
                  Aplicar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Por qué falló la petición, para que el operador sepa si esperar, volver a entrar o revisar el registro (13 nov).
export function motivoFalloEnVivo(e: unknown) {
  if (e instanceof DOMException && e.name === "TimeoutError")
    return "La búsqueda tardó más de un minuto y se canceló. Inténtalo de nuevo en un rato.";
  if (e instanceof ErrorAPI) {
    if (e.status === 401)
      return "Tu sesión se cerró: vuelve a entrar al panel.";
    if (e.status === 403)
      return "El panel rechazó la petición. Recarga la página y vuelve a intentarlo.";
    if (e.status === 422) return "Aún no se puede buscar: " + e.message;
    if (e.status >= 502)
      return "El servidor del panel no respondió a tiempo (puede estar despertando). Espera un minuto y vuelve a intentarlo.";
    return "La búsqueda falló por un error del servidor. Inténtalo de nuevo en un minuto.";
  }
  return "No hubo conexión con el panel. Revisa tu internet y vuelve a intentarlo.";
}

export function EnVivo({
  config,
  perfilId,
  onAjustar,
}: {
  config: Configuracion;
  perfilId: string;
  onAjustar: (cambio: Partial<Perfil>) => void;
}) {
  const [r, setR] = useState<EstimacionEnVivo | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  async function estimar() {
    setCargando(true);
    setError("");
    try {
      const x = await api<EstimacionEnVivo>("/estimacion-en-vivo", {
        method: "POST",
        body: JSON.stringify({ configuracion: config, perfil_id: perfilId }),
        signal: AbortSignal.timeout(75000),
      });
      if (x.incompleto)
        setError(
          "Aún no se puede buscar: " +
            (x.motivo || "revisa los campos del perfil."),
        );
      else if (x.ocupado || x.espera || x.error)
        setError(x.nota || x.error || "");
      else setR(x);
    } catch (e) {
      setError(motivoFalloEnVivo(e));
    } finally {
      setCargando(false);
    }
  }
  const fallo =
    r?.fuentes &&
    Object.entries(r.fuentes)
      .filter(([, f]) => f.error || (f.busquedas && f.fallidas === f.busquedas))
      .map(([n]) => n);
  return (
    <div className="live">
      <button
        type="button"
        className="button secondary small"
        disabled={cargando}
        onClick={estimar}
      >
        {cargando ? (
          <Loader2 size={14} className="spin" />
        ) : (
          <Search size={14} />
        )}
        {cargando
          ? "Buscando en LinkedIn y Get on Board… (hasta 30 s)"
          : r
            ? "Volver a buscar en internet"
            : "Buscar en internet ahora"}
      </button>
      {!cargando && (
        <span className="live-gratis">
          No gasta Apify: solo LinkedIn público y Get on Board, sin cuentas.
        </span>
      )}
      {error && (
        <p className="live-note" role="status">
          {error}
        </p>
      )}
      {r && !cargando && r.compatibles === 0 && (
        <p className="live-note" role="status">
          La búsqueda rápida revisó {r.avisos} avisos de hoy y ninguno nuevo
          cumple todo. Es solo una muestra: la cifra de los últimos 30 días, de
          arriba, es la que dice cuántas llegan.
        </p>
      )}
      {r && !cargando && (r.compatibles ?? 0) > 0 && (
        <div className="live-result" role="status" aria-live="polite">
          <p className="preview-main">
            <Target size={15} />
            <span>
              <strong>≈ {r.compatibles}</strong>{" "}
              {r.compatibles === 1
                ? "encontrada ahora en las fuentes cumple"
                : "encontradas ahora en las fuentes cumplen"}{" "}
              este perfil
              <span className="preview-sub">
                {" "}
                · {r.nuevas} aún no guardadas · {r.del_cargo} del cargo en{" "}
                {r.avisos} avisos revisados
                {r.ya_entregadas ? ` · ${r.ya_entregadas} ya entregadas` : ""}
              </span>
            </span>
          </p>
          {!!r.limitantes?.length && (
            <ul className="preview-tips">
              {r.limitantes.slice(0, 2).map((l) => (
                <li key={l.motivo}>
                  <span>
                    {l.sugerencia}: <strong>+{l.vacantes}</strong>
                  </span>
                  {ajustesSinDato[l.motivo] && (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => onAjustar(ajustesSinDato[l.motivo])}
                    >
                      Aplicar
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!!fallo?.length && (
            <p className="live-note">
              {fallo.join(" y ")} no respondió esta vez; el número puede quedar
              corto.
            </p>
          )}
          <p className="live-note">{r.nota}</p>
        </div>
      )}
    </div>
  );
}

export const MONEDAS = [
  "USD",
  "EUR",
  "COP",
  "MXN",
  "ARS",
  "CLP",
  "PEN",
  "BRL",
  "UYU",
  "DOP",
  "GTQ",
  "CRC",
];
export const TIPOS_CONTRATO: [string, string][] = [
  ["freelance", "Freelance o por proyecto"],
  ["part_time", "Medio tiempo"],
  ["contract", "Temporal o por prestación"],
  ["internship", "Prácticas o pasantía"],
];
export function FiltrosPerfil({
  p,
  i,
  patch,
}: {
  p: Perfil;
  i: number;
  patch: (id: string, v: Partial<Perfil>) => void;
}) {
  const restricciones = p.restricciones || [];
  const cambiar = (n: number, r: Restriccion) =>
    patch(p.id, {
      restricciones: restricciones.map((x, k) => (k === n ? r : x)),
    });
  const quitar = (n: number) =>
    patch(p.id, { restricciones: restricciones.filter((_, k) => k !== n) });
  const nueva = (tipo: string): Restriccion =>
    tipo === "salario_minimo"
      ? { tipo, monto: 0, moneda: "USD", periodo: "month" }
      : tipo === "palabras"
        ? { tipo, palabras: [] }
        : tipo === "otra"
          ? { tipo, texto: "" }
          : { tipo: "contrato", tipos: [] };
  return (
    <div className="filtros-perfil">
      <Plegable
        mostrar={
          "Prioridades (opcional)" +
          ((p.sectores_preferidos?.length || 0) +
          (p.palabras_preferidas?.length || 0)
            ? ` · ${(p.sectores_preferidos?.length || 0) + (p.palabras_preferidas?.length || 0)}`
            : "")
        }
        ocultar="Ocultar prioridades"
      >
        <p className="field-help">
          Solo ordenan: cuando hay más vacantes que la meta, primero las que
          mencionan estos sectores o palabras. Nunca descartan. Déjalas vacías
          si no ayudan (por ejemplo en QA).
        </p>
        <TagInput
          label={"Sectores preferidos del perfil " + (i + 1)}
          values={p.sectores_preferidos || []}
          onChange={(v) => patch(p.id, { sectores_preferidos: v })}
        />
        <TagInput
          label={"Palabras clave preferidas del perfil " + (i + 1)}
          values={p.palabras_preferidas || []}
          onChange={(v) => patch(p.id, { palabras_preferidas: v })}
        />
      </Plegable>
      <fieldset className="restricciones">
        <legend>Este perfil NO acepta…</legend>
        {restricciones.map((r, n) => (
          <div className="restriccion" key={n}>
            {r.tipo === "salario_minimo" && (
              <div className="restriccion-campos">
                <span>Salario menor a</span>
                <input
                  type="number"
                  min={1}
                  aria-label={`Salario mínimo del perfil ${i + 1}`}
                  value={r.monto || ""}
                  onChange={(e) =>
                    cambiar(n, { ...r, monto: Number(e.target.value) || 0 })
                  }
                />
                <select
                  aria-label={`Moneda del salario del perfil ${i + 1}`}
                  value={r.moneda}
                  onChange={(e) => cambiar(n, { ...r, moneda: e.target.value })}
                >
                  {MONEDAS.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
                <select
                  aria-label={`Periodo del salario del perfil ${i + 1}`}
                  value={r.periodo}
                  onChange={(e) =>
                    cambiar(n, { ...r, periodo: e.target.value })
                  }
                >
                  <option value="month">al mes</option>
                  <option value="year">al año</option>
                  <option value="hour">por hora</option>
                </select>
              </div>
            )}
            {r.tipo === "palabras" && (
              <TagInput
                label={`Vacantes que mencionan (perfil ${i + 1})`}
                values={r.palabras}
                onChange={(v) => cambiar(n, { ...r, palabras: v })}
              />
            )}
            {r.tipo === "otra" && (
              <div className="restriccion-campos">
                <span>Otra:</span>
                <input
                  aria-label={`Otra restricción del perfil ${i + 1}`}
                  maxLength={80}
                  placeholder="Ej.: agencias de reclutamiento"
                  value={r.texto}
                  onChange={(e) => cambiar(n, { ...r, texto: e.target.value })}
                />
              </div>
            )}
            {r.tipo === "contrato" && (
              <div className="restriccion-campos">
                <span>Contratos de tipo</span>
                {TIPOS_CONTRATO.map(([valor, texto]) => (
                  <label key={valor} className="chip-check">
                    <input
                      type="checkbox"
                      checked={r.tipos.includes(valor)}
                      onChange={(e) =>
                        cambiar(n, {
                          ...r,
                          tipos: e.target.checked
                            ? [...r.tipos, valor]
                            : r.tipos.filter((x) => x !== valor),
                        })
                      }
                    />
                    {texto}
                  </label>
                ))}
              </div>
            )}
            <button
              type="button"
              className="text-button"
              aria-label={`Quitar restricción ${n + 1} del perfil ${i + 1}`}
              onClick={() => quitar(n)}
            >
              Quitar
            </button>
          </div>
        ))}
        {restricciones.length < 10 && (
          <select
            className="nueva-restriccion"
            aria-label={`Añadir restricción al perfil ${i + 1}`}
            value=""
            onChange={(e) =>
              e.target.value &&
              patch(p.id, {
                restricciones: [...restricciones, nueva(e.target.value)],
              })
            }
          >
            <option value="">＋ Añadir restricción…</option>
            <option value="salario_minimo">Salario menor a…</option>
            <option value="palabras">Vacantes que mencionan…</option>
            <option value="contrato">Tipo de contrato…</option>
            <option value="otra">Otra…</option>
          </select>
        )}
        <p className="field-help">
          Nada de esto descarta: si el aviso lo dice claramente, la vacante
          llega después, con una etiqueta. El salario se compara también en
          otras monedas, con un margen del 10 %.
        </p>
      </fieldset>
    </div>
  );
}
export type BorradorCliente = {
  c: Cliente;
  ps: Perfil[];
  ct: Contacto;
  guardado: number;
};
// localStorage puede no existir o fallar (ventana privada, sitio bloqueado): nunca rompe el panel.
export function leerLocal<T>(clave: string): T | null {
  try {
    const v = window.localStorage.getItem(clave);
    return v ? (JSON.parse(v) as T) : null;
  } catch {
    return null;
  }
}
export function guardarLocal(clave: string, valor: unknown) {
  try {
    window.localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    /* sin almacenamiento: se sigue sin borrador */
  }
}
export function borrarLocal(clave: string) {
  try {
    window.localStorage.removeItem(clave);
  } catch {
    /* nada que borrar */
  }
}
export function ClienteDialog({
  cliente,
  config,
  contacto,
  onClose,
  onSave,
  onGuardarContacto,
  onCrearCargo,
}: {
  cliente: Cliente | null;
  config: Configuracion;
  // Contrato v30: el WhatsApp llega precargado (sin esperar al abrir) y se guarda sin hacer esperar al cerrar.
  contacto?: Contacto;
  onClose: () => void;
  onSave: (c: Cliente, p: Perfil[]) => void;
  onGuardarContacto: (id: string, ct: Contacto, tenia: boolean) => void;
  onCrearCargo: (c: Cargo) => void;
}) {
  // Sección 8 (13 nov): crear un cargo sin salir del cliente. `null` = cerrado; si no, el perfil que lo pidió.
  const [cargoPara, setCargoPara] = useState<string | null>(null);
  const [c, setC] = useState<Cliente>(
    cliente ? { ...cliente } : { id: uid(), nombre: "", activo: true },
  );
  // WhatsApp del cliente: se guarda al momento en una tabla privada, fuera de la configuración programada.
  const vacioContacto: Contacto = {
    telefono: "",
    nombre_saludo: "",
    consentimiento: false,
  };
  const contactoInicial = contacto || vacioContacto;
  const [ct, setCt] = useState<Contacto>(contactoInicial);
  // Contrato v35: el código del país se elige en una lista y se escribe solo el número.
  const [telPais, setTelPais] = useState(
    () =>
      separarTelefono(contactoInicial.telefono).pais ||
      (contactoInicial.telefono ? "" : "CO"),
  );
  const numero = separarTelefono(ct.telefono, telPais).numero;
  const [ps, setPs] = useState<Perfil[]>(() => {
    if (cliente)
      return structuredClone(
        config.perfiles.filter((p) => p.cliente_id === cliente.id),
      );
    // Un cliente nuevo empieza con un perfil listo para llenar (sección 7a).
    const primero = config.cargos.find((x) => x.activo);
    return primero ? [perfilNuevo(c.id, primero.id)] : [];
  });
  const [error, setError] = useState("");
  const cargos = config.cargos.filter((c) => c.activo);
  // Reunión del 14 nov: lo escrito se guarda solo en este navegador mientras se edita. Si algo falla (pantalla en
  // blanco, conexión), al volver a abrir el formulario se ofrece recuperarlo. Nada sale del navegador hasta guardar.
  const claveBorrador = "adaptia:borrador-cliente:" + (cliente?.id ?? "nuevo");
  const inicial = useRef(JSON.stringify({ c, ps, ct: contactoInicial }));
  const [recuperable, setRecuperable] = useState<BorradorCliente | null>(() => {
    const guardado = leerLocal<BorradorCliente>(claveBorrador);
    return guardado &&
      JSON.stringify({ c: guardado.c, ps: guardado.ps, ct: guardado.ct }) !==
        inicial.current
      ? guardado
      : null;
  });
  useEffect(() => {
    const actual = JSON.stringify({ c, ps, ct });
    if (actual !== inicial.current)
      guardarLocal(claveBorrador, { c, ps, ct, guardado: Date.now() });
  }, [c, ps, ct, claveBorrador]);
  function recuperar(b: BorradorCliente) {
    const activos = new Set(config.cargos.map((x) => x.id));
    setC(b.c);
    // Un cargo que ya no existe se cambia por el primero activo para que el perfil siga siendo válido.
    setPs(
      b.ps.map((p) =>
        activos.has(p.cargo_id) || !cargos.length
          ? p
          : { ...p, cargo_id: cargos[0].id },
      ),
    );
    setCt(b.ct);
    setRecuperable(null);
  }
  function patch(id: string, v: Partial<Perfil>) {
    setPs(ps.map((p) => (p.id === id ? { ...p, ...v } : p)));
  }
  const borrador: Configuracion = {
    ...config,
    clientes: [
      ...config.clientes.filter((x) => x.id !== c.id),
      { ...c, nombre: c.nombre.trim() || "Cliente", activo: true },
    ],
    perfiles: [...config.perfiles.filter((p) => p.cliente_id !== c.id), ...ps],
  };
  const previa = useVistaPrevia(borrador);
  const metasBorrador = conMetas(borrador);
  return (
    <>
      <Dialog
        ancho
        titulo={cliente ? "Editar cliente" : "Nuevo cliente"}
        subtitulo="Define qué oportunidades son útiles para esta persona."
        onClose={onClose}
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!ps.length) {
              setError("Añade al menos un perfil de búsqueda.");
              return;
            }
            if (!ps.every((p) => p.idiomas.length)) {
              setError("Elige al menos un idioma del aviso por perfil.");
              return;
            }
            const filaMala = ps.some((p) =>
              filasDe(p).some(
                (f) =>
                  !f.modalidades.length ||
                  (!f.paises.length && !f.ciudades.length),
              ),
            );
            if (filaMala) {
              setError(
                "Cada ubicación necesita un país o una ciudad y al menos una modalidad.",
              );
              return;
            }
            if (ct.telefono.trim() && !ct.telefono.trim().startsWith("+")) {
              setError("Elige el país del número de WhatsApp.");
              return;
            }
            if (JSON.stringify(ct) !== JSON.stringify(contactoInicial))
              onGuardarContacto(c.id, ct, Boolean(contacto));
            borrarLocal(claveBorrador);
            // Una restricción a medio llenar (sin monto, sin palabras ni tipos) no se guarda.
            onSave(
              c,
              ps.map((p) => ({
                ...p,
                restricciones: (p.restricciones || []).filter((r) =>
                  r.tipo === "salario_minimo"
                    ? r.monto > 0
                    : r.tipo === "palabras"
                      ? r.palabras.length > 0
                      : r.tipo === "otra"
                        ? r.texto.trim().length >= 2
                        : r.tipos.length > 0,
                ),
              })),
            );
          }}
        >
          {recuperable && (
            <div className="recuperar" role="status">
              <span>
                Tienes cambios sin guardar de las{" "}
                {new Date(recuperable.guardado).toLocaleTimeString("es-CO", {
                  hour: "numeric",
                  minute: "2-digit",
                })}
                .
              </span>
              <div>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => recuperar(recuperable)}
                >
                  Recuperar lo que escribías
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    borrarLocal(claveBorrador);
                    setRecuperable(null);
                  }}
                >
                  Descartar
                </button>
              </div>
            </div>
          )}
          {/* Contrato v35: el nombre ocupa media fila; el WhatsApp va debajo en una sola fila horizontal. */}
          <div className="cliente-cabecera">
            <div className="field">
              <label htmlFor="cliente-nombre">
                Nombre o referencia del cliente
              </label>
              <input
                id="cliente-nombre"
                autoFocus
                required
                maxLength={100}
                value={c.nombre}
                placeholder="Ej.: Ana Gómez · Diseño"
                onChange={(e) => setC({ ...c, nombre: e.target.value })}
              />
            </div>
            <span className="casilla-comunidad">
              <label>
                <input
                  type="checkbox"
                  checked={!!c.comunidad}
                  onChange={(e) => setC({ ...c, comunidad: e.target.checked })}
                />
                Es un grupo de WhatsApp (Comunidad)
              </label>
              <Ayuda etiqueta="grupo Comunidad">
                Un grupo en vez de una persona. Recibe vacantes solo cuando
                sobra cupo diario, después de atender a los clientes.
              </Ayuda>
            </span>
          </div>
          <fieldset className="whatsapp-contacto">
            <legend>WhatsApp (opcional)</legend>
            <label className="check-line">
              <input
                type="checkbox"
                checked={ct.consentimiento}
                onChange={(e) =>
                  setCt({ ...ct, consentimiento: e.target.checked })
                }
              />
              Aceptó recibir vacantes por WhatsApp
            </label>
            {ct.consentimiento && (
              <>
                <div className="whatsapp-fila">
                  <div className="field">
                    <label htmlFor="cliente-codigo">País</label>
                    <select
                      id="cliente-codigo"
                      value={telPais}
                      onChange={(e) => {
                        setTelPais(e.target.value);
                        setCt({
                          ...ct,
                          telefono: unirTelefono(e.target.value, numero),
                        });
                      }}
                    >
                      <option value="">Elige…</option>
                      <optgroup label="Frecuentes">
                        {FRECUENTES.map((x) => (
                          <OpcionCodigo key={x} pais={x} />
                        ))}
                      </optgroup>
                      <optgroup label="Todos los países">
                        {todosLosCodigos.map((x) => (
                          <OpcionCodigo key={x} pais={x} />
                        ))}
                      </optgroup>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="cliente-telefono">Número</label>
                    <input
                      id="cliente-telefono"
                      type="tel"
                      inputMode="tel"
                      autoComplete="off"
                      placeholder="300 123 4567"
                      value={numero}
                      onChange={(e) =>
                        setCt({
                          ...ct,
                          telefono: unirTelefono(telPais, e.target.value),
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="cliente-saludo">Nombre para saludar</label>
                    <input
                      id="cliente-saludo"
                      maxLength={60}
                      placeholder="Ej.: Ana"
                      value={ct.nombre_saludo}
                      onChange={(e) =>
                        setCt({ ...ct, nombre_saludo: e.target.value })
                      }
                    />
                  </div>
                </div>
                <p className="field-help">
                  Cada mañana tendrás su mensaje listo en «Mensajes». Nada se
                  envía solo.
                </p>
              </>
            )}
          </fieldset>
          <div className="section-title">
            <h3>Perfiles de búsqueda</h3>
            <span className="muted">
              {ps.length} {ps.length === 1 ? "perfil" : "perfiles"}
            </span>
          </div>
          {ps.map((p, i) => (
            <section className="profile-editor" key={p.id}>
              <div className="profile-heading">
                <span className="tiny-kicker">PERFIL {i + 1}</span>
                <button
                  type="button"
                  className="text-button danger"
                  onClick={() => setPs(ps.filter((x) => x.id !== p.id))}
                >
                  Quitar perfil
                </button>
              </div>
              <div className="form-grid dos">
                <div className="field">
                  <label htmlFor={"cargo-" + p.id}>Cargo</label>
                  <select
                    id={"cargo-" + p.id}
                    aria-label={"Cargo del perfil " + (i + 1)}
                    value={p.cargo_id}
                    onChange={(e) =>
                      e.target.value === "__nuevo"
                        ? setCargoPara(p.id)
                        : patch(p.id, { cargo_id: e.target.value })
                    }
                  >
                    {cargos.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                    {config.cargos
                      .filter((c) => !c.activo)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nombre} (archivado: se reactiva al guardar)
                        </option>
                      ))}
                    <option value="__nuevo">＋ Añadir cargo nuevo…</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor={"meta-" + p.id}>Meta diaria</label>
                  <input
                    id={"meta-" + p.id}
                    aria-label={"Meta diaria del perfil " + (i + 1)}
                    type="number"
                    min={0}
                    max={120}
                    value={p.meta_diaria ?? metasBorrador.metaDe(p)}
                    onChange={(e) =>
                      patch(p.id, {
                        meta_diaria: Math.max(
                          0,
                          Math.min(120, Number(e.target.value) || 0),
                        ),
                      })
                    }
                  />
                </div>
              </div>
              <UbicacionesPerfil p={p} i={i} patch={patch} />
              <div className="form-grid tres">
                <div className="field">
                  <label htmlFor={"antiguedad-" + p.id}>
                    Antigüedad máxima de publicación
                  </label>
                  <select
                    id={"antiguedad-" + p.id}
                    aria-label={"Antigüedad del perfil " + (i + 1)}
                    value={p.antiguedad_dias}
                    onChange={(e) =>
                      patch(p.id, { antiguedad_dias: Number(e.target.value) })
                    }
                  >
                    {[1, 3, 7, 14, 21, 30].map((n) => (
                      <option key={n} value={n}>
                        {n} {n === 1 ? "día" : "días"}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <span className="etiqueta-ayuda">
                    <label htmlFor={"anos-" + p.id}>Años de experiencia</label>
                    <Ayuda etiqueta="años de experiencia">
                      {p.experiencia_anos != null
                        ? p.experiencia_anos <= 2
                          ? "Con 2 años o menos no se filtra por experiencia: entra cualquier vacante de entrada."
                          : `Busca vacantes que pidan de ${p.experiencia_min} a ${p.experiencia_max} años.` +
                            (p.experiencia_anos >= 5
                              ? " Las junior o de prácticas van al final, con su etiqueta."
                              : "")
                        : p.experiencia_min !== null ||
                            p.experiencia_max !== null
                          ? `Hoy busca de ${p.experiencia_min ?? 0} a ${p.experiencia_max ?? 40} años. Si escribes sus años, buscará de 3 menos a 3 más.`
                          : "Vacío: sin filtro de experiencia. Con un valor, busca de 3 años menos a 3 más."}{" "}
                      Los años solo ordenan: las que piden otros años llegan
                      después, con su etiqueta.
                    </Ayuda>
                  </span>
                  {/* Sesión de prueba (17 nov): una lista con sus límites, en vez de escribir el número. */}
                  <select
                    id={"anos-" + p.id}
                    aria-label={"Años de experiencia del perfil " + (i + 1)}
                    value={p.experiencia_anos ?? ""}
                    onChange={(e) => {
                      // Contratos v20 y v22: de N años menos a N más (el servidor hace la misma cuenta).
                      const n =
                        e.target.value === ""
                          ? null
                          : Math.max(0, Math.min(40, Number(e.target.value)));
                      const m = p.margen_experiencia ?? 3;
                      patch(p.id, {
                        experiencia_anos: n,
                        experiencia_min: n === null ? null : Math.max(0, n - m),
                        experiencia_max:
                          n === null ? null : Math.min(40, n + m),
                      });
                    }}
                  >
                    <option value="">
                      {p.experiencia_anos == null &&
                      (p.experiencia_min !== null || p.experiencia_max !== null)
                        ? `Como hoy: ${p.experiencia_min ?? 0}–${p.experiencia_max ?? 40} años`
                        : "Sin filtro"}
                    </option>
                    <option value={0}>Sin experiencia</option>
                    {Array.from(
                      { length: Math.max(20, p.experiencia_anos ?? 0) },
                      (_, k) => k + 1,
                    ).map((n) => (
                      <option key={n} value={n}>
                        {n} {n === 1 ? "año" : "años"}
                      </option>
                    ))}
                  </select>
                  <select
                    className="margen"
                    aria-label={"Margen de años del perfil " + (i + 1)}
                    value={p.margen_experiencia ?? 3}
                    onChange={(e) => {
                      const m = Number(e.target.value) as 3 | 4;
                      const n = p.experiencia_anos;
                      patch(p.id, {
                        margen_experiencia: m,
                        ...(n != null
                          ? {
                              experiencia_min: Math.max(0, n - m),
                              experiencia_max: Math.min(40, n + m),
                            }
                          : {}),
                      });
                    }}
                  >
                    <option value={3}>Margen ±3 años</option>
                    <option value={4}>Margen ±4 años</option>
                  </select>
                </div>
              </div>
              <div className="form-grid dos">
                <div
                  className="field"
                  role="group"
                  aria-labelledby={"idioma-" + p.id}
                >
                  <span className="campo-titulo" id={"idioma-" + p.id}>
                    Idioma del aviso
                  </span>
                  <div className="check-line">
                    {[
                      ["es", "Español"],
                      ["en", "Inglés"],
                    ].map(([code, label]) => (
                      <label key={code}>
                        <input
                          type="checkbox"
                          checked={p.idiomas.includes(code)}
                          onChange={(e) =>
                            patch(p.id, {
                              idiomas: e.target.checked
                                ? [...p.idiomas, code]
                                : p.idiomas.filter((x) => x !== code),
                            })
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </div>
                {p.idiomas.includes("en") && (
                  <div className="field">
                    <span className="etiqueta-ayuda">
                      <label htmlFor={"ingles-" + p.id}>
                        Inglés requerido: hasta
                      </label>
                      <Ayuda etiqueta="nivel de inglés">
                        Es el nivel que pide el aviso, aparte del idioma en que
                        está escrito. Solo ordena: las que piden más nivel
                        llegan después, con la etiqueta «Pide inglés C1».
                      </Ayuda>
                    </span>
                    <select
                      id={"ingles-" + p.id}
                      aria-label={"Inglés del perfil " + (i + 1)}
                      value={p.ingles_maximo}
                      onChange={(e) =>
                        patch(p.id, { ingles_maximo: e.target.value })
                      }
                    >
                      <option value="sin_filtro">Sin filtro</option>
                      {["A1", "A2", "B1", "B2", "C1", "C2", "native"].map(
                        (n) => (
                          <option value={n} key={n}>
                            {n === "native" ? "Nativo" : n}
                          </option>
                        ),
                      )}
                    </select>
                  </div>
                )}
              </div>
              <FiltrosPerfil p={p} i={i} patch={patch} />
              <PreviewPerfil
                info={previa.datos?.perfiles?.[p.id]}
                estado={previa.estado}
                motivo={previa.motivo}
                pendiente={previa.datos?.incompletos?.[p.id]}
                onAjustar={(cambio) => patch(p.id, cambio)}
              />
              <EnVivo
                config={borrador}
                perfilId={p.id}
                onAjustar={(cambio) => patch(p.id, cambio)}
              />
            </section>
          ))}
          {ps.length ? (
            <button
              type="button"
              disabled={!cargos.length}
              className="text-button otro-perfil"
              onClick={() => setPs([...ps, perfilNuevo(c.id, cargos[0].id)])}
            >
              <Plus size={15} />
              Añadir otro perfil
            </button>
          ) : (
            <button
              type="button"
              disabled={!cargos.length}
              className="button secondary full dashed"
              onClick={() => setPs([...ps, perfilNuevo(c.id, cargos[0].id)])}
            >
              <Plus size={16} />
              Añadir perfil de búsqueda
            </button>
          )}
          {!cargos.length && (
            <button
              type="button"
              className="button secondary"
              onClick={() => setCargoPara("")}
            >
              <Plus size={16} />
              Añadir cargo
            </button>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => {
                borrarLocal(claveBorrador);
                onClose();
              }}
            >
              Cancelar
            </button>
            <button className="button primary">
              {cliente ? "Aplicar cambios" : "Añadir cliente"}
              <Check size={15} />
            </button>
          </div>
        </form>
      </Dialog>
      {cargoPara !== null && (
        <CargoDialog
          cargo={null}
          notify={() => undefined}
          onClose={() => setCargoPara(null)}
          onSave={(nuevo) => {
            onCrearCargo(nuevo);
            const destino = cargoPara;
            if (destino)
              setPs((actuales) =>
                actuales.map((x) =>
                  x.id === destino ? { ...x, cargo_id: nuevo.id } : x,
                ),
              );
            else
              setPs((actuales) => [...actuales, perfilNuevo(c.id, nuevo.id)]);
            setCargoPara(null);
          }}
        />
      )}
    </>
  );
}

// La bandera de un país a partir de su código ISO (solo se muestra).
function bandera(codigo: string) {
  return String.fromCodePoint(
    ...[...codigo.toUpperCase()].map((l) => 0x1f1e6 + l.charCodeAt(0) - 65),
  );
}
const MODALIDADES: [string, string][] = [
  ["remoto", "Remoto"],
  ["hibrido", "Híbrido"],
  ["presencial", "Presencial"],
];
// Contrato v35: zonas horarias en las que puede trabajar, con ciudades de referencia. Las antiguas se leen así.
const ZONAS: [string, string][] = [
  ["UTC-10", "Honolulu"],
  ["UTC-9", "Anchorage"],
  ["UTC-8", "Los Ángeles, Vancouver"],
  ["UTC-7", "Denver, Phoenix"],
  ["UTC-6", "Ciudad de México, Chicago, San José"],
  ["UTC-5", "Bogotá, Lima, Nueva York"],
  ["UTC-4", "Santiago, Caracas, Santo Domingo"],
  ["UTC-3", "Buenos Aires, Montevideo, São Paulo"],
  ["UTC-1", "Azores"],
  ["UTC+0", "Londres, Lisboa"],
  ["UTC+1", "Madrid, París, Berlín"],
  ["UTC+2", "Atenas, Helsinki, El Cairo"],
  ["UTC+3", "Estambul, Moscú, Nairobi"],
  ["UTC+4", "Dubái"],
  ["UTC+5", "Karachi"],
  ["UTC+5:30", "India"],
  ["UTC+7", "Bangkok, Yakarta"],
  ["UTC+8", "Singapur, Manila, Pekín"],
  ["UTC+9", "Tokio, Seúl"],
  ["UTC+10", "Sídney"],
  ["UTC+12", "Auckland"],
];
const ANTIGUAS: Record<string, string> = {
  us_este: "UTC-5",
  us_pacifico: "UTC-8",
  europa: "UTC+1",
};
const nombreZona = (z: string, vive?: number | null) => {
  const c = ZONAS.find(([v]) => v === z)?.[1];
  const base = c ? `${z.replace("-", "−")} · ${c}` : z.replace("-", "−");
  return vive == null ? base : `${base} (${diferencia(z, vive)})`;
};
// Sesión de prueba (17 nov): la zona dicha respecto a donde vive («2 h menos que donde vive»).
function horasDe(z: string) {
  const m = /^UTC([+-])(\d{1,2})(?::(\d{2}))?$/.exec(z);
  if (!m) return 0;
  const h = Number(m[2]) + Number(m[3] || 0) / 60;
  return m[1] === "-" ? -h : h;
}
function diferencia(z: string, vive: number) {
  const d = horasDe(z) - vive;
  if (d === 0) return "misma hora que donde vive";
  const n = Math.abs(d);
  const t = Number.isInteger(n)
    ? `${n} h`
    : `${Math.floor(n)} h ${Math.round((n % 1) * 60)} min`;
  return `${t} ${d > 0 ? "más" : "menos"} que donde vive`;
}

function ZonasHorarias({
  p,
  i,
  patch,
}: {
  p: Perfil;
  i: number;
  patch: (id: string, v: Partial<Perfil>) => void;
}) {
  const zonas = [
    ...new Set((p.acepta_horario || []).map((z) => ANTIGUAS[z] || z)),
  ];
  const guardar = (v: string[]) => patch(p.id, { acepta_horario: v });
  const vive = utcDe(p.vive_en);
  return (
    <div className="zonas-horarias">
      <span className="etiqueta-ayuda">
        <span className="campo-titulo" id={"zonas-" + p.id}>
          Otras zonas horarias en las que puede trabajar (opcional)
        </span>
        <Ayuda etiqueta="zonas horarias">
          La zona de donde vive siempre cuenta. Una remota que solo pide un
          horario (por ejemplo «horario de Nueva York») le llega si cruza alguna
          de estas zonas, con una hora de margen.
        </Ayuda>
      </span>
      <div
        className="zonas-lista"
        role="group"
        aria-labelledby={"zonas-" + p.id}
      >
        {zonas.map((z) => (
          <span className="chip-zona" key={z}>
            {nombreZona(z, vive)}
            <button
              type="button"
              className="icon"
              aria-label={`Quitar ${nombreZona(z)} del perfil ${i + 1}`}
              onClick={() => guardar(zonas.filter((x) => x !== z))}
            >
              <X size={13} />
            </button>
          </span>
        ))}
        {zonas.length < 12 && (
          <select
            aria-label={`Añadir zona horaria al perfil ${i + 1}`}
            value=""
            onChange={(e) =>
              e.target.value && guardar([...zonas, e.target.value])
            }
          >
            <option value="">＋ Añadir zona…</option>
            {ZONAS.filter(([v]) => !zonas.includes(v)).map(([v]) => (
              <option key={v} value={v}>
                {nombreZona(v, vive)}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

// Contrato v30: dónde trabajaría, en filas «Ciudades · Países · modalidades». La primera es donde vive. Reemplaza a
// «se mudaría a», las casillas de países y «puede trabajar legalmente en».
function UbicacionesPerfil({
  p,
  i,
  patch,
}: {
  p: Perfil;
  i: number;
  patch: (id: string, v: Partial<Perfil>) => void;
}) {
  const filas = filasDe(p);
  const regiones = REGIONES.map((r) => r.codigo);
  const guardar = (nuevas: Ubicacion[]) =>
    patch(p.id, conFilas(p, nuevas, regiones));
  const cambiar = (n: number, cambio: Partial<Ubicacion>) =>
    guardar(filas.map((f, k) => (k === n ? { ...f, ...cambio } : f)));
  return (
    <fieldset className="ubicaciones">
      <legend>
        ¿Dónde trabajaría?{" "}
        <Ayuda etiqueta="ubicaciones">
          Una fila por lugar. La primera es donde vive. Una vacante sirve si
          alguna fila la acepta: remota abierta a uno de sus países, o híbrida o
          presencial con oficina en uno de sus países o ciudades. Para quien
          tiene permiso de trabajo en otro país, añade una fila con ese país y
          «Remoto». Las ciudades son opcionales: vacío es cualquier ciudad.
        </Ayuda>
      </legend>
      {filas.map((f, n) => (
        <div className="ubicacion-fila" key={n}>
          <span className="ubicacion-titulo">
            {n === 0 ? "¿Dónde vive?" : "Ubicación " + (n + 1)}
          </span>
          {/* Sesión de prueba (17 nov): primero el país; después la ciudad, con sugerencias de ese país. */}
          <SelectorPaises
            visible="Países"
            etiqueta={`Países de la ubicación ${n + 1}, perfil ${i + 1}`}
            placeholder={n === 0 ? "Ej.: Colombia" : "Ej.: España o LATAM"}
            valores={f.paises}
            onChange={(v) => cambiar(n, { paises: v })}
            extra={n === 0 ? [] : REGIONES}
          />
          <TagInput
            visible="Ciudades"
            label={`Ciudades de la ubicación ${n + 1}, perfil ${i + 1}`}
            placeholder={
              f.paises.length
                ? "Elige o escribe una ciudad (opcional)"
                : "Primero elige el país (opcional)"
            }
            values={f.ciudades}
            onChange={(v) => cambiar(n, { ciudades: v })}
            sugerencias={ciudadesDe(f.paises)}
          />
          <div
            className="ubicacion-modos"
            role="group"
            aria-label={`Modalidades de la ubicación ${n + 1}, perfil ${i + 1}`}
          >
            {MODALIDADES.map(([v, t]) => (
              <label key={v}>
                <input
                  type="checkbox"
                  aria-label={`${t} en la ubicación ${n + 1} del perfil ${i + 1}`}
                  checked={f.modalidades.includes(v)}
                  onChange={(e) =>
                    cambiar(n, {
                      modalidades: e.target.checked
                        ? [...f.modalidades, v]
                        : f.modalidades.filter((x) => x !== v),
                    })
                  }
                />
                {t}
              </label>
            ))}
          </div>
          {n > 0 && (
            <button
              type="button"
              className="icon"
              aria-label={`Quitar la ubicación ${n + 1} del perfil ${i + 1}`}
              onClick={() => guardar(filas.filter((_, k) => k !== n))}
            >
              <X size={16} />
            </button>
          )}
        </div>
      ))}
      <div className="ubicaciones-pie">
        {filas.length < 10 && (
          <button
            type="button"
            className="text-button"
            onClick={() =>
              guardar([
                ...filas,
                { paises: [], ciudades: [], modalidades: ["remoto"] },
              ])
            }
          >
            <Plus size={15} />
            Añadir otra ubicación
          </button>
        )}
        <ZonasHorarias p={p} i={i} patch={patch} />
      </div>
    </fieldset>
  );
}
