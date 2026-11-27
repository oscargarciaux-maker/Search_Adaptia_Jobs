"""Hook PreToolUse (PR 1.5): no leer ni escribir archivos de secretos (.env, claves, certificados privados).
Recibe el evento por stdin; con código 2 Claude Code bloquea la acción y muestra el motivo.
Lee el evento como UTF-8 (no con la codificación del sistema), revisa las rutas de Windows igual que las de Linux
(«\\» se trata como «/») y, si el evento no se entiende, sale con 2: falla cerrado.
Vigila Read, Edit, Write, MultiEdit y NotebookEdit (rutas), Bash y PowerShell (`command`) y Grep y Glob (`path`, más
los patrones de archivos `glob` y, en Glob, `pattern`). El `pattern` de Grep es el texto que se busca, no una ruta, y
no se revisa. Se lanza con `lanzar_python.sh`, que elige un Python de verdad."""
import fnmatch
import json
import re
import sys

PROHIBIDOS = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|.*secret.*\.json|credentials.*)$", re.I)
PERMITIDOS = re.compile(r"(^|/)\.env\.(example|ejemplo|plantilla)$|supabase/certificados/.*\.crt$", re.I)


def bloquear(motivo):
    print(motivo, file=sys.stderr)
    sys.exit(2)


def leer_evento(crudo):
    """Devuelve (rutas, patrones): rutas que la acción abre o nombra y patrones de archivos (Grep `glob`, Glob
    `pattern`)."""
    evento = json.loads(crudo.decode("utf-8", errors="replace"))
    datos = evento.get("tool_input") or {}
    rutas = [datos.get("file_path") or "", datos.get("path") or "", datos.get("notebook_path") or ""]
    comando = datos.get("command") or ""
    patrones = [datos.get("glob") or ""]
    if evento.get("tool_name") == "Glob":  # en Grep, `pattern` es el texto que se busca, no un nombre de archivo
        patrones.append(datos.get("pattern") or "")
    if not all(isinstance(x, str) for x in [*rutas, comando, *patrones]):  # forma inesperada: main() lo bloquea
        raise TypeError("campos que no son texto")
    rutas += re.findall(r"[\w./\\-]*\.env(?:\.[\w-]+)?\b", comando, re.I)  # Windows abre «.ENV» igual que «.env»
    return [_como_abre_windows(r) for r in rutas if r], [p for p in patrones if p]


# Nombres de muestra: un patrón que encaje con algún secreto y con ningún archivo corriente apunta a secretos.
SECRETOS_DE_MUESTRA = (".env", ".env.local", "a.pem", "a.key", "id_rsa", "credentials", "credentials.json",
                       "a_secret.json")
CORRIENTES_DE_MUESTRA = ("config.json", "notas.txt", "app.py", "readme.md", "index.ts", "datos.yaml", ".gitignore")


def patron_alcanza_secretos(patron):
    """True si el último tramo del patrón («**/.e*», «*.pe?», «.en[v]», «*.{ts,pem}») encaja con un nombre de secreto
    y con ningún archivo corriente. Los patrones amplios («*», «**/*.json», «.*») no se bloquean: Glob y Grep con
    ellos recorren todo el proyecto, no apuntan a un secreto (Glob solo lista nombres)."""
    llaves = re.search(r"\{([^{}]*)\}", patron)
    if llaves:  # fnmatch no entiende «{a,b}»: se prueba cada opción
        return any(patron_alcanza_secretos(patron[:llaves.start()] + opcion + patron[llaves.end():])
                   for opcion in llaves.group(1).split(","))
    tramo = _como_abre_windows(patron).rsplit("/", 1)[-1].lower()
    secreto = any(fnmatch.fnmatchcase(nombre, tramo) for nombre in SECRETOS_DE_MUESTRA)
    return secreto and not any(fnmatch.fnmatchcase(nombre, tramo) for nombre in CORRIENTES_DE_MUESTRA)


def _como_abre_windows(ruta):
    """Barras de Windows a «/», sin flujo NTFS («.env::$DATA») ni espacios o puntos finales («.env. »), que Windows
    ignora al abrir el archivo."""
    ruta = re.sub(r":[^/]*$", "", ruta.replace("\\", "/"))
    return ruta.rstrip(" .") or ruta


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        rutas, patrones = leer_evento(sys.stdin.buffer.read())
        prohibidas = [r for r in rutas if PROHIBIDOS.search(r) and not PERMITIDOS.search(r)]
        prohibidas += [p for p in patrones if patron_alcanza_secretos(p)]
    except Exception as error:  # cualquier fallo al leer el evento bloquea
        bloquear(f"Bloqueado: el control de secretos no pudo leer la acción ({type(error).__name__}). "
                 "Por seguridad no se deja pasar; revisa .claude/hooks/bloquear_secretos.py.")
    if prohibidas:
        bloquear(f"Bloqueado: «{prohibidas[0]}» puede alcanzar archivos de secretos. Las claves viven en los secretos "
                 "de GitHub y del alojamiento, nunca en el repositorio ni en la conversación.")


if __name__ == "__main__":
    main()
