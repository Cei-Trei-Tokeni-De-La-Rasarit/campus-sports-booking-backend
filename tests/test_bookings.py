"""Testele pentru rezervarea unui slot (POST /rezervari)."""

import threading
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services import booking_service

URL = "/rezervari"
FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}


@pytest.fixture
def user(log_in: Callable[..., tuple[int, dict[str, str]]]) -> tuple[int, dict]:
    """Un utilizator autentificat: id-ul și header-ul cu token-ul lui."""
    return log_in()


@pytest.fixture
def slot_id(client: TestClient, add_time_slot: Callable[..., int]) -> int:
    """Un slot liber la o facilitate activă."""
    return add_time_slot(create_facility(client), "2026-12-01", "10:00", "11:00")


def create_facility(client: TestClient, **changes: object) -> int:
    """Adaugă o facilitate prin API și întoarce id-ul ei."""
    response = client.post("/facilitati", json={**FACILITY, **changes})
    assert response.status_code == 201
    return response.json()["id"]


def book(client: TestClient, headers: dict, slot: object, accepted: object = True):
    """Trimite cererea de rezervare pentru slotul dat."""
    return client.post(
        URL, json={"slot_id": slot, "regulament_acceptat": accepted}, headers=headers
    )


def slot_status(slot: int) -> str:
    """Starea slotului din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT status FROM time_slot WHERE id = :id"), {"id": slot}
        )


def count_bookings() -> int:
    """Numărul de rezervări din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(text("SELECT COUNT(*) FROM booking"))


def assert_nothing_booked(slot: int) -> None:
    """Verifică că nu s-a creat nicio rezervare și slotul a rămas liber."""
    assert count_bookings() == 0
    assert slot_status(slot) == "free"


def assert_invalid_data(response, slot: int) -> None:
    """Verifică răspunsul 400 și că nu s-a rezervat nimic."""
    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert_nothing_booked(slot)


# Cazul reușit


