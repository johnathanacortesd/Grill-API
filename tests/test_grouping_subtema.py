# ======================================
# Recall-biased grouping: same fact → same Subtema_IA
# ======================================
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai_analyzer import (  # noqa: E402
    canonicalize_subtopics,
    cluster_similar_rows,
    enrich_rows_with_ai,
    extract_brand_context,
    generate_brand_variants,
    subtema_has_fact_fidelity,
)
from pipeline import KEY_MAP  # noqa: E402

BRAND = "Universidad Autónoma de Occidente"
ALIASES = ["UAO"]


def _regexes():
    return generate_brand_variants(BRAND, ALIASES)


def _row(title, body):
    regexes = _regexes()
    ctx = extract_brand_context(body, title, regexes, brand=BRAND, aliases=ALIASES)
    return {
        "Título": title,
        "Resumen - Aclaracion": body,
        "Contexto analizado": ctx,
        "is_duplicate": False,
    }


def _same_cluster(rows):
    cmap = cluster_similar_rows(rows, KEY_MAP, _regexes())
    return cmap, len(set(cmap.values())) == 1


class ParaphraseSharesSubtemaTests(unittest.TestCase):
    def test_paraphrased_republications_same_cluster_and_subtema(self):
        body = (
            "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede "
            "en el norte de Cali para ampliar cobertura educativa. El rector destacó la inversión."
        )
        rows = [
            _row("Inauguración de la sede norte de la UAO en Cali", body),
            _row(
                "La UAO abre su sede norte para ampliar cobertura en Cali",
                body + " El rector destacó la inversión realizada.",
            ),
        ]
        cmap, same = _same_cluster(rows)
        self.assertTrue(same, msg=cmap)
        with patch("ai_analyzer.OpenAI"):
            with patch("ai_analyzer._call_openai_cluster") as mock_llm:
                mock_llm.return_value = (
                    "Positivo",
                    "Infraestructura",
                    "Apertura de sede norte",
                )
                out = enrich_rows_with_ai(rows, KEY_MAP, BRAND, ALIASES, "sk-test")
        self.assertEqual(mock_llm.call_count, 1)
        self.assertEqual(out[0]["Subtema_IA"], out[1]["Subtema_IA"])
        self.assertEqual(out[0]["Subtema_IA"], "Apertura de sede norte")

    def test_enrich_does_not_rewrite_shared_subtema_when_titles_differ(self):
        body = (
            "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede "
            "en el norte de Cali para ampliar cobertura educativa. El rector destacó la inversión."
        )
        rows = [
            _row("Inauguración de la sede norte de la UAO en Cali", body),
            _row(
                "La UAO abre su sede norte para ampliar cobertura en Cali",
                body + " El rector destacó la inversión realizada.",
            ),
        ]
        with patch("ai_analyzer.OpenAI"):
            with patch("ai_analyzer._call_openai_cluster") as mock_llm:
                mock_llm.return_value = (
                    "Positivo",
                    "Infraestructura",
                    "Puesta en marcha campus norte",
                )
                out = enrich_rows_with_ai(rows, KEY_MAP, BRAND, ALIASES, "sk-test")
        self.assertEqual(out[0]["Subtema_IA"], out[1]["Subtema_IA"])
        self.assertEqual(out[0]["Subtema_IA"], "Puesta en marcha campus norte")
        self.assertNotEqual(out[0]["Subtema_IA"], out[0]["Título"])
        self.assertNotEqual(out[1]["Subtema_IA"], out[1]["Título"])


class DifferentFactsSoftPreferenceTests(unittest.TestCase):
    def test_inauguracion_vs_convenio_preferably_separate(self):
        # Soft preference: different actions should stay apart. If a future
        # recall tweak merges them, document the tradeoff — do not restore
        # brand-evidence-only merges to "fix" this.
        rows = [
            _row(
                "UAO inaugura sede norte en Cali",
                "La Universidad Autónoma de Occidente inauguró una sede para ampliar cobertura educativa en el norte de Cali.",
            ),
            _row(
                "UAO firma convenio de investigación en Cali",
                "La Universidad Autónoma de Occidente firmó un convenio de investigación con empresas del Valle del Cauca.",
            ),
        ]
        _cmap, same = _same_cluster(rows)
        self.assertFalse(same)


class SoftFidelityKeepsLlmTests(unittest.TestCase):
    def test_soft_fidelity_does_not_treat_synonym_as_garbage(self):
        self.assertTrue(
            subtema_has_fact_fidelity(
                "Puesta en marcha campus norte",
                "UAO inaugura nueva sede en el norte de Cali",
                "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede en el norte de Cali.",
                BRAND,
            )
        )
        self.assertFalse(
            subtema_has_fact_fidelity(
                "Reforma tributaria nacional debate",
                "UAO inaugura nueva sede en el norte de Cali",
                "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede en el norte de Cali.",
                BRAND,
            )
        )


class CanonizeSynonymAndFactTests(unittest.TestCase):
    def test_unifies_synonym_subtemas_around_80(self):
        results = {
            0: ("Neutro", "Infraestructura", "Apertura de sede norte"),
            1: ("Neutro", "Infraestructura", "Apertura de campus norte"),
        }
        out = canonicalize_subtopics(results)
        self.assertEqual(out[0][2], out[1][2])

    def test_unifies_leftover_clusters_with_similar_fact_context(self):
        body = (
            "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede "
            "en el norte de Cali para ampliar cobertura educativa."
        )
        results = {
            0: ("Positivo", "Infraestructura", "Apertura de sede norte"),
            1: ("Positivo", "Infraestructura", "Inauguración de campus norte"),
        }
        ctxs = {
            0: f"Inauguración de la sede norte de la UAO en Cali. {body}",
            1: f"La UAO abre su sede norte para ampliar cobertura en Cali. {body}",
        }
        out = canonicalize_subtopics(results, ctxs)
        self.assertEqual(out[0][2], out[1][2])

    def test_brand_evidence_alone_does_not_unify(self):
        results = {
            0: ("Positivo", "Infraestructura", "Apertura de sede norte"),
            1: ("Positivo", "Investigación y Ciencia", "Convenio de investigación empresarial"),
        }
        brand_only = {
            0: "La Universidad Autónoma de Occidente inauguró una sede en Cali.",
            1: "La Universidad Autónoma de Occidente firmó un convenio en Cali.",
        }
        out = canonicalize_subtopics(results, brand_only)
        self.assertEqual(out[0][2], "Apertura de sede norte")
        self.assertEqual(out[1][2], "Convenio de investigación empresarial")


if __name__ == "__main__":
    unittest.main()
