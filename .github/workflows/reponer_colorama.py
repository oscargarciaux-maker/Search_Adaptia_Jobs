"""Copia de `base` (main) a `rama` (rama de Dependabot) los bloques del lock cuya pieza lleva marcador de plataforma en
el .in y que pip-compile quitó. No cambia versiones: si la versión del .in no es la de main, falla y avisa."""
import re
import sys
from pathlib import Path

base, rama = Path(sys.argv[1]), Path(sys.argv[2])
INICIO = re.compile(r"^[A-Za-z0-9]")


def nombre(linea):
    return re.match(r"[A-Za-z0-9_.-]+", linea).group(0).lower().replace("_", "-")


def bloques(texto):
    """(encabezado, [bloque, ...]) donde cada bloque son las líneas de una pieza, desde su `nombre==versión` hasta la siguiente."""
    lineas = texto.splitlines(keepends=True)
    posiciones = [i for i, l in enumerate(lineas) if INICIO.match(l)]
    fin = posiciones[1:] + [len(lineas)]
    return lineas[:posiciones[0]], [lineas[a:b] for a, b in zip(posiciones, fin)]


fallos = []
for lock, entrada in (("requirements.txt", "requirements.in"), ("requirements-auditoria.txt", "requirements-auditoria.in")):
    pedidas = {}
    for linea in (rama / entrada).read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)\s*;\s*(.+?)\s*", linea.split("#")[0].strip())
        if m:
            pedidas[m.group(1).lower().replace("_", "-")] = m.group(2)
    encabezado, piezas = bloques((rama / lock).read_bytes().decode("utf-8"))
    presentes = {nombre(b[0]) for b in piezas}
    _, piezas_main = bloques((base / lock).read_bytes().decode("utf-8"))
    for pieza, version in pedidas.items():
        if pieza in presentes:
            continue
        origen = next((b for b in piezas_main if nombre(b[0]) == pieza and b[0].startswith(f"{pieza}=={version} ")), None)
        if origen is None:
            fallos.append(f"{lock}: falta {pieza}=={version} y main no tiene ese bloque; hay que añadirlo a mano")
            continue
        sitio = next((i for i, b in enumerate(piezas) if nombre(b[0]) > pieza), len(piezas))
        piezas.insert(sitio, origen)
        print(f"{lock}: repuesto {pieza}=={version}")
    (rama / lock).write_bytes("".join(encabezado + [l for b in piezas for l in b]).encode("utf-8"))
if fallos:
    sys.exit("\n".join(fallos))
