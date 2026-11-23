"""Testele pentru programul pe zile (/facilitati/{id}/program) și pentru
intervalele generate din el (KAN-106)."""

from collections.abc import Callable
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.services import facility_service

# „Acum”, fixat ca testele să nu depindă de ceas: luni, 23.11.2026, ora 09:00.
NOW = datetime(2026, 11, 23, 9, 0)

FACILITY = {"nume": "Sala 1", "sport": "Tenis", "locatie": "Corp A", "capacitate": 4}

# Deschis doar lunea, 08:00-12:00, cu intervale de 2 ore.
MONDAY_MORNING = {
    "durata_slot": 120,
    "zile": [{"zi": 1, "deschidere": "08:00", "inchidere": "12:00"}],
}


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ora României e fixată la NOW."""
    monkeypatch.setattr(facility_service, "romania_now", lambda db: NOW)


@pytest.fixture(autouse=True)
def authenticate_as_admin(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Folosește un administrator pentru operațiile protejate."""
    client.headers.update(admin_headers)


@pytest.fixture
def facility_id(client: TestClient) -> int:
    """O facilitate nouă, fără program."""
    response = client.post("/facilitati", json=FACILITY)
    assert response.status_code == 201
    return response.json()["id"]


def put_schedule(client: TestClient, facility: int, schedule: dict):
    """Trimite programul nou al facilității."""
    return client.put(f"/facilitati/{facility}/program", json=schedule)


def slots(client: TestClient, facility: int, start: str, end: str) -> list[tuple]:
    """Intervalele din calendar, ca (data, început, sfârșit, stare)."""
    response = client.get(
        f"/facilitati/{facility}/sloturi", params={"de_la": start, "pana_la": end}
    )
    assert response.status_code == 200
    return [
        (slot["data"], slot["ora_start"], slot["ora_sfarsit"], slot["stare"])
        for slot in response.json()
    ]


def count_slots() -> int:
    """Numărul de intervale din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(text("SELECT COUNT(*) FROM time_slot"))


def slot_status(slot_id: int) -> str | None:
    """Starea intervalului sau None dacă a fost șters."""
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT status FROM time_slot WHERE id = :id"), {"id": slot_id}
        )


def add_booking(slot_id: int, user_id: int, status: str = "confirmed") -> None:
    """Adaugă o rezervare direct în baza de test."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO booking (user_id, slot_id, status) "
                "VALUES (:user_id, :slot_id, :status)"
            ),
            {"user_id": user_id, "slot_id": slot_id, "status": status},
        )


# Citirea și salvarea programului.


def test_facility_without_schedule_has_empty_program(
    client: TestClient, facility_id: int
) -> None:
    response = client.get(f"/facilitati/{facility_id}/program")

    assert response.status_code == 200
    assert response.json() == {"durata_slot": 120, "zile": []}


def test_put_schedule_saves_it_in_day_order(
    client: TestClient, facility_id: int
) -> None:
    schedule = {
        "durata_slot": 90,
        "zile": [
            {"zi": 6, "deschidere": "10:00", "inchidere": "13:00"},
            {"zi": 1, "deschidere": "08:00", "inchidere": "20:00"},
        ],
    }

    response = put_schedule(client, facility_id, schedule)

    assert response.status_code == 200
    expected = {"durata_slot": 90, "zile": schedule["zile"][::-1]}
    assert response.json() == {**expected, "rezervari_in_afara_programului": 0}
    assert client.get(f"/facilitati/{facility_id}/program").json() == expected


def test_put_schedule_replaces_the_old_one(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)
    new = {
        "durata_slot": 60,
        "zile": [{"zi": 3, "deschidere": "14:00", "inchidere": "16:00"}],
    }

    put_schedule(client, facility_id, new)

    assert client.get(f"/facilitati/{facility_id}/program").json() == new


def test_empty_day_list_means_closed_all_week(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)

    response = put_schedule(client, facility_id, {"durata_slot": 120, "zile": []})

    assert response.status_code == 200
    assert slots(client, facility_id, "2026-11-23", "2026-11-30") == []


def test_schedule_of_missing_facility_returns_404(client: TestClient) -> None:
    assert client.get("/facilitati/999999/program").status_code == 404
    assert put_schedule(client, 999999, MONDAY_MORNING).status_code == 404


def test_put_schedule_without_token_returns_401(
    client: TestClient, facility_id: int
) -> None:
    client.headers.pop("Authorization")

    assert put_schedule(client, facility_id, MONDAY_MORNING).status_code == 401


