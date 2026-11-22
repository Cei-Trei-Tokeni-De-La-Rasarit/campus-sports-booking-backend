"""Testele pentru mesajele de validare (400) în română și pentru răspunsurile
cu facilități care au în baza de date valori din afara limitelor de la intrare.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.validation_messages import count_with_noun, translate_message

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}

# Bucăți din mesajele în engleză ale lui Pydantic, care nu trebuie să apară.
ENGLISH_WORDS = ("should", "Field required", "Input", "Value error", "invalid ")


@pytest.fixture(autouse=True)
def authenticate_as_admin(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Folosește un administrator pentru operațiile protejate."""
    client.headers.update(admin_headers)


def insert_facility(capacity: int, name: str = "Sala veche") -> int:
    """Adaugă o facilitate direct în SQL, ocolind validările API-ului."""
    with engine.begin() as connection:
        return connection.scalar(
            text(
                "INSERT INTO facility (name, sport, location, capacity, status) "
                "VALUES (:name, 'Tenis', 'Corp A', :capacity, 'active') RETURNING id"
            ),
            {"name": name, "capacity": capacity},
        )


def assert_romanian(message: str) -> None:
    """Mesajul începe cu „Date invalide.” și nu conține texte în engleză."""
    assert message.startswith("Date invalide. ")
    for word in ENGLISH_WORDS:
        assert word not in message


# Răspunsurile cu facilități: limitele de la intrare nu se aplică la ieșire.


@pytest.mark.parametrize("capacity", [1001, 50000])
def test_catalog_shows_facility_with_unusual_capacity(
    client: TestClient, capacity: int
) -> None:
    unusual = insert_facility(capacity)
    normal = client.post("/facilitati", json=FACILITY).json()["id"]

    response = client.get("/facilitati")

    assert response.status_code == 200
    by_id = {facility["id"]: facility for facility in response.json()}
    assert by_id[unusual]["capacitate"] == capacity
    assert normal in by_id


def test_facility_with_empty_name_in_database_is_returned(client: TestClient) -> None:
    facility_id = insert_facility(10, name="   ")

    for path in (f"/facilitati/{facility_id}", "/facilitati/toate"):
        assert client.get(path).status_code == 200


def test_input_limits_still_apply_on_create(client: TestClient) -> None:
    response = client.post("/facilitati", json={**FACILITY, "capacitate": 1500})

    assert response.status_code == 400
    assert response.json()["mesaj"] == (
        "Date invalide. capacitate: valoarea poate fi cel mult 1000"
    )


# Mesajele de validare, prin API.


def test_messages_for_several_fields_are_in_romanian(client: TestClient) -> None:
    response = client.post(
        "/facilitati", json={**FACILITY, "nume": "  ", "capacitate": 0}
    )

    assert response.status_code == 400
    assert response.json()["mesaj"] == (
        "Date invalide. nume: textul trebuie să aibă cel puțin 1 caracter; "
        "capacitate: valoarea trebuie să fie cel puțin 1"
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"sport": "Tenis"}, "nume: câmpul este obligatoriu"),
        (
            {**FACILITY, "nume": "a" * 101},
            "nume: textul poate avea cel mult 100 de caractere",
        ),
        ({**FACILITY, "capacitate": "4"}, "capacitate: valoarea trebuie să fie un"),
        ({**FACILITY, "status": "x"}, "'activa', 'mentenanta' sau 'inactiva'"),
        ({**FACILITY, "nume": 5}, "nume: valoarea trebuie să fie text"),
    ],
)
def test_facility_validation_messages(
    client: TestClient, body: dict, expected: str
) -> None:
    response = client.post("/facilitati", json=body)

    assert response.status_code == 400
    assert expected in response.json()["mesaj"]
    assert_romanian(response.json()["mesaj"])


def test_invalid_json_body_has_romanian_message(client: TestClient) -> None:
    response = client.post(
        "/facilitati",
        content="{nu e json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert "corpul cererii nu este un JSON valid" in response.json()["mesaj"]
    assert_romanian(response.json()["mesaj"])


def test_path_parameter_is_named_id(client: TestClient) -> None:
    response = client.get("/facilitati/abc")

    assert response.status_code == 400
    assert response.json()["mesaj"] == (
        "Date invalide. id: valoarea trebuie să fie un număr întreg"
    )


def test_query_parameter_message(client: TestClient) -> None:
    response = client.get("/facilitati", params={"disponibile_azi": "poate"})

    assert response.status_code == 400
    assert response.json()["mesaj"] == (
        "Date invalide. disponibile_azi: valoarea trebuie să fie true sau false"
    )


def test_own_message_has_no_value_error_prefix(client: TestClient) -> None:
    response = client.post(
        "/rezervari", json={"slot_id": 1, "regulament_acceptat": False}
    )

    assert response.status_code == 400
    assert response.json()["mesaj"] == (
        "Date invalide. regulament_acceptat: Trebuie să accepți regulamentul sălii."
    )


def test_invalid_email_has_romanian_message(client: TestClient) -> None:
    response = client.post(
        "/auth/autentificare", json={"email": "fara-arond", "parola": "orice123"}
    )

    assert response.status_code == 400
    assert "email: adresa de email nu este validă" in response.json()["mesaj"]
    assert_romanian(response.json()["mesaj"])


def test_invalid_date_in_query_has_romanian_message(client: TestClient) -> None:
    facility_id = client.post("/facilitati", json=FACILITY).json()["id"]

    response = client.get(
        f"/facilitati/{facility_id}/sloturi",
        params={"de_la": "ieri", "pana_la": "2026-11-30"},
    )

    assert response.status_code == 400
    assert "data trebuie să fie în formatul AAAA-LL-ZZ" in response.json()["mesaj"]
    assert_romanian(response.json()["mesaj"])


# Funcțiile ajutătoare, direct.


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "1 caracter"),
        (2, "2 caractere"),
        (19, "19 caractere"),
        (20, "20 de caractere"),
        (100, "100 de caractere"),
        (101, "101 caractere"),
        (150, "150 de caractere"),
    ],
)
def test_count_with_noun(count: int, expected: str) -> None:
    assert count_with_noun(count, "caracter", "caractere") == expected


def test_unknown_error_type_gets_general_message() -> None:
    assert translate_message({"type": "tip_nou", "msg": "Something"}) == (
        "valoare invalidă"
    )
