#!/usr/bin/env bash
# Lanza un hook de Python con un Python de verdad, en Windows (Git Bash) y en Linux (27 nov).
# Uso: bash lanzar_python.sh <script.py>   (el evento del hook llega por stdin y pasa intacto al script)
#
# Por qué existe: en Windows «python3» suele ser el acceso directo de la Microsoft Store, que no ejecuta nada y sale
# con 9009. Claude Code toma cualquier código distinto de 0 o 2 como un error que NO bloquea, así que el control de
# secretos no protegía. Aquí se prueba cada candidato ANTES de usarlo (con stdin vacío, para no gastar el evento) y
# solo se ejecuta el primero que responde como Python 3.
# Falla cerrado: si no hay Python o el script termina con un código raro, sale con 2 (Claude Code bloquea).

script="${1:-}"
if [ -z "$script" ]; then
  echo "Bloqueado: lanzar_python.sh necesita la ruta del script del hook." >&2
  exit 2
fi
shift

es_python_real() {
  # Un Python 3 de verdad escribe exactamente esta marca; el acceso directo de la Store no escribe nada.
  [ "$("$@" -c 'import sys; sys.stdout.write("python-real-%d" % sys.version_info[0])' </dev/null 2>/dev/null)" \
    = "python-real-3" ]
}

for candidato in "python3" "python" "py -3"; do
  set -- $candidato  # «py -3» se separa en programa y opción
  command -v "$1" >/dev/null 2>&1 || continue
  if es_python_real "$@"; then
    "$@" -I "$script"  # -I: no carga módulos de la carpeta actual ni variables PYTHON*
    codigo=$?
    [ "$codigo" -eq 0 ] && exit 0
    [ "$codigo" -ne 2 ] && echo "Bloqueado: el hook $script terminó con un error ($codigo); por seguridad no se deja pasar." >&2
    exit 2
  fi
done

echo "Bloqueado: no se encontró un Python 3 que funcione (probé python3, python y py -3). Por seguridad no se deja" \
  "pasar la acción. Instala Python 3 o desactiva el alias «python3» de la Microsoft Store." >&2
exit 2
