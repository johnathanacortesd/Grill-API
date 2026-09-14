# ======================================
# Casos dorados y reglas SPEC_TONO_TEMA
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
    DEFAULT_CUBOS,
    SUBTEMA_MAX_WORDS,
    SUBTEMA_MIN_WORDS,
    _call_openai_cluster,
    apply_tone_guards,
    assign_closed_tema,
    check_exact_byline_rule,
    extract_brand_context,
    generate_brand_variants,
    has_brand_evidence,
    mask_similar_entities,
    parse_alias_list,
    snap_to_cubo,
    validate_or_repair_subtema,
)

CASES_PATH = os.path.join(os.path.dirname(__file__), "casos_dorados.json")


def _load_golden():
    with open(CASES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _ctx_for(case, fixture):
    brand = fixture["brand"]
    aliases = fixture["aliases"]
    regexes = generate_brand_variants(brand, aliases)
    return extract_brand_context(
        case["body"], case["title"], regexes, brand=brand, aliases=aliases
    )


class AliasParseTests(unittest.TestCase):
    def test_split_comma_semicolon_newline(self):
        self.assertEqual(
            parse_alias_list("UAO, Autónoma; Occidente\nUTB"),
            ["UAO", "Autónoma", "Occidente", "UTB"],
        )

    def test_split_nested_list_items(self):
        self.assertEqual(
            parse_alias_list(["UAO, U.A.O.", "Autónoma de Occidente"]),
            ["UAO", "U.A.O.", "Autónoma de Occidente"],
        )

    def test_generate_brand_variants_splits_aliases(self):
        regexes = generate_brand_variants("Marca", ["UAO; U.A.O.\nAlma Mater"])
        blob = "visita de la uao y del alma mater"
        self.assertTrue(any(__import__("re").search(rx, blob) for rx in regexes))


class BrandEvidenceTests(unittest.TestCase):
    def test_no_concat_before_match_excludes_foreign_tragedy(self):
        fixture = _load_golden()
        case = next(c for c in fixture["cases"] if c["id"] == "positivo_brand_actor")
        ctx = _ctx_for(case, fixture)
        self.assertTrue(has_brand_evidence(ctx))
        self.assertIn("aporta", ctx.lower())
        self.assertNotIn("20 muertos", ctx.lower())
        self.assertNotIn("tragedia nacional", ctx.lower())

    def test_title_and_body_split_separately(self):
        brand = "UAO"
        aliases = ["Universidad Autónoma de Occidente"]
        regexes = generate_brand_variants(brand, aliases)
        ctx = extract_brand_context(
            "Otras universidades denuncian recortes. La UAO lanza becas nuevas.",
            "Crisis educativa nacional deja miles de afectados",
            regexes,
            brand=brand,
            aliases=aliases,
        )
        self.assertIn("lanza becas", ctx.lower())
        self.assertNotIn("crisis educativa nacional", ctx.lower())
        self.assertNotIn("otras universidades denuncian", ctx.lower())

    def test_mask_similar_entities_before_match(self):
        brand = "Universidad Autónoma de Occidente"
        regexes = generate_brand_variants(brand, ["UAO"])
        text = "La Universidad Nacional y la Universidad Autónoma de Occidente firmaron un convenio."
        masked = mask_similar_entities(text, regexes)
        self.assertIn("[ENTIDAD]", masked)
        self.assertIn("Universidad Autónoma de Occidente", masked)
        ctx = extract_brand_context(text, "Titular ajeno", regexes, brand=brand, aliases=["UAO"])
        self.assertIn("Autónoma de Occidente", ctx)
        self.assertNotIn("Titular ajeno", ctx)


class GoldenCasesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = _load_golden()
        cls.brand = cls.fixture["brand"]
        cls.aliases = cls.fixture["aliases"]
        cls.regexes = generate_brand_variants(cls.brand, cls.aliases)

    def test_cubo_count(self):
        self.assertEqual(len(DEFAULT_CUBOS), 21)
        self.assertNotIn("Otros", DEFAULT_CUBOS)

    def test_each_golden_case(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                ctx = extract_brand_context(
                    case["body"],
                    case["title"],
                    self.regexes,
                    brand=self.brand,
                    aliases=self.aliases,
                )
                if case["expect_brand_evidence"]:
                    self.assertTrue(has_brand_evidence(ctx), msg=f"{case['id']} ctx={ctx!r}")
                else:
                    self.assertFalse(has_brand_evidence(ctx), msg=f"{case['id']} ctx={ctx!r}")
                    self.assertEqual(ctx, "")

                for needle in case.get("evidence_must_include") or []:
                    self.assertIn(needle.lower(), ctx.lower(), msg=case["id"])
                for needle in case.get("evidence_must_not_include") or []:
                    self.assertNotIn(needle.lower(), ctx.lower(), msg=case["id"])

                if case["id"] == "byline":
                    scope = f"{case['title']} {ctx} {case['body']}"
                    self.assertTrue(check_exact_byline_rule(scope, self.brand, self.aliases))
                    tono, tema, subtema = _call_openai_cluster(
                        client=MagicMock(),
                        model="test",
                        brand=self.brand,
                        aliases=self.aliases,
                        brand_regexes=self.regexes,
                        ctx=ctx,
                        title_ref=case["title"],
                    )
                    self.assertEqual(tono, "Neutro")
                    self.assertEqual(tema, case["expected_tema"])
                    self.assertEqual(subtema, case["expected_subtema"])
                    continue

                tono = apply_tone_guards(
                    case["llm_tono"],
                    ctx,
                    self.brand,
                    self.aliases,
                    self.regexes,
                )
                self.assertEqual(tono, case["expected_tono"], msg=f"{case['id']} ctx={ctx!r}")


class SubtemaAndTemaTests(unittest.TestCase):
    def test_subtema_validator_clips_and_repairs(self):
        long_txt = "Apertura de la nueva sede norte para ampliar cobertura educativa regional"
        clipped = validate_or_repair_subtema(
            long_txt, "UAO", "Apertura de la nueva sede norte en Cali", ""
        )
        n = len(clipped.split())
        self.assertGreaterEqual(n, SUBTEMA_MIN_WORDS)
        self.assertLessEqual(n, SUBTEMA_MAX_WORDS)

        repaired = validate_or_repair_subtema(
            "Sede",
            "UAO",
            "Apertura de sede norte en Cali",
            "La universidad inauguró una sede para ampliar cobertura.",
        )
        self.assertGreaterEqual(len(repaired.split()), SUBTEMA_MIN_WORDS)
        self.assertLessEqual(len(repaired.split()), SUBTEMA_MAX_WORDS)

    def test_never_ship_otros(self):
        self.assertIsNone(snap_to_cubo("Otros"))
        self.assertIsNone(snap_to_cubo("otro"))
        tema = assign_closed_tema(
            "Otros",
            "Apertura de sede norte",
            "Apertura de la nueva sede norte en Cali",
        )
        self.assertNotEqual(tema.lower(), "otros")
        self.assertIn(tema, DEFAULT_CUBOS)

    def test_closed_cubo_keeps_valid_llm_label(self):
        self.assertEqual(
            assign_closed_tema("Educación Superior", "Apertura de sede norte", "x"),
            "Educación Superior",
        )


class DualPromptTests(unittest.TestCase):
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

    def test_blocks_a_tone_and_b_subtema_when_brand_evidence(self):
        brand = "Universidad Autónoma de Occidente"
        aliases = ["UAO"]
        regexes = generate_brand_variants(brand, aliases)
        ctx = "La UAO aporta donaciones y respalda a las familias afectadas."
        client, calls = self._fake_client(
            {"tono": "Neutro", "tema": "Otros", "subtema": "Aporte humanitario institucional"}
        )
        tono, tema, subtema = _call_openai_cluster(
            client, "gpt-test", brand, aliases, regexes, ctx,
            "Titular de referencia de aporte",
            request_tone=True, request_theme=True,
        )
        self.assertEqual(len(calls), 1)
        system = calls[0]["messages"][0]["content"]
        user = calls[0]["messages"][1]["content"]
        self.assertIn("ASPECTUAL", system.upper())
        self.assertIn("BLOQUE A", system.upper())
        self.assertIn("BLOQUE B", system.upper())
        self.assertIn("BLOQUE A", user.upper())
        self.assertIn("BLOQUE B", user.upper())
        self.assertEqual(tono, "Positivo")
        self.assertNotEqual(tema.lower(), "otros")
        self.assertIn(tema, DEFAULT_CUBOS)
        n = len(subtema.split())
        self.assertGreaterEqual(n, SUBTEMA_MIN_WORDS)
        self.assertLessEqual(n, SUBTEMA_MAX_WORDS)

    def test_skips_tone_block_without_brand_evidence(self):
        brand = "UAO"
        regexes = generate_brand_variants(brand, [])
        client, calls = self._fake_client(
            {"tema": "Gobierno y Política", "subtema": "Reforma tributaria nacional debate"}
        )
        tono, tema, _sub = _call_openai_cluster(
            client, "gpt-test", brand, [], regexes, "",
            "Gobierno anuncia reforma tributaria nacional",
            request_tone=True, request_theme=True,
        )
        self.assertEqual(tono, "Neutro")
        user = calls[0]["messages"][1]["content"]
        self.assertNotIn("BLOQUE A — TONO", user)
        self.assertIn("BLOQUE B", user.upper())
        self.assertNotEqual(tema.lower(), "otros")


if __name__ == "__main__":
    unittest.main()
