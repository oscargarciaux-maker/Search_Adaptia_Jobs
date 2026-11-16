"""PR 1.5 (16 nov): nada externo cambia sin que lo decidamos. Cada dependencia directa está fijada en `requirements.in` y
`requirements.txt` (pip-compile) la instala con su huella (sha256), igual que todas las piezas que trae por dentro."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COMANDO = "pip-compile --allow-unsafe --generate-hashes --strip-extras requirements.in (con Python 3.12)"


def _directas(archivo="requirements.in"):
    salida = {}
    for linea in (RAIZ / archivo).read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if linea:
            m = re.fullmatch(r"([A-Za-z0-9_.-]+)(\[[^\]]+\])?==([^\s;]+)", linea)
            assert m, f"«{linea}» debe fijar una versión exacta con =="
            salida[m.group(1).lower().replace("_", "-")] = m.group(3)
    return salida


def _bloqueadas(archivo="requirements.txt"):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    bloques = re.split(r"\n(?=[A-Za-z0-9])", texto)
    salida = {}
    for b in bloques:
        m = re.match(r"([A-Za-z0-9_.-]+)(\[[^\]]+\])?==(\S+)", b)
        if m:
            salida[m.group(1).lower().replace("_", "-")] = (m.group(3), "--hash=sha256:" in b)
    return salida


import pytest


@pytest.mark.parametrize("base", ["requirements", "requirements-auditoria"])
def test_lock_coincide_con_requirements_y_todo_lleva_huella(base):
    directas, bloqueadas = _directas(base + ".in"), _bloqueadas(base + ".txt")
    for nombre, version in directas.items():
        assert nombre in bloqueadas, f"{nombre} falta en el .txt compilado; regenera con: {COMANDO}"
        assert bloqueadas[nombre][0] == version, f"{nombre} difiere del .txt compilado; regenera con: {COMANDO}"
    assert all(con_huella for _, con_huella in bloqueadas.values()), "toda pieza del lock lleva su sha256"


def test_flujos_y_docker_instalan_desde_el_lock_con_huellas():
    archivos = [*sorted((RAIZ / ".github" / "workflows").glob("*.yml")), RAIZ / "Dockerfile"]
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        for orden in re.findall(r"pip install[^\n]*", texto):
            if "-r " in orden:
                assert re.search(r"--require-hashes -r requirements(-auditoria)?\.txt", orden), f"{archivo.name}: {orden}"
