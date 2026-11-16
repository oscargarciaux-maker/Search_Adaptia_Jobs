"""Rastro de los errores que se toleran a propósito (PR 1.5, 16 nov): la búsqueda sigue, pero el error deja una línea
en el registro de GitHub Actions o del panel. Así ningún fallo se pierde sin dejar huella. No guarda datos de clientes:
solo el lugar y el tipo de error, con el mensaje recortado."""
import sys


def aviso(donde, error):
    mensaje = " ".join(str(error).split())[:300]
    print(f"[aviso] {donde}: {type(error).__name__}: {mensaje}", file=sys.stderr, flush=True)
