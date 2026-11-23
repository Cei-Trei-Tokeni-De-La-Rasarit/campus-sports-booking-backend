"""Testele pentru resetarea parolei prin email (KAN-111).

Emailurile nu pleacă: fixture-ul `sent_emails` din conftest le reține, iar
testele citesc linkul din textul lor.
"""

import hashlib
import re
from collections.abc import Callable
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.services import email_service, password_reset_service

EMAIL = "ana.ionescu@student.usv.ro"
OLD_PASSWORD = "parola-sigura"
NEW_PASSWORD = "parola-noua-2026"
REQUESTED = {
    "mesaj": "Dacă există un cont cu această adresă, vei primi pe email un link "
    "pentru resetarea parolei."
}
CHANGED = {"mesaj": "Parola a fost schimbată. Te poți autentifica cu parola nouă."}
INVALID_TOKEN = {
    "mesaj": "Linkul pentru resetarea parolei nu este valid sau a expirat. "
    "Cere un link nou."
}
LINK = re.compile(r"(\S+)/parola-noua\?token=(\S+)")


@pytest.fixture
def user_id(log_in: Callable[..., tuple[int, dict[str, str]]]) -> int:
    """Un cont existent, cu parola OLD_PASSWORD."""
    return log_in(EMAIL)[0]


def request_reset(client: TestClient, data: object):
    """Cere un link de resetare."""
    return client.post("/auth/resetare-parola", json=data)


def confirm(client: TestClient, token: object, password: object = NEW_PASSWORD):
    """Trimite token-ul și parola nouă."""
    return client.post(
        "/auth/resetare-parola/confirmare",
        json={"token": token, "parola_noua": password},
    )


def token_from(message: EmailMessage) -> str:
    """Token-ul din linkul unui email de resetare."""
    match = LINK.search(message.get_content())
    assert match is not None
    return match.group(2)


def new_token(client: TestClient, sent_emails: list[EmailMessage]) -> str:
    """Cere un link pentru EMAIL și întoarce token-ul din el."""
    assert request_reset(client, {"email": EMAIL}).status_code == 200
    return token_from(sent_emails[-1])


def can_log_in(client: TestClient, password: str) -> bool:
    """Spune dacă autentificarea cu parola dată reușește."""
    response = client.post(
        "/auth/autentificare", json={"email": EMAIL, "parola": password}
    )
    return response.status_code == 200


def tokens_in_db() -> list[tuple]:
    """Token-urile din baza de test, ca (utilizator, hash, folosit)."""
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT user_id, token_hash, used FROM password_reset_token ORDER BY id"
            )
        )
        return [tuple(row) for row in rows]


