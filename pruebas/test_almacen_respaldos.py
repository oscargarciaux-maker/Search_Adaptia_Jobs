"""Respaldos en el bucket privado de Supabase Storage, con Storage simulado y datos ficticios (sin red)."""
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import pytest

from buscador import almacen_respaldos as ar, respaldo

LLAVE = "A" * 43  # 32 bytes en base64 URL segura (ficticia)
RAIZ = Path(__file__).resolve().parents[1]


class StorageFalso:
    """Imita las rutas de la API de Storage que usa el módulo."""

    def __init__(self, publico=None):
        self.bucket = None if publico is None else {"id": "respaldos", "public": publico, "limite": 50_000_000}
        self.objetos = {}
        self.llamadas = []
        self.fallar_subida = False
        self.corromper = set()

    def request(self, metodo, url, headers=None, json=None, data=None, timeout=None):
        ruta = url.split("/storage/v1", 1)[1]
        self.llamadas.append((metodo, ruta, dict(headers or {})))
        if ruta == "/bucket/respaldos" and metodo == "GET":
            return self._r(200, self.bucket) if self.bucket else self._r(400, {"error": "Bucket not found"})
        if ruta == "/bucket" and metodo == "POST":
            self.bucket = {"id": json["id"], "public": json["public"], "limite": json["file_size_limit"]}
            return self._r(200, {"name": json["id"]})
        if ruta == "/object/list/respaldos":
            return self._r(200, self._listar(json["prefix"])[json["offset"]:json["offset"] + json["limit"]])
        if ruta.startswith("/object/respaldos/") and metodo == "POST":
            if self.fallar_subida:
                return self._r(500, {})
            nombre = ruta[len("/object/respaldos/"):]
            if nombre in self.objetos:
                return self._r(400, {"error": "Duplicate"})
            if len(data) > self.bucket["limite"]:
                return self._r(413, {})
            self.objetos[nombre] = bytes(data)
            return self._r(200, {"Key": nombre})
        if ruta.startswith("/object/authenticated/respaldos/"):
            nombre = ruta[len("/object/authenticated/respaldos/"):]
            if nombre not in self.objetos:
                return self._r(400, {"error": "not_found"})
            datos = self.objetos[nombre]
            return self._r(200, contenido=datos + b"x" if nombre in self.corromper else datos)
        if ruta == "/object/respaldos" and metodo == "DELETE":
            for n in json["prefixes"]:
                self.objetos.pop(n, None)
            return self._r(200, [])
        return self._r(404, {})

    def _listar(self, prefijo):
        vistos, salida = set(), []
        for nombre in sorted(self.objetos):
            if not nombre.startswith(prefijo):
                continue
            resto = nombre[len(prefijo):]
            if "/" in resto:
                carpeta = resto.split("/", 1)[0]
                if carpeta not in vistos:
                    vistos.add(carpeta)
                    salida.append({"name": carpeta, "id": None, "metadata": None})
            else:
                salida.append({"name": resto, "id": "x", "metadata": {"size": len(self.objetos[nombre])}})
        return salida

    @staticmethod
    def _r(estado, datos=None, contenido=b""):
        return SimpleNamespace(status_code=estado, json=lambda: datos, content=contenido)


def _almacen(storage, clave="sb_secret_ficticia"):
    return ar.Almacen("https://ficticio.supabase.co", clave, sesion=storage, pausa=0)


def _cifrado_ficticio(ruta, filas=300):
    """Un .enc con el mismo formato que respaldo.crear, con filas inventadas."""
    nonce = os.urandom(12)
    cifrador = Cipher(algorithms.AES(respaldo.clave(LLAVE)), modes.GCM(nonce)).encryptor()
    cifrador.authenticate_additional_data(respaldo.MAGIA)
    claro = gzip.compress(b"".join(json.dumps({"tabla": "ofertas", "fila_json": json.dumps(
        {"id": i, "titulo": f"Cargo ficticio {i}", "relleno": os.urandom(16).hex()})}).encode() + b"\n"
        for i in range(filas)), mtime=0)
    ruta.write_bytes(respaldo.MAGIA + nonce + cifrador.update(claro) + cifrador.finalize() + cifrador.tag)
    return claro


