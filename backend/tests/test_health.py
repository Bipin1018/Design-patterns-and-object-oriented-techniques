"""Smoke test for the health endpoint.

Run from the backend/ directory:  pytest
Passes whether or not PostgreSQL is up — it asserts the contract, not the
environment. With Compose running, db is "ok"; with it stopped, db is "fail".
"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_returns_200_and_a_valid_db_field() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["db"] in {"ok", "fail"}
    assert payload["status"] in {"ok", "degraded"}


def test_status_and_db_agree() -> None:
    payload = client.get("/health").json()

    assert (payload["status"] == "ok") == (payload["db"] == "ok")


def test_swagger_is_disabled_and_scalar_is_served() -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404

    scalar = client.get("/scalar")
    assert scalar.status_code == 200
    assert "scalar" in scalar.text.lower()


def test_openapi_documents_health() -> None:
    schema = client.get("/openapi.json").json()

    assert "/health" in schema["paths"]
    assert "/scalar" not in schema["paths"]
