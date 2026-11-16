"""Testele pentru rolurile la modificarea facilităților (KAN-53, KAN-95).

Creare și ștergere: doar administrator. Editare: manager sau administrator.
Citirea (catalogul și detaliile) rămâne publică.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import ALGORITHM, SECRET_KEY
from app.database import engine

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}
CHANGED = {**FACILITY, "nume": "Sala de tenis renovată"}

FORBIDDEN = {"mesaj": "Nu ai permisiunile necesare pentru această acțiune."}

# Rolurile din API și valoarea lor din baza de date.
ROLE_IN_DB = {"client": "user", "manager": "manager", "administrator": "administrator"}


@pytest.fixture
def headers_for(
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> Callable[[str], dict[str, str]]:
    """Creează un cont cu rolul dat și întoarce header-ul cu token-ul lui.

    Același rol, cerut a doua oară în test, folosește contul deja creat.
    """
    created: dict[str, dict[str, str]] = {}

    def create(role: str) -> dict[str, str]:
        if role not in created:
            user_id, headers = log_in(f"{role}@usv.ro")
            with engine.begin() as connection:
                connection.execute(
                    text('UPDATE "user" SET role = :role WHERE id = :id'),
                    {"role": ROLE_IN_DB[role], "id": user_id},
                )
            created[role] = headers
        return created[role]

    return create


@pytest.fixture
def facility_id(client: TestClient, headers_for: Callable) -> int:
    """O facilitate existentă, adăugată de un administrator."""
    response = client.post(
        "/facilitati", json=FACILITY, headers=headers_for("administrator")
    )
    assert response.status_code == 201
    return response.json()["id"]


def send(client: TestClient, method: str, facility_id: int, headers: dict):
    """Trimite cererea de creare, editare sau ștergere cu header-ul dat."""
    if method == "POST":
        return client.post("/facilitati", json=FACILITY, headers=headers)
    if method == "PUT":
        return client.put(f"/facilitati/{facility_id}", json=CHANGED, headers=headers)
    return client.delete(f"/facilitati/{facility_id}", headers=headers)


def facilities_in_db() -> list[tuple]:
    """Toate facilitățile din baza de test, ca să vedem că nimic nu s-a schimbat."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT id, name, status FROM facility ORDER BY id")
        ).all()


def token(**claims: object) -> dict[str, str]:
    """Un header cu un token construit în test (de exemplu, expirat)."""
    key = claims.pop("key", SECRET_KEY)
    return {"Authorization": f"Bearer {jwt.encode(claims, key, ALGORITHM)}"}


METHODS = ["POST", "PUT", "DELETE"]
PAST = datetime.now(timezone.utc) - timedelta(hours=1)
FUTURE = datetime.now(timezone.utc) + timedelta(hours=1)


# Fără autentificare sau cu un token greșit: 401 și nimic schimbat.


@pytest.mark.parametrize("method", METHODS)
def test_change_facility_without_token_returns_401(
    client: TestClient, facility_id: int, method: str
) -> None:
    before = facilities_in_db()

    response = send(client, method, facility_id, {})

    assert response.status_code == 401
    assert response.json() == {"mesaj": "Lipsește token-ul de autentificare."}
    assert facilities_in_db() == before


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer token-inventat"},
        {"Authorization": "Basic YWRtaW46YWRtaW4="},
        token(sub="1", exp=PAST),
        token(sub="1", exp=FUTURE, key="alta-cheie-de-cel-putin-32-de-bytes!!"),
    ],
    ids=["inventat", "alta-schema", "expirat", "alta-cheie"],
)
def test_change_facility_with_invalid_token_returns_401(
    client: TestClient, facility_id: int, method: str, headers: dict
) -> None:
    before = facilities_in_db()

    response = send(client, method, facility_id, headers)

    assert response.status_code == 401
    assert facilities_in_db() == before


# Rolul client: 403 la toate și nimic schimbat.


@pytest.mark.parametrize("method", METHODS)
def test_client_cannot_change_facilities(
    client: TestClient, facility_id: int, headers_for: Callable, method: str
) -> None:
    headers = headers_for("client")
    before = facilities_in_db()

    response = send(client, method, facility_id, headers)

    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    assert facilities_in_db() == before


# Rolul manager: poate edita, dar nu poate crea sau șterge.


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_manager_cannot_create_or_delete_facilities(
    client: TestClient, facility_id: int, headers_for: Callable, method: str
) -> None:
    headers = headers_for("manager")
    before = facilities_in_db()

    response = send(client, method, facility_id, headers)

    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    assert facilities_in_db() == before


def test_manager_can_edit_facility(
    client: TestClient, facility_id: int, headers_for: Callable
) -> None:
    response = send(client, "PUT", facility_id, headers_for("manager"))

    assert response.status_code == 200
    assert response.json()["nume"] == CHANGED["nume"]
    assert facilities_in_db()[0][1] == CHANGED["nume"]


# Rolul administrator: poate face toate operațiile.


def test_administrator_can_create_facility(
    client: TestClient, facility_id: int, headers_for: Callable
) -> None:
    response = send(client, "POST", facility_id, headers_for("administrator"))

    assert response.status_code == 201
    assert len(facilities_in_db()) == 2


def test_administrator_can_edit_facility(
    client: TestClient, facility_id: int, headers_for: Callable
) -> None:
    response = send(client, "PUT", facility_id, headers_for("administrator"))

    assert response.status_code == 200
    assert facilities_in_db()[0][1] == CHANGED["nume"]


def test_administrator_can_delete_facility(
    client: TestClient, facility_id: int, headers_for: Callable
) -> None:
    response = send(client, "DELETE", facility_id, headers_for("administrator"))

    assert response.status_code == 204
    assert facilities_in_db() == []


# Citirea rămâne publică.


def test_reading_facilities_needs_no_token(
    client: TestClient, facility_id: int
) -> None:
    assert client.get("/facilitati").status_code == 200
    assert client.get(f"/facilitati/{facility_id}").status_code == 200
    params = {"de_la": "2026-12-01", "pana_la": "2026-12-07"}
    assert (
        client.get(f"/facilitati/{facility_id}/sloturi", params=params).status_code
        == 200
    )


# Lista completă pentru administrare: GET /facilitati/toate.


def test_list_all_facilities_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/facilitati/toate")

    assert response.status_code == 401


def test_client_cannot_list_all_facilities(
    client: TestClient, headers_for: Callable
) -> None:
    response = client.get("/facilitati/toate", headers=headers_for("client"))

    assert response.status_code == 403
    assert response.json() == FORBIDDEN


@pytest.mark.parametrize("role", ["manager", "administrator"])
def test_list_all_facilities_includes_inactive_ones(
    client: TestClient, headers_for: Callable, role: str
) -> None:
    admin = headers_for("administrator")
    for status in ["activa", "mentenanta", "inactiva"]:
        response = client.post(
            "/facilitati", json={**FACILITY, "status": status}, headers=admin
        )
        assert response.status_code == 201

    response = client.get("/facilitati/toate", headers=headers_for(role))

    assert response.status_code == 200
    assert [facility["status"] for facility in response.json()] == [
        "activa",
        "mentenanta",
        "inactiva",
    ]
    # Catalogul public rămâne doar cu sălile active.
    assert len(client.get("/facilitati").json()) == 1
