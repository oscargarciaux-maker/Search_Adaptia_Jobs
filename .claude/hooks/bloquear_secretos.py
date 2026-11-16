"""Hook PreToolUse (PR 1.5): no leer ni escribir archivos de secretos (.env, claves, certificados privados).
Recibe el evento por stdin; con código 2 Claude Code bloquea la acción y muestra el motivo."""
import json
import re
import sys

PROHIBIDOS = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|.*secret.*\.json|credentials.*)$", re.I)
PERMITIDOS = re.compile(r"(^|/)\.env\.(example|ejemplo|plantilla)$|supabase/certificados/.*\.crt$", re.I)

evento = json.load(sys.stdin)
datos = evento.get("tool_input") or {}
rutas = [datos.get("file_path") or "", datos.get("path") or "", datos.get("notebook_path") or ""]
comando = datos.get("command") or ""
rutas += re.findall(r"[\w./-]*\.env(?:\.[\w-]+)?\b", comando)
for ruta in filter(None, rutas):
    if PROHIBIDOS.search(ruta) and not PERMITIDOS.search(ruta):
        print(f"Bloqueado: «{ruta}» puede contener secretos. Las claves viven en los secretos de GitHub "
              "y del alojamiento, nunca en el repositorio ni en la conversación.", file=sys.stderr)
        sys.exit(2)
