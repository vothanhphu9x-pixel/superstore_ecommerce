from fastapi.testclient import TestClient

from analytics.contracts import METRIC_CONTRACTS
from api.app import app
from api.routers import staff as staff_router
from core.config import get_settings
from core.internal_auth import change_staff_role


def test_missing_api_configuration_fails_closed(
    client, api_headers, monkeypatch
):
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()

    response = client.get("/api/dashboard", headers=api_headers)

    assert response.status_code == 503


def test_missing_request_key_is_forbidden(client):
    response = client.get("/api/dashboard")

    assert response.status_code == 403


def test_wrong_request_key_is_forbidden(client):
    response = client.get(
        "/api/dashboard",
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 403


def test_api_key_without_staff_session_is_unauthorized(
    client, api_headers
):
    response = client.get("/api/dashboard", headers=api_headers)

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Staff authentication is required"
    )


def test_login_requires_api_key(
    client, make_staff, staff_credentials
):
    make_staff()

    response = client.post(
        "/api/staff/login",
        json=staff_credentials,
    )

    assert response.status_code == 403
    assert "superstore_staff" not in response.cookies


def test_wrong_password_does_not_create_session(
    make_staff, login_staff
):
    make_staff()

    response = login_staff(password="wrong-password")

    assert response.status_code == 401
    assert "superstore_staff" not in response.cookies


def test_valid_login_sets_cookie_and_unlocks_index(
    client,
    make_staff,
    login_staff,
    api_headers,
):
    make_staff()

    login = login_staff()

    assert login.status_code == 200
    assert login.json()["role"] == "admin"
    assert set(login.json()["metrics"]) == set(METRIC_CONTRACTS)
    assert "superstore_staff" in login.cookies
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=lax" in login.headers["set-cookie"].lower()

    me = client.get("/api/staff/me", headers=api_headers)
    index = client.get("/api/dashboard", headers=api_headers)

    assert me.status_code == 200
    assert me.json()["email"] == "staff@company.com"
    assert index.status_code == 200
    assert set(index.json()["metrics"]) == set(METRIC_CONTRACTS)


def test_login_uses_new_redis_client_after_restart(
    make_staff, api_headers, staff_credentials
):
    make_staff()

    with TestClient(app) as first_client:
        first_redis = app.state.rate_limit_redis
        first_login = first_client.post(
            "/api/staff/login",
            headers=api_headers,
            json=staff_credentials,
        )
        assert first_login.status_code == 200

    with TestClient(app) as second_client:
        assert app.state.rate_limit_redis is not first_redis
        second_login = second_client.post(
            "/api/staff/login",
            headers=api_headers,
            json=staff_credentials,
        )
        assert second_login.status_code == 200


def test_login_fails_closed_when_redis_is_unavailable(
    client, make_staff, api_headers, staff_credentials, monkeypatch
):
    class UnavailableRedis:
        async def eval(self, *_args):
            raise ConnectionError("Redis unavailable")

    make_staff()
    monkeypatch.setattr(
        client.app.state,
        "rate_limit_redis",
        UnavailableRedis(),
    )

    response = client.post(
        "/api/staff/login",
        headers=api_headers,
        json=staff_credentials,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Login is temporarily unavailable"


def test_staff_cookie_does_not_replace_api_key(
    client, make_staff, login_staff
):
    make_staff()
    assert login_staff().status_code == 200

    response = client.get("/api/dashboard")

    assert response.status_code == 403


def test_invalid_staff_cookie_is_unauthorized(
    client, api_headers
):
    client.cookies.set("superstore_staff", "invalid-token")

    response = client.get(
        "/api/dashboard",
        headers=api_headers,
    )

    assert response.status_code == 401


def test_role_change_invalidates_existing_cookie(
    client,
    make_staff,
    login_staff,
    api_headers,
):
    make_staff()
    assert login_staff().status_code == 200

    change_staff_role("staff@company.com", "sales")
    response = client.get(
        "/api/dashboard",
        headers=api_headers,
    )

    assert response.status_code == 401


def test_logout_clears_cookie_and_session(
    client,
    make_staff,
    login_staff,
    api_headers,
):
    make_staff()
    assert login_staff().status_code == 200

    logout = client.post(
        "/api/staff/logout",
        headers=api_headers,
    )
    dashboard = client.get(
        "/api/dashboard",
        headers=api_headers,
    )

    assert logout.status_code == 200
    assert "superstore_staff" in logout.headers["set-cookie"]
    assert dashboard.status_code == 401


def test_login_rate_limit_returns_429(
    client, api_headers, staff_credentials, monkeypatch
):
    async def deny_request(**_kwargs):
        return False

    monkeypatch.setattr(
        staff_router,
        "allow_request",
        deny_request,
    )

    response = client.post(
        "/api/staff/login",
        headers=api_headers,
        json=staff_credentials,
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
