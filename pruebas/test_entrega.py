"""Entrega diaria en el formato del contrato de datos v1: filas, roles, variedad, nunca repetidas, Supabase y
publicaciones de Apify."""

from buscador import contrato, entrega, familias, supabase, vacante
from buscador.fuentes import publicaciones_apify

HOY = "2026-11-05"
CORREO = "talento" + "@" + "empresa.co"   # armado por partes: la prueba del repositorio busca correos escritos
TEXTO_ES = ("Buscamos Product Designer para nuestro equipo de producto en Bogotá. Modalidad híbrida. Requisitos: "
            "3 a 5 años de experiencia en diseño de producto, Figma, prototipos y design system. Inglés B2 deseable. "
            "Ofrecemos contrato a término indefinido, tiempo completo. Salario: COP 6.000.000 - 8.000.000 al mes. "
            "Envía tu portafolio a " + CORREO)
TEXTO_EN = ("We are looking for a Senior QA Engineer to join our fully remote team across LATAM. You will design test "
            "plans, automate with Cypress and Playwright, and work with product teams. Requirements: 5+ years of "
            "experience in QA automation, fluent English (C1). Full-time contractor role. Compensation: USD 3,000 - "
            "4,500 per month.")


def _v(titulo, empresa, ubicacion, texto, enlace, directo="", fecha="2026-11-04", hoy=HOY, remoto=None):
    return vacante.crear(titulo, empresa, enlace, "LinkedIn", ubicacion, descripcion=texto, fecha=fecha, hoy=hoy,
                         enlace_directo=directo, remoto=remoto)


def test_filas_del_contrato_en_espanol():
    v = _v("Product Designer", "Acme", "Bogotá, Distrito Capital, Colombia (Híbrido)", TEXTO_ES,
           "https://www.linkedin.com/jobs/view/product-designer-at-acme-4012345678?refId=abc&trk=x",
           directo="https://job-boards.greenhouse.io/acme/jobs/123?gh_src=lnkd&utm_source=li")
    filas = contrato.filas(v, "Product designer", "exact", HOY, "2026-11-05T07:00:00Z")
    assert [f["offer_url"] for f in filas] == ["https://www.linkedin.com/jobs/view/4012345678/"]
    f = filas[0]
    assert set(f) == set(contrato.COLUMNAS + contrato.EXTRAS)
    assert f["external_id"] == "lnkd-4012345678" and f["vacante_id"] == v["id"]
    assert f["source_portal"] == "LinkedIn"
    assert f["enlaces_alternativos"] == ["https://job-boards.greenhouse.io/acme/jobs/123", "https://www.linkedin.com/jobs/view/4012345678/"]
    assert (f["work_mode"], f["office_city"], f["office_country"], f["hire_scope"], f["hire_countries"]) == \
        ("hybrid", "Bogotá", "CO", "city", "CO")
    assert f["posting_language"] == "es" and f["language_requirements"] == "en:B2:0"
    assert (f["years_experience_min"], f["years_experience_max"]) == (3, 5)
    assert f["employment_type"] == "full_time" and f["seniority"] == ""
    assert (f["salary_min"], f["salary_max"], f["salary_currency"], f["salary_period"]) == (6000000, 8000000, "COP", "month")
    assert f["apply_email"] == CORREO
    assert f["published_date"] == "2026-11-04" and f["status"] == "active"
    assert "figma" in f["keywords_technical"].split("|")
    assert f["industries"] == "" and f["summary"] == ""   # los completa la plataforma con IA


def test_filas_del_contrato_remoto_latam_en_ingles():
    v = _v("Senior QA Engineer", "Globant", "Latin America (Remote)", TEXTO_EN,
           "https://www.linkedin.com/jobs/view/4099999999/")
    f = contrato.filas(v)[0]
    assert (f["work_mode"], f["hire_scope"], f["hire_regions"], f["office_country"]) == ("remote", "region", "LATAM", "")
    assert f["posting_language"] == "en" and f["language_requirements"] == "en:C1:1"
    assert f["seniority"] == "senior" and f["years_experience_min"] == 5 and f["years_experience_max"] == ""
    assert f["employment_type"] == "contract"     # "Full-time contractor role"
    assert (f["salary_currency"], f["salary_min"], f["salary_max"], f["salary_period"]) == ("USD", 3000, 4500, "month")


