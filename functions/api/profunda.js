// Cloudflare Pages Function: lanza en GitHub Actions la búsqueda en vivo de un cargo (flujo profunda.yml).
// Variables del proyecto de Pages (Settings > Variables and Secrets):
//   GITHUB_REPO          "usuario/repositorio" (texto)
//   GITHUB_TOKEN_FLUJOS  token de GitHub con permiso solo de "Actions: read and write" en ese repositorio (secreto)
function json(datos, status = 200) {
  return new Response(JSON.stringify(datos), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export async function onRequestPost({ request, env }) {
  if (!env.GITHUB_REPO || !env.GITHUB_TOKEN_FLUJOS) return json({ error: "Faltan GITHUB_REPO o GITHUB_TOKEN_FLUJOS" }, 501);
  let cuerpo;
  try { cuerpo = await request.json(); } catch (e) { return json({ error: "Cuerpo inválido" }, 400); }
  const consulta = String(cuerpo.consulta || "").trim().slice(0, 80);
  const pais = String(cuerpo.pais || "").trim().toUpperCase();
  if (!consulta || (pais && !/^[A-Z]{2}$/.test(pais))) return json({ error: "Consulta o país inválidos" }, 400);
  const r = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/profunda.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN_FLUJOS}`, Accept: "application/vnd.github+json",
               "User-Agent": "buscador-vacantes-latam", "X-GitHub-Api-Version": "2022-11-28" },
    body: JSON.stringify({ ref: "main", inputs: { consulta, pais } }),
  });
  if (r.status !== 204) return json({ error: `GitHub respondió ${r.status}` }, 502);
  return json({ ok: true });
}