def test_de_punta_a_punta_cifrar_subir_listar_bajar_descifrar(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "TROZO", 4096)  # fuerza varios trozos
    storage = StorageFalso()
    almacen = _almacen(storage)
    claro = _cifrado_ficticio(tmp_path / "semanal.enc")
    m = ar.subir(almacen, tmp_path / "semanal.enc", "semanal", "123", datetime(2026, 11, 30, tzinfo=timezone.utc))
    assert m["carpeta"] == "semanal/2026-11-30_123" and len(m["partes"]) > 2
    assert storage.bucket["public"] is False and storage.bucket["limite"] <= 50_000_000
    assert [c for c, _ in ar.validos(almacen, "semanal")] == ["semanal/2026-11-30_123"]
    ar.bajar(almacen, m["carpeta"], tmp_path / "bajado.enc")
    assert (tmp_path / "bajado.enc").read_bytes() == (tmp_path / "semanal.enc").read_bytes()
    salida = io.BytesIO()
    respaldo.descifrar(tmp_path / "bajado.enc", LLAVE, salida)
    assert salida.read() == claro


def test_la_clave_nueva_va_solo_en_apikey_y_nunca_se_imprime(tmp_path, capsys):
    storage = StorageFalso()
    _cifrado_ficticio(tmp_path / "a.enc", filas=5)
    ar.subir(_almacen(storage), tmp_path / "a.enc", "semanal", "1")
    assert all(h.get("apikey") == "sb_secret_ficticia" and "Authorization" not in h for _, _, h in storage.llamadas)
    antigua = StorageFalso(publico=False)
    ar.subir(_almacen(antigua, clave="eyJficticia"), tmp_path / "a.enc", "semanal", "2")
    assert all(h.get("Authorization") == "Bearer eyJficticia" for _, _, h in antigua.llamadas)
    salida = capsys.readouterr()
    assert "ficticia" not in salida.out + salida.err


def test_bucket_publico_falla_sin_subir_nada(tmp_path):
    storage = StorageFalso(publico=True)
    _cifrado_ficticio(tmp_path / "a.enc", filas=5)
    with pytest.raises(RuntimeError, match="es público"):
        ar.subir(_almacen(storage), tmp_path / "a.enc", "semanal", "1")
    assert storage.objetos == {}


def test_trozo_corrupto_al_bajarlo_hace_fallar_la_subida(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "TROZO", 1024)
    storage = StorageFalso()
    storage.corromper.add("semanal/2026-11-30_9/parte-001")
    _cifrado_ficticio(tmp_path / "a.enc")
    with pytest.raises(RuntimeError, match="no coincide"):
        ar.subir(_almacen(storage), tmp_path / "a.enc", "semanal", "9", datetime(2026, 11, 30, tzinfo=timezone.utc))
    assert "semanal/2026-11-30_9/manifiesto.json" not in storage.objetos  # sin manifiesto no cuenta como respaldo
    assert ar.validos(_almacen(storage), "semanal") == []


def test_si_storage_falla_el_job_falla(tmp_path, monkeypatch):
    storage = StorageFalso()
    storage.fallar_subida = True
    _cifrado_ficticio(tmp_path / "a.enc", filas=5)
    almacen = _almacen(storage)
    monkeypatch.setattr(ar, "Almacen", lambda: almacen)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        ar.main(["subir", "--tipo", "semanal", "--carpeta", str(tmp_path)])


def test_no_sobrescribe_un_respaldo_existente(tmp_path):
    storage = StorageFalso()
    _cifrado_ficticio(tmp_path / "a.enc", filas=5)
    dia = datetime(2026, 11, 30, tzinfo=timezone.utc)
    ar.subir(_almacen(storage), tmp_path / "a.enc", "semanal", "1", dia)
    with pytest.raises(RuntimeError, match="Ya existe"):
        ar.subir(_almacen(storage), tmp_path / "a.enc", "semanal", "1", dia)


