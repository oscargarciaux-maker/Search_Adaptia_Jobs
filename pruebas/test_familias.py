"""Mapa de cargos: títulos reales (LinkedIn, Indeed, elempleo, portales de empresas) y su familia esperada."""
import re

import pytest

from buscador import familias, normalizar

# (título, familia que debe aparecer, coincidencia esperada)
POSITIVOS = [
    # Diseño de producto y UX/UI
    ("Senior Product Designer (UX/UI)", "diseno-producto-ux", "exacto"),
    ("Product Designer", "diseno-producto-ux", "exacto"),
    ("Lead Product Designer - Remote work | REF#300445", "diseno-producto-ux", "exacto"),
    ("Staff Product Designer", "diseno-producto-ux", "exacto"),
    ("Diseñadora / Diseñador UX", "diseno-producto-ux", "exacto"),
    ("1961 -  Diseñador UX/UI – Experiencia de Usuario e Interfaces", "diseno-producto-ux", "exacto"),
    ("Diseñador(a) UX/UI", "diseno-producto-ux", "exacto"),
    ("UI/UX Designer", "diseno-producto-ux", "exacto"),
    ("UX/UI Designer - Fully Remote (LATAM)", "diseno-producto-ux", "exacto"),
    ("Senior UX Designer", "diseno-producto-ux", "exacto"),
    ("Product Designer Associate (Diseñador asociado de Producto) - Bogotá [Hybrid]", "diseno-producto-ux", "exacto"),
    ("Diseñador de producto digital", "diseno-producto-ux", "exacto"),
    ("Designer de Produto Pleno", "diseno-producto-ux", "exacto"),
    ("Middle UX/UI Designer - Back Office", "diseno-producto-ux", "exacto"),
    ("Front UI/UX Specialist", "diseno-producto-ux", "exacto"),
    ("Diseñador UI", "diseno-producto-ux", "exacto"),
    ("Digital Product Designer", "diseno-producto-ux", "exacto"),
    ("Interaction Designer", "diseno-producto-ux", "similar"),
    ("Design Systems Designer", "diseno-producto-ux", "similar"),
    ("Head of Design", "diseno-producto-ux", "similar"),
    ("Consultor UX Proficient", "diseno-producto-ux", "similar"),
    ("Especialista UX/UI", "diseno-producto-ux", "exacto"),
    ("Visual Designer", "diseno-producto-ux", "similar"),
    ("Product Owner", "diseno-producto-ux", "cercano"),
    ("UX Writer", "diseno-producto-ux", "cercano"),
    ("Desinger UX", "diseno-producto-ux", "similar"),
    # UX Research
    ("UX Researcher", "ux-research", "exacto"),
    ("Senior User Researcher", "ux-research", "exacto"),
    ("Investigadora UX", "ux-research", "exacto"),
    ("Research Ops Specialist", "ux-research", "similar"),
    # Diseño web, gráfico, ilustración, motion, 3D, videojuegos, servicios, instruccional
    ("Diseñador(a) Web (UX/UI) Jr", "diseno-web", "exacto"),
    ("Web Designer (Webflow)", "diseno-web", "exacto"),
    ("Senior Web Designer  -  UI/UX", "diseno-web", "exacto"),
    ("Diseñador gráfico", "diseno-grafico", "exacto"),
    ("Graphic Designer 3D / Architect (Remote - Argentina)", "diseno-grafico", "exacto"),
    ("Paid Media Designer", "diseno-grafico", "similar"),
    ("Brand Designer", "diseno-grafico", "similar"),
    ("Director de arte", "diseno-grafico", "similar"),
    ("Diseñador de redes sociales", "diseno-grafico", "similar"),
    ("Ilustrador digital", "ilustracion", "exacto"),
    ("Concept Artist", "ilustracion", "similar"),
    ("Motion Graphics Designer", "motion-animacion", "exacto"),
    ("Motion Designer LATAM (Full Remote)", "motion-animacion", "exacto"),
    ("Animador 2D", "motion-animacion", "exacto"),
    ("3D Animator", "motion-animacion", "exacto"),
    ("VFX Artist", "motion-animacion", "similar"),
    ("Artista 3D", "diseno-3d", "exacto"),
    ("3D Generalist", "diseno-3d", "exacto"),
    ("Senior UI Artist (Unreal Engine 5)", "diseno-videojuegos", "exacto"),
    ("Game Designer", "diseno-videojuegos", "exacto"),
    ("Level Designer", "diseno-videojuegos", "exacto"),
    ("Talento B - Diseño de Servicios", "diseno-servicios-cx", "exacto"),
    ("Service Designer", "diseno-servicios-cx", "exacto"),
    ("CX Designer", "diseno-servicios-cx", "exacto"),
    ("Diseñador instruccional", "diseno-instruccional", "exacto"),
    ("Instructional Designer (E-learning)", "diseno-instruccional", "exacto"),
    # Video, foto y audio
    ("Editor de video", "edicion-video", "exacto"),
    ("Video Editor", "edicion-video", "exacto"),
    ("Semi Senior Video Editor", "edicion-video", "exacto"),
    ("Editora de video para redes sociales", "edicion-video", "exacto"),
    ("Editor de Reels", "edicion-video", "similar"),
    ("YouTube Video Editor", "edicion-video", "exacto"),
    ("Short Form Video Editor (TikTok)", "edicion-video", "exacto"),
    ("Videógrafo", "edicion-video", "cercano"),  # una palabra: baja un grado
    ("Colorista", "edicion-video", "cercano"),
    ("Fotógrafo de producto", "produccion-audiovisual", "exacto"),
    ("Productor audiovisual", "produccion-audiovisual", "exacto"),
    ("Podcast Editor", "audio-sonido", "exacto"),
    ("Ingeniero de sonido", "audio-sonido", "exacto"),
    # Desarrollo
    ("Frontend Developer (React)", "frontend", "exacto"),
    ("Desarrollador Front-End Semi Senior", "frontend", "exacto"),
    ("Front End Engineer", "frontend", "exacto"),
    ("React Developer", "frontend", "similar"),
    ("Desarrollador Angular", "frontend", "similar"),
    ("Backend Developer (Node.js)", "backend", "exacto"),
    ("Desarrollador Backend Java", "backend", "exacto"),
    ("Desarrollador Java Semi Senior", "backend", "similar"),
    ("Python Developer", "backend", "similar"),
    (".NET Developer", "backend", "similar"),
    ("Desarrollador .NET", "backend", "similar"),
    ("PHP Developer (Laravel)", "backend", "similar"),
    ("Golang Developer", "backend", "similar"),
    ("Desarrollador Full Stack", "fullstack", "exacto"),
    ("Full-Stack Engineer", "fullstack", "exacto"),
    ("MERN Developer", "fullstack", "similar"),
    ("Desarrollador", "desarrollo-software", "similar"),
    ("Software Engineer", "desarrollo-software", "exacto"),
    ("Ingeniero de Software", "desarrollo-software", "exacto"),
    ("Programador", "desarrollo-software", "similar"),
    ("Analista Programador", "desarrollo-software", "similar"),
    ("Desenvolvedor de Software", "desarrollo-software", "exacto"),
    ("Flutter Developer", "movil", "exacto"),
    ("Desarrollador iOS", "movil", "exacto"),
    ("Android Developer", "movil", "exacto"),
    ("React Native Developer", "movil", "exacto"),
    ("Unity Developer", "videojuegos-desarrollo", "exacto"),
    ("Game Developer", "videojuegos-desarrollo", "exacto"),
    ("Desarrollador WordPress", "wordpress-cms", "exacto"),
    ("Shopify Developer", "wordpress-cms", "exacto"),
    ("Webmaster", "wordpress-cms", "similar"),
    ("Desarrollador web", "wordpress-cms", "exacto"),
    ("No-Code Developer (Bubble)", "no-code", "exacto"),
    ("Automation Specialist (Zapier / Make)", "no-code", "exacto"),
    ("Desarrollador RPA", "no-code", "exacto"),
    ("Salesforce Developer", "crm-erp", "exacto"),
    ("Consultor SAP FICO", "crm-erp", "exacto"),
    ("Desarrollador ABAP", "crm-erp", "exacto"),
    ("Solidity Developer", "blockchain", "exacto"),
    ("Tech Lead", "arquitectura-software", "exacto"),
    ("Arquitecto de Software", "arquitectura-software", "exacto"),
    ("Engineering Manager", "arquitectura-software", "exacto"),
    # Calidad
    ("QA Automation Engineer", "qa", "exacto"),
    ("Analista QA", "qa", "exacto"),
    ("Tester Manual", "qa", "similar"),
    ("Software Tester", "qa", "exacto"),
    ("QA", "qa", "similar"),
    # Datos e IA
    ("Data Analyst Jr", "analista-datos", "exacto"),
    ("Analista de Datos", "analista-datos", "exacto"),
    ("Product Analyst Jr.", "analista-datos", "exacto"),
    ("Analista BI", "bi", "exacto"),
    ("Power BI Developer", "bi", "exacto"),
    ("Data Scientist", "ciencia-datos", "exacto"),
    ("Científica de Datos", "ciencia-datos", "exacto"),
    ("Data Engineer", "ingenieria-datos", "exacto"),
    ("Ingeniera de Datos", "ingenieria-datos", "exacto"),
    ("Machine Learning Engineer", "ia-ml", "exacto"),
    ("AI Engineer", "ia-ml", "exacto"),
    ("LLM Engineer", "ia-ml", "exacto"),
    ("AI Trainer - Spanish", "entrenamiento-ia", "exacto"),
    ("Data Annotator", "entrenamiento-ia", "exacto"),
    # Infraestructura y seguridad
    ("DevOps Engineer", "devops-sre", "exacto"),
    ("Site Reliability Engineer (SRE)", "devops-sre", "exacto"),
    ("Cloud Engineer AWS", "cloud", "exacto"),
    ("Soporte Técnico Nivel 1", "soporte-ti", "exacto"),
    ("Help Desk Analyst", "soporte-ti", "exacto"),
    ("Analista de Soporte", "soporte-ti", "exacto"),
    ("Administrador de Sistemas Linux", "sistemas-redes", "exacto"),
    ("Network Engineer", "sistemas-redes", "exacto"),
    ("DBA Oracle", "sistemas-redes", "similar"),
    ("Analista de Ciberseguridad", "ciberseguridad", "exacto"),
    ("SOC Analyst", "ciberseguridad", "exacto"),
    ("Pentester", "ciberseguridad", "similar"),
    # Producto y proyectos
    ("Product Manager", "product-manager", "exacto"),
    ("Technical Product Manager", "product-manager", "exacto"),
    ("Product Owner", "product-owner", "exacto"),
    ("Scrum Master", "project-manager", "exacto"),
    ("Project Manager IT", "project-manager", "exacto"),
    ("Líder de proyectos", "project-manager", "exacto"),
    ("Business Analyst", "analista-negocio", "exacto"),
    ("Analista Funcional", "analista-negocio", "exacto"),
    # Contenido y marketing
    ("Copywriter", "copywriting-redaccion", "similar"),
    ("Redactor de contenidos", "copywriting-redaccion", "exacto"),
    ("Content Writer", "copywriting-redaccion", "exacto"),
    ("UX Writer", "ux-writing-contenido", "exacto"),
    ("Content Designer", "ux-writing-contenido", "exacto"),
    ("Community Manager", "community-redes", "exacto"),
    ("Social Media Manager", "community-redes", "exacto"),
    ("Creador de contenido UGC", "community-redes", "exacto"),
    ("Especialista SEO", "seo-sem", "exacto"),
    ("Traductor de inglés", "traduccion", "similar"),
    ("English-Spanish Translator", "traduccion", "exacto"),
    ("Especialista en Marketing Digital", "marketing-digital", "exacto"),
    ("Marketing Manager", "marketing-digital", "exacto"),
    ("Trafficker Digital", "performance-growth", "exacto"),
    ("Growth Marketer", "performance-growth", "exacto"),
    ("Media Buyer", "performance-growth", "exacto"),
    ("Ecommerce Manager", "ecommerce", "exacto"),
    # Ventas, clientes, personas y administración
    ("SDR - Sales Development Representative", "ventas-tech", "exacto"),
    ("Account Executive (SaaS)", "ventas-tech", "exacto"),
    ("Business Developer", "ventas-tech", "similar"),
    ("Customer Success Manager", "customer-success", "exacto"),
    ("Agente de Atención al Cliente Bilingüe", "customer-success", "exacto"),
    ("Technical Recruiter", "reclutamiento", "exacto"),
    ("Reclutadora IT", "reclutamiento", "exacto"),
    ("Talent Acquisition Specialist", "reclutamiento", "exacto"),
    ("Asistente virtual bilingüe", "asistente-virtual", "exacto"),
    ("Executive Assistant (Remote)", "asistente-virtual", "exacto"),
    ("Instructor de programación", "educacion-tech", "exacto"),
]

