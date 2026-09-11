"""Notification sender delivering e-mails over SMTP."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage as MimeMessage

from rendez_vite.domain.errors import NotificationError
from rendez_vite.domain.models import EmailMessage

TransportFactory = Callable[[], smtplib.SMTP]


class SmtpEmailNotifier:
    """Send the alert as an e-mail through an SMTP relay.

    ``smtplib`` is blocking, so the delivery is pushed to a worker thread to keep the
    activity coroutine responsive.
    """

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        *,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        timeout: float = 10.0,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        """Build the notifier.

        Parameters
        ----------
        host
            Hostname of the SMTP relay.
        port
            Port of the SMTP relay.
        sender
            Address the e-mails are sent from.
        username
            Optional login used to authenticate.
        password
            Optional password used to authenticate.
        use_tls
            Whether STARTTLS is negotiated before sending.
        timeout
            Connection timeout in seconds.
        transport_factory
            Callable building the SMTP connection, overridden in tests.
        """
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout = timeout
        self._transport_factory = transport_factory or self._default_transport_factory

    def _default_transport_factory(self) -> smtplib.SMTP:
        """Open a connection to the configured relay.

        Returns
        -------
        smtplib.SMTP
            The freshly opened connection.
        """
        return smtplib.SMTP(self._host, self._port, timeout=self._timeout)

    async def send(self, message: EmailMessage) -> None:
        """Deliver the message through the relay.

        Parameters
        ----------
        message
            Rendered message to deliver.

        Raises
        ------
        NotificationError
            If the relay rejects the message or cannot be reached.
        """
        await asyncio.to_thread(self._send_blocking, message)

    def _send_blocking(self, message: EmailMessage) -> None:
        """Perform the blocking SMTP exchange.

        Parameters
        ----------
        message
            Rendered message to deliver.

        Raises
        ------
        NotificationError
            If the relay rejects the message or cannot be reached.
        """
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.recipient
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        try:
            with self._transport_factory() as transport:
                if self._use_tls:
                    transport.starttls(context=ssl.create_default_context())
                if self._username and self._password:
                    transport.login(self._username, self._password)
                transport.send_message(mime)
        except (OSError, smtplib.SMTPException) as error:
            raise NotificationError(f"SMTP delivery to {message.recipient} failed") from error
