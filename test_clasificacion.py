"""Regression tests for tema / subtema / tono / grouping in app.py.

Streamlit is mocked so the module can be imported without a running server.
"""
import io
import re
import sys
import unittest
from unittest.mock import MagicMock, patch


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _install_streamlit_stub():
    st = MagicMock()
    st.session_state = _Session()
    st.secrets = {}
    st.set_page_config = lambda **_k: None
    sys.modules.setdefault("streamlit", st)
    return st


_install_streamlit_stub()

import app  # noqa: E402


MARCA = "Universidad Tecnológica de Bolívar"
ALIAS = "UTB"


class TestAnalisisOrder(unittest.TestCase):
    def test_usa_fragmentos_de_marca_primero(self):
        titulo = "El gobierno anuncia reforma tributaria nacional"
        resumen = "El Congreso debate impuestos. La UTB lanza una carrera de medicina deportiva en Cartagena."
        texto, hay = app._texto_clasificacion(titulo, resumen, MARCA, ALIAS)
        self.assertTrue(hay)
        self.assertIn("carrera", texto.lower())
        self.assertNotIn("reforma tributaria", texto.lower())

    def test_cae_a_resumen_si_no_hay_marca(self):
        titulo = "Corto"
        resumen = "El ministerio publicó un informe de movilidad urbana sobre el nuevo metro de Bogotá."
        texto, hay = app._texto_clasificacion(titulo, resumen, MARCA, ALIAS)
        self.assertFalse(hay)
        self.assertIn("movilidad", texto.lower())
        self.assertNotIn("Corto", texto)

    def test_cae_a_titulo_si_resumen_insuficiente(self):
        titulo = "Apertura del laboratorio de biotecnología marina"
        resumen = "N/A"
        texto, hay = app._texto_clasificacion(titulo, resumen, MARCA, ALIAS)
        self.assertFalse(hay)
        self.assertIn("laboratorio", texto.lower())


class TestEtiquetasEspecificas(unittest.TestCase):
    def test_no_emite_cubos_genericos(self):
        texto = (
            "La Universidad Tecnológica de Bolívar lanza una nueva carrera de medicina "
            "deportiva junto al hospital universitario de Cartagena."
        )
        sub = app._extraer_subtema_especifico(texto, MARCA, ALIAS)
        self.assertFalse(app._es_etiqueta_generica(sub), sub)
        self.assertNotIn(",", sub)
        self.assertNotEqual(sub.strip().lower(), "sin tema")
        self.assertNotIn("cobertura", sub.lower())
        self.assertGreaterEqual(len(sub.split()), 2)

    def test_etiqueta_generica_detecta_sintomas(self):
        for raw in (
            "Cobertura de información relevante",
            "Cobertura informativa general",
            "Sin tema",
            "Varios",
        ):
            self.assertTrue(app._es_etiqueta_generica(raw), raw)

    def test_investigacion_no_empieza_por_verbo(self):
        texto = (
            "La Universidad Tecnológica de Bolívar enfrenta una investigación "
            "por fallas operativas en sus laboratorios."
        )
        sub = app._extraer_subtema_especifico(texto, MARCA, ALIAS)
        self.assertFalse(app._es_verbo_cabeza(sub.split()[0]), sub)
        self.assertIn("investig", app.unidecode(sub.lower()))

    def test_lanzamiento_es_subtema_valido(self):
        self.assertTrue(app._validar_estructura_subtema("Lanzamiento de carrera deportiva"))

    def test_limpiar_tema_quita_comas(self):
        limpio = app.limpiar_tema("Educación superior, formación profesional")
        self.assertNotIn(",", limpio)
        self.assertTrue(limpio)
        self.assertFalse(app._es_etiqueta_generica(limpio))

    def test_fallback_del_clasificador_nunca_generico(self):
        clf = app.ClasificadorSubtema(MARCA, ALIAS)
        clf._last_blob = (
            "La UTB firma un convenio de formación profesional con el SENA "
            "para técnicos en logística portuaria."
        )
        et = clf._fallback(["UTB firma convenio con el SENA"])
        self.assertFalse(app._es_etiqueta_generica(et), et)
        self.assertNotIn(",", et)


class TestTonoSinMarca(unittest.TestCase):
    def test_sin_fragmentos_contexto_vacio(self):
        ctx = app.extraer_contexto_marca(
            "Crisis del sector avícola nacional",
            "Los productores piden ayudas al gobierno por el alza de insumos.",
            MARCA,
            ALIAS,
        )
        self.assertEqual(ctx, "")

    def test_con_fragmentos_contexto_no_vacio(self):
        ctx = app.extraer_contexto_marca(
            "UTB recibe premio de innovación",
            "La Universidad Tecnológica de Bolívar fue galardonada por su laboratorio.",
            MARCA,
            ALIAS,
        )
        self.assertTrue(ctx)
        self.assertTrue(app._menciona_marca_o_alias(ctx, MARCA, ALIAS))

    def test_snippet_pkl_usa_solo_contexto(self):
        snip = app._snippet_tono_pkl(
            "Titular negativo sobre el sector",
            "La UTB recibió un premio a la excelencia académica.",
        )
        self.assertIn("premio", snip.lower())
        self.assertNotIn("Titular negativo", snip)


