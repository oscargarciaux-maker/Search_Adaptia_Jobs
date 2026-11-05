"""Prueba explícita de una oferta LinkedIn con cargo máximo de USD 0,01, sin escribir en Supabase."""
import json
import os

from buscador import bodega, enlaces
from buscador.apify import ejecutar
from buscador.fuentes import linkedin_apify
from buscador.http import Cliente


def main():
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        raise SystemExit("Falta APIFY_TOKEN en los secretos de GitHub.")
    cfg = bodega.config()["apify"]
    cuerpo = linkedin_apify.entrada(cfg["actor_linkedin"], ["ux designer"],
                                   {"location": "Latin America", "f_WT": "2"}, 30, 1)
    items, stats = ejecutar(Cliente(), cfg["actor_linkedin"], cuerpo, token, 0.01, max_items=1,
                            build=cfg["build_linkedin"], limite_segundos=180)
    print(json.dumps({"ejecucion": stats, "registros": len(items)}, ensure_ascii=False))
    if stats.get("error") or not items:
        raise SystemExit("No se pudo verificar una oferta real de Apify. No se escribió en Supabase.")
    v = linkedin_apify.normalizar_item(items[0])
    ok = bool(v["titulo"] and v["empresa"] and enlaces.es_linkedin(v["enlace"]) and len(v["descripcion"]) >= 200)
    print(json.dumps({"oferta_formal": ok, "titulo": v["titulo"], "ubicacion": v["ubicacion"],
                      "fecha": v["fecha"], "caracteres_descripcion": len(v["descripcion"])}, ensure_ascii=False))
    if not ok:
        raise SystemExit("Apify no devolvió una ficha de empleo completa.")


if __name__ == "__main__":
    main()
