"""HTTP metrics and structured request logs for a single worker."""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid

from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from prometheus_client import Counter, Histogram
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from core.config import BASE_DIR, get_settings


REQUESTS = Counter(
    "superstore_http_requests_total",
    "Completed HTTP requests",
    ["method", "route", "status"],
)

DURATION = Histogram(
    "superstore_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(
        0.01,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2,
        5,
        10,
        15,
        30,
    ),
)

EXCLUDED_PATHS = {
    "/metrics",
    "/api/health/live",
    "/api/health/ready",
}

KNOWN_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "fastapi",
            "event": "http_request",
            **getattr(record, "fields", {}),
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
        )


def request_logger() -> logging.Logger:
    logger = logging.getLogger("superstore.http")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)

    log_directory = get_settings().app_log_dir

    if log_directory:
        directory = Path(log_directory)
        if not directory.is_absolute():
            directory = BASE_DIR / directory
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = RotatingFileHandler(
            directory / "http.log",
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.logger = request_logger()

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ):
        if (
            scope["type"] != "http"
            or scope["path"] in EXCLUDED_PATHS
        ):
            return await self.app(
                scope,
                receive,
                send,
            )

        request_id = uuid.uuid4().hex

        scope.setdefault(
            "state",
            {},
        )["request_id"] = request_id

        started = time.perf_counter()

        status_code = 500
        error_type = None
        error_frames = None

        async def observed_send(message: Message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]

                headers = list(
                    message.get("headers", [])
                )

                headers.append(
                    (
                        b"x-request-id",
                        request_id.encode(),
                    )
                )

                message["headers"] = headers

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                observed_send,
            )

        except Exception as exc:
            status_code = 500
            error_type = type(exc).__name__

            error_frames = [
                {
                    "file": Path(frame.filename).name,
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(
                    exc.__traceback__
                )[-12:]
            ]

            raise

        finally:
            elapsed = time.perf_counter() - started

            route = getattr(
                scope.get("route"),
                "path",
                "unmatched",
            )

            method = scope.get("method", "OTHER")

            if method not in KNOWN_METHODS:
                method = "OTHER"

            REQUESTS.labels(
                method,
                route,
                str(status_code),
            ).inc()

            DURATION.labels(
                method,
                route,
            ).observe(elapsed)

            log_level = (
                logging.ERROR
                if status_code >= 500
                else logging.INFO
            )

            self.logger.log(
                log_level,
                "http_request",
                extra={
                    "fields": {
                        "request_id": request_id,
                        "method": method,
                        "route": route,
                        "status": status_code,
                        "duration_ms": round(
                            elapsed * 1000,
                            2,
                        ),
                        "error_type": error_type,
                        "error_frames": error_frames,
                    }
                },
            )
