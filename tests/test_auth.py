"""Testele pentru crearea unui cont (POST /auth/inregistrare)."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import ALGORITHM, SECRET_KEY
from app.database import engine

URL = "/auth/inregistrare"
ACCOUNT = {
    "nume": "Andrei Popescu",
    "email": "andrei.popescu@student.usv.ro",
    "parola": "parola-sigura",
}


def register(client: TestClient, **changes: object):
    """Trimite cererea de înregistrare cu datele de bază, plus modificările date."""
    return client.post(URL, json={**ACCOUNT, **changes})


def count_users() -> int:
    """Numărul de conturi din baza de test."""
    with engine.connect() as connection:
        return connection.scalar(text('SELECT COUNT(*) FROM "user"'))


def assert_invalid_data(response) -> None:
    """Verifică răspunsul 400 și că nu s-a creat niciun cont."""
    assert response.status_code == 400
    assert response.json()["mesaj"].startswith("Date invalide.")
    assert count_users() == 0


def test_register_returns_201_with_user_data(client: TestClient) -> None:
    response = register(client)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data == {
        "id": data["id"],
        "nume": "Andrei Popescu",
        "email": "andrei.popescu@student.usv.ro",
        "rol": "client",
        "notificari_email": False,
    }


def test_register_saves_bcrypt_hash_not_password(client: TestClient) -> None:
    register(client)

    with engine.connect() as connection:
        saved = connection.scalar(text('SELECT password_hash FROM "user"'))
    assert saved != ACCOUNT["parola"]
    assert bcrypt.checkpw(ACCOUNT["parola"].encode(), saved.encode())


def test_register_response_has_no_password(client: TestClient) -> None:
    response = register(client)

    assert "parola" not in response.json()
    assert "password_hash" not in response.json()


def test_register_with_email_notifications(client: TestClient) -> None:
    response = register(client, notificari_email=True)

    assert response.status_code == 201
    assert response.json()["notificari_email"] is True


def test_register_ignores_role_sent_by_client(client: TestClient) -> None:
    response = register(client, rol="administrator")

    assert response.status_code == 201
    assert response.json()["rol"] == "client"


@pytest.mark.parametrize(
    "email", ["andrei.popescu@student.usv.ro", "andrei.popescu@usv.ro"]
)
def test_register_accepts_institutional_domains(client: TestClient, email: str) -> None:
    assert register(client, email=email).status_code == 201


def test_register_trims_name_and_lowercases_email(client: TestClient) -> None:
    response = register(
        client, nume="  Andrei Popescu  ", email="Andrei.Popescu@Student.USV.ro"
    )

    assert response.json()["nume"] == "Andrei Popescu"
    assert response.json()["email"] == "andrei.popescu@student.usv.ro"


def test_register_with_existing_email_returns_409(client: TestClient) -> None:
    register(client)

    response = register(client, nume="Alt Nume")

    assert response.status_code == 409
    assert response.json() == {
        "mesaj": "Există deja un cont înregistrat cu această adresă de email."
    }
    assert count_users() == 1


def test_register_with_same_email_in_capitals_returns_409(
    client: TestClient,
) -> None:
    register(client)

    response = register(client, email="ANDREI.POPESCU@STUDENT.USV.RO")

    assert response.status_code == 409


@pytest.mark.parametrize(
    "email",
    [
        "andrei@gmail.com",
        "andrei@usv.ro.example.com",
        "andrei@fakeusv.ro",
        "andrei@student.usv.com",
    ],
)
def test_register_with_non_institutional_email_returns_400(
    client: TestClient, email: str
) -> None:
    response = register(client, email=email)

    assert_invalid_data(response)
    assert "instituționale" in response.json()["mesaj"]


@pytest.mark.parametrize("email", ["andrei", "andrei@", "@usv.ro", ""])
def test_register_with_invalid_email_returns_400(
    client: TestClient, email: str
) -> None:
    assert_invalid_data(register(client, email=email))


def test_register_with_password_of_8_characters_returns_201(
    client: TestClient,
) -> None:
    assert register(client, parola="a" * 8).status_code == 201


def test_register_with_password_of_7_characters_returns_400(
    client: TestClient,
) -> None:
    assert_invalid_data(register(client, parola="a" * 7))


def test_register_with_password_of_72_characters_returns_201(
    client: TestClient,
) -> None:
    assert register(client, parola="a" * 72).status_code == 201


def test_register_with_password_of_73_characters_returns_400(
    client: TestClient,
) -> None:
    assert_invalid_data(register(client, parola="a" * 73))


def test_register_with_password_over_72_bytes_returns_400(
    client: TestClient,
) -> None:
    # 40 de litere „ă” au 40 de caractere, dar 80 de bytes.
    assert_invalid_data(register(client, parola="ă" * 40))


@pytest.mark.parametrize("name", ["", "   ", "A", "A" * 101])
def test_register_with_invalid_name_returns_400(client: TestClient, name: str) -> None:
    assert_invalid_data(register(client, nume=name))


@pytest.mark.parametrize("field", ["nume", "email", "parola"])
def test_register_without_field_returns_400(client: TestClient, field: str) -> None:
    data = {key: value for key, value in ACCOUNT.items() if key != field}

    response = client.post(URL, json=data)

    assert_invalid_data(response)
    assert field in response.json()["mesaj"]


@pytest.mark.parametrize("field", ["nume", "email", "parola"])
def test_register_with_null_field_returns_400(client: TestClient, field: str) -> None:
    assert_invalid_data(register(client, **{field: None}))


@pytest.mark.parametrize("field", ["nume", "email", "parola"])
def test_register_with_number_instead_of_text_returns_400(
    client: TestClient, field: str
) -> None:
    assert_invalid_data(register(client, **{field: 12345678}))


@pytest.mark.parametrize("value", ["da", 1, None])
def test_register_with_invalid_notifications_returns_400(
    client: TestClient, value: object
) -> None:
    assert_invalid_data(register(client, notificari_email=value))


def test_register_with_empty_body_returns_400(client: TestClient) -> None:
    assert_invalid_data(client.post(URL, json={}))


def test_register_without_body_returns_400(client: TestClient) -> None:
    assert_invalid_data(client.post(URL))


def test_login_returns_token_and_current_user(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/autentificare",
        json={"email": ACCOUNT["email"], "parola": ACCOUNT["parola"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token"]
    assert data["utilizator"]["rol"] == "client"
    assert "parola" not in data["utilizator"]
    assert "password_hash" not in data["utilizator"]

    me_response = client.get(
        "/utilizatori/eu",
        headers={"Authorization": f"Bearer {data['token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == data["utilizator"]


def test_login_with_invalid_credentials_returns_401(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/autentificare",
        json={"email": ACCOUNT["email"], "parola": "parola-gresita"},
    )

    assert response.status_code == 401


def test_me_without_token_returns_401(client: TestClient) -> None:
    register(client)

    response = client.get("/utilizatori/eu")

    assert response.status_code == 401
    assert response.json()["mesaj"] == "Lipsește token-ul de autentificare."


def login(client: TestClient, **changes: object):
    """Autentifică utilizatorul de test, cu modificări opționale."""
    data = {"email": ACCOUNT["email"], "parola": ACCOUNT["parola"]}
    data.update(changes)
    return client.post("/auth/autentificare", json=data)


def test_login_unknown_email_uses_same_error_as_wrong_password(
    client: TestClient,
) -> None:
    register(client)
    wrong_password = login(client, parola="parola-gresita")
    unknown_email = login(client, email="necunoscut@student.usv.ro")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert unknown_email.json() == wrong_password.json()


@pytest.mark.parametrize("field", ["email", "parola"])
@pytest.mark.parametrize("value", [None, ""])
def test_login_with_null_or_empty_field_returns_400(
    client: TestClient, field: str, value: object
) -> None:
    register(client)
    assert login(client, **{field: value}).status_code == 400


@pytest.mark.parametrize("field", ["email", "parola"])
def test_login_with_missing_field_returns_400(client: TestClient, field: str) -> None:
    register(client)
    data = {"email": ACCOUNT["email"], "parola": ACCOUNT["parola"]}
    del data[field]

    assert client.post("/auth/autentificare", json=data).status_code == 400


@pytest.mark.parametrize("password", ["a" * 73, "ă" * 40])
def test_login_with_password_over_72_bytes_returns_400(
    client: TestClient, password: str
) -> None:
    register(client)

    assert login(client, parola=password).status_code == 400


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        ),
        jwt.encode({"sub": "1"}, SECRET_KEY, algorithm=ALGORITHM),
        jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            "wrong-secret-for-tests-32-bytes!!",
            algorithm=ALGORITHM,
        ),
    ],
)
def test_me_with_invalid_token_returns_401(client: TestClient, token: str) -> None:
    register(client)

    response = client.get(
        "/utilizatori/eu", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_deleted_user_cannot_use_existing_token(client: TestClient) -> None:
    register(client)
    token = login(client).json()["token"]

    with engine.begin() as connection:
        connection.execute(
            text('DELETE FROM "user" WHERE email = :email'),
            {"email": ACCOUNT["email"]},
        )

    response = client.get(
        "/utilizatori/eu", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
