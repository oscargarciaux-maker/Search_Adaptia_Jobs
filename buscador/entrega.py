"""Entrega diaria: `por_rol` vacantes nuevas por rol, lo más variadas posible, en el formato del contrato de datos v1.

Corre al final de la bodega. Elige de la bodega las vacantes que nunca se han entregado (trabajo/entregadas.json guarda
su huella y sus enlaces), las reparte por rol (datos/entrega.yaml) y, dentro de cada rol, va tomando la que menos se
parece a las ya elegidas: idioma, nivel, país, modalidad, fuente y empresa. Sube las filas a Supabase (supabase.py). La exportación automática CSV/Excel de la versión anterior queda desactivada
por defecto; la utilidad de exportación se conserva para usos explícitos.
"""
import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

from buscador import contrato, familias, normalizar

RAIZ = Path(__file__).resolve().parent.parent
GRADOS = familias.GRADOS            # exacto, similar, cercano
GRADO_CONTRATO = {"exacto": "exact", "similar": "similar", "cercano": "close"}


def config():
    return yaml.safe_load((RAIZ / "datos" / "entrega.yaml").read_text(encoding="utf-8"))


def huellas(v):
    """Claves con las que se reconoce una vacante ya entregada: su identidad estable y todos sus enlaces limpios."""
    return [v["id"]] + [contrato.url_limpia(u) for u in
                        [v.get("enlace"), v.get("enlace_directo"), *v.get("_enlaces", [])] if u]


def rol_de(v, roles):
    """(rol, grado) de la vacante: el rol con la coincidencia más fuerte; si empatan, el primero de la lista."""
    grados = {f["familia"]: f["coincidencia"] for f in v.get("familias", [])}
    titulo = normalizar.texto(v.get("titulo", ""))
    mejor = None
    for orden, rol in enumerate(roles):
        en_rol = [grados[f] for f in rol["familias"] if f in grados]
        if not en_rol:
            continue
        if rol.get("titulo") and not any(normalizar.contiene_frase(titulo, normalizar.texto(p)) for p in rol["titulo"]):
            continue
        grado = min(en_rol, key=GRADOS.index)
        clave = (GRADOS.index(grado), orden)
        if mejor is None or clave < mejor[0]:
            mejor = (clave, rol, grado)
    return (mejor[1], mejor[2]) if mejor else (None, None)


def _rasgos(v):
    fila = contrato.filas(v)[0] if v.get("enlace") or v.get("enlace_directo") else {}
    return {
        "idioma": v.get("idioma", ""),
        "nivel": fila.get("seniority") or "sin nivel",
        "pais": fila.get("office_country") or "|".join(sorted(v.get("paises", []))) or "sin dato",
        "modo": fila.get("work_mode") or "sin dato",
        "fuente": v.get("fuente", ""),
        "empresa": normalizar.empresa(v.get("empresa", "")),
        "con_texto": len(v.get("_descripcion", "")) >= 200,
    }


def prioridad_remota(v):
    if v.get("confianza_pais") == "baja":
        return 3
    if v.get("modalidad") == "remoto":
        return 0 if v.get("confianza_pais") == "alta" and len(v.get("paises", [])) > 1 else 1
    return 2


def variadas(candidatas, cuantas, max_por_empresa, hoy, preferir_remotas=False):
    """Toma `cuantas` candidatas [(vacante, grado)] una por una: en cada paso la de menor costo, donde el costo sube con
    lo que ya se repite (idioma, nivel, país, modalidad, fuente), con un grado más débil, sin descripción o más vieja."""
    elegidas, conteo = [], {k: Counter() for k in ("idioma", "nivel", "pais", "modo", "fuente", "empresa")}
    resto = [(v, g, _rasgos(v)) for v, g in candidatas]
    hoy_d = date.fromisoformat(hoy)
    while resto and len(elegidas) < cuantas:
        def costo(item):
            v, g, r = item
            dias = (hoy_d - date.fromisoformat((v.get("fecha_publicacion") or v.get("visto_primera_vez") or hoy)[:10])).days
            return (3.0 * conteo["idioma"][r["idioma"]] + 2.0 * conteo["nivel"][r["nivel"]] +
                    1.5 * conteo["pais"][r["pais"]] + 1.0 * conteo["modo"][r["modo"]] +
                    1.0 * conteo["fuente"][r["fuente"]] + 4.0 * GRADOS.index(g) +
                    (0 if r["con_texto"] else 4.0) + 0.3 * max(0, dias))
        resto = [x for x in resto if conteo["empresa"][x[2]["empresa"]] < max_por_empresa]
        if not resto:
            break
        mejor = min(resto, key=lambda item: (prioridad_remota(item[0]) if preferir_remotas else 0, costo(item)))
        resto.remove(mejor)
        v, g, r = mejor
        elegidas.append((v, g))
        for k in conteo:
            conteo[k][r[k]] += 1
    return elegidas


