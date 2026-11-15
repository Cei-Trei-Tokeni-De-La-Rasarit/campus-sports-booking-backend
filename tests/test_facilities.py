"""Testele pentru facilități (/facilitati): CRUD și catalogul cu filtre."""

from collections.abc import Callable
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services import facility_service

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
    "program": "Luni-Vineri 08:00-22:00",
}


def count_facilities() -> int:
    """Numărul de facilități din baza de test, indiferent de status."""
    with engine.connect() as connection:
        return connection.scalar(text("SELECT COUNT(*) FROM facility"))


def create_facility(client: TestClient) -> dict:
    """Adaugă o facilitate prin API și o întoarce."""
    response = client.post("/facilitati", json=FACILITY)
    assert response.status_code == 201
    return response.json()


def test_list_facilities_is_empty_at_start(client: TestClient) -> None:
    response = client.get("/facilitati")

    assert response.status_code == 200
    assert response.json() == []


def test_create_facility_returns_201_with_data(client: TestClient) -> None:
    response = client.post("/facilitati", json=FACILITY)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["nume"] == FACILITY["nume"]
    assert data["capacitate"] == FACILITY["capacitate"]
    assert data["status"] == "activa"


def test_created_facility_appears_in_list(client: TestClient) -> None:
    facility = create_facility(client)

    response = client.get("/facilitati")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [facility["id"]]


def test_get_facility_returns_its_data(client: TestClient) -> None:
    facility = create_facility(client)

    response = client.get(f"/facilitati/{facility['id']}")

    assert response.status_code == 200
    assert response.json() == facility


def test_update_facility_changes_data(client: TestClient) -> None:
    facility = create_facility(client)
    changes = {**FACILITY, "capacitate": 6, "status": "inactiva"}

    response = client.put(f"/facilitati/{facility['id']}", json=changes)

    assert response.status_code == 200
    assert response.json()["capacitate"] == 6
    assert response.json()["status"] == "inactiva"
    saved = client.get(f"/facilitati/{facility['id']}").json()
    assert saved["capacitate"] == 6


def test_delete_facility_removes_it(client: TestClient) -> None:
    facility = create_facility(client)

    response = client.delete(f"/facilitati/{facility['id']}")

    assert response.status_code == 204
    assert client.get(f"/facilitati/{facility['id']}").status_code == 404


# Un id care nu există: tabelele sunt goale la începutul fiecărui test.
MISSING_ID = 9999


def test_get_missing_facility_returns_404(client: TestClient) -> None:
    response = client.get(f"/facilitati/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}


def test_update_missing_facility_returns_404_and_creates_nothing(
    client: TestClient,
) -> None:
    response = client.put(f"/facilitati/{MISSING_ID}", json=FACILITY)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}
    assert count_facilities() == 0


