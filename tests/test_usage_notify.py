# ======================================
# Pruebas de notificación opcional de uso
# ======================================
import os
import smtplib
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from usage_notify import (  # noqa: E402
    build_usage_body,
    build_usage_subject,
    send_usage_notification,
    smtp_configured,
)

COMPLETE_SECRETS = {
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "notify-example@gmail.com",
    "SMTP_PASSWORD": "fake-app-password",
    "SMTP_FROM": "notify-example@gmail.com",
    "USAGE_NOTIFY_EMAIL": "ops-example@example.com",
}


def _smtp_mock():
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.__exit__.return_value = False
    return smtp


class SmtpConfiguredTests(unittest.TestCase):
    def test_true_when_all_keys_present(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(smtp_configured(COMPLETE_SECRETS))

    def test_false_when_a_key_is_missing(self):
        incomplete = dict(COMPLETE_SECRETS)
        incomplete.pop("SMTP_PASSWORD")
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(smtp_configured(incomplete))

    def test_false_when_a_key_is_blank(self):
        blank = dict(COMPLETE_SECRETS)
        blank["USAGE_NOTIFY_EMAIL"] = "   "
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(smtp_configured(blank))

    def test_reads_from_environment_when_secrets_empty(self):
        with patch.dict(os.environ, COMPLETE_SECRETS, clear=True):
            self.assertTrue(smtp_configured({}))


class SendUsageNotificationTests(unittest.TestCase):
    def test_sends_when_configured(self):
        smtp = _smtp_mock()
        ts = datetime(2026, 9, 14, 23, 15, tzinfo=timezone.utc)
        with patch.dict(os.environ, {}, clear=True):
            with patch("usage_notify.smtplib.SMTP", return_value=smtp) as smtp_cls:
                sent = send_usage_notification(
                    COMPLETE_SECRETS,
                    brand="Ecopetrol",
                    dossier_name="dossier_cliente.xlsx",
                    total_rows=120,
                    unique_rows=100,
                    duplicates=20,
                    duration="12.34s",
                    output_filename="Dossier_Ecopetrol_20260914_2315.xlsx",
                    timestamp=ts,
                )

        self.assertTrue(sent)
        smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=20)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with(
            "notify-example@gmail.com", "fake-app-password"
        )
        smtp.send_message.assert_called_once()
        msg = smtp.send_message.call_args.args[0]
        self.assertEqual(msg["Subject"], "[Grill-API] Análisis completado — Ecopetrol")
        self.assertEqual(msg["From"], "notify-example@gmail.com")
        self.assertEqual(msg["To"], "ops-example@example.com")
        body = msg.get_content()
        self.assertIn("Grill-API", body)
        self.assertIn("2026-09-14 23:15:00 UTC", body)
        self.assertIn("Ecopetrol", body)
        self.assertIn("120", body)
        self.assertIn("100", body)
        self.assertIn("20", body)
        self.assertIn("12.34s", body)
        self.assertIn("Dossier_Ecopetrol_20260914_2315.xlsx", body)

    def test_subject_falls_back_to_dossier_name(self):
        self.assertEqual(
            build_usage_subject(brand="", dossier_name="noticias.xlsx"),
            "[Grill-API] Análisis completado — noticias.xlsx",
        )

    def test_body_includes_metrics(self):
        body = build_usage_body(
            brand="Bancolombia",
            total_rows=10,
            unique_rows=8,
            duplicates=2,
            duration="1.00s",
            output_filename="out.xlsx",
            timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
        self.assertIn("Marca / cliente: Bancolombia", body)
        self.assertIn("Registros totales: 10", body)
        self.assertIn("Únicos: 8", body)
        self.assertIn("Duplicados: 2", body)
        self.assertIn("Duración: 1.00s", body)
        self.assertIn("Archivo de salida: out.xlsx", body)

    def test_noop_when_secrets_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("usage_notify.smtplib.SMTP") as smtp_cls:
                sent = send_usage_notification(
                    {},
                    brand="Ecopetrol",
                    total_rows=1,
                    unique_rows=1,
                    duplicates=0,
                    duration="0.10s",
                    output_filename="out.xlsx",
                )

        self.assertFalse(sent)
        smtp_cls.assert_not_called()

    def test_failure_does_not_raise(self):
        smtp = _smtp_mock()
        smtp.send_message.side_effect = smtplib.SMTPException("boom")
        with patch.dict(os.environ, {}, clear=True):
            with patch("usage_notify.smtplib.SMTP", return_value=smtp):
                sent = send_usage_notification(
                    COMPLETE_SECRETS,
                    brand="Ecopetrol",
                    total_rows=3,
                    unique_rows=3,
                    duplicates=0,
                    duration="2.00s",
                    output_filename="out.xlsx",
                )

        self.assertFalse(sent)

    def test_login_failure_does_not_raise(self):
        smtp = _smtp_mock()
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
        with patch.dict(os.environ, {}, clear=True):
            with patch("usage_notify.smtplib.SMTP", return_value=smtp):
                sent = send_usage_notification(COMPLETE_SECRETS)

        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