def test_alcances_del_contrato():
    mundo = _v("UX Designer", "A", "Remote - Worldwide", TEXTO_EN, "https://jobs.lever.co/a/1")
    europa = _v("UX Designer", "B", "Remote - Europe", TEXTO_EN, "https://jobs.lever.co/b/1")
    mexico = _v("UX Designer", "C", "Remote, Mexico", TEXTO_EN, "https://jobs.lever.co/c/1")
    sin_region = _v("UX Designer", "D", "Remote", "Design screens for our app. " * 20, "https://jobs.lever.co/d/1")
    assert contrato.ubicacion(mundo)[3:] == ("worldwide", [], [])
    assert contrato.ubicacion(europa)[3:] == ("region", [], ["EU"])
    assert contrato.ubicacion(mexico)[3:] == ("country", ["MX"], [])
    assert contrato.ubicacion(sin_region)[3] == ""          # no lo aclara: vacío, no se inventa


def test_presencial_solo_si_el_aviso_lo_dice():
    v = _v("QA Analyst", "Banco", "Lima, Peru", "Probar aplicaciones móviles y web del banco. " * 10,
           "https://www.linkedin.com/jobs/view/4011111111/")
    f = contrato.filas(v)[0]
    assert f["work_mode"] == "" and f["office_country"] == "PE" and f["hire_scope"] == "city"


def test_salarios_y_seniority():
    assert contrato.salario("$12,000.00 - $15,000.00", "Sueldo: $12,000.00 - $15,000.00 MXN mensuales") == \
        ("$12,000.00 - $15,000.00", 12000, 15000, "MXN", "month")
    assert contrato.salario("$100,000") [3] == ""            # un "$" solo no dice la moneda
    assert contrato.salario("R$ 4.500,50 por mês")[1:4] == (4500.5, "", "BRL")
    assert contrato.salario("US$ 50k - 70k per year")[1:5] == (50000, 70000, "USD", "year")
    assert contrato.seniority("Staff Product Designer") == "senior"
    assert contrato.seniority("Head of Product") == "lead"
    assert contrato.seniority("Product Designer Semi Senior") == "mid"
    assert contrato.seniority("Practicante de QA") == "intern"


def test_url_limpia_y_external_id():
    assert contrato.url_limpia("https://co.linkedin.com/jobs/view/ux-designer-at-x-4123456789?position=1") == \
        "https://www.linkedin.com/jobs/view/4123456789/"
    assert contrato.external_id("https://www.linkedin.com/posts/ana_hiring-activity-7391234567890123456-abcd") == \
        "lnkdpost-7391234567890123456"
    a = contrato.external_id("https://apply.workable.com/acme/j/ABC123/?utm_source=x")
    assert a == contrato.external_id("https://apply.workable.com/acme/j/ABC123/") and a.startswith("workable-")


def test_entregable():
    v = _v("QA Analyst", "", "Lima, Peru", TEXTO_ES, "https://www.linkedin.com/jobs/view/4011111112/")
    assert contrato.entregable(v) == "sin empresa"
    v = _v("QA Analyst", "X", "Lima, Peru", "corto", "https://www.linkedin.com/jobs/view/4011111113/")
    assert contrato.entregable(v) == "sin descripción completa"
    v = _v("Analista de QA", "X", "São Paulo, Brazil", "Você vai atuar com testes automatizados, não é necessário "
           "inglês. Nossa vaga é para trabalho presencial e o conhecimento em Cypress é desejável. " * 3,
           "https://www.linkedin.com/jobs/view/4011111114/")
    assert contrato.entregable(v) == "idioma fuera del contrato"


