"""Prueba de viabilidad de Apify (sección 8.2, decisión de Oscar del 28 nov): ¿vale la pena comprar Starter?

La cuenta gratis da USD 5 al mes y Apify la BLOQUEA al agotarlos. Se gastan al ritmo de Starter (`ritmo_diario_usd`
en datos/config.yaml, 19/30 ≈ 0,63 al día) y se mide, por día y acumulado en el mes, en `trabajo/apify_medicion.json`:

- `usd_reservado`: lo que se apartó del crédito antes de llamar a Apify (conservador: es lo que cuenta para el tope).
- `usd_reportado`: lo que Apify informó que costó cada ejecución (`usageTotalUsd`).
- `avisos`: avisos formales y posts que trajo Apify.
- `seleccion`: vacantes de la selección del día que SOLO encontró Apify (si otra fuente también la tenía, no cuenta).
- `utiles`: de esas, las que llegaron a algún cliente (asignadas a un perfil que no es de Comunidad).
- `perfiles_a_5`: perfiles que llegan al mínimo de 5 y sin las de Apify se quedaban cortos.
- `usd_por_vacante_util`: USD reportados del mes ÷ vacantes útiles del mes (con lo reservado si Apify no informó).

Todo es agregado: ni nombres, ni perfiles, ni cargos, ni IDs de vacantes. El archivo va a la rama pública `publicado`
y los registros de Actions solo muestran estos totales.
"""
import json
from pathlib import Path

ARCHIVO = "apify_medicion.json"
# Fuentes de la salud de la corrida que gastan crédito de Apify.
SALUD_APIFY = ("LinkedIn (Apify)", "Publicaciones LinkedIn (Apify)", "LinkedIn (Apify) rescate", "LinkedIn (Apify) posts")
# Una vacante cuenta como «de Apify» si todas sus fuentes son de Apify (formales, ofertas desde el feed o posts).
FUENTES_APIFY = {"LinkedIn (Apify)", "LinkedIn (oferta desde feed)", "LinkedIn (publicación)", "LinkedIn (post)"}
DE_CORRIDA = ("usd_reservado", "usd_reportado", "avisos", "corridas")
DE_ASIGNACION = ("seleccion", "utiles", "perfiles_a_5")


def solo_apify(v):
    fuentes = set((v or {}).get("fuentes") or [(v or {}).get("fuente")]) - {None, ""}
    return bool(fuentes) and fuentes <= FUENTES_APIFY


def de_corrida(salud):
    """Gasto y avisos de Apify de una corrida, desde su salud por fuente."""
    total = dict.fromkeys(("usd_reservado", "usd_reportado", "avisos"), 0)
    agotado = False
    for nombre in SALUD_APIFY:
        s = (salud or {}).get(nombre) or {}
        total["usd_reservado"] += float(s.get("usd_reservado") or 0)
        total["usd_reportado"] += float(s.get("usd_reportado") or 0)
        total["avisos"] += int(s.get("avisos") or 0) + int(s.get("fichas_formales") or 0) + int(s.get("posts") or 0)
        agotado = agotado or bool(s.get("credito_agotado"))
    total["usd_reservado"] = round(total["usd_reservado"], 6)
    total["usd_reportado"] = round(total["usd_reportado"], 6)
    return dict(total, credito_agotado=agotado)


