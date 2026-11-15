"""Testele pentru operațiile CRUD pe facilități (/facilitati)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
    "program": "Luni-Vineri 08:00-22:00",
}


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
    assert client.get("/facilitati").json() == []


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
    assert client.get("/facilitati").json() == []


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