def elegir(vacantes, entregadas, hoy, cfg=None):
    """{rol_id: [(vacante, grado)]} con las vacantes nuevas de cada rol, y un resumen por rol."""
    cfg = cfg or config()
    roles = cfg["roles"]
    desde = (date.fromisoformat(hoy) - timedelta(days=cfg.get("dias_frescura", 14))).isoformat()
    por_rol, motivos = {r["id"]: [] for r in roles}, Counter()
    descartes_rol = {r["id"]: Counter() for r in roles}
    for v in vacantes:
        rol, grado = rol_de(v, roles)
        if not rol:
            continue
        if any(h in entregadas for h in huellas(v)):
            motivos["ya entregada"] += 1
            descartes_rol[rol["id"]]["ya entregada"] += 1
            continue
        if (v.get("visto_primera_vez") or "") < desde:
            motivos["vista hace más de %d días" % cfg.get("dias_frescura", 14)] += 1
            descartes_rol[rol["id"]]["fuera de frescura"] += 1
            continue
        motivo = contrato.entregable(v, tuple(cfg.get("idiomas", ["es", "en"])))
        if motivo:
            motivos[motivo] += 1
            descartes_rol[rol["id"]][motivo] += 1
            continue
        por_rol[rol["id"]].append((v, grado))
    salida, resumen = {}, {}
    for rol in roles:
        candidatas = por_rol[rol["id"]]
        salida[rol["id"]] = variadas(candidatas, cfg["por_rol"], cfg.get("max_por_empresa", 2), hoy,
                                      cfg.get("preferir_remotas", False))
        elegidas = [v for v, _ in salida[rol["id"]]]
        empresas = Counter(normalizar.empresa(v["empresa"]) for v, _ in candidatas)
        capacidad = sum(min(n, cfg.get("max_por_empresa", 2)) for n in empresas.values())
        resumen[rol["id"]] = {
            "nombre": rol["nombre"], "candidatas": len(candidatas), "entregadas": len(elegidas),
            "faltan": max(0, cfg["por_rol"] - len(elegidas)),
            "idiomas": dict(Counter(v["idioma"] for v in elegidas)),
            "niveles": dict(Counter(contrato.seniority(v["titulo"]) or "sin nivel" for v in elegidas)),
            "paises": dict(Counter((v["paises"][0] if len(v["paises"]) == 1 else "varios") for v in elegidas)),
            "remotas": sum(v["modalidad"] == "remoto" for v in elegidas),
            "remotas_amplias": sum(prioridad_remota(v) == 0 for v in elegidas),
            "descartadas": dict(descartes_rol[rol["id"]]),
            "empresas_disponibles": len(empresas),
            "capacidad_con_tope_empresa": capacidad,
            "limitadas_por_empresa": len(candidatas) - capacidad,
            "reserva_sin_entregar": len(candidatas) - len(elegidas),
        }
    return salida, {"roles": resumen, "descartadas": dict(motivos)}


def filas_de(elegidas, roles, hoy, capturada):
    nombres = {r["id"]: r["nombre"] for r in roles}
    filas, ids = [], set()
    for rol_id, lista in elegidas.items():
        for v, grado in lista:
            for fila in contrato.filas(v, nombres[rol_id], GRADO_CONTRATO.get(grado, grado), hoy, capturada):
                if fila["external_id"] not in ids:   # dos vacantes con el mismo enlace directo: una sola fila
                    ids.add(fila["external_id"])
                    filas.append(fila)
    return filas