class TestAgrupacion(unittest.TestCase):
    def test_misma_historia_comparte_etiquetas(self):
        titulos = [
            "UTB lanza carrera de medicina deportiva en Cartagena",
            "La UTB lanza carrera de medicina deportiva en Cartagena",
        ]
        resumenes = [
            "La Universidad Tecnológica de Bolívar presentó su nueva carrera de medicina deportiva.",
            "La Universidad Tecnológica de Bolívar presentó su nueva carrera de medicina deportiva.",
        ]
        temas, subtemas = app.etiquetar_sin_llm(titulos, resumenes, MARCA, ALIAS)
        self.assertEqual(subtemas[0], subtemas[1])
        self.assertEqual(temas[0], temas[1])
        self.assertFalse(app._es_etiqueta_generica(subtemas[0]), subtemas[0])
        self.assertNotIn(",", subtemas[0])
        self.assertNotIn(",", temas[0])

    def test_historias_distintas_no_comparten_subtema(self):
        titulos = [
            "UTB lanza carrera de medicina deportiva",
            "UTB es investigada por presuntas irregularidades en contrataciones",
        ]
        resumenes = [
            "La Universidad Tecnológica de Bolívar abre una carrera de medicina deportiva.",
            "La Universidad Tecnológica de Bolívar enfrenta una investigación por contrataciones.",
        ]
        _temas, subtemas = app.etiquetar_sin_llm(titulos, resumenes, MARCA, ALIAS)
        self.assertNotEqual(app.string_norm_label(subtemas[0]), app.string_norm_label(subtemas[1]))
        for s in subtemas:
            self.assertFalse(app._es_etiqueta_generica(s), s)

    def test_consistencia_propaga_solo_equivalentes(self):
        df = __import__("pandas").DataFrame({
            "Título": [
                "UTB lanza carrera de medicina deportiva",
                "La UTB lanza carrera de medicina deportiva",
                "Sancionan a otra universidad por fraude en becas",
            ],
            "Resumen - Aclaracion": [
                "La Universidad Tecnológica de Bolívar abre medicina deportiva.",
                "La Universidad Tecnológica de Bolívar abre medicina deportiva.",
                "Otra institución fue sancionada por fraude en el programa de becas.",
            ],
            "Tono IA": ["Positivo", "Neutro", "Negativo"],
            "Tema": ["Educación superior", "Educación superior", "Fraude en becas"],
            "Subtema": [
                "Lanzamiento de carrera deportiva",
                "Lanzamiento de carrera universitaria",
                "Sanción por fraude académico",
            ],
        })
        with patch.object(app, "get_embeddings_batch", return_value=[None, None, None]):
            out = app.aplicar_consistencia_grupos(
                df, "Título", "Resumen - Aclaracion",
                marca=MARCA, aliases=ALIAS,
            )
        self.assertEqual(out.loc[0, "Subtema"], out.loc[1, "Subtema"])
        self.assertEqual(out.loc[0, "Tono IA"], "Positivo")
        self.assertEqual(out.loc[1, "Tono IA"], "Positivo")
        self.assertNotEqual(out.loc[2, "Subtema"], out.loc[0, "Subtema"])
        self.assertEqual(out.loc[2, "Tono IA"], "Negativo")


class TestPklYHeuristica(unittest.TestCase):
    def _pipeline_temas(self, textos, clases):
        from sklearn.pipeline import make_pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
        import joblib

        pipe = make_pipeline(TfidfVectorizer(), MultinomialNB())
        pipe.fit(textos, clases)
        buf = io.BytesIO()
        joblib.dump(pipe, buf)
        buf.seek(0)
        return buf, list(dict.fromkeys(clases))

    def test_pkl_generico_se_reemplaza_dentro_del_vocabulario(self):
        buf, clases = self._pipeline_temas(
            [
                "lanzamiento carrera deportiva utb medicina",
                "cobertura general de noticias del dia",
                "convenio formacion profesional sena educacion",
            ],
            [
                "Educación superior",
                "Cobertura de información relevante",
                "Educación superior",
            ],
        )
        titulos = ["UTB lanza carrera de medicina deportiva"]
        resumenes = ["La Universidad Tecnológica de Bolívar abre medicina deportiva."]
        textos = [app._texto_clasificacion(titulos[0], resumenes[0], MARCA, ALIAS)[0]]
        pack = app.analizar_temas_con_pkl(textos, buf)
        self.assertIsNotNone(pack)
        temas, clases_out = pack
        self.assertEqual(len(temas), 1)
        self.assertIn(temas[0], clases_out)
        self.assertIn(temas[0], clases)
        self.assertFalse(app._es_etiqueta_generica(temas[0]), temas[0])

    def test_pkl_nunca_sale_del_vocabulario_ni_con_pred_generica(self):
        clases = [
            "Reconocimientos institucionales",
            "Gestión hospitalaria",
            "Cobertura de información relevante",
        ]
        buf, _ = self._pipeline_temas(
            [
                "reconocimiento premio distincion acr radiology",
                "hospital clinica pacientes internacion",
                "cobertura de informacion relevante noticias",
            ],
            clases,
        )
        texto = (
            "La Fundación Santa Fe de Bogotá fue reconocida por el American College "
            "of Radiology y se convirtió en la primera institución de Latinoamérica."
        )
        pack = app.analizar_temas_con_pkl([texto], buf)
        self.assertIsNotNone(pack)
        temas, clases_out = pack
        self.assertIn(temas[0], clases_out)
        forzado = app._resolver_etiqueta_pkl(
            "Cobertura de información relevante", texto, clases
        )
        self.assertIn(forzado, clases)
        self.assertFalse(app._es_etiqueta_generica(forzado), forzado)
        pd = __import__("pandas")
        df = pd.DataFrame({
            "Título": ["Distinción ACR"],
            "Resumen - Aclaracion": [texto],
            "Contexto analizado": [texto],
            "Tono IA": ["Positivo"],
            "Tema": ["Tema inventado que no está en el pkl"],
            "Subtema": ["Reconocimiento de ACR en Latinoamérica"],
        })
        with patch.object(app, "get_embeddings_batch", return_value=[None]):
            out = app.aplicar_consistencia_grupos(
                df, "Título", "Resumen - Aclaracion",
                marca="Fundación Santa Fe de Bogotá", aliases=None,
                vocabulario_tema=clases,
            )
        self.assertIn(out.loc[0, "Tema"], clases)

    def test_sin_pkl_etiquetas_especificas(self):
        titulos = ["Investigación por fallas operativas en el campus de la UTB"]
        resumenes = [
            "La Universidad Tecnológica de Bolívar enfrenta una investigación por fallas operativas en laboratorios."
        ]
        temas, subtemas = app.etiquetar_sin_llm(titulos, resumenes, MARCA, ALIAS)
        self.assertFalse(app._es_etiqueta_generica(subtemas[0]), subtemas[0])
        self.assertFalse(app._es_etiqueta_generica(temas[0]), temas[0])
        self.assertNotIn(",", subtemas[0])
        self.assertNotIn(",", temas[0])


