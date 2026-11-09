"""
Outgoing email: password reset links, and account and review outcomes.

Configured by the NCCRD_MAIL_* settings (see ``nccrd.config``). Callers send
from a background task, so a slow or failing mail server never holds up or
fails the request; a failure is logged.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from nccrd.config import nccrd_config

logger = logging.getLogger(__name__)


def _deliver(message: EmailMessage) -> None:
    """Hand the message to the configured SMTP server."""
    mail = nccrd_config.NCCRD.MAIL
    context = ssl.create_default_context()
    if mail.SSL:
        server = smtplib.SMTP_SSL(mail.HOST, mail.PORT, timeout=mail.TIMEOUT, context=context)
    else:
        server = smtplib.SMTP(mail.HOST, mail.PORT, timeout=mail.TIMEOUT)
    with server:
        if mail.TLS and not mail.SSL:
            server.starttls(context=context)
        if mail.USERNAME:
            server.login(mail.USERNAME, mail.PASSWORD or "")
        server.send_message(message)


def send_mail(to: str, subject: str, body: str, *, sender_name: str = "NCCRD") -> bool:
    """
    Send a plain-text email; True if the mail server accepted it. Never
    raises: run it as a background task.
    """
    mail = nccrd_config.NCCRD.MAIL
    if not mail.HOST:
        logger.warning("Mail is not set up (NCCRD_MAIL_HOST is empty), so this email was not sent: %r", subject)
        return False

    sender = mail.FROM or mail.USERNAME
    if not sender:
        logger.warning("Mail has no sender address (set NCCRD_MAIL_FROM), so this email was not sent: %r", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, sender))
    message["To"] = to
    message.set_content(body)
    try:
        _deliver(message)
    except (OSError, smtplib.SMTPException):
        # The address and settings stay out of the log; the error says enough.
        logger.exception("Could not send the email %r", subject)
        return False
    return True