# (título, familia que NO debe aparecer)
NEGATIVOS = [
    ("Linux Engineer", "diseno-producto-ux"),
    ("Linux Engineer", "arquitectura-software"),
    ("Senior UI Artist (Unreal Engine 5)", "diseno-producto-ux"),
    ("Diseñador industrial", "diseno-producto-ux"),
    ("Diseñador de modas (desarrollo de producto)", "diseno-producto-ux"),
    ("Diseñador de interiores", "diseno-grafico"),
    ("Front-end Developer UX/UI", "diseno-producto-ux"),
    ("Business Developer", "backend"),
    ("Business Developer", "desarrollo-software"),
    ("Ingeniero civil", "desarrollo-software"),
    ("Ingeniero de procesos", "desarrollo-software"),
    ("Editor de textos", "edicion-video"),
    ("Managing Editor", "edicion-video"),
    ("Video Editor", "copywriting-redaccion"),
    ("Guardia de seguridad", "ciberseguridad"),
    ("Personal Trainer", "entrenamiento-ia"),
    ("Gerente de obra", "project-manager"),
    ("Network Marketing", "marketing-digital"),
    ("Administrador de restaurante", "sistemas-redes"),
    ("Quality Inspector", "qa"),
    ("Cajero de supermercado", None),
    ("Auxiliar de bodega", None),
    ("Conductor de camión", None),
]