def test_roles_de_la_entrega():
    roles = entrega.config()["roles"]
    ids = {f["id"] for f in familias.mapa()}
    assert all(set(r["familias"]) <= ids for r in roles)
    assert [r["id"] for r in roles] == ["product-designer", "ux-ui-designer", "product-owner", "product-manager",
                                        "ai-engineer", "qa"]
    pd = _v("Senior Product Designer", "A", "Bogotá, Colombia", TEXTO_ES, "https://www.linkedin.com/jobs/view/1")
    ux = _v("Diseñador UX/UI", "B", "Bogotá, Colombia", TEXTO_ES, "https://www.linkedin.com/jobs/view/2")
    po = _v("Product Owner", "C", "Bogotá, Colombia", TEXTO_ES, "https://www.linkedin.com/jobs/view/3")
    ai = _v("Machine Learning Engineer", "D", "Bogotá, Colombia", TEXTO_ES, "https://www.linkedin.com/jobs/view/4")
    assert entrega.rol_de(pd, roles)[0]["id"] == "product-designer"
    assert entrega.rol_de(ux, roles)[0]["id"] == "ux-ui-designer"
    assert entrega.rol_de(po, roles) == (roles[2], "exacto")
    assert entrega.rol_de(ai, roles)[0]["id"] == "ai-engineer"


def test_qa_no_se_rellena_con_desarrollo_generico_y_conserva_variantes():
    roles = entrega.config()["roles"]
    for titulo in ("Software Engineer - Backend", "DevOps Engineer", "Senior Software Engineer - LATAM"):
        v = _v(titulo, "Empresa", "Remote LATAM", "Build software services. " * 20, "https://jobs.lever.co/acme/1")
        assert "qa" not in {f["familia"] for f in v["familias"]}
        assert entrega.rol_de(v, roles)[0] is None
    for titulo in ("QA Tester Jr.", "Tester Jr. Manual Bilingüe", "QA Test Automation | Mid (Remote)",
                   "Software Developer in Test", "SDET"):
        v = _v(titulo, "Empresa", "Remote LATAM", TEXTO_EN, "https://jobs.lever.co/acme/2")
        assert entrega.rol_de(v, roles)[0]["id"] == "qa"
    servicio = _v("QA, Customer Success Manager, LATAM", "Empresa", "Remote LATAM", TEXTO_EN,
                   "https://jobs.lever.co/acme/customer-success")
    assert "qa" not in {f["familia"] for f in servicio["familias"]}


def test_ia_conserva_cargo_mixto_explicito_sin_contar_todo_backend():
    roles = entrega.config()["roles"]
    for titulo in ("Machine Learning / Data Engineer", "LLM Engineer", "Applied AI Engineer"):
        v = _v(titulo, "Empresa", "Remote LATAM", TEXTO_EN, "https://jobs.lever.co/acme/3")
        assert entrega.rol_de(v, roles)[0]["id"] == "ai-engineer"
    v = _v("Senior Backend Developer", "Empresa", "Remote LATAM", TEXTO_EN, "https://jobs.lever.co/acme/4")
    assert entrega.rol_de(v, roles)[0] is None


def test_afinidad_antes_de_alcance_remoto_para_cuota():
    exacta = _v("QA Analyst", "A", "Remote, Mexico", TEXTO_EN, "https://jobs.lever.co/a/1")
    cercana = _v("Software Developer in Test", "B", "Remote Worldwide", TEXTO_EN, "https://jobs.lever.co/b/1")
    assert entrega.variadas([(cercana, "cercano"), (exacta, "exacto")], 1, 2, HOY,
                           preferir_remotas=True)[0][0]["id"] == exacta["id"]


def test_reetiquetar_corrige_familias_guardadas_sin_cambiar_identidad():
    v = _v("DevOps Engineer", "Empresa", "Remote LATAM", TEXTO_EN, "https://jobs.lever.co/acme/5")
    v["familias"].append({"familia": "qa", "coincidencia": "cercano"})
    anterior = v["id"], v["detectada_en"], v["vista_en"]
    actual = vacante.reetiquetar(v)
    assert "qa" not in {f["familia"] for f in actual["familias"]}
    assert (actual["id"], actual["detectada_en"], actual["vista_en"]) == anterior


def _muchas(n, idioma_en_cada=2):
    salida = []
    for i in range(n):
        en = i % idioma_en_cada == 0
        nivel = ["Junior ", "Senior ", "", "Lead "][i % 4]
        lugar = ["Bogotá, Colombia", "Lima, Peru", "Ciudad de México, México", "Remote - LATAM"][i % 4]
        cargo = ["QA Analyst", "QA Engineer", "Software Tester"][i % 3]   # 3 cargos distintos por empresa
        salida.append(_v(f"{nivel}{cargo}", f"Empresa {i // 3}", lugar, (TEXTO_EN if en else TEXTO_ES) + f" #{i}",
                         f"https://www.linkedin.com/jobs/view/40{i:08d}/"))
    return salida


