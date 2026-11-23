"""Testele pentru schimbarea rolului și alocarea facilităților (KAN-94).

`PUT /utilizatori/{id}/rol` este doar pentru administrator. Pentru rolul
manager, `facilitati_alocate` spune ce facilități poate edita managerul.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine

FACILITY = {
    "nume": "Sala de tenis Nr. 3",
    "sport": "Tenis",
    "locatie": "Corp A",
    "capacitate": 4,
}

FORBIDDEN = {"mesaj": "Nu ai permisiunile necesare pentru această acțiune."}


@pytest.fixture
def facilities(client: TestClient, admin_headers: dict[str, str]) -> list[int]:
    """Trei facilități existente, adăugate de administrator."""
    ids = []
    for number in range(1, 4):
        response = client.post(
            "/facilitati",
            json={**FACILITY, "nume": f"Sala {number}"},
            headers=admin_headers,
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])
    return ids


@pytest.fixture
def user(
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> tuple[int, dict[str, str]]:
    """Un client obișnuit: id-ul lui și header-ul cu token-ul lui."""
    return log_in("ana.ionescu@student.usv.ro")


def change_role(
    client: TestClient, user_id: object, data: object, headers: dict[str, str]
):
    """Trimite cererea de schimbare a rolului."""
    return client.put(f"/utilizatori/{user_id}/rol", json=data, headers=headers)


def role_in_db(user_id: int) -> str:
    """Rolul utilizatorului, așa cum este salvat în baza de date."""
    with engine.connect() as connection:
        return connection.scalar(
            text('SELECT role FROM "user" WHERE id = :id'), {"id": user_id}
        )


def assigned_in_db(user_id: int) -> list[int]:
    """Facilitățile alocate utilizatorului, din tabelul facility_manager."""
    with engine.connect() as connection:
        return list(
            connection.scalars(
                text(
                    "SELECT facility_id FROM facility_manager "
                    "WHERE manager_id = :id ORDER BY facility_id"
                ),
                {"id": user_id},
            )
        )


# Cazurile reușite.


def test_admin_makes_client_a_manager_with_facilities(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
) -> None:
    user_id, _ = user

    response = change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": facilities[:2]},
        admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": user_id,
        "nume": "Andrei Popescu",
        "email": "ana.ionescu@student.usv.ro",
        "rol": "manager",
        "notificari_email": False,
    }
    assert role_in_db(user_id) == "manager"
    assert assigned_in_db(user_id) == facilities[:2]


def test_new_list_replaces_the_old_allocations(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
) -> None:
    user_id, _ = user
    change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": facilities[:2]},
        admin_headers,
    )

    response = change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": [facilities[2]]},
        admin_headers,
    )

    assert response.status_code == 200
    assert assigned_in_db(user_id) == [facilities[2]]


@pytest.mark.parametrize(
    "data",
    [{"rol": "manager"}, {"rol": "manager", "facilitati_alocate": None}],
    ids=["fara-lista", "lista-null"],
)
def test_manager_without_list_has_no_facilities(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
    data: dict,
) -> None:
    user_id, _ = user
    change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": facilities},
        admin_headers,
    )

    response = change_role(client, user_id, data, admin_headers)

    assert response.status_code == 200
    assert role_in_db(user_id) == "manager"
    assert assigned_in_db(user_id) == []


def test_manager_with_empty_list_has_no_facilities(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
) -> None:
    user_id, _ = user

    response = change_role(
        client, user_id, {"rol": "manager", "facilitati_alocate": []}, admin_headers
    )

    assert response.status_code == 200
    assert assigned_in_db(user_id) == []


@pytest.mark.parametrize(
    ("role", "role_in_database"),
    [("client", "user"), ("administrator", "administrator")],
)
def test_manager_who_loses_the_role_loses_his_facilities(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
    role: str,
    role_in_database: str,
) -> None:
    user_id, _ = user
    change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": facilities},
        admin_headers,
    )

    response = change_role(client, user_id, {"rol": role}, admin_headers)

    assert response.status_code == 200
    assert response.json()["rol"] == role
    assert role_in_db(user_id) == role_in_database
    assert assigned_in_db(user_id) == []


def test_changing_one_manager_keeps_the_others(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    log_in: Callable[..., tuple[int, dict[str, str]]],
    facilities: list[int],
) -> None:
    user_id, _ = user
    other_id, _ = log_in("mihai.rusu@student.usv.ro")
    for manager_id in (user_id, other_id):
        change_role(
            client,
            manager_id,
            {"rol": "manager", "facilitati_alocate": [facilities[0]]},
            admin_headers,
        )

    change_role(client, user_id, {"rol": "client"}, admin_headers)

    assert assigned_in_db(other_id) == [facilities[0]]


def test_new_role_applies_to_the_existing_token(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
) -> None:
    user_id, headers = user
    change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": [facilities[0]]},
        admin_headers,
    )

    assigned = client.put(
        f"/facilitati/{facilities[0]}", json=FACILITY, headers=headers
    )
    other = client.put(f"/facilitati/{facilities[1]}", json=FACILITY, headers=headers)

    assert assigned.status_code == 200
    assert other.status_code == 403
    assert client.get("/utilizatori/eu", headers=headers).json()["rol"] == "manager"


def test_deleted_facility_disappears_from_allocations(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
) -> None:
    user_id, _ = user
    change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": facilities[:2]},
        admin_headers,
    )

    response = client.delete(f"/facilitati/{facilities[0]}", headers=admin_headers)

    assert response.status_code == 204
    assert assigned_in_db(user_id) == [facilities[1]]


# Conflict: administratorul nu își schimbă propriul rol.


@pytest.mark.parametrize("role", ["client", "manager", "administrator"])
def test_admin_cannot_change_own_role(
    client: TestClient, log_in: Callable[..., tuple[int, dict[str, str]]], role: str
) -> None:
    admin_id, headers = log_in("admin.roluri@usv.ro")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE \"user\" SET role = 'administrator' WHERE id = :id"),
            {"id": admin_id},
        )

    response = change_role(client, admin_id, {"rol": role}, headers)

    assert response.status_code == 409
    assert "propriul rol" in response.json()["mesaj"]
    assert role_in_db(admin_id) == "administrator"
    assert assigned_in_db(admin_id) == []


def test_admin_can_change_role_of_another_admin(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
) -> None:
    user_id, _ = user
    change_role(client, user_id, {"rol": "administrator"}, admin_headers)

    response = change_role(client, user_id, {"rol": "client"}, admin_headers)

    assert response.status_code == 200
    assert role_in_db(user_id) == "user"


# Utilizator inexistent sau id greșit în adresă.


@pytest.mark.parametrize("user_id", [999, 0, -1, 2_147_483_648])
def test_change_role_of_missing_user_returns_404(
    client: TestClient, admin_headers: dict[str, str], user_id: int
) -> None:
    response = change_role(client, user_id, {"rol": "client"}, admin_headers)

    assert response.status_code == 404
    assert response.json() == {"mesaj": "Utilizatorul nu există."}


def test_change_role_with_text_id_returns_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = change_role(client, "abc", {"rol": "client"}, admin_headers)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")


# Date invalide: 400 și nimic schimbat.


@pytest.mark.parametrize(
    "data",
    [
        {},
        None,
        [],
        {"facilitati_alocate": [1]},
        {"rol": None},
        {"rol": ""},
        {"rol": "   "},
        {"rol": "student"},
        {"rol": "user"},
        {"rol": "Manager"},
        {"rol": 1},
        {"rol": "manager", "facilitati_alocate": "1"},
        {"rol": "manager", "facilitati_alocate": 1},
        {"rol": "manager", "facilitati_alocate": {"id": 1}},
        {"rol": "manager", "facilitati_alocate": ["1"]},
        {"rol": "manager", "facilitati_alocate": [1.0]},
        {"rol": "manager", "facilitati_alocate": [True]},
        {"rol": "manager", "facilitati_alocate": [None]},
        {"rol": "manager", "facilitati_alocate": [0]},
        {"rol": "manager", "facilitati_alocate": [-1]},
        {"rol": "manager", "facilitati_alocate": [2_147_483_648]},
    ],
)
def test_invalid_data_returns_400(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    data: object,
) -> None:
    user_id, _ = user

    response = change_role(client, user_id, data, admin_headers)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert role_in_db(user_id) == "user"
    assert assigned_in_db(user_id) == []


@pytest.mark.parametrize("role", ["client", "administrator"])
def test_facilities_for_another_role_return_400(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
    role: str,
) -> None:
    user_id, _ = user

    response = change_role(
        client,
        user_id,
        {"rol": role, "facilitati_alocate": [facilities[0]]},
        admin_headers,
    )

    assert response.status_code == 400
    assert "doar pentru rolul manager" in response.json()["mesaj"]
    assert role_in_db(user_id) == "user"


def test_empty_list_for_another_role_returns_400(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
) -> None:
    user_id, _ = user

    response = change_role(
        client, user_id, {"rol": "client", "facilitati_alocate": []}, admin_headers
    )

    assert response.status_code == 400
    assert "doar pentru rolul manager" in response.json()["mesaj"]


def test_repeated_facility_returns_400(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
) -> None:
    user_id, _ = user
    repeated = [facilities[0], facilities[1], facilities[0]]

    response = change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": repeated},
        admin_headers,
    )

    assert response.status_code == 400
    assert "o singură dată" in response.json()["mesaj"]
    assert role_in_db(user_id) == "user"
    assert assigned_in_db(user_id) == []


def test_missing_facility_returns_400_and_changes_nothing(
    client: TestClient,
    admin_headers: dict[str, str],
    user: tuple[int, dict[str, str]],
    facilities: list[int],
) -> None:
    user_id, _ = user
    change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": [facilities[0]]},
        admin_headers,
    )

    response = change_role(
        client,
        user_id,
        {"rol": "manager", "facilitati_alocate": [facilities[1], 998, 999]},
        admin_headers,
    )

    assert response.status_code == 400
    assert response.json() == {
        "mesaj": "Date invalide. facilitati_alocate: facilitățile 998, 999 nu există."
    }
    # Alocarea veche rămâne neschimbată.
    assert assigned_in_db(user_id) == [facilities[0]]


# Autentificare și rol: doar administratorul poate schimba roluri.


def test_change_role_without_token_returns_401(
    client: TestClient, user: tuple[int, dict[str, str]]
) -> None:
    user_id, _ = user

    response = change_role(client, user_id, {"rol": "manager"}, {})

    assert response.status_code == 401
    assert role_in_db(user_id) == "user"


@pytest.mark.parametrize("role_in_database", ["user", "manager"])
def test_only_admin_can_change_roles(
    client: TestClient,
    log_in: Callable[..., tuple[int, dict[str, str]]],
    user: tuple[int, dict[str, str]],
    role_in_database: str,
) -> None:
    user_id, _ = user
    caller_id, headers = log_in("apelant@usv.ro")
    with engine.begin() as connection:
        connection.execute(
            text('UPDATE "user" SET role = :role WHERE id = :id'),
            {"role": role_in_database, "id": caller_id},
        )

    response = change_role(client, user_id, {"rol": "administrator"}, headers)

    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    assert role_in_db(user_id) == "user"


def test_client_cannot_make_himself_admin(
    client: TestClient, user: tuple[int, dict[str, str]]
) -> None:
    user_id, headers = user

    response = change_role(client, user_id, {"rol": "administrator"}, headers)

    assert response.status_code == 403
    assert role_in_db(user_id) == "user"