CTX_FENAVI_AVICOLA = (
    "PRESIDENTE DE FENAVI El sector avícola realizará su encuentro anual "
    "para analizar las oportunidades de exportación, las perspectivas de "
    "crecimiento de la Industria y las estrategias ante la volatilidad de la tasa de cambio."
)
CTX_FLA_PERSONAS = (
    "Presidente - Fenavi Javier Díaz Presidente - Analdex Dirigente y "
    "exgerente - Fábrica de licores de Antioquia, FLA"
)
TITULO_FENAVI = "Presidente de Fenavi"


def _habla_de_fla(texto: str) -> bool:
    n = app.unidecode(str(texto or "").lower())
    return any(tok in n for tok in ("licor", "fla", "fabrica"))


class TestFenaviNoHeredaFla(unittest.TestCase):
    """Una nota del encuentro avícola no puede heredar FLA de otra nota del lote."""

    def test_nucleo_distinto_bloquea_fusión_aunque_corpus_grande(self):
        self.assertTrue(
            app._hechos_nucleo_distinto(CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS, "Fenavi", None)
        )
        self.assertFalse(
            app._pueden_compartir_subtema(
                CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS, "Fenavi", None, estricto=False
            )
        )
        self.assertFalse(
            app._historias_son_el_mismo_hecho(CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS)
        )

    def test_subtema_propio_no_menciona_fla(self):
        sub_a = app._extraer_subtema_especifico(CTX_FENAVI_AVICOLA, "Fenavi", None)
        self.assertFalse(app._es_etiqueta_generica(sub_a), sub_a)
        self.assertFalse(_habla_de_fla(sub_a), sub_a)
        blob = app.unidecode(sub_a.lower())
        self.assertTrue(
            any(tok in blob for tok in ("encuentro", "avicol", "export", "volatil", "cambio")),
            sub_a,
        )
        self.assertFalse(
            app._etiqueta_pertenece_al_texto(
                "Fábrica de licores de Antioquia", CTX_FENAVI_AVICOLA
            )
        )
        self.assertTrue(
            app._etiqueta_pertenece_al_texto(
                "Fábrica de licores de Antioquia", CTX_FLA_PERSONAS
            )
        )

    def test_etiquetar_sin_llm_no_copia_fla(self):
        titulos = [TITULO_FENAVI, TITULO_FENAVI]
        resumenes = [CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS]
        temas, subtemas = app.etiquetar_sin_llm(titulos, resumenes, "Fenavi", None)
        self.assertFalse(_habla_de_fla(subtemas[0]), subtemas[0])
        self.assertFalse(_habla_de_fla(temas[0]), temas[0])
        self.assertNotEqual(
            app.string_norm_label(subtemas[0]),
            app.string_norm_label(subtemas[1]),
        )
        self.assertFalse(app._es_etiqueta_generica(subtemas[0]), subtemas[0])
        self.assertFalse(app._es_etiqueta_generica(subtemas[1]), subtemas[1])
        self.assertNotIn(",", subtemas[0])
        self.assertNotIn(",", subtemas[1])

    def test_grupo_noticia_compartido_no_contamina(self):
        pd = __import__("pandas")
        df = pd.DataFrame({
            "Título": [TITULO_FENAVI, TITULO_FENAVI],
            "Resumen - Aclaracion": [CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS],
            "Contexto analizado": [CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS],
            "Grupo noticia": ["G00001", "G00001"],
            "Tono IA": ["Neutro", "Neutro"],
            "Tema": ["Fábrica de licores de Antioquia", "Fábrica de licores de Antioquia"],
            "Subtema": ["Fábrica de licores de Antioquia", "Fábrica de licores de Antioquia"],
        })
        with patch.object(app, "get_embeddings_batch", return_value=[None, None]):
            out = app.aplicar_consistencia_grupos(
                df, "Título", "Resumen - Aclaracion",
                marca="Fenavi", aliases=None,
            )
        self.assertFalse(_habla_de_fla(out.loc[0, "Subtema"]), out.loc[0, "Subtema"])
        self.assertFalse(_habla_de_fla(out.loc[0, "Tema"]), out.loc[0, "Tema"])
        self.assertNotEqual(
            app.string_norm_label(out.loc[0, "Subtema"]),
            app.string_norm_label("Fábrica de licores de Antioquia"),
        )

    def test_llm_no_reutiliza_fla_del_lote(self):
        pd = __import__("pandas")
        clf = app.ClasificadorSubtema("Fenavi", None)
        pbar = MagicMock()
        col = pd.Series([CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS])
        res = pd.Series([CTX_FENAVI_AVICOLA, CTX_FLA_PERSONAS])
        tit = pd.Series([TITULO_FENAVI, TITULO_FENAVI])
        with patch.object(app, "get_embeddings_batch", return_value=[None, None]), \
             patch.object(
                 clf, "_generar_etiqueta",
                 return_value="Fábrica de licores de Antioquia",
             ):
            subtemas = clf.procesar_lote(col, pbar, res, tit)
        self.assertEqual(len(subtemas), 2)
        self.assertFalse(_habla_de_fla(subtemas[0]), subtemas[0])
        self.assertFalse(app._es_etiqueta_generica(subtemas[0]), subtemas[0])
        self.assertNotIn(",", subtemas[0])
        self.assertNotEqual(
            app.string_norm_label(subtemas[0]),
            app.string_norm_label(subtemas[1]),
        )


