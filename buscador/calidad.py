"""Descartes explícitos de contenido que no es una oferta; no certifica autenticidad de empresas."""
import re

from buscador import enlaces, normalizar

NO_ES_OFERTA = re.compile(r"\b(webinar|bootcamp|masterclass|curso|course|workshop|open to work|opentowork|"
                         r"busco empleo|busco trabajo|buscando empleo|buscando trabajo)\b")


def motivo(titulo, enlace, fuente=""):
    if NO_ES_OFERTA.search(normalizar.texto(titulo)):
        return "contenido que no es una oferta"
    if not enlaces.sirve(enlace):
        return "sin enlace de postulación válido"
    if "publicación" in fuente and not enlaces.es_linkedin(enlace):
        return "publicación pendiente de verificar"
    h = enlaces.host(enlace)
    if (h == "linkedin.com" or h.endswith(".linkedin.com")) and not enlaces.es_linkedin(enlace):
        return "LinkedIn sin enlace a una oferta formal"
    return ""