def test_put_schedule_as_client_returns_403(
    client: TestClient,
    facility_id: int,
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> None:
    _, headers = log_in("client.program@student.usv.ro")

    response = client.put(
        f"/facilitati/{facility_id}/program", json=MONDAY_MORNING, headers=headers
    )

    assert response.status_code == 403


def test_get_schedule_is_public(client: TestClient, facility_id: int) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)
    client.headers.pop("Authorization")

    assert client.get(f"/facilitati/{facility_id}/program").status_code == 200


@pytest.mark.parametrize(
    "schedule",
    [
        {"zile": []},
        {"durata_slot": 45, "zile": []},
        {"durata_slot": "120", "zile": []},
        {"durata_slot": 120},
        {"durata_slot": 120, "zile": None},
        {
            "durata_slot": 120,
            "zile": [{"zi": 0, "deschidere": "08:00", "inchidere": "10:00"}],
        },
        {
            "durata_slot": 120,
            "zile": [{"zi": 8, "deschidere": "08:00", "inchidere": "10:00"}],
        },
        {
            "durata_slot": 120,
            "zile": [{"zi": "1", "deschidere": "08:00", "inchidere": "10:00"}],
        },
        {"durata_slot": 120, "zile": [{"zi": 1, "inchidere": "10:00"}]},
        {
            "durata_slot": 120,
            "zile": [{"zi": 1, "deschidere": "8", "inchidere": "10:00"}],
        },
        {
            "durata_slot": 120,
            "zile": [{"zi": 1, "deschidere": "25:00", "inchidere": "10:00"}],
        },
        {
            "durata_slot": 120,
            "zile": [{"zi": 1, "deschidere": "08:00:30", "inchidere": "10:00"}],
        },
    ],
)
def test_invalid_schedule_returns_400(
    client: TestClient, facility_id: int, schedule: dict
) -> None:
    response = put_schedule(client, facility_id, schedule)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert client.get(f"/facilitati/{facility_id}/program").json()["zile"] == []


@pytest.mark.parametrize(
    ("days", "message"),
    [
        (
            [
                {"zi": 1, "deschidere": "08:00", "inchidere": "10:00"},
                {"zi": 1, "deschidere": "12:00", "inchidere": "14:00"},
            ],
            "o singură dată",
        ),
        ([{"zi": 1, "deschidere": "10:00", "inchidere": "10:00"}], "după ora de"),
        ([{"zi": 1, "deschidere": "12:00", "inchidere": "08:00"}], "după ora de"),
        ([{"zi": 2, "deschidere": "08:00", "inchidere": "09:00"}], "ziua 2"),
    ],
)
def test_schedule_rules_return_400_with_message(
    client: TestClient, facility_id: int, days: list, message: str
) -> None:
    response = put_schedule(client, facility_id, {"durata_slot": 120, "zile": days})

    assert response.status_code == 400
    assert message in response.json()["mesaj"]


def test_schedule_with_90_minute_slots_must_divide_exactly(
    client: TestClient, facility_id: int
) -> None:
    day = {"zi": 1, "deschidere": "08:00", "inchidere": "11:00"}

    assert (
        put_schedule(
            client, facility_id, {"durata_slot": 90, "zile": [day]}
        ).status_code
        == 200
    )
    assert (
        put_schedule(
            client, facility_id, {"durata_slot": 120, "zile": [day]}
        ).status_code
        == 400
    )


# Intervalele generate din program.


def test_calendar_generates_slots_from_schedule(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)

    assert slots(client, facility_id, "2026-11-23", "2026-11-30") == [
        ("2026-11-23", "08:00", "10:00", "liber"),
        ("2026-11-23", "10:00", "12:00", "liber"),
        ("2026-11-30", "08:00", "10:00", "liber"),
        ("2026-11-30", "10:00", "12:00", "liber"),
    ]


def test_calendar_does_not_duplicate_generated_slots(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)

    first = slots(client, facility_id, "2026-11-23", "2026-11-30")
    second = slots(client, facility_id, "2026-11-23", "2026-11-30")

    assert first == second
    assert count_slots() == 4


def test_calendar_does_not_generate_past_days(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)

    assert slots(client, facility_id, "2026-11-16", "2026-11-22") == []
    assert count_slots() == 0