def test_book_slot_returns_201_with_booking_data(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    user_id, headers = user

    response = book(client, headers, slot_id)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["utilizator_id"] == user_id
    assert data["stare"] == "confirmata"
    assert data["data_crearii"]
    assert data["slot"] == {
        "id": slot_id,
        "facilitate_id": data["slot"]["facilitate_id"],
        "data": "2026-12-01",
        "ora_start": "10:00",
        "ora_sfarsit": "11:00",
        "stare": "rezervat",
    }


def test_book_slot_marks_slot_booked_and_saves_booking(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    user_id, headers = user

    book(client, headers, slot_id)

    assert slot_status(slot_id) == "booked"
    with engine.connect() as connection:
        saved = connection.execute(
            text("SELECT user_id, slot_id, status FROM booking")
        ).all()
    assert saved == [(user_id, slot_id, "confirmed")]


def test_booked_slot_appears_as_booked_in_calendar(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    facility_id = book(client, user[1], slot_id).json()["slot"]["facilitate_id"]

    response = client.get(
        f"/facilitati/{facility_id}/sloturi",
        params={"de_la": "2026-12-01", "pana_la": "2026-12-01"},
    )

    assert response.json()[0]["stare"] == "rezervat"


def test_book_slot_ignores_user_id_sent_in_body(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict]],
    slot_id: int,
) -> None:
    other_id, _ = log_in("alt.student@student.usv.ro")
    user_id, headers = log_in()

    response = client.post(
        URL,
        json={
            "slot_id": slot_id,
            "regulament_acceptat": True,
            "utilizator_id": other_id,
        },
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["utilizator_id"] == user_id


# Autentificare


def test_book_slot_without_token_returns_401(client: TestClient, slot_id: int) -> None:
    response = book(client, {}, slot_id)

    assert response.status_code == 401
    assert response.json() == {"mesaj": "Lipsește token-ul de autentificare."}
    assert_nothing_booked(slot_id)


@pytest.mark.parametrize(
    "header", ["Bearer token-inventat", "Basic YWJjOmRlZg==", "Bearer "]
)
def test_book_slot_with_invalid_token_returns_401(
    client: TestClient, slot_id: int, header: str
) -> None:
    response = book(client, {"Authorization": header}, slot_id)

    assert response.status_code == 401
    assert_nothing_booked(slot_id)


def test_book_slot_without_token_and_invalid_data_returns_401(
    client: TestClient,
) -> None:
    # Fără cont, nu primești nici măcar detalii despre datele greșite.
    response = client.post(URL, json={})

    assert response.status_code == 401


# Regulamentul


@pytest.mark.parametrize("accepted", [False, None, "da", 1, "true"])
def test_book_slot_without_accepted_rules_returns_400(
    client: TestClient, user: tuple[int, dict], slot_id: int, accepted: object
) -> None:
    response = book(client, user[1], slot_id, accepted)

    assert_invalid_data(response, slot_id)
    assert "regulament_acceptat" in response.json()["mesaj"]


def test_book_slot_with_rules_refused_explains_why(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    response = book(client, user[1], slot_id, False)

    assert "Trebuie să accepți regulamentul" in response.json()["mesaj"]


# Datele trimise


@pytest.mark.parametrize("field", ["slot_id", "regulament_acceptat"])
def test_book_slot_without_field_returns_400(
    client: TestClient, user: tuple[int, dict], slot_id: int, field: str
) -> None:
    data = {"slot_id": slot_id, "regulament_acceptat": True}
    del data[field]

    response = client.post(URL, json=data, headers=user[1])

    assert_invalid_data(response, slot_id)
    assert field in response.json()["mesaj"]


@pytest.mark.parametrize(
    "value", [None, "", "1", "abc", 1.5, True, [1], 0, -1, 2_147_483_648]
)
def test_book_slot_with_invalid_slot_id_returns_400(
    client: TestClient, user: tuple[int, dict], slot_id: int, value: object
) -> None:
    response = book(client, user[1], value)

    assert_invalid_data(response, slot_id)
    assert "slot_id" in response.json()["mesaj"]


def test_book_slot_with_empty_body_returns_400(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    assert_invalid_data(client.post(URL, json={}, headers=user[1]), slot_id)


def test_book_slot_without_body_returns_400(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    assert_invalid_data(client.post(URL, headers=user[1]), slot_id)


# Slotul


def test_book_missing_slot_returns_404(
    client: TestClient, user: tuple[int, dict], slot_id: int
) -> None:
    response = book(client, user[1], slot_id + 1000)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Slotul nu există."}
    assert_nothing_booked(slot_id)


@pytest.mark.parametrize("status", ["booked", "blocked"])
def test_book_slot_that_is_not_free_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    add_time_slot: Callable[..., int],
    status: str,
) -> None:
    slot = add_time_slot(create_facility(client), status=status)

    response = book(client, user[1], slot)

    assert response.status_code == 409
    assert response.json() == {"mesaj": "Slotul nu mai este liber."}
    assert count_bookings() == 0
    assert slot_status(slot) == status


def test_book_same_slot_twice_returns_409(
    client: TestClient, log_in: Callable[..., tuple[int, dict]], slot_id: int
) -> None:
    _, first = log_in("primul@student.usv.ro")
    _, second = log_in("al.doilea@student.usv.ro")
    assert book(client, first, slot_id).status_code == 201

    response = book(client, second, slot_id)

    assert response.status_code == 409
    assert count_bookings() == 1


@pytest.mark.parametrize("status", ["mentenanta", "inactiva"])
def test_book_slot_of_unavailable_facility_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    add_time_slot: Callable[..., int],
    status: str,
) -> None:
    slot = add_time_slot(create_facility(client, status=status))

    response = book(client, user[1], slot)

    assert response.status_code == 409
    assert response.json() == {"mesaj": "Facilitatea nu poate fi rezervată acum."}
    assert_nothing_booked(slot)


# Cereri în același timp


def test_simultaneous_bookings_of_same_slot_only_one_succeeds(
    user: tuple[int, dict], slot_id: int
) -> None:
    user_id, _ = user
    requests = 5
    start_together = threading.Barrier(requests)
    results: list[str] = []

    def try_to_book() -> None:
        with SessionLocal() as db:
            start_together.wait()
            try:
                booking_service.create_booking(db, user_id, slot_id)
                results.append("rezervat")
            except booking_service.SlotNotAvailableError:
                results.append("ocupat")

    threads = [threading.Thread(target=try_to_book) for _ in range(requests)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["ocupat"] * (requests - 1) + ["rezervat"]
    assert count_bookings() == 1
    assert slot_status(slot_id) == "booked"
