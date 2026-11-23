"""Testele pentru reprogramarea unei rezervări (PATCH /rezervari/{id}, KAN-113)."""

import threading
from collections.abc import Callable
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services import booking_service, facility_service

FACILITY = {"nume": "Sala 1", "sport": "Tenis", "locatie": "Corp A", "capacitate": 4}

# „Acum” e fixat: 30 noiembrie 2026, ora 12:00 (ora României). Intervalele de
# pe 2 decembrie sunt la peste 24 de ore, deci rezervările se pot reprograma.
NOW = datetime(2026, 11, 30, 12, 0)
DAY = "2026-12-02"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ora României e fixată la NOW."""
    monkeypatch.setattr(facility_service, "romania_now", lambda db: NOW)


@pytest.fixture
def facility_id(client: TestClient, admin_headers: dict[str, str]) -> int:
    """O facilitate activă."""
    response = client.post("/facilitati", json=FACILITY, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def user(log_in: Callable[..., tuple[int, dict[str, str]]]) -> tuple[int, dict]:
    """Un utilizator autentificat: id-ul și header-ul cu token-ul lui."""
    return log_in("student.reprogramare@student.usv.ro")


def book(client: TestClient, headers: dict, slot: int) -> int:
    """Rezervă intervalul prin API și întoarce id-ul rezervării."""
    response = client.post(
        "/rezervari",
        json={"slot_id": slot, "regulament_acceptat": True},
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


def reschedule(client: TestClient, headers: dict, booking: int, slot: object):
    """Trimite cererea de reprogramare."""
    return client.patch(
        f"/rezervari/{booking}", json={"slot_id": slot}, headers=headers
    )


def slot_status(slot: int) -> str:
    """Starea intervalului din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT status FROM time_slot WHERE id = :id"), {"id": slot}
        )


def booking_row(booking: int) -> tuple[int, str]:
    """(intervalul, starea) rezervării din baza de test."""
    with engine.connect() as connection:
        return tuple(
            connection.execute(
                text("SELECT slot_id, status FROM booking WHERE id = :id"),
                {"id": booking},
            ).one()
        )


def notification_types(user_id: int) -> list[str]:
    """Tipurile notificărilor utilizatorului, în ordinea creării."""
    with engine.connect() as connection:
        return list(
            connection.scalars(
                text("SELECT type FROM notification WHERE user_id = :id ORDER BY id"),
                {"id": user_id},
            )
        )


def assert_unchanged(booking: int, old_slot: int, new_slot: int) -> None:
    """Rezervarea a rămas pe intervalul vechi, iar intervalul nou e liber."""
    assert booking_row(booking) == (old_slot, "confirmed")
    assert slot_status(old_slot) == "booked"
    assert slot_status(new_slot) == "free"


# Cazul reușit.