def test_calendar_does_not_generate_beyond_the_horizon(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)

    # Ziua 56 de la 23.11.2026 e 18.01.2027 (luni); următoarea luni e în afara.
    assert slots(client, facility_id, "2027-01-18", "2027-01-25") == [
        ("2027-01-18", "08:00", "10:00", "liber"),
        ("2027-01-18", "10:00", "12:00", "liber"),
    ]


def test_generation_skips_slots_overlapping_existing_ones(
    client: TestClient, facility_id: int, add_time_slot: Callable[..., int]
) -> None:
    add_time_slot(facility_id, "2026-11-30", "09:00", "11:00", "booked")
    put_schedule(
        client,
        facility_id,
        {
            "durata_slot": 60,
            "zile": [{"zi": 1, "deschidere": "08:00", "inchidere": "12:00"}],
        },
    )

    assert slots(client, facility_id, "2026-11-30", "2026-11-30") == [
        ("2026-11-30", "08:00", "09:00", "liber"),
        ("2026-11-30", "09:00", "11:00", "rezervat"),
        ("2026-11-30", "11:00", "12:00", "liber"),
    ]


def test_facility_without_schedule_keeps_only_existing_slots(
    client: TestClient, facility_id: int, add_time_slot: Callable[..., int]
) -> None:
    add_time_slot(facility_id, "2026-11-30", "18:00", "19:00")

    assert slots(client, facility_id, "2026-11-23", "2026-11-30") == [
        ("2026-11-30", "18:00", "19:00", "liber"),
    ]


# Schimbarea programului și intervalele existente.


def test_changing_schedule_cleans_future_slots(
    client: TestClient,
    facility_id: int,
    add_time_slot: Callable[..., int],
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> None:
    user_id, _ = log_in("client.program@student.usv.ro")
    # Toate în afara noului program (luni 08:00-12:00), în afară de primul.
    kept_free = add_time_slot(facility_id, "2026-11-30", "08:00", "10:00")
    free_outside = add_time_slot(facility_id, "2026-11-30", "18:00", "20:00")
    other_day = add_time_slot(facility_id, "2026-12-01", "08:00", "10:00")
    booked = add_time_slot(facility_id, "2026-11-30", "14:00", "16:00", "booked")
    add_booking(booked, user_id)
    blocked = add_time_slot(facility_id, "2026-11-30", "16:00", "18:00", "blocked")
    with_history = add_time_slot(facility_id, "2026-12-02", "08:00", "10:00")
    add_booking(with_history, user_id, "cancelled")
    # Azi, deja început (NOW e 09:00): trecutul nu se atinge.
    started = add_time_slot(facility_id, "2026-11-23", "08:30", "09:30")

    response = put_schedule(client, facility_id, MONDAY_MORNING)

    assert response.status_code == 200
    assert response.json()["rezervari_in_afara_programului"] == 1
    assert slot_status(kept_free) == "free"
    assert slot_status(free_outside) is None
    assert slot_status(other_day) is None
    assert slot_status(booked) == "booked"
    assert slot_status(blocked) == "blocked"
    assert slot_status(with_history) == "blocked"
    assert slot_status(started) == "free"


def test_changing_slot_duration_replaces_free_slots(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)
    slots(client, facility_id, "2026-11-30", "2026-11-30")

    put_schedule(
        client,
        facility_id,
        {
            "durata_slot": 60,
            "zile": [{"zi": 1, "deschidere": "08:00", "inchidere": "10:00"}],
        },
    )

    assert slots(client, facility_id, "2026-11-30", "2026-11-30") == [
        ("2026-11-30", "08:00", "09:00", "liber"),
        ("2026-11-30", "09:00", "10:00", "liber"),
    ]


def test_slot_generated_from_schedule_can_be_booked(
    client: TestClient,
    facility_id: int,
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)
    response = client.get(
        f"/facilitati/{facility_id}/sloturi",
        params={"de_la": "2026-11-30", "pana_la": "2026-11-30"},
    )
    slot = response.json()[0]["id"]
    _, headers = log_in("client.program@student.usv.ro")

    booking = client.post(
        "/rezervari",
        json={"slot_id": slot, "regulament_acceptat": True},
        headers=headers,
    )

    assert booking.status_code == 201


def test_inactive_facility_gets_no_generated_slots(
    client: TestClient, facility_id: int
) -> None:
    put_schedule(client, facility_id, MONDAY_MORNING)
    client.put(f"/facilitati/{facility_id}", json={**FACILITY, "status": "inactiva"})

    assert slots(client, facility_id, "2026-11-23", "2026-11-30") == []