def move_tokens_back(minutes: int) -> None:
    """Mută în trecut crearea și expirarea token-urilor (ca și cum ar fi vechi)."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE password_reset_token SET "
                "created_at = created_at - make_interval(mins => :minutes), "
                "expires_at = expires_at - make_interval(mins => :minutes)"
            ),
            {"minutes": minutes},
        )


# POST /auth/resetare-parola


def test_request_sends_link_to_existing_account(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    response = request_reset(client, {"email": EMAIL})

    assert response.status_code == 200
    assert response.json() == REQUESTED
    assert len(sent_emails) == 1
    message = sent_emails[0]
    assert message["To"] == EMAIL
    assert message["Subject"] == password_reset_service.EMAIL_SUBJECT
    assert "Andrei Popescu" in message.get_content()
    match = LINK.search(message.get_content())
    assert match is not None
    assert match.group(1) == password_reset_service.FRONTEND_URL


def test_only_the_hash_of_the_token_is_stored(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)

    expected_hash = hashlib.sha256(token.encode()).hexdigest()
    assert tokens_in_db() == [(user_id, expected_hash, False)]


def test_token_expires_after_30_minutes(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    new_token(client, sent_emails)

    with engine.connect() as connection:
        lifetime = connection.scalar(
            text("SELECT expires_at - created_at FROM password_reset_token")
        )
    assert lifetime == password_reset_service.TOKEN_LIFETIME


def test_unknown_email_gets_the_same_answer_and_no_email(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    response = request_reset(client, {"email": "nimeni@student.usv.ro"})

    assert response.status_code == 200
    assert response.json() == REQUESTED
    assert sent_emails == []
    assert tokens_in_db() == []


def test_email_is_found_regardless_of_case_and_spaces(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    response = request_reset(client, {"email": "  Ana.Ionescu@Student.USV.ro "})

    assert response.status_code == 200
    assert [message["To"] for message in sent_emails] == [EMAIL]


def test_at_most_three_requests_per_hour(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    for _ in range(3):
        request_reset(client, {"email": EMAIL})

    response = request_reset(client, {"email": EMAIL})

    # Același răspuns, dar fără email nou și fără token nou.
    assert response.status_code == 200
    assert response.json() == REQUESTED
    assert len(sent_emails) == 3
    assert len(tokens_in_db()) == 3


def test_limit_resets_after_an_hour(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    for _ in range(3):
        request_reset(client, {"email": EMAIL})
    move_tokens_back(61)

    request_reset(client, {"email": EMAIL})

    assert len(sent_emails) == 4


def test_limit_is_counted_for_each_account(
    client: TestClient,
    user_id: int,
    log_in: Callable[..., tuple[int, dict[str, str]]],
    sent_emails: list[EmailMessage],
) -> None:
    log_in("mihai.rusu@student.usv.ro")
    for _ in range(3):
        request_reset(client, {"email": EMAIL})

    request_reset(client, {"email": "mihai.rusu@student.usv.ro"})

    assert sent_emails[-1]["To"] == "mihai.rusu@student.usv.ro"


class FailingSender:
    """Un trimițător care nu reușește niciodată (server SMTP indisponibil)."""

    def send(self, message: EmailMessage) -> None:
        raise email_service.EmailSendError("Emailul nu a putut fi trimis.")


def test_email_error_does_not_change_the_answer(
    client: TestClient, user_id: int, caplog: pytest.LogCaptureFixture
) -> None:
    previous = email_service.use_sender(FailingSender())
    try:
        response = request_reset(client, {"email": EMAIL})
    finally:
        email_service.use_sender(previous)

    assert response.status_code == 200
    assert response.json() == REQUESTED
    assert "nu a fost trimis" in caplog.text
    # Linkul nu ajunge în log.
    assert "parola-noua?token=" not in caplog.text


@pytest.mark.parametrize(
    "data",
    [
        {},
        None,
        [],
        {"email": None},
        {"email": ""},
        {"email": "   "},
        {"email": "nu-e-email"},
        {"email": 123},
        {"email": "a" * 140 + "@student.usv.ro"},
    ],
    ids=[
        "obiect-gol",
        "null",
        "lista",
        "email-null",
        "email-gol",
        "doar-spatii",
        "fara-arond",
        "numar",
        "prea-lung",
    ],
)
def test_invalid_request_returns_400(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage], data: object
) -> None:
    response = request_reset(client, data)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert sent_emails == []


# POST /auth/resetare-parola/confirmare


def test_valid_token_changes_the_password(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)

    response = confirm(client, token)

    assert response.status_code == 200
    assert response.json() == CHANGED
    assert can_log_in(client, NEW_PASSWORD)
    assert not can_log_in(client, OLD_PASSWORD)


def test_token_can_be_used_only_once(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)
    confirm(client, token)

    response = confirm(client, token, "alta-parola-noua")

    assert response.status_code == 400
    assert response.json() == INVALID_TOKEN
    assert can_log_in(client, NEW_PASSWORD)


def test_other_tokens_of_the_account_become_invalid(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    first = new_token(client, sent_emails)
    second = new_token(client, sent_emails)

    assert confirm(client, second).status_code == 200
    response = confirm(client, first, "alta-parola-noua")

    assert response.status_code == 400
    assert [used for _, _, used in tokens_in_db()] == [True, True]


def test_tokens_of_other_accounts_stay_valid(
    client: TestClient,
    user_id: int,
    log_in: Callable[..., tuple[int, dict[str, str]]],
    sent_emails: list[EmailMessage],
) -> None:
    log_in("mihai.rusu@student.usv.ro")
    request_reset(client, {"email": "mihai.rusu@student.usv.ro"})
    other = token_from(sent_emails[-1])
    confirm(client, new_token(client, sent_emails))

    response = confirm(client, other)

    assert response.status_code == 200


def test_expired_token_is_rejected(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)
    move_tokens_back(31)

    response = confirm(client, token)

    assert response.status_code == 400
    assert response.json() == INVALID_TOKEN
    assert can_log_in(client, OLD_PASSWORD)


def test_token_still_works_just_before_expiry(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)
    move_tokens_back(29)

    assert confirm(client, token).status_code == 200


@pytest.mark.parametrize(
    "token", ["token-inventat", "a" * 43], ids=["inventat", "lungime-reala"]
)
def test_unknown_token_is_rejected(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage], token: str
) -> None:
    new_token(client, sent_emails)

    response = confirm(client, token)

    assert response.status_code == 400
    assert response.json() == INVALID_TOKEN
    assert can_log_in(client, OLD_PASSWORD)


def test_token_from_deleted_account_is_rejected(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)
    with engine.begin() as connection:
        connection.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": user_id})

    response = confirm(client, token)

    assert response.status_code == 400


def test_password_of_exactly_eight_characters_is_accepted(
    client: TestClient, user_id: int, sent_emails: list[EmailMessage]
) -> None:
    token = new_token(client, sent_emails)

    assert confirm(client, token, "12345678").status_code == 200
    assert can_log_in(client, "12345678")


@pytest.mark.parametrize(
    "password",
    ["", "1234567", None, 12345678, "ă" * 37],
    ids=["goala", "sapte-caractere", "null", "numar", "peste-72-de-bytes"],
)
def test_invalid_new_password_returns_400_and_keeps_the_token(
    client: TestClient,
    user_id: int,
    sent_emails: list[EmailMessage],
    password: object,
) -> None:
    token = new_token(client, sent_emails)

    response = confirm(client, token, password)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert can_log_in(client, OLD_PASSWORD)
    # Token-ul nu s-a consumat: utilizatorul poate încerca din nou.
    assert confirm(client, token).status_code == 200


@pytest.mark.parametrize(
    "data",
    [
        {},
        None,
        {"parola_noua": NEW_PASSWORD},
        {"token": "abc"},
        {"token": None, "parola_noua": NEW_PASSWORD},
        {"token": "", "parola_noua": NEW_PASSWORD},
        {"token": 123, "parola_noua": NEW_PASSWORD},
        {"token": "a" * 101, "parola_noua": NEW_PASSWORD},
    ],
    ids=[
        "obiect-gol",
        "null",
        "fara-token",
        "fara-parola",
        "token-null",
        "token-gol",
        "token-numar",
        "token-prea-lung",
    ],
)
def test_invalid_confirmation_data_returns_400(
    client: TestClient, user_id: int, data: object
) -> None:
    response = client.post("/auth/resetare-parola/confirmare", json=data)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert can_log_in(client, OLD_PASSWORD)
