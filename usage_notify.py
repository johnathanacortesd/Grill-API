# ======================================
# Notificación opcional de uso por correo
# ======================================
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Mapping, Optional

logger = logging.getLogger("limpieza_grill")

APP_NAME = "Grill-API"

REQUIRED_SECRET_KEYS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "USAGE_NOTIFY_EMAIL",
)

SMTP_TIMEOUT_SECONDS = 20


def _get_secret(secrets_like: Optional[Mapping[str, Any]], key: str) -> str:
    """Lee una clave desde un dict-like (p. ej. st.secrets) y, si falta, desde el entorno."""
    raw = None
    if secrets_like is not None:
        getter = getattr(secrets_like, "get", None)
        if callable(getter):
            try:
                raw = getter(key)
            except Exception:
                raw = None
        else:
            try:
                raw = secrets_like[key]  # type: ignore[index]
            except Exception:
                raw = None
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get(key)
    if raw is None:
        return ""
    return str(raw).strip()


def smtp_configured(secrets_like: Optional[Mapping[str, Any]] = None) -> bool:
    """True si están todas las claves SMTP_* y USAGE_NOTIFY_EMAIL (secrets o env)."""
    return all(_get_secret(secrets_like, key) for key in REQUIRED_SECRET_KEYS)


def _smtp_settings(secrets_like: Optional[Mapping[str, Any]]) -> Optional[dict]:
    values = {key: _get_secret(secrets_like, key) for key in REQUIRED_SECRET_KEYS}
    if not all(values.values()):
        return None
    try:
        port = int(values["SMTP_PORT"])
    except (TypeError, ValueError):
        logger.info("SMTP_PORT inválido; se omite la notificación de uso.")
        return None
    if port <= 0:
        logger.info("SMTP_PORT inválido; se omite la notificación de uso.")
        return None
    values["SMTP_PORT"] = port
    return values


def _display_or_na(value: Any) -> str:
    if value is None:
        return "N/A"
    text = str(value).strip()
    return text if text else "N/A"


def build_usage_subject(*, brand: Any = None, dossier_name: Any = None) -> str:
    label = _display_or_na(brand)
    if label == "N/A":
        label = _display_or_na(dossier_name)
    if label == "N/A":
        label = "dossier"
    return f"[Grill-API] Análisis completado — {label}"


def build_usage_body(
    *,
    brand: Any = None,
    dossier_name: Any = None,
    total_rows: Any = None,
    unique_rows: Any = None,
    duplicates: Any = None,
    duration: Any = None,
    output_filename: Any = None,
    timestamp: Optional[datetime] = None,
) -> str:
    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts_utc = ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "Se completó un análisis en Grill-API.\n"
        "\n"
        f"Aplicación: {APP_NAME}\n"
        f"Fecha y hora: {ts_utc}\n"
        f"Marca / cliente: {_display_or_na(brand)}\n"
        f"Archivo de entrada: {_display_or_na(dossier_name)}\n"
        f"Archivo de salida: {_display_or_na(output_filename)}\n"
        "\n"
        f"Registros totales: {_display_or_na(total_rows)}\n"
        f"Únicos: {_display_or_na(unique_rows)}\n"
        f"Duplicados: {_display_or_na(duplicates)}\n"
        f"Duración: {_display_or_na(duration)}\n"
        "\n"
        "Este correo es una notificación automática de uso.\n"
    )


def send_usage_notification(
    secrets_like: Optional[Mapping[str, Any]] = None,
    *,
    brand: Any = None,
    dossier_name: Any = None,
    total_rows: Any = None,
    unique_rows: Any = None,
    duplicates: Any = None,
    duration: Any = None,
    output_filename: Any = None,
    timestamp: Optional[datetime] = None,
) -> bool:
    """Envía un correo de uso. No lanza: si falta config o SMTP falla, solo registra el evento."""
    try:
        settings = _smtp_settings(secrets_like)
        if not settings:
            logger.info(
                "Notificación de uso omitida: faltan SMTP_* o USAGE_NOTIFY_EMAIL en secrets/entorno."
            )
            return False

        msg = EmailMessage()
        msg["Subject"] = build_usage_subject(brand=brand, dossier_name=dossier_name)
        msg["From"] = settings["SMTP_FROM"]
        msg["To"] = settings["USAGE_NOTIFY_EMAIL"]
        msg.set_content(
            build_usage_body(
                brand=brand,
                dossier_name=dossier_name,
                total_rows=total_rows,
                unique_rows=unique_rows,
                duplicates=duplicates,
                duration=duration,
                output_filename=output_filename,
                timestamp=timestamp,
            )
        )

        with smtplib.SMTP(
            settings["SMTP_HOST"],
            settings["SMTP_PORT"],
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
            smtp.send_message(msg)

        logger.info("Notificación de uso enviada a %s", settings["USAGE_NOTIFY_EMAIL"])
        return True
    except Exception:
        logger.exception("Fallo al enviar la notificación de uso; el análisis no se interrumpe.")
        return False