@pytest.mark.parametrize("titulo,familia,grado", POSITIVOS)
def test_titulo_en_su_familia(titulo, familia, grado):
    resultado = {r["familia"]: r["coincidencia"] for r in familias.clasificar(titulo)}
    assert resultado.get(familia) == grado, resultado


@pytest.mark.parametrize("titulo,familia", NEGATIVOS)
def test_titulo_fuera_de_familia(titulo, familia):
    resultado = {r["familia"] for r in familias.clasificar(titulo)}
    if familia is None:
        assert not resultado, resultado
    else:
        assert familia not in resultado, resultado


def test_herramientas_en_la_descripcion_rescatan_titulos_raros():
    r = familias.clasificar("Editor", "Buscamos editor con experiencia en Premiere Pro y CapCut para reels de TikTok")
    assert {"familia": "edicion-video", "coincidencia": "cercano"} in r
    assert familias.clasificar("Editor", "Editor para la revista mensual de la compañía") == []


def test_hay_al_menos_150_casos():
    assert len(POSITIVOS) + len(NEGATIVOS) >= 150


def test_mapa_bien_formado():
    mapa = familias.mapa()
    ids = [f["id"] for f in mapa]
    assert len(ids) == len(set(ids)) and len(ids) >= 50
    for f in mapa:
        assert re.fullmatch(r"[a-z0-9-]+", f["id"]), f["id"]
        assert f["nombre"] and f["area"], f["id"]
        assert 1 <= len(f["consultas"]) <= 8, f["id"]
        assert f["_titulos"]["exacto"], f"{f['id']} sin títulos exactos"
        for campo in ("exactos", "similares", "cercanos", "herramientas", "genericos", "excluir"):
            assert isinstance(f.get(campo) or [], list), (f["id"], campo)


def test_la_pagina_recibe_cada_familia_con_sus_claves():
    pagina = familias.para_la_pagina()
    ux = next(f for f in pagina if f["id"] == "diseno-producto-ux")
    assert "product designer" in ux["claves"] and "ux/ui" in ux["claves"]
    assert "product owner" in ux["cercanos"]


def test_nivel_del_titulo():
    assert normalizar.nivel("Senior Product Designer") == "senior"
    assert normalizar.nivel("Desarrollador Java Semi Senior") == "semi senior"
    assert normalizar.nivel("Diseñador UX Jr") == "junior"
    assert normalizar.nivel("Lead Product Designer") == "lead"
    assert normalizar.nivel("Product Design Intern") == "trainee"
    assert normalizar.nivel("UX Designer III") == "senior"
    assert normalizar.nivel("Product Manager") == ""
