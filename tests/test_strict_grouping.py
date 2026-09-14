# ======================================
# Agrupación estricta por mismo hecho + fidelidad de subtema
# ======================================
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai_analyzer import (  # noqa: E402
    _call_openai_cluster,
    build_fact_context,
    canonicalize_subtopics,
    cluster_similar_rows,
    enrich_rows_with_ai,
    extract_brand_context,
    generate_brand_variants,
    subtema_has_fact_fidelity,
    validate_or_repair_subtema,
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


def _clustered(rows):
    cmap = cluster_similar_rows(rows, KEY_MAP, _regexes())
    return cmap, len(set(cmap.values())) == 1


class MustNotClusterDifferentFactsTests(unittest.TestCase):
    def test_same_brand_city_different_facts(self):
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
        _cmap, same = _clustered(rows)
        self.assertFalse(same)

    def test_protests_vs_scholarships_same_brand_city(self):
        rows = [
            _row(
                "Estudiantes de la UAO protestan en Cali por alza de matrículas",
                "Los estudiantes de la Universidad Autónoma de Occidente se movilizaron en Cali contra el incremento de matrículas.",
            ),
            _row(
                "La UAO lanza nuevas becas de posgrado en Cali",
                "La Universidad Autónoma de Occidente anunció becas de posgrado para estudiantes de Cali y el Valle.",
            ),
        ]
        _cmap, same = _clustered(rows)
        self.assertFalse(same)

    def test_same_event_anchor_without_distinctive_overlap(self):
        rows = [
            _row(
                "Universidad Autónoma: inaugura sede norte",
                "La UAO inauguró su sede norte para ampliar cobertura.",
            ),
            _row(
                "Universidad Autónoma: denuncia recortes presupuestales",
                "La UAO denunció recortes presupuestales que afectan investigación.",
            ),
        ]
        _cmap, same = _clustered(rows)
        self.assertFalse(same)

    def test_two_word_lead_only_is_not_enough(self):
        rows = [
            _row(
                "Rector anuncia ampliación de cobertura en el norte",
                "El rector de la UAO anunció ampliación de cobertura en el campus norte.",
            ),
            _row(
                "Rector anuncia recorte de presupuestos de investigación",
                "El rector de la UAO anunció recortes en los presupuestos de investigación.",
            ),
        ]
        _cmap, same = _clustered(rows)
        self.assertFalse(same)


class MustClusterRepublicationsTests(unittest.TestCase):
    def test_near_identical_title_and_body(self):
        rows = [
            _row(
                "UAO inaugura nueva sede en el norte de Cali",
                "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede en el norte de Cali para ampliar cobertura educativa.",
            ),
            _row(
                "La UAO inaugura nueva sede en el norte de Cali",
                "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede en el norte de Cali para ampliar la cobertura educativa regional.",
            ),
        ]
        _cmap, same = _clustered(rows)
        self.assertTrue(same)

    def test_paraphrased_title_same_body(self):
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
        _cmap, same = _clustered(rows)
        self.assertTrue(same)


class CanonizationNoCrossFactTests(unittest.TestCase):
    def test_does_not_rewrite_subtema_from_similar_brand_context(self):
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
        results = {
            0: ("Positivo", "Infraestructura", "Apertura de sede norte"),
            1: ("Positivo", "Investigación y Ciencia", "Convenio de investigación empresarial"),
        }
        ctxs = {0: rows[0]["Contexto analizado"], 1: rows[1]["Contexto analizado"]}
        out = canonicalize_subtopics(results, ctxs)
        self.assertEqual(out[0][2], "Apertura de sede norte")
        self.assertEqual(out[1][2], "Convenio de investigación empresarial")
        self.assertNotEqual(out[0][1], out[1][1])
        self.assertEqual(out[0][0], "Positivo")
        self.assertEqual(out[1][0], "Positivo")

    def test_unifies_only_near_identical_subtema_strings(self):
        results = {
            0: ("Neutro", "Infraestructura", "Apertura de sede norte"),
            1: ("Neutro", "Infraestructura", "Apertura de sede norte"),
        }
        out = canonicalize_subtopics(results, {0: "x" * 80, 1: "y" * 80})
        self.assertEqual(out[0][2], out[1][2])
        self.assertEqual(out[0][2], "Apertura de sede norte")


class FactContextAndFidelityTests(unittest.TestCase):
    def test_build_fact_context_is_title_plus_body(self):
        fact = build_fact_context(
            "UAO inaugura sede norte en Cali",
            "El rector cortó la cinta en el campus norte.",
        )
        self.assertIn("UAO inaugura sede norte", fact)
        self.assertIn("rector cortó la cinta", fact)

    def test_fidelity_fails_garbage_unrelated_to_title_body(self):
        self.assertFalse(
            subtema_has_fact_fidelity(
                "Reforma tributaria nacional debate",
                "Apertura de la nueva sede norte en Cali",
                "La universidad inauguró una sede para ampliar cobertura educativa.",
                BRAND,
            )
        )

    def test_fidelity_passes_when_subtema_words_are_in_title(self):
        self.assertTrue(
            subtema_has_fact_fidelity(
                "Apertura de sede norte",
                "Apertura de la nueva sede norte en Cali",
                "La universidad inauguró una sede para ampliar cobertura educativa.",
                BRAND,
            )
        )

    def test_repair_prefers_title_not_hecho_puntual(self):
        repaired = validate_or_repair_subtema(
            "Sede",
            "UAO",
            "Apertura de sede norte en Cali",
            "La universidad inauguró una sede.",
        )
        self.assertNotIn("hecho puntual", repaired.lower())
        self.assertGreaterEqual(len(repaired.split()), 3)

    def _fake_client(self, payload):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            msg = MagicMock()
            msg.content = json.dumps(payload)
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        return client, calls

    def test_bloque_b_prompt_includes_fact_context(self):
        regexes = _regexes()
        brand_ctx = "La UAO aporta donaciones y respalda a las familias afectadas."
        fact = (
            "UAO inaugura sede norte en Cali. "
            "El rector cortó la cinta de la nueva sede en el norte."
        )
        client, calls = self._fake_client(
            {"tono": "Positivo", "tema": "Infraestructura", "subtema": "Apertura de sede norte"}
        )
        _call_openai_cluster(
            client,
            "gpt-test",
            BRAND,
            ALIASES,
            regexes,
            brand_ctx,
            "UAO inaugura sede norte en Cali",
            request_tone=True,
            request_theme=True,
            fact_ctx=fact,
        )
        self.assertEqual(len(calls), 1)
        user = calls[0]["messages"][1]["content"]
        self.assertIn("BLOQUE A", user.upper())
        self.assertIn("BLOQUE B", user.upper())
        self.assertIn("Contexto del hecho", user)
        self.assertIn(fact, user)
        self.assertIn("BLOQUE A", calls[0]["messages"][0]["content"].upper())

    def test_llm_garbage_subtema_is_repaired_from_group_title(self):
        regexes = _regexes()
        title = "Apertura de la nueva sede norte en Cali"
        body = "La universidad inauguró una sede para ampliar cobertura educativa."
        client, _calls = self._fake_client(
            {"tono": "Neutro", "tema": "Gestión Tributaria", "subtema": "Reforma tributaria nacional debate"}
        )
        _tono, _tema, subtema = _call_openai_cluster(
            client,
            "gpt-test",
            BRAND,
            ALIASES,
            regexes,
            "La UAO inauguró una sede.",
            title,
            request_tone=True,
            request_theme=True,
            fact_ctx=build_fact_context(title, body),
        )
        self.assertTrue(subtema_has_fact_fidelity(subtema, title, body, BRAND))
        self.assertNotIn("tributar", subtema.lower())
        self.assertNotIn("reforma", subtema.lower())


class EnrichRowsUsesOwnFactContextTests(unittest.TestCase):
    def test_different_facts_do_not_share_subtema(self):
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
        with patch("ai_analyzer.OpenAI"):
            with patch("ai_analyzer._call_openai_cluster") as mock_llm:
                mock_llm.return_value = (
                    "Neutro",
                    "Gestión Tributaria",
                    "Reforma tributaria nacional debate",
                )
                out = enrich_rows_with_ai(rows, KEY_MAP, BRAND, ALIASES, "sk-test")
        self.assertEqual(mock_llm.call_count, 2)
        self.assertTrue(all("fact_ctx" in (c.kwargs or {}) for c in mock_llm.call_args_list))
        self.assertNotEqual(out[0]["Subtema_IA"], out[1]["Subtema_IA"])
        self.assertNotIn("reforma", out[0]["Subtema_IA"].lower())
        self.assertNotIn("reforma", out[1]["Subtema_IA"].lower())
        self.assertTrue(
            subtema_has_fact_fidelity(
                out[0]["Subtema_IA"],
                rows[0]["Título"],
                rows[0]["Resumen - Aclaracion"],
                BRAND,
            )
        )
        self.assertTrue(
            subtema_has_fact_fidelity(
                out[1]["Subtema_IA"],
                rows[1]["Título"],
                rows[1]["Resumen - Aclaracion"],
                BRAND,
            )
        )

    def test_republication_still_one_llm_call(self):
        rows = [
            _row(
                "UAO inaugura nueva sede en el norte de Cali",
                "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede en el norte de Cali para ampliar cobertura educativa.",
            ),
            _row(
                "La UAO inaugura nueva sede en el norte de Cali",
                "La Universidad Autónoma de Occidente inauguró este lunes su nueva sede en el norte de Cali para ampliar la cobertura educativa regional.",
            ),
        ]
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


if __name__ == "__main__":
    unittest.main()
