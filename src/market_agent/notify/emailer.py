"""SMTP email notifier.

Supports two modes:

* **Authenticated** (e.g. Gmail + App Password): set ``SMTP_TLS=true``,
  ``SMTP_USER``, and ``SMTP_PASSWORD`` in ``.env``.
* **Unauthenticated local relay** (e.g. Postfix on the same VM): leave
  ``SMTP_USER`` / ``SMTP_PASSWORD`` blank and set ``SMTP_HOST=localhost``,
  ``SMTP_PORT=25``, ``SMTP_TLS=false`` (the defaults).
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from market_agent.config import settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send EOD reports via SMTP.

    Auth is optional — when ``user`` / ``password`` are absent the notifier
    connects without STARTTLS and skips ``LOGIN``, which works against a
    local unauthenticated relay such as Postfix on ``localhost:25``.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        tls: bool | None = None,
        user: str | None = None,
        password: str | None = None,
        email_from: str | None = None,
        email_to: str | None = None,
    ) -> None:
        self.host = host or settings.smtp_host
        self.port = port if port is not None else settings.smtp_port
        self.tls = tls if tls is not None else settings.smtp_tls
        self.user = user or settings.smtp_user
        self.password = password or settings.smtp_password
        self.email_from = email_from or settings.email_from or self.user
        self.email_to = email_to or settings.email_to

    @property
    def _use_auth(self) -> bool:
        return bool(self.user and self.password)

    def send(self, subject: str, body_markdown: str) -> None:
        """Send *body_markdown* as a plain-text email.

        When ``SMTP_USER`` / ``SMTP_PASSWORD`` are not set the method
        connects without STARTTLS and skips ``LOGIN`` — suitable for a
        local Postfix relay.  When credentials *are* set it upgrades the
        connection with STARTTLS before authenticating.

        Raises:
            ValueError: ``EMAIL_TO`` is not configured.
            ValueError: credentials are partially supplied (one but not both).
            smtplib.SMTPException: on SMTP-level errors.
        """
        if not self.email_to:
            raise ValueError("EMAIL_TO is not configured.  Set it in .env or pass it explicitly.")

        # Catch the easy misconfiguration: one credential set but not the other
        if bool(self.user) != bool(self.password):
            raise ValueError(
                "SMTP_USER and SMTP_PASSWORD must both be set (or both left blank for "
                "unauthenticated relay)."
            )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to
        msg.attach(MIMEText(body_markdown, "plain", "utf-8"))

        logger.info(
            "Sending email '%s' to %s via %s:%s (tls=%s auth=%s)",
            subject,
            self.email_to,
            self.host,
            self.port,
            self.tls,
            self._use_auth,
        )

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.ehlo()
            if self.tls:
                smtp.starttls()
                smtp.ehlo()
            if self._use_auth:
                smtp.login(self.user, self.password)
            smtp.sendmail(self.email_from, [self.email_to], msg.as_string())

        logger.info("Email sent successfully.")

