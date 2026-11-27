"""Portabilidad a Windows (27 nov): todo archivo de texto se lee y se escribe en UTF-8 dicho en el código.

Sin `encoding`, Python usa la codificación del sistema: UTF-8 en Linux (CI), pero cp1252 en Windows, y ahí los SQL y
YAML con tildes fallan. Esta prueba revisa el código fuente (sin ejecutarlo) y avisa de cada lectura o escritura de
texto que no diga su codificación. Los archivos binarios (modo con «b») no la necesitan."""
import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS = ["buscador", "panel", "pruebas", ".claude/hooks"]

# Funciones que abren archivos: (posición del modo, modo si no se dice). Los temporales son binarios por defecto.
ABREN = {"open": (1, "r"), "fdopen": (1, "r"), "NamedTemporaryFile": (0, "w+b"), "TemporaryFile": (0, "w+b"),
         "SpooledTemporaryFile": (1, "w+b")}
MODULOS_CON_RUTA = {"io", "builtins", "gzip", "bz2", "lzma", "codecs"}  # x.open(ruta, modo), como open()
SUBPROCESOS = {"run", "check_output", "Popen", "call", "check_call"}


def _nombres(func):
    """(función, módulo o None): `os.open` → ("open", "os"); `Path(r).open` → ("open", None); `open` → ("open", "")."""
    if isinstance(func, ast.Name):
        return func.id, ""
    if isinstance(func, ast.Attribute):
        return func.attr, func.value.id if isinstance(func.value, ast.Name) else None
    return None, None


def _falta_codificacion(llamada):
    """Devuelve la operación si la llamada abre texto sin `encoding`; si no, None."""
    nombre, modulo = _nombres(llamada.func)
    claves = {k.arg: k.value for k in llamada.keywords}
    if "encoding" in claves or None in claves:  # None: **kwargs, no se puede saber
        return None
    n = len(llamada.args)
    if nombre == "read_text":
        return None if n >= 1 else nombre
    if nombre == "write_text":
        return None if n >= 2 else nombre
    if nombre in ABREN:
        if nombre == "open" and modulo == "os":
            return None  # os.open es de bajo nivel: devuelve un número, no un archivo de texto
        posicion, por_defecto = ABREN[nombre]
        if nombre == "open" and modulo != "" and modulo not in MODULOS_CON_RUTA:
            posicion = 0  # Path.open(modo)
        if modulo in ("gzip", "bz2", "lzma"):
            por_defecto = "rb"  # los comprimidos son binarios si no se pide «t»
        modo = claves.get("mode", llamada.args[posicion] if n > posicion else None)
        valor = por_defecto if modo is None else modo.value if isinstance(modo, ast.Constant) else None
        if not isinstance(valor, str) or "b" in valor:
            return None  # modo binario, o calculado en ejecución (no se adivina)
        return nombre
    if nombre in SUBPROCESOS:
        texto = claves.get("text", claves.get("universal_newlines"))
        if isinstance(texto, ast.Constant) and texto.value is True:
            return f"{nombre}(text=True)"
    return None


def _hallazgos():
    for carpeta in CARPETAS:
        for archivo in sorted((RAIZ / carpeta).rglob("*.py")):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Call) and (operacion := _falta_codificacion(nodo)):
                    yield archivo.relative_to(RAIZ).as_posix(), nodo.lineno, operacion


def test_todo_texto_se_abre_con_codificacion_utf8():
    faltan = [f"{ruta}:{linea} {op}" for ruta, linea, op in _hallazgos()]
    assert not faltan, "añade encoding=\"utf-8\" en:\n" + "\n".join(faltan)


@pytest.mark.parametrize("codigo, falla", [
    ("p.read_text()", True), ("p.read_text(encoding='utf-8')", False), ("p.read_text('utf-8')", False),
    ("p.write_text(x)", True), ("p.write_text(x, encoding='utf-8')", False),
    ("open(r)", True), ("open(r, 'a')", True), ("open(r, 'rb')", False), ("open(r, 'w', encoding='utf-8')", False),
    ("p.open()", True), ("p.open('rb')", False), ("Path(r).open('rb')", False), ("io.open(r, 'w')", True),
    ("os.fdopen(d, 'w')", True), ("os.fdopen(d, 'wb')", False), ("os.open(r, 1)", False),
    ("tempfile.NamedTemporaryFile()", False), ("tempfile.NamedTemporaryFile('w')", True),
    ("gzip.open(r, 'wt')", True), ("gzip.open(r, 'rb')", False), ("gzip.open(r)", False), ("codecs.open(r, 'w')", True), ("subprocess.run(c, text=True)", True),
    ("subprocess.run(c, text=True, encoding='utf-8')", False), ("subprocess.run(c)", False),
])
def test_el_revisor_distingue_texto_de_binario(codigo, falla):
    assert bool(_falta_codificacion(ast.parse(codigo).body[0].value)) is falla
