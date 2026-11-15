"""Testele pentru operațiile CRUD pe facilități (/facilitati)."""

from collections.abc import Callable

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
