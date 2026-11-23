"""Testele pentru regulamentul unei facilități (citire și editare)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.schemas.regulation import MAX_REGULATION_LENGTH

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


# PUT /facilitati/{id}/regulament (KAN-110): administratorul sau managerul sălii.

NEW_TEXT = "1. Accesul se face cu încălțăminte de sală.\n2. Fără mâncare pe teren."


@pytest.fixture
def facility_id(client: TestClient, admin_headers: dict[str, str]) -> int:
    """O facilitate fără regulament."""
    return create_facility(client, admin_headers)


@pytest.fixture
def user_with_role(
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> Callable[[str], tuple[int, dict[str, str]]]:
    """Creează un cont cu rolul dat (valoarea din bază); întoarce id și header."""

    def create(role: str) -> tuple[int, dict[str, str]]:
        user_id, headers = log_in(f"{role}.regulament@usv.ro")
        with engine.begin() as connection:
            connection.execute(
                text('UPDATE "user" SET role = :role WHERE id = :id'),
                {"role": role, "id": user_id},
            )
        return user_id, headers

    return create


def put_regulation(
    client: TestClient, facility_id: object, data: object, headers: dict[str, str]
):
    """Trimite regulamentul nou al facilității."""
    return client.put(
        f"/facilitati/{facility_id}/regulament", json=data, headers=headers
    )


def regulations_in_db() -> list[tuple]:
    """Toate regulamentele din baza de test, ca (facilitate, text)."""
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT facility_id, content FROM regulation ORDER BY id")
        )
        return [tuple(row) for row in rows]


def test_admin_creates_regulation_for_facility_without_one(
    client: TestClient, admin_headers: dict[str, str], facility_id: int
) -> None:
    response = put_regulation(client, facility_id, {"text": NEW_TEXT}, admin_headers)

    assert response.status_code == 200
    assert response.json() == {"facilitate_id": facility_id, "text": NEW_TEXT}
    assert regulations_in_db() == [(facility_id, NEW_TEXT)]


def test_admin_replaces_existing_regulation(
    client: TestClient, admin_headers: dict[str, str], facility_id: int
) -> None:
    add_regulation(facility_id)

    response = put_regulation(client, facility_id, {"text": NEW_TEXT}, admin_headers)

    assert response.status_code == 200
    assert response.json()["text"] == NEW_TEXT
    assert regulations_in_db() == [(facility_id, NEW_TEXT)]
    public = client.get(f"/facilitati/{facility_id}/regulament")
    assert public.json()["text"] == NEW_TEXT


def test_changing_one_regulation_keeps_the_others(
    client: TestClient, admin_headers: dict[str, str], facility_id: int
) -> None:
    other_id = create_facility(client, admin_headers)
    add_regulation(other_id)

    put_regulation(client, facility_id, {"text": NEW_TEXT}, admin_headers)

    assert regulations_in_db() == [
        (other_id, REGULATION_TEXT),
        (facility_id, NEW_TEXT),
    ]


def test_text_is_trimmed_and_keeps_inner_lines(
    client: TestClient, admin_headers: dict[str, str], facility_id: int
) -> None:
    response = put_regulation(
        client, facility_id, {"text": f"  \n{NEW_TEXT}\n  "}, admin_headers
    )

    assert response.status_code == 200
    assert regulations_in_db() == [(facility_id, NEW_TEXT)]


def test_text_of_maximum_length_is_accepted(
    client: TestClient, admin_headers: dict[str, str], facility_id: int
) -> None:
    longest = "ă" * MAX_REGULATION_LENGTH

    response = put_regulation(client, facility_id, {"text": longest}, admin_headers)

    assert response.status_code == 200
    assert regulations_in_db() == [(facility_id, longest)]


def test_manager_edits_regulation_of_his_facility(
    client: TestClient,
    facility_id: int,
    user_with_role: Callable[[str], tuple[int, dict[str, str]]],
) -> None:
    manager_id, headers = user_with_role("manager")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO facility_manager (manager_id, facility_id) "
                "VALUES (:manager_id, :facility_id)"
            ),
            {"manager_id": manager_id, "facility_id": facility_id},
        )

    response = put_regulation(client, facility_id, {"text": NEW_TEXT}, headers)

    assert response.status_code == 200
    assert regulations_in_db() == [(facility_id, NEW_TEXT)]


def test_manager_cannot_edit_regulation_of_other_facility(
    client: TestClient,
    facility_id: int,
    user_with_role: Callable[[str], tuple[int, dict[str, str]]],
) -> None:
    add_regulation(facility_id)
    _, headers = user_with_role("manager")

    response = put_regulation(client, facility_id, {"text": NEW_TEXT}, headers)

    assert response.status_code == 403
    assert response.json() == {"mesaj": "Poți modifica doar facilitățile alocate ție."}
    assert regulations_in_db() == [(facility_id, REGULATION_TEXT)]


def test_client_cannot_edit_regulation(
    client: TestClient,
    facility_id: int,
    user_with_role: Callable[[str], tuple[int, dict[str, str]]],
) -> None:
    _, headers = user_with_role("user")

    response = put_regulation(client, facility_id, {"text": NEW_TEXT}, headers)

    assert response.status_code == 403
    assert response.json() == {
        "mesaj": "Nu ai permisiunile necesare pentru această acțiune."
    }
    assert regulations_in_db() == []


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer token-inventat"}],
    ids=["fara-token", "token-invalid"],
)
def test_edit_regulation_without_valid_token_returns_401(
    client: TestClient, facility_id: int, headers: dict[str, str]
) -> None:
    response = put_regulation(client, facility_id, {"text": NEW_TEXT}, headers)

    assert response.status_code == 401
    assert regulations_in_db() == []


@pytest.mark.parametrize("missing_id", [9999, 0, -1, 2_147_483_648])
def test_edit_regulation_of_missing_facility_returns_404(
    client: TestClient, admin_headers: dict[str, str], missing_id: int
) -> None:
    response = put_regulation(client, missing_id, {"text": NEW_TEXT}, admin_headers)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Facilitatea nu există."}
    assert regulations_in_db() == []


def test_edit_regulation_with_text_id_returns_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = put_regulation(client, "abc", {"text": NEW_TEXT}, admin_headers)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")


@pytest.mark.parametrize(
    "data",
    [
        {},
        None,
        [],
        "text",
        {"continut": NEW_TEXT},
        {"text": None},
        {"text": ""},
        {"text": "   "},
        {"text": "\n\t "},
        {"text": "a" * (MAX_REGULATION_LENGTH + 1)},
        {"text": 123},
        {"text": True},
        {"text": ["Regula 1"]},
        {"text": {"ro": NEW_TEXT}},
    ],
    ids=[
        "obiect-gol",
        "null",
        "lista",
        "text-simplu",
        "camp-gresit",
        "text-null",
        "text-gol",
        "doar-spatii",
        "doar-spatii-albe",
        "prea-lung",
        "numar",
        "boolean",
        "lista-in-text",
        "obiect-in-text",
    ],
)
def test_invalid_regulation_returns_400_and_keeps_the_old_one(
    client: TestClient, admin_headers: dict[str, str], facility_id: int, data: object
) -> None:
    add_regulation(facility_id)

    response = put_regulation(client, facility_id, data, admin_headers)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert regulations_in_db() == [(facility_id, REGULATION_TEXT)]


def test_too_long_text_names_the_limit(
    client: TestClient, admin_headers: dict[str, str], facility_id: int
) -> None:
    data = {"text": "a" * (MAX_REGULATION_LENGTH + 1)}

    response = put_regulation(client, facility_id, data, admin_headers)

    assert response.json() == {
        "mesaj": "Date invalide. text: textul poate avea cel mult 5000 de caractere"
    }
