"""El hook que impide tocar archivos de secretos funciona igual en Windows y falla cerrado (27 nov).

Antes leía el evento con la codificación del sistema: en Windows (cp1252) un texto con «Á» o «Í» lo hacía caer con un
error que Claude Code no trata como bloqueo, y la acción pasaba sin control. Ahora lee UTF-8 y, si algo no se entiende,
bloquea (código 2). Los secretos de estas pruebas son nombres de archivo inventados."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "bloquear_secretos.py"


def _correr(crudo):
    return subprocess.run([sys.executable, str(HOOK)], input=crudo, capture_output=True, timeout=30)


def _evento(**datos):
    return json.dumps({"tool_name": "Bash", "tool_input": datos}, ensure_ascii=False).encode("utf-8")


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