class TestSubtemaCompleto(unittest.TestCase):
    """Subtemas completos para cualquier marca: no trocear nombres ni omitir el hecho."""

    def _assert_subtema_completo(self, sub, texto, marca):
        n = app.unidecode(sub.lower())
        self.assertFalse(app._es_etiqueta_generica(sub), sub)
        self.assertNotIn(",", sub)
        self.assertGreaterEqual(len(sub.split()), 2, sub)
        self.assertFalse(app._etiqueta_trocea_nombre(sub, texto, marca, None), sub)
        self.assertFalse(app._es_nombre_o_fragmento_marca(sub, marca, None), sub)

    def test_no_trocea_nombres_propios_de_marcas_distintas(self):
        casos = [
            (
                "Fundación Santa Fe de Bogotá",
                "La Fundación Santa Fe de Bogotá fue reconocida por el American College of Radiology "
                "y se convirtió en la primera institución de Latinoamérica en lograr esta distinción. "
                "La Fundación Santa Fe de Bogotá fue reconocida por el American College of Radiology (ACR) "
                "como ACR® International Center for Quality and Safety.",
                ("acr", "american college", "latinoameric", "quality", "distincion"),
            ),
            (
                "Hospital San Juan de Dios",
                "El Hospital San Juan de Dios fue reconocido por la World Health Organization (WHO) "
                "como centro de referencia en atención materna y se convirtió en el primer hospital "
                "de la región en lograr esta distinción.",
                ("who", "world health", "atencion", "materna", "distincion", "referencia"),
            ),
            (
                "Caja de Compensación Familiar de Fenalco",
                "La Caja de Compensación Familiar de Fenalco inauguró un centro de bienestar laboral "
                "en Cartagena para afiliados del sector comercio.",
                ("inaugur", "bienestar", "cartagena", "centro", "afiliad"),
            ),
        ]
        for marca, ctx, tokens_hecho in casos:
            with self.subTest(marca=marca):
                sub = app._extraer_subtema_especifico(ctx, marca, None)
                self._assert_subtema_completo(sub, ctx, marca)
                n = app.unidecode(sub.lower())
                self.assertTrue(any(tok in n for tok in tokens_hecho), sub)
                marca_n = app.unidecode(marca.lower())
                if "bogot" in n and "santa" in marca_n:
                    self.assertIn("santa fe de bogot", n, sub)
                if "dios" in n and "juan" in marca_n:
                    self.assertIn("san juan de dios", n, sub)

    def test_etiquetar_respeta_contexto_de_marca(self):
        marca = "Hospital San Juan de Dios"
        ctx = (
            "El Hospital San Juan de Dios fue reconocido por la World Health Organization (WHO) "
            "como centro de referencia en atención materna."
        )
        _temas, subtemas = app.etiquetar_sin_llm(
            ["Hospital recibe distinción internacional"],
            [ctx],
            marca,
            None,
        )
        self._assert_subtema_completo(subtemas[0], ctx, marca)
        n = app.unidecode(subtemas[0].lower())
        self.assertTrue(any(tok in n for tok in ("who", "world health", "atencion", "materna", "referencia")), subtemas[0])


