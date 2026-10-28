"""Pruebas del esqueleto: la configuración se puede leer y el repositorio no trae claves ni correos.

El repositorio se le entrega a otra persona y puede ser público: ninguna clave, token ni correo debe quedar en un
archivo (las claves van en los secretos de GitHub y de Cloudflare).
"""
import re
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent

# Formatos de claves de los servicios del proyecto (GitHub, Apify, Anthropic, AWS) y bloques de llave privada
CLAVES = re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|apify_api_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}"
                    r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
CORREO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]{2,}")
# Direcciones técnicas que no son de una persona (p. ej. el usuario de GitHub Actions al publicar)
CORREOS_PERMITIDOS = {"41898282+github-actions[bot]@users.noreply.github.com"}


def archivos_del_repositorio():
    salida = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=RAIZ,
                            capture_output=True, text=True, check=True).stdout
    return [RAIZ / linea for linea in salida.splitlines() if linea and (RAIZ / linea).is_file()]


def test_config_se_lee_y_trae_lo_basico():
    config = yaml.safe_load((RAIZ / "datos" / "config.yaml").read_text(encoding="utf-8"))
    assert config["dias_maximos"] == 30
    assert "CO" in config["paises_activos"] and "VE" in config["paises_activos"]
    assert all(re.fullmatch(r"[A-Z]{2}", p) for p in config["paises_activos"])
    assert set(config["apify"]) >= {"actor_linkedin", "actor_linkedin_respaldo", "tope_por_corrida_usd"}


def test_ningun_archivo_trae_claves_ni_correos():
    problemas = []
    for ruta in archivos_del_repositorio():
        try:
            texto = ruta.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # archivos binarios (imágenes, datos comprimidos)
        if CLAVES.search(texto):
            problemas.append(f"{ruta.relative_to(RAIZ)}: parece una clave")
        for correo in set(CORREO.findall(texto)) - CORREOS_PERMITIDOS:
            problemas.append(f"{ruta.relative_to(RAIZ)}: correo {correo}")
    assert not problemas, "\n".join(problemas)


def test_el_detector_reconoce_claves_y_correos():
    assert CLAVES.search("token = ghp_" + "a" * 36)
    assert CLAVES.search("APIFY_TOKEN=apify_api_" + "B" * 30)
    assert CORREO.search("escribe a alguien" + "@" + "empresa.com")  # partido para no dispararse a sí mismo
    assert not CLAVES.search("APIFY_TOKEN va en los secretos de GitHub")
