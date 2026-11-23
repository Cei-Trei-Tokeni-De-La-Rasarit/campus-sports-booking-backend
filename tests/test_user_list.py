"""Testele pentru lista utilizatorilor (GET /utilizatori)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

URL = "/utilizatori"
FACILITY = {"nume": "Sala", "sport": "Tenis", "locatie": "Corp A", "capacitate": 4}


@pytest.fixture
def people(
    client: TestClient,
    admin_headers: dict[str, str],
    log_in: Callable[..., tuple[int, dict[str, str]]],
) -> dict[str, int]:
    """Un client și un manager cu două săli alocate (plus administratorul)."""
    student, _ = log_in("ana.client@student.usv.ro")
    manager, _ = log_in("mihai.manager@usv.ro")
    halls = [
        client.post(
            "/facilitati", json={**FACILITY, "nume": f"Sala {n}"}, headers=admin_headers
        ).json()["id"]
        for n in (1, 2)
    ]
    response = client.put(
        f"{URL}/{manager}/rol",
        json={"rol": "manager", "facilitati_alocate": halls[::-1]},
        headers=admin_headers,
    )
    assert response.status_code == 200
    return {
        "student": student,
        "manager": manager,
        "hall1": halls[0],
        "hall2": halls[1],
    }


def emails(response) -> list[str]:
    """Emailurile din răspuns, în ordinea primită."""
    return sorted(user["email"] for user in response.json())


def test_list_users_returns_everyone_with_assigned_facilities(
    client: TestClient, admin_headers: dict[str, str], people: dict[str, int]
) -> None:
    response = client.get(URL, headers=admin_headers)

    assert response.status_code == 200
    by_id = {user["id"]: user for user in response.json()}
    assert len(by_id) == 3
    manager = by_id[people["manager"]]
    assert manager["rol"] == "manager"
    assert manager["facilitati_alocate"] == [people["hall1"], people["hall2"]]
    assert by_id[people["student"]]["facilitati_alocate"] == []
    assert by_id[people["student"]]["rol"] == "client"
    for user in by_id.values():
        assert set(user) == {
            "id",
            "nume",
            "email",
            "rol",
            "notificari_email",
            "facilitati_alocate",
        }


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("client", ["ana.client@student.usv.ro"]),
        ("manager", ["mihai.manager@usv.ro"]),
        ("administrator", ["admin.facilities@student.usv.ro"]),
    ],
)
def test_filter_by_role(
    client: TestClient,
    admin_headers: dict[str, str],
    people: dict[str, int],
    role: str,
    expected: list[str],
) -> None:
    response = client.get(URL, params={"rol": role}, headers=admin_headers)

    assert response.status_code == 200
    assert emails(response) == expected


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("MIHAI", ["mihai.manager@usv.ro"]),
        ("@usv.ro", ["mihai.manager@usv.ro"]),
        ("  ana.client  ", ["ana.client@student.usv.ro"]),
        ("nimeni", []),
        ("%", []),
        (
            "",
            [
                "admin.facilities@student.usv.ro",
                "ana.client@student.usv.ro",
                "mihai.manager@usv.ro",
            ],
        ),
    ],
)
def test_search_in_name_and_email(
    client: TestClient,
    admin_headers: dict[str, str],
    people: dict[str, int],
    search: str,
    expected: list[str],
) -> None:
    response = client.get(URL, params={"cautare": search}, headers=admin_headers)

    assert response.status_code == 200
    assert emails(response) == expected


def test_filters_combined(
    client: TestClient, admin_headers: dict[str, str], people: dict[str, int]
) -> None:
    response = client.get(
        URL, params={"rol": "client", "cautare": "mihai"}, headers=admin_headers
    )

    assert response.json() == []


@pytest.mark.parametrize("params", [{"rol": "student"}, {"cautare": "a" * 101}])
def test_invalid_filter_returns_400(
    client: TestClient, admin_headers: dict[str, str], params: dict[str, str]
) -> None:
    response = client.get(URL, params=params, headers=admin_headers)

    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")


def test_list_users_without_token_returns_401(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize("role", ["client", "manager"])
def test_list_users_for_non_admin_returns_403(
    client: TestClient,
    admin_headers: dict[str, str],
    log_in: Callable[..., tuple[int, dict[str, str]]],
    role: str,
) -> None:
    user_id, headers = log_in("cineva@student.usv.ro")
    if role == "manager":
        client.put(
            f"{URL}/{user_id}/rol", json={"rol": "manager"}, headers=admin_headers
        )

    assert client.get(URL, headers=headers).status_code == 403