def test_delete_missing_facility_returns_404(client: TestClient) -> None:
    response = client.delete(f"/facilitati/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}


def test_delete_facility_with_time_slots_returns_409_and_keeps_it(
    client: TestClient, add_time_slot: Callable[[int], None]
) -> None:
    facility = create_facility(client)
    add_time_slot(facility["id"])

    response = client.delete(f"/facilitati/{facility['id']}")

    assert response.status_code == 409
    assert "inactiva" in response.json()["mesaj"]
    assert client.get(f"/facilitati/{facility['id']}").json() == facility


# Cazurile-limită pentru datele unei facilități (KAN-88).

REQUIRED_FIELDS = ["nume", "sport", "locatie", "capacitate"]
TEXT_FIELDS = ["nume", "sport", "locatie"]
# Lungimea maximă a fiecărui câmp text, ca în baza de date.
MAX_LENGTHS = {"nume": 100, "sport": 50, "locatie": 150, "program": 200}
# Un id mai mare decât poate stoca o coloană INT din PostgreSQL.
TOO_LARGE_ID = 99_999_999_999


def assert_invalid_data(client: TestClient, response) -> None:
    """Verifică răspunsul 400 și că nu s-a salvat nicio facilitate."""
    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert count_facilities() == 0


def test_create_facility_with_empty_body_returns_400(client: TestClient) -> None:
    response = client.post("/facilitati", json={})

    assert_invalid_data(client, response)


def test_create_facility_without_body_returns_400(client: TestClient) -> None:
    response = client.post("/facilitati")

    assert_invalid_data(client, response)


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_create_facility_with_missing_field_returns_400(
    client: TestClient, field: str
) -> None:
    data = {key: value for key, value in FACILITY.items() if key != field}

    response = client.post("/facilitati", json=data)

    assert_invalid_data(client, response)
    assert field in response.json()["mesaj"]


@pytest.mark.parametrize("field", [*REQUIRED_FIELDS, "status"])
def test_create_facility_with_null_field_returns_400(
    client: TestClient, field: str
) -> None:
    response = client.post("/facilitati", json={**FACILITY, field: None})

    assert_invalid_data(client, response)


@pytest.mark.parametrize("value", ["", "   "])
@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_create_facility_with_blank_text_returns_400(
    client: TestClient, field: str, value: str
) -> None:
    response = client.post("/facilitati", json={**FACILITY, field: value})

    assert_invalid_data(client, response)


@pytest.mark.parametrize("field", MAX_LENGTHS)
def test_create_facility_with_too_long_text_returns_400(
    client: TestClient, field: str
) -> None:
    too_long = "a" * (MAX_LENGTHS[field] + 1)

    response = client.post("/facilitati", json={**FACILITY, field: too_long})

    assert_invalid_data(client, response)


@pytest.mark.parametrize("field", MAX_LENGTHS)
def test_create_facility_with_text_at_max_length_returns_201(
    client: TestClient, field: str
) -> None:
    longest = "a" * MAX_LENGTHS[field]

    response = client.post("/facilitati", json={**FACILITY, field: longest})

    assert response.status_code == 201
    assert response.json()[field] == longest


def test_create_facility_strips_spaces_around_text(client: TestClient) -> None:
    data = {
        **FACILITY,
        "nume": "  Sala de tenis  ",
        "sport": " Tenis ",
        "locatie": " Corp A ",
        "program": " Luni-Vineri ",
    }

    response = client.post("/facilitati", json=data)

    assert response.status_code == 201
    saved = client.get(f"/facilitati/{response.json()['id']}").json()
    assert saved["nume"] == "Sala de tenis"
    assert saved["sport"] == "Tenis"
    assert saved["locatie"] == "Corp A"
    assert saved["program"] == "Luni-Vineri"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_create_facility_with_empty_schedule_saves_null(
    client: TestClient, value: str | None
) -> None:
    response = client.post("/facilitati", json={**FACILITY, "program": value})

    assert response.status_code == 201
    assert response.json()["program"] is None


@pytest.mark.parametrize("capacity", [0, -1, 1001])
def test_create_facility_with_capacity_out_of_range_returns_400(
    client: TestClient, capacity: int
) -> None:
    response = client.post("/facilitati", json={**FACILITY, "capacitate": capacity})

    assert_invalid_data(client, response)


@pytest.mark.parametrize("capacity", [1, 1000])
def test_create_facility_with_capacity_at_limit_returns_201(
    client: TestClient, capacity: int
) -> None:
    response = client.post("/facilitati", json={**FACILITY, "capacitate": capacity})

    assert response.status_code == 201
    assert response.json()["capacitate"] == capacity


@pytest.mark.parametrize("capacity", ["4", "patru", 4.5, 4.0, True, [4]])
def test_create_facility_with_wrong_capacity_type_returns_400(
    client: TestClient, capacity: object
) -> None:
    response = client.post("/facilitati", json={**FACILITY, "capacitate": capacity})

    assert_invalid_data(client, response)


@pytest.mark.parametrize("value", [123, True, ["Sala"]])
def test_create_facility_with_wrong_name_type_returns_400(
    client: TestClient, value: object
) -> None:
    response = client.post("/facilitati", json={**FACILITY, "nume": value})

    assert_invalid_data(client, response)


@pytest.mark.parametrize("status", ["inexistent", "active", "ACTIVA", ""])
def test_create_facility_with_unknown_status_returns_400(
    client: TestClient, status: str
) -> None:
    response = client.post("/facilitati", json={**FACILITY, "status": status})

    assert_invalid_data(client, response)


@pytest.mark.parametrize(
    "changes",
    [{"nume": "   "}, {"capacitate": 0}, {"capacitate": "6"}, {"status": "x"}],
)
def test_update_facility_with_invalid_data_returns_400_and_keeps_it(
    client: TestClient, changes: dict
) -> None:
    facility = create_facility(client)

    response = client.put(f"/facilitati/{facility['id']}", json={**FACILITY, **changes})

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert client.get(f"/facilitati/{facility['id']}").json() == facility


@pytest.mark.parametrize("facility_id", [0, -1, TOO_LARGE_ID])
@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_facility_with_impossible_id_returns_404(
    client: TestClient, method: str, facility_id: int
) -> None:
    response = client.request(method, f"/facilitati/{facility_id}", json=FACILITY)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}


