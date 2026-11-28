"""P-12.2: la memoria de la normalización y el mínimo de años solo cambian la velocidad, nunca el resultado."""
import re
import unicodedata

import pytest

from buscador import bodega, contrato, normalizar


# Foto de las funciones tal como eran antes de P-12.2, para comprobar que la memoria no cambia nada. Si algún día se
# cambia la regla de normalización a propósito, se actualiza aquí también.
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
def test_mismo_resultado_con_y_sin_memoria(entrada):
    assert normalizar.sin_tildes(entrada) == _sin_tildes_original(entrada)
    assert normalizar.texto(entrada) == _texto_original(entrada)
    with normalizar.con_memoria():
        for _ in range(2):  # la segunda vez sale de la memoria
            assert normalizar.sin_tildes(entrada) == _sin_tildes_original(entrada)
            assert normalizar.texto(entrada) == _texto_original(entrada)


def _guardadas():
    return normalizar._texto.cache_info().currsize + normalizar._sin_tildes.cache_info().currsize


def test_sin_busqueda_no_retiene_nada():
    """El servidor del panel normaliza descripciones fuera de una búsqueda: ahí no se guarda nada en memoria."""
    normalizar.texto("Diseñador de producto con descripción larga")
    assert _guardadas() == 0


def test_memoria_acotada_y_se_vacia_al_salir():
    assert normalizar._texto.cache_info().maxsize == normalizar._sin_tildes.cache_info().maxsize == normalizar.MAX_CACHE
    with normalizar.con_memoria():
        normalizar.texto("Diseñador de producto")
        with normalizar.con_memoria():  # anidado: el de dentro no vacía
            normalizar.texto("Analista")
        assert _guardadas() == 4
    assert _guardadas() == 0
    assert normalizar._memoria_activa is False


def test_bodega_usa_la_memoria_y_la_vacia_aunque_falle(monkeypatch):
    vista = []

    def falla(*a, **k):
        normalizar.texto("algo que queda en la memoria")
        vista.append(_guardadas())
        raise RuntimeError("fallo de prueba")

    monkeypatch.setattr(bodega, "_correr", falla)
    with pytest.raises(RuntimeError):
        bodega.correr("/no/se/usa", prueba=True)
    assert vista == [2] and _guardadas() == 0 and normalizar._memoria_activa is False


DESCRIPCIONES = ["", None, "Buscamos 3-5 años de experiencia en diseño.", "Requires 2 to 4 years of experience",
                 "3 a 50 años de experiencia", "5-3 años de experiencia", "Entre 4 y 6 años en ventas",
                 "1–2 años de experiência", "texto sin años", "3-5 años " + "x" * 90 + " experiencia"]


@pytest.mark.parametrize("minimo", [None, 0, 1, 2, 3, 4, 5, 20, 39, 40, 41, -1])
@pytest.mark.parametrize("descripcion", DESCRIPCIONES)
def test_minimo_de_anos_no_depende_de_la_descripcion(descripcion, minimo):
    """`afinidad` usa solo el mínimo: sin la descripción da exactamente lo mismo (valor y tipo). `anos_min` siempre es
    entero o None (`etiquetas.anos_min`)."""
    con, sin = contrato.anos(descripcion, minimo)[0], contrato.anos_minimos(minimo)
    assert con == sin and type(con) is type(sin)


def test_recortar_antes_de_normalizar_cambiaria_el_resultado():
    """Por qué no se recorta a 12.000 caracteres antes de quitar tildes: un texto con tildes ya separadas se acorta al
    normalizar, y cortarlo antes dejaría fuera parte de lo que hoy se lee."""
    texto = "á" * 12000
    assert normalizar.sin_tildes(texto)[:12000] != normalizar.sin_tildes(texto[:12000])[:12000]
