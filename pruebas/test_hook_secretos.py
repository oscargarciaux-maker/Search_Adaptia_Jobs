"""El hook que impide tocar archivos de secretos funciona igual en Windows y falla cerrado (27 nov).

Antes leía el evento con la codificación del sistema: en Windows (cp1252) un texto con «Á» o «Í» lo hacía caer con un
error que Claude Code no trata como bloqueo, y la acción pasaba sin control. Ahora lee UTF-8 y, si algo no se entiende,
bloquea (código 2). Los secretos de estas pruebas son nombres de archivo inventados.

También vigila PowerShell, Grep y Glob, y se lanza con `lanzar_python.sh`, que elige un Python de verdad: en Windows
«python3» suele ser el acceso directo de la Microsoft Store, que sale con 9009 y dejaba pasar todo."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "bloquear_secretos.py"


def _correr(crudo):
    return subprocess.run([sys.executable, str(HOOK)], input=crudo, capture_output=True, timeout=30)


def _evento(herramienta=None, **datos):
    herramienta = herramienta or ("Bash" if "command" in datos else "Read")
    return json.dumps({"tool_name": herramienta, "tool_input": datos}, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("datos", [
    {"command": "echo «ÁREA ÍNDICE» y acentos: canción, añoranza"},
    {"file_path": "docs/GUÍA_ÁREA.md"},
    {"file_path": "datos/.env.example"},
])
def test_deja_pasar_texto_con_tildes_sin_secretos(datos):
    resultado = _correr(_evento(**datos))
    assert resultado.returncode == 0, resultado.stderr.decode("utf-8")


@pytest.mark.parametrize("datos", [
    {"file_path": "config/.env"},
    {"file_path": r"C:\Users\ejemplo\proyecto\.env.produccion"},
    {"file_path": r"C:\p\.env::$DATA"}, {"file_path": "C:\\p\\.env "}, {"file_path": "C:\\p\\.env."},
    {"file_path": "llaves/servidor_falso.pem"},
    {"command": "cat .env.local  # Ánimo, Índice"},
    {"path": "credentials_ejemplo_falso.json"},
])
def test_bloquea_secretos_aunque_haya_tildes_o_rutas_de_windows(datos):
    resultado = _correr(_evento(**datos))
    assert resultado.returncode == 2
    assert "Bloqueado" in resultado.stderr.decode("utf-8")


@pytest.mark.parametrize("crudo", [b"esto no es json", b"", b'{"tool_input": {"file_path": 5}}', b"[1, 2]"])
def test_si_no_entiende_el_evento_bloquea(crudo):
    resultado = _correr(crudo)
    assert resultado.returncode == 2
    assert "no pudo leer" in resultado.stderr.decode("utf-8")


def test_bytes_que_no_son_utf8_no_lo_tumban():
    crudo = _evento(command="echo ÁÍ").replace("ÁÍ".encode("utf-8"), b"\xc1\xcd")  # cp1252 pegado a mano
    assert _correr(crudo).returncode == 0


# --- Herramientas nuevas en el matcher (27 nov): PowerShell, Grep y Glob ---

@pytest.mark.parametrize("herramienta,datos", [
    ("PowerShell", {"command": "Get-Content .env"}),
    ("PowerShell", {"command": "Get-Content .ENV"}),
    ("PowerShell", {"command": r"Get-Content C:\proyecto\.env.local"}),
    ("Grep", {"pattern": "CLAVE", "path": ".env"}),
    ("Grep", {"pattern": "CLAVE", "path": "config", "glob": ".env*"}),
    ("Grep", {"pattern": "x", "glob": "*.{ts,pem}"}),
    # Con comodines dentro del nombre (Thermos): un glob que coincide pasa por delante del .gitignore de ripgrep
    ("Grep", {"pattern": "CLAVE", "glob": "?env"}),
    ("Grep", {"pattern": "CLAVE", "glob": "*env*"}),
    ("Glob", {"pattern": "**/.env"}),
    ("Glob", {"pattern": "**/.env.*"}),
    ("Glob", {"pattern": "**/.e*"}),
    ("Glob", {"pattern": ".en[v]"}),
    ("Glob", {"pattern": "*.pe?"}),
    ("Glob", {"pattern": "llaves/*.key"}),
])
def test_bloquea_powershell_grep_y_glob_sobre_secretos(herramienta, datos):
    resultado = _correr(_evento(herramienta, **datos))
    assert resultado.returncode == 2, (herramienta, datos)
    assert "Bloqueado" in resultado.stderr.decode("utf-8")


@pytest.mark.parametrize("herramienta,datos", [
    ("Read", {"file_path": "buscador/bodega.py"}),
    ("PowerShell", {"command": "Get-ChildItem $env:TEMP"}),
    ("Grep", {"pattern": r"\.env", "path": "docs"}),  # buscar el texto «.env» en documentos no abre el archivo
    ("Grep", {"pattern": "def ", "glob": "*.py"}),
    ("Glob", {"pattern": "**/*.py"}),
    ("Glob", {"pattern": "**/*.json"}),  # amplio: también encaja con archivos corrientes
    ("Glob", {"pattern": "**/*"}),
    ("Glob", {"pattern": "**/.env.example"}),
    ("Glob", {"pattern": "**/.env.*.example"}),
])
def test_deja_pasar_busquedas_y_lecturas_normales(herramienta, datos):
    resultado = _correr(_evento(herramienta, **datos))
    assert resultado.returncode == 0, resultado.stderr.decode("utf-8")


def test_settings_vigila_las_herramientas_y_usa_el_lanzador():
    ajustes = json.loads((HOOK.parent.parent / "settings.json").read_text(encoding="utf-8"))
    (entrada,) = [e for e in ajustes["hooks"]["PreToolUse"] if "bloquear_secretos.py" in e["hooks"][0]["command"]]
    vigiladas = set(entrada["matcher"].split("|"))
    assert {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell", "Grep", "Glob"} <= vigiladas
    comando = entrada["hooks"][0]["command"]
    assert comando.startswith("bash ") and "lanzar_python.sh" in comando and "python3" not in comando


# --- El lanzador elige un Python de verdad y falla cerrado (27 nov) ---

LANZADOR = HOOK.parent / "lanzar_python.sh"


def _bash():
    """Git Bash en Windows (no el bash de WSL, que vive en System32 o WindowsApps) o el bash del sistema en Linux."""
    for ruta in [shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"]:
        if ruta and Path(ruta).exists() and not any(x in ruta.lower() for x in ("system32", "windowsapps")):
            return ruta
    pytest.skip("no hay bash para probar el lanzador")


def _ejecutable(carpeta, nombre, cuerpo):
    archivo = carpeta / nombre
    archivo.write_text("#!/bin/sh\n" + cuerpo + "\n", encoding="utf-8", newline="\n")
    archivo.chmod(0o755)


PYTHON_REAL = f'exec "{Path(sys.executable).as_posix()}" "$@"'


def _lanzar(carpeta, crudo, *argumentos):
    entorno = {**os.environ, "PATH": str(carpeta)}  # solo los ejecutables falsos de la prueba
    argumentos = argumentos or (str(HOOK),)
    return subprocess.run([_bash(), str(LANZADOR), *argumentos], input=crudo, capture_output=True, timeout=60,
                          env=entorno)


@pytest.fixture
def python3_de_la_store(tmp_path):
    """Carpeta de PATH con un «python3» que imita el acceso directo de la Microsoft Store: sale con 9009."""
    carpeta = tmp_path / "bin"
    carpeta.mkdir()
    _ejecutable(carpeta, "python3", "echo 'no se encontró Python' >&2\nexit 9009")
    return carpeta


@pytest.mark.parametrize("nombre,cuerpo", [
    ("python", PYTHON_REAL),
    ("py", f'[ "$1" = "-3" ] || exit 9\nshift\n{PYTHON_REAL}'),  # el lanzador de Windows, con «-3»
])
def test_lanzador_salta_el_python3_falso_y_usa_uno_real(python3_de_la_store, nombre, cuerpo):
    _ejecutable(python3_de_la_store, nombre, cuerpo)
    secreto = _lanzar(python3_de_la_store, _evento(file_path="config/.env"))
    assert secreto.returncode == 2
    assert "«config/.env» puede alcanzar archivos de secretos" in secreto.stderr.decode("utf-8")  # llegó intacto
    normal = _lanzar(python3_de_la_store, _evento(file_path="buscador/bodega.py"))
    assert normal.returncode == 0, normal.stderr.decode("utf-8")


def test_lanzador_descarta_un_python_que_no_es_3(python3_de_la_store):
    _ejecutable(python3_de_la_store, "python", "printf 'python-real-2'")
    resultado = _lanzar(python3_de_la_store, _evento(file_path="buscador/bodega.py"))
    assert resultado.returncode == 2
    assert "no se encontró un Python 3" in resultado.stderr.decode("utf-8")


def test_lanzador_sin_python_sale_con_2(python3_de_la_store):
    resultado = _lanzar(python3_de_la_store, _evento(file_path="buscador/bodega.py"))
    assert resultado.returncode == 2
    assert "no se encontró un Python 3" in resultado.stderr.decode("utf-8")


def test_lanzador_sin_script_sale_con_2(python3_de_la_store):
    resultado = subprocess.run([_bash(), str(LANZADOR)], input=b"{}", capture_output=True, timeout=60)
    assert resultado.returncode == 2
    assert "necesita la ruta del script" in resultado.stderr.decode("utf-8")


def test_lanzador_convierte_un_fallo_del_hook_en_bloqueo(python3_de_la_store, tmp_path):
    _ejecutable(python3_de_la_store, "python", PYTHON_REAL)
    roto = tmp_path / "roto.py"
    roto.write_text("raise SystemExit(1)\n", encoding="utf-8")
    resultado = _lanzar(python3_de_la_store, _evento(file_path="buscador/bodega.py"), str(roto))
    assert resultado.returncode == 2
    assert "terminó con un error (1)" in resultado.stderr.decode("utf-8")
