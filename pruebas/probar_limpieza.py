"""Ensayo en PostgreSQL local aislado de la revisión y limpieza de vacantes fuera del objetivo (contrato v13)."""
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from buscador import catalogo, limpiar_fuera_objetivo as limpieza, migraciones, vacante

ESPANOL = ("Buscamos un Product Designer para nuestro equipo en Bogotá. Funciones: diseñar flujos y prototipos. "
           "Requisitos: 3 años de experiencia y manejo de Figma. Ofrecemos trabajo híbrido. ") * 3
INGLES = ("We are looking for a Product Designer to join our team. You will run research and design flows. "
          "Requirements: 4 years of experience with Figma and the product team. ") * 3
FRANCES = ("Nous recherchons un Product Designer pour rejoindre notre équipe à Paris. Vous serez responsable des "
           "parcours utilisateurs et des prototypes avec les équipes produit. ") * 3


def _vacante(n, ubicacion, texto, remoto=None, **guardado):
    v = vacante.crear("Product Designer", f"Empresa {n}", f"https://jobs.lever.co/empresa/{n}", "Lever",
                      ubicacion=ubicacion, descripcion=texto, fecha="2026-11-06", remoto=remoto, hoy="2026-11-07")
    v.update(guardado)  # cómo quedó guardada con las reglas de entonces
    return v


CASOS = {  # nombre: (vacante, decisión esperada)
    "presencial_rumania": (lambda: _vacante(1, "Bucarest, Rumania (Presencial)", INGLES, paises=["CO"]), "borrar"),
    "remota_reino_unido": (lambda: _vacante(2, "Londres, Inglaterra, Reino Unido", INGLES, True,
                                             paises=["CO"], confianza_pais="baja"), "borrar"),
    "frances": (lambda: _vacante(3, "Remote - Worldwide", FRANCES, True, idioma="es"), "borrar"),
    "dudosa": (lambda: _vacante(4, "Conshohocken, PA", INGLES), "revisar"),
    "remota_latam": (lambda: _vacante(5, "Remote - LATAM", INGLES, True), ""),
    "bogota": (lambda: _vacante(6, "Bogotá, Colombia (Híbrido)", ESPANOL), ""),
}


def main():
    if os.environ.get("ADAPTIA_PRUEBA_SQL") != "true" or os.environ.get("PGHOST", "127.0.0.1") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Solo PostgreSQL local aislado")

    def conectar(db="postgres"):
        return psycopg.connect(host="127.0.0.1", port=os.environ.get("PGPORT", "5432"), user="postgres",
                               password=os.environ.get("PGPASSWORD", "prueba-migraciones"), dbname=db, autocommit=True)
    nombre = "adaptia_limpieza_" + uuid4().hex
    with conectar() as c:
        for rol in ("anon", "authenticated", "service_role"):
            if not c.execute("select 1 from pg_roles where rolname=%s", (rol,)).fetchone():
                c.execute(sql.SQL("create role {} {}").format(sql.Identifier(rol),
                          sql.SQL("bypassrls") if rol == "service_role" else sql.SQL("")))
        c.execute(sql.SQL("create database {}").format(sql.Identifier(nombre)))
    try:
        vacantes = {k: (f(), esperado) for k, (f, esperado) in CASOS.items()}
        with conectar(nombre) as c, tempfile.TemporaryDirectory() as carpeta:
            with c.transaction():
                migraciones.aplicar(c, migraciones.descubrir())
            numeros = {}
            for k, (v, _) in vacantes.items():
                c.execute("insert into public.catalogo_vacantes select * from "
                          "jsonb_populate_record(null::public.catalogo_vacantes,%s)",
                          (Jsonb(catalogo.fila(v, "2026-11-07T00:00:00Z")),))
                c.execute("insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,"
                          "snapshot) values(%s,'2026-11-07','product_designer','exact',now(),%s)", (v["id"], Jsonb(v)))
                numeros[k] = c.execute("insert into public.ofertas(external_id,job_title,company_name,offer_url,"
                                       "vacante_id,scraped_at) values(%s,%s,%s,%s,%s,'2026-11-07') returning id",
                                       (v["id"], v["titulo"], v["empresa"], v["enlace"], v["id"])).fetchone()[0]
            # Fila antigua sin catálogo: se juzga por sus propias columnas.
            numeros["sin_catalogo"] = c.execute(
                "insert into public.ofertas(external_id,job_title,company_name,offer_url,location,work_mode,"
                "posting_language) values('vieja','QA Engineer','Empresa','https://jobs.lever.co/x/v',"
                "'Varsovia, Mazovia, Polonia','onsite','en') returning id").fetchone()[0]

            revision = limpieza.correr(c, carpeta)
            assert revision["propuestas_para_borrar"] == 4 and revision["para_revisar_a_mano"] == 1, revision
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 7  # revisar no cambia nada
            listado = (Path(carpeta) / "revision.html").read_text(encoding="utf-8")
            assert "Bucarest" in listado and revision["huella"] in listado
            assert "Product Designer" in (Path(carpeta) / "revision.csv").read_text(encoding="utf-8-sig")

            try:  # huella equivocada: no cambia nada
                limpieza.correr(c, carpeta, True, "0000000000")
                raise AssertionError("Aplicó con una huella equivocada")
            except SystemExit:
                pass
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 7

            hecho = limpieza.correr(c, carpeta, True, revision["huella"], conservar=str(numeros["frances"]),
                                    borrar_tambien=str(numeros["dudosa"]))
            assert hecho["ofertas_borradas"] == 4 and hecho["catalogo_archivado"] == 3, hecho
            quedan = {r[0] for r in c.execute("select id from public.ofertas")}
            assert quedan == {numeros["frances"], numeros["remota_latam"], numeros["bogota"]}, quedan
            estados = dict(c.execute("select id,status from public.catalogo_vacantes"))
            assert estados[vacantes["presencial_rumania"][0]["id"]] == "archived"
            assert estados[vacantes["frances"][0]["id"]] == estados[vacantes["bogota"][0]["id"]] == "active"
            assert c.execute("select count(*) from public.entregas_diarias").fetchone()[0] == 6  # historial intacto
        print("Limpieza v13: listado sin cambios, huella obligatoria, conservar y borrar_tambien respetados, "
              "presencial/remota fuera y otros idiomas retirados, LATAM y España conservadas, historial intacto: aprobados.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
