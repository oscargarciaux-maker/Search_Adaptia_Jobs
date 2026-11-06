"""Autoridades del sistema + raíz pública oficial Supabase; siempre verificar CA y nombre del servidor."""
from contextlib import contextmanager
from pathlib import Path
import ssl
import tempfile

import certifi
from cryptography import x509
from cryptography.hazmat.primitives import hashes

CA = Path(__file__).resolve().parent.parent / "supabase/certificados/prod-ca-2021.crt"
HUELLA = "807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa"


@contextmanager
def autoridades():
    publico = CA.read_bytes()
    certificado = x509.load_pem_x509_certificate(publico)
    if certificado.fingerprint(hashes.SHA256()).hex() != HUELLA or not certificado.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise RuntimeError("[DB_TLS_CA] La raíz pública Supabase no coincide con la versión aprobada; revisar el archivo del proyecto.")
    sistema = ssl.get_default_verify_paths().cafile
    raiz = Path(sistema) if sistema and Path(sistema).is_file() else Path(certifi.where())
    with tempfile.TemporaryDirectory(prefix="adaptia-ca-") as carpeta:
        ruta = Path(carpeta) / "autoridades.pem"
        ruta.write_bytes(raiz.read_bytes().rstrip() + b"\n" + publico)
        yield str(ruta)