CTX_ENCUENTRO_PANEL = (
    "El encuentro reunió al Dr. Giancarlo Buitrago, director de Investigaciones y Educación de LaCardio; "
    "al Dr. Gerardo Andrés Puentes Leal, líder de las Unidades de Endoscopia y del Servicio de Gastroenterología "
    "y jefe de Estudios y Epidemiología Clínicos del Hospital Serena del Mar; a Eddy Carolina Betancourt, "
    "directora científica de Alianza Team; y a Erick Eduardo Orozco Acosta, director del Doctorado en "
    "Inteligencia Artificial de la Universidad Simón Bolívar."
)

CTX_FORO_NUBARIA = (
    "El foro reunió a Marta Quilez, directora de Innovación Azul de Nubaria Tech; "
    "y a Pablo Reines, líder del Laboratorio de Robótica de la Universidad de Zelta."
)


class TestSubtemaFraseEvento(unittest.TestCase):
    """Subtema = frase de evento completa, no un n-grama ni un nombre de pila recortado."""

    def _assert_frase_evento(self, sub, texto):
        self.assertFalse(app._es_etiqueta_generica(sub), sub)
        self.assertNotIn(",", sub)
        self.assertGreaterEqual(len(sub.split()), 2, sub)
        self.assertFalse(app._subtema_de_baja_calidad(sub, texto), sub)
        n = app.unidecode(sub.lower())
        self.assertNotIn("reunio", n, sub)
        self.assertFalse(n.rstrip(".").endswith("giancarlo"), sub)
        self.assertFalse(n.rstrip(".").endswith("marta"), sub)
        self.assertFalse(n.rstrip(".").endswith("pablo"), sub)

    def test_encuentro_no_es_n_grama_ni_pila(self):
        sub = app._extraer_subtema_especifico(CTX_ENCUENTRO_PANEL, "LaCardio", ["lacardio"])
        self._assert_frase_evento(sub, CTX_ENCUENTRO_PANEL)
        n = app.unidecode(sub.lower())
        self.assertIn("encuentro", n)
        self.assertTrue(
            any(tok in n for tok in ("investig", "educacion", "especialist")),
            sub,
        )

    def test_encuentro_sin_marca_tambien_es_evento(self):
        sub = app._extraer_subtema_especifico(CTX_ENCUENTRO_PANEL, "", None)
        self._assert_frase_evento(sub, CTX_ENCUENTRO_PANEL)
        self.assertIn("encuentro", app.unidecode(sub.lower()))

    def test_rechaza_scrap_reunio_giancarlo(self):
        scrap = "Encuentro de reunio giancarlo"
        self.assertTrue(app._subtema_de_baja_calidad(scrap, CTX_ENCUENTRO_PANEL), scrap)
        regenerada = app._asegurar_etiqueta_especifica(
            scrap, CTX_ENCUENTRO_PANEL, "LaCardio", ["lacardio"]
        )
        self._assert_frase_evento(regenerada, CTX_ENCUENTRO_PANEL)
        self.assertNotEqual(app.string_norm_label(regenerada), app.string_norm_label(scrap))

    def test_foro_marca_ficticia_no_es_caso_especial(self):
        sub = app._extraer_subtema_especifico(CTX_FORO_NUBARIA, "Nubaria Tech", ["nubaria"])
        self._assert_frase_evento(sub, CTX_FORO_NUBARIA)
        n = app.unidecode(sub.lower())
        self.assertTrue(
            any(tok in n for tok in ("foro", "innovacion", "robotic", "laboratorio")),
            sub,
        )
        self.assertNotIn("reunio", n)


CTX_DIPORTO = (
    "Diporto propone una experiencia residencial de lujo que invita a descubrir "
    "una nueva forma de habitar e invertir en el Gran Canal de Serena del Mar. "
    "Único en su tipo, este desarrollo propone un entorno donde paisaje, "
    "arquitectura y vida se encuentran."
)
_COLLAGE_DIPORTO = "Canal de único en su tipo este desarrollo"


class TestSubtemaHechoNominal(unittest.TestCase):
    """El subtema es un encabezado gramatical del hecho, no un collage de keywords."""

    def _assert_residencial_lujo(self, sub):
        n = app.unidecode(sub.lower())
        self.assertFalse(re.search(r"canal de unico", n), sub)
        self.assertFalse(re.search(r"unico en su tipo este desarrollo", n), sub)
        self.assertFalse(app._es_etiqueta_generica(sub), sub)
        self.assertNotIn(",", sub)
        self.assertFalse(app._subtema_de_baja_calidad(sub, CTX_DIPORTO), sub)
        self.assertTrue(
            ("residencial" in n and ("lujo" in n or "serena" in n or "desarrollo" in n or "proyecto" in n))
            or ("desarrollo" in n and ("serena" in n or "lujo" in n or "residencial" in n))
            or ("proyecto" in n and ("residencial" in n or "lujo" in n)),
            sub,
        )

    def test_collage_es_baja_calidad(self):
        self.assertTrue(
            app._subtema_de_baja_calidad(_COLLAGE_DIPORTO, CTX_DIPORTO),
            _COLLAGE_DIPORTO,
        )

    def test_extraer_no_emite_collage(self):
        for marca, aliases in (
            ("Diporto", None),
            ("Serena del Mar", None),
            ("Diporto", ["Serena del Mar", "Gran Canal"]),
        ):
            with self.subTest(marca=marca):
                sub = app._extraer_subtema_especifico(CTX_DIPORTO, marca, aliases)
                self._assert_residencial_lujo(sub)

    def test_etiquetar_sin_llm_no_emite_collage(self):
        for marca, aliases in (
            ("Diporto", None),
            ("Serena del Mar", None),
        ):
            with self.subTest(marca=marca):
                _temas, subtemas = app.etiquetar_sin_llm(
                    ["Diporto lanza residencial de lujo"],
                    [CTX_DIPORTO],
                    marca,
                    aliases,
                )
                self._assert_residencial_lujo(subtemas[0])

    def test_no_une_tokens_sueltos_con_de(self):
        import inspect
        src = inspect.getsource(app._extraer_subtema_especifico)
        self.assertNotIn("join(top", src)
        self.assertNotIn("_palabras_contenido_evento", src)
        self.assertFalse(hasattr(app, "_palabras_contenido_evento"))


