from fastapi.testclient import TestClient

from api.app import app
from core.config import get_settings


client = TestClient(app)


def test_missing_api_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()

    response = client.get("/api/dashboard")

    assert response.status_code == 503


def test_missing_request_key_is_forbidden(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret-key")
    get_settings.cache_clear()

    response = client.get("/api/dashboard")

    assert response.status_code == 403


def test_wrong_request_key_is_forbidden(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret-key")
    get_settings.cache_clear()

    response = client.get(
        "/api/dashboard",
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 403


def test_correct_request_key_can_read_contract(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret-key")
    get_settings.cache_clear()

    response = client.get(
        "/api/dashboard",
        headers={"X-API-Key": "test-secret-key"},
    )

    assert response.status_code == 200
    assert "kpi" in response.json()["metrics"]