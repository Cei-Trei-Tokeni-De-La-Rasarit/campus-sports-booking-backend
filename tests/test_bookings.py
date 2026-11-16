"""Testele pentru rezervarea unui slot (POST /rezervari)."""

import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services import booking_service, facility_service

URL = "/rezervari"
FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}

# „Acum” e fixat cu o zi înaintea sloturilor din teste (1 decembrie 2026),
# ca testele să nu depindă de ziua în care rulează.
NOW = datetime(2026, 11, 30, 12, 0)
ADMIN_HEADERS: dict[str, str] = {}


@pytest.fixture(autouse=True)
def set_admin_headers(admin_headers: dict[str, str]) -> None:
    """Pune la dispoziția helperelor de setup un administrator autentificat."""
    ADMIN_HEADERS.clear()
    ADMIN_HEADERS.update(admin_headers)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Face ca „acum” să fie 30 noiembrie 2026, ora 12:00 (ora României)."""
    monkeypatch.setattr(facility_service, "romania_now", lambda db: NOW)


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
    response = client.post(
        "/facilitati", json={**FACILITY, **changes}, headers=ADMIN_HEADERS
    )
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
    created = datetime.fromisoformat(data["data_crearii"])
    assert created.tzinfo is not None
    assert abs(datetime.now(timezone.utc) - created) < timedelta(minutes=1)
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


@pytest.mark.parametrize(
    ("slot_date", "start", "end"),
    [
        ("2026-11-29", "14:00", "15:00"),
        ("2026-11-30", "10:00", "11:00"),
        ("2026-11-30", "11:30", "12:30"),
        ("2026-11-30", "12:00", "13:00"),
    ],
    ids=["ieri", "s-a-terminat-azi", "a-inceput", "incepe-acum"],
)
def test_book_slot_that_has_started_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    add_time_slot: Callable[..., int],
    slot_date: str,
    start: str,
    end: str,
) -> None:
    slot = add_time_slot(create_facility(client), slot_date, start, end)

    response = book(client, user[1], slot)

    assert response.status_code == 409
    assert response.json() == {
        "mesaj": "Slotul a început deja și nu mai poate fi rezervat."
    }
    assert_nothing_booked(slot)


def test_book_slot_later_today_returns_201(
    client: TestClient, user: tuple[int, dict], add_time_slot: Callable[..., int]
) -> None:
    slot = add_time_slot(create_facility(client), "2026-11-30", "12:01", "13:00")

    assert book(client, user[1], slot).status_code == 201


# Rezervări suprapuse și numărul maxim
TOMORROW = "2026-12-01"


def add_booking(user_id: int, slot: int, status: str = "confirmed") -> None:
    """Scrie o rezervare direct în baza de test (de exemplu, una anulată)."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO booking (user_id, slot_id, status) "
                "VALUES (:user_id, :slot_id, :status)"
            ),
            {"user_id": user_id, "slot_id": slot, "status": status},
        )


OVERLAP_MESSAGE = {"mesaj": "Ai deja o rezervare care se suprapune cu acest interval."}


@pytest.mark.parametrize(
    ("start", "end"),
    [("10:00", "11:00"), ("10:30", "11:30"), ("09:30", "10:30"), ("10:15", "10:45")],
    ids=["aceeasi-ora", "incepe-in-timpul", "se-termina-in-timpul", "inclus"],
)
def test_book_overlapping_slot_at_other_facility_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    slot_id: int,
    add_time_slot: Callable[..., int],
    start: str,
    end: str,
) -> None:
    assert book(client, user[1], slot_id).status_code == 201
    other = add_time_slot(create_facility(client), TOMORROW, start, end)

    response = book(client, user[1], other)

    assert response.status_code == 409
    assert response.json() == OVERLAP_MESSAGE
    assert count_bookings() == 1
    assert slot_status(other) == "free"


@pytest.mark.parametrize(
    ("slot_date", "start", "end"),
    [
        (TOMORROW, "11:00", "12:00"),
        (TOMORROW, "09:00", "10:00"),
        ("2026-12-02", "10:00", "11:00"),
    ],
    ids=["imediat-dupa", "imediat-inainte", "alta-zi"],
)
def test_book_slot_next_to_own_booking_returns_201(
    client: TestClient,
    user: tuple[int, dict],
    slot_id: int,
    add_time_slot: Callable[..., int],
    slot_date: str,
    start: str,
    end: str,
) -> None:
    book(client, user[1], slot_id)
    other = add_time_slot(create_facility(client), slot_date, start, end)

    assert book(client, user[1], other).status_code == 201


def test_cancelled_booking_does_not_block_same_interval(
    client: TestClient,
    user: tuple[int, dict],
    add_time_slot: Callable[..., int],
) -> None:
    user_id, headers = user
    old = add_time_slot(create_facility(client), TOMORROW, "10:00", "11:00")
    add_booking(user_id, old, "cancelled")
    other = add_time_slot(create_facility(client), TOMORROW, "10:00", "11:00")

    assert book(client, headers, other).status_code == 201