class TestCotaLLMYVelocidad(unittest.TestCase):
    """El etiquetado no puede cascada de refine ni colgarse en 1/N."""

    def test_generar_etiqueta_no_espiral_de_refine(self):
        import json as _json
        clf = app.ClasificadorSubtema(MARCA, ALIAS)
        calls = {"n": 0}

        def fake_create(*_a, **_k):
            calls["n"] += 1
            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = _json.dumps({"subtema": "Varios"})
            resp.choices = [choice]
            resp.get = lambda k, d=None: {} if k == "usage" else d
            return resp

        blob = "Un texto demasiado vago para que la heurística cierre sola. Hechos varios del día."
        with patch.object(app.openai.ChatCompletion, "create", side_effect=fake_create):
            et = clf._generar_etiqueta(
                [blob],
                ["Noticia institucional del sector"],
                [blob],
            )
        self.assertLessEqual(calls["n"], app.MAX_LLM_CALLS_POR_ETIQUETA, calls["n"])
        self.assertLessEqual(getattr(clf, "_llm_calls_last", calls["n"]), app.MAX_LLM_CALLS_POR_ETIQUETA)
        self.assertTrue(str(et).strip())

    def test_heuristica_salta_llm_si_ya_es_alta_calidad(self):
        clf = app.ClasificadorSubtema(MARCA, ALIAS)
        calls = {"n": 0}

        def boom(*_a, **_k):
            calls["n"] += 1
            raise AssertionError("LLM no debía llamarse")

        blob = (
            "La Universidad Tecnológica de Bolívar lanza una nueva carrera de medicina "
            "deportiva junto al hospital universitario de Cartagena."
        )
        with patch.object(app.openai.ChatCompletion, "create", side_effect=boom):
            et = clf._generar_etiqueta(
                [blob],
                ["UTB lanza carrera de medicina deportiva"],
                [blob],
            )
        self.assertEqual(calls["n"], 0)
        self.assertFalse(app._es_etiqueta_generica(et), et)
        self.assertFalse(app._subtema_de_baja_calidad(et, blob), et)

    def test_validar_completa_sin_llm_por_defecto(self):
        calls = {"n": 0}

        def boom(*_a, **_k):
            calls["n"] += 1
            raise AssertionError("no LLM")

        with patch.object(app.openai.ChatCompletion, "create", side_effect=boom):
            et = app._validar_etiqueta_completa(
                "Lanzamiento de",
                titulos_grp=["UTB lanza carrera de medicina deportiva"],
                resumenes_grp=["La UTB abre medicina deportiva."],
                marca=MARCA, aliases=ALIAS, usar_llm=False,
            )
        self.assertEqual(calls["n"], 0)
        self.assertTrue(str(et).strip())

    def test_umbrales_corpus_grande_no_exigen_090(self):
        u = app._umbrales_adaptativos(313)
        self.assertLessEqual(u["sim_minima_agrupacion"], 0.84)
        self.assertLess(u["sim_minima_agrupacion"], 0.90)
        u_chico = app._umbrales_adaptativos(4)
        self.assertGreaterEqual(u_chico["sim_minima_agrupacion"], 0.90)

    def test_gpt5_nano_se_fuerza_a_default(self):
        env = {
            "OPENAI_CLASIF_MODEL": "gpt-5-nano-2025-08-07",
            "OPENAI_CLASIF_ALLOW_GPT5": "1",
        }
        with patch.dict(__import__("os").environ, env, clear=False):
            modelo = app._resolver_modelo_clasificacion()
        self.assertEqual(modelo, "gpt-4.1-nano-2025-04-14")
        self.assertEqual(modelo, app.MODELO_CLASIF_DEFAULT)
        self.assertTrue(app.advertencia_modelo_clasificacion())

    def test_80_singletons_como_mucho_4_chatcompletions(self):
        """80 grupos no pueden disparar 80 ChatCompletions: solo lotes de 25–40."""
        import json as _json
        n = 80
        clf = app.ClasificadorSubtema(MARCA, ALIAS)
        titulos = [f"Nota institucional {i} del dia" for i in range(n)]
        resumenes = [
            f"Cobertura general de hechos varios {i}. Informacion relevante del sector."
            for i in range(n)
        ]
        col = __import__("pandas").Series(resumenes)
        tit = __import__("pandas").Series(titulos)
        res = __import__("pandas").Series(resumenes)
        calls = {"n": 0, "models": []}
        progress = []

        def fake_create(*_a, **kw):
            calls["n"] += 1
            calls["models"].append(kw.get("model"))
            n_items = 30
            payload = {str(i): f"Hecho institucional {i}" for i in range(n_items)}
            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = _json.dumps(payload)
            resp.choices = [choice]
            resp.get = lambda k, d=None: {} if k == "usage" else d
            return resp

        class _P:
            def progress(self, frac, text=""):
                progress.append(str(text))

        env = {
            "OPENAI_CLASIF_MODEL": "gpt-5-nano-2025-08-07",
            "GRILL_PULIR_SUBTEMAS": "1",
        }
        with patch.dict(__import__("os").environ, env, clear=False), \
             patch.object(app, "get_embeddings_batch", return_value=[None] * n), \
             patch.object(app, "_candidato_subtema_ok", return_value=False), \
             patch.object(app.openai.ChatCompletion, "create", side_effect=fake_create):
            app.refrescar_modelo_clasificacion()
            subtemas = clf.procesar_lote(col, _P(), res, tit)
        self.assertEqual(len(subtemas), n)
        self.assertLessEqual(calls["n"], 4, calls)
        self.assertTrue(calls["models"])
        self.assertTrue(all(m == "gpt-4.1-nano-2025-04-14" for m in calls["models"]), calls["models"])
        uno_a_uno = [
            t for t in progress
            if __import__("re").search(r"Etiquetando\s+\d+\s*/\s*\d+", t)
            and "lote" not in t.lower()
        ]
        self.assertFalse(uno_a_uno, uno_a_uno)
        self.assertTrue(
            any("lote" in t.lower() or "heurístic" in t.lower() or "heuristic" in t.lower()
                for t in progress),
            progress[:8],
        )

    def test_modelo_usado_es_41_nano_aunque_env_sea_gpt5(self):
        import json as _json
        seen = []

        def fake_create(*_a, **kw):
            seen.append(kw.get("model"))
            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = _json.dumps({"0": "Lanzamiento de carrera deportiva"})
            resp.choices = [choice]
            resp.get = lambda k, d=None: {} if k == "usage" else d
            return resp

        env = {"OPENAI_CLASIF_MODEL": "gpt-5-nano-2025-08-07"}
        items = [{
            "idx": 0,
            "texto": "La UTB lanza una carrera de medicina deportiva en Cartagena.",
            "titulo": "UTB lanza carrera",
            "resumen": "La UTB abre medicina deportiva.",
            "heuristica": "Varios",
        }]
        with patch.dict(__import__("os").environ, env, clear=False), \
             patch.object(app.openai.ChatCompletion, "create", side_effect=fake_create):
            app.refrescar_modelo_clasificacion()
            app._pulir_subtemas_en_lotes(items, MARCA, ALIAS)
        self.assertEqual(seen, ["gpt-4.1-nano-2025-04-14"])


