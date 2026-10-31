// Cloudflare Pages Function: historial de vacantes enviadas, compartido entre los equipos de quien usa la página.
// Necesita un espacio KV enlazado con el nombre ENVIADAS (Pages > Settings > Functions > KV namespace bindings).
// La página entera está detrás de Cloudflare Access, así que solo llegan aquí los correos autorizados.
const CLAVE = "ids";
const MAXIMO = 50000;

function json(datos, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export async function onRequestGet({ env }) {
  if (!env.ENVIADAS) return json({ error: "Falta el espacio KV ENVIADAS" }, 501);
  return json(JSON.parse((await env.ENVIADAS.get(CLAVE)) || "[]"));
}

export async function onRequestPost({ request, env }) {
  if (!env.ENVIADAS) return json({ error: "Falta el espacio KV ENVIADAS" }, 501);
  let nuevos;
  try { nuevos = await request.json(); } catch (e) { return json({ error: "Cuerpo inválido" }, 400); }
  if (!Array.isArray(nuevos)) return json({ error: "Se espera una lista de ids" }, 400);
  const actuales = new Set(JSON.parse((await env.ENVIADAS.get(CLAVE)) || "[]"));
  nuevos.filter(id => typeof id === "string" && /^[a-f0-9]{16}$/.test(id)).forEach(id => actuales.add(id));
  const lista = [...actuales].slice(-MAXIMO);
  await env.ENVIADAS.put(CLAVE, JSON.stringify(lista));
  return json({ total: lista.length });
}
