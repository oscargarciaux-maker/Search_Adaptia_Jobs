"""Hook PreToolUse (PR 1.5): no leer ni escribir archivos de secretos (.env, claves, certificados privados).
Recibe el evento por stdin; con código 2 Claude Code bloquea la acción y muestra el motivo.

Portabilidad (27 nov): el evento se lee como bytes UTF-8, no con la codificación del sistema (cp1252 en Windows, que
fallaba con «Á» o «Í» y dejaba pasar todo sin avisar). Si el evento no se puede entender, bloquea: falla cerrado.
Las rutas de Windows (con «\\») se revisan igual que las de Linux."""
import json
import re
import sys

PROHIBIDOS = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|.*secret.*\.json|credentials.*)$", re.I)
PERMITIDOS = re.compile(r"(^|/)\.env\.(example|ejemplo|plantilla)$|supabase/certificados/.*\.crt$", re.I)


def bloquear(motivo):
    print(motivo, file=sys.stderr)
    sys.exit(2)


def rutas_del_evento(crudo):
    evento = json.loads(crudo.decode("utf-8", errors="replace"))
    datos = evento.get("tool_input") or {}
    rutas = [datos.get("file_path") or "", datos.get("path") or "", datos.get("notebook_path") or ""]
    comando = datos.get("command") or ""
    if not all(isinstance(x, str) for x in [*rutas, comando]):
        raise TypeError("campos que no son texto")
    rutas += re.findall(r"[\w./\\-]*\.env(?:\.[\w-]+)?\b", comando)
    return [r.replace("\\", "/") for r in rutas if r]


def main():
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        rutas = rutas_del_evento(sys.stdin.buffer.read())
    except Exception as error:  # cualquier fallo al leer el evento bloquea
        bloquear(f"Bloqueado: el control de secretos no pudo leer la acción ({type(error).__name__}). "
                 "Por seguridad no se deja pasar; revisa .claude/hooks/bloquear_secretos.py.")
    for ruta in rutas:
        if PROHIBIDOS.search(ruta) and not PERMITIDOS.search(ruta):
            bloquear(f"Bloqueado: «{ruta}» puede contener secretos. Las claves viven en los secretos de GitHub "
                     "y del alojamiento, nunca en el repositorio ni en la conversación.")


if __name__ == "__main__":
    main()
