"""Hook PreToolUse (PR 1.5): no leer ni escribir archivos de secretos (.env, claves, certificados privados).
Recibe el evento por stdin; con código 2 Claude Code bloquea la acción y muestra el motivo.
Lee el evento como UTF-8 (no con la codificación del sistema), revisa las rutas de Windows igual que las de Linux
(«\\» se trata como «/») y, si el evento no se entiende, sale con 2: falla cerrado."""
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
    if not all(isinstance(x, str) for x in [*rutas, comando]):  # forma inesperada: main() lo bloquea
        raise TypeError("campos que no son texto")
    rutas += re.findall(r"[\w./\\-]*\.env(?:\.[\w-]+)?\b", comando)
    return [_como_abre_windows(r) for r in rutas if r]


def _como_abre_windows(ruta):
    """Barras de Windows a «/», sin flujo NTFS («.env::$DATA») ni espacios o puntos finales («.env. »), que Windows
    ignora al abrir el archivo."""
    ruta = re.sub(r":[^/]*$", "", ruta.replace("\\", "/"))
    return ruta.rstrip(" .") or ruta


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
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