def test_reschedule_moves_booking_to_new_slot(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == booking
    assert data["stare"] == "confirmata"
    assert data["slot"]["id"] == new_slot
    assert data["slot"]["ora_start"] == "15:00"
    assert booking_row(booking) == (new_slot, "confirmed")
    assert slot_status(old_slot) == "free"
    assert slot_status(new_slot) == "booked"


def test_reschedule_adds_notification_with_both_slots(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, "2026-12-03", "15:00", "16:00")
    booking = book(client, user[1], old_slot)

    reschedule(client, user[1], booking, new_slot)

    assert notification_types(user[0]) == ["confirmation", "reschedule"]
    notification = client.get("/notificari", headers=user[1]).json()[0]
    assert notification["tip"] == "reprogramare"
    assert notification["mesaj"] == (
        "Sala 1 · Miercuri, 2 decembrie · 10:00 – 11:00 → "
        "Sala 1 · Joi, 3 decembrie · 15:00 – 16:00"
    )


def test_reschedule_to_overlapping_slot_of_same_booking_is_allowed(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    # 10:00-12:00 mutat pe 11:00-13:00: se suprapune doar cu rezervarea mutată.
    old_slot = add_time_slot(facility_id, DAY, "10:00", "12:00")
    new_slot = add_time_slot(facility_id, DAY, "11:00", "13:00")
    booking = book(client, user[1], old_slot)

    assert reschedule(client, user[1], booking, new_slot).status_code == 200


def test_reschedule_when_user_has_maximum_bookings(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    # Cu 3 rezervări active (maximul), reprogramarea tot merge: numărul nu crește.
    bookings = [
        book(client, user[1], add_time_slot(facility_id, DAY, f"{h}:00", f"{h + 1}:00"))
        for h in (8, 10, 12)
    ]
    new_slot = add_time_slot(facility_id, DAY, "18:00", "19:00")

    assert reschedule(client, user[1], bookings[0], new_slot).status_code == 200


# Rezervarea.


def test_reschedule_without_token_returns_401(
    client: TestClient, facility_id: int, add_time_slot: Callable[..., int]
) -> None:
    slot = add_time_slot(facility_id, DAY, "10:00", "11:00")

    assert client.patch("/rezervari/1", json={"slot_id": slot}).status_code == 401


@pytest.mark.parametrize("booking", [999999, 2**40])
def test_reschedule_missing_booking_returns_404(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
    booking: int,
) -> None:
    slot = add_time_slot(facility_id, DAY, "10:00", "11:00")

    response = reschedule(client, user[1], booking, slot)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Rezervarea nu există."}


def test_reschedule_booking_of_another_user_returns_404(
    client: TestClient,
    user: tuple[int, dict],
    log_in: Callable[..., tuple[int, dict[str, str]]],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)
    _, other = log_in("altcineva@student.usv.ro")

    response = reschedule(client, other, booking, new_slot)

    assert response.status_code == 404
    assert_unchanged(booking, old_slot, new_slot)


def test_reschedule_cancelled_booking_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)
    client.delete(f"/rezervari/{booking}", headers=user[1])

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 409
    assert booking_row(booking) == (old_slot, "cancelled")
    assert slot_status(new_slot) == "free"


def test_reschedule_less_than_24_hours_before_returns_400(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    # 1 decembrie, 11:00 e la 23 de ore de NOW.
    old_slot = add_time_slot(facility_id, "2026-12-01", "11:00", "12:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 400
    assert "24 de ore" in response.json()["mesaj"]
    assert_unchanged(booking, old_slot, new_slot)


# Intervalul nou.


def test_reschedule_to_same_slot_returns_400(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    booking = book(client, user[1], slot)

    response = reschedule(client, user[1], booking, slot)

    assert response.status_code == 400
    assert booking_row(booking) == (slot, "confirmed")
    assert slot_status(slot) == "booked"


def test_reschedule_to_missing_slot_returns_404(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, 999999)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Slotul nu există."}


def test_reschedule_to_slot_of_another_facility_returns_400(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    admin_headers: dict[str, str],
    add_time_slot: Callable[..., int],
) -> None:
    other = client.post(
        "/facilitati", json={**FACILITY, "nume": "Sala 2"}, headers=admin_headers
    ).json()["id"]
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(other, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 400
    assert "aceeași sală" in response.json()["mesaj"]
    assert_unchanged(booking, old_slot, new_slot)


@pytest.mark.parametrize(
    ("new_status", "start", "end"),
    [
        ("booked", "15:00", "16:00"),
        ("blocked", "15:00", "16:00"),
    ],
)
def test_reschedule_to_slot_that_is_not_free_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
    new_status: str,
    start: str,
    end: str,
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, start, end, new_status)
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 409
    assert response.json() == {"mesaj": "Slotul nu mai este liber."}
    assert booking_row(booking) == (old_slot, "confirmed")
    assert slot_status(old_slot) == "booked"
    assert slot_status(new_slot) == new_status


def test_reschedule_to_started_slot_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, "2026-11-30", "11:00", "13:00")
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 409
    assert "a început" in response.json()["mesaj"]
    assert_unchanged(booking, old_slot, new_slot)


def test_reschedule_when_facility_is_inactive_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    admin_headers: dict[str, str],
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)
    client.put(
        f"/facilitati/{facility_id}",
        json={**FACILITY, "status": "inactiva"},
        headers=admin_headers,
    )

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 409
    assert_unchanged(booking, old_slot, new_slot)


def test_reschedule_overlapping_another_booking_returns_409(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    admin_headers: dict[str, str],
    add_time_slot: Callable[..., int],
) -> None:
    other_facility = client.post(
        "/facilitati", json={**FACILITY, "nume": "Sala 2"}, headers=admin_headers
    ).json()["id"]
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)
    # Altă rezervare a aceluiași utilizator, în altă sală, la aceeași oră.
    book(client, user[1], add_time_slot(other_facility, DAY, "15:30", "16:30"))

    response = reschedule(client, user[1], booking, new_slot)

    assert response.status_code == 409
    assert "se suprapune" in response.json()["mesaj"]
    assert_unchanged(booking, old_slot, new_slot)


@pytest.mark.parametrize("slot", ["5", 5.0, True, None, 0, -1, 2**31])
def test_reschedule_with_invalid_slot_id_returns_400(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
    slot: object,
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    booking = book(client, user[1], old_slot)

    response = reschedule(client, user[1], booking, slot)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert booking_row(booking) == (old_slot, "confirmed")


def test_reschedule_without_body_returns_400(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    booking = book(client, user[1], add_time_slot(facility_id, DAY, "10:00", "11:00"))

    response = client.patch(f"/rezervari/{booking}", headers=user[1])

    assert response.status_code == 400


# Cereri în același timp.


def run_together(requests: list[Callable[[], None]]) -> None:
    """Pornește cererile în același moment, pe fire de execuție separate.

    O eroare neprevăzută într-un fir (de exemplu, un deadlock în PostgreSQL)
    face testul să pice, nu doar să afișeze un avertisment.
    """
    start_together = threading.Barrier(len(requests))
    errors: list[BaseException] = []

    def run(request: Callable[[], None]) -> None:
        start_together.wait()
        try:
            request()
        except Exception as error:  # noqa: BLE001 - o raportăm mai jos
            errors.append(error)

    threads = [threading.Thread(target=run, args=(r,)) for r in requests]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


def test_simultaneous_reschedules_to_same_slot_only_one_succeeds(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict[str, str]]],
    facility_id: int,
    add_time_slot: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = [log_in(f"student{i}@student.usv.ro") for i in range(3)]
    bookings = [
        (
            user_id,
            book(
                client,
                headers,
                add_time_slot(facility_id, DAY, f"{h}:00", f"{h + 1}:00"),
            ),
        )
        for (user_id, headers), h in zip(users, (8, 9, 10), strict=True)
    ]
    target = add_time_slot(facility_id, DAY, "18:00", "19:00")
    results: list[str] = []
    # Toate cererile trec de verificări înainte ca vreuna să ocupe intervalul.
    all_checked = threading.Barrier(len(bookings))

    def now_after_all_checked(db: object) -> datetime:
        all_checked.wait()
        return NOW

    monkeypatch.setattr(facility_service, "romania_now", now_after_all_checked)

    def attempt(user_id: int, booking: int) -> Callable[[], None]:
        def run() -> None:
            with SessionLocal() as db:
                try:
                    booking_service.reschedule_booking(db, user_id, booking, target)
                    results.append("mutat")
                except booking_service.SlotNotAvailableError:
                    results.append("refuzat")

        return run

    run_together([attempt(user_id, booking) for user_id, booking in bookings])

    assert sorted(results) == ["mutat"] + ["refuzat"] * 2
    with engine.connect() as connection:
        on_target = connection.scalar(
            text("SELECT COUNT(*) FROM booking WHERE slot_id = :id"), {"id": target}
        )
    assert on_target == 1
    assert slot_status(target) == "booked"


def test_simultaneous_reschedule_and_cancel_leave_consistent_state(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)

    def move() -> None:
        with SessionLocal() as db:
            try:
                booking_service.reschedule_booking(db, user[0], booking, new_slot)
            except booking_service.BookingAlreadyCancelledError:
                pass

    def cancel() -> None:
        with SessionLocal() as db:
            try:
                booking_service.cancel_booking(db, user[0], booking)
            except booking_service.BookingAlreadyCancelledError:
                pass

    run_together([move, cancel])

    slot, status = booking_row(booking)
    if status == "cancelled":
        # Anularea a câștigat: niciun interval nu rămâne ocupat.
        assert slot_status(old_slot) == "free"
        assert slot_status(new_slot) == "free"
    else:
        # Reprogramarea a câștigat: doar intervalul nou e ocupat.
        assert slot == new_slot
        assert slot_status(new_slot) == "booked"
        assert slot_status(old_slot) == "free"


def test_cancel_after_concurrent_reschedule_frees_the_new_slot(
    client: TestClient,
    user: tuple[int, dict],
    facility_id: int,
    add_time_slot: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_slot = add_time_slot(facility_id, DAY, "10:00", "11:00")
    new_slot = add_time_slot(facility_id, DAY, "15:00", "16:00")
    booking = book(client, user[1], old_slot)
    real_check = booking_service.can_be_cancelled
    moved = []

    # Anularea a citit deja rezervarea (pe intervalul vechi); exact acum o
    # reprogramare, din altă sesiune, o mută pe intervalul nou.
    def reschedule_in_between(slot: object, now: datetime) -> bool:
        if not moved:
            moved.append(True)
            with SessionLocal() as other:
                booking_service.reschedule_booking(other, user[0], booking, new_slot)
        return real_check(slot, now)

    monkeypatch.setattr(booking_service, "can_be_cancelled", reschedule_in_between)

    with SessionLocal() as db:
        booking_service.cancel_booking(db, user[0], booking)

    # Rezervarea e anulată și niciun interval nu rămâne ocupat de ea.
    assert booking_row(booking) == (new_slot, "cancelled")
    assert slot_status(new_slot) == "free"
    assert slot_status(old_slot) == "free"
