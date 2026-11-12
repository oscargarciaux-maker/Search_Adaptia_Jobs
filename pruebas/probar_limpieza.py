"""Ensayo en PostgreSQL local aislado de la limpieza del contrato v12 (portugués y solo Brasil)."""
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from buscador import catalogo, limpiar_idioma_pais, migraciones, vacante

PORTUGUES = ("Estamos buscando um(a) Product Designer para atuar na nossa equipe. Você será responsável por pesquisas "
             "com usuários e protótipos. Requisitos: experiência com Figma e conhecimento em design systems. ") * 3
ESPANOL = ("Buscamos un Product Designer para nuestro equipo en Bogotá. Funciones: diseñar flujos y prototipos. "
           "Requisitos: 3 años de experiencia y manejo de Figma. Ofrecemos trabajo híbrido. ") * 3
INGLES = ("We are looking for a Product Designer to join our remote team across Latin America. You will run research "
          "and design flows. Requirements: 4 years of experience with Figma. ") * 3


def _vacante(n, ubicacion, texto, remoto=None, **guardado):
    v = vacante.crear("Product Designer", f"Empresa {n}", f"https://jobs.lever.co/empresa/{n}", "Lever",
                      ubicacion=ubicacion, descripcion=texto, fecha="2026-11-06", remoto=remoto, hoy="2026-11-07")
    v.update(guardado)  # cómo quedó guardada antes del arreglo (idioma «es», país BR)
    return v


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
        vacantes = {
            "portugues": _vacante(1, "São Paulo, Brazil", PORTUGUES, idioma="es", paises=["BR"]),
            "solo_brasil": _vacante(2, "Remoto, Brazil", INGLES, True, paises=["BR"]),
            "varios": _vacante(3, "Argentina (Remote); Mexico (Remote); São Paulo, Brazil", INGLES, True,
                               paises=["AR", "BR", "MX"]),
            "espanol": _vacante(4, "Bogotá, Colombia (Híbrido)", ESPANOL),
        }
        with conectar(nombre) as c:
            with c.transaction():
                migraciones.aplicar(c, migraciones.descubrir())
            for v in vacantes.values():
                c.execute("insert into public.catalogo_vacantes select * from "
                          "jsonb_populate_record(null::public.catalogo_vacantes,%s)",
                          (Jsonb(catalogo.fila(v, "2026-11-07T00:00:00Z")),))
                c.execute("insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,"
                          "snapshot) values(%s,'2026-11-07','product_designer','exact',now(),%s)", (v["id"], Jsonb(v)))
                c.execute("insert into public.ofertas(external_id,job_title,company_name,offer_url,vacante_id,"
                          "hire_countries,scraped_at) values(%s,%s,%s,%s,%s,%s,'2026-11-07')",
                          (v["id"], v["titulo"], v["empresa"], v["enlace"], v["id"], v["paises"]))
            # Una fila antigua sin vacante en el catálogo, pero que dice contratar solo en Brasil.
            c.execute("insert into public.ofertas(external_id,job_title,company_name,offer_url,hire_countries) values"
                      "('antigua-br','QA','Empresa','https://jobs.lever.co/x/antigua','{BR}')")

            simulado = limpiar_idioma_pais.correr(c)
            assert simulado["ofertas_a_borrar"] == 3 and simulado["catalogo_a_archivar"] == 2, simulado
            assert simulado["catalogo_por_motivo"] == {"en portugués": 1, "solo para Brasil": 1}, simulado
            assert c.execute("select count(*) from public.ofertas").fetchone()[0] == 5  # simular no cambia nada
            assert "Product Designer" not in str(simulado) and "lever" not in str(simulado)  # solo conteos

            aplicado = limpiar_idioma_pais.correr(c, aplicar_cambios=True)
            assert aplicado["ofertas_borradas"] == 3 and aplicado["catalogo_archivado"] == 2, aplicado
            quedan = {r[0] for r in c.execute("select external_id from public.ofertas")}
            assert quedan == {vacantes["varios"]["id"], vacantes["espanol"]["id"]}, quedan
            estados = dict(c.execute("select id,status from public.catalogo_vacantes"))
            assert estados[vacantes["portugues"]["id"]] == estados[vacantes["solo_brasil"]["id"]] == "archived"
            assert estados[vacantes["varios"]["id"]] == estados[vacantes["espanol"]["id"]] == "active"
            assert c.execute("select count(*) from public.entregas_diarias").fetchone()[0] == 4  # historial intacto
            otra = limpiar_idioma_pais.correr(c, aplicar_cambios=True)  # repetirla no hace nada más
            assert otra["ofertas_borradas"] == 0 and otra["catalogo_archivado"] == 0, otra
        print("Limpieza v12: simulación sin cambios, portugués y solo Brasil retirados de ofertas y archivados, "
              "remotas de varios países y español conservadas, historial intacto, repetible: aprobados.")
    finally:
        with conectar() as c:
            c.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(nombre)))


if __name__ == "__main__":
    main()
