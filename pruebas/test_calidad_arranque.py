"""Contenido ajeno a vacantes, exportación retirada y fallos visibles de la primera corrida."""
import base64
import json

import pytest

from buscador import bodega, calidad, contrato, entrega, supabase, vacante, validacion
from buscador.fuentes import publicaciones_apify

HOY = "2026-11-04"
TEXTO = "We are hiring a UX Designer to join our remote team in LATAM. Apply through our careers page. " * 5


def oferta():
    return vacante.crear("UX Designer", "Empresa", "https://jobs.lever.co/a/1", "Lever",
                         ubicacion="Remote - LATAM", descripcion=TEXTO, hoy=HOY)


@pytest.mark.parametrize("titulo", ["Webinar Product Designer", "Curso UX/UI", "Product Designer Open to Work"])
def test_contenido_no_laboral_no_aceptado(titulo):
    assert calidad.motivo(titulo, "https://jobs.lever.co/a/1")
    assert vacante.crear(titulo, "A", "https://jobs.lever.co/a/1", "Apify", descripcion=TEXTO) is None


@pytest.mark.parametrize("url", ["https://evil-linkedin.com/jobs/view/12345678", "javascript://linkedin.com/posts/123",
                                  "https://linkedin.com.evil.example/posts/123", "http://[incorrecto"])
def test_enlace_falso_no_aceptado_en_publicaciones(url):
    item = {"url": url, "text": TEXTO, "author": {"type": "company", "name": "Empresa"}}
    assert publicaciones_apify.a_vacante(item, {"diseno-producto-ux"})[0] is None


def test_publicacion_aunque_parezca_valida_no_cuenta_como_oferta_formal():
    item = {"url": "https://www.linkedin.com/posts/empresa_hiring-activity-1234567890123456789",
            "text": TEXTO, "author": {"type": "company", "name": "Empresa"}}
    class Cliente:
        def post_json(self, *args, **kwargs):
            return {"data": {"id": "run", "status": "SUCCEEDED", "defaultDatasetId": "dataset"}}
        def json(self, *args, **kwargs):
            return [item, dict(item, text="We are offering a UX course for remote designers.")]
    datos, salud = publicaciones_apify.buscar(Cliente(), "actor-ficticio", ["ux"], {"diseno-producto-ux"}, HOY,
                                              token="token-ficticio")
    assert datos == [] and salud["vacantes"] == 0
    assert salud["pendientes_revision"] == 1 and salud["descartadas"]
    v = dict(oferta(), fuente="LinkedIn (publicación)", enlace=item["url"])
    assert contrato.entregable(v) == "publicación pendiente de verificar"
    assert bodega.limpiar([v], [], HOY, 30, set(), set())[0] == []


def test_apify_con_formato_inesperado_falla_explicito():
    class Cliente:
        def post_json(self, *args, **kwargs):
            return {"error": "formato distinto"}
    datos, salud = publicaciones_apify.buscar(Cliente(), "actor", ["ux"], set(), HOY, token="ficticio")
    assert datos == [] and salud["error"]


def test_supabase_sin_excel_por_defecto_y_pendientes_conservados(tmp_path):
    pendientes = {}
    r = entrega.correr([oferta()], {}, HOY, HOY + "T12:00:00Z", tmp_path,
                       subir=lambda filas: {"omitida": "sin configurar"}, pendientes=pendientes)
    assert r["archivos"] is False and not list(tmp_path.glob("*.xlsx")) and not list(tmp_path.glob("*.csv"))
    assert pendientes and r["supabase"]["pendientes"] == 1


def test_preflight_impide_recoger_y_modificar_estado_si_no_hay_supabase(tmp_path, monkeypatch):
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    archivo = trabajo / "estado.json"
    archivo.write_text('{"anterior": true}')
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    def prohibido(*args, **kwargs):
        raise AssertionError("No debe recoger antes de comprobar Supabase")
    monkeypatch.setattr(bodega, "recoger", prohibido)
    with pytest.raises(RuntimeError, match="Supabase es obligatorio"):
        bodega.correr(tmp_path, hoy=HOY)
    assert archivo.read_text() == '{"anterior": true}'


