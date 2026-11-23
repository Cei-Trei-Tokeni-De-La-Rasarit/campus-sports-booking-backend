"""Testele pentru trimiterea emailurilor (KAN-107).

Nicio conexiune reală: serverul SMTP e înlocuit cu FakeSmtp, care reține ce
i se cere, iar aplicația folosește în teste trimițătorul fals din conftest.
"""

import logging
import smtplib
from email.message import EmailMessage

import pytest

from app.services import email_service

SMTP_ENV = {
    "EMAIL_MODE": "smtp",
    "SMTP_HOST": "smtp.exemplu.test",
    "SMTP_PORT": "587",
    "SMTP_USER": "echipa@exemplu.test",
    "SMTP_PASSWORD": "parola-secreta-de-test",
    "EMAIL_FROM": "Campus Sports Booking <echipa@exemplu.test>",
}
SUBJECT = "Resetarea parolei"
BODY = "Bună, Ana! Folosește linkul acesta în următoarele 30 de minute: ăîșțâ"


class FakeSmtp:
    """Serverul SMTP simulat: reține conexiunea, autentificarea și emailurile."""

    instances: list["FakeSmtp"] = []
    fail_on: str | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        if FakeSmtp.fail_on == "connect":
            raise ConnectionRefusedError("serverul nu răspunde")
        self.address = (host, port)
        self.timeout = timeout
        self.calls: list[str] = []
        self.login_data: tuple[str, str] | None = None
        self.messages: list[EmailMessage] = []
        FakeSmtp.instances.append(self)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *args: object) -> None:
        self.calls.append("quit")

    def starttls(self, context: object) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append("login")
        if FakeSmtp.fail_on == "login":
            raise smtplib.SMTPAuthenticationError(
                535, b"Username and Password not accepted"
            )
        self.login_data = (user, password)

    def send_message(self, message: EmailMessage) -> None:
        self.calls.append("send")
        self.messages.append(message)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSmtp]:
    """Înlocuiește smtplib.SMTP cu serverul simulat."""
    FakeSmtp.instances = []
    FakeSmtp.fail_on = None
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    return FakeSmtp


def smtp_sender() -> email_service.SmtpSender:
    """Un trimițător SMTP cu datele de test."""
    sender, _ = email_service.create_sender(SMTP_ENV)
    assert isinstance(sender, email_service.SmtpSender)
    return sender


def message(to: str = "ana.popescu@student.usv.ro") -> EmailMessage:
    """Un email de test, construit ca în aplicație."""
    return email_service.build_message(to, SUBJECT, BODY, SMTP_ENV["EMAIL_FROM"])


# Construirea emailului.


def test_message_has_sender_recipient_subject_and_body() -> None:
    built = message()

    assert built["From"] == SMTP_ENV["EMAIL_FROM"]
    assert built["To"] == "ana.popescu@student.usv.ro"
    assert built["Subject"] == SUBJECT
    assert built.get_content().strip() == BODY
    assert built.get_content_charset() == "utf-8"


def test_message_with_diacritics_in_subject_is_encoded() -> None:
    built = email_service.build_message(
        "ana.popescu@student.usv.ro", "Rezervare anulată", BODY, "a@exemplu.test"
    )

    # Antetul ajunge codat (ASCII) pe fir, dar se citește înapoi corect.
    assert "Rezervare anulată" not in built.as_string()
    assert built["Subject"] == "Rezervare anulată"


@pytest.mark.parametrize(
    ("to", "subject"),
    [
        ("ana@student.usv.ro", "Subiect\nBcc: altcineva@exemplu.test"),
        ("ana@student.usv.ro\r\nBcc: altcineva@exemplu.test", "Subiect"),
    ],
)
def test_header_with_new_line_is_rejected(to: str, subject: str) -> None:
    with pytest.raises(ValueError):
        email_service.build_message(to, subject, BODY, "a@exemplu.test")


# Alegerea modului din .env.


def test_console_mode_is_the_default() -> None:
    sender, _ = email_service.create_sender({})

    assert isinstance(sender, email_service.ConsoleSender)


def test_smtp_mode_uses_the_settings_from_env() -> None:
    sender, from_address = email_service.create_sender(SMTP_ENV)

    assert isinstance(sender, email_service.SmtpSender)
    assert sender.settings.host == "smtp.exemplu.test"
    assert sender.settings.port == 587
    assert from_address == SMTP_ENV["EMAIL_FROM"]


def test_unknown_mode_stops_the_server() -> None:
    with pytest.raises(RuntimeError, match="EMAIL_MODE"):
        email_service.create_sender({"EMAIL_MODE": "gmail"})


@pytest.mark.parametrize("missing", list(email_service.SMTP_VARIABLES))
def test_smtp_mode_with_missing_variable_names_it(missing: str) -> None:
    env = {**SMTP_ENV, missing: ""}

    with pytest.raises(RuntimeError, match=missing):
        email_service.create_sender(env)


def test_smtp_port_must_be_a_number() -> None:
    with pytest.raises(RuntimeError, match="SMTP_PORT"):
        email_service.create_sender({**SMTP_ENV, "SMTP_PORT": "abc"})


# Modul consolă.


def test_console_mode_writes_the_email_to_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=email_service.__name__):
        email_service.ConsoleSender().send(message())

    assert "ana.popescu@student.usv.ro" in caplog.text
    assert SUBJECT in caplog.text
    assert BODY in caplog.text


# Trimiterea prin SMTP (server simulat).


def test_smtp_sender_encrypts_logs_in_and_sends(fake_smtp: type[FakeSmtp]) -> None:
    smtp_sender().send(message())

    server = fake_smtp.instances[0]
    assert server.address == ("smtp.exemplu.test", 587)
    assert server.timeout == email_service.SMTP_TIMEOUT_SECONDS
    # STARTTLS înainte de autentificare: parola nu circulă necriptată.
    assert server.calls == ["starttls", "login", "send", "quit"]
    assert server.login_data == ("echipa@exemplu.test", "parola-secreta-de-test")
    assert server.messages[0]["To"] == "ana.popescu@student.usv.ro"


@pytest.mark.parametrize("fail_on", ["connect", "login"])
def test_smtp_error_raises_email_send_error_without_secrets_in_log(
    fake_smtp: type[FakeSmtp], caplog: pytest.LogCaptureFixture, fail_on: str
) -> None:
    fake_smtp.fail_on = fail_on

    with pytest.raises(email_service.EmailSendError):
        smtp_sender().send(message())

    assert "nu a putut fi trimis" in caplog.text
    assert SMTP_ENV["SMTP_PASSWORD"] not in caplog.text
    assert BODY not in caplog.text


# Funcția folosită de aplicație.


def test_send_email_uses_the_current_sender(sent_emails: list[EmailMessage]) -> None:
    email_service.send_email("ana.popescu@student.usv.ro", SUBJECT, BODY)

    assert len(sent_emails) == 1
    assert sent_emails[0]["To"] == "ana.popescu@student.usv.ro"
    assert sent_emails[0].get_content().strip() == BODY


def test_tests_never_use_a_real_sender() -> None:
    sender = email_service.use_sender(email_service.ConsoleSender())
    email_service.use_sender(sender)

    assert not isinstance(
        sender, email_service.SmtpSender | email_service.ConsoleSender
    )