def test_variedad_y_tope_por_empresa():
    vac = _muchas(60, idioma_en_cada=6)   # solo 1 de cada 6 en inglés
    cfg = dict(entrega.config(), preferir_remotas=False)  # aislar la variedad de la prioridad remota
    elegidas, resumen = entrega.elegir(vac, {}, HOY, cfg)
    qa = [v for v, _ in elegidas["qa"]]
    assert len(qa) == 20
    idiomas = resumen["roles"]["qa"]["idiomas"]
    assert idiomas.get("en", 0) >= 8          # las pocas en inglés suben, no quedan 20 en español
    assert len(resumen["roles"]["qa"]["niveles"]) >= 3
    empresas = [v["empresa"] for v in qa]
    assert max(empresas.count(e) for e in set(empresas)) <= 2


def test_nunca_repetidas(tmp_path):
    vac = _muchas(50)
    entregadas, recibidas = {}, []
    def subir(filas):
        ids = {f["external_id"] for f in filas}
        recibidas.append(ids)
        return {"filas": len(filas), "enviadas": len(filas), "confirmadas": list(ids)}
    r1 = entrega.correr(vac, entregadas, HOY, "2026-11-05T07:00:00Z", tmp_path, subir=subir)
    r2 = entrega.correr(vac, entregadas, "2026-11-06", "2026-11-06T07:00:00Z", tmp_path, subir=subir)
    assert r1["vacantes"] == 20 and r2["vacantes"] == 20 and not recibidas[0] & recibidas[1]
    r3 = entrega.correr(vac, entregadas, "2026-11-07", "2026-11-07T07:00:00Z", tmp_path, subir=subir)
    assert r3["vacantes"] == 10 and r3["roles"]["qa"]["faltan"] == 10
    assert not list(tmp_path.iterdir())


def test_fila_para_supabase():
    v = _v("Senior QA Engineer", "Globant", "Latin America (Remote)", TEXTO_EN, "https://www.linkedin.com/jobs/view/4099999999/")
    fila = supabase.fila_db(contrato.filas(v, "QA", "exact", HOY, "2026-11-05T07:00:00Z")[0])
    assert fila["hire_regions"] == ["LATAM"] and fila["hire_countries"] is None
    assert fila["language_requirements"] == [{"language": "en", "level": "C1", "required": True}]
    assert fila["salary_min"] == 3000 and fila["office_city"] is None and fila["delivery_date"] == HOY


class _Sesion:
    def __init__(self, codigo=201):
        self.llamadas, self.codigo = [], codigo

    def post(self, url, json, headers, timeout):
        self.llamadas.append((url, len(json), headers))

        class R:
            status_code = self.codigo
            text = "error"
        return R()


def test_subir_a_supabase_por_lotes():
    filas = [dict.fromkeys(contrato.COLUMNAS + contrato.EXTRAS, "") | {"external_id": f"x-{i}", "job_title": "QA",
                                                                       "company_name": "A"} for i in range(1200)]
    s = _Sesion()
    r = supabase.subir(filas, "https://abc.supabase.co", "sb_secret_123", sesion=s)
    assert r.pop("confirmadas") == [f"x-{i}" for i in range(1200)]
    assert r == {"filas": 1200, "enviadas": 1200, "errores": []}
    assert [n for _, n, _ in s.llamadas] == [500, 500, 200]
    url, _, cab = s.llamadas[0]
    assert url.endswith("/rest/v1/ofertas?on_conflict=external_id")
    assert "ignore-duplicates" in cab["Prefer"] and "Authorization" not in cab   # nunca sobrescribe
    assert supabase.subir(filas[:3], "https://abc.supabase.co", "x", sesion=_Sesion(401))["errores"]
    assert "omitida" in supabase.subir(filas[:1], url="", clave="")


