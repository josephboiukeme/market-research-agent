"""SMTP email notifier."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from market_agent.config import settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send EOD reports via SMTP (supports Gmail App Passwords and generic SMTP)."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        email_from: str | None = None,
        email_to: str | None = None,
    ) -> None:
        self.host = host or settings.smtp_host
        self.port = port or settings.smtp_port
        self.user = user or settings.smtp_user
        self.password = password or settings.smtp_password
        self.email_from = email_from or settings.email_from or self.user
        self.email_to = email_to or settings.email_to

    def send(self, subject: str, body_markdown: str) -> None:
        """Send *body_markdown* as a plain-text email (markdown is readable as plain text).

        Raises:
            ValueError: if required settings (TO, USER, PASSWORD) are not configured.
            smtplib.SMTPException: on SMTP-level errors.
        """
        if not self.email_to:
            raise ValueError("EMAIL_TO is not configured.  Set it in .env or pass it explicitly.")
        if not self.user or not self.password:
            raise ValueError(
                "SMTP_USER / SMTP_PASSWORD are not configured.  "
                "Set them in .env or pass them explicitly."
            )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to

        # Plain-text part (markdown is readable as-is)
        msg.attach(MIMEText(body_markdown, "plain", "utf-8"))

        logger.info(
            "Sending email '%s' to %s via %s:%s",
            subject,
            self.email_to,
            self.host,
            self.port,
        )

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(self.user, self.password)
            smtp.sendmail(self.email_from, [self.email_to], msg.as_string())

        logger.info("Email sent successfully.")
