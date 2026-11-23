"""Trimiterea emailurilor: modulul comun pentru resetarea parolei (N7) și
notificările pe email (KAN-65).

Modul de trimitere se alege din `.env`, cu `EMAIL_MODE`:
- `consola` (implicit): emailul nu pleacă, apare în logul serverului; așa
  se poate lucra fără datele contului de email;
- `smtp`: emailul se trimite prin serverul SMTP din `.env` (Gmail).
În teste se folosește un trimițător fals (vezi `use_sender`).
"""

import logging
import os
import smtplib
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from dotenv import load_dotenv

# Variabilele din .env trebuie citite și dacă modulul e importat primul.
load_dotenv()

logger = logging.getLogger(__name__)

EMAIL_MODES = ("consola", "smtp")
SMTP_VARIABLES = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM")

# Câte secunde așteptăm serverul SMTP înainte să renunțăm.
SMTP_TIMEOUT_SECONDS = 10

# Cel mai mare număr de port TCP.
MAX_PORT = 65535


class EmailSendError(Exception):
    """Emailul nu a putut fi trimis (server indisponibil, autentificare etc.)."""


@dataclass(frozen=True)
class SmtpSettings:
    """Datele de conectare la serverul SMTP, citite din `.env`."""

    host: str
    port: int
    user: str
    password: str
    sender: str


class EmailSender(Protocol):
    """Orice obiect care știe să trimită un email gata construit."""

    def send(self, message: EmailMessage) -> None:
        """Trimite emailul; la eroare ridică EmailSendError."""


class ConsoleSender:
    """Nu trimite nimic: scrie emailul în logul serverului (pentru dezvoltare)."""

    def send(self, message: EmailMessage) -> None:
        """Scrie destinatarul, subiectul și textul în log."""
        logger.info(
            "Email (modul consolă, netrimis) către %s, subiect „%s”:\n%s",
            message["To"],
            message["Subject"],
            message.get_content(),
        )


class SmtpSender:
    """Trimite emailul printr-un server SMTP, cu conexiune criptată (STARTTLS)."""

    def __init__(self, settings: SmtpSettings) -> None:
        self.settings = settings

    def send(self, message: EmailMessage) -> None:
        """Se conectează, se autentifică și trimite; la eroare EmailSendError."""
        settings = self.settings
        try:
            server = smtplib.SMTP(
                settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS
            )
            try:
                server.starttls(context=ssl.create_default_context())
                server.login(settings.user, settings.password)
                server.send_message(message)
            finally:
                close_quietly(server)
        except (smtplib.SMTPException, OSError) as error:
            # În log apar doar tipul erorii și adresa mascată: fără parolă,
            # fără adresa completă (date personale) și fără textul emailului
            # (de exemplu, linkul pentru resetarea parolei).
            logger.error(
                "Emailul către %s nu a putut fi trimis: %s",
                mask_address(str(message["To"])),
                type(error).__name__,
            )
            raise EmailSendError("Emailul nu a putut fi trimis.") from error


def close_quietly(server: smtplib.SMTP) -> None:
    """Închide conexiunea SMTP fără să ridice erori.

    Dacă serverul nu răspunde corect la QUIT, emailul a plecat deja; o eroare
    aici ar face aplicația să creadă că trimiterea a eșuat (și ar putea
    retrimite emailul), așa că doar o notăm în log.
    """
    try:
        server.quit()
    except (smtplib.SMTPException, OSError) as error:
        logger.warning("Conexiunea SMTP nu s-a închis curat: %s", type(error).__name__)
        server.close()


def mask_address(address: str) -> str:
    """Ascunde adresa pentru log.

    De exemplu, „ana.popescu@student.usv.ro” devine „a***@student.usv.ro”.
    """
    local, separator, domain = address.rpartition("@")
    if not separator or not local:
        return "***"
    return f"{local[0]}***@{domain}"


def load_smtp_settings(environ: Mapping[str, str]) -> SmtpSettings:
    """Citește datele SMTP; dacă lipsește una, spune care (RuntimeError)."""
    missing = [name for name in SMTP_VARIABLES if not environ.get(name)]
    if missing:
        raise RuntimeError(
            "EMAIL_MODE=smtp, dar lipsesc variabilele: "
            + ", ".join(missing)
            + " (vezi .env.example)."
        )
    try:
        port = int(environ["SMTP_PORT"])
    except ValueError:
        port = 0
    if not 1 <= port <= MAX_PORT:
        raise RuntimeError(
            f"SMTP_PORT trebuie să fie un număr între 1 și {MAX_PORT} "
            "(de exemplu, 587)."
        )
    return SmtpSettings(
        host=environ["SMTP_HOST"],
        port=port,
        user=environ["SMTP_USER"],
        password=environ["SMTP_PASSWORD"],
        sender=environ["EMAIL_FROM"],
    )


def create_sender(environ: Mapping[str, str]) -> tuple[EmailSender, str]:
    """Alege trimițătorul după EMAIL_MODE; întoarce și adresa expeditorului."""
    mode = environ.get("EMAIL_MODE") or "consola"
    if mode not in EMAIL_MODES:
        raise RuntimeError(
            f"EMAIL_MODE poate fi doar {' sau '.join(EMAIL_MODES)}, nu „{mode}”."
        )
    if mode == "smtp":
        settings = load_smtp_settings(environ)
        return SmtpSender(settings), settings.sender
    sender = environ.get("EMAIL_FROM") or "Campus Sports Booking <noreply@localhost>"
    # Avertisment la pornire, ca să nu pară că emailurile pleacă.
    logger.warning("EMAIL_MODE=consola: emailurile nu se trimit, apar doar în log.")
    return ConsoleSender(), sender


# Trimițătorul folosit de aplicație, ales o singură dată, la pornire: o
# configurație greșită oprește serverul imediat, nu la primul email.
_sender, _from_address = create_sender(os.environ)


def use_sender(sender: EmailSender) -> EmailSender:
    """Înlocuiește trimițătorul (în teste); întoarce trimițătorul vechi."""
    global _sender
    previous, _sender = _sender, sender
    return previous


def build_message(to: str, subject: str, body: str, sender: str) -> EmailMessage:
    """Construiește emailul text, în UTF-8.

    Un antet cu „rând nou” (de exemplu, un subiect care ar încerca să adauge
    destinatari ascunși) e respins de biblioteca email cu ValueError.
    """
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body, charset="utf-8")
    return message


def send_email(to: str, subject: str, body: str) -> None:
    """Trimite un email text; la eroare ridică EmailSendError."""
    _sender.send(build_message(to, subject, body, _from_address))
