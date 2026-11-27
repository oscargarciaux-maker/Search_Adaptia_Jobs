> Histórico. Vigente: docs/CONTRATO_VIGENTE.md

# Contrato de datos v33: el nivel de inglés ordena, no descarta

**Fecha:** 16 de noviembre de 2026. **Corrige:** el punto 1 de [v32](CONTRATO_DATOS_v32.md). **Sin SQL ni IA.**

Decisión de Oscar: si el perfil acepta avisos en inglés y el aviso está en inglés, ya se sabe que hay inglés. El
nivel (B1, B2, C1…) sirve para entregarle primero los mejores matches, no para descartar.

- Si el aviso exige más nivel que el del perfil, llega igual. Lleva la etiqueta «Pide inglés C1» y va después de las
  que encajan en todo, como en [v27](CONTRATO_DATOS_v27.md).
- Lo que descarta sigue igual: la ubicación (filas de v30: país o ciudad con su modalidad), el idioma del aviso y las
  reglas del sistema (abierta, enlace, sin repetir, fecha confirmada, 30 días).

Prueba: `pruebas/panel/test_control.py::test_v33_ingles_exigido_mayor_ordena_y_deja_etiqueta`.