def test_facility_with_text_id_returns_400(client: TestClient) -> None:
    response = client.get("/facilitati/abc")

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")


# Catalogul facilităților, cu filtre (KAN-54).


def add_facility(client: TestClient, **changes: object) -> int:
    """Adaugă o facilitate cu datele de bază plus modificările date; întoarce id-ul."""
    response = client.post("/facilitati", json={**FACILITY, **changes})
    assert response.status_code == 201
    return response.json()["id"]


def catalog_ids(client: TestClient, **filters: object) -> list[int]:
    """Cere catalogul cu filtrele date și întoarce id-urile primite."""
    response = client.get("/facilitati", params=filters)
    assert response.status_code == 200
    return [facility["id"] for facility in response.json()]


@pytest.mark.parametrize("status", ["inactiva", "mentenanta"])
def test_catalog_shows_only_active_facilities(client: TestClient, status: str) -> None:
    active = add_facility(client)
    add_facility(client, status=status)

    assert catalog_ids(client) == [active]


def test_catalog_search_matches_part_of_name_ignoring_case(
    client: TestClient,
) -> None:
    tennis = add_facility(client, nume="Sala de tenis Nr. 3")
    add_facility(client, nume="Bazin olimpic")

    assert catalog_ids(client, cautare="TENIS") == [tennis]
    assert catalog_ids(client, cautare="nr. 3") == [tennis]


def test_catalog_search_without_match_returns_empty_list(client: TestClient) -> None:
    add_facility(client)

    assert catalog_ids(client, cautare="fotbal") == []


@pytest.mark.parametrize("value", ["%", "_", "\\"])
def test_catalog_search_treats_sql_wildcards_as_text(
    client: TestClient, value: str
) -> None:
    add_facility(client, nume="Sala de tenis")
    with_symbol = add_facility(client, nume=f"Sala {value} 2")

    assert catalog_ids(client, cautare=value) == [with_symbol]


def test_catalog_filters_by_sport_ignoring_case(client: TestClient) -> None:
    tennis = add_facility(client, sport="Tenis")
    add_facility(client, sport="Tenis de masă")
    add_facility(client, sport="Înot")

    assert catalog_ids(client, sport="tenis") == [tennis]


def test_catalog_filters_by_minimum_capacity(client: TestClient) -> None:
    add_facility(client, capacitate=3)
    exact = add_facility(client, capacitate=4)
    larger = add_facility(client, capacitate=20)

    assert catalog_ids(client, capacitate_min=4) == [exact, larger]


def test_catalog_combines_filters(client: TestClient) -> None:
    match = add_facility(client, nume="Teren tenis 1", sport="Tenis", capacitate=4)
    add_facility(client, nume="Teren tenis 2", sport="Tenis", capacitate=2)
    add_facility(client, nume="Teren fotbal", sport="Fotbal", capacitate=22)

    assert catalog_ids(client, cautare="teren", sport="Tenis", capacitate_min=4) == [
        match
    ]


@pytest.mark.parametrize(
    "filters", [{"cautare": ""}, {"cautare": "   "}, {"sport": ""}]
)
def test_catalog_empty_filter_is_ignored(client: TestClient, filters: dict) -> None:
    facility = add_facility(client)

    assert catalog_ids(client, **filters) == [facility]


def test_catalog_ignores_unknown_parameters(client: TestClient) -> None:
    facility = add_facility(client)

    assert catalog_ids(client, necunoscut="x") == [facility]


@pytest.mark.parametrize("value", ["0", "-1", "1001", "abc", "4.5", ""])
def test_catalog_with_invalid_minimum_capacity_returns_400(
    client: TestClient, value: str
) -> None:
    response = client.get("/facilitati", params={"capacitate_min": value})

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert "capacitate_min" in response.json()["mesaj"]


