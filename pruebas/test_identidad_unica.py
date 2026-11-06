"""Regresiones de copias entre portales sin confundir otros cargos, países o requisiciones."""
from copy import deepcopy

from buscador import contrato, entrega, identidad, vacante

DESCRIPCION = ("Buscamos QA Engineer para probar una plataforma de comercio. Responsabilidades: diseñar escenarios, "
    "analizar incidentes, ejecutar regresiones, automatizar pruebas y documentar resultados. Colaborarás con producto, "
    "ingeniería, diseño y soporte durante cada entrega. Requerimos conocimientos de Cypress, Playwright, Python, SQL, "
    "Postman y API REST, además de comunicación escrita, planificación, revisión de criterios de aceptación y atención "
    "al detalle. Ofrecemos contrato indefinido, formación, seguro médico, vacaciones y un equipo distribuido. "
    "El trabajo permite desarrollar herramientas internas, supervisar integraciones y mejorar cobertura continua.")


def oferta(n, **op):
    return vacante.crear(op.get("titulo", "QA Engineer"), op.get("empresa", "Empresa A"),
        op.get("url", f"https://jobs.lever.co/a/{n}"), op.get("fuente", "Lever"),
        ubicacion=op.get("lugar", "Remote LATAM"), descripcion=op.get("texto", DESCRIPCION), hoy="2026-11-06")


def test_formatos_de_dos_portales_son_una_vacante_con_ambos_enlaces():
    a = oferta(1)
    b = oferta(2, url="https://www.linkedin.com/jobs/view/123456789/", fuente="LinkedIn",
               texto="<main><p>" + DESCRIPCION.replace(". ", ".</p><p>") + "</p></main>")
    unida, = vacante.juntar([a, b])
    assert unida["id"] == a["id"] and unida["enlace"] == b["enlace"]
    assert set(unida["_ids_fusionados"]) == {a["id"], b["id"]}
    fila, = contrato.filas(unida, solo_comprobados=False)
    assert fila["vacante_id"] == a["id"] and len(fila["enlaces_alternativos"]) == 2


def test_pequeno_aviso_de_origen_no_crea_otra_oportunidad():
    a, b = oferta(1), oferta(2, texto=DESCRIPCION + " Solicita aquí.")
    assert identidad.misma(a, b)
    assert len(vacante.juntar([a, b])) == 1


def test_no_unir_por_titulo_solo_ni_por_descripcion_recortada():
    a = oferta(1)
    for b in (oferta(2, texto="Otro equipo busca probar videojuegos y administrar infraestructura. " * 10),
              oferta(3, texto=DESCRIPCION[:220]), oferta(4, titulo="Junior QA Engineer"),
              oferta(5, lugar="Remote Spain"), oferta(6, empresa="Empresa B")):
        assert len(vacante.juntar([a, b])) == 2


def test_requisiciones_explicitas_distintas_se_conservan():
    a, b = oferta(1, texto=DESCRIPCION + " Requisition ID: ABC1234"), oferta(2, texto=DESCRIPCION + " Requisition ID: ABC1235")
    assert not identidad.misma(a, b)
    assert len(vacante.juntar([a, b])) == 2


def test_empresa_desconocida_no_es_identidad_comun():
    assert len(vacante.juntar([oferta(1, empresa="Empresa confidencial"), oferta(2, empresa="Empresa confidencial")])) == 2


def test_seleccion_no_cuenta_la_copia_ni_la_reelige_por_id_fusionado():
    a, b = oferta(1), oferta(2)
    configuracion = entrega.config()
    elegidas, reporte = entrega.elegir([a, b], {}, "2026-11-06", configuracion)
    assert len(elegidas["qa"]) == 1 and reporte["roles"]["qa"]["faltan"] == 19
    elegidas, _ = entrega.elegir([a, b], {b["id"]: "2026-11-05"}, "2026-11-06", configuracion)
    assert not elegidas["qa"]


def test_lote_historico_con_copias_informa_deficit_sin_reescribirlo():
    a, b = oferta(1), oferta(2)
    iniciales = {"qa": [(a, "exacto"), (b, "exacto")]}
    copia = deepcopy(iniciales)
    _, reporte = entrega.elegir([], {}, "2026-11-06", iniciales=iniciales)
    assert reporte["roles"]["qa"]["unicas"] == 1
    assert reporte["roles"]["qa"]["faltan"] == 19
    assert iniciales == copia
