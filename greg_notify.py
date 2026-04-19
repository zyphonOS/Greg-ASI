from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


def send_email(to_addr: str, subject: str, body: str) -> dict:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM") or user
    if not all([host, port, user, password, sender]):
        return {"ok": False, "error": "SMTP not configured"}
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = to_addr
        message.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(sender, to_addr, message.as_string())
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def send_zyphon_email(subject: str, body: str, flag_name: str = "GREG_ENABLE_EMAIL_FEATURES") -> dict:
    if (os.getenv(flag_name) or "").strip().lower() not in {"1", "true", "yes", "on"}:
        return {"ok": False, "skipped": True, "reason": "feature_disabled"}
    to_addr = os.getenv("ZYPHON_EMAIL") or os.getenv("GREG_NOTIFY_TO") or ""
    if not to_addr:
        return {"ok": False, "error": "No founder email configured"}
    return send_email(to_addr, subject, body)


def send_webhook(url: str, payload: dict) -> dict:
    try:
        response = requests.post(url, json=payload, timeout=15)
        return {"ok": response.ok, "status": response.status_code, "text": response.text[:500]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class NotificationEngine:
    def evaluate(self, state: dict) -> dict:
        world = state.get("world", {})
        drift = state.get("drift", {})
        should_alert = float(drift.get("coefficient", 0.0)) >= 0.7
        summary = {
            "tick": state.get("tick", 0),
            "agent_count": world.get("agent_count", 0),
            "drift": drift.get("coefficient", 0.0),
            "alerted": False,
        }
        if should_alert:
            result = send_zyphon_email(
                "Greg drift warning",
                (
                    f"Tick: {summary['tick']}\n"
                    f"Agents: {summary['agent_count']}\n"
                    f"Drift coefficient: {summary['drift']}\n"
                ),
            )
            summary["alerted"] = bool(result.get("ok"))
        return summary
