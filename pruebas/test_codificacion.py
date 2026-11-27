"""Portabilidad a Windows (27 nov): todo archivo de texto se lee y se escribe en UTF-8 dicho en el código.

Sin `encoding`, Python usa la codificación del sistema: UTF-8 en Linux (CI), pero cp1252 en Windows, y ahí los SQL y
YAML con tildes fallan. Esta prueba revisa el código fuente (sin ejecutarlo) y avisa de cada lectura o escritura de
texto que no diga su codificación. Los archivos binarios (modo con «b») no la necesitan."""
import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS = ["buscador", "panel", "pruebas"]


def _texto(nodo):
    return nodo.value if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else None


def _falta_codificacion(llamada):
    """Devuelve la operación si la llamada abre texto sin `encoding`; si no, None."""
    f = llamada.func
    nombre = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
    claves = {k.arg: k.value for k in llamada.keywords}
    if "encoding" in claves or None in claves:  # None: **kwargs, no se puede saber
        return None
    n = len(llamada.args)
    if nombre == "read_text":
        return None if n >= 1 else nombre
    if nombre == "write_text":
        return None if n >= 2 else nombre
    if nombre in ("open", "fdopen", "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"):
        modulo = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else None
        if nombre == "open" and modulo == "os":
            return None  # os.open es de bajo nivel: devuelve un número, no un archivo de texto
        if nombre in ("open", "fdopen"):
            # open(ruta, modo) e io.open/os.fdopen llevan el modo segundo; Path.open(modo) lo lleva primero.
            metodo = nombre == "open" and isinstance(f, ast.Attribute) and modulo not in ("io", "builtins")
            posicion, por_defecto = (0 if metodo else 1), "r"
        else:
            posicion, por_defecto = 0, "w+b"  # los temporales son binarios si no se dice otra cosa
        modo = claves.get("mode", llamada.args[posicion] if n > posicion else None)
        valor = por_defecto if modo is None else _texto(modo)
        if valor is None or "b" in valor:
            return None  # modo binario, o calculado en ejecución (no se adivina)
        return nombre
    if nombre in ("run", "check_output", "Popen", "call", "check_call"):
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
                    yield f"{archivo.relative_to(RAIZ).as_posix()}:{nodo.lineno} {operacion}"


# Archivos que hoy cambia el PR abierto #154: se corrigen en un PR aparte cuando se fusione, y entonces se quitan de aquí.
PENDIENTES = {"pruebas/test_calidad_arranque.py", "pruebas/test_verificar_enlaces.py", "panel/ejecutor.py"}


def test_todo_texto_se_abre_con_codificacion_utf8():
    faltan = [h for h in _hallazgos() if h.split(":")[0] not in PENDIENTES]
    assert not faltan, "añade encoding=\"utf-8\" en:\n" + "\n".join(faltan)


@pytest.mark.parametrize("codigo, falla", [
    ("p.read_text()", True), ("p.read_text(encoding='utf-8')", False), ("p.read_text('utf-8')", False),
    ("p.write_text(x)", True), ("p.write_text(x, encoding='utf-8')", False),
    ("open(r)", True), ("open(r, 'a')", True), ("open(r, 'rb')", False), ("open(r, 'w', encoding='utf-8')", False),
    ("p.open()", True), ("p.open('rb')", False), ("Path(r).open('rb')", False), ("io.open(r, 'w')", True),
    ("os.fdopen(d, 'w')", True), ("os.fdopen(d, 'wb')", False), ("os.open(r, 1)", False),
    ("tempfile.NamedTemporaryFile()", False), ("tempfile.NamedTemporaryFile('w')", True), ("subprocess.run(c, text=True)", True),
    ("subprocess.run(c, text=True, encoding='utf-8')", False), ("subprocess.run(c)", False),
])
def test_el_revisor_distingue_texto_de_binario(codigo, falla):
    assert bool(_falta_codificacion(ast.parse(codigo).body[0].value)) is falla
