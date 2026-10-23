import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.operations import router
from core.config import get_settings
from core.observability import ObservabilityMiddleware


def test_operations_and_redacted_request_logging(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "APP_LOG_DIR",
        str(tmp_path),
    )
    get_settings.cache_clear()

    logger = logging.getLogger(
        "superstore.http"
    )

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    app = FastAPI()

    app.include_router(router)
    app.add_middleware(
        ObservabilityMiddleware
    )

    @app.get("/test/{item_id}")
    def sample(item_id: str):
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get(
            "/test/private-value"
            "?password=never-log-this",
            headers={
                "X-API-Key": "never-log-this",
                "Cookie": (
                    "superstore_staff="
                    "never-log-this"
                ),
            },
        )

        assert response.status_code == 200

        request_id = response.headers[
            "x-request-id"
        ]

        assert len(request_id) == 32

        health = client.get(
            "/api/health/live"
        )

        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        metrics = client.get(
            "/metrics"
        ).text

        assert (
            "superstore_http_requests_total"
            in metrics
        )

        assert (
            'route="/test/{item_id}"'
            in metrics
        )

    logs = (
        tmp_path / "http.log"
    ).read_text()

    assert "never-log-this" not in logs
    assert "private-value" not in logs
    assert "/test/{item_id}" in logs
