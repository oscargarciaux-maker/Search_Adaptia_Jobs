#!/usr/bin/env bash
# Hook Stop (PR 1.5): si el turno cambió Python o datos, corre las pruebas rápidas antes de cerrar. Si fallan, Claude
# Code no da el turno por terminado y recibe el resumen para arreglarlo. Sin esos cambios no hace nada.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git status --porcelain -- '*.py' 'datos/*.yaml' | grep -q . || exit 0
registro=$(mktemp)
timeout 170 python -m pytest -q -x pruebas >"$registro" 2>&1
codigo=$?
if [ "$codigo" != "0" ]; then
  echo "Las pruebas rápidas fallan; arréglalas antes de terminar:" >&2
  tail -15 "$registro" >&2
  rm -f "$registro"
  exit 2
fi
rm -f "$registro"
exit 0