def registrar_medicion(historial, resumen, hoy, dias=30):
    """Serie corta para medir continuidad real; no predice ofertas futuras ni almacena descripciones."""
    historial[hoy] = {
        "fecha": hoy, "meta_cumplida": resumen["meta_cumplida"],
        "pendientes_supabase": (resumen.get("supabase") or {}).get("pendientes", 0),
        "roles": {rid: {k: r[k] for k in ("candidatas", "entregadas", "faltan", "reserva_sin_entregar")}
                  for rid, r in resumen["roles"].items()},
    }
    desde = (date.fromisoformat(hoy) - timedelta(days=dias - 1)).isoformat()
    for dia in [dia for dia in historial if dia < desde]:
        del historial[dia]
    return [historial[dia] for dia in sorted(historial) if dia <= hoy][-7:]


def escribir(carpeta, hoy, filas, dias_guardados=60):
    """datos/entregas/<hoy>.csv y .xlsx, y ultima.csv/.xlsx; borra las de más de `dias_guardados` días."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    columnas = contrato.COLUMNAS + contrato.EXTRAS
    for nombre in (f"{hoy}.csv", "ultima.csv"):
        with open(carpeta / nombre, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columnas)
            w.writeheader()
            w.writerows(filas)
    try:
        from openpyxl import Workbook
        libro = Workbook()
        hoja = libro.active
        hoja.title = "ofertas"
        hoja.append(columnas)
        for fila in filas:
            hoja.append([fila[c] if c != "description_full" else fila[c][:32000] for c in columnas])
        hoja.freeze_panes = "A2"
        for nombre in (f"{hoy}.xlsx", "ultima.xlsx"):
            libro.save(carpeta / nombre)
    except ImportError:
        pass
    limite = (date.fromisoformat(hoy) - timedelta(days=dias_guardados)).isoformat()
    for archivo in carpeta.glob("20*-*-*.*"):
        if archivo.stem < limite:
            archivo.unlink()


def correr(vacantes, entregadas, hoy, capturada, carpeta, subir=None, pendientes=None, persistir=None,
           exportar=None):
    """Elige, escribe y sube. `entregadas` (dict huella → fecha) se actualiza con lo entregado hoy.
    Devuelve el resumen para salud.json."""
    cfg = config()
    elegidas, resumen = elegir(vacantes, entregadas, hoy, cfg)
    filas = filas_de(elegidas, cfg["roles"], hoy, capturada)
    generar_archivos = cfg.get("exportar_archivos", False) if exportar is None else exportar
    if generar_archivos:
        escribir(carpeta, hoy, filas)
    pendientes = pendientes if pendientes is not None else {}
    for fila in filas:
        pendientes.setdefault(fila["external_id"], fila)
    if persistir:
        persistir(pendientes)  # diario durable antes de cualquier petición
    for lista in elegidas.values():
        for v, _ in lista:
            for h in huellas(v):
                entregadas[h] = hoy
    # Se olvida lo entregado hace más de 180 días (para entonces la vacante ya se borró de la bodega)
    limite = (date.fromisoformat(hoy) - timedelta(days=180)).isoformat()
    for h in [h for h, f in entregadas.items() if f < limite]:
        del entregadas[h]
    resumen["vacantes"] = sum(len(x) for x in elegidas.values())
    resumen["filas"] = len(filas)
    resumen["archivos"] = bool(generar_archivos)
    resumen["meta_por_rol"] = cfg["por_rol"]
    resumen["meta_cumplida"] = all(r["faltan"] == 0 for r in resumen["roles"].values())
    if subir is not None:
        resultado = dict(subir(list(pendientes.values())))
        for external_id in resultado.pop("confirmadas", []):
            pendientes.pop(external_id, None)
        resultado["pendientes"] = len(pendientes)
        resumen["supabase"] = resultado
        if persistir:
            persistir(pendientes)
    return resumen