@pytest.mark.parametrize(("name", "limit"), [("cautare", 100), ("sport", 50)])
def test_catalog_with_too_long_text_filter_returns_400(
    client: TestClient, name: str, limit: int
) -> None:
    response = client.get("/facilitati", params={name: "a" * (limit + 1)})

    assert response.status_code == 400
    assert name in response.json()["mesaj"]


# Filtrul disponibile_azi: ora de acum e fixată, ca testele să nu depindă de ceas.
NOW = datetime(2026, 12, 1, 12, 0)
TODAY = "2026-12-01"


@pytest.fixture
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Face ca „acum” să fie 1 decembrie 2026, ora 12:00 (ora României)."""
    monkeypatch.setattr(facility_service, "romania_now", lambda db: NOW)


def test_romania_now_comes_from_database(client: TestClient) -> None:
    with SessionLocal() as db:
        now = facility_service.romania_now(db)

    assert isinstance(now, datetime)
    assert now.tzinfo is None


@pytest.mark.usefixtures("fixed_now")
def test_catalog_available_today_keeps_facility_with_free_slot_later_today(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    available = add_facility(client)
    add_time_slot(available, TODAY, "14:00", "15:00", "free")
    add_facility(client)

    assert catalog_ids(client, disponibile_azi="true") == [available]


@pytest.mark.usefixtures("fixed_now")
@pytest.mark.parametrize(
    ("slot_date", "start", "end", "status"),
    [
        (TODAY, "14:00", "15:00", "booked"),
        (TODAY, "14:00", "15:00", "blocked"),
        (TODAY, "10:00", "11:00", "free"),
        (TODAY, "11:30", "12:30", "free"),
        (TODAY, "12:00", "13:00", "free"),
        ("2026-11-30", "14:00", "15:00", "free"),
        ("2026-12-02", "14:00", "15:00", "free"),
    ],
    ids=[
        "rezervat",
        "blocat",
        "s-a-terminat",
        "a-inceput",
        "incepe-acum",
        "ieri",
        "maine",
    ],
)
def test_catalog_available_today_skips_facility_without_bookable_slot_today(
    client: TestClient,
    add_time_slot: Callable[..., int],
    slot_date: str,
    start: str,
    end: str,
    status: str,
) -> None:
    facility = add_facility(client)
    add_time_slot(facility, slot_date, start, end, status)

    assert catalog_ids(client, disponibile_azi="true") == []


@pytest.mark.usefixtures("fixed_now")
def test_catalog_available_today_lists_facility_once_with_many_free_slots(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility = add_facility(client)
    add_time_slot(facility, TODAY, "14:00", "15:00", "free")
    add_time_slot(facility, TODAY, "16:00", "17:00", "free")

    assert catalog_ids(client, disponibile_azi="true") == [facility]


@pytest.mark.usefixtures("fixed_now")
def test_catalog_available_today_skips_inactive_facility(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    facility = add_facility(client, status="mentenanta")
    add_time_slot(facility, TODAY, "14:00", "15:00", "free")

    assert catalog_ids(client, disponibile_azi="true") == []


@pytest.mark.usefixtures("fixed_now")
def test_catalog_available_today_combines_with_other_filters(
    client: TestClient, add_time_slot: Callable[..., int]
) -> None:
    tennis = add_facility(client, sport="Tenis")
    football = add_facility(client, sport="Fotbal")
    add_time_slot(tennis, TODAY, "14:00", "15:00", "free")
    add_time_slot(football, TODAY, "14:00", "15:00", "free")

    assert catalog_ids(client, disponibile_azi="true", sport="tenis") == [tennis]


@pytest.mark.usefixtures("fixed_now")
def test_catalog_available_today_false_does_not_filter(
    client: TestClient,
) -> None:
    facility = add_facility(client)

    assert catalog_ids(client, disponibile_azi="false") == [facility]


@pytest.mark.parametrize("value", ["abc", "2", ""])
def test_catalog_with_invalid_available_today_returns_400(
    client: TestClient, value: str
) -> None:
    response = client.get("/facilitati", params={"disponibile_azi": value})

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert "disponibile_azi" in response.json()["mesaj"]
