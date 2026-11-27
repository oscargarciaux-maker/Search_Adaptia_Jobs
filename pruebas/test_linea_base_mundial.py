"""Sección 7: la línea base del objetivo mundial corre sin la bodega real y el control (h) no cambia.

Bodega mínima FICTICIA (empresas y enlaces inventados), armada con `vacante.crear` como la crearía una búsqueda."""
import gzip
import json

import pytest

from buscador import medicion, vacante

HOY = "2026-11-27"
EN = ("We are hiring a designer to own end-to-end product design for our platform. You will run user research, "
      "build prototypes in Figma, work with engineers and product managers, and ship features used by many people "
      "every day. Strong portfolio required. ")
ES = ("Buscamos una persona para diseñar la experiencia de nuestros productos digitales. Harás investigación con "
      "usuarios, prototipos en Figma y trabajarás con el equipo de ingeniería y de producto para lanzar funciones "
      "que usan miles de personas cada día. ")


def _vacantes():
    filas = [("Product Designer", "Remote - Worldwide", EN, True), ("Product Designer", "Remote - Brazil", EN, True),
             ("Product Designer", "São Paulo, Brazil", EN, False), ("Product Designer", "Berlin, Germany (Hybrid)", EN, False),
             ("Diseñador de Producto", "Remoto - Colombia", ES, True), ("Diseñador de Producto", "Remoto - LATAM", ES, True),
             ("Product Designer", "Remote - Colombia", EN, True), ("Product Designer", "Remote - India", EN, True),
             ("Diseñador de Producto", "Remoto - Estados Unidos", ES, True)]
    salida = []
    for i, (titulo, lugar, texto, remoto) in enumerate(filas):
        v = vacante.crear(titulo, f"Empresa Ficticia {i}", f"https://boards.greenhouse.io/ficticia{i}/jobs/{1000 + i}",
                          "Greenhouse", ubicacion=lugar, descripcion=texto * 2, fecha=HOY, remoto=remoto, hoy=HOY)
        assert v is not None
        salida.append(v)
    return salida


@pytest.fixture(scope="module")
def texto():
    return json.dumps(_vacantes(), ensure_ascii=False)


@pytest.fixture(scope="module")
def medida(texto):
    return medicion.medir_mundial(texto, HOY)


def test_corren_todos_los_escenarios_y_solo_hay_conteos(medida):
    assert set(medida["escenarios"]) == set("abcdefgh")
    for r in medida["escenarios"].values():
        etapas = r["etapas"]
        assert list(etapas) == list(medicion.ETAPAS)
        assert all(isinstance(n, int) and n >= 0 for n in etapas.values())
        # hasta «afinidad» cada etapa recorta a la anterior («panel» puede sumar ampliaciones)
        hasta_afinidad = [etapas[k] for k in medicion.ETAPAS[:4]]
        assert hasta_afinidad == sorted(hasta_afinidad, reverse=True)
    texto = json.dumps(medida, ensure_ascii=False)
    assert "Ficticia" not in texto and "greenhouse" not in texto  # ni empresas ni enlaces


def test_el_objetivo_reconoce_lo_que_pide_cada_escenario(medida):
    e = medida["escenarios"]
    assert e["a"]["etapas"]["objetivo"] >= 2  # mundial + Brasil
    assert e["b"]["etapas"]["objetivo"] >= 1 and e["e"]["etapas"]["objetivo"] >= 1
    assert e["h"]["etapas"]["objetivo"] >= 1


def test_comparar_contra_si_misma_no_falla(medida):
    lineas, cambio = medicion.comparar(medida, medida)
    assert not cambio
    assert all(any(linea.startswith(f"| {clave} ") for linea in lineas) for clave in medicion.ESCENARIOS)


def test_comparar_falla_si_cambia_el_control(medida):
    otra = json.loads(json.dumps(medida))
    otra["escenarios"]["h"]["etapas"]["panel"] += 1
    assert medicion.comparar(medida, otra)[1]
    otra = json.loads(json.dumps(medida))
    otra["escenarios"]["a"]["etapas"]["panel"] += 1  # un escenario a–g sí puede cambiar
    otra["escenarios"]["h"]["admitidas"] += 50  # y el volumen total (7.2 puede subirlo a propósito)
    otra["escenarios"]["h"]["segundos"]["limpiar"] += 9.5
    assert not medicion.comparar(medida, otra)[1]


def test_linea_comandos_guarda_y_compara(tmp_path, texto, capsys):
    ruta = tmp_path / "bodega.json.gz"
    with gzip.open(ruta, "wt", encoding="utf-8") as f:
        f.write(texto)
    base = tmp_path / "base.json"
    assert medicion.main(["--bodega", str(ruta), "--mundial", "--guardar", str(base), "--hoy", HOY]) == 0
    assert json.loads(base.read_text(encoding="utf-8"))["bodega"]["sha256"] == medicion._sha256(ruta)
    assert medicion.main(["--bodega", str(ruta), "--comparar", str(base)]) == 0
    assert medicion.main(["--bodega", str(ruta), "--comparar", str(base), "--hoy", "2026-11-01"]) == 2
    datos = json.loads(base.read_text(encoding="utf-8"))
    datos["escenarios"]["h"]["etapas"]["afinidad"] += 1
    base.write_text(json.dumps(datos), encoding="utf-8")
    assert medicion.main(["--bodega", str(ruta), "--comparar", str(base)]) == 1
    datos["bodega"]["sha256"] = "0" * 64
    base.write_text(json.dumps(datos), encoding="utf-8")
    assert medicion.main(["--bodega", str(ruta), "--comparar", str(base)]) == 2
    capsys.readouterr()


def test_la_linea_base_guardada_tiene_solo_conteos():
    from pathlib import Path
    ruta = Path(__file__).parent / "datos" / "linea_base_mundial.json"
    if not ruta.exists():
        pytest.skip("aún no hay línea base guardada")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert len(datos["bodega"]["sha256"]) == 64 and len(datos["bodega"]["commit"]) == 40
    # si falla, cambió el mapa de cargos: las comparaciones mezclarían ese cambio con los de la sección 7
    assert datos["huella_cargos"] == medicion.huella_de_cargos(medicion.cargos_del_panel())
    assert set(datos["escenarios"]) == set(medicion.ESCENARIOS)
    permitidas = {"nombre"}  # el nombre del escenario ficticio; todo lo demás son números
    def numeros(x, clave=""):
        if isinstance(x, dict):
            return all(numeros(v, k) for k, v in x.items())
        return clave in permitidas or isinstance(x, (int, float))
    assert numeros(datos["escenarios"]) and numeros(datos["conjunto"])
