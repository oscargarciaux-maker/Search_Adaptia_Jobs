export class ErrorAPI extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  ruta: string,
  opciones: RequestInit = {},
): Promise<T> {
  const r = await fetch("/api" + ruta, {
    ...opciones,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...opciones.headers },
  });
  const d = await r
    .json()
    .catch(() => ({ detail: "No se pudo leer la respuesta del servidor." }));
  if (!r.ok) {
    if (r.status === 401) window.dispatchEvent(new Event("sesion-vencida"));
    throw new ErrorAPI(
      d.errores?.map((x: { mensaje: string }) => x.mensaje).join(" · ") ||
        d.detail ||
        "No se pudo confirmar la operación.",
      r.status,
    );
  }
  return d as T;
}