def test_other_users_booking_does_not_block_same_interval(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict]],
    slot_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    _, first = log_in("primul@student.usv.ro")
    _, second = log_in("al.doilea@student.usv.ro")
    book(client, first, slot_id)
    other = add_time_slot(create_facility(client), TOMORROW, "10:00", "11:00")

    assert book(client, second, other).status_code == 201


def add_free_slots(client: TestClient, add_time_slot: Callable, count: int) -> list:
    """Adaugă sloturi libere mâine, la ore diferite, care nu se suprapun."""
    facility = create_facility(client)
    return [
        add_time_slot(facility, TOMORROW, f"{8 + i:02d}:00", f"{8 + i:02d}:30")
        for i in range(count)
    ]


def test_fourth_active_booking_returns_409(
    client: TestClient, user: tuple[int, dict], add_time_slot: Callable[..., int]
) -> None:
    *first_three, fourth = add_free_slots(client, add_time_slot, 4)
    for slot in first_three:
        assert book(client, user[1], slot).status_code == 201

    response = book(client, user[1], fourth)

    assert response.status_code == 409
    assert response.json() == {"mesaj": "Poți avea cel mult 3 rezervări active."}
    assert count_bookings() == 3
    assert slot_status(fourth) == "free"


@pytest.mark.parametrize(
    ("slot_date", "start", "end", "status"),
    [
        ("2026-11-29", "10:00", "11:00", "confirmed"),
        ("2026-11-30", "11:00", "12:30", "confirmed"),
        (TOMORROW, "18:00", "19:00", "cancelled"),
    ],
    ids=["ieri", "a-inceput-azi", "anulata"],
)
def test_past_or_cancelled_bookings_do_not_count_to_maximum(
    client: TestClient,
    user: tuple[int, dict],
    add_time_slot: Callable[..., int],
    slot_date: str,
    start: str,
    end: str,
    status: str,
) -> None:
    user_id, headers = user
    old = add_time_slot(create_facility(client), slot_date, start, end, "booked")
    add_booking(user_id, old, status)

    for slot in add_free_slots(client, add_time_slot, 3):
        assert book(client, headers, slot).status_code == 201


def test_maximum_is_per_user(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict]],
    add_time_slot: Callable[..., int],
) -> None:
    _, first = log_in("primul@student.usv.ro")
    _, second = log_in("al.doilea@student.usv.ro")
    slots = add_free_slots(client, add_time_slot, 4)
    for slot in slots[:3]:
        book(client, first, slot)

    assert book(client, second, slots[3]).status_code == 201


# Cereri în același timp


def run_together(requests: list[Callable[[], None]]) -> None:
    """Pornește cererile date în același moment, pe fire de execuție separate."""
    start_together = threading.Barrier(len(requests))

    def run(request: Callable[[], None]) -> None:
        start_together.wait()
        request()

    threads = [threading.Thread(target=run, args=(r,)) for r in requests]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def booking_attempt(user_id: int, slot: int, results: list[str]) -> Callable:
    """O încercare de rezervare direct prin serviciu, cu sesiunea ei."""

    def attempt() -> None:
        with SessionLocal() as db:
            try:
                booking_service.create_booking(db, user_id, slot)
                results.append("rezervat")
            except (
                booking_service.SlotNotAvailableError,
                booking_service.TooManyBookingsError,
            ):
                results.append("refuzat")

    return attempt


def test_simultaneous_bookings_of_same_slot_only_one_succeeds(
    log_in: Callable[..., tuple[int, dict]], slot_id: int
) -> None:
    users = [log_in(f"student{i}@student.usv.ro")[0] for i in range(5)]
    results: list[str] = []

    run_together([booking_attempt(u, slot_id, results) for u in users])

    assert sorted(results) == ["refuzat"] * 4 + ["rezervat"]
    assert count_bookings() == 1
    assert slot_status(slot_id) == "booked"


def test_simultaneous_bookings_of_same_user_respect_the_maximum(
    client: TestClient, user: tuple[int, dict], add_time_slot: Callable[..., int]
) -> None:
    user_id, headers = user
    facility = create_facility(client)
    for hour in ("08", "09"):
        slot = add_time_slot(facility, TOMORROW, f"{hour}:00", f"{hour}:30")
        assert book(client, headers, slot).status_code == 201
    free_slots = [
        add_time_slot(facility, TOMORROW, f"{hour}:00", f"{hour}:30")
        for hour in ("14", "15", "16", "17")
    ]
    results: list[str] = []

    run_together([booking_attempt(user_id, s, results) for s in free_slots])

    # Mai era loc pentru o singură rezervare (maximul e 3).
    assert sorted(results) == ["refuzat"] * 3 + ["rezervat"]
    assert count_bookings() == 3
