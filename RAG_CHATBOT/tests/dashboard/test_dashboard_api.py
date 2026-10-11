from analytics.dashboard_queries import DASHBOARD_QUERIES


def test_dashboard_index_and_metric_follow_staff_role(
    client,
    make_staff,
    login_staff,
    api_headers,
):
    make_staff(role="marketing")
    assert login_staff().status_code == 200

    index = client.get(
        "/api/dashboard",
        headers=api_headers,
    )
    metric = client.get(
        "/api/dashboard/kpi",
        headers=api_headers,
    )

    assert index.status_code == 200
    assert index.json()["metrics"] == []
    assert index.json()["contracts"] == {}
    assert metric.status_code == 403


def test_authorized_metric_uses_session_without_snowflake(
    client,
    make_staff,
    login_staff,
    api_headers,
    monkeypatch,
):
    make_staff()
    assert login_staff().status_code == 200

    async def fake_kpi(**params):
        assert params == {
            "month_from": 20230101,
            "month_to": 20231201,
        }
        return {
            "REVENUE": 100,
            "GROSS_PROFIT": 20,
            "ORDERS": 2,
            "AVG_ORDER_VALUE": 50,
            "MARGIN_PCT": 20,
        }

    monkeypatch.setitem(DASHBOARD_QUERIES, "kpi", fake_kpi)

    response = client.get(
        "/api/dashboard/kpi"
        "?month_from=20230101&month_to=20231201",
        headers=api_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["REVENUE"] == 100
    assert response.json()["cached"] is False


def test_unknown_metric_returns_404(
    client, make_staff, login_staff, api_headers
):
    make_staff()
    assert login_staff().status_code == 200

    response = client.get(
        "/api/dashboard/not-a-metric",
        headers=api_headers,
    )

    assert response.status_code == 404


def test_invalid_month_returns_422(
    client, make_staff, login_staff, api_headers
):
    make_staff()
    assert login_staff().status_code == 200

    response = client.get(
        "/api/dashboard/kpi"
        "?month_from=20230115&month_to=20231201",
        headers=api_headers,
    )

    assert response.status_code == 422


def test_invalid_query_payload_returns_502(
    client,
    make_staff,
    login_staff,
    api_headers,
    monkeypatch,
):
    make_staff()
    assert login_staff().status_code == 200

    async def incomplete_kpi(**_params):
        return {"REVENUE": 100}

    monkeypatch.setitem(
        DASHBOARD_QUERIES,
        "kpi",
        incomplete_kpi,
    )

    response = client.get(
        "/api/dashboard/kpi",
        headers=api_headers,
    )

    assert response.status_code == 502
    assert "Data contract failed" in response.json()["detail"]


def test_query_failure_returns_502(
    client,
    make_staff,
    login_staff,
    api_headers,
    monkeypatch,
):
    make_staff()
    assert login_staff().status_code == 200

    async def failed_kpi(**_params):
        raise RuntimeError("test query failure")

    monkeypatch.setitem(
        DASHBOARD_QUERIES,
        "kpi",
        failed_kpi,
    )

    response = client.get(
        "/api/dashboard/kpi",
        headers=api_headers,
    )

    assert response.status_code == 502
    assert "Unable to load metric" in response.json()["detail"]