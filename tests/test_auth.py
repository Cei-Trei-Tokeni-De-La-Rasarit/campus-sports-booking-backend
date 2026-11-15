"""Teste de integrare pentru endpoint-ul POST /auth/register."""

import pytest
from fastapi.testclient import TestClient


def test_register_success_student_email(client: TestClient) -> None:
    """Înregistrare reușită cu email @student.usv.ro; parola nu este expusă."""
    payload = {
        "name": "Ion Popescu",
        "email": "Ion.Popescu@student.usv.ro",
        "password": "parolaSigura123",
        "email_notifications": True,
    }
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ion Popescu"
    assert body["email"] == "ion.popescu@student.usv.ro"
    assert body["role"] == "user"
    assert body["email_notifications"] is True
    assert isinstance(body["id"], int)
    assert "password" not in body
    assert "password_hash" not in body


def test_register_success_staff_email_with_defaults(client: TestClient) -> None:
    """Înregistrare reușită cu @usv.ro și valoarea implicită pentru notificări."""
    payload = {
        "name": "Maria Ionescu",
        "email": "maria.ionescu@usv.ro",
        "password": "parolaSigura123",
    }
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "maria.ionescu@usv.ro"
    assert body["role"] == "user"
    assert body["email_notifications"] is False


def test_register_strips_spaces_around_name_and_email(client: TestClient) -> None:
    """Spațiile de la începutul și sfârșitul numelui/emailului sunt eliminate."""
    payload = {
        "name": "  Andrei Vasile  ",
        "email": "  Andrei.Vasile@student.usv.ro  ",
        "password": "parolaSigura123",
    }
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Andrei Vasile"
    assert body["email"] == "andrei.vasile@student.usv.ro"


def test_register_ignores_role_escalation_attempt(client: TestClient) -> None:
    """Un utilizator nou primește mereu rolul 'user', chiar dacă trimite alt rol."""
    payload = {
        "name": "Tentativa Admin",
        "email": "admin.fals@student.usv.ro",
        "password": "parolaSigura123",
        "role": "administrator",
    }
    response = client.post("/auth/register", json=payload)

    assert response.status_code in (201, 400)
    if response.status_code == 201:
        assert response.json()["role"] == "user"


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    """Un email deja existent (inclusiv cu majuscule diferite) returnează 409."""
    first = client.post(
        "/auth/register",
        json={
            "name": "Ion Popescu",
            "email": "duplicat@student.usv.ro",
            "password": "parolaSigura123",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={
            "name": "Alt Nume",
            "email": "DUPLICAT@student.usv.ro",
            "password": "altaParola123",
        },
    )
    assert second.status_code == 409


@pytest.mark.parametrize(
    "invalid_email",
    [
        "utilizator@gmail.com",
        "utilizator@yahoo.com",
        "student@fakeusv.ro",
        "student@fake-student.usv.ro",
        "student@student.usv.ro.evil.com",
        "student@usv.com",
        "nu-este-email",
        "",
        "   ",
    ],
)
def test_register_non_institutional_or_invalid_email_returns_400(
    client: TestClient, invalid_email: str
) -> None:
    """Adresele din afara domeniilor USV sau malformate sunt respinse cu 400."""
    response = client.post(
        "/auth/register",
        json={
            "name": "Utilizator Test",
            "email": invalid_email,
            "password": "parolaSigura123",
        },
    )
    assert response.status_code == 400


def test_register_with_empty_or_missing_body_returns_400(client: TestClient) -> None:
    """Cererile fără body sau cu JSON gol returnează 400."""
    assert client.post("/auth/register").status_code == 400
    assert client.post("/auth/register", json={}).status_code == 400


@pytest.mark.parametrize("missing_field", ["name", "email", "password"])
def test_register_with_missing_field_returns_400(
    client: TestClient, missing_field: str
) -> None:
    """Lipsa oricărui câmp obligatoriu returnează 400."""
    payload = {
        "name": "Ion Popescu",
        "email": "complet@student.usv.ro",
        "password": "parolaSigura123",
    }
    del payload[missing_field]

    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400


@pytest.mark.parametrize(
    "null_field", ["name", "email", "password", "email_notifications"]
)
def test_register_with_null_field_returns_400(
    client: TestClient, null_field: str
) -> None:
    """Transmiterea valorii null pentru orice câmp returnează 400."""
    payload: dict[str, object] = {
        "name": "Ion Popescu",
        "email": "nulltest@student.usv.ro",
        "password": "parolaSigura123",
        "email_notifications": False,
    }
    payload[null_field] = None

    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400


@pytest.mark.parametrize("blank_name", ["", "   ", "\t\n"])
def test_register_with_blank_name_returns_400(
    client: TestClient, blank_name: str
) -> None:
    """Un nume gol sau format doar din spații returnează 400."""
    response = client.post(
        "/auth/register",
        json={
            "name": blank_name,
            "email": "nume.gol@student.usv.ro",
            "password": "parolaSigura123",
        },
    )
    assert response.status_code == 400


def test_register_name_length_boundaries(client: TestClient) -> None:
    """Verifică limitele de lungime ale numelui (minim 2, maxim 100 caractere)."""
    too_short = client.post(
        "/auth/register",
        json={
            "name": "A",
            "email": "nume.scurt@student.usv.ro",
            "password": "parolaSigura123",
        },
    )
    assert too_short.status_code == 400

    at_max = client.post(
        "/auth/register",
        json={
            "name": "A" * 100,
            "email": "nume.maxim@student.usv.ro",
            "password": "parolaSigura123",
        },
    )
    assert at_max.status_code == 201

    too_long = client.post(
        "/auth/register",
        json={
            "name": "A" * 101,
            "email": "nume.lung@student.usv.ro",
            "password": "parolaSigura123",
        },
    )
    assert too_long.status_code == 400


def test_register_password_length_boundaries(client: TestClient) -> None:
    """Verifică limitele de lungime ale parolei (sub minim și peste maxim)."""
    too_short = client.post(
        "/auth/register",
        json={
            "name": "Ion Popescu",
            "email": "parola.scurta@student.usv.ro",
            "password": "12345",
        },
    )
    assert too_short.status_code == 400

    valid_min = client.post(
        "/auth/register",
        json={
            "name": "Ion Popescu",
            "email": "parola.valida@student.usv.ro",
            "password": "parola12",
        },
    )
    assert valid_min.status_code == 201

    too_long = client.post(
        "/auth/register",
        json={
            "name": "Ion Popescu",
            "email": "parola.lunga@student.usv.ro",
            "password": "x" * 129,
        },
    )
    assert too_long.status_code == 400


@pytest.mark.parametrize(
    "bad_payload",
    [
        {
            "name": 12345,
            "email": "tip.gresit1@student.usv.ro",
            "password": "parolaSigura123",
        },
        {
            "name": ["Ion"],
            "email": "tip.gresit2@student.usv.ro",
            "password": "parolaSigura123",
        },
        {
            "name": "Ion Popescu",
            "email": 999,
            "password": "parolaSigura123",
        },
        {
            "name": "Ion Popescu",
            "email": "tip.gresit3@student.usv.ro",
            "password": "parolaSigura123",
            "email_notifications": "nu-este-bool",
        },
    ],
)
def test_register_with_wrong_field_types_returns_400(
    client: TestClient, bad_payload: dict[str, object]
) -> None:
    """Tipurile de date invalide în JSON sunt respinse cu 400."""
    response = client.post("/auth/register", json=bad_payload)
    assert response.status_code == 400
