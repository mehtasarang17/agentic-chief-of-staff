"""SMTP email sender utility."""
from email.message import EmailMessage
import smtplib
from typing import Optional

from app.config import settings


class EmailSendError(Exception):
    """Raised when email sending fails."""


def send_email(
    to_email: str,
    subject: str,
    body: str,
    to_name: Optional[str] = None,
) -> None:
    """Send an email via SMTP using configured settings."""
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise EmailSendError("SMTP is not configured.")

    msg = EmailMessage()
    from_name = settings.SMTP_FROM_NAME or "Chief of Staff"
    msg["From"] = f"{from_name} <{settings.SMTP_FROM}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if settings.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        if settings.SMTP_USE_TLS:
            server.starttls()

    try:
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    except Exception as exc:
        raise EmailSendError(str(exc)) from exc
    finally:
        server.quit()
