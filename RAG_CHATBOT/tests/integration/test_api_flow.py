from core.internal_auth import change_staff_role


def test_login_role_change_relogin_and_logout_flow(
    client,
    make_staff,
    login_staff,
    api_headers,
):
    make_staff(role="marketing")

    first_login = login_staff()
    assert first_login.status_code == 200
    assert first_login.json()["role"] == "marketing"

    first_index = client.get(
        "/api/dashboard",
        headers=api_headers,
    )
    assert first_index.status_code == 200
    assert first_index.json()["metrics"] == []

    change_staff_role("staff@company.com", "admin")

    stale_session = client.get(
        "/api/dashboard",
        headers=api_headers,
    )
    assert stale_session.status_code == 401

    second_login = login_staff()
    assert second_login.status_code == 200
    assert second_login.json()["role"] == "admin"

    second_index = client.get(
        "/api/dashboard",
        headers=api_headers,
    )
    assert second_index.status_code == 200
    assert "kpi" in second_index.json()["metrics"]

    logout = client.post(
        "/api/staff/logout",
        headers=api_headers,
    )
    assert logout.status_code == 200

    after_logout = client.get(
        "/api/dashboard",
        headers=api_headers,
    )
    assert after_logout.status_code == 401