def test_publicaciones_de_apify():
    validas = {"diseno-producto-ux", "ux-research", "product-owner", "product-manager", "ia-ml", "qa"}
    buena = {"linkedinUrl": "https://www.linkedin.com/posts/ana-perez_hiring-activity-7391234567890123456-abcd?utm_source=x",
             "content": "¡Estamos contratando! Buscamos Senior Product Designer para trabajar 100% remoto desde "
                        "Colombia o México. Experiencia con Figma y design systems. Envía tu CV por DM.",
             "author": {"name": "Ana Pérez", "info": "Talent Acquisition Lead at Rappi | Tech recruiter", "type": "profile"},
             "postedAt": {"date": "2026-11-04T15:20:00.000Z"}}
    v, motivo = publicaciones_apify.a_vacante(buena, validas)
    assert motivo == "" and v["titulo"] == "Senior Product Designer" and v["empresa"] == "Rappi"
    assert v["fecha"] == "2026-11-04" and v["remoto"] is True and "Colombia" in v["ubicacion"]
    assert v["enlace"].endswith("-abcd")
    vac = vacante.crear(v["titulo"], v["empresa"], v["enlace"], v["fuente"], v["ubicacion"], descripcion=v["descripcion"],
                        fecha=v["fecha"], remoto=v["remoto"], hoy=HOY)
    assert vac is None  # indicio del feed pendiente de verificar; no se envía a Supabase
    open_to_work = dict(buena, content="#OpenToWork Soy Product Designer y estoy buscando trabajo en Colombia.")
    assert publicaciones_apify.a_vacante(open_to_work, validas)[1] == "no anuncia una contratación"
    sin_empresa = dict(buena, author={"name": "Ana", "info": "Diseñadora", "type": "profile"})
    assert publicaciones_apify.a_vacante(sin_empresa, validas)[1] == "sin empresa"
    empresa_autora = dict(buena, author={"name": "Nubank", "type": "company"})
    assert publicaciones_apify.a_vacante(empresa_autora, validas)[0]["empresa"] == "Nubank"
    lejos = dict(buena, content="We're hiring a Product Designer in New York, onsite.")
    assert publicaciones_apify.a_vacante(lejos, validas)[1] == "sin país ni remoto"


def test_entrada_del_actor_y_sin_token():
    e = publicaciones_apify.entrada("harvestapi/linkedin-post-search", ["a", "b"], 6, HOY)
    assert e["searchQueries"] == ["a", "b"] and e["maxPosts"] == 6 and e["postedLimit"] == "24h"
    e = publicaciones_apify.entrada("lofomachines/linkedin-post-search-scraper", ["a"], 6, HOY)
    assert e["keywords"] == ["a"] and e["publishedAfter"] == "2026-11-04"
    crudas, stats = publicaciones_apify.buscar(None, "harvestapi/linkedin-post-search", ["a"], set(), HOY, token="")
    assert crudas == [] and "omitida" in stats
    consultas = entrega.config()["consultas_publicaciones"]
    assert consultas and all(sum(c.count(op) for op in (" AND ", " OR ", " NOT ")) <= 5 for c in consultas)


def test_direccion_de_supabase_con_ruta():
    """La pantalla Data API muestra https://<proyecto>.supabase.co/rest/v1/: se usa solo el dominio."""
    assert supabase.base("https://abc.supabase.co/rest/v1/") == "https://abc.supabase.co"
    assert supabase.base(" https://abc.supabase.co/ ") == "https://abc.supabase.co"
    s = _Sesion()
    supabase.subir([dict.fromkeys(contrato.COLUMNAS + contrato.EXTRAS, "") | {"external_id": "x"}],
                   "https://abc.supabase.co/rest/v1", "sb_secret_1", sesion=s)
    assert s.llamadas[0][0] == "https://abc.supabase.co/rest/v1/ofertas?on_conflict=external_id"


def test_region_dudosa_no_completa_meta_pero_mundial_si():
    texto = "Design screens for our application and collaborate with the product team. " * 8
    for ubicacion in ("Remote", "Ciudad sin identificar"):
        v = _v("Product Designer", "Empresa", ubicacion, texto, "https://jobs.lever.co/a/incierta")
        assert v["confianza_pais"] == "baja"
        assert contrato.entregable(v) == "elegibilidad regional por confirmar"
        elegidas, _ = entrega.elegir([v], {}, HOY)
        assert not any(elegidas.values())
    mundial = _v("Product Designer", "Empresa", "Remote Worldwide", texto, "https://jobs.lever.co/a/mundial")
    assert not contrato.entregable(mundial)
