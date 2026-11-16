"""Testele pentru regulamentul unei facilități."""

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}
REGULATION_TEXT = "Este obligatoriu echipamentul sportiv adecvat."


def create_facility(client: TestClient, admin_headers: dict[str, str]) -> int:
    """Adaugă o facilitate prin API și întoarce id-ul ei."""
    response = client.post("/facilitati", json=FACILITY, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


def add_regulation(facility_id: int) -> None:
    """Adaugă regulamentul direct în baza de test."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO regulation (facility_id, content) "
                "VALUES (:facility_id, :content)"
            ),
            {"facility_id": facility_id, "content": REGULATION_TEXT},
        )


def test_get_facility_regulation_returns_text_without_authentication(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    facility_id = create_facility(client, admin_headers)
    add_regulation(facility_id)

    response = client.get(f"/facilitati/{facility_id}/regulament")

    assert response.status_code == 200
    assert response.json() == {
        "facilitate_id": facility_id,
        "text": REGULATION_TEXT,
    }


def test_get_regulation_for_missing_facility_returns_404(
    client: TestClient,
) -> None:
    response = client.get("/facilitati/9999/regulament")

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}


def test_get_regulation_for_facility_without_regulation_returns_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    facility_id = create_facility(client, admin_headers)

    response = client.get(f"/facilitati/{facility_id}/regulament")

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu are regulament."}


def test_get_regulation_with_invalid_id_returns_400(client: TestClient) -> None:
    response = client.get("/facilitati/abc/regulament")

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