def test_poda_conserva_los_ultimos_validos_y_nunca_el_ultimo(tmp_path):
    storage = StorageFalso()
    almacen = _almacen(storage)
    _cifrado_ficticio(tmp_path / "a.enc", filas=5)
    inicio = datetime(2026, 10, 4, tzinfo=timezone.utc)
    for semana in range(6):
        ar.subir(almacen, tmp_path / "a.enc", "semanal", str(semana), inicio + timedelta(weeks=semana))
    storage.objetos["semanal/2026-10-01_roto/parte-000"] = b"incompleto"   # subida a medias, más vieja
    storage.objetos["semanal/2026-12-31_roto/parte-000"] = b"incompleto"   # a medias, más nueva que el último válido
    ar.subir(almacen, tmp_path / "a.enc", "antes-de-limpiar", "7", inicio)
    borradas = ar.podar(almacen, "semanal", conservar=4)
    assert borradas == ["semanal/2026-10-01_roto", "semanal/2026-10-04_0", "semanal/2026-10-11_1"]
    assert [c for c, _ in ar.validos(almacen, "semanal")] == [
        "semanal/2026-10-18_2", "semanal/2026-10-25_3", "semanal/2026-11-01_4", "semanal/2026-11-08_5"]
    assert "semanal/2026-12-31_roto/parte-000" in storage.objetos       # puede ser una subida en curso
    assert ar.podar(almacen, "antes-de-limpiar") == [] and ar.validos(almacen, "antes-de-limpiar")
    assert ar.podar(almacen, "semanal", conservar=0) == [  # aunque pidan 0, el último válido se queda
        "semanal/2026-10-18_2", "semanal/2026-10-25_3", "semanal/2026-11-01_4"]
    assert [c for c, _ in ar.validos(almacen, "semanal")] == ["semanal/2026-11-08_5"]


def test_poda_no_borra_si_no_puede_leer_un_manifiesto(tmp_path):
    storage = StorageFalso()
    almacen = _almacen(storage)
    _cifrado_ficticio(tmp_path / "a.enc", filas=5)
    for semana in range(3):
        ar.subir(almacen, tmp_path / "a.enc", "semanal", str(semana),
                 datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(weeks=semana))
    original = storage.request
    def falla_manifiesto(metodo, url, **k):
        if url.endswith("2026-11-01_0/manifiesto.json"):
            return StorageFalso._r(503)
        return original(metodo, url, **k)
    storage.request = falla_manifiesto
    with pytest.raises(RuntimeError, match="HTTP 503"):
        ar.podar(almacen, "semanal", conservar=1)
    storage.request = original
    assert len(ar.validos(almacen, "semanal")) == 3


def test_subir_cli_deja_resumen_sin_secretos_y_avisa_si_la_poda_falla(tmp_path, monkeypatch, capsys):
    storage = StorageFalso()
    carpeta = tmp_path / "respaldos"
    carpeta.mkdir()
    _cifrado_ficticio(carpeta / "semanal-x.enc", filas=5)
    almacen = _almacen(storage)
    monkeypatch.setattr(ar, "Almacen", lambda: almacen)
    monkeypatch.setattr(ar, "podar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("caída ficticia")))
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    ar.main(["subir", "--tipo", "semanal", "--carpeta", str(carpeta)])
    texto = resumen.read_text(encoding="utf-8")
    assert "bucket privado `respaldos`" in texto and "No se pudo revisar ni podar" in texto
    assert "[aviso] almacen_respaldos.podar" in capsys.readouterr().err
    assert "sb_secret" not in texto


def test_exige_un_solo_respaldo_en_la_carpeta(tmp_path):
    with pytest.raises(RuntimeError, match="exactamente un"):
        ar._archivo_unico(tmp_path)


def _paso(texto, nombre):
    inicio = texto.index(f"- name: {nombre}")
    fin = texto.find("\n      - ", inicio + 1)
    return texto[inicio:fin if fin != -1 else len(texto)]


@pytest.mark.parametrize("flujo,tipo", [("respaldo.yml", "semanal"), ("limpiar_fuera_objetivo.yml", "antes-de-limpiar")])
def test_workflows_suben_a_storage_y_el_artefacto_dura_un_dia(flujo, tipo):
    texto = (RAIZ / ".github" / "workflows" / flujo).read_text(encoding="utf-8")
    paso = _paso(texto, "Guardar la copia en Storage privado")
    assert f"python -m buscador.almacen_respaldos subir --tipo {tipo}" in paso
    assert "SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}" in paso
    assert "SUPABASE_BACKUP_KEY" not in paso  # subir no necesita descifrar
    assert texto.index("--fase respaldo") < texto.index("almacen_respaldos subir") < texto.index("upload-artifact")
    red = _paso(texto, "Red de seguridad temporal")
    assert "retention-days: 1\n" in red + "\n" and "retention-days: 90" not in texto
