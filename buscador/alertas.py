"""Alertas por correo al operador (contrato v10): búsqueda completa, pocas vacantes o fallo.

El destinatario se configura en el panel y vive en Supabase (`panel_ajustes`), nunca en el repositorio ni en los logs.
Se envía con la API de Resend (`RESEND_API_KEY`, remitente `ALERTAS_REMITENTE`). Sin clave o sin destinatario no se
envía nada y solo se anota. El correo no incluye nombres ni datos de clientes: cifras por cargo y enlaces.
"""
import argparse
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

TIPOS = ("exito", "pocas_vacantes", "fallo")
RESEND = "https://api.resend.com/emails"
CORREO = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
FALLOS_HORARIOS_PARA_AVISAR = 3


def hoy_bogota():
    return datetime.now(timezone(timedelta(hours=-5))).date().isoformat()


class Ajustes:
    """Lectura y escritura de `panel_ajustes` con la credencial de servicio."""

    def __init__(self, sesion=None):
        from buscador import supabase
        self.url, self.clave = supabase.credenciales()
        self.sesion = sesion or requests.Session()

    @property
    def disponible(self):
        return bool(self.url and self.clave)

    def _cab(self):
        cab = {"apikey": self.clave, "Content-Type": "application/json"}
        if self.clave.startswith("eyJ"):
            cab["Authorization"] = "Bearer " + self.clave
        return cab

    def leer(self, clave, defecto=None):
        r = self.sesion.get(f"{self.url}/rest/v1/panel_ajustes", headers=self._cab(), timeout=20,
                            params={"clave": "eq." + clave, "select": "valor", "limit": 1})
        if r.status_code != 200:
            return defecto
        filas = r.json()
        return filas[0]["valor"] if filas else defecto

    def guardar(self, clave, valor):
        r = self.sesion.post(f"{self.url}/rest/v1/panel_ajustes", headers={**self._cab(),
                             "Prefer": "resolution=merge-duplicates,return=minimal"}, timeout=20,
                             params={"on_conflict": "clave"},
                             json={"clave": clave, "valor": valor, "actualizado_en": datetime.now(timezone.utc).isoformat()})
        return r.status_code in (200, 201, 204)

    def ejecucion_panel(self, fecha):
        r = self.sesion.get(f"{self.url}/rest/v1/panel_ejecuciones", headers=self._cab(), timeout=20,
                            params={"fecha": "eq." + fecha, "select": "estado,resumen", "limit": 1})
        return (r.json() or [None])[0] if r.status_code == 200 else None


def configuracion_valida(valor):
    """{destinatarios, tipos} limpios; lanza ValueError con un mensaje para el operador."""
    valor = valor or {}
    destinatarios = [d.strip() for d in valor.get("destinatarios", []) if str(d).strip()]
    if len(destinatarios) > 5:
        raise ValueError("Escribe como máximo 5 correos.")
    for d in destinatarios:
        if len(d) > 120 or not CORREO.match(d):
            raise ValueError("Revisa el correo: debe tener la forma nombre@example.com.")
    tipos = [t for t in valor.get("tipos", list(TIPOS)) if t in TIPOS]
    return {"destinatarios": list(dict.fromkeys(destinatarios)), "tipos": tipos}


def fuentes_con_clave_invalida(salud):
    """Fuentes pagadas cuya clave fue rechazada (Apify tras rotar sus claves): sin aviso, la fuente cae a 0 en silencio."""
    return [n for n, v in ((salud or {}).get("fuentes") or {}).items() if isinstance(v, dict) and v.get("clave_invalida")]


def decidir(modo, resultado, salud, panel=None, fallos_seguidos=0):
    """Qué alerta corresponde, o None. `modo`: diario (noche), manana (pasada de la mañana) o horaria."""
    entrega = (salud or {}).get("entrega") or {}
    tecnico = resultado != "success" and (not salud or not entrega or any(
        (entrega.get(k) or {}).get("pendientes") or (entrega.get(k) or {}).get("errores")
        for k in ("supabase", "registro_seleccion")))
    if modo == "horaria":
        return "fallo" if resultado != "success" and fallos_seguidos == FALLOS_HORARIOS_PARA_AVISAR else None
    if tecnico or fuentes_con_clave_invalida(salud):
        return "fallo"
    bajo_minimo = ((panel or {}).get("resumen") or {}).get("perfiles_bajo_minimo", 0)
    if entrega.get("meta_cumplida") and not bajo_minimo:
        return "exito"
    # La noche con faltantes no avisa todavía: la pasada de la mañana intenta completar el día.
    return "pocas_vacantes" if modo == "manana" else None


