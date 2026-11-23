"""Testele pentru regulile CORS (ce cereri poate trimite frontend-ul din browser)."""

import pytest
from fastapi.testclient import TestClient

FRONTEND = "http://localhost:5173"


def preflight(client: TestClient, origin: str, headers: str):
    """Cererea de verificare (OPTIONS) pe care browserul o trimite înainte de POST."""
    return client.options(
        "/facilitati",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": headers,
        },
    )


@pytest.mark.parametrize(
    "headers", ["content-type", "authorization", "authorization,content-type"]
)
def test_frontend_may_send_token_and_json(client: TestClient, headers: str) -> None:
    response = preflight(client, FRONTEND, headers)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    allowed = response.headers["access-control-allow-headers"].lower()
    for header in headers.split(","):
        assert header in allowed


def test_other_headers_are_refused(client: TestClient) -> None:
    response = preflight(client, FRONTEND, "x-header-necunoscut")

    assert response.status_code == 400


def test_unknown_origin_is_refused(client: TestClient) -> None:
    response = preflight(client, "http://site-strain.example", "authorization")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_simple_request_from_frontend_gets_cors_header(client: TestClient) -> None:
    response = client.get("/facilitati", headers={"Origin": FRONTEND})

    assert response.headers["access-control-allow-origin"] == FRONTEND


def test_frontend_may_send_patch(client: TestClient) -> None:
    # PATCH /notificari/{id} marchează o notificare ca citită.
    response = client.options(
        "/notificari/1",
        headers={
            "Origin": FRONTEND,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]
