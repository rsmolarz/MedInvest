"""Email sending abstraction.

Supports:
- SendGrid (recommended)
- Postmark

Configured via environment variables:
- EMAIL_PROVIDER=sendgrid|postmark
- SENDGRID_API_KEY, SENDGRID_FROM
- POSTMARK_SERVER_TOKEN, POSTMARK_FROM

This module is safe for ops alerts (admin-only). It does not enforce CAN-SPAM/etc.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else None


def send_email(*, to_email: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    provider = (_env("EMAIL_PROVIDER") or "sendgrid").lower()
    if provider == "postmark":
        return _send_postmark(to_email=to_email, subject=subject, text=text, html=html)
    return _send_sendgrid(to_email=to_email, subject=subject, text=text, html=html)


def _send_sendgrid(*, to_email: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    api_key = _env("SENDGRID_API_KEY")
    from_email = _env("SENDGRID_FROM")
    if not api_key or not from_email:
        logger.warning("SendGrid not configured; skipping email")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}],
    }
    if html:
        payload["content"].append({"type": "text/html", "value": html})

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if 200 <= r.status_code < 300:
            return True
        logger.error("SendGrid email failed: %s %s", r.status_code, r.text)
        return False
    except Exception:
        logger.exception("SendGrid email exception")
        return False


def _send_postmark(*, to_email: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    token = _env("POSTMARK_SERVER_TOKEN")
    from_email = _env("POSTMARK_FROM")
    if not token or not from_email:
        logger.warning("Postmark not configured; skipping email")
        return False

    payload = {
        "From": from_email,
        "To": to_email,
        "Subject": subject,
        "TextBody": text,
    }
    if html:
        payload["HtmlBody"] = html

    try:
        r = requests.post(
            "https://api.postmarkapp.com/email",
            headers={
                "X-Postmark-Server-Token": token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        if 200 <= r.status_code < 300:
            return True
        logger.error("Postmark email failed: %s %s", r.status_code, r.text)
        return False
    except Exception:
        logger.exception("Postmark email exception")
        return False
