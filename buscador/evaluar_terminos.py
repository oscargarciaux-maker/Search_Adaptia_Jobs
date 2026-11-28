"""P-14.2: evaluación SIN CONEXIÓN de los términos ampliados por un LLM, antes de encenderlos.

Sobre una bodega guardada (la pública de la rama `publicado`) y con perfiles y cargos FICTICIOS (los de
`buscador/medicion.py`), cuenta por cargo cuántas vacantes pasan cargo → lugar → idioma → requisitos con los términos
de siempre y con los ampliados (filtrados por `panel.terminos.filtrar_ampliados`, como en la búsqueda). Saca además una
muestra de las vacantes NUEVAS (las que solo entran por un término ampliado) para revisar a mano si son del oficio.

Mide solo lo que ya está en la bodega: los términos nuevos también se BUSCAN, así que traerían además avisos que hoy
no se capturan (eso no se puede medir sin conexión). No lee Supabase ni datos de clientes.

Uso: python -m buscador.evaluar_terminos --bodega <bodega.json.gz> --terminos <propuestas.json> [--salida eval.json]
`propuestas.json` = {"<nombre del cargo>": {"es": [...], "en": [...]}, ...} (lo que respondió el LLM a
`panel.terminos.prompt_ampliados`).
"""
import argparse
import gzip
import json
import random
from pathlib import Path

PASOS = ("cargo", "lugar", "idioma", "requisitos")
PAISES = ("MX", "CO", "AR", "ES")
IDIOMAS = (("es",), ("es", "en"))


def _leer(ruta):
    abrir = gzip.open if str(ruta).endswith(".gz") else open
    with abrir(ruta, "rt", encoding="utf-8") as f:
        return json.load(f)


def cargos(nombre, propuesta):
    """(cargo de siempre, cargo con los términos ampliados, términos que pasaron el filtro)."""
    from buscador.medicion import cargo_crudo
    from panel.contenido import cargo_operativo
    from panel.terminos import filtrar_ampliados
    crudo = cargo_crudo(nombre)
    base = cargo_operativo(crudo)
    extra = filtrar_ampliados(propuesta, base)
    return base, cargo_operativo(crudo, ampliados=extra), extra


def del_cargo(vacantes, cargo):
    """Ids cuyo título el cargo reconoce exacto o similar (`grado`, la regla de la selección)."""
    from panel.terminos import grado
    return {v["id"] for v in vacantes if grado(v["titulo"], cargo)[0] in ("exacto", "similar")}


class Perfiles:
    """Lugar, idioma y requisitos de cada perfil ficticio, calculados una sola vez por vacante (no dependen del cargo)."""

    def __init__(self, por_id, hoy):
        from buscador.medicion import perfil
        from panel.modelos import Perfil
        self.por_id, self.hoy = por_id, hoy
        self.perfiles = {f"{pais} {'+'.join(idiomas)} remoto": Perfil.model_validate(perfil(pais, idiomas=idiomas))
                         for idiomas in IDIOMAS for pais in PAISES}
        self._paso = {}

    def paso(self, clave, vid):
        """Último paso que pasa la vacante para ese perfil: 'cargo' (no pasa el lugar), 'lugar', 'idioma' o
        'requisitos'."""
        if (clave, vid) not in self._paso:
            from panel.afinidad import evaluar, lugar
            v, p = self.por_id[vid], self.perfiles[clave]
            if lugar(v, p)[0]:
                r = "cargo"
            elif v.get("idioma") not in p.idiomas:
                r = "lugar"
            else:
                r = "requisitos" if evaluar(v, p, self.hoy)["compatible"] else "idioma"
            self._paso[clave, vid] = r
        return self._paso[clave, vid]

    def embudo(self, clave, ids):
        n = {k: 0 for k in PASOS}
        pasa = set()
        for vid in ids:
            ultimo = PASOS.index(self.paso(clave, vid))
            for k in PASOS[:ultimo + 1]:
                n[k] += 1
            if ultimo == len(PASOS) - 1:
                pasa.add(vid)
        return n, pasa


def evaluar(vacantes, propuestas, hoy, muestra=30, semilla=14):
    vacantes = [v for v in vacantes if v.get("titulo") and v.get("tipo") != "post" and v.get("id")]
    por_id = {v["id"]: v for v in vacantes}
    perfiles = Perfiles(por_id, hoy)
    resultado, nuevas = {}, {}
    for nombre, propuesta in propuestas.items():
        base, ampliado, extra = cargos(nombre, propuesta)
        antes, despues = del_cargo(vacantes, base), del_cargo(vacantes, ampliado)
        fila = {"terminos_propuestos": sum(len(propuesta.get(k) or []) for k in ("es", "en")),
                "terminos_usados": len(extra), "perfiles": {}}
        for clave in perfiles.perfiles:
            (n_a, pasa_a), (n_d, pasa_d) = perfiles.embudo(clave, antes), perfiles.embudo(clave, despues)
            fila["perfiles"][clave] = {k: [n_a[k], n_d[k]] for k in PASOS}
            for vid in pasa_d - pasa_a:
                nuevas.setdefault(vid, set()).add(nombre)
        resultado[nombre] = fila
    azar = random.Random(semilla)
    elegidas = sorted(nuevas)
    azar.shuffle(elegidas)
    ejemplos = [{"cargo": sorted(nuevas[i])[0], "titulo": por_id[i]["titulo"][:90], "idioma": por_id[i].get("idioma"),
                 "fuente": por_id[i].get("fuente")} for i in elegidas[:muestra]]
    return {"cargos": resultado, "nuevas_total": len(nuevas), "muestra": ejemplos}


def _texto(r):
    lineas = []
    for nombre, fila in r["cargos"].items():
        lineas.append(f"{nombre}: {fila['terminos_usados']}/{fila['terminos_propuestos']} términos pasan el filtro")
        for clave, pasos in fila["perfiles"].items():
            lineas.append(f"  {clave:18} " + " · ".join(f"{k} {a}→{d}" for k, (a, d) in pasos.items()))
    lineas.append(f"Vacantes nuevas que pasan los requisitos (algún perfil): {r['nuevas_total']}")
    lineas += [f"  [{e['idioma']}] {e['titulo']}  ← {e['cargo']}" for e in r["muestra"]]
    return "\n".join(lineas)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--bodega", required=True)
    a.add_argument("--terminos", required=True)
    a.add_argument("--hoy", default=None)
    a.add_argument("--muestra", type=int, default=30)
    a.add_argument("--salida")
    args = a.parse_args(argv)
    from buscador import normalizar
    from datetime import date
    hoy = args.hoy or date.today().isoformat()
    with normalizar.con_memoria():
        r = evaluar(_leer(args.bodega), _leer(args.terminos), hoy, args.muestra)
    if args.salida:
        Path(args.salida).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(_texto(r))
    return r


if __name__ == "__main__":
    main()