class TestContextoTonoFuente(unittest.TestCase):
    def test_contexto_combina_titulo_y_resumen(self):
        ctx = app.extraer_contexto_marca(
            "UTB inaugura laboratorio de biotecnología",
            "La Universidad Tecnológica de Bolívar abrió un laboratorio de biotecnología marina en Cartagena.",
            MARCA, ALIAS,
        )
        self.assertTrue(ctx)
        self.assertIn("laboratorio", ctx.lower())
        self.assertTrue(app._menciona_marca_o_alias(ctx, MARCA, ALIAS))
        self.assertGreaterEqual(len(ctx.split()), 6)

    def test_contexto_no_inventa_marca(self):
        ctx = app.extraer_contexto_marca(
            "Crisis del sector avícola nacional",
            "Los productores piden ayudas al gobierno por el alza de insumos.",
            MARCA, ALIAS,
        )
        self.assertEqual(ctx, "")

    def test_contexto_prioriza_titulo_resumen_sobre_cuerpo(self):
        cuerpo = ("HTML scrap sucio. " * 40) + "La UTB aparece al final del cuerpo sucio."
        ctx = app.extraer_contexto_marca(
            "UTB lanza carrera de medicina",
            "La UTB presenta medicina deportiva en Cartagena.",
            MARCA, ALIAS, cuerpo,
        )
        self.assertIn("medicina", ctx.lower())
        self.assertNotIn("HTML scrap", ctx)
        self.assertTrue(app._menciona_marca_o_alias(ctx, MARCA, ALIAS))

    def test_texto_clasificacion_sigue_orden_marca_resumen_titulo(self):
        texto, hay = app._texto_clasificacion(
            "El gobierno anuncia reforma tributaria nacional",
            "El Congreso debate impuestos. La UTB lanza una carrera de medicina deportiva en Cartagena.",
            MARCA, ALIAS,
        )
        self.assertTrue(hay)
        self.assertIn("carrera", texto.lower())
        self.assertNotIn("reforma tributaria", texto.lower())

    def test_tono_sin_mencion_es_neutro_sin_inventar(self):
        clf = app.ClasificadorTono(MARCA, ALIAS)
        self.assertFalse(clf._menciona_marca("Crisis del sector sin la institución"))
        det = app._tono_determinista(
            "Crisis del sector avícola nacional sin mención institucional",
            MARCA, ALIAS,
        )
        self.assertIsNone(det)

    def test_clasificar_core_sin_llm_expone_columnas(self):
        df = app.clasificar_noticias_core(
            ["UTB lanza carrera de medicina deportiva"],
            ["La Universidad Tecnológica de Bolívar abre medicina deportiva."],
            MARCA, ALIAS, usar_llm=False,
        )
        for col in ("Contexto analizado", "Tono IA", "Tema", "Subtema", "Grupo noticia"):
            self.assertIn(col, df.columns)
        self.assertFalse(app._es_etiqueta_generica(df.loc[0, "Subtema"]), df.loc[0, "Subtema"])

    def test_colab_txt_es_standalone_sin_import_app(self):
        from pathlib import Path
        src = Path(__file__).resolve().parent.joinpath("Grill_API_Colab.txt").read_text(encoding="utf-8")
        self.assertNotIn("import app", src)
        self.assertNotIn("from app", src)
        self.assertIn("clasificar_noticias_core", src)
        self.assertIn("gpt-4.1-nano-2025-04-14", src)
        compile(src, "Grill_API_Colab.txt", "exec")

    def test_colab_tema_claro_y_upload_obvio(self):
        from pathlib import Path
        src = Path(__file__).resolve().parent.joinpath("Grill_API_Colab.txt").read_text(encoding="utf-8")
        self.assertIn("1. Sube el Excel (.xlsx) aquí", src)
        self.assertNotIn("#0d0d0d", src)
        self.assertNotIn("body_background_fill=\"#0d0d0d\"", src)
        self.assertTrue(
            "Soft" in src or "light" in src.lower() or "#f5f5f5" in src or "#ffffff" in src,
            "Colab debe usar tema claro",
        )


