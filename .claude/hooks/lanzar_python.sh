#!/usr/bin/env bash
# Lanza un hook de Python con un Python de verdad, en Windows (Git Bash) y en Linux (27 nov).
# Uso: bash lanzar_python.sh <script.py>   (solo ese argumento; el evento del hook llega por stdin y pasa intacto)
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

probar() {  # probar <programa> [opciones]: si es un Python 3 de verdad, corre el script con él y termina
  command -v "$1" >/dev/null 2>&1 || return 0
  # Un Python 3 de verdad escribe exactamente esta marca; el acceso directo de la Store no escribe nada.
  local marca
  marca=$("$@" -c 'import sys; sys.stdout.write("python-real-%d" % sys.version_info[0])' </dev/null 2>/dev/null)
  [ "$marca" = "python-real-3" ] || return 0
  "$@" -I "$script"  # -I: no carga módulos de la carpeta actual ni variables PYTHON*
  local codigo=$?
  [ "$codigo" -eq 0 ] && exit 0
  [ "$codigo" -ne 2 ] && echo "Bloqueado: el hook $script terminó con un error ($codigo); por seguridad no se deja pasar." >&2
  exit 2
}

probar python3
probar python
probar py -3

echo "Bloqueado: no se encontró un Python 3 que funcione (probé python3, python y py -3). Por seguridad no se deja" \
  "pasar la acción. Instala Python 3 o desactiva el alias «python3» de la Microsoft Store." >&2
exit 2
