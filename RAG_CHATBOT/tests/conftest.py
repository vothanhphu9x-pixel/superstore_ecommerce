import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.config import get_settings
from core.internal_auth import create_staff_user


@pytest.fixture
def auth_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret-key")
    monkeypatch.setenv("STAFF_DB_PATH", str(tmp_path / "staff.db"))
    monkeypatch.setenv("STAFF_JWT_SECRET", "a" * 64)
    monkeypatch.setenv("INTERNAL_EMAIL_DOMAINS", "company.com")
    monkeypatch.setenv("STAFF_COOKIE_SECURE", "false")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "api.log"))
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest.fixture
def api_headers():
    return {"X-API-Key": "test-secret-key"}


@pytest.fixture
def staff_credentials():
    return {
        "email": "staff@company.com",
        "password": "StrongPassword123!",
    }


@pytest.fixture
def client(auth_environment):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_staff(auth_environment, staff_credentials):
    def create(role="admin"):
        return create_staff_user(
            email=staff_credentials["email"],
            name="Staff User",
            role=role,
            password=staff_credentials["password"],
        )

    return create


@pytest.fixture
def login_staff(client, api_headers, staff_credentials):
    def login(password=None):
        return client.post(
            "/api/staff/login",
            headers=api_headers,
            json={
                "email": staff_credentials["email"],
                "password": (
                    staff_credentials["password"]
                    if password is None
                    else password
                ),
            },
        )

    return login