class TestVelocidadCorpusGrande(unittest.TestCase):
    """400 filas no pueden hacer n×n SequenceMatcher ni ChatCompletion de subtema/tema."""

    def test_grafo_equivalencia_bloqueado_menos_5000_pares(self):
        n = 400
        titulos = [f"Zeta{i} anuncia hecho puntual {i} en Cali" for i in range(n)]
        resumenes = [f"Resumen corto del hecho {i} en la jornada regional." for i in range(n)]
        app.construir_grafo_equivalencia(titulos, resumenes, marca="ZetaCorp")
        self.assertLess(app._PARES_GRAFO_REVISADOS, 5000, app._PARES_GRAFO_REVISADOS)
        self.assertLess(app._PARES_GRAFO_REVISADOS, n * 20)

    def test_consistencia_400_titulos_menos_2s(self):
        import time as _time
        pd = __import__("pandas")
        n = 400
        titulos = [f"Zeta{i} anuncia hecho puntual {i} en Cali" for i in range(n)]
        resumenes = [f"Resumen corto del hecho {i} en la jornada regional." for i in range(n)]
        df = pd.DataFrame({
            "Título": titulos,
            "Resumen - Aclaracion": resumenes,
            "Tono IA": ["Neutro"] * n,
            "Tema": ["Hecho puntual"] * n,
            "Subtema": [f"Hecho puntual {i}" for i in range(n)],
        })
        t0 = _time.perf_counter()
        with patch.object(app, "get_embeddings_batch", return_value=[None] * n):
            out = app.aplicar_consistencia_grupos(
                df, "Título", "Resumen - Aclaracion", marca="ZetaCorp",
            )
        elapsed = _time.perf_counter() - t0
        self.assertEqual(len(out), n)
        self.assertLess(elapsed, 2.0, elapsed)
        self.assertLess(app._PARES_GRAFO_REVISADOS, 5000, app._PARES_GRAFO_REVISADOS)
        self.assertTrue(all(str(g).startswith("G") for g in out["Grupo noticia"]))

    def test_clasificar_core_default_cero_chatcompletions(self):
        n = 80
        titulos = [
            f"Zeta{i} inaugura laboratorio de biotecnología marina en Cartagena"
            for i in range(n)
        ]
        resumenes = [
            f"La empresa Zeta{i} abre un laboratorio de biotecnología marina en Cartagena."
            for i in range(n)
        ]
        calls = {"n": 0}

        def boom(*_a, **_k):
            calls["n"] += 1
            raise AssertionError("ChatCompletion no debe llamarse con flags por defecto")

        with patch.object(app, "get_embeddings_batch", return_value=[None] * n), \
             patch.object(app.openai.ChatCompletion, "create", side_effect=boom), \
             patch.dict(__import__("os").environ, {
                 "GRILL_PULIR_SUBTEMAS": "0",
                 "GRILL_PULIR_TEMAS": "0",
                 "GRILL_PULIR_TONO": "0",
             }, clear=False):
            df = app.clasificar_noticias_core(titulos, resumenes, "ZetaCorp", usar_llm=True)
        self.assertEqual(calls["n"], 0)
        self.assertEqual(len(df), n)
        self.assertIn("Grupo noticia", df.columns)
        self.assertIn("Subtema", df.columns)
        self.assertTrue(all(not app._es_etiqueta_generica(s) for s in df["Subtema"].tolist()[:5]))


if __name__ == "__main__":
    unittest.main()
