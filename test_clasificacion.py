"""Regression tests for tema / subtema / tono / grouping in app.py.

Streamlit is mocked so the module can be imported without a running server.
"""
import io
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
    def test_pkl_generico_se_reemplaza(self):
        from sklearn.pipeline import make_pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
        import joblib

        pipe = make_pipeline(TfidfVectorizer(), MultinomialNB())
        pipe.fit(
            [
                "lanzamiento carrera deportiva utb",
                "convenio formacion profesional sena",
            ],
            ["Cobertura de información relevante", "Educación, formación"],
        )
        buf = io.BytesIO()
        joblib.dump(pipe, buf)
        buf.seek(0)
        titulos = ["UTB lanza carrera de medicina deportiva"]
        resumenes = ["La Universidad Tecnológica de Bolívar abre medicina deportiva."]
        textos = [app._texto_clasificacion(titulos[0], resumenes[0], MARCA, ALIAS)[0]]
        preds = app.analizar_temas_con_pkl(textos, buf)
        self.assertIsNotNone(preds)
        temas = app._etiquetas_desde_pkl_o_heuristica(preds, titulos, resumenes, MARCA, ALIAS)
        self.assertEqual(len(temas), 1)
        self.assertFalse(app._es_etiqueta_generica(temas[0]), temas[0])
        self.assertNotIn(",", temas[0])

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


if __name__ == "__main__":
    unittest.main()
