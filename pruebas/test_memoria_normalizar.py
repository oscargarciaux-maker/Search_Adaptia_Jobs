"""P-12.2: la memoria de la normalización y el mínimo de años solo cambian la velocidad, nunca el resultado."""
import re
import unicodedata

import pytest

from buscador import bodega, contrato, normalizar


def _sin_tildes_original(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")


def _texto_original(texto_crudo):
    t = _sin_tildes_original(texto_crudo).lower()
    t = re.sub(r"[^a-z0-9+#./ ]+", " ", t)
    t = re.sub(r"(?<![a-z0-9])\.|\.(?![a-z0-9])", " ", t)
    return re.sub(r"\s+", " ", t).strip()


ENTRADAS = [None, "", 0, 0.0, False, 12, 3.5, True, "Diseñadora UX/UI Sr.", "São Paulo — Híbrido",
            "árbol ya descompuesto", "Ç#, .NET y node.js", "  espacios   raros\t\n", "ÅÉÎÕÜ ñ ß ø",
            "Ｆｕｌｌ ｗｉｄｔｈ", "emoji 🚀 y «comillas»", "x" * 20000 + "ó"]


@pytest.mark.parametrize("entrada", ENTRADAS)
def test_mismo_resultado_que_sin_memoria(entrada):
    normalizar.vaciar_cache()
    for _ in range(2):  # la segunda vez sale de la memoria
        assert normalizar.sin_tildes(entrada) == _sin_tildes_original(entrada)
        assert normalizar.texto(entrada) == _texto_original(entrada)


def test_memoria_acotada_y_se_vacia():
    normalizar.vaciar_cache()
    normalizar.texto("Diseñador de producto")
    assert normalizar._texto.cache_info().currsize == 1
    assert normalizar._sin_tildes.cache_info().currsize == 1
    assert normalizar._texto.cache_info().maxsize == normalizar._sin_tildes.cache_info().maxsize == normalizar.MAX_CACHE
    normalizar.vaciar_cache()
    assert normalizar._texto.cache_info().currsize == normalizar._sin_tildes.cache_info().currsize == 0


def test_bodega_vacia_la_memoria_aunque_falle(monkeypatch):
    def falla(*a, **k):
        normalizar.texto("algo que queda en la memoria")
        raise RuntimeError("fallo de prueba")

    monkeypatch.setattr(bodega, "_correr", falla)
    with pytest.raises(RuntimeError):
        bodega.correr("/no/se/usa", prueba=True)
    assert normalizar._texto.cache_info().currsize == 0


DESCRIPCIONES = ["", None, "Buscamos 3-5 años de experiencia en diseño.", "Requires 2 to 4 years of experience",
                 "3 a 50 años de experiencia", "5-3 años de experiencia", "Entre 4 y 6 años en ventas",
                 "1–2 años de experiência", "texto sin años", "3-5 años " + "x" * 90 + " experiencia"]


@pytest.mark.parametrize("minimo", [None, 0, 1, 2, 3, 4, 5, 20, 39, 40, 41, -1])
@pytest.mark.parametrize("descripcion", DESCRIPCIONES)
def test_minimo_de_anos_no_depende_de_la_descripcion(descripcion, minimo):
    """`afinidad.evaluar` usa solo el mínimo: calcularlo sin la descripción da exactamente lo mismo (valor y tipo)."""
    con, sin = contrato.anos(descripcion, minimo)[0], contrato.anos("", minimo)[0]
    assert con == sin and type(con) is type(sin)


def test_recortar_antes_de_normalizar_cambiaria_el_resultado():
    """Por qué no se recorta a 12.000 caracteres antes de quitar tildes: un texto con tildes ya separadas se acorta al
    normalizar, y cortarlo antes dejaría fuera parte de lo que hoy se lee."""
    texto = "á" * 12000
    assert normalizar.sin_tildes(texto)[:12000] != normalizar.sin_tildes(texto[:12000])[:12000]
