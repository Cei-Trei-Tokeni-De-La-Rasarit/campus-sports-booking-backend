"""Testele pentru limita de încercări greșite la autentificare (KAN-127)."""

import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services import auth_service, login_limit_service

URL = "/auth/autentificare"
EMAIL = "ana.limita@student.usv.ro"
PASSWORD = "parola-corecta-1"
WRONG = "parola-gresita-1"
START = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
BLOCKED = "Prea multe încercări. Încearcă din nou peste câteva minute."


class Clock:
    """Ceasul din teste: „acum” se mută înainte doar când cere testul."""

    def __init__(self) -> None:
        self.now = START

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """Înlocuiește ora bazei de date cu un ceas controlat de test."""
    fake = Clock()
    monkeypatch.setattr(login_limit_service, "database_now", lambda db: fake.now)
    return fake


@pytest.fixture
def account(client: TestClient) -> None:
    """Un cont cu parola PASSWORD."""
    response = client.post(
        "/auth/inregistrare",
        json={"nume": "Ana Limita", "email": EMAIL, "parola": PASSWORD},
    )
    assert response.status_code == 201


def login(client: TestClient, password: str, email: str = EMAIL):
    """Trimite o cerere de autentificare."""
    return client.post(URL, json={"email": email, "parola": password})


def fail_times(client: TestClient, count: int, email: str = EMAIL) -> list[int]:
    """Trimite `count` parole greșite și întoarce codurile primite."""
    return [login(client, WRONG, email).status_code for _ in range(count)]


def count_attempts() -> int:
    """Numărul de încercări greșite salvate."""
    with engine.connect() as connection:
        return connection.scalar(text("SELECT COUNT(*) FROM login_attempt"))


def test_five_wrong_passwords_get_401_and_the_sixth_429(
    client: TestClient, account: None, clock: Clock
) -> None:
    assert fail_times(client, 5) == [401] * 5

    response = login(client, WRONG)

    assert response.status_code == 429
    assert response.json() == {"mesaj": BLOCKED}
    assert response.headers["retry-after"] == str(15 * 60)


def test_blocked_email_is_refused_even_with_the_right_password(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 5)

    response = login(client, PASSWORD)

    assert response.status_code == 429
    assert "token" not in response.json()


def test_email_is_unblocked_after_15_minutes(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 5)
    clock.advance(minutes=14, seconds=59)
    assert login(client, PASSWORD).status_code == 429

    clock.advance(seconds=1)

    assert login(client, PASSWORD).status_code == 200


def test_retry_after_counts_down_to_the_unblocking_moment(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 5)
    clock.advance(minutes=10)

    response = login(client, WRONG)

    assert response.status_code == 429
    assert response.headers["retry-after"] == str(5 * 60)


def test_attempts_while_blocked_do_not_extend_the_block(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 5)
    # Un atacator continuă să încerce cât emailul e blocat.
    for _ in range(3):
        clock.advance(minutes=4)
        assert login(client, WRONG).status_code == 429

    clock.advance(minutes=3)  # 15 minute de la încercările greșite

    assert login(client, PASSWORD).status_code == 200


def test_old_attempts_leave_the_window_one_by_one(
    client: TestClient, account: None, clock: Clock
) -> None:
    # Câte o încercare greșită pe minut: la 10:00, 10:01, ..., 10:04.
    for _ in range(5):
        assert login(client, WRONG).status_code == 401
        clock.advance(minutes=1)
    assert login(client, WRONG).status_code == 429  # 10:05, blocat

    clock.advance(minutes=10)  # 10:15: încercarea de la 10:00 a expirat

    assert login(client, WRONG).status_code == 401
    assert login(client, WRONG).status_code == 429


def test_successful_login_clears_the_wrong_attempts(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 4)
    assert login(client, PASSWORD).status_code == 200
    assert count_attempts() == 0

    assert fail_times(client, 5) == [401] * 5
    assert login(client, WRONG).status_code == 429


def test_unknown_email_is_limited_the_same_way(
    client: TestClient, clock: Clock
) -> None:
    unknown = "nu.exista@student.usv.ro"

    assert fail_times(client, 5, unknown) == [401] * 5
    response = login(client, WRONG, unknown)

    assert response.status_code == 429
    assert response.json() == {"mesaj": BLOCKED}


def test_email_case_does_not_bypass_the_limit(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 3)
    fail_times(client, 2, EMAIL.upper())

    assert login(client, PASSWORD, "  " + EMAIL.title()).status_code == 429


def test_other_emails_are_not_affected(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 6, "altcineva@student.usv.ro")

    assert login(client, PASSWORD).status_code == 200


def test_expired_attempts_are_deleted(
    client: TestClient, account: None, clock: Clock
) -> None:
    fail_times(client, 3)
    clock.advance(minutes=16)

    login(client, WRONG)

    assert count_attempts() == 1


def test_simultaneous_wrong_attempts_cannot_bypass_the_limit(
    client: TestClient, account: None
) -> None:
    results: list[str] = []
    errors: list[BaseException] = []
    start_together = threading.Barrier(10)

    def attempt() -> None:
        start_together.wait()
        try:
            with SessionLocal() as db:
                auth_service.authenticate_user(db, EMAIL, WRONG)
        except auth_service.InvalidCredentialsError:
            results.append("401")
        except login_limit_service.TooManyAttemptsError:
            results.append("429")
        except Exception as error:  # noqa: BLE001 - raportat mai jos
            errors.append(error)

    threads = [threading.Thread(target=attempt) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert sorted(results) == ["401"] * 5 + ["429"] * 5
    assert count_attempts() == 5


def test_login_still_works_normally(client: TestClient, account: None) -> None:
    response = login(client, PASSWORD)

    assert response.status_code == 200
    assert response.json()["utilizator"]["email"] == EMAIL
