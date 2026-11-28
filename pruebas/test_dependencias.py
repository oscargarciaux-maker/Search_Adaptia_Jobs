"""PR 1.5 (16 nov): nada externo cambia sin que lo decidamos. Cada dependencia directa está fijada en `requirements.in` y
`requirements.txt` (uv pip compile) la instala con su huella (sha256), igual que todas las piezas que trae por dentro."""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
COMANDO = "uv pip compile --universal --generate-hashes --python-version 3.12 -o {base}.txt {base}.in"
# P-13.2 (28 nov): el lock es universal (un solo lock para Linux y Windows), así que lo que solo usa Windows
# (colorama, `sys_platform == 'win32'`) queda en el .txt con su marcador y sus huellas aunque se compile en Linux.
# Dependabot (ecosistema `uv`) lee la cabecera del .txt y recompila con las mismas opciones, `--universal` incluida.
# Para regenerar en local: `pip install uv` (o `pipx run uv ...`) y el comando de arriba.


def _marcador(texto):
    """Marcador de plataforma sin espacios ni «;» (`; sys_platform == "win32"` → `sys_platform=="win32"`), o vacío."""
    return re.sub(r"\s+", "", (texto or "").strip().lstrip(";")).replace("'", '"')


def _directas(archivo="requirements.in"):
    salida = {}
    for linea in (RAIZ / archivo).read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if linea:
            m = re.fullmatch(r"([A-Za-z0-9_.-]+)(\[[^\]]+\])?==([^\s;]+)(\s*;.+)?", linea)
            assert m, f"«{linea}» debe fijar una versión exacta con =="
            salida[m.group(1).lower().replace("_", "-")] = (m.group(3), _marcador(m.group(4)))
    return salida


def _bloqueadas(archivo="requirements.txt"):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    bloques = re.split(r"\n(?=[A-Za-z0-9])", texto)
    salida = {}
    for b in bloques:
        m = re.match(r"([A-Za-z0-9_.-]+)(\[[^\]]+\])?==(\S+)([^\\\n]*)", b)
        if m:
            salida[m.group(1).lower().replace("_", "-")] = (m.group(3), _marcador(m.group(4)), "--hash=sha256:" in b)
    return salida


@pytest.mark.parametrize("base", ["requirements", "requirements-auditoria"])
def test_lock_coincide_con_requirements_y_todo_lleva_huella(base):
    directas, bloqueadas = _directas(base + ".in"), _bloqueadas(base + ".txt")
    for nombre, (version, marcador) in directas.items():
        assert nombre in bloqueadas, f"{nombre} falta en {base}.txt; regenera con: {COMANDO.format(base=base)}"
        assert bloqueadas[nombre][:2] == (version, marcador), \
            f"{nombre} difiere de {base}.txt (versión o marcador); regenera con: {COMANDO.format(base=base)}"
    assert all(con_huella for *_, con_huella in bloqueadas.values()), "toda pieza del lock lleva su sha256"


@pytest.mark.parametrize("base", ["requirements", "requirements-auditoria"])
def test_lock_universal_compilado_con_uv(base):
    """Un lock de pip-compile (o de uv sin `--universal`) pierde colorama al compilarse en Linux: la cabecera lo delata."""
    lineas = (RAIZ / (base + ".txt")).read_text(encoding="utf-8").splitlines()
    cabecera = next((l.strip("# ") for l in lineas[:5] if l.strip("# ").startswith("uv pip compile")), "")
    assert all(o in cabecera.split() for o in ("--universal", "--generate-hashes", "--python-version", "3.12")), \
        f"{base}.txt no es un lock universal de uv; regenera con: {COMANDO.format(base=base)}"


def test_colorama_queda_fijada_para_windows():
    """pytest, click y bandit piden colorama solo en Windows: el .in debe pedirla con su marcador (que el lock la
    conserve lo exige `test_lock_coincide_con_requirements_y_todo_lleva_huella`)."""
    for base in ("requirements", "requirements-auditoria"):
        assert _directas(base + ".in").get("colorama", ("", ""))[1] == 'sys_platform=="win32"', base


def test_flujos_y_docker_instalan_desde_el_lock_con_huellas():
    archivos = [*sorted((RAIZ / ".github" / "workflows").glob("*.yml")), RAIZ / "Dockerfile"]
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        for orden in re.findall(r"pip install[^\n]*", texto):
            if "-r " in orden:
                assert re.search(r"--require-hashes -r requirements(-auditoria)?\.txt", orden), f"{archivo.name}: {orden}"