def leer(trabajo, hoy):
    try:
        datos = json.loads((Path(trabajo) / ARCHIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    if not isinstance(datos, dict) or datos.get("mes") != hoy[:7] or not isinstance(datos.get("por_dia"), dict):
        datos = {"mes": hoy[:7], "por_dia": {}}  # mes nuevo: se mide de cero, como el crédito
    return datos


def _guardar(trabajo, datos):
    ruta = Path(trabajo) / ARCHIVO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def anotar_corrida(trabajo, hoy, corrida):
    """Suma el gasto y los avisos de esta corrida al día (varias corridas al día se suman)."""
    datos = leer(trabajo, hoy)
    dia = datos["por_dia"].setdefault(hoy, {})
    for k in ("usd_reservado", "usd_reportado", "avisos"):
        dia[k] = round(dia.get(k, 0) + corrida.get(k, 0), 6)
    dia["corridas"] = dia.get("corridas", 0) + 1
    _guardar(trabajo, datos)
    return datos


def anotar_asignacion(trabajo, hoy, conteos):
    """Lo que Apify aportó a lo asignado hoy. Cada pasada recuenta todo el día, así que se queda el mayor."""
    datos = leer(trabajo, hoy)
    dia = datos["por_dia"].setdefault(hoy, {})
    for k in DE_ASIGNACION:
        dia[k] = max(int(dia.get(k, 0)), int(conteos.get(k, 0)))
    _guardar(trabajo, datos)
    return datos


def del_mes(datos):
    dias = (datos or {}).get("por_dia") or {}
    total = {k: round(sum(float(d.get(k, 0)) for d in dias.values()), 6) for k in DE_CORRIDA + DE_ASIGNACION}
    for k in ("avisos", "corridas") + DE_ASIGNACION:
        total[k] = int(total[k])
    gasto = total["usd_reportado"] or total["usd_reservado"]
    total["usd_por_vacante_util"] = round(gasto / total["utiles"], 4) if total["utiles"] else None
    total["dias"] = len(dias)
    return total


def contar_asignacion(filas, snapshot_de, perfiles, de_comunidad, minimo, ya_hoy=None, vacante_de=None):
    """Conteos agregados de una pasada de `panel.ejecutor.registrar`. `filas`: asignaciones de esta pasada;
    `snapshot_de`: {vacante_id: vacante} de la selección del día; `perfiles`: los activos; `ya_hoy`: {perfil_id: [ids]}
    de pasadas anteriores de hoy; `vacante_de(id)`: la vacante de la bodega, para saber de qué fuente es."""
    vacante_de = vacante_de or snapshot_de.get
    # Los posts de LinkedIn los trae solo Apify; su fila lo dice en la explicación y no están en la bodega.
    es_apify = {f["vacante_id"]: True for f in filas
                if any(isinstance(e, dict) and e.get("tipo") == "post" for e in f.get("explicacion") or [])}

    def apify(vid):
        if vid not in es_apify:
            es_apify[vid] = solo_apify(snapshot_de.get(vid) or vacante_de(vid))
        return es_apify[vid]

    por_perfil = {}
    for f in filas:
        por_perfil.setdefault(f["perfil_id"], set()).add(f["vacante_id"])
    for pid, ids in (ya_hoy or {}).items():
        por_perfil.setdefault(str(pid), set()).update(ids)
    reales = {str(p.id) for p in perfiles if not de_comunidad(p)}
    utiles = {vid for pid, ids in por_perfil.items() if pid in reales for vid in ids if apify(vid)}
    a_5 = sum(1 for pid, ids in por_perfil.items() if pid in reales and len(ids) >= minimo
              and len([v for v in ids if not apify(v)]) < minimo)
    return {"seleccion": sum(1 for vid in snapshot_de if apify(vid)), "utiles": len(utiles), "perfiles_a_5": a_5}


def avisos_de_gasto(presupuesto, tope_mensual):
    """Avisos (no averías): el crédito se acabó o lo reservado del mes pasó del 80 % del tope."""
    from buscador.apify import AVISO_GASTO
    salida = []
    if (presupuesto or {}).get("bloqueado"):
        salida.append("Apify sin crédito en el plan: la fuente queda detenida hasta el mes siguiente")
    usado = round(sum(((presupuesto or {}).get("reservas") or {}).values()), 6)
    if tope_mensual and usado > AVISO_GASTO * float(tope_mensual):
        salida.append(f"Apify: lo reservado este mes (USD {usado:.2f}) pasa del {AVISO_GASTO * 100:.0f} % del tope "
                      f"(USD {float(tope_mensual):.2f})")
    return salida


def linea(datos=None, totales=None):
    """Una línea para los registros públicos: solo totales del mes (de `datos` o ya calculados en `totales`)."""
    t = totales or del_mes(datos)
    costo = "sin dato" if t["usd_por_vacante_util"] is None else f"USD {t['usd_por_vacante_util']:.3f}"
    return (f"Apify en el mes ({t['dias']} días): reservado USD {t['usd_reservado']:.2f}, reportado USD "
            f"{t['usd_reportado']:.2f}, avisos {t['avisos']}, en la selección {t['seleccion']}, útiles {t['utiles']}, "
            f"perfiles que llegan a 5 gracias a Apify {t['perfiles_a_5']}, costo por vacante útil {costo}")
