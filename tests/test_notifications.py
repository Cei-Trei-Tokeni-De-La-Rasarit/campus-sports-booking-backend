"""Testele pentru notificări (GET /notificari, PATCH /notificari/{id}).

Notificările se creează automat la confirmarea și la anularea unei rezervări.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.services import facility_service

URL = "/notificari"
FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}
# „Acum” e luni, 30 noiembrie 2026, ora 12:00; sloturile sunt după 2 zile,
# ca rezervările să poată fi și anulate (minimum 24 de ore înainte).
NOW = datetime(2026, 11, 30, 12, 0)
SLOT_DAY = "2026-12-02"
SLOT_TEXT = "Sala de tenis Nr. 3 · Miercuri, 2 decembrie · 10:00 – 11:00"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Face ca „acum” să fie 30 noiembrie 2026, ora 12:00 (ora României)."""
    monkeypatch.setattr(facility_service, "romania_now", lambda db: NOW)


@pytest.fixture
def slot_id(
    client: TestClient,
    admin_headers: dict[str, str],
    add_time_slot: Callable[..., int],
) -> int:
    """Un slot liber, miercuri 2 decembrie 2026, 10:00 – 11:00."""
    response = client.post("/facilitati", json=FACILITY, headers=admin_headers)
    assert response.status_code == 201
    return add_time_slot(response.json()["id"], SLOT_DAY, "10:00", "11:00")


@pytest.fixture
def user(log_in: Callable[..., tuple[int, dict[str, str]]]) -> tuple[int, dict]:
    """Un utilizator autentificat: id-ul și header-ul cu token-ul lui."""
    return log_in("ana.popescu@student.usv.ro")


def book(client: TestClient, headers: dict, slot: int):
    """Rezervă slotul dat."""
    return client.post(
        "/rezervari",
        json={"slot_id": slot, "regulament_acceptat": True},
        headers=headers,
    )


def notifications(client: TestClient, headers: dict, **filters: object) -> list:
    """Notificările utilizatorului autentificat."""
    response = client.get(URL, headers=headers, params=filters)
    assert response.status_code == 200
    return response.json()


def mark(client: TestClient, headers: dict, notification: object, body: object):
    """Trimite cererea de marcare a unei notificări."""
    return client.patch(f"{URL}/{notification}", json=body, headers=headers)


def count_notifications() -> int:
    """Numărul de notificări din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(text("SELECT COUNT(*) FROM notification"))


def is_read_in_db(notification: int) -> bool:
    """Valoarea is_read din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT is_read FROM notification WHERE id = :id"),
            {"id": notification},
        )


# Notificările create automat


def test_new_user_has_no_notifications(client: TestClient, user: tuple) -> None:
    assert notifications(client, user[1]) == []


def test_booking_creates_confirmation_notification(
    client: TestClient, user: tuple, slot_id: int
) -> None:
    assert book(client, user[1], slot_id).status_code == 201

    [notification] = notifications(client, user[1])

    assert notification["id"] > 0
    assert notification["tip"] == "confirmare"
    assert notification["mesaj"] == SLOT_TEXT
    assert notification["citita"] is False
    created = datetime.fromisoformat(notification["data"])
    assert created.tzinfo is not None
    assert abs(datetime.now(timezone.utc) - created) < timedelta(minutes=1)


def test_cancellation_creates_notification_listed_first(
    client: TestClient, user: tuple, slot_id: int
) -> None:
    booking = book(client, user[1], slot_id).json()["id"]

    assert client.delete(f"/rezervari/{booking}", headers=user[1]).status_code == 204

    result = notifications(client, user[1])
    assert [(n["tip"], n["mesaj"]) for n in result] == [
        ("anulare", SLOT_TEXT),
        ("confirmare", SLOT_TEXT),
    ]


def test_refused_booking_creates_no_notification(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict]],
    user: tuple,
    slot_id: int,
) -> None:
    _, other_headers = log_in("mihai.ionescu@student.usv.ro")
    assert book(client, other_headers, slot_id).status_code == 201

    # Slotul e deja ocupat: rezervarea e refuzată, deci nu apare nicio notificare.
    assert book(client, user[1], slot_id).status_code == 409

    assert notifications(client, user[1]) == []
    assert count_notifications() == 1


def test_refused_cancellation_creates_no_notification(
    client: TestClient,
    user: tuple,
    admin_headers: dict[str, str],
    add_time_slot: Callable[..., int],
) -> None:
    facility = client.post("/facilitati", json=FACILITY, headers=admin_headers)
    # Slot peste mai puțin de 24 de ore: anularea e refuzată (400).
    slot = add_time_slot(facility.json()["id"], "2026-12-01", "10:00", "11:00")
    booking = book(client, user[1], slot).json()["id"]

    assert client.delete(f"/rezervari/{booking}", headers=user[1]).status_code == 400

    assert [n["tip"] for n in notifications(client, user[1])] == ["confirmare"]


