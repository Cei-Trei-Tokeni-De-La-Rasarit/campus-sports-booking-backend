"""Testele pentru antetele de securitate de pe răspunsurile API (KAN-126)."""

import pytest
from fastapi.testclient import TestClient

from app.security_headers import API_CSP, DOCS_CSP

COMMON = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


def assert_security_headers(response, csp: str = API_CSP) -> None:
    """Răspunsul are toate antetele de securitate, cu CSP-ul dat."""
    for name, value in COMMON.items():
        assert response.headers[name] == value
    assert response.headers["content-security-policy"] == csp


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/", 200),
        ("GET", "/facilitati", 200),
        ("GET", "/facilitati/999999", 404),
        ("GET", "/facilitati/abc", 400),
        ("GET", "/rezervari", 401),
        ("POST", "/rezervari", 401),
        ("GET", "/nu-exista", 404),
        ("GET", "/openapi.json", 200),
    ],
)
def test_responses_have_security_headers(
    client: TestClient, method: str, path: str, status: int
) -> None:
    response = client.request(method, path)

    assert response.status_code == status
    assert_security_headers(response)


def test_validation_error_has_security_headers(client: TestClient) -> None:
    response = client.post("/auth/autentificare", json={"email": "x"})

    assert response.status_code == 400
    assert_security_headers(response)


def test_cors_preflight_has_security_headers(client: TestClient) -> None:
    response = client.options(
        "/facilitati",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert_security_headers(response)


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_documentation_pages_get_the_docs_csp(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert_security_headers(response, csp=DOCS_CSP)


def test_docs_csp_allows_what_swagger_loads(client: TestClient) -> None:
    html = client.get("/docs").text

    # Pagina Swagger încarcă scripturile și stilurile de pe cdn.jsdelivr.net,
    # pe care CSP-ul documentației trebuie să le permită.
    assert "https://cdn.jsdelivr.net/npm/swagger-ui-dist" in html
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in DOCS_CSP
    assert "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in DOCS_CSP


def test_api_csp_forbids_everything_and_framing() -> None:
    assert API_CSP == "default-src 'none'; frame-ancestors 'none'"
    assert "frame-ancestors 'none'" in DOCS_CSP