def contenido(tipo, modo, salud, panel=None, enlace_ejecucion="", enlace_panel=""):
    """(asunto, html, texto). Solo cifras por cargo; sin nombres de clientes."""
    entrega = (salud or {}).get("entrega") or {}
    resumen = (panel or {}).get("resumen") or {}
    fecha = (salud or {}).get("fecha") or hoy_bogota()
    total, meta = entrega.get("vacantes", resumen.get("vacantes", 0)), resumen.get("meta", 120)
    momento = {"diario": "la búsqueda de la noche", "manana": "la pasada de la mañana",
               "horaria": "las capturas de cada hora"}[modo]
    asunto = {"exito": f"Adaptia · {fecha}: {total} de {meta} vacantes listas",
              "pocas_vacantes": f"Adaptia · {fecha}: faltan vacantes ({total} de {meta})",
              "fallo": f"Adaptia · {fecha}: {momento} necesita revisión"}[tipo]
    lineas = []
    claves = fuentes_con_clave_invalida(salud)
    if claves:
        lineas.append(f"{', '.join(claves)} rechazó la clave: crea una nueva en Apify (Settings → API & Integrations) y "
                      "actualiza el secreto APIFY_TOKEN en GitHub (Settings → Secrets → Actions). Mientras tanto esa "
                      "fuente no aporta vacantes.")
    if tipo == "fallo" and not (claves and entrega):
        lineas.append(f"Falló {momento}. Lo ya entregado se conserva; la siguiente ejecución reintenta sola. "
                      "Abre el registro para ver el error.")
    elif tipo == "fallo":
        lineas.append(f"Resultado de {momento}: {total} vacantes de {meta}.")
    else:
        lineas.append(f"Resultado de {momento}: {total} vacantes de {meta}.")
    roles = entrega.get("roles") or {}
    embudo = entrega.get("embudo") or {}
    for rid, r in roles.items():
        texto = f"{r.get('nombre', rid)}: {r.get('entregadas', 0)}"
        if r.get("faltan"):
            texto += f" (faltan {r['faltan']})"
        ampliadas = sum((r.get("ampliadas") or {}).values())
        if ampliadas:
            texto += f", {ampliadas} por ampliación"
        perdida = (embudo.get(rid) or {}).get("principal_perdida")
        if r.get("faltan") and perdida:
            texto += f". Mayor pérdida: {perdida}"
        lineas.append("• " + texto)
    if not resumen.get("perfiles_bajo_minimo"):
        resumen = dict(resumen, perfiles_bajo_minimo=sum(r.get("perfiles_bajo_minimo", 0) for r in roles.values()))
    if resumen.get("perfiles_bajo_minimo"):
        lineas.append(f"{resumen['perfiles_bajo_minimo']} perfil(es) de clientes quedaron con menos de 5 vacantes. "
                      "Revisa sus filtros con «Estimar con búsqueda en vivo».")
    enlaces = [(t, u) for t, u in (("Ver en el panel", enlace_panel), ("Ver el registro de la ejecución", enlace_ejecucion)) if u]
    texto = "\n".join(lineas + [f"{t}: {u}" for t, u in enlaces])
    cuerpo = "".join(f"<p>{html.escape(l)}</p>" for l in lineas)
    cuerpo += "".join(f'<p><a href="{html.escape(u)}">{html.escape(t)}</a></p>' for t, u in enlaces)
    return asunto, f'<div style="font-family:sans-serif;font-size:15px;color:#1e3028">{cuerpo}</div>', texto


def enviar(destinatarios, asunto, cuerpo_html, cuerpo_texto, sesion=None):
    """True si Resend aceptó el correo. Nunca escribe direcciones en el log."""
    clave, remitente = os.environ.get("RESEND_API_KEY", "").strip(), os.environ.get("ALERTAS_REMITENTE", "").strip()
    if not clave or not remitente or not destinatarios:
        return False
    r = (sesion or requests).post(RESEND, timeout=20, headers={"Authorization": "Bearer " + clave},
                                  json={"from": remitente, "to": destinatarios, "subject": asunto,
                                        "html": cuerpo_html, "text": cuerpo_texto})
    return r.status_code in (200, 201, 202)


def correr(modo, resultado, salida, ajustes=None, sesion=None):
    ajustes = ajustes or Ajustes()
    if not ajustes.disponible:
        return "sin Supabase: no hay dónde leer el destinatario"
    config = configuracion_valida(ajustes.leer("alertas", {}))
    estado = ajustes.leer("alertas_estado", {}) or {}
    if modo == "horaria":
        estado["fallos_horarios_seguidos"] = 0 if resultado == "success" else estado.get("fallos_horarios_seguidos", 0) + 1
        ajustes.guardar("alertas_estado", estado)
    try:
        salud = json.loads((Path(salida) / "datos/salud.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        salud = None
    fecha = (salud or {}).get("fecha") or hoy_bogota()
    panel = ajustes.ejecucion_panel(fecha) if modo != "horaria" else None
    tipo = decidir(modo, resultado, salud, panel, estado.get("fallos_horarios_seguidos", 0))
    if not tipo:
        return "sin alerta para este resultado"
    if tipo not in config["tipos"] or not config["destinatarios"]:
        return f"alerta «{tipo}» desactivada o sin destinatario"
    repo, run = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", "")
    enlace = f"https://github.com/{repo}/actions/runs/{run}" if repo and run else ""
    asunto, cuerpo_html, cuerpo_texto = contenido(tipo, modo, salud, panel, enlace, os.environ.get("PANEL_ORIGIN", ""))
    if enviar(config["destinatarios"], asunto, cuerpo_html, cuerpo_texto, sesion):
        return f"alerta «{tipo}» enviada a {len(config['destinatarios'])} destinatario(s)"
    return f"alerta «{tipo}» no enviada: falta RESEND_API_KEY/ALERTAS_REMITENTE o Resend la rechazó"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modo", choices=["diario", "manana", "horaria"], required=True)
    p.add_argument("--resultado", default="success")
    p.add_argument("--salida", default="salida")
    a = p.parse_args()
    try:
        print("Alertas:", correr(a.modo, a.resultado, a.salida))
    except Exception as e:  # noqa: BLE001 — una alerta nunca cambia el resultado de la ejecución
        print("Alertas: no se pudo procesar:", type(e).__name__)


if __name__ == "__main__":
    main()
