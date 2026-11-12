"""Corte cifrado de las tablas del proyecto y trabajo; no incluye Auth/Storage del proveedor."""
import base64
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from psycopg import sql

TABLAS = ("catalogo_vacantes", "entregas_diarias", "ofertas", "ofertas_enlaces_historicos", "estado_operativo", "apify_reservas", "panel_configuracion", "panel_versiones", "panel_ejecuciones", "panel_asignaciones", "panel_ajustes", "adaptia_migraciones")
SECUENCIAS = ("ofertas_id_seq", "estado_operativo_revision_seq")
MAGIA = b"ADAPTIA1\n"


def clave(valor):
    try:
        resultado = base64.b64decode(valor.strip() + "=" * (-len(valor.strip()) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise RuntimeError("SUPABASE_BACKUP_KEY debe contener 32 bytes en base64 URL segura.") from None
    if len(resultado) != 32:
        raise RuntimeError("SUPABASE_BACKUP_KEY debe contener 32 bytes en base64 URL segura.")
    return resultado


def existentes(conn, nombres):
    return [n for n in nombres if conn.execute("select to_regclass(%s)", ("public." + n,)).fetchone()[0]]


def crear(conn, trabajo, destino, llave):
    """El llamador mantiene excluidos los escritores. Streaming gzip + AES-256-GCM, sin copia en claro."""
    destino, trabajo = Path(destino), Path(trabajo)
    destino.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + "." + uuid4().hex + ".partial")
    nonce = os.urandom(12)
    cifrador = Cipher(algorithms.AES(clave(llave)), modes.GCM(nonce)).encryptor()
    cifrador.authenticate_additional_data(MAGIA)
    class Flujo:
        def __init__(self, archivo): self.archivo = archivo
        def write(self, b):
            self.archivo.write(cifrador.update(b))
            return len(b)
        def flush(self): self.archivo.flush()
    try:
        with os.fdopen(os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as archivo:
            archivo.write(MAGIA + nonce)
            with gzip.GzipFile(fileobj=Flujo(archivo), mode="wb", mtime=0) as comprimido:
                def escribir(obj): comprimido.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
                with conn.transaction():
                    conn.execute("set transaction isolation level repeatable read read only")
                    tablas, secuencias = existentes(conn, TABLAS), existentes(conn, SECUENCIAS)
                    escribir({"formato": 1, "tablas": tablas, "secuencias": secuencias,
                              "creado_en": datetime.now(timezone.utc).isoformat(),
                              "codigo_commit": os.environ.get("GITHUB_SHA", ""), "ejecucion_id": os.environ.get("GITHUB_RUN_ID", "")})
                    for tabla in tablas:
                        with conn.cursor(name="corte_" + tabla) as cursor:
                            cursor.execute(sql.SQL("select row_to_json(t)::text from public.{} t").format(sql.Identifier(tabla)))
                            for fila, in cursor:
                                escribir({"tabla": tabla, "fila_json": fila})
                    for nombre in secuencias:
                        valor, llamada = conn.execute(sql.SQL("select last_value,is_called from public.{}").format(sql.Identifier(nombre))).fetchone()
                        escribir({"secuencia": nombre, "valor": valor, "llamada": llamada})
                if trabajo.exists():
                    for ruta in sorted(trabajo.rglob("*")):
                        if ruta.is_symlink(): raise RuntimeError("El corte de trabajo no admite enlaces simbólicos.")
                        if ruta.is_file():
                            escribir({"archivo": ruta.relative_to(trabajo).as_posix(),
                                      "contenido": base64.b64encode(ruta.read_bytes()).decode()})
            archivo.write(cifrador.finalize())
            archivo.write(cifrador.tag)
            archivo.flush()
            os.fsync(archivo.fileno())
        temporal.replace(destino)
        return destino
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise


def descifrar(archivo, llave, destino):
    """No se usa ninguna fila hasta verificar la autenticidad de todo el cifrado."""
    with Path(archivo).open("rb") as entrada:
        if entrada.read(len(MAGIA)) != MAGIA: raise RuntimeError("Formato de respaldo desconocido.")
        nonce = entrada.read(12)
        entrada.seek(-16, 2)
        final = entrada.tell()
        tag = entrada.read(16)
        descifrador = Cipher(algorithms.AES(clave(llave)), modes.GCM(nonce, tag)).decryptor()
        descifrador.authenticate_additional_data(MAGIA)
        entrada.seek(len(MAGIA) + 12)
        while entrada.tell() < final:
            destino.write(descifrador.update(entrada.read(min(1024 * 1024, final - entrada.tell()))))
        destino.write(descifrador.finalize())
    destino.seek(0)


def restaurar(conn, archivo, llave, trabajo):
    """Solo un destino aislado vacío. El esquema se prepara antes; devuelve el trabajo en otra carpeta."""
    trabajo = Path(trabajo)
    if trabajo.exists(): raise RuntimeError("El destino de trabajo debe ser una carpeta nueva.")
    with tempfile.TemporaryFile() as comprimido:
        descifrar(archivo, llave, comprimido)
        with conn.transaction():
            for tabla in existentes(conn, TABLAS[:-1]):
                if conn.execute(sql.SQL("select exists(select 1 from public.{})").format(sql.Identifier(tabla))).fetchone()[0]:
                    raise RuntimeError("La restauración exige tablas de negocio vacías.")
            # Restaurar el corte exacto, incluso si contenía aliases todavía sin reconciliar.
            # El ALTER se revierte junto con los datos si falla la transacción.
            trigger_unico = conn.execute("""select tgenabled from pg_trigger
                where tgrelid=to_regclass('public.ofertas') and tgname='oferta_unica'""").fetchone()
            if trigger_unico and trigger_unico[0] != 'D':
                conn.execute("alter table public.ofertas disable trigger oferta_unica")
            with gzip.GzipFile(fileobj=comprimido, mode="rb") as entrada:
                cabecera = json.loads(next(entrada))
                if cabecera.get("formato") != 1 or not set(cabecera["tablas"]) <= set(TABLAS):
                    raise RuntimeError("Tablas/formato de respaldo inválidos.")
                if "adaptia_migraciones" in cabecera["tablas"]:
                    conn.execute("delete from public.adaptia_migraciones")
                archivos, columnas_por_tabla, lote = [], {}, []
                tabla_lote = None
                def enviar():
                    if not lote: return
                    identidad = sql.SQL("overriding system value") if tabla_lote == "ofertas" else sql.SQL("")
                    conn.execute(sql.SQL("insert into public.{} {} select * from jsonb_populate_recordset(null::public.{}, %s::jsonb)")
                        .format(sql.Identifier(tabla_lote), identidad, sql.Identifier(tabla_lote)), ("[" + ",".join(lote) + "]",))
                    lote.clear()
                for linea in entrada:
                    dato = json.loads(linea)
                    if "tabla" not in dato or dato["tabla"] != tabla_lote or len(lote) >= 100:
                        enviar()
                    if "tabla" in dato:
                        tabla = dato["tabla"]
                        if tabla not in cabecera["tablas"]: raise RuntimeError("Tabla fuera del inventario.")
                        if tabla not in columnas_por_tabla:
                            columnas_por_tabla[tabla] = {r[0] for r in conn.execute("select column_name from information_schema.columns where table_schema='public' and table_name=%s", (tabla,))}
                        if not set(json.loads(dato["fila_json"])) <= columnas_por_tabla[tabla]:
                            raise RuntimeError("El respaldo contiene columnas desconocidas; preparar su versión de esquema antes de restaurar.")
                        tabla_lote = tabla
                        lote.append(dato["fila_json"])
                    elif "secuencia" in dato:
                        if dato["secuencia"] not in SECUENCIAS: raise RuntimeError("Secuencia desconocida.")
                        conn.execute("select setval(%s::regclass,%s,%s)", ("public." + dato["secuencia"], dato["valor"], dato["llamada"]))
                    elif "archivo" in dato:
                        ruta = PurePosixPath(dato["archivo"])
                        if ruta.is_absolute() or ".." in ruta.parts or not ruta.parts or "\\" in str(ruta):
                            raise RuntimeError("Ruta de trabajo inválida.")
                        archivos.append((ruta, base64.b64decode(dato["contenido"], validate=True)))
                    else: raise RuntimeError("Registro de respaldo desconocido.")
                enviar()
            if trigger_unico and trigger_unico[0] != 'D':
                modo = {'O': '', 'A': 'always ', 'R': 'replica '}[trigger_unico[0]]
                conn.execute("alter table public.ofertas enable " + modo + "trigger oferta_unica")
            trabajo.mkdir(mode=0o700, parents=True)
            for ruta, contenido in archivos:
                destino = trabajo / str(ruta)
                destino.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with os.fdopen(os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as salida:
                    salida.write(contenido)
