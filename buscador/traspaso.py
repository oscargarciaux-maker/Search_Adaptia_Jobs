"""Traspaso a otro proyecto Supabase (p. ej., el de pago del cliente) y copia periódica cifrada.

Reutiliza el corte cifrado y la restauración probados en `respaldo` y las migraciones registradas. El destino debe ser un
proyecto sin las tablas de este sistema: así nunca se mezcla con la base de otra aplicación del cliente. Todo el destino
se prepara en una sola transacción; si algo falla, queda como estaba. El origen solo se marca como trasladado después de
comprobar los conteos, y desde entonces las capturas se detienen hasta que los secretos apunten al destino.
Nunca imprime credenciales ni contenido de vacantes o clientes: solo conteos.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from psycopg import sql

from buscador import migraciones, respaldo

MARCA = ("control", "trasladada")


def inventario(conn):
    """Conteos por tabla y valor de cada secuencia: lo mínimo para comparar origen y destino sin exponer datos."""
    tablas = {t: conn.execute(sql.SQL("select count(*) from public.{}").format(sql.Identifier(t))).fetchone()[0]
              for t in respaldo.existentes(conn, respaldo.TABLAS)}
    secuencias = {s: list(conn.execute(sql.SQL("select last_value,is_called from public.{}").format(sql.Identifier(s))).fetchone())
                  for s in respaldo.existentes(conn, respaldo.SECUENCIAS)}
    return {"tablas": tablas, "secuencias": secuencias}


def trasladada(conn):
    if not respaldo.existentes(conn, ("estado_operativo",)):
        return None
    fila = conn.execute("select payload from public.estado_operativo where cola=%s and identificador=%s", MARCA).fetchone()
    return fila[0] if fila else None


def exigir_vigente(conn):
    """El origen debe tener aplicadas todas las migraciones del código: el destino se instala con las mismas."""
    if trasladada(conn):
        raise RuntimeError("Esta base ya se trasladó. Cambia SUPABASE_URL, SUPABASE_SECRET_KEY y SUPABASE_DB_URL por los del destino.")
    if migraciones.pendientes(conn, migraciones.descubrir()):
        raise RuntimeError("El origen tiene migraciones pendientes: ejecuta «Preparar Supabase» antes del traspaso.")


def exigir_destino_libre(conn):
    """Ninguna tabla con los nombres de este sistema: protege la base de otra aplicación y evita mezclar dos historiales."""
    ocupadas = respaldo.existentes(conn, (*respaldo.TABLAS, "adaptia_migraciones"))
    if ocupadas:
        raise RuntimeError("El destino ya tiene tablas de este sistema (" + ", ".join(sorted(set(ocupadas))) + "). "
                           "Usa un proyecto Supabase nuevo y vacío, distinto del de la página web.")


def restaurar(conn, copia, llave):
    """Instala el esquema y restaura el corte en una sola transacción; devuelve el inventario resultante."""
    exigir_destino_libre(conn)
    with tempfile.TemporaryDirectory() as carpeta, conn.transaction():
        migraciones.aplicar(conn, migraciones.descubrir())
        respaldo.restaurar(conn, copia, llave, Path(carpeta) / "trabajo")
        migraciones.validar(conn)
        return inventario(conn)


def marcar(conn, destino):
    conn.execute("""insert into public.estado_operativo(cola,identificador,payload) values(%s,%s,%s::jsonb)
      on conflict(cola,identificador) do nothing""",
                 (*MARCA, json.dumps({"destino": destino, "en": datetime.now(timezone.utc).isoformat(timespec="seconds")})))


def comparar(origen, destino):
    diferencias = [f"{t}: origen {n}, destino {destino['tablas'].get(t)}" for t, n in origen["tablas"].items()
                   if destino["tablas"].get(t) != n]
    diferencias += [f"secuencia {s}" for s, v in origen["secuencias"].items() if destino["secuencias"].get(s) != v]
    if diferencias:
        raise RuntimeError("El destino no coincide con el origen; el origen sigue operando sin cambios. " + "; ".join(diferencias))


def trasladar(origen, destino, trabajo, llave, copia, ref_destino, ensayo=False):
    """Origen y destino son conexiones administrativas distintas. Devuelve el inventario comprobado.
    `ensayo`: copia y comprueba igual, pero el origen sigue operando (para practicar con un proyecto de prueba)."""
    exigir_vigente(origen)
    exigir_destino_libre(destino)
    with migraciones.bloqueo(origen):
        respaldo.crear(origen, trabajo, copia, llave)
        esperado = inventario(origen)
        obtenido = restaurar(destino, copia, llave)
        comparar(esperado, obtenido)
        if not ensayo:
            marcar(origen, ref_destino)
    return esperado


def resumen(titulo, inv):
    filas = "\n".join(f"| {t} | {n} |" for t, n in inv["tablas"].items())
    return f"### {titulo}\n\n| Tabla | Filas |\n|---|---|\n{filas}\n"


def _escribir_resumen(texto):
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    print(texto)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fase", choices=("respaldo", "traspaso"), required=True)
    p.add_argument("--salida", default="salida")
    p.add_argument("--privado", default="privado")
    p.add_argument("--ensayo", action="store_true", help="Traspaso de práctica: no detiene el origen")
    args = p.parse_args()
    llave = os.environ.get("SUPABASE_BACKUP_KEY", "")
    respaldo.clave(llave)
    fecha = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    trabajo = Path(args.salida) / "trabajo"
    with migraciones.conexion(os.environ.get("SUPABASE_DB_URL", ""), os.environ.get("SUPABASE_URL", "")) as origen:
        if args.fase == "respaldo":
            copia = Path(args.privado) / "respaldos" / f"semanal-{fecha}.enc"
            exigir_vigente(origen)
            with migraciones.bloqueo(origen):
                respaldo.crear(origen, trabajo, copia, llave)
                inv = inventario(origen)
            _escribir_resumen(resumen("Copia de seguridad cifrada creada", inv))
            return
        url_destino = os.environ.get("SUPABASE_URL_DESTINO", "")
        if url_destino.rstrip("/") == os.environ.get("SUPABASE_URL", "").rstrip("/"):
            raise RuntimeError("El destino es el mismo proyecto que el origen.")
        with migraciones.conexion(os.environ.get("SUPABASE_DB_URL_DESTINO", ""), url_destino) as destino:
            copia = Path(args.privado) / "respaldos" / f"traspaso-{fecha}.enc"
            inv = trasladar(origen, destino, trabajo, llave, copia, url_destino, ensayo=args.ensayo)
    if args.ensayo:
        _escribir_resumen(resumen("Ensayo comprobado: el destino coincide con el origen", inv) +
                          "\nEra un ensayo: tu base actual sigue operando igual. El proyecto de prueba ya no está vacío; "
                          "para repetir el ensayo usa otro proyecto o bórralo desde Supabase.")
        return
    _escribir_resumen(resumen("Traspaso comprobado: el destino coincide con el origen", inv) +
                      "\nEl origen quedó marcado como trasladado: las capturas se detendrán hasta que cambies "
                      "SUPABASE_URL, SUPABASE_SECRET_KEY y SUPABASE_DB_URL por los del destino.")


if __name__ == "__main__":
    main()