def test_user_sees_only_own_notifications(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict]],
    user: tuple,
    slot_id: int,
) -> None:
    _, other_headers = log_in("mihai.ionescu@student.usv.ro")
    book(client, other_headers, slot_id)

    assert notifications(client, user[1]) == []
    assert len(notifications(client, other_headers)) == 1


# GET /notificari


def test_unread_filter_returns_only_unread(
    client: TestClient, user: tuple, slot_id: int
) -> None:
    booking = book(client, user[1], slot_id).json()["id"]
    client.delete(f"/rezervari/{booking}", headers=user[1])
    confirmation = notifications(client, user[1])[1]
    mark(client, user[1], confirmation["id"], {"citita": True})

    unread = notifications(client, user[1], necitite=True)
    every = notifications(client, user[1], necitite=False)

    assert [n["tip"] for n in unread] == ["anulare"]
    assert len(every) == 2


@pytest.mark.parametrize("value", ["abc", "2", ""])
def test_unread_filter_with_invalid_value_returns_400(
    client: TestClient, user: tuple, value: str
) -> None:
    response = client.get(URL, headers=user[1], params={"necitite": value})

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer token-inventat"}],
    ids=["fara-token", "token-gresit"],
)
def test_list_notifications_without_valid_token_returns_401(
    client: TestClient, headers: dict
) -> None:
    assert client.get(URL, headers=headers).status_code == 401


# PATCH /notificari/{id}


@pytest.fixture
def notification_id(client: TestClient, user: tuple, slot_id: int) -> int:
    """Notificarea de confirmare a unei rezervări a utilizatorului."""
    book(client, user[1], slot_id)
    return notifications(client, user[1])[0]["id"]


def test_mark_notification_as_read_returns_200(
    client: TestClient, user: tuple, notification_id: int
) -> None:
    response = mark(client, user[1], notification_id, {"citita": True})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == notification_id
    assert data["citita"] is True
    assert data["tip"] == "confirmare"
    assert is_read_in_db(notification_id) is True


def test_mark_notification_as_unread_again(
    client: TestClient, user: tuple, notification_id: int
) -> None:
    mark(client, user[1], notification_id, {"citita": True})

    response = mark(client, user[1], notification_id, {"citita": False})

    assert response.status_code == 200
    assert response.json()["citita"] is False
    assert is_read_in_db(notification_id) is False


def test_mark_other_users_notification_returns_404(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict]],
    notification_id: int,
) -> None:
    _, other_headers = log_in("mihai.ionescu@student.usv.ro")

    response = mark(client, other_headers, notification_id, {"citita": True})

    # Același răspuns ca pentru o notificare inexistentă.
    assert response.status_code == 404
    assert response.json() == {"mesaj": "Notificarea nu există."}
    assert is_read_in_db(notification_id) is False


@pytest.mark.parametrize("notification", [999, 0, -1, 2**40])
def test_mark_missing_notification_returns_404(
    client: TestClient, user: tuple, notification: int
) -> None:
    response = mark(client, user[1], notification, {"citita": True})

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Notificarea nu există."}


@pytest.mark.parametrize(
    "body",
    [{}, {"citita": None}, {"citita": "true"}, {"citita": 1}, {"alt_camp": True}],
    ids=["gol", "null", "text", "numar", "camp-gresit"],
)
def test_mark_notification_with_invalid_body_returns_400(
    client: TestClient, user: tuple, notification_id: int, body: object
) -> None:
    response = mark(client, user[1], notification_id, body)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert is_read_in_db(notification_id) is False


def test_mark_notification_without_body_returns_400(
    client: TestClient, user: tuple, notification_id: int
) -> None:
    response = client.patch(f"{URL}/{notification_id}", headers=user[1])

    assert response.status_code == 400


def test_mark_notification_with_invalid_id_returns_400(
    client: TestClient, user: tuple
) -> None:
    response = mark(client, user[1], "abc", {"citita": True})

    assert response.status_code == 400


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer token-inventat"}],
    ids=["fara-token", "token-gresit"],
)
def test_mark_notification_without_valid_token_returns_401(
    client: TestClient, notification_id: int, headers: dict
) -> None:
    response = mark(client, headers, notification_id, {"citita": True})

    assert response.status_code == 401
    assert is_read_in_db(notification_id) is False
