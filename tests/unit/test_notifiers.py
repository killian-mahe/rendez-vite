from __future__ import annotations

import logging
import smtplib
from typing import cast

import pytest

from rendez_vite.domain.errors import NotificationError
from rendez_vite.domain.models import EmailMessage
from rendez_vite.infrastructure.notifiers.console import ConsoleNotifier
from rendez_vite.infrastructure.notifiers.smtp import SmtpEmailNotifier, TransportFactory


@pytest.fixture
def message():
    return EmailMessage(recipient="patient@test", subject="Créneau libre", body="Mercredi 09:00")


class FakeSmtp:
    def __init__(self, failure: Exception | None = None):
        self.failure = failure
        self.started_tls = False
        self.credentials: tuple[str, str] | None = None
        self.sent: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, mime):
        if self.failure is not None:
            raise self.failure
        self.sent.append(mime["To"])


def factory_for(transport: FakeSmtp) -> TransportFactory:
    return cast("TransportFactory", lambda: transport)


async def test_console_notifier_logs_the_message(message, caplog):
    with caplog.at_level(logging.INFO):
        await ConsoleNotifier(logging.getLogger("test.console")).send(message)
    assert "patient@test" in caplog.text
    assert "Mercredi 09:00" in caplog.text


async def test_smtp_notifier_sends_the_message(message):
    transport = FakeSmtp()
    notifier = SmtpEmailNotifier(
        "smtp.test",
        587,
        "bot@test",
        username="bot",
        password="hunter2",
        transport_factory=factory_for(transport),
    )
    await notifier.send(message)
    assert transport.sent == ["patient@test"]
    assert transport.started_tls is True
    assert transport.credentials == ("bot", "hunter2")


async def test_smtp_notifier_can_skip_tls_and_authentication(message):
    transport = FakeSmtp()
    notifier = SmtpEmailNotifier(
        "smtp.test", 25, "bot@test", use_tls=False, transport_factory=factory_for(transport)
    )
    await notifier.send(message)
    assert transport.started_tls is False
    assert transport.credentials is None


@pytest.mark.parametrize(
    "failure", [smtplib.SMTPRecipientsRefused({}), OSError("connection reset")]
)
async def test_smtp_failures_are_reported(message, failure):
    notifier = SmtpEmailNotifier(
        "smtp.test", 587, "bot@test", transport_factory=factory_for(FakeSmtp(failure))
    )
    with pytest.raises(NotificationError, match="patient@test"):
        await notifier.send(message)


def test_the_default_transport_targets_the_configured_relay(monkeypatch):
    captured: dict[str, object] = {}

    def fake_smtp(host, port, timeout):
        captured.update(host=host, port=port, timeout=timeout)
        return FakeSmtp()

    monkeypatch.setattr(smtplib, "SMTP", fake_smtp)
    notifier = SmtpEmailNotifier("smtp.test", 2525, "bot@test", timeout=3.0)
    notifier._default_transport_factory()
    assert captured == {"host": "smtp.test", "port": 2525, "timeout": 3.0}
