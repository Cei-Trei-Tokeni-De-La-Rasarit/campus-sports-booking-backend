"""Testele pentru calendarul unei facilități (GET /facilitati/{id}/sloturi)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}
# O săptămână din decembrie 2026, de luni până duminică.
WEEK = {"de_la": "2026-11-30", "pana_la": "2026-12-06"}


def create_facility(client: TestClient) -> int:
    """Adaugă o facilitate prin API și întoarce id-ul ei."""
    response = client.post("/facilitati", json=FACILITY)
    assert response.status_code == 201
    return response.json()["id"]


def get_slots(client: TestClient, facility_id: int, **period: str):
    """Cere calendarul facilității pentru perioada dată."""
    return client.get(f"/facilitati/{facility_id}/sloturi", params=period)


def assert_invalid_data(response) -> None:
    """Verifică răspunsul 400 în formatul din specificație."""
    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")


def test_list_slots_returns_slot_data_in_romanian(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility_id = create_facility(client)
    slot_id = add_time_slot(facility_id, "2026-12-02", "12:00", "13:00", "free")

    response = get_slots(client, facility_id, **WEEK)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": slot_id,
            "facilitate_id": facility_id,
            "data": "2026-12-02",
            "ora_start": "12:00",
            "ora_sfarsit": "13:00",
            "stare": "liber",
        }
    ]


@pytest.mark.parametrize(
    ("db_status", "api_status"),
    [("free", "liber"), ("booked", "rezervat"), ("blocked", "blocat")],
)
def test_list_slots_translates_status(
    client: TestClient,
    add_time_slot: Callable[..., int],
    db_status: str,
    api_status: str,
) -> None:
    facility_id = create_facility(client)
    add_time_slot(facility_id, "2026-12-02", status=db_status)

    response = get_slots(client, facility_id, **WEEK)

    assert [slot["stare"] for slot in response.json()] == [api_status]


def test_list_slots_are_ordered_by_date_and_hour(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility_id = create_facility(client)
    later = add_time_slot(facility_id, "2026-12-03", "09:00", "10:00")
    afternoon = add_time_slot(facility_id, "2026-12-02", "18:00", "19:00")
    morning = add_time_slot(facility_id, "2026-12-02", "08:00", "09:00")

    response = get_slots(client, facility_id, **WEEK)

    assert [slot["id"] for slot in response.json()] == [morning, afternoon, later]


def test_list_slots_includes_both_ends_of_the_period(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility_id = create_facility(client)
    first_day = add_time_slot(facility_id, "2026-11-30")
    last_day = add_time_slot(facility_id, "2026-12-06")
    add_time_slot(facility_id, "2026-11-29")
    add_time_slot(facility_id, "2026-12-07")

    response = get_slots(client, facility_id, **WEEK)

    assert [slot["id"] for slot in response.json()] == [first_day, last_day]


def test_list_slots_for_a_single_day(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility_id = create_facility(client)
    slot_id = add_time_slot(facility_id, "2026-12-02")
    add_time_slot(facility_id, "2026-12-03")

    response = get_slots(client, facility_id, de_la="2026-12-02", pana_la="2026-12-02")

    assert [slot["id"] for slot in response.json()] == [slot_id]


def test_list_slots_returns_only_slots_of_that_facility(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility_id = create_facility(client)
    other_facility_id = create_facility(client)
    slot_id = add_time_slot(facility_id, "2026-12-02")
    add_time_slot(other_facility_id, "2026-12-02")

    response = get_slots(client, facility_id, **WEEK)

    assert [slot["id"] for slot in response.json()] == [slot_id]


def test_list_slots_without_slots_returns_empty_list(client: TestClient) -> None:
    facility_id = create_facility(client)

    response = get_slots(client, facility_id, **WEEK)

    assert response.status_code == 200
    assert response.json() == []


def test_list_slots_for_period_of_31_days_returns_200(client: TestClient) -> None:
    facility_id = create_facility(client)

    response = get_slots(client, facility_id, de_la="2026-12-01", pana_la="2026-12-31")

    assert response.status_code == 200


def test_list_slots_for_period_longer_than_31_days_returns_400(
    client: TestClient,
) -> None:
    facility_id = create_facility(client)

    response = get_slots(client, facility_id, de_la="2026-12-01", pana_la="2027-01-01")

    assert_invalid_data(response)
    assert "31" in response.json()["mesaj"]


def test_list_slots_with_start_after_end_returns_400(client: TestClient) -> None:
    facility_id = create_facility(client)

    response = get_slots(client, facility_id, de_la="2026-12-06", pana_la="2026-11-30")

    assert_invalid_data(response)


@pytest.mark.parametrize("missing", ["de_la", "pana_la"])
def test_list_slots_without_date_returns_400(client: TestClient, missing: str) -> None:
    facility_id = create_facility(client)
    period = {key: value for key, value in WEEK.items() if key != missing}

    response = get_slots(client, facility_id, **period)

    assert_invalid_data(response)
    assert missing in response.json()["mesaj"]


@pytest.mark.parametrize("value", ["abc", "2026-13-01", "2026-02-30", "01.12.2026", ""])
def test_list_slots_with_invalid_date_returns_400(
    client: TestClient, value: str
) -> None:
    facility_id = create_facility(client)

    response = get_slots(client, facility_id, de_la=value, pana_la="2026-12-06")

    assert_invalid_data(response)


@pytest.mark.parametrize("facility_id", [9999, 0, -1, 99_999_999_999])
def test_list_slots_of_missing_facility_returns_404(
    client: TestClient, facility_id: int
) -> None:
    response = get_slots(client, facility_id, **WEEK)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}