@pytest.mark.parametrize("clave", ["sb_publishable_ficticia", "clave-desconocida"])
def test_preflight_rechaza_clave_publica_o_invalida(monkeypatch, clave):
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://ejemplo.supabase.co", clave))
    with pytest.raises(RuntimeError):
        supabase.exigir_conexion()


def test_preflight_acepta_service_role_y_comprueba_esquema(monkeypatch):
    parte = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
    monkeypatch.setattr(supabase, "credenciales", lambda: ("https://ejemplo.supabase.co", "cabecera." + parte + ".firma"))
    monkeypatch.setattr(supabase, "probar", lambda url, clave: (True, "esquema correcto"))
    assert supabase.exigir_conexion() == "esquema correcto"


def test_probar_pide_todas_las_columnas():
    llamadas = []
    class Sesion:
        def get(self, url, **kwargs):
            llamadas.append(url)
            return type("R", (), {"status_code": 200})()
    assert supabase.probar("https://ejemplo.supabase.co", "sb_secret_ficticia", Sesion())[0]
    assert "description_full" in llamadas[0] and "delivery_date" in llamadas[0]


def test_corrida_vacia_no_reescribe_estado_previo(tmp_path, monkeypatch):
    cfg = bodega.config()
    cfg["refuerzo"]["rondas"] = 0
    monkeypatch.setattr(bodega, "config", lambda: cfg)
    monkeypatch.setattr(supabase, "exigir_conexion", lambda: "correcto")
    monkeypatch.setattr(bodega, "recoger", lambda *a, **k: ([], set(), set(), {}))
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    (trabajo / "estado.json").write_text('{"anterior": true}')
    with pytest.raises(RuntimeError, match="catálogo válido"):
        bodega.correr(tmp_path, hoy=HOY)
    assert json.loads((trabajo / "estado.json").read_text()) == {"anterior": True}


def test_prueba_de_integracion_no_exige_claves_ni_genera_excel(tmp_path, monkeypatch):
    from buscador import verificar_enlaces
    monkeypatch.setattr(verificar_enlaces, "comprobar", lambda *a, **k: None)
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    def prohibido():
        raise AssertionError("Una prueba no debe exigir Supabase")
    monkeypatch.setattr(supabase, "exigir_conexion", prohibido)
    monkeypatch.setattr(bodega, "recoger", lambda *a, **k: ([{
        "titulo": "UX Designer", "empresa": "Empresa", "enlace": "https://jobs.lever.co/a/1", "fuente": "Lever",
        "ubicacion": "Remote - LATAM", "descripcion": TEXTO}], set(), set(), {}))
    r = bodega.correr(tmp_path, hoy=HOY, prueba=True)
    assert r["codigo_commit"] == "1" * 40 and r["ejecucion_id"] == "123"
    assert r["entrega"]["archivos"] is False
    assert not (tmp_path / "trabajo/entregadas.json").exists()
    assert not (tmp_path / "trabajo/pendientes_supabase.json").exists()
    assert not list(tmp_path.rglob("*.xlsx"))


def test_validacion_no_confunde_workflow_exitoso_con_entrega_completa():
    reporte = {"vacantes_en_bodega": 120, "entrega": {"meta_cumplida": True,
               "supabase": {"filas": 120, "enviadas": 120, "pendientes": 0, "errores": []}}}
    assert validacion.errores(reporte) == []
    reporte["entrega"]["supabase"]["pendientes"] = 1
    assert validacion.errores(reporte)
    reporte["entrega"]["supabase"]["pendientes"] = 0
    reporte["entrega"]["meta_cumplida"] = False
    assert validacion.errores(reporte)


def test_escritura_interrumpida_de_json_preserva_estado_anterior(tmp_path, monkeypatch):
    archivo = tmp_path / "pendientes_supabase.json"
    archivo.write_text('{"anterior": true}')
    def interrumpir(datos, flujo, **kwargs):
        flujo.write('{"incompleto":')
        raise OSError("escritura interrumpida")
    monkeypatch.setattr(bodega.json, "dump", interrumpir)
    with pytest.raises(OSError):
        bodega._guardar_json(archivo, {"nuevo": True})
    assert json.loads(archivo.read_text()) == {"anterior": True